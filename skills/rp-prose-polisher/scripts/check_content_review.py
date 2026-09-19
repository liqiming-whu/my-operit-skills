#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容自查检测脚本
检测章节文件中的重复句式、句长单一、描写词汇重复、段落结构模版化、传球式对话。
对标 check_ai_flavor.py 的设计风格，用于步骤 6 的自动化检测。
"""

import os
import re
import sys
import statistics
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent))
from _dialogue_utils import build_dialogue_mask, _mask_toggle_quotes
from _content_utils import count_chinese_chars, extract_content

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


# ============================================================
# 检测规则定义
# ============================================================

# 规则A1：连续同主语开头检测 — 主语词列表 + 连续阈值
# 仅检测人称代词，不纳入其他名词（角色名、物件名等），避免润色时来回反复修改
REPEATED_SUBJECT_WORDS = ['我', '他', '她']
REPEATED_SUBJECT_THRESHOLD = 3  # 连续3句同主语开头即标记

# 规则A2：句长分布 — 标准差阈值（字数）
SENTENCE_LENGTH_STDEV_MIN = 3.0   # 标准差低于此值说明句长过于均匀
SENTENCE_LENGTH_SAMPLE_SIZE = 10  # 滑动窗口大小

# 规则A3：高频描写词汇 — (词, 阈值) 同一章出现超过阈值次即警告
HIGH_FREQ_DESCRIPTORS = [
    # 表情/眉眼
    ('皱眉', 3), ('眉头', 3), ('眉心', 3), ('眉宇', 3),
    ('目光', 3), ('眼神', 3), ('视线', 3), ('眼眸', 3), ('眸子', 3),
    ('眼眶', 3), ('眼角', 3),
    # 手部动作
    ('拳头', 3), ('攥', 4), ('握紧', 3), ('指节', 3),
    # 呼吸/身体（心跳/呼吸类，非互动道具）
    ('呼吸', 4), ('深吸', 3), ('屏住', 3),
    ('心脏', 3), ('心跳', 3),
    # 姿态/动作
    ('转身', 3), ('回头', 3),
    ('脚步', 3), ('后退', 3), ('上前', 3),
    ('沉默', 3), ('安静', 3),
    ('颤抖', 3), ('僵硬', 3),
    # 语气/声音
    ('低声', 3), ('沉声', 3), ('冷冷', 3), ('淡淡', 3),
    ('轻笑', 3), ('冷笑', 3), ('苦笑', 3), ('叹气', 3), ('叹了口气', 3),
    # 视觉
    ('瞥', 4), ('扫了', 3), ('盯着', 3), ('注视', 3),
]

# 规则A4：段落结构模版 — 检测同一模式连续出现
# 段落类型标记：D=对话行, A=动作/叙述行, P=心理/内心独白行
# 连续3段以上相同模式组合即警告（如 D-A-P, D-A-P, D-A-P）

# 规则C1：传球式对话 — 连续交替台词
# 检测纯台词行交替出现 >= 7 步（连续超过6条对话即判定）

# ============================================================
# 工具函数
# ============================================================

def split_sentences(text: str) -> list:
    """将中文文本分割为句子列表，每项为 (句子文本, 行号)"""
    lines = text.split('\n')
    sentences = []
    for line_no, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            continue
        # 跳过纯Markdown标记行
        if re.match(r'^[#>*-]', stripped) and len(stripped) < 5:
            continue
        # 用句末标点分割
        parts = re.split(r'([。！？…\.!\?]+)', stripped)
        current = ''
        for part in parts:
            if re.match(r'^[。！？…\.!\?]+$', part):
                current += part
                if current.strip():
                    sentences.append((current.strip(), line_no))
                current = ''
            else:
                current += part
        if current.strip():
            sentences.append((current.strip(), line_no))
    return sentences


def is_dialogue_line(text: str) -> bool:
    """判断一行是否主要是对话（以引号开头或包含大量对话内容）"""
    stripped = text.strip()
    # 以引号开头
    if stripped.startswith('"') or stripped.startswith('"') or stripped.startswith('「'):
        return True
    # 包含引号且引号内文字占比高
    quote_matches = re.findall(r'[""「」]([^""「」]+)[""「」]', stripped)
    if quote_matches:
        quote_chars = sum(count_chinese_chars(q) for q in quote_matches)
        total_chars = count_chinese_chars(stripped)
        if total_chars > 0 and quote_chars / total_chars > 0.4:
            return True
    return False


def get_first_chinese_char(text: str) -> str:
    """获取文本中第一个中文字符"""
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff':
            return ch
    return ''


# ============================================================
# 检测函数
# ============================================================

def check_a1_subject_repetition(content: str) -> list:
    """检测连续同主语开头（仅检测同一人称代词连续出现，不同主语交替不算）"""
    issues = []
    lines = content.split('\n')
    n = len(lines)
    i = 0
    while i < n:
        stripped = lines[i].strip()
        if not stripped or len(stripped) < 3:
            i += 1
            continue
        first_ch = get_first_chinese_char(stripped)
        if first_ch not in REPEATED_SUBJECT_WORDS:
            i += 1
            continue

        # 以目标人称代词开头 → 向后扫描同一主语连续出现的句子
        current_subj = first_ch
        consecutive = [(i + 1, current_subj, stripped[:60])]
        j = i + 1
        while j < n:
            next_stripped = lines[j].strip()
            # 允许一行空行（常见段落分隔），跳过并继续
            if not next_stripped:
                j += 1
                continue
            if len(next_stripped) < 3:
                j += 1
                continue
            next_ch = get_first_chinese_char(next_stripped)
            if next_ch == current_subj:
                # 同一主语 → 加入连续组
                consecutive.append((j + 1, next_ch, next_stripped[:60]))
                j += 1
            else:
                # 主语不同 → 连续组终止
                break

        if len(consecutive) >= REPEATED_SUBJECT_THRESHOLD:
            issues.append({
                'type': '重复句式:连续同主语',
                'line': consecutive[0][0],
                'match': f'连续{len(consecutive)}句以"{current_subj}"开头',
                'content': ' | '.join([t[:40] for _, _, t in consecutive]),
            })
            i = j  # 跳过已检测组
        else:
            i += 1
    return issues


def check_a2_sentence_length(content: str) -> list:
    """检测句长分布是否过于均匀"""
    issues = []
    lines = content.split('\n')
    # 收集所有有效句子的字数
    all_sentence_lengths = []
    sentence_samples = []  # (line_no, sentence_text, length)

    for line_no, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or len(stripped) < 5:
            continue
        if re.match(r'^[#>*-]', stripped) and len(stripped) < 10:
            continue

        # 按句末标点拆分
        parts = re.split(r'([。！？…])', stripped)
        current = ''
        for part in parts:
            if part in '。！？…':
                current += part
                cn_chars = count_chinese_chars(current)
                if cn_chars >= 5:
                    all_sentence_lengths.append(cn_chars)
                    sentence_samples.append((line_no, current[:60], cn_chars))
                current = ''
            else:
                current += part

    if len(all_sentence_lengths) < 10:
        return issues  # 句子太少，不做统计

    # 计算整体标准差
    overall_stdev = statistics.stdev(all_sentence_lengths) if len(all_sentence_lengths) > 1 else 0

    if overall_stdev < SENTENCE_LENGTH_STDEV_MIN:
        avg_len = statistics.mean(all_sentence_lengths)
        issues.append({
            'type': '句长单一',
            'line': 0,
            'match': f'句长标准差 {overall_stdev:.1f}（阈值≥{SENTENCE_LENGTH_STDEV_MIN}），平均句长 {avg_len:.0f}字',
            'content': f'共{len(all_sentence_lengths)}句，句长集中在{avg_len:.0f}字附近，缺乏长短变化',
        })

    # 滑动窗口检测：连续N句长度波动过小
    window_size = SENTENCE_LENGTH_SAMPLE_SIZE
    for i in range(len(sentence_samples) - window_size + 1):
        window = sentence_samples[i:i + window_size]
        lengths = [w[2] for w in window]
        window_stdev = statistics.stdev(lengths) if len(lengths) > 1 else 0
        if window_stdev < 2.0:  # 10句内标准差小于2，非常均匀
            issues.append({
                'type': '句长单一(局部)',
                'line': window[0][0],
                'match': f'连续{window_size}句长度标准差 {window_stdev:.1f}（几乎等长）',
                'content': f'示例: {window[0][1][:50]} ...',
            })
            break  # 只报一次
    return issues


def check_a3_descriptor_frequency(content: str) -> list:
    """检测高频描写词汇"""
    issues = []
    for word, threshold in HIGH_FREQ_DESCRIPTORS:
        count = content.count(word)
        if count >= threshold:
            # 找到匹配行
            lines = content.split('\n')
            match_lines = []
            for i, line in enumerate(lines, 1):
                if word in line:
                    match_lines.append(str(i))

            issues.append({
                'type': '描写词重复',
                'line': int(match_lines[0]) if match_lines else 0,
                'match': f'"{word}" 出现 {count} 次（阈值≥{threshold}次）',
                'content': f'分布行: {", ".join(match_lines[:8])}{"..." if len(match_lines) > 8 else ""}',
            })
    return issues


def check_a4_paragraph_pattern(content: str) -> list:
    """检测段落结构模版化（重构版：段落级对话密度 + 类型集中度）"""
    issues = []

    # 构建对话掩码（来自 _dialogue_utils 共享模块）
    dialogue_mask = build_dialogue_mask(content)

    # 按空行分割段落，同时记录每个段落在原文中的字符偏移范围
    lines = content.split('\n')
    paragraphs = []  # [(start_pos, end_pos, para_text), ...]
    pos = 0
    para_start = None
    para_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if para_lines:
                para_text = '\n'.join(para_lines)
                paragraphs.append((para_start, pos - 1, para_text))
                para_lines = []
                para_start = None
        else:
            if para_start is None:
                para_start = pos
            para_lines.append(line)
        pos += len(line) + 1  # +1 for newline

    # 最后一个段落
    if para_lines:
        para_text = '\n'.join(para_lines)
        paragraphs.append((para_start, pos - 1, para_text))

    # 分类每个段落（对话密度三区间，对齐 content-review-guide.md A4 定义）
    para_types = []
    para_lengths = []

    for start, end, para_text in paragraphs:
        total_chars = count_chinese_chars(para_text)
        if total_chars < 20:  # 过短段落跳过
            continue

        # 计算段落内处于对话引号内的中文字符数
        dialogue_chars = 0
        for p in range(start, min(end, len(dialogue_mask))):
            if dialogue_mask[p] and '\u4e00' <= content[p] <= '\u9fff':
                dialogue_chars += 1

        dialogue_ratio = dialogue_chars / total_chars if total_chars > 0 else 0

        # 三区间分类
        if dialogue_ratio >= 0.7:
            para_types.append('纯对话段')
        elif dialogue_ratio <= 0.1:
            para_types.append('纯叙述/心理段')
        else:
            para_types.append('混合段')

        para_lengths.append(total_chars)

    if len(para_types) < 3:
        return issues  # 段落太少，不做统计

    # 检测类型集中度：同一类型占比 > 90% 即警告
    type_counts = Counter(para_types)
    dominant_count = max(type_counts.values())
    dominant_ratio = dominant_count / len(para_types)

    if dominant_ratio > 0.9:
        dominant_type = max(type_counts, key=type_counts.get)
        if dominant_type == '混合段':
            suggestion = '纯对话段或纯叙述/心理段'
        else:
            suggestion = '混合段或其他类型段落'
        issues.append({
            'type': '段落结构模版',
            'line': 0,
            'match': f'共 {len(para_types)} 段中，{dominant_count} 段（{dominant_ratio*100:.0f}%）为「{dominant_type}」',
            'content': f'占比超过 90% 阈值。建议插入 {suggestion} 打破单调。',
        })

    # 辅助检测：段落长度方差（变异系数 < 0.3 说明段落长度高度集中）
    if len(para_lengths) >= 5:
        avg_len = statistics.mean(para_lengths)
        stdev = statistics.stdev(para_lengths)
        if avg_len > 0 and stdev / avg_len < 0.3:
            issues.append({
                'type': '段落长度单一',
                'line': 0,
                'match': f'段落长度变异系数 {stdev/avg_len:.2f}（标准差 {stdev:.0f} 字，均值 {avg_len:.0f} 字）',
                'content': f'共 {len(para_lengths)} 段，段落长度高度集中，缺乏长短变化',
            })

    return issues


def check_c1_pingpong_dialogue(content: str) -> list:
    """检测传球式对话"""
    issues = []
    lines = content.split('\n')

    # 提取连续对话块
    dialogue_blocks = []
    current_block = []

    for line_no, line in enumerate(lines, 1):
        stripped = line.strip()
        if is_dialogue_line(stripped):
            current_block.append((line_no, stripped))
        else:
            if len(current_block) >= 7:
                dialogue_blocks.append(current_block)
            current_block = []
    if len(current_block) >= 7:
        dialogue_blocks.append(current_block)

    for block in dialogue_blocks:
        if len(block) >= 7:  # 至少7句纯对话（连续超过6条即判定为传球式）
            issues.append({
                'type': '传球式对话',
                'line': block[0][0],
                'match': f'连续 {len(block)} 句纯对话无动作/心理穿插',
                'content': f'从 L{block[0][0]} "{block[0][1][:40]}..." 到 L{block[-1][0]} "{block[-1][1][:40]}..."',
            })
    return issues


def check_content_review(file_path: str) -> dict:
    """执行所有内容自查检测"""
    path = Path(file_path)

    if not path.exists():
        return {
            'file': str(path),
            'exists': False,
            'total_score': 0,
            'status': 'error',
            'issues': [],
            'message': f'文件不存在: {file_path}'
        }

    content = extract_content(path)
    total_chars = count_chinese_chars(content)

    if total_chars == 0:
        return {
            'file': str(path),
            'exists': True,
            'total_chars': 0,
            'total_score': 0,
            'status': 'empty',
            'issues': [],
            'message': '文件为空（无中文字符），请先输入正文内容'
        }

    all_issues = []

    # A1: 连续同主语
    all_issues.extend(check_a1_subject_repetition(content))

    # A2: 句长分布
    all_issues.extend(check_a2_sentence_length(content))

    # A3: 描写词汇重复
    all_issues.extend(check_a3_descriptor_frequency(content))

    # A4: 段落结构模版
    all_issues.extend(check_a4_paragraph_pattern(content))

    # C1: 传球式对话
    all_issues.extend(check_c1_pingpong_dialogue(content))

    # 按行号排序
    all_issues.sort(key=lambda x: x['line'])

    # 计算得分：每千字问题数
    score_per_1000 = (len(all_issues) / total_chars) * 1000 if total_chars > 0 else 0

    # 判定：每千字 ≤ 3 个问题为通过
    threshold = 3.0
    status = 'pass' if score_per_1000 <= threshold else 'fail'

    return {
        'file': str(path),
        'exists': True,
        'total_chars': total_chars,
        'issue_count': len(all_issues),
        'score_per_1000': round(score_per_1000, 2),
        'threshold': threshold,
        'status': status,
        'issues': all_issues,
        'message': f'内容问题密度: {score_per_1000:.2f}/千字 (阈值: {threshold}/千字)'
    }


def check_all_chapters(directory: str, pattern: str = '第*.md') -> list:
    """检查目录下所有章节"""
    dir_path = Path(directory)
    if not dir_path.exists():
        print(f'错误: 目录不存在 - {directory}')
        return []

    chapter_files = sorted(dir_path.glob(pattern))
    results = []
    for chapter_file in chapter_files:
        result = check_content_review(str(chapter_file))
        results.append(result)
    return results


def print_results(results: list, threshold: float = 3.0):
    """打印检测报告"""
    if not results:
        print('没有找到章节文件')
        return

    total_issues = 0
    passed = 0
    failed = 0
    all_issues_by_type = {}

    print('\n' + '=' * 60)
    print('内容自查检测报告')
    print('=' * 60)

    for result in results:
        if not result['exists']:
            print(f'\n❌ {result["file"]}')
            print(f'   {result["message"]}')
            continue

        total_issues += result['issue_count']

        if result['status'] == 'pass':
            passed += 1
            icon = '✅'
        else:
            failed += 1
            icon = '⚠️ '

        print(f'\n{icon} {Path(result["file"]).name}')
        print(f'   总字数: {result["total_chars"]:,}')
        print(f'   内容问题数: {result["issue_count"]}')
        print(f'   密度: {result["score_per_1000"]:.2f}/千字 (阈值: {threshold}/千字)')

        # 按类型统计
        for issue in result.get('issues', []):
            t = issue['type']
            all_issues_by_type[t] = all_issues_by_type.get(t, 0) + 1

        # 显示所有问题（带行号）
        if result['issues']:
            print(f'   问题详情:')
            for issue in result['issues']:
                if issue['line'] > 0:
                    print(f'     L{issue["line"]:>4d} [{issue["type"]}] {issue["match"]}')
                else:
                    print(f'     ---   [{issue["type"]}] {issue["match"]}')
                print(f'           {issue["content"]}')

    print('\n' + '-' * 60)
    print(f'总计: {len(results)} 章 | {passed} 章通过 | {failed} 章需润色 | 总问题数: {total_issues}')
    print('-' * 60)

    if all_issues_by_type:
        print(f'\n问题类型分布:')
        sorted_types = sorted(all_issues_by_type.items(), key=lambda x: x[1], reverse=True)
        for t, count in sorted_types:
            bar = '█' * min(count, 30)
            print(f'  {t:<25s} {count:>3d} {bar}')

    if failed > 0:
        print(f'\n⚠️  有 {failed} 章内容问题超标，建议执行内容自查润色:')
        print(f'   1. 先处理"重复句式"和"描写词重复"（最快见效）')
        print(f'   2. 再处理"传球式对话"和"段落结构模版"（改善阅读节奏）')
        print(f'   3. 最后通读全章检查角色性格一致性和互动生动性（需人工判断）')
        print(f'\n   参考: references/guides/content-review-guide.md')


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print('用法:')
        print('  检测单章: python check_content_review.py <章节文件路径>')
        print('  检测全部: python check_content_review.py --all <目录路径>')
        print('')
        print('示例:')
        print('  python check_content_review.py novels/故事/第01章.md')
        print('  python check_content_review.py --all novels/故事')
        return

    if sys.argv[1] == '--all':
        if len(sys.argv) < 3:
            print('错误: 使用 --all 时需要指定目录路径')
            return
        directory = sys.argv[2]
        results = check_all_chapters(directory)
        print_results(results)
    else:
        file_path = sys.argv[1]
        result = check_content_review(file_path)
        print_results([result])


if __name__ == '__main__':
    main()
