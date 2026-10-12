#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only, heuristic Chinese prose review locator (Python 3 standard library).

No pass/fail grade. Every finding requires literary/contextual review.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import statistics
from typing import Any
from safe_files import read_source, write_new


# A few high-risk textual shapes, NOT an exhaustive ban list.
RULES = [
    (
        "contrast",
        "否定转折候选",
        r"(?:不是|并非)[^。！？!?\n]{1,45}?(?:而是|却是|实则)",
        "检查是否为旁白替读者作主题总结；正常纠正事实的对白通常保留。",
    ),
    (
        "explanation",
        "后置解释候选",
        r"(?:这(?:说明|证明|意味着)|(?:这个|这一)(?:动作|举动|细节)(?:说明|证明|显出|意味着)|(?:她|他)(?:没有哭|没有落泪|并未落泪)[，,](?:她|他)(?:是|只是在))",
        "检查前文的对白与动作是否已经成立；若只是在重复意义，优先删解说。",
    ),
    (
        "stock_emotion",
        "程式化情绪句",
        r"(?:一股[^。！？!?\n]{1,20}?涌上心头|某种[^。！？!?\n]{1,30}?的存在|内心深处|一阵[^。！？!?\n]{1,20}?袭上心头)",
        "检查抽象情绪是否遮住了人物当时真正的感受与选择。",
    ),
    (
        "stock_action",
        "惯用情绪动作",
        r"(?:指节泛白|脸色泛白|喉结滚了滚|眼神闪了闪|嘴角(?:勾起|扬起)(?:一抹|一个)?[^，。！？!?\n]{0,12}?弧度|笑意不达眼底|身体比脑子快)",
        "这只是常见模板提醒。检查是否反复用它替不同人物表达同一种情绪。",
    ),
    (
        "double_negation",
        "重复否定解释候选",
        r"(?:没有|并未)[^。！？!?\n]{1,22}?[，,](?:没有|并未)[^。！？!?\n]{1,22}?(?:而是|只是|她是在|他是在)",
        "检查排比否定是否在替读者解释意义，或是否确有修辞目的。",
    ),
    (
        "translationese",
        "译腔候选",
        r"(?:产生了[^，。！？!?\n]{0,24}?(?:的意图|的愿望|的想法)|对[^，。！？!?\n]{1,20}?进行了[^，。！？!?\n]{1,15}?(?:的|处理|操作))",
        "查看是否可用自然的中文动词替换名词化结构；专业语境可能适用原句。",
    ),
]
COMPILED = [(code, label, re.compile(pattern), guidance) for code, label, pattern, guidance in RULES]

# Repeated terms are an observation, not mandatory synonym-replacement tasks.
WATCH_REPEAT = (
    "皱眉", "指节", "眸子", "眼神", "目光", "下意识", "低声", "缓缓", "顿了顿", "沉默", "叹了口气", "泛白"
)
QUOTE_OPEN = {"“": "”", "「": "」", "『": "』", "‘": "’"}
QUOTE_CLOSE = set(QUOTE_OPEN.values())


def prose_lines(text: str) -> list[tuple[int, str]]:
    """Skip Markdown metadata and fenced code, while retaining original line numbers."""
    lines = text.splitlines()
    in_fence = False
    fence_char = ""
    in_frontmatter = bool(lines and lines[0].strip() == "---")
    in_comment = False
    out: list[tuple[int, str]] = []
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if in_frontmatter:
            if number > 1 and line in {"---", "..."}:
                in_frontmatter = False
            continue
        if re.match(r"^(```+|~~~+)", line):
            c = line[0]
            if not in_fence:
                in_fence, fence_char = True, c
            elif c == fence_char:
                in_fence, fence_char = False, ""
            continue
        if in_fence:
            continue
        if "<!--" in line:
            in_comment = True
        if in_comment:
            if "-->" in line:
                in_comment = False
            continue
        if re.match(r"^#{1,6}\s", raw):
            continue
        if line == "---" or not line:
            continue
        out.append((number, raw))
    return out


def quote_mask(line: str) -> list[bool]:
    """Indicate whether characters are within quotation marks on a single line.

    This is a source quote detector, not a reliable speaker attribution system.
    """
    mask = [False] * len(line)
    stack: list[str] = []
    for i, ch in enumerate(line):
        if ch in QUOTE_OPEN:
            stack.append(QUOTE_OPEN[ch])
            continue
        if ch in QUOTE_CLOSE and stack and stack[-1] == ch:
            stack.pop()
            continue
        if ch in {'"', '＂'}:
            if stack and stack[-1] == ch:
                stack.pop()
            elif not stack:
                stack.append(ch)
            continue
        mask[i] = bool(stack)
    return mask


def match_location(mask: list[bool], start: int, end: int) -> str:
    flags = mask[start:end]
    if flags and all(flags):
        return "引号内"
    if any(flags):
        return "含引号边界"
    return "引号外"


def count_hanzi(text: str) -> int:
    return len(re.findall(r"[\u3400-\u9fff]", text))


def analyze_content(text: str, *, source: str = "(text)") -> dict[str, Any]:
    lines = prose_lines(text)
    findings: list[dict[str, Any]] = []
    excerpts: list[str] = []
    repeated: dict[str, list[tuple[int, str]]] = {term: [] for term in WATCH_REPEAT}

    for line_no, line in lines:
        excerpts.append(line)
        mask = quote_mask(line)
        seen = set()
        for code, title, pat, advice in COMPILED:
            for hit in pat.finditer(line):
                # Do not double-report identical positions from different patterns.
                key = (hit.start(), hit.end(), code)
                if key in seen:
                    continue
                seen.add(key)
                findings.append({
                    "code": code, "title": title, "line": line_no,
                    "column": hit.start() + 1,
                    "matched": hit.group(0),
                    "context": line.strip()[:130],
                    "quote_scope": match_location(mask, hit.start(), hit.end()),
                    "review_hint": advice,
                    "kind": "需要语境判断的词面线索",
                })
        for term in WATCH_REPEAT:
            for hit in re.finditer(re.escape(term), line):
                repeated[term].append((line_no, line.strip()[:115]))

    # An optional coarse repetition heads-up. There is no quality-based threshold.
    repeats = [
        {"term": term, "count": len(hits), "sample_lines": [ln for ln, _ in hits[:5]]}
        for term, hits in repeated.items() if len(hits) >= 6
    ]
    joined = "\n".join(excerpts)
    sentence_lengths = [count_hanzi(seg) for seg in re.split(r"[。！？!?]+", joined)]
    sentence_lengths = [n for n in sentence_lengths if n >= 2]
    dialogue_start = sum(bool(re.match(r"^\s*[“「『\"]", line)) for _, line in lines)
    # Informational only: uninterrupted dialogue paragraphs are not automatically
    # "ping-pong" conversations because the code does not identify speakers.
    longest_dialogue_run = 0
    current_dialogue_run = 0
    for _, line in lines:
        if re.match(r"^\s*[“「『\"]", line):
            current_dialogue_run += 1
            longest_dialogue_run = max(longest_dialogue_run, current_dialogue_run)
        else:
            current_dialogue_run = 0
    stat: dict[str, Any] = {
        "chinese_characters": count_hanzi(joined),
        "prose_nonempty_lines": len(lines),
        "sentences_approx": len(sentence_lengths),
        "sentence_length_median_approx": round(statistics.median(sentence_lengths), 1) if sentence_lengths else 0,
        "sentence_length_sd_approx": round(statistics.pstdev(sentence_lengths), 1) if len(sentence_lengths) > 1 else 0,
        "dialogue_start_lines": dialogue_start,
        "longest_quoted_line_run": longest_dialogue_run,
        "emdashes": joined.count("——"),
        "simile_intro_words": sum(len(re.findall(rf"{re.escape(term)}", joined)) for term in ["仿佛", "宛如", "如同", "犹如"]),
    }
    findings.sort(key=lambda x: (x["line"], x["column"]))
    return {
        "source": source,
        "sha256": sha256(text.encode("utf-8")).hexdigest(),
        "purpose": "只读疑点索引；不提供 AI 味分数、不自动判定文学质量",
        "stats": stat,
        "findings": findings,
        "repetition_hints": repeats,
    }


def escape_markdown(text: str) -> str:
    return text.replace("`", "\\`").replace("\r", " ").replace("\n", " ")


def render_markdown(result: dict[str, Any], max_show: int = 40) -> str:
    s = result["stats"]
    out = [
        "# 中文小说语言疑点索引（自动辅助；非文学评分）", "",
        f"- 文件：`{escape_markdown(result['source'])}`",
        f"- 原文 SHA-256：`{result['sha256']}`",
        f"- 规模：汉字约 {s['chinese_characters']}；约 {s['sentences_approx']} 句；原文行数（不含标题/代码块）{s['prose_nonempty_lines']}",
        f"- 描述性统计：句长中位数约 {s['sentence_length_median_approx']} 字；句长标准差约 {s['sentence_length_sd_approx']}；破折号 {s['emdashes']} 处；引号起首行 {s['dialogue_start_lines']} 行；最长连续引号起首行 {s['longest_quoted_line_run']} 行",
        "",
        "**注意：统计量不是通过条件；检测命中不是文风错误。连续对白不能由此自动认定为‘传球式对白’。**",
        "", "## 待人工阅读确认的候选位置", "",
    ]
    if not result["findings"]:
        out.append("未命中预置高风险词面模式。**这不意味着没有文风问题；也不意味着已完成文学审读。**")
    else:
        for x in result["findings"][:max_show]:
            out.extend([
                f"- **L{x['line']}:{x['column']} · {x['title']}**（{x['quote_scope']}）：`{escape_markdown(x['matched'])}`",
                f"  - 上下文：{escape_markdown(x['context'])}",
                f"  - 核验：{x['review_hint']}",
            ])
        remaining = len(result["findings"]) - max_show
        if remaining > 0:
            out.append(f"- 另有 {remaining} 条词面命中未展开；如需全量索引，请输出 JSON。")
    out.extend(["", "## 重复用词提醒（不代表必须替换）", ""])
    if result["repetition_hints"]:
        for x in result["repetition_hints"]:
            out.append(f"- `{x['term']}` 共 {x['count']} 次，示例行号：{', '.join(map(str,x['sample_lines']))}。只检查是否服务叙事。")
    else:
        out.append("暂无达到提醒阈值的观察词。")
    out.extend(["", "## 请由读稿者补完的文学判断", "", "- 哪 1–3 处最值得保留？为什么？", "- 最影响阅读的至多 5 个问题是什么？", "- 哪些命中应当明确保留？", "- 修改会损失什么？", ""])
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="只读中文小说文风疑点扫描，不打分，不编辑文件")
    ap.add_argument("file", type=Path, help="单个 UTF-8 正文文件")
    ap.add_argument("--format", choices=["markdown", "json"], default="markdown")
    ap.add_argument("--out", type=Path, help="报告路径；缺省输出到标准输出")
    ap.add_argument("--max-show", type=int, default=40, help="Markdown 中最多展开多少条词面命中")
    args = ap.parse_args()
    path: Path = args.file.expanduser().resolve()
    if not path.is_file():
        ap.error(f"正文不存在：{path}")
    if args.out and args.out.expanduser().resolve() == path:
        ap.error("报告文件不得覆盖原文")
    try:
        content, original_hash = read_source(path)
    except UnicodeDecodeError:
        ap.error("正文需为 UTF-8 文本")
    result = analyze_content(content, source=str(path))
    result["sha256"] = original_hash
    body = json.dumps(result, ensure_ascii=False, indent=2) + "\n" if args.format == "json" else render_markdown(result, args.max_show)
    if args.out:
        outpath = args.out.expanduser().resolve()
        try:
            write_new(outpath, body)
        except FileExistsError:
            ap.error("报告路径已存在；请另起文件名，不覆盖任何已有文件")
        print(f"已写入只读扫描报告：{outpath}")
    else:
        print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
