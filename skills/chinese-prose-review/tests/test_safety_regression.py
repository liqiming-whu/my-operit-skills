"""B01/D03 principles from the task; synthetic prose, no novel source files."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from scan_prose import analyze_content


class Regression(unittest.TestCase):
    def run_cli(self, script, *args):
        return subprocess.run([sys.executable, '-B', str(ROOT/'scripts'/script), *map(str, args)], capture_output=True, text=True)

    def test_natural_chinese_b01(self):
        for text in ['她站得很稳。', '他说话的时候，窗外下起了雨。', '她不禁笑了。或许明天会放晴。', '他没走，也没有催她。', '她像往常一样收起书卷。', '月光仿佛薄纱，落在窗前——她还醒着。']:
            with self.subTest(text=text):
                self.assertEqual(analyze_content(text)['findings'], [])

    def test_contextual_negation_remains_candidate(self):
        r=analyze_content('“不是遗失，而是我把钥匙借给邻居了。”')
        self.assertEqual(r['findings'][0]['quote_scope'], '引号内')
        self.assertIn('语境判断', r['findings'][0]['kind'])
        self.assertNotIn('score', r)

    def test_rhetoric_and_dialogue_are_stats_only(self):
        r=analyze_content('\n'.join(['“她仿佛睡着了——别吵。”']*7))
        self.assertEqual(r['findings'], [])
        self.assertEqual(r['stats']['emdashes'], 7)
        self.assertEqual(r['stats']['longest_quoted_line_run'], 7)

    def test_cli_default_readonly_and_raw_hash(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'source.md'; data='她站得很稳。\r\n她不禁笑了。\r\n'.encode(); p.write_bytes(data)
            scan=self.run_cli('scan_prose.py',p,'--format','json')
            self.assertEqual(scan.returncode,0,scan.stderr)
            self.assertEqual(json.loads(scan.stdout)['sha256'],hashlib.sha256(data).hexdigest())
            self.assertEqual(p.read_bytes(),data)
            self.assertEqual(list(Path(d).iterdir()),[p])

    def test_candidate_and_comparison_preserve_source(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'source.md'; c=Path(d)/'candidate.md'; report=Path(d)/'diff.md'
            data='她笑了。\r\n'.encode();p.write_bytes(data)
            prep=self.run_cli('prepare_candidate.py',p,c)
            self.assertEqual(prep.returncode,0,prep.stderr)
            digest=json.loads(prep.stdout)['original_sha256']
            self.assertEqual(c.read_bytes(),data)
            c.write_text('她转身笑了。\n',encoding='utf-8')
            result=self.run_cli('compare_revisions.py',p,c,'--expected-original-sha256',digest,'--out',report)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn(digest,report.read_text())
            self.assertIn('-她笑了。',report.read_text())
            self.assertEqual(p.read_bytes(),data)
            p.write_text('原稿被外部改动。',encoding='utf-8')
            rejected=self.run_cli('compare_revisions.py',p,c,'--expected-original-sha256',digest)
            self.assertNotEqual(rejected.returncode,0)
            self.assertIn('基线不一致',rejected.stderr)

    def test_output_aliases_and_existing_files_rejected_d03(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'source.md';c=Path(d)/'candidate.md';p.write_bytes(b'original\r\n');c.write_bytes(b'candidate\r\n')
            hard=Path(d)/'hard.md';os.link(p,hard)
            sym=Path(d)/'sym.md';sym.symlink_to(p)
            report=Path(d)/'report.md';report.write_bytes(b'previous report')
            for script, inputs in [('scan_prose.py',[p]),('compare_revisions.py',[p,c])]:
                for target in [p,c,hard,sym,report]:
                    with self.subTest(script=script,target=target):
                        result=self.run_cli(script,*inputs,'--out',target)
                        self.assertNotEqual(result.returncode,0)
                        self.assertEqual(p.read_bytes(),b'original\r\n')
                        self.assertEqual(c.read_bytes(),b'candidate\r\n')
                        self.assertEqual(report.read_bytes(),b'previous report')
            for target in [p,hard,sym,c]:
                self.assertNotEqual(self.run_cli('prepare_candidate.py',p,target).returncode,0)
            self.assertNotEqual(self.run_cli('compare_revisions.py',p,hard).returncode,0)
