#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对话掩码工具 — 供 check_cliche.py / check_content_review.py 共享使用。
"""


def _mask_toggle_quotes(text: str, mask: list, quote_char: str):
    """
    为开闭符相同的引号（如 " 和 "）构建掩码。
    奇数次出现=开，偶数次=闭。未闭合则标记到行末。
    """
    i = 0
    toggle_open = -1
    while i < len(text):
        pos = text.find(quote_char, i)
        if pos == -1:
            break
        if toggle_open == -1:
            toggle_open = pos
        else:
            for j in range(toggle_open + 1, pos):
                mask[j] = True
            toggle_open = -1
        i = pos + 1
    if toggle_open != -1:
        line_end = text.find('\n', toggle_open)
        if line_end == -1:
            line_end = len(text)
        for j in range(toggle_open + 1, line_end):
            mask[j] = True


def build_dialogue_mask(text: str) -> list:
    """
    构建字符级对话掩码：mask[i] 为 True 表示位置 i 的字符处于对话引号内部。

    支持的引号对（覆盖中文书写全部常见引号）：
      - "" (U+201C / U+201D) — 中文弯引号
      - "" (U+0022)          — ASCII 双引号，开闭同符，奇偶成对
      - "" (U+FF02)           — 全角双引号，开闭同符，奇偶成对
      - 「」 (U+300C / U+300D) — 中文直角引号
      - '' (U+2018 / U+2019) — 中文单引号（内心独白、特殊标记等）
      - 『』 (U+300E / U+300F) — 双直角引号（嵌套引用、书名号等）

    未闭合引号视为从开口到该行末尾的对话延续。
    """
    mask = [False] * len(text)

    # 开闭符不同的引号对
    quote_pairs = [
        ('\u201c', '\u201d'),   # "…"
        ('\u300c', '\u300d'),   # 「…」
        ('\u2018', '\u2019'),   # '…' 中文单引号（内心独白等）
        ('\u300e', '\u300f'),   # 『…』 双直角引号（嵌套引用/书名）
    ]

    for open_q, close_q in quote_pairs:
        i = 0
        while i < len(text):
            open_pos = text.find(open_q, i)
            if open_pos == -1:
                break
            close_pos = text.find(close_q, open_pos + 1)
            if close_pos == -1:
                line_end = text.find('\n', open_pos)
                if line_end == -1:
                    line_end = len(text)
                for j in range(open_pos + 1, line_end):
                    mask[j] = True
                i = open_pos + 1
            else:
                for j in range(open_pos + 1, close_pos):
                    mask[j] = True
                i = close_pos + 1

    # 开闭同符的引号（奇偶成对匹配）
    for q in ['\u0022', '\uff02']:  # " (ASCII) 和 " (全角)
        _mask_toggle_quotes(text, mask, q)

    return mask
