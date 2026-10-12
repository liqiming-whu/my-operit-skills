#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal tests for false positives, source line numbers, and read-only mode."""
import sys
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from scan_prose import analyze_content, prose_lines, quote_mask, render_markdown  # noqa: E402
from compare_revisions import comparison  # noqa: E402


class TestProseScanner(unittest.TestCase):
    def test_uplift_flag_only_candidate(self):
        text = '她要的不是胜利，而是尊严。\n“不是这张，是昨天那张。”'
        result = analyze_content(text)
        self.assertTrue(any(f['code'] == 'contrast' for f in result['findings']))
        self.assertIn("需要语境判断", result["findings"][0]["kind"])

    def test_great_line_not_forced_to_explain(self):
        text = '“高人住在很远的地方。远到收不着润笔。”'
        result = analyze_content(text)
        self.assertFalse(result['findings'])

    def test_stock_action_and_location(self):
        result = analyze_content('她笑了。\n他指节泛白。')
        actions = [f for f in result['findings'] if f['code'] == 'stock_action']
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]['line'], 2)
        self.assertEqual(actions[0]['matched'], '指节泛白')

    def test_quoted_span(self):
        q = '她说：“我不是怕你，而是怕下雨。”'
        mask = quote_mask(q)
        self.assertTrue(mask[q.index('我')])
        self.assertFalse(mask[q.index('她')])
        result = analyze_content(q)
        self.assertEqual(result['findings'][0]['quote_scope'], '引号内')

    def test_fenced_code_and_title_skipped(self):
        text = '# 第一章\n```text\n她要的不是胜利，而是尊严。\n```\n她轻轻笑了。'
        result = analyze_content(text)
        self.assertFalse(result['findings'])
        self.assertEqual(prose_lines(text), [(5, '她轻轻笑了。')])

    def test_stats_no_pass_fail(self):
        result = analyze_content('“她笑了。”\n他转身离开。')
        self.assertNotIn('score', result)
        self.assertNotIn('status', result)
        report = render_markdown(result)
        self.assertIn('非文学评分', report)

    def test_readonly_comparison(self):
        original = '她要的不是胜利，而是尊严。\n'
        revised = '她放下剑，走出了院子。\n'
        result = comparison(original, revised, 'original.md', 'candidate.md')
        self.assertIn('原稿 SHA-256', result)
        self.assertIn('词面命中变化不代表文学质量变化', result)

    def test_source_unmodified_by_scanner(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / '正文.md'
            content = '他指节泛白。\n'
            p.write_text(content, encoding='utf-8')
            analyze_content(p.read_text(encoding='utf-8'))
            self.assertEqual(p.read_text(encoding='utf-8'), content)


if __name__ == '__main__':
    unittest.main()
