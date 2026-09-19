#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI语言痕迹检测脚本 — 对应 polishing-guide.md 规则一/二/三/五/六（可检测部分）。
检测：华丽形容词、程度副词、比喻修辞、四字格律、AI句式模板、抽象情绪标签、笼统描述词。
对话个性化（无独立编号规则，见 polishing-guide 诊断表）和规则四（节奏感重塑）无脚本检测，必须人工执行。
规则七（八股文禁令）已拆分到 check_cliche.py。
对标 check_content_review.py 的设计风格。
"""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _content_utils import count_chinese_chars, extract_content

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


# ============================================================
# 检测规则定义
# ============================================================

# ── 规则一：形容词大清洗 ──（华丽形容词白名单）
AI_ADJECTIVES = [
    '璀璨', '瑰丽', '绚烂', '斑斓', '流光溢彩', '美轮美奂', '金碧辉煌',
    '磅礴', '浩瀚无垠', '无垠', '无边无际', '恢弘', '气吞山河', '波澜壮阔',
    '静谧', '幽深', '诡谲', '肃穆', '凝重',
]

# ── 规则一：形容词大清洗 ──（程度副词）
AI_ADVERBS = [
    '无比', '极其', '格外', '分外', '难以言喻的', '难以言喻',
    '不可名状的', '不可名状',
]

# ── 规则三：打破四字格律 ──（高频四字词白名单）
AI_FOUR_CHAR = [
    # 情绪类
    '心潮澎湃', '热血沸腾', '百感交集', '思绪万千', '感慨万千',
    '情不自禁', '不由自主',
    # 意志类
    '毫不犹豫', '毫不留情', '毅然决然', '义无反顾', '坚定不移',
    # 评价类
    '无可挑剔', '无与伦比', '叹为观止', '前所未有',
    # 氛围类
    '鸦雀无声', '万籁俱寂', '灯火阑珊', '华灯初上',
    # 言情高频
    '怦然心动', '小鹿乱撞', '面红耳赤', '心跳加速', '脸颊发烫',
    # 奇幻高频
    '毁天灭地', '天崩地裂', '翻江倒海',
]

# ── 规则六：AI句式扫除 ──（句式模板正则）
# 注：「仿佛...一般」「似乎...一般/似的」已移至下方规则一扩展「比喻修辞」检测
# 注：「不禁」已完全移至 check_cliche.py 规则七·第三类（心理副词），本脚本不检测
AI_SENTENCE_PATTERNS = [
    (r'一股.{1,20}?涌上心头', 'AI句式: 一股...涌上心头'),
    (r'内心深处', 'AI句式: 内心深处'),
    (r'在这一刻', 'AI句式: 在这一刻'),
    (r'某种.{1,20}?的存在', 'AI句式: 某种...的存在'),
    (r'显得格外', 'AI句式: 显得格外...'),
    (r'心中(?:不由得|不自觉地|涌起|充满了|满是)', 'AI句式: 心中...'),
    (r'感到(?:一阵|一股|一种).{1,20}?(?:的|之感)', 'AI句式: 感到一阵/一股/一种...'),
]


# ── 规则二：抽象变具象 ──（抽象情绪标签正则）
ABSTRACT_EMOTION_PATTERNS = [
    (r'他(?:感到|觉得|感受到)(?:十分|非常|极为|异常|格外)?(?:愤怒|悲伤|恐惧|害怕|紧张|焦虑|兴奋|喜悦|快乐|痛苦)', '抽象情绪: 直接陈述情绪'),
    (r'她(?:感到|觉得|感受到)(?:十分|非常|极为|异常|格外)?(?:愤怒|悲伤|恐惧|害怕|紧张|焦虑|兴奋|喜悦|快乐|痛苦)', '抽象情绪: 直接陈述情绪'),
    (r'(?:心中|心里|内心)(?:充满了?|满是|涌起了?|升起了?)(?:.{1,10})?(?:愤怒|悲伤|恐惧|害怕|紧张|焦虑|兴奋|喜悦|痛苦|失落|孤独)', '抽象情绪: 心中充满XX'),
    (r'(?:一股|一阵|一种)(?:难以言喻的|莫名的|强烈的|深深的|前所未有)?.{0,5}(?:感|情绪)', '抽象情绪: 一股/一阵/一种...感'),
]

# ── 规则五：细节具象化 ──（笼统描述词，仅8个固定短语）
VAGUE_DESCRIPTORS = [
    '十分疲惫', '非常疲惫', '极其疲惫', '异常疲惫',
    '十分美丽', '非常美丽', '极其美丽', '异常美丽',
    '十分紧张', '非常紧张', '极其紧张', '异常紧张',
    '十分安静', '非常安静', '极其安静', '异常安静',
]

# ── 规则一扩展：比喻修辞密度（比喻标记词正则）
# 独立阈值：每千字比喻标记超过此值即视为比喻滥用（在规则一润色中处理）
SIMILE_THRESHOLD_PER_1000 = 0.5  # 超过此值计入 issue
SIMILE_PATTERNS = [
    # 明喻标记（像/如系列）
    (r'仿佛.{1,30}?(?:一般|似的|一样)', '比喻: 仿佛...一般/似的/一样'),
    (r'似乎.{1,30}?(?:一般|似的|一样)', '比喻: 似乎...一般/似的/一样'),
    (r'如同.{1,30}?(?:一般|似的|一样)', '比喻: 如同...一般/似的/一样'),
    (r'宛如.{1,20}', '比喻: 宛如...'),
    (r'犹如.{1,20}', '比喻: 犹如...'),
    (r'好似.{1,20}', '比喻: 好似...'),
    (r'恰似.{1,20}', '比喻: 恰似...'),
    (r'好比.{1,20}', '比喻: 好比...'),
    (r'就像.{1,25}?(?:一样|似的)', '比喻: 就像...一样/似的'),
    (r'好像.{1,25}?(?:一样|似的)', '比喻: 好像...一样/似的'),
    # 像 + 一样/似的（排除「像往常」「像平时」等非比喻用法）
    (r'像(?!往常|平时|日常|以往|从前|从前那样|以前|以前那样|刚才|刚刚|上次|上回|那|这)\s*.{1,25}?(?:一样|似的)', '比喻: 像...一样/似的'),
    # ...般的
    (r'.{1,25}般\s*(?:的|地)', '比喻: ...般的...'),
    (r'.{2,20}般\s*(?:安静|沉默|微笑|叹息|语气|神情|眼神|声音|表情)', '比喻: ...般的...'),
    # 独立"......似的"（无前导比喻标记词，如"发疯似的""着了魔似的"）
    # 排除「似乎」（已有独立模式）和「似的的」
    (r'(?<!似)\S{2,20}似的(?!的)', '比喻: ...似的'),
]

# ============================================================
# 规则七（八股文禁令）已拆分到 check_cliche.py
# 本脚本仅检测 polishing-guide 规则一/二/三/五/六 的可检测部分
# ============================================================


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


def check_ai_flavor(file_path: str) -> dict:
    """检测单个章节的AI痕迹"""
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

    # ── 规则一：华丽形容词 ──
    adj_matches = find_word_line_numbers(content, AI_ADJECTIVES)
    if adj_matches:
        for m in adj_matches:
            issues.append({
                'type': '华丽形容词',
                'line': m['line'],
                'match': m['match'],
                'content': m['content'],
            })

    # ── 规则一：程度副词 ──
    adv_matches = find_word_line_numbers(content, AI_ADVERBS)
    if adv_matches:
        for m in adv_matches:
            issues.append({
                'type': '程度副词',
                'line': m['line'],
                'match': m['match'],
                'content': m['content'],
            })

    # ── 规则三：四字格律 ──
    four_matches = find_word_line_numbers(content, AI_FOUR_CHAR)
    if four_matches:
        for m in four_matches:
            issues.append({
                'type': '四字格律',
                'line': m['line'],
                'match': m['match'],
                'content': m['content'],
            })

    # ── 规则六：AI句式模板 ──
    for pattern, label in AI_SENTENCE_PATTERNS:
        sent_matches = find_line_numbers(content, pattern)
        for m in sent_matches:
            issues.append({
                'type': label,
                'line': m['line'],
                'match': m['match'],
                'content': m['content'],
            })

    # ── 规则二：抽象情绪标签 ──
    for pattern, label in ABSTRACT_EMOTION_PATTERNS:
        emo_matches = find_line_numbers(content, pattern)
        for m in emo_matches:
            issues.append({
                'type': label,
                'line': m['line'],
                'match': m['match'],
                'content': m['content'],
            })

    # ── 规则五：笼统描述词 ──
    vague_matches = find_word_line_numbers(content, VAGUE_DESCRIPTORS)
    if vague_matches:
        for m in vague_matches:
            issues.append({
                'type': '笼统描述',
                'line': m['line'],
                'match': m['match'],
                'content': m['content'],
            })

    # ── 规则一扩展：比喻修辞密度（按质量排序，仅上报超出允许数量的最差部分）──
    simile_matches = []
    for pattern, label in SIMILE_PATTERNS:
        s_matches = find_line_numbers(content, pattern)
        for m in s_matches:
            match_len = len(m['match'])
            simile_matches.append({
                'type': label,
                'line': m['line'],
                'match': m['match'],
                'content': m['content'],
                '_match_len': match_len,
                '_label': label,
            })

    # 过滤「一般的/一般地」的独立非比喻用法（如"一般地不说话"中的副词"一般地"）
    _standalone_yiban = re.compile(r'^一般\s*[的地]$')
    simile_matches = [
        m for m in simile_matches
        if not _standalone_yiban.match(m['match'])
    ]

    # 比喻密度独立判定：超过阈值时按"干瘪度"排序，仅上报超出部分
    simile_density = (len(simile_matches) / total_chars) * 1000 if total_chars > 0 else 0
    if simile_density > SIMILE_THRESHOLD_PER_1000 and len(simile_matches) > 0:
        # 计算允许保留的比喻数量（至少保留1个，不会全部删光）
        allowed_count = max(1, int(SIMILE_THRESHOLD_PER_1000 * total_chars / 1000))
        excess_count = len(simile_matches) - allowed_count

        if excess_count > 0:
            # 按"干瘪度"给每个比喻打分：分越高越该优先处理
            def _simile_badness(sm):
                score = 0
                label = sm['_label']
                # 越模板化的标记词 → 分越高（越该上报）
                if '仿佛' in label:
                    score += 3
                elif '就像' in label:
                    score += 2
                elif '好像' in label:
                    score += 2
                elif '似乎' in label:
                    score += 1
                elif '如同' in label:
                    score += 1
                elif '像...一样' in label or '像...似的' in label:
                    score += 2
                elif '...般的' in label:
                    score += 1
                elif '...似的' in label:
                    score += 2
                # 比喻越短 → 越可能是边角料填充物
                if sm['_match_len'] < 8:
                    score += 2
                elif sm['_match_len'] < 12:
                    score += 1
                elif sm['_match_len'] > 25:
                    score -= 1  # 较长比喻通常更有内容
                return score

            ranked = sorted(simile_matches, key=_simile_badness, reverse=True)
            # 只上报最差的那部分（= 超出允许数量的部分）
            flagged_similes = ranked[:excess_count]
            # 去掉内部排序字段，建议替换而非暴力删除
            for sm in flagged_similes:
                del sm['_match_len']
                del sm['_label']
                sm['content'] = f'{sm["content"]}  ⟵ 建议替换为具象白描或更自然的表达，保留原意'
            issues.extend(flagged_similes)

    # ============================================================
    # 规则七（八股文禁令）已拆分到 check_cliche.py
    # 本脚本仅检测 polishing-guide 规则一/二/三/五/六 的可检测部分
    # ============================================================

    # 按行号排序
    issues.sort(key=lambda x: x['line'])

    # 计算得分：每千字AI痕迹数（越低越好）
    score_per_1000 = (len(issues) / total_chars) * 1000 if total_chars > 0 else 0

    # 判定：每千字 <= 1 个痕迹为通过
    threshold = 1.0
    status = 'pass' if score_per_1000 <= threshold else 'fail'

    return {
        'file': str(path),
        'exists': True,
        'total_chars': total_chars,
        'issue_count': len(issues),
        'score_per_1000': round(score_per_1000, 2),
        'threshold': threshold,
        'status': status,
        'issues': issues,
        'simile_count': len(simile_matches),
        'simile_density': round(simile_density, 2),
        'simile_status': 'pass' if simile_density <= SIMILE_THRESHOLD_PER_1000 else 'fail',
        'message': f'AI痕迹密度: {score_per_1000:.2f}/千字 (阈值: {threshold}/千字)'
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
        result = check_ai_flavor(str(chapter_file))
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
    print('AI痕迹检测报告（对应 polishing-guide 规则一/二/三/五/六）')
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
        print(f'   AI痕迹数: {result["issue_count"]}')
        print(f'   密度: {result["score_per_1000"]:.2f}/千字 (阈值: {threshold}/千字)')
        # 比喻密度独立展示（不论是否超标都显示，让AI始终能感知比喻状态）
        _simile_density = result.get('simile_density', 0)
        _simile_status = result.get('simile_status', 'pass')
        _simile_icon = '✅' if _simile_status == 'pass' else '⚠️ '
        print(f'   比喻密度: {_simile_density:.2f}/千字 (阈值: ≤{result.get("simile_threshold", SIMILE_THRESHOLD_PER_1000)}/千字) {_simile_icon}')

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

    print('\n' + '-' * 60)
    print(f'总计: {len(results)} 章 | {passed} 章通过 | {failed} 章需润色 | 总问题数: {total_issues}')
    print('-' * 60)

    if all_issues_by_type:
        print(f'\n问题类型分布:')
        sorted_types = sorted(all_issues_by_type.items(), key=lambda x: x[1], reverse=True)
        for t, count in sorted_types[:10]:
            bar = '█' * min(count, 30)
            print(f'  {t:<20s} {count:>3d} {bar}')

    if failed > 0:
        print(f'\n⚠️  有 {failed} 章AI痕迹超标，建议执行深度润色:')
        print(f'   1. 查看上方「问题类型分布」，优先处理数量最多的类别')
        print(f'   2. 多数情况下华丽形容词和四字格律最常见（最快见效），但也可能是比喻修辞或抽象情绪占主导')
        print(f'   3. 通读全章检查节奏和对话个性')
        print(f'\n   参考: references/guides/polishing-guide.md（规则一~七）')
        print(f'   八股文检测请运行: python scripts/check_cliche.py <文件路径>')


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print('用法:')
        print('  检测单章: python check_ai_flavor.py <章节文件路径>')
        print('  检测全部: python check_ai_flavor.py --all <目录路径>')
        print('')
        print('示例:')
        print('  python check_ai_flavor.py novels/故事/第01章.md')
        print('  python check_ai_flavor.py --all novels/故事')
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
        result = check_ai_flavor(file_path)
        print_results([result])


if __name__ == '__main__':
    main()
