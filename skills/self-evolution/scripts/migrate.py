#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate.py — Self-Evolution v2 · 一次性迁移工具（旧版 → v2 artifact）

不是 Runtime，是一次性数据迁移工具（任务书 §21）：把旧版 Self-Evolution 状态
（.learning-trail.json 等）迁到 v2 的 .agent-os/evolution/ artifacts。

迁移完成后此脚本可删除或归档到 tools/migration/，不参与 v2 演进运行时。

用法：
  python3 migrate.py --dry-run   # 预览将迁移多少条
  python3 migrate.py             # 执行迁移（迁移过的条目幂等跳过）
"""

import argparse
import json
import os

import _core
import discover


def legacy_trail_path():
    ws = _core._workspace()
    return os.path.join(ws, "memory", ".learning-trail.json")


def load_legacy():
    p = legacy_trail_path()
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def to_candidate(entry):
    """旧 entry → v2 candidate（只迁移有 pattern 可归类的演进候选）。

    v2.3 字段语义对齐：recurrence→observation_count、sessions→unique_sessions。
    同时产出 _stats 供门槛判断（discover._meets_threshold 需要 stats 形态）。
    """
    text = str(entry.get("summary", "")) + " " + str(entry.get("content", ""))
    target = entry.get("area", entry.get("topic", "unknown"))
    pattern_key = entry.get("pattern_key") or str(entry.get("id", ""))
    observation_count = int(entry.get("recurrence", entry.get("count", 0)) or 0)
    unique_sessions = int(entry.get("sessions", 0) or 0)
    independent_sources = int(entry.get("independent_sources", 0) or 0)
    systemic = bool(entry.get("systemic", False))
    cand = {
        "scope": entry.get("scope", "unknown"),
        "target": target,
        "pattern_key": pattern_key,
        "problem": text[:300],
        "evidence_refs": [str(entry.get("id", ""))],
        "observation_count": observation_count,
        "unique_sessions": unique_sessions,
        "independent_sources": independent_sources,
        "systemic": systemic,
        "confidence": float(entry.get("confidence", 0) or 0),
        "impact": entry.get("impact", "low"),
    }
    cand["_stats"] = {
        "observation_count": observation_count,
        "unique_sessions": unique_sessions if unique_sessions else None,
        "independent_sources": independent_sources,
        "verified_count": 0,
        "systemic": systemic,
    }
    return cand


def run(dry_run):
    trail = load_legacy()
    if not trail:
        print(json.dumps({"status": "no_legacy_trail"}, ensure_ascii=False, indent=2))
        return
    entries = trail.get("entries", []) or []
    migrated = 0
    skipped = 0
    for entry in entries:
        cand = to_candidate(entry)
        # 口径：只有达到门槛才迁成 Candidate（避免垃圾入库）。
        # v2.3 修复：_meets_threshold(stats, n_verified) 需 stats 形态 + n_verified 两个参数；
        # 旧代码误传 candidate dict 且缺参 → TypeError。
        stats = cand.pop("_stats", {})
        n_verified = stats.get("verified_count", 0)
        ok, _reason = discover._meets_threshold(stats, n_verified)
        if not ok:
            skipped += 1
            continue
        if discover._core.find_candidate(cand["scope"], cand["target"], cand["pattern_key"]):
            skipped += 1
            continue
        if dry_run:
            migrated += 1
            continue
        cid = _core.save_artifact("candidate", cand)
        migrated += 1
    print(json.dumps({
        "status": "dry_run" if dry_run else "migrated",
        "scanned": len(entries),
        "migrated": migrated,
        "skipped": skipped,
        "destination": _core.evo_dir(),
    }, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description="Self-Evolution v2 migration (one-time)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    run(args.dry_run)


if __name__ == "__main__":
    main()
