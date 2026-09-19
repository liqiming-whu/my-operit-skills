#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
八股文禁令检测脚本 — 对应 polishing-guide.md 规则七（全部八子类）。
检测：破折号滥用、总结套话、心理副词、模糊限定词、
"不是…而是…"句式、心理陈述、二元套话、时间状语精简。
对标 check_ai_flavor.py 的设计风格。
"""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _dialogue_utils import build_dialogue_mask, _mask_toggle_quotes
from _content_utils import count_chinese_chars, extract_content

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


# ============================================================
# 检测规则定义（全部来自 polishing-guide.md 规则七）
# ============================================================

# 规则七 · 第二类：总结/概括性套话
BAN_SUMMARY_PHRASES = [
    '总而言之', '综上所述', '从某种意义上说', '从某种意义上讲',
    '总的来看', '总的来讲', '总的来说',
    '简而言之', '简言之',
    '概括来说', '概括而言',
    '一言以蔽之',
    '归根结底', '归根到底',
]

# 规则七 · 第三类：心理/行为副词
BAN_PSYCH_ADVERBS = [
    '不禁', '不由地', '不由得', '下意识地',
]

# 规则七 · 第四类：模糊限定词
BAN_VAGUE_MODIFIERS = [
    '或许', '也许', '大概',
]

# 规则七 · 第六类：第一人称心理陈述（叙述中，对话中不算）
BAN_FIRST_PERSON_MENTAL = [
    '我感到', '我觉得', '我认为',
]

# 规则七 · 第七类：二元对立套话
BAN_DICHOTOMY_PHRASES = [
    '一方面', '另一方面',
    '说实话', '不过说真的', '话说回来',
    '不过有一说一', '有一说一',
]

# 规则七 · 第八类：时间状语"的时候"
BAN_TIME_PHRASES = [
    '的时候',
]

# 规则七 · 第五类："不是……而是/是……"句式（正则）
BAN_NOT_BUT_PATTERNS = [
    (r'不是.{1,30}?而是', '八股句式: 不是...而是...'),
    (r'这不是.{1,30}?这是', '八股句式: 这不是...这是...'),
    (r'不是.{1,20}?是(?!的|因|为|不|没)', '八股句式: 不是...是...'),
]

# 规则七 · 第一类：破折号密度阈值（每千字破折号数量）
EMDASH_THRESHOLD_PER_1000 = 4  # 超过此值视为滥用


def find_line_numbers(text: str, pattern: str) -> list:
    """查找匹配模式所在的行号列表"""
    lines = text.split('\n')
    matches = []
    for i, line in enumerate(lines, 1):
        for m in re.finditer(pattern, line):
            matches.append({
                'line': i,
                'content': line.strip()[:80],
                'match': m.group(),
            })
    return matches


def find_word_line_numbers(text: str, word_list: list) -> list:
    """查找列表中的词在文本中的所有出现位置（同词同行多次出现分别记录）"""
    lines = text.split('\n')
    matches = []
    running_offset = 0
    for i, line in enumerate(lines, 1):
        for word in word_list:
            start = 0
            while True:
                pos = line.find(word, start)
                if pos == -1:
                    break
                matches.append({
                    'line': i,
                    'content': line.strip()[:80],
                    'match': word,
                    'char_offset': running_offset + pos,
                })
                start = pos + len(word)
        running_offset += len(line) + 1  # +1 for \n
    return matches


def _match_char_offset(text: str, line_no: int, match_word: str, lines: list) -> int:
    """
    给定行号和匹配词，返回该匹配项在全文中的字符偏移量。
    如果同一行出现多次，返回第一次出现的位置。
    """
    offset = 0
    for i in range(line_no - 1):
        offset += len(lines[i]) + 1  # +1 for newline
    line_text = lines[line_no - 1]
    pos_in_line = line_text.find(match_word)
    return offset + max(pos_in_line, 0)


def _is_in_dialogue(text: str, line_no: int, match_word: str,
                    content_lines: list, dialogue_mask: list,
                    char_offset: int = None) -> bool:
    """
    判断匹配词是否处于对话引号内部。
    复用 build_dialogue_mask 构建的字符级掩码。
    若提供 char_offset 则直接使用，否则回退到 _match_char_offset 推算。
    """
    if char_offset is None:
        char_offset = _match_char_offset(text, line_no, match_word, content_lines)
    match_end = char_offset + len(match_word)
    for pos in range(char_offset, min(match_end, len(dialogue_mask))):
        if dialogue_mask[pos]:
            return True
    return False


def check_cliche(file_path: str) -> dict:
    """检测单个章节的八股文痕迹"""
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

    issues = []

    # 规则七 · 第二类：总结套话
    summary_matches = find_word_line_numbers(content, BAN_SUMMARY_PHRASES)
    if summary_matches:
        for m in summary_matches:
            issues.append({
                'type': '八股:总结套话',
                'line': m['line'],
                'match': m['match'],
                'content': m['content'],
            })

    # 规则七 · 第三类：心理副词（对话中豁免）
    # 构建对话掩码（后续第三/四/六类共用）
    _dialogue_mask = build_dialogue_mask(content)
    _content_lines = content.split('\n')

    psych_matches = find_word_line_numbers(content, BAN_PSYCH_ADVERBS)
    if psych_matches:
        for m in psych_matches:
            # 过滤误匹配："不禁"不作为独立副词时跳过（如"禁不禁""不禁不"中的"不禁"）
            if m['match'] == '不禁':
                co = m.get('char_offset')
                if co is not None:
                    # 精准检查：此 "不禁" 是否处于复合词中
                    # "禁不禁" → "不禁" 前一个字是 "禁"
                    if co >= 1 and content[co - 1] == '禁':
                        continue
                    # "不禁不…" → "不禁" 后紧跟 "不"
                    if co + 2 < len(content) and content[co + 2] == '不':
                        continue
                else:
                    # 回退：旧的行级启发式（matches 无 char_offset 时使用）
                    if '情不自禁' in m['content'] or '不禁不' in m['content']:
                        continue
            # 对话中豁免：角色口语中的"我不禁笑了"等是自然的
            if _is_in_dialogue(content, m['line'], m['match'], _content_lines, _dialogue_mask,
                               m.get('char_offset')):
                continue
            issues.append({
                'type': '八股:心理副词',
                'line': m['line'],
                'match': m['match'],
                'content': m['content'],
            })

    # 规则七 · 第四类：模糊限定词（对话中豁免）
    vague_mod_matches = find_word_line_numbers(content, BAN_VAGUE_MODIFIERS)
    if vague_mod_matches:
        for m in vague_mod_matches:
            # 对话中豁免：角色口语中"或许吧""大概是这样"是自然的
            if _is_in_dialogue(content, m['line'], m['match'], _content_lines, _dialogue_mask,
                                m.get('char_offset')):
                continue
            issues.append({
                'type': '八股:模糊限定',
                'line': m['line'],
                'match': m['match'],
                'content': m['content'],
            })

    # 规则七 · 第六类：心理陈述（仅叙述中，对话中的"我感到/我觉得/我认为"正常保留）
    # 使用跨行对话掩码替代原来的行级判断，解决跨行对话的误判问题。
    first_person_matches = find_word_line_numbers(content, BAN_FIRST_PERSON_MENTAL)
    if first_person_matches:
        for m in first_person_matches:
            if _is_in_dialogue(content, m['line'], m['match'], _content_lines, _dialogue_mask,
                               m.get('char_offset')):
                continue  # 在对话引号内，正常保留
            issues.append({
                'type': '八股:心理陈述',
                'line': m['line'],
                'match': m['match'],
                'content': m['content'],
            })

    # 规则七 · 第七类：二元套话（对话与叙述统一检测，不区分豁免）
    dichotomy_matches = find_word_line_numbers(content, BAN_DICHOTOMY_PHRASES)
    if dichotomy_matches:
        for m in dichotomy_matches:
            issues.append({
                'type': '八股:二元套话',
                'line': m['line'],
                'match': m['match'],
                'content': m['content'],
            })

    # 规则七 · 第八类：时间状语"的时候"（对话中豁免）
    time_matches = find_word_line_numbers(content, BAN_TIME_PHRASES)
    if time_matches:
        for m in time_matches:
            # 对话中豁免：角色口语中的"的时候"是自然的
            if _is_in_dialogue(content, m['line'], m['match'], _content_lines, _dialogue_mask,
                                m.get('char_offset')):
                continue
            issues.append({
                'type': '八股:时间状语',
                'line': m['line'],
                'match': m['match'],
                'content': m['content'],
            })

    # 规则七 · 第五类："不是…而是…"句式
    for pattern, label in BAN_NOT_BUT_PATTERNS:
        notbut_matches = find_line_numbers(content, pattern)
        for m in notbut_matches:
            issues.append({
                'type': label,
                'line': m['line'],
                'match': m['match'],
                'content': m['content'],
            })

    # 规则七 · 第一类：破折号密度（独立计分，不纳入主 issue 池）
    # 每个「——」含 2 个「—」，故独立 — = 总 — 数 − 2×——数，最终处数 = ——数 + 独立数
    _pair = content.count('——')
    emdash_count = _pair + (content.count('—') - 2 * _pair)
    emdash_per_1000 = 0
    emdash_issues = []
    if total_chars > 0:
        emdash_per_1000 = (emdash_count / total_chars) * 1000
        if emdash_per_1000 > EMDASH_THRESHOLD_PER_1000:
            # 找到所有破折号所在行
            emdash_lines = []
            for i, line in enumerate(content.split('\n'), 1):
                if '——' in line or '—' in line:
                    emdash_lines.append(str(i))
            emdash_issues.append({
                'type': '八股:破折号滥用',
                'line': 0,  # 汇总级别
                'match': f'共{emdash_count}处破折号，密度{emdash_per_1000:.1f}/千字（阈值≤{EMDASH_THRESHOLD_PER_1000}/千字）',
                'content': f'分布行: {", ".join(emdash_lines[:10])}{"..." if len(emdash_lines) > 10 else ""}',
            })

    # 按行号排序（仅非破折号 issues）
    issues.sort(key=lambda x: x['line'])

    # 计算得分：每千字八股文痕迹数（越低越好），破折号独立计分不纳入
    score_per_1000 = (len(issues) / total_chars) * 1000 if total_chars > 0 else 0

    # 判定：主检测 ≤ 1.0/千字 且 破折号密度 ≤ 4.0/千字，两项均通过才算整体 PASS
    threshold = 1.0
    main_pass = score_per_1000 <= threshold
    emdash_pass = emdash_per_1000 <= EMDASH_THRESHOLD_PER_1000
    status = 'pass' if (main_pass and emdash_pass) else 'fail'

    return {
        'file': str(path),
        'exists': True,
        'total_chars': total_chars,
        'issue_count': len(issues),
        'score_per_1000': round(score_per_1000, 2),
        'threshold': threshold,
        'status': status,
        'issues': issues,
        # 破折号独立计分字段
        'emdash_count': emdash_count,
        'emdash_per_1000': round(emdash_per_1000, 2),
        'emdash_threshold': EMDASH_THRESHOLD_PER_1000,
        'emdash_status': 'pass' if emdash_pass else 'fail',
        'emdash_issues': emdash_issues,
        'message': f'八股文密度: {score_per_1000:.2f}/千字 (阈值: ≤{threshold}/千字) | 破折号密度: {emdash_per_1000:.2f}/千字 (阈值: ≤{EMDASH_THRESHOLD_PER_1000}/千字)'
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
        result = check_cliche(str(chapter_file))
        results.append(result)
    return results


def print_results(results: list, threshold: float = 1.0):
    """打印检测报告"""
    if not results:
        print('没有找到章节文件')
        return

    total_issues = 0
    passed = 0
    failed = 0
    all_issues_by_type = {}

    print('\n' + '=' * 60)
    print('八股文禁令检测报告（对应 polishing-guide 规则七）')
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
        print(f'   八股文痕迹数: {result["issue_count"]}')
        print(f'   密度: {result["score_per_1000"]:.2f}/千字 (阈值: {threshold}/千字)')
        # 破折号独立得分展示
        emdash_icon = '✅' if result.get('emdash_status', 'pass') == 'pass' else '⚠️ '
        print(f'   破折号: {result.get("emdash_count", 0)}处, {result.get("emdash_per_1000", 0):.2f}/千字 (阈值: ≤{result.get("emdash_threshold", EMDASH_THRESHOLD_PER_1000)}/千字) {emdash_icon}')

        # 按类型统计
        for issue in result.get('issues', []):
            t = issue['type']
            all_issues_by_type[t] = all_issues_by_type.get(t, 0) + 1

        # 显示前5个问题（带行号）
        if result['issues']:
            print(f'   主要问题（前5条）:')
            shown = 0
            for issue in result['issues']:
                if shown >= 5:
                    break
                print(f'     L{issue["line"]:>4d} [{issue["type"]}] {issue["match"]}')
                print(f'           原文: {issue["content"]}')
                shown += 1
            if len(result['issues']) > 5:
                print(f'     ... 还有 {len(result["issues"]) - 5} 个问题')

        # 显示破折号问题（独立展示）
        if result.get('emdash_issues'):
            for issue in result['emdash_issues']:
                print(f'     ---   [{issue["type"]}] {issue["match"]}')
                print(f'            {issue["content"]}')

    print('\n' + '-' * 60)
    print(f'总计: {len(results)} 章 | {passed} 章通过 | {failed} 章需润色 | 总问题数: {total_issues}')
    print('-' * 60)

    if all_issues_by_type:
        print(f'\n八股类型分布:')
        sorted_types = sorted(all_issues_by_type.items(), key=lambda x: x[1], reverse=True)
        for t, count in sorted_types[:10]:
            bar = '█' * min(count, 30)
            print(f'  {t:<20s} {count:>3d} {bar}')

    if failed > 0:
        print(f'\n⚠️  有 {failed} 章八股文超标，建议执行去八股文润色:')
        print(f'   1. 先处理破折号滥用和总结套话')
        print(f'   2. 再处理"不是…而是…"句式、二元套话和时间状语')
        print(f'   3. 最后清理心理副词和模糊限定词')
        print(f'\n   参考: references/guides/polishing-guide.md（规则七）')


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print('用法:')
        print('  检测单章: python check_cliche.py <章节文件路径>')
        print('  检测全部: python check_cliche.py --all <目录路径>')
        print('')
        print('示例:')
        print('  python check_cliche.py novels/故事/第01章.md')
        print('  python check_cliche.py --all novels/故事')
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
        result = check_cliche(file_path)
        print_results([result])


if __name__ == '__main__':
    main()
