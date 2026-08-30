#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
provenance.py — Agent OS 统一 provenance_ref 解析与机器真相验证。

【背景】agent-os-vault 桥此前接受 Vault frontmatter 里任意 provenance_ref
（如 "evidence.jsonl:999:abcd"）并写入 registry —— 伪造引用可绕过溯源。
本模块提供**只信任机器真相源**的 provenance 验证接口：
  1) 解析 provenance_ref（两种格式）
  2) 从真实源文件（ontology JSONL / evidence.jsonl / evolution artifact）定位记录
  3) **重新计算**记录的指纹（绝不采用 Vault/调用方自带的 hash）
  4) 比对声明指纹与机器重算指纹 → valid/invalid + 原因

【格式】
  <file>:<line>:<fp16>      —— JSONL（entities.jsonl / relations.jsonl / evidence.jsonl）
  <file>::<artifact_id>     —— .agent-os/evolution artifact（change/proposal/...）
  EVD-xxxx / EXP-xxx       —— 抽象证据/经验 ID（需在 evidence.jsonl 存在方能解析）

【信任边界】
  - provenance_ref 的 file/line 只是"定位线索"，不构成信任。
  - 必须重算 SHA-256 指纹并与声明比对；fingerprint 不匹配 → reject。
  - 源记录不存在 / 行号无记录 / 指纹不合 → reject。

【职责边界】纯只读验证；不写证据、不写 JSONL、不持有状态。
"""

import os
import re as _re

_HEX_RE = _re.compile(r"^[0-9a-fA-F]+$")
_ID_RE = _re.compile(r"^(EVD|EXP|DEC)-[A-Za-z0-9_-]+$")


try:
    # 与 ontology.py / agent-os-vault 共用同一 canonical（保证指纹规则唯一）
    from skills._lib.canonical import (
        canonical_json, sha256, fp16,
        canonical_entity, canonical_relation, canonical_evidence,
    )
except Exception:  # pragma: no cover — 降级：本地内联，保证模块可独立导入
    import hashlib
    import json as _json
    canonical_json = lambda o: _json.dumps(o, ensure_ascii=False, sort_keys=True,
                                           separators=(",", ":"))
    sha256 = lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest()
    fp16 = lambda s: sha256(s)[:16]

    def canonical_entity(e):
        stable = {"id": e.get("id"), "type": e.get("type"), "name": e.get("name"),
                  "status": e.get("status", "active"), "scope": e.get("scope", "AGENT"),
                  "owner_type": e.get("owner_type"), "owner_id": e.get("owner_id"),
                  "properties": e.get("properties", {}) or {}}
        return canonical_json({k: v for k, v in stable.items() if v not in (None, "")})

    def canonical_relation(r):
        stable = {"id": r.get("id"), "from_id": r.get("from_id"),
                  "predicate": r.get("predicate"), "to_id": r.get("to_id"),
                  "status": r.get("status", "active"),
                  "properties": r.get("properties", {}) or {}}
        return canonical_json({k: v for k, v in stable.items() if v not in (None, "")})

    def canonical_evidence(e):
        return canonical_json({k: e.get(k) for k in
                               ("id", "source", "pattern_key", "problem", "verified")
                               if e.get(k) is not None})


def _read_lines_raw(path):
    """读 JSONL 原始行 → [(obj, line_no)]。损坏行跳过（保留行号连续性）。"""
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for n, raw in enumerate(f, 1):
            s = raw.strip()
            if not s:
                continue
            try:
                import json as _json
                out.append((_json.loads(s), n))
            except Exception:
                continue
    return out


def parse_provenance_ref(ref):
    """解析 provenance_ref → dict。返回 {type: jsonl|artifact|abstract|unknown, ...}。

    - "<file>:<line>:<fp16>"       → jsonl
    - "<file>::<artifact_id>"      → artifact
    - "EVD-xxx" / "EXP-xxx"        → abstract（需到 evidence/experience 源解析）
    - 其它                          → unknown（不可验证）
    """
    if not ref or not isinstance(ref, str):
        return {"type": "unknown", "reason": "缺失或非字符串"}
    ref = ref.strip()
    if "::" in ref:
        src, aid = ref.split("::", 1)
        return {"type": "artifact", "source": src, "artifact_id": aid}
    parts = ref.split(":")
    if len(parts) == 3 and parts[2] and _is_hex(parts[2]):
        try:
            line = int(parts[1])
        except ValueError:
            return {"type": "unknown", "reason": "行号非整数"}
        return {"type": "jsonl", "source": parts[0], "line": line,
                "declared_fp": parts[2]}
    if re_fullmatch_id(ref):
        return {"type": "abstract", "id": ref}
    return {"type": "unknown", "reason": "无法识别的格式"}


def _is_hex(s):
    return bool(_HEX_RE.match(s))


def re_fullmatch_id(s):
    return bool(_ID_RE.match(s))


def _jsonl_source_path(source, evo_root):
    """把 provenance 的 source 文件名映射到真实文件路径。

    允许：entities.jsonl / relations.jsonl / evidence.jsonl（及 source 可能是
    .agent-os/evolution 下的相对路径）。返回绝对路径或 None。
    """
    base = os.path.abspath(evo_root or "")
    if source in ("entities.jsonl", "relations.jsonl"):
        # ontology data 目录由调用方传入；这里仅接受绝对路径映射函数由调用方补全。
        return source
    if source == "evidence.jsonl":
        return os.path.join(base, "evidence.jsonl") if base else "evidence.jsonl"
    # artifact 相对路径（.agent-os/evolution/changes/xxx.json）
    cand = source
    if cand.startswith(".agent-os/"):
        cand = os.path.join("..", cand)
    return cand


def _record_from_jsonl(source, line, ont_auth=None, evo_root=""):
    """从真实 JSONL 源定位指定行。返回 (obj, recomputed_fp_fn) 或 (None, None)。

    ont_auth: dict {"entities": path, "relations": path} —— ontology 数据目录。
    """
    path = None
    if source == "entities.jsonl":
        path = ont_auth.get("entities") if ont_auth else None
        wrap = "entity"
    elif source == "relations.jsonl":
        path = ont_auth.get("relations") if ont_auth else None
        wrap = "relation"
    elif source == "evidence.jsonl":
        path = os.path.join(evo_root, "evidence.jsonl") if evo_root else "evidence.jsonl"
        wrap = None
    else:
        # 尝试把 source 当相对文件
        cand = source
        if cand.startswith(".."):
            cand = os.path.join(evo_root, cand)
        if os.path.exists(cand):
            path = cand
            wrap = None
    if not path or not os.path.exists(path):
        return None, None
    for obj, ln in _read_lines_raw(path):
        if ln == line:
            if wrap == "entity":
                e = obj.get("entity", {})
                if e.get("id"):
                    return e, (lambda: fingerprint_entity_with(e))
            elif wrap == "relation":
                r = obj.get("relation", {})
                if r.get("id"):
                    return r, (lambda: fingerprint_relation_with(r))
            elif obj.get("id"):
                return obj, (lambda: fingerprint_evidence_with(obj))
            return obj, None
    return None, None


def fingerprint_entity_with(e):
    return fp16(canonical_entity(e)) if e and e.get("id") else None


def fingerprint_relation_with(r):
    return fp16(canonical_relation(r)) if r and r.get("id") else None


def fingerprint_evidence_with(e):
    return fp16(canonical_evidence(e)) if e and e.get("id") else None


def verify_jsonl_provenance(parsed, ont_auth=None, evo_root=""):
    """校验 JSONL 型 provenance：源行存在 + 指纹重算一致。

    返回 {"ok": bool, "reason": str, "recomputed_fp": str|None, "type": str}。
    """
    src = parsed.get("source")
    line = parsed.get("line")
    declared = str(parsed.get("declared_fp") or "").lower()
    obj, fn = _record_from_jsonl(src, line, ont_auth=ont_auth, evo_root=evo_root)
    if obj is None:
        return {"ok": False, "reason": "源记录不存在：{0}:{1}".format(src, line),
                "recomputed_fp": None, "type": "jsonl"}
    if fn is None:
        return {"ok": False, "reason": "源记录无稳定指纹可验证：{0}:{1}".format(src, line),
                "recomputed_fp": None, "type": "jsonl"}
    recomputed = fn()
    if recomputed is None:
        return {"ok": False, "reason": "源记录无法计算指纹", "recomputed_fp": None,
                "type": "jsonl"}
    if recomputed.lower() != declared:
        return {"ok": False,
                "reason": "指纹不匹配：声明={0} 重算={1}".format(declared, recomputed),
                "recomputed_fp": recomputed, "type": "jsonl"}
    return {"ok": True, "reason": "OK", "recomputed_fp": recomputed, "type": "jsonl"}


def _artifact_exists(source, artifact_id, evo_root=""):
    """校验 .agent-os/evolution artifact 指向存在（只校验存在性，artifact 指纹以 id 签名）。"""
    if not evo_root or not os.path.isdir(evo_root):
        return False
    src = source or ""
    # source 形如 ".agent-os/evolution/changes/CHG-xxx.json" 或 "changes/CHG-xxx.json"
    norm = src.replace(".agent-os/evolution/", "").replace(os.sep, "/")
    # 遍历 evolution 子目录找匹配 artifact id
    for sub in ("candidates", "diagnoses", "proposals", "changes", "regressions"):
        p = os.path.join(evo_root, sub, artifact_id + ".json")
        if os.path.exists(p):
            return True
    return False


def verify_artifact_provenance(parsed, evo_root=""):
    """校验 artifact 型 provenance（<file>::<artifact_id>）。

    只要求 artifact 记录在 .agent-os/evolution 下存在即可（artifact 视图的
    provenance 本身就是稳定签名）。返回 {"ok": bool, "reason": str}。
    """
    aid = parsed.get("artifact_id")
    if not aid:
        return {"ok": False, "reason": "artifact_id 缺失", "type": "artifact"}
    if not _artifact_exists(parsed.get("source", ""), aid, evo_root):
        return {"ok": False,
                "reason": "evolution artifact 不存在：{0}".format(aid),
                "type": "artifact"}
    return {"ok": True, "reason": "OK", "type": "artifact"}


def resolve_abstract_provenance(ref, evo_root=""):
    """把抽象 ID（EVD-xxx / EXP-xxx）解析为 evidence 记录。

    在 evidence.jsonl 中按 id 查找；找不到 → invalid。返回 {"ok", "reason", "record"}。
    """
    rec = None
    if evo_root:
        evp = os.path.join(evo_root, "evidence.jsonl")
        for obj, _ in _read_lines_raw(evp):
            if obj.get("id") == ref:
                rec = obj
                break
    if rec is None:
        return {"ok": False, "reason": "evidence 不存在：{0}".format(ref), "record": None}
    return {"ok": True, "reason": "OK", "record": rec}


def verify_provenance(ref, *, ont_auth=None, evo_root=""):
    """统一入口：给定 provenance_ref，校验其是否指向**真实且指纹一致**的机器真相。

    返回 {"ok": bool, "reason": str, "type": str, "recomputed_fp": str|None}。

    ont_auth: dict {"entities": <路径>, "relations": <路径>}（可选，来自桥当前 ontology 数据）。
    evo_root: .agent-os/evolution 目录（evidence.jsonl 与 artifact 所在）。
    """
    parsed = parse_provenance_ref(ref)
    t = parsed["type"]
    if t == "jsonl":
        res = verify_jsonl_provenance(parsed, ont_auth=ont_auth, evo_root=evo_root)
        res["type"] = "jsonl"
        return res
    if t == "artifact":
        res = verify_artifact_provenance(parsed, evo_root=evo_root)
        res["type"] = "artifact"
        res["recomputed_fp"] = None
        return res
    if t == "abstract":
        res = resolve_abstract_provenance(parsed.get("id"), evo_root=evo_root)
        if res["ok"]:
            return {"ok": True, "reason": "OK", "type": "abstract",
                    "recomputed_fp": fingerprint_evidence_with(res["record"])}
        return {"ok": False, "reason": res["reason"], "type": "abstract",
                "recomputed_fp": None}
    return {"ok": False, "reason": parsed.get("reason") or "未知 provenance 格式",
            "type": "unknown", "recomputed_fp": None}
