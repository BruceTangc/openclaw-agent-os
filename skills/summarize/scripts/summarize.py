#!/usr/bin/env python3
"""summarize.py — Summarize Skill 的预处理脚本层。

按精简版 SKILL.md §11：chunking（语义分块）、dedup（多文档去重）、
aggregate（多文档聚合）等重活由脚本完成，LLM 只做核心抽取与格式化。

用法（在 scripts/ 目录下）：
  python3 summarize.py --chunk <file> [--overlap 0.15]     # 语义分块
  python3 summarize.py --dedup <file> [--threshold 0.9]    # 多文档去重
  python3 summarize.py --aggregate <dir> [--out out.txt]   # 多文档聚合
  python3 summarize.py --clean <file>                      # 内容清洗（去噪音）
  python3 summarize.py --stats <file>                      # 文本统计
  python3 summarize.py --verify <summary> <source>         # 关键事实可追溯检查（骨架）
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime

NL = chr(10)
NL2 = chr(10) + chr(10)


# ── 基础工具 ──────────────────────────────────────────────


def read_text(path):
    if not os.path.exists(path):
        raise FileNotFoundError("文件不存在: {0}".format(path))
    f = open(path, encoding="utf-8", errors="ignore")
    content = f.read()
    f.close()
    return content


def normalize(text):
    """归一化：折叠空白，去掉零宽字符。"""
    text = text.replace("\u200b", "").replace("\ufeff", "")
    text = re.sub(r"[ \t\u3000]+", " ", text)
    return text.strip()


def sha1(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


# ── 1. 语义分块 ──────────────────────────────────────────


def chunk_by_semantics(text, overlap=0.15, max_chars=2500):
    """按章节/标题/段落边界分块；硬切时保留 overlap。

    边界优先级：markdown 标题(#/##/###) > 空行分段 > 句子。
    """
    if overlap < 0 or overlap > 0.5:
        overlap = 0.15
    lines = text.splitlines()
    chunks = []
    cur = []
    for line in lines:
        if re.match(r"^#{1,4}\s+", line) and cur:
            chunks.append(NL.join(cur))
            cur = [line]
        else:
            cur.append(line)
    if cur:
        chunks.append(NL.join(cur))
    final = []
    for c in chunks:
        if len(c) <= max_chars:
            final.append(c.strip())
            continue
        paras = [p.strip() for p in re.split(NL + r"\s*" + NL, c) if p.strip()]
        buf = ""
        for p in paras:
            if buf and len(buf) + len(p) > max_chars:
                final.append(buf.strip())
                buf = p
            else:
                buf = (buf + NL2 + p) if buf else p
        if buf:
            final.append(buf.strip())
    result = []
    for c in final:
        if len(c) <= max_chars:
            result.append(c)
            continue
        step = int(max_chars * (1 - overlap))
        i = 0
        while i < len(c):
            result.append(c[i:i + max_chars])
            i += step
    return [c for c in result if c]


# ── 2. 多文档去重 ────────────────────────────────────────


def dedup_lines(text, threshold=0.9):
    """基于 2-gram Jaccard 相似度的行级去重。

    返回 (去重后文本, 重复行数, 相似对样例)。
    """
    lines = [l for l in text.splitlines() if l.strip()]
    kept = []
    kept_lines = []
    seen = []
    dup = 0
    samples = []

    def grams(s):
        s = re.sub(r"\s+", "", s.lower())
        return set(s[i:i + 2] for i in range(max(0, len(s) - 1)))

    for line in lines:
        g = grams(line)
        is_dup = False
        for k, kg in enumerate(seen):
            if not g or not kg:
                sim = 0
            else:
                sim = len(g & kg) / len(g | kg)
            if sim >= threshold:
                is_dup = True
                dup += 1
                if len(samples) < 5:
                    samples.append((line[:40], kept_lines[k][:40], round(sim, 2)))
                break
        if not is_dup:
            kept.append(line)
            kept_lines.append(line)
            seen.append(g)
    return NL.join(kept), dup, samples


# ── 3. 多文档聚合 ────────────────────────────────────────


def aggregate_dir(dir_path):
    """聚合目录下所有文本文件，带源标注，输出结构化 JSON。"""
    if not os.path.isdir(dir_path):
        raise NotADirectoryError("不是目录: {0}".format(dir_path))
    docs = []
    for fname in sorted(os.listdir(dir_path)):
        p = os.path.join(dir_path, fname)
        if not os.path.isfile(p):
            continue
        if fname.endswith((".json", ".jsonl")):
            continue
        try:
            content = read_text(p)
        except Exception:
            continue
        # F-RVW-001/修复: 缓存首次读取结果，避免同一文件读两次。
        raw = content
        # P2-2/修复: 截断时输出 truncation metadata，避免把截断后的内容当成完整事实。
        truncated = len(raw) > 50000
        content = raw[:50000]
        docs.append({
            "source_id": fname,
            "title": fname,
            "url": None,
            "date": None,
            "type": "document",
            "chars": len(content),
            "original_chars": len(raw),
            "hash": sha1(content),
            "truncated": truncated,
            "truncation_note": "content 超出 50000 字符已被截断，SUMMARY != FACT" if truncated else None,
            "content": content,
        })
    return {"documents": docs, "count": len(docs), "aggregated_at": datetime.now().isoformat()}


# ── 4. 内容清洗 ──────────────────────────────────────────


def clean_text(text):
    """去导航/广告/页脚噪音行，保留内容行。保守策略：宁可少删。"""
    lines = text.splitlines()
    kept = []
    removed = 0
    for line in lines:
        s = line.strip()
        if not s:
            kept.append("")
            continue
        if len(s) <= 12:
            if re.search(r"首页|登录|注册|广告|导航|版权所有|©|ICP备", s):
                removed += 1
                continue
        kept.append(s)
    out = NL.join(kept)
    out = re.sub(NL + "{3,}", NL2, out)
    return out, removed


# ── 5. 统计 ──────────────────────────────────────────────


def text_stats(text):
    chars = len(text)
    lines = len(text.splitlines())
    words = len(re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9]+", text))
    return {
        "chars": chars,
        "lines": lines,
        "words_approx": words,
        "hash": sha1(text),
    }


# ── 6. 验证骨架 ──────────────────────────────────────────


def verify_coverage(summary_path, source_path):
    """抽查摘要中的关键数字/专名是否在源文本中出现（可追溯检查的骨架）。

    提取规则（避免中文跨词边界误报）：
    - 数字（2位以上）、日期（2026-08-15 型）、百分比
    - 书名号《...》内的内容（教材/书名专名）
    - 不再提取任意 4-8 连续中文字符（会把"有机化学用"这种跨词串误判为未出现）
    """
    summary = read_text(summary_path)
    source = read_text(source_path)
    tokens = set()
    # 数字 / 日期 / 百分比
    tokens |= set(re.findall(r"\d{4}[-/]\d{1,2}(?:[-/]\d{1,2})?", summary))
    tokens |= set(re.findall(r"\d{2,}", summary))
    tokens |= set(re.findall(r"\d+(?:\.\d+)?%", summary))
    # 书名号内容（中文专名，最可靠）
    tokens |= set(re.findall(r"《([^》]+)》", summary))
    found = 0
    missing = []
    for t in tokens:
        if t in source:
            found += 1
        else:
            missing.append(t)
    return {
        "summary_tokens": len(tokens),
        "traceable": found,
        "missing_candidates": missing[:20],
        "traceable_ratio": round(found / len(tokens), 2) if tokens else 1.0,
    }


# ── 6.5 结构化提取 ──────────────────────────────────────


def cmd_extract(args):
    """--extract <text> [--mode MODE]: 结构化提取骨架。

    参数为直接文本（--extract "行情时间戳必须验证"），与 SKILL.md 用法一致。
    用规则提取：关键数字/日期、书名号专名、实体候选（CJK 词组）、句子级
    fact 候选，并输出 Summarize 标准 schema 骨架，供 LLM 填充
    facts/claims/inferences 等语义字段。此命令是"骨架"，不做语义判断。
    """
    import re as _re
    text = args.extract
    _src_label = "inline-text"
    stats = text_stats(text)

    # 数字 / 日期 / 百分比
    numbers = sorted(set(_re.findall(r"\d{2,}", text)))[:50]
    dates = sorted(set(_re.findall(r"\d{4}[-/]\d{1,2}(?:[-/]\d{1,2})?", text)))[:30]
    percents = sorted(set(_re.findall(r"\d+(?:\.\d+)?%", text)))[:30]

    # 书名号专名
    book_marks = sorted(set(_re.findall(r"《([^》]+)》", text)))[:30]

    # 实体候选：连续 CJK 2-4 字词，过滤停用词 + 频率 >=2 或长度>=4
    stop = ("我们", "他们", "你们", "这个", "那个", "因为", "所以", "但是",
            "以及", "通过", "关于", "对于", "如果", "虽然", "同时", "此外",
            "主要", "重要", "当前", "现在", "问题", "情况", "方面", "部分",
            "方式", "过程", "结果", "影响", "作用", "意义", "目的", "目标",
            "要求", "标准", "规定", "政策", "制度", "体系", "结构", "类型",
            "数量", "质量", "程度", "水平", "范围", "领域", "方向", "趋势",
            "状况", "状态", "条件", "环境", "因素", "原因", "效果", "效率",
            "成本", "收益", "风险", "机会", "挑战", "优势", "劣势", "特点",
            "特征", "属性", "参数", "指标", "认为", "表示", "说明", "指出",
            "建议", "希望", "计划", "开始", "结束", "完成", "实现", "达到",
            "增加", "减少", "提高", "降低", "改善", "优化", "加强", "促进",
            "推动", "负责", "参与", "配合", "协调", "组织", "安排", "部署",
            "执行", "实施", "落实", "跟进", "跟踪", "监控", "监督", "检查",
            "审核", "评估", "评价", "反馈", "总结", "记录", "保存", "提交",
            "上报", "审批", "批准", "同意", "拒绝", "接受", "采纳", "采用",
            "应用", "利用", "基于", "依据", "根据", "按照", "遵循", "遵守",
            "符合", "满足", "突破", "创新", "研发", "设计", "规划", "策略",
            "战略", "机制", "体制", "架构", "框架", "平台", "工具", "设备",
            "材料", "资源", "资金", "资产", "费用", "支出", "收入", "利润",
            "增长", "下降", "波动", "报错", "失败", "错误", "成功", "正常",
            "异常", "修复", "排查", "定位", "解决", "覆盖", "丢失", "污染",
            "兼容", "稳定", "可靠", "准确", "及时", "最新", "权威", "官方",
            "真实", "完整", "系统", "数据", "核算", "分析", "管理", "操作",
            "功能", "信息", "相关", "内容", "方法", "使用", "开发", "测试",
            "产品", "用户", "服务", "支持", "处理", "生成", "存在", "方案",
            "改进", "同步", "延迟", "联合", "提出", "之间", "发现", "需要",
            "进行", "可以", "应该", "必须")
    cjk_words = {}
    for m in _re.finditer(r"[\u4e00-\u9fff]{2,}", text):
        w = m.group(0)
        # 只取 2-4 字连续词作为实体候选（长句整体提取会产生含停用词的噪声）
        if len(w) > 4:
            continue
        if w in stop:
            continue
        cjk_words[w] = cjk_words.get(w, 0) + 1
    entity_candidates = sorted(
        (w for w, c in cjk_words.items() if c >= 2 or len(w) >= 3),
        key=lambda w: (-cjk_words[w], -len(w)))[:30]

    # 句子级候选 facts（按句号/感叹号切分，取长度适中的）
    sentences = [s.strip() for s in _re.split(r"[。！？；\n]", text) if 8 <= len(s.strip()) <= 80]
    fact_candidates = sentences[:20]

    result = {
        "status": "success",
        "mode": args.mode or "standard",
        "summary": {
            "title": _src_label,
            "one_liner": "",
            "key_points": [],
        },
        "extracted_candidates": {
            "numbers": numbers,
            "dates": dates,
            "percents": percents,
            "book_marks": book_marks,
            "entity_candidates": entity_candidates,
            "fact_candidates": fact_candidates,
        },
        "structured": {
            "facts": [],
            "claims": [],
            "conclusions": [],
            "inferences": [],
            "uncertainties": [],
            "conflicts": [],
            "evidence": [],
            "decisions": [],
            "action_items": [],
            "risks": [],
            "open_questions": [],
            "entities": [],
            "relations": [],
            "note": "SUMMARY != FACT: 由规则提取的是候选事实(fact_candidates)，须经 LLM 区分 facts/claims/inferences/uncertainties/conflicts；'可能A'不得判为'A'",
        },
        "state": {"completed": [], "in_progress": [], "pending": []},
        "integrations": {
            "memory_candidates": [],
            "ontology_candidates": {"entities": [], "relations": []},
            "experience": None,
        },
        "sources": [{"source_id": _src_label, "title": _src_label}],
        "quality": {
            "faithfulness": None, "completeness": None, "relevance": None,
            "compression": None, "redundancy": None, "attribution": None, "overall": None,
        },
        "warnings": ["extract 是规则骨架，语义字段（facts/claims/inferences 等）需 LLM 填充"],
        "stats": stats,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


# ── main ─────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Summarize Skill 预处理层")
    parser.add_argument("--chunk", metavar="FILE", help="语义分块")
    parser.add_argument("--overlap", type=float, default=0.15, help="overlap 比例 (默认0.15)")
    parser.add_argument("--dedup", metavar="FILE", help="行级去重")
    parser.add_argument("--threshold", type=float, default=0.9, help="去重相似度阈值 (默认0.9)")
    parser.add_argument("--aggregate", metavar="DIR", help="聚合目录下多文档")
    parser.add_argument("--out", metavar="FILE", help="输出文件（聚合/清洗用）")
    parser.add_argument("--clean", metavar="FILE", help="内容清洗")
    parser.add_argument("--stats", metavar="FILE", help="文本统计")
    parser.add_argument("--verify", nargs=2, metavar=("SUMMARY", "SOURCE"), help="可追溯验证")
    parser.add_argument("--extract", metavar="TEXT", help="结构化提取骨架（直接传文本）")
    parser.add_argument("--mode", default=None, metavar="MODE", help="提取模式 (quick/standard/deep/agent 等)")
    args = parser.parse_args()

    if args.chunk:
        text = read_text(args.chunk)
        chunks = chunk_by_semantics(text, overlap=args.overlap)
        print("分块数: {0} (overlap={1})".format(len(chunks), args.overlap))
        for i, c in enumerate(chunks, 1):
            print("--- 块 {0} ({1} 字符) ---".format(i, len(c)))
            print(c[:200] + ("..." if len(c) > 200 else ""))
        return 0

    if args.dedup:
        text = read_text(args.dedup)
        cleaned, dup, samples = dedup_lines(text, threshold=args.threshold)
        print("原行数: {0} | 去重后: {1} | 判重: {2}".format(
            len([l for l in text.splitlines() if l.strip()]),
            len(cleaned.splitlines()), dup))
        for s in samples:
            print("  相似对: {0} ~ {1} (sim={2})".format(s[0], s[1], s[2]))
        if args.out:
            w = open(args.out, "w", encoding="utf-8")
            w.write(cleaned)
            w.close()
            print("已写: {0}".format(args.out))
        return 0

    if args.aggregate:
        result = aggregate_dir(args.aggregate)
        print("聚合 {0} 个文档，总 {1} 字符".format(
            result["count"], sum(d["chars"] for d in result["documents"])))
        for d in result["documents"]:
            print("  - {0} ({1} 字符, hash={2})".format(d["source_id"], d["chars"], d["hash"]))
        if args.out:
            w = open(args.out, "w", encoding="utf-8")
            json.dump(result, w, ensure_ascii=False, indent=2)
            w.close()
            print("已写: {0}".format(args.out))
        return 0

    if args.clean:
        text = read_text(args.clean)
        cleaned, removed = clean_text(text)
        print("清洗完成: 移除 {0} 行噪音 | {1} → {2} 字符".format(removed, len(text), len(cleaned)))
        if args.out:
            w = open(args.out, "w", encoding="utf-8")
            w.write(cleaned)
            w.close()
            print("已写: {0}".format(args.out))
        else:
            print(cleaned[:2000])
        return 0

    if args.stats:
        text = read_text(args.stats)
        print(json.dumps(text_stats(text), ensure_ascii=False, indent=2))
        return 0

    if args.extract:
        return cmd_extract(args)
    if args.verify:
        res = verify_coverage(args.verify[0], args.verify[1])
        print("摘要关键 token: {0} | 源中可追溯: {1} | 比例: {2}".format(
            res["summary_tokens"], res["traceable"], res["traceable_ratio"]))
        if res["missing_candidates"]:
            print("未在源中出现（候选核查）: {0}".format(", ".join(res["missing_candidates"])))
        if res["traceable_ratio"] < 0.8:
            print("警告: 可追溯比例偏低，建议复核摘要是否编造")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
