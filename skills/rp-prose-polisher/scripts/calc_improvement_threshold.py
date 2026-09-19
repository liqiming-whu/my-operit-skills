#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
改进阈值计算脚本
根据正文中文字数动态计算重试验证中的「最小密度降幅」阈值。
按五档分界匹配：≤5千字→0.10 | 5千~1.2万→0.06 | 1.2万~2.5万→0.04 | 2.5万~3.3万→0.03 | >3.3万→0.02。
各档阈值均 ≤ 该区间内 1 个 issue 减少对应的密度变化，确保重试改进判定在数学上可达。

输出格式：最后一行固定为 MIN_IMPROVEMENT_THRESHOLD=X.XX，
供调用方（AI）直接提取使用。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _content_utils import count_chinese_chars, extract_content


def calc_improvement_threshold(total_chars: int) -> dict:
    """
    根据总字数计算最小密度降幅阈值（/千字）。

    设计原则：
      - 阈值 ≤ 该区间内绝大多数情况下 1 个 issue 减少对应的密度变化
      - 各区间按字数递增而逐级降低，上限清晰
    """
    if total_chars <= 5000:
        threshold = 0.10
        bracket = '≤5,000 字'
    elif total_chars <= 12000:
        threshold = 0.06
        bracket = '5,001–12,000 字'
    elif total_chars <= 25000:
        threshold = 0.04
        bracket = '12,001–25,000 字'
    elif total_chars <= 33333:
        threshold = 0.03
        bracket = '25,001–33,333 字'
    else:
        threshold = 0.02
        bracket = '>33,333 字'

    single_issue_density = (1000 / total_chars) if total_chars > 0 else float('inf')

    return {
        'total_chars': total_chars,
        'bracket': bracket,
        'threshold': threshold,
        'single_issue_density': round(single_issue_density, 4),
        'one_issue_sufficient': single_issue_density >= threshold,
    }


def main():
    if len(sys.argv) < 2:
        print('用法: python calc_improvement_threshold.py <正文文件路径>')
        print('')
        print('示例:')
        print('  python calc_improvement_threshold.py /path/to/正文.md')
        return

    file_path = sys.argv[1]
    path = Path(file_path)

    if not path.exists():
        print(f'错误: 文件不存在 - {file_path}')
        # 文件不存在时输出默认值，确保调用方不会中断
        print('MIN_IMPROVEMENT_THRESHOLD=0.05')
        return

    content = extract_content(path)
    total_chars = count_chinese_chars(content)

    if total_chars == 0:
        print('警告: 文件为空或没有中文字符，使用默认阈值 0.05/千字')
        print('MIN_IMPROVEMENT_THRESHOLD=0.05')
        return

    result = calc_improvement_threshold(total_chars)

    print(f'总字数: {total_chars:,}')
    print(f'所属区间: {result["bracket"]}')
    print(f'1 个 issue 密度贡献: {result["single_issue_density"]:.4f}/千字')
    print(f'建议最小降幅阈值: {result["threshold"]:.2f}/千字')
    if result['one_issue_sufficient']:
        print('说明: 减少 1 个 issue 即可满足降幅要求')
    else:
        needed = int(result['threshold'] / result['single_issue_density']) + 1
        print(f'说明: 需减少至少 {needed} 个 issue 才能满足降幅要求')
    print('')
    # 固定输出行，供 AI 提取
    print(f'MIN_IMPROVEMENT_THRESHOLD={result["threshold"]:.2f}')


if __name__ == '__main__':
    main()
