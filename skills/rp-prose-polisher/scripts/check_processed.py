#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
前置检查与标记脚本 — 供 SKILL.md 步骤 1（前置检查）和步骤 11（打标记）使用。

用法:
  前置检查:  python check_processed.py <文件路径>
  打标记:    python check_processed.py --stamp <文件路径>

输出 STATUS= 行供 AI 解析：
  FILE_NOT_FOUND   — 文件不存在
  FILE_EMPTY       — 文件存在但无中文内容（空白或仅符号）
  ALREADY_PROCESSED— 文件已包含处理标记
  READY            — 文件就绪，可以开始处理
"""

import sys
from pathlib import Path

# 从共享模块导入，确保与所有检测脚本使用相同的正文提取和字数统计逻辑
sys.path.insert(0, str(Path(__file__).parent))
from _content_utils import count_chinese_chars, extract_content

PROCESSED_MARKER = "<!-- prose-polisher:processed:v1 -->"


def do_stamp(file_path: str) -> None:
    """在文件开头添加处理标记（不重复打标记）"""
    path = Path(file_path)
    if not path.exists():
        print("STAMP_FAILED: 文件不存在")
        sys.exit(1)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if PROCESSED_MARKER in content:
        print("STAMP_SKIPPED: 标记已存在，跳过")
        return

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(PROCESSED_MARKER + '\n\n' + content)

    print("STAMP_OK")


def do_check(file_path: str) -> None:
    """检查文件状态（使用 extract_content 确保与检测脚本统计口径一致）"""
    path = Path(file_path)

    if not path.exists():
        print("STATUS=FILE_NOT_FOUND")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        raw_content = f.read()

    if PROCESSED_MARKER in raw_content:
        print("STATUS=ALREADY_PROCESSED")
        return

    # 使用 extract_content 获取正文，与所有检测脚本保持一致
    body = extract_content(path)
    if count_chinese_chars(body) == 0:
        print("STATUS=FILE_EMPTY")
        return

    print("STATUS=READY")


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  前置检查: python check_processed.py <文件路径>")
        print("  打标记:   python check_processed.py --stamp <文件路径>")
        sys.exit(1)

    if sys.argv[1] == '--stamp':
        if len(sys.argv) < 3:
            print("错误: --stamp 需要指定文件路径")
            sys.exit(1)
        do_stamp(sys.argv[2])
    else:
        do_check(sys.argv[1])


if __name__ == '__main__':
    main()
