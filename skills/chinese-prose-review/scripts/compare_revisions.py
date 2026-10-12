#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare an original Chinese novel chapter with its separately saved candidate.

The report is descriptive, and a decrease in regex findings is not a quality score.
Does not write either input file.
"""
from __future__ import annotations

import argparse
from collections import Counter
import difflib
from pathlib import Path
from scan_prose import analyze_content
from safe_files import read_source, write_new


def md_escape(x: str) -> str:
    return x.replace("`", "\\`")


def comparison(before: str, after: str, old_label: str, new_label: str, max_diff_lines: int = 100, *, original_hash=None, candidate_hash=None) -> str:
    o = analyze_content(before, source=old_label)
    n = analyze_content(after, source=new_label)
    if original_hash is not None:
        o["sha256"] = original_hash
    if candidate_hash is not None:
        n["sha256"] = candidate_hash
    a = before.splitlines(keepends=True)
    b = after.splitlines(keepends=True)
    changed = sum(tag != "equal" for tag, _, _, _, _ in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes())
    old_patterns = Counter(x["code"] for x in o["findings"])
    new_patterns = Counter(x["code"] for x in n["findings"])
    summary = [
        "# 中文小说修订回验（版本差异与待审信号）", "",
        f"- 原稿：`{md_escape(old_label)}`",
        f"- 候选：`{md_escape(new_label)}`",
        f"- 原稿 SHA-256：`{o['sha256']}`",
        f"- 候选 SHA-256：`{n['sha256']}`",
        f"- 汉字数：{o['stats']['chinese_characters']} → {n['stats']['chinese_characters']}",
        f"- 发生变化的差异块约 {changed} 处（用于定位，不是改稿质量评分）", "",
        "**词面命中变化不代表文学质量变化。请读完整章，尤其检查原稿好句是否被误伤。**", "",
        "## 规则命中增减（仅供定位）", "",
    ]
    for typ in sorted(set(old_patterns) | set(new_patterns)):
        delta = new_patterns[typ] - old_patterns[typ]
        summary.append(f"- `{typ}`：{old_patterns[typ]} → {new_patterns[typ]}（变化 {delta:+d}）")
    if not old_patterns and not new_patterns:
        summary.append("- 两个版本均未命中预置词面模式；仍需人工审读。")
    summary.extend(["", "## 修改片段（节选）", "", "```diff"])
    diff = list(difflib.unified_diff(a, b, fromfile=old_label, tofile=new_label, n=2))
    summary.extend(s.rstrip("\n") for s in diff[:max_diff_lines])
    summary.append("```")
    if len(diff) > max_diff_lines:
        summary.append(f"\n已截取前 {max_diff_lines} 行差异，共 {len(diff)} 行。需要时可增加 `--max-diff-lines`。")
    summary.extend(["", "## 人工回验", "", "- 原来最值得保留的对白、留白、意象是否还在？", "- 哪些修改真正改善了阅读，哪些只是为消除词面命中？", "- 修改是否改变事实、人物口吻、时间/地点/视角或重要信息？（需独立事实审计）", ""])
    return "\n".join(summary)


def main() -> int:
    ap = argparse.ArgumentParser(description="比较原稿与候选；只生成报告，不修改任何输入文件")
    ap.add_argument("original", type=Path)
    ap.add_argument("candidate", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--expected-original-sha256", help="修改前保存的原稿字节哈希；不一致则拒绝回验")
    ap.add_argument("--max-diff-lines", type=int, default=100)
    args = ap.parse_args()
    oldp, newp = args.original.expanduser().resolve(), args.candidate.expanduser().resolve()
    if not oldp.is_file() or not newp.is_file():
        ap.error("原稿或修订候选不存在")
    if oldp.samefile(newp):
        ap.error("原稿与候选必须是不同文件")
    if args.out and args.out.expanduser().resolve() in {oldp, newp}:
        ap.error("报告文件不得覆盖原稿或候选")
    try:
        before, old_hash = read_source(oldp)
        after, new_hash = read_source(newp)
    except UnicodeDecodeError:
        ap.error("文件需为 UTF-8 编码")
    if args.expected_original_sha256 and old_hash != args.expected_original_sha256.lower():
        ap.error("原稿 SHA-256 与修改前基线不一致；停止回验")
    result = comparison(before, after, str(oldp), str(newp), max(0, args.max_diff_lines), original_hash=old_hash, candidate_hash=new_hash)
    if args.out:
        path = args.out.expanduser().absolute()
        try:
            write_new(path, result)
        except FileExistsError:
            ap.error("报告路径已存在；请另起文件名，不覆盖任何已有文件")
        print(f"已写入对照报告：{path}")
    else:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
