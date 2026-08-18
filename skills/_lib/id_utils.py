#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v1.3 Hardening — 统一 ID helper (Batch 2)

不再让每个 Skill 自己发明 ID。统一:
  generate_id(prefix, canonical=None)  → UUID4 (prefix_xxxxxxxx-...)
  deterministic_id(prefix, obj)        → SHA256(canonical_json) 固定 identity

禁止使用 Python hash() (进程内随机) / int(time.time()) 作为业务 ID。
deterministic identity 用于: 需要跨进程/跨运行可复现的指纹(请求去重、signal
fingerprint、artifact hash 等), 一律 SHA256(canonical_json)。
"""

import hashlib
import json
import os
import uuid


def _canonical_json(obj):
    """canonical JSON: sort_keys + 紧凑编码, 保证跨进程一致。"""
    if isinstance(obj, str):
        obj = {"value": obj}
    try:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False)
    except (TypeError, ValueError):
        return json.dumps({"value": str(obj)}, sort_keys=True,
                          separators=(",", ":"), ensure_ascii=False)


def generate_id(prefix):
    """UUID4 随机 ID: {prefix}_{uuid4hex}。所有业务实体统一用这个。"""
    return "{0}_{1}".format(str(prefix).strip("_"), uuid.uuid4().hex)


def deterministic_id(prefix, obj):
    """确定性 ID: {prefix}_{sha256(canonical_json)[:16]}。"""
    h = hashlib.sha256(_canonical_json(obj).encode("utf-8")).hexdigest()[:16]
    return "{0}_{1}".format(str(prefix).strip("_"), h)


def sha256sum(data):
    """通用 SHA256 hex (用于 file fingerprint / artifact hash)。"""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def file_fingerprint(path, chunk_size=65536):
    """文件内容 SHA256 (Batch 8 self-evolution expected file hash 用)。"""
    if not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()
