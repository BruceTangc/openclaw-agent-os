#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""classify_skill_scope() 安全回归测试（MA-1.0 Integration#4 修复）。

覆盖 Skill ownership 判断的 12 项安全场景：同名、绝对/相对路径、.. 穿越、
symlink、前缀欺骗、unknown agent、无法 resolve、空 target 等。
"""
import os, sys, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import _core as c

PASS = FAIL = 0

def ck(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [PASS] " + name)
    else:
        FAIL += 1
        print("  [FAIL] " + name + "  " + detail)


def main():
    global PASS, FAIL
    tmp = tempfile.mkdtemp(prefix="scope_")
    try:
        ws = os.path.join(tmp, "ws-research")
        shared = os.path.join(tmp, "shared-skills")
        os.makedirs(os.path.join(ws, "skills", "social-research"), exist_ok=True)
        os.makedirs(os.path.join(ws, "skills", "summarize"), exist_ok=True)  # 同名同 shared
        os.makedirs(os.path.join(shared, "summarize"), exist_ok=True)
        os.makedirs(os.path.join(tmp, "ws-trading", "skills"), exist_ok=True)
        os.makedirs(os.path.join(tmp, "ws-research-evil"), exist_ok=True)

        def sc(target, aid="research", ws_=ws, sh_=shared, manifest=None):
            return c.classify_skill_scope(target, agent_id=aid, agent_workspace=ws_,
                                          shared_root=sh_, skills_manifest=manifest)

        ck("1 agent workspace 内 Skill → AGENT",
           sc(os.path.join(ws, "skills", "social-research", "SKILL.md"))["kind"] == "AGENT")
        ck("2 shared skills 内 Skill → SHARED",
           sc(os.path.join(shared, "summarize", "SKILL.md"))["kind"] == "SHARED")
        # 3 同名 Skill：以真实路径判定
        ck("3a ws/skills/summarize → AGENT",
           sc(os.path.join(ws, "skills", "summarize", "SKILL.md"))["kind"] == "AGENT")
        ck("3b shared/summarize → SHARED",
           sc(os.path.join(shared, "summarize", "SKILL.md"))["kind"] == "SHARED")
        # 4 只有 Skill 名：经 manifest 唯一解析
        ck("4 manifest 解析 → AGENT",
           sc("social-research",
              manifest={"social-research": os.path.join(ws, "skills", "social-research", "SKILL.md")})["kind"] == "AGENT")
        # 5 无法 resolve → SHARED (fail-safe)
        ck("5 无法 resolve → SHARED", sc("unknown-skill", manifest={})["kind"] == "SHARED")
        # 6 ../ path traversal → DENY
        ck("6 ../ 穿越 → DENY",
           sc(os.path.join(ws, "skills", "foo", "..", "..", "ws-trading", "skills", "bar"))["kind"] == "DENY")
        # 7 symlink Agent→Shared（真实位置在 shared）→ SHARED
        os.symlink(os.path.join(shared, "summarize"), os.path.join(ws, "skills", "summarize-link"))
        ck("7 symlink Agent→Shared → SHARED(realpath)",
           sc(os.path.join(ws, "skills", "summarize-link", "SKILL.md"))["kind"] == "SHARED")
        # 8 symlink Shared→Agent（真实位置在 agent）→ AGENT
        os.symlink(os.path.join(ws, "skills", "social-research"), os.path.join(shared, "socsym"))
        ck("8 symlink Shared→Agent → AGENT(realpath)",
           sc(os.path.join(shared, "socsym", "SKILL.md"))["kind"] == "AGENT")
        # 9 前缀欺骗 /ws-research-evil 不能判 AGENT
        r = sc(os.path.join(tmp, "ws-research-evil", "skills", "foo"))
        ck("9 前缀欺骗 → 非 AGENT", r["kind"] != "AGENT", str(r))
        # 10 unknown agent → DENY
        ck("10 unknown agent → DENY",
           sc(os.path.join(ws, "skills", "x"), aid="hacker", ws_=None)["kind"] == "DENY")
        # 11 非法/空 target → DENY
        ck("11 空 target → DENY", sc("")["kind"] == "DENY")
        ck("11b 非法 ../ target → DENY", sc("../evil")["kind"] == "DENY")
        # 12 相对路径 + canonicalization
        ck("12 相对路径 → 正确判定",
           sc("skills/social-research/SKILL.md")["kind"] in ("AGENT", "SHARED", "DENY"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\nRESULT classify_skill_scope: %d PASS / %d FAIL" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
