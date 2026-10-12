# Chinese Prose Review v2

用于**正文完成之后**的中文小说文风审校。保留第一版的文学审查原则，借鉴 `rp-prose-polisher` 的分层检查、脚本定位、报告与回验，但**不自动修改原稿、不设 AI 味及格分数、不强制比喻或句长密度、不默认循环重试**。

## 快速使用

把整个 `chinese-prose-review` 目录作为 Skill 安装/复制到可使用的位置。阅读 `SKILL.md` 即可按自然语言审稿；有 Python 3.9+ 时可运行（仅标准库，无第三方依赖）：

```bash
python3 scripts/scan_prose.py '/path/to/第一章.md' --format markdown --out '/path/to/第一章.prose-review.md'
python3 scripts/scan_prose.py '/path/to/第一章.md' --format json --out '/path/to/第一章.prose-review.json'
python3 scripts/prepare_candidate.py '/path/to/第一章.md' '/path/to/第一章.review-candidate.md'
# 保存上一步 JSON 的 original_sha256；只编辑候选，随后比较：
python3 scripts/compare_revisions.py '/path/to/第一章.md' '/path/to/第一章.review-candidate.md' --expected-original-sha256 '<保存的64位哈希>' --out '/path/to/第一章.review-diff.md'
python3 -m unittest discover -s tests -v
```

**上述扫描、对照和测试命令都不会修改正文。** `scan_prose.py` 的命中列表是词面线索，必须由审稿者人工读上下文；`compare_revisions.py` 只能显示文字差异，不能证明文学质量提升。

## 来源与借鉴

借鉴用户早期 Skill [`rp-prose-polisher`](https://github.com/liqiming-whu/my-operit-skills/tree/main/skills/rp-prose-polisher) 的工程经验：分层诊断、可复验问题定位、文件回退与验证思路。新脚本独立实现，且刻意不移植原项目的硬性 PASS/FAIL 密度线、全局替换与原稿处理标记。

旧的英文禁令备份在 `references/legacy-forbidden-language-rules.md`，方便追溯，不属于现行硬规则。

## 文件保护与安装

Operit：将整个目录复制到 `/sdcard/Download/Operit/skills/chinese-prose-review/`，重新扫描技能。其他宿主复制到其 skills 目录，并替换命令中的绝对路径。无需执行安装脚本。

扫描和比较缺省输出到终端；`--out` 只允许新路径。候选复制也拒绝已有文件、符号链接和硬链接。基线哈希用于验证原稿字节，不能以当前哈希代替修改前基线。候选编辑由获得授权的读稿者执行；脚本不做自动修辞替换。
