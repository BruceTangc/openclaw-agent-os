#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
canonical.py — Agent OS 统一 canonical 序列化 / SHA-256 指纹 helper。

【背景】ontology.py 与 agent-os-vault 桥各自维护了一套"稳定字段 canonical 指纹"
（实体/关系/证据）。两套实现此前逐字重复，存在漂移风险：ontology CLI 打指纹
用的规则与桥导出/校验用的规则必须**完全一致**，否则同一 JSONL 行会被算成不同
指纹，导致 provenance 校验失败或 reconcile 误报。

本模块收敛为**唯一** canonical 实现。既有调用点（ontology.py / agent_os_vault.py）
改为 import 本模块；因实现与历史逐字一致，迁移前后已落盘的指纹不变。

【规则】与 ontology.py `_canonical_json/_canonical_entity/_canonical_relation` 逐字对齐：
  - 键递归按字典序排序（json sort_keys）
  - ensure_ascii=False + 紧凑 separators=(",",":")
  - 实体/关系指纹只取稳定字段，忽略易变时间戳与 `_line`

【职责边界】纯函数；不读文件、不写文件、不持有状态。
"""

import hashlib
import json

try:
    from id_utils import sha256sum, file_fingerprint  # noqa: F401  复用统一 hash 语义
except Exception:  # pragma: no cover
    sha256sum = lambda data: hashlib.sha256(
        data.encode("utf-8") if isinstance(data, str) else data).hexdigest()
    file_fingerprint = None


def canonical_json(obj):
    """稳定 canonical 序列化（provenance 指纹用）。

    键递归按字典序排序，值 JSON 序列化，ensure_ascii=False + sort_keys +
    紧凑分隔；同一 JSONL 任意两次读取结果一致。
    """
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def fp16(s):
    """SHA-256 前 16 hex（provenance_ref 尾段用，缩短引用）。"""
    return sha256(s)[:16]


def canonical_entity(e):
    """实体的稳定指纹：只取稳定字段（见 META.md 串行化规则），忽略易变时间戳。"""
    stable = {
        "id": e.get("id"),
        "type": e.get("type"),
        "name": e.get("name"),
        "status": e.get("status", "active"),
        "scope": e.get("scope", "AGENT"),
        "owner_type": e.get("owner_type"),
        "owner_id": e.get("owner_id"),
        "properties": e.get("properties", {}) or {},
    }
    return canonical_json({k: v for k, v in stable.items() if v not in (None, "")})


def canonical_relation(r):
    """关系的稳定指纹：只取稳定字段，忽略 _line 与易变时间戳。"""
    stable = {
        "id": r.get("id"),
        "from_id": r.get("from_id"),
        "predicate": r.get("predicate"),
        "to_id": r.get("to_id"),
        "status": r.get("status", "active"),
        "properties": r.get("properties", {}) or {},
    }
    return canonical_json({k: v for k, v in stable.items() if v not in (None, "")})


# 证据稳定指纹的字段子集（与 ontology.py / agent-os-vault 导出 provenance 规则一致）
EVIDENCE_FP_FIELDS = ("id", "source", "pattern_key", "problem", "verified")


def canonical_evidence(e):
    """Evidence 的稳定指纹：只取与导出 provenance_ref 同 namespace 的字段子集。

    与 agent-os-vault 渲染 evidence 视图开头 `provenance_ref` 尾段用同一规则，
    保证"视图声明指纹 = 机器重算指纹"。
    """
    return canonical_json(
        {k: e.get(k) for k in EVIDENCE_FP_FIELDS if e.get(k) is not None})


def fingerprint_entity(e):
    return fp16(canonical_entity(e))


def fingerprint_relation(r):
    return fp16(canonical_relation(r))


def fingerprint_evidence(e):
    return fp16(canonical_evidence(e))
