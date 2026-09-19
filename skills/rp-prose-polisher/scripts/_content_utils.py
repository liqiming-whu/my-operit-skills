#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
正文提取与字数统计 — 供全部检测脚本和前置检查脚本共享使用。

包含两个函数：
  - count_chinese_chars(text)  : 统计文本中中文字符数（去除 markdown 标记后）
  - extract_content(file_path) : 从文件中提取正文内容，跳过章节标题行之前的内容

所有脚本导入此模块以确保正文提取和字数统计口径一致。
"""

import re
from pathlib import Path


def count_chinese_chars(text: str) -> int:
    """统计中文字数（与其他检测脚本保持一致）"""
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'~~(.*?)~~', r'\1', text)
    text = re.sub(r'`(.*?)`', r'\1', text)
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    return len(chinese_chars)


def extract_content(file_path: Path) -> str:
    """从章节文件中提取正文内容（跳过第一个 #章/回合 标题行之前的内容）"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    lines = content.split('\n')
    content_start = 0
    for i, line in enumerate(lines):
        if line.startswith('#') and ('章' in line or '回合' in line):
            content_start = i + 1
            break
    return '\n'.join(lines[content_start:])
