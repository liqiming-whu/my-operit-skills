---
name: chinese-prose-review
description: Review a finished Chinese fiction draft for formulaic AI prose, translationese, redundant explanation, unnatural dialogue and rhythm. Preserve the author's voice; locate suspicious patterns with optional Python scripts; revise only with explicit permission and never overwrite the original. Use when the user requests 小说文风审查、去AI味、去八股、文学润色、中文小说校读 or prose review.
metadata:
  trigger: 小说文风审查、去AI味、去八股、文学润色、中文小说校读、prose review
  source: chinese-prose-review v2; selective engineering patterns adapted from rp-prose-polisher
---

# Chinese Prose Review · 中文小说文风审校

> **信任已经成立的文学瞬间。让好句子自己活着。**
>
> **DO NOT optimize a score, a forbidden-word count, or compliance with a writing template. The final criterion is the passage's actual effect on an attentive reader.**

## 适用范围与权限

- **仅在已有正文后使用**，或用户明确要求评价、修改已有文本时使用。不得作为主笔创作前必须通过的语文考试；不得强制列出全部禁词后再写正文。
- **运行依赖：Python 3.9+，仅使用标准库；无需 pip 安装。**
- **默认模式：只审查，不改文件。** 如用户没有明确要求修改，返回诊断和少量建议即可。
- **修改模式：必须有明确授权。** 仅产生另存的修订候选；原稿不得直接覆盖、批量替换或打处理标记。用户明确指定新文件路径的，从其要求；否则以 `{原名}.review-candidate.md` 命名，已有候选时另起序号。
- 已有现成片段或上传文件时直接处理；若用户只说“帮我润色”但未提供文本或文件位置，简短询问。**禁止擅自取目录里“最近修改的一章”冒充目标。**
- 一次只处理被指定的章节/片段；明确批量请求才批量处理。每个文件的原稿与候选分开记录。
- 本 Skill 审查**语言与文学阅读效果**。时间线、世界设定、权限与战力逻辑由独立事实审计负责；读到明显疑点可移交，不能借文风审查擅改正史。

## 借鉴的工程能力及其界限

旧 `rp-prose-polisher` 的分层检查、问题定位、文件备份与回验有价值；本 Skill 只吸收这些**方法**，不导入其硬性密度合格线、自动刷分重试、原地修改、全局替换标点或“已优化”永久标记。

| 可以由脚本做的事 | 必须由读稿者做的事 |
|---|---|
| 提醒高风险句式及位置、显示短上下文 | 判断该句是否真的有八股感、是否属于人物独特口吻 |
| 统计疑似重复词、破折号、句长与纯对白连续段 | 判断重复是否有叙事功能、标点是否服务节奏 |
| 给出可复验的行号和检测结果 JSON | 区分留白与信息缺失、好比喻与废话比喻 |
| 对照修订前后的文本差异 | 判断“修改后更好读吗”，必要时决定保留原句 |

**A script match is a review candidate, never proof of bad writing. A decreasing flag count MUST NOT be presented as a literary improvement score.**

## 工作流程（按次序）

### 第一遍：不带尺子读完整段

先读全文，记录这段**为什么值得读**：人物当下的欲望、对白的自然反应、特殊的观察、值得保留的句子（通常选 1–3 处）。再记录真正让你出戏、读着滞涩或感到作者在旁边讲解的地方。

这一步不运行查禁词、不算句长、不拿每句与规则表对照。创作的成功部分应先受保护。

### 第二遍：轻量检测，定位疑点

如可使用终端与 Python 3，先读 `references/review-guide.md`；随后用**绝对路径**调用脚本（脚本仅使用 Python 标准库）：

```bash
python3 /path/to/chinese-prose-review/scripts/scan_prose.py '/path/to/第1章.md' --format markdown --out '/path/to/第1章.prose-review.md'
# 也支持机器可读的 JSON：--format json --out /path/to/report.json
```

脚本是**可选的辅助工具**；环境没有 Python 或没有文件访问权限时，照样可以人工审读，但不得声称已跑脚本。它的输出是「候选线索」，没有 PASS/FAIL 或“AI味得分”。

逐条确认可疑位置，尤其注意两组例外：

- 「不是……而是……」用于事实纠正、角色争辩时可以自然；用于旁白强行给主题升华时往往应删减。
- 「不禁」「或许」「大概」「的时候」「仿佛」、成语、破折号、一般比喻、短句、长句、直接心理描写都不是自动错误。**不要将普通中文词汇用复杂动作或华丽意象替代。**

具体模式和反例见 `references/review-guide.md`。早年的严格禁词表保存在 `references/legacy-forbidden-language-rules.md`，只供追溯审美目标与构造对照样例，**不是现行逐字禁令**。

### 第三遍：文学判断与最小建议

优先处理真正影响阅读的 1–5 个问题，而不是机械列出所有命中项。每一项应说明：

1. **证据**：原文的位置、短引文和必要上下文。
2. **阅读后果**：它为什么让此处的情绪、对白、节奏或人物辨识度变弱。
3. **建议**：保留、删除解释、压缩重复、局部重写、或交由主笔决定。
4. **修改代价**：有什么值得保留的语气、信息、伏笔可能受损。

不得用「出现了某个禁词」代替后果说明。也不得强迫每个段落出现一个好句、一个前世回忆或一个私心展示。

### 第四遍：获授权时，另存候选并回验

- 按用户授权范围修改，**先复制再改候选文件**。可运行以下命令创建全新候选，并保存输出 JSON 中的 `original_sha256` 作为修改前基线；候选已存在时拒绝覆盖，另起序号：

```bash
python3 /path/to/chinese-prose-review/scripts/prepare_candidate.py '/path/to/第1章.md' '/path/to/第1章.review-candidate.md'
```

- 保存基线后，仅编辑候选。重点是局部最小改动；不能把 Kimi/Claude 已经写好的自然句子磨成统一笔调。
- 不用 `sed -i` 或其他全局命令替换破折号、否定词、比喻词；不用脚本把标记自动替换成“正确句式”。
- 完成后完整重读候选，重点看人物是否还鲜活、节奏有无断裂、原先的好句有没有被误伤。
- 可用对照脚本回验，显示变更片段与风险模式增减，但**不能仅凭命中数变少宣布胜利**：

```bash
python3 /path/to/chinese-prose-review/scripts/compare_revisions.py '/path/to/第1章.md' '/path/to/第1章.review-candidate.md' --expected-original-sha256 '<修改前保存的64位哈希>' --out '/path/to/第1章.review-diff.md'
```

- 扫描和比较报告中的 CLI 哈希按原始文件字节计算（保留 CRLF / BOM）；基线不一致时停止回验。两种报告输出均拒绝覆盖已有路径（包括指向输入的符号链接、硬链接），重复运行须另起报告文件名。未提供修改前基线时，只能报告当前指纹，不能声称原稿未被改动。
- 保留原稿的哈希校验信息；若工具无法保存、回读或者比较，明确报告未验证之处。不得伪称修改完成。

## 默认交付格式

**没有修改权限时**：

1. 「应当保留」：1–3 处真正成立的语言或人物瞬间，并解释效果。
2. 「最妨碍阅读」：至多 5 项，按影响程度排，逐项举证；注明「明显模板」「语境存疑」「审美选择」。
3. 「最小修改建议」：示例只为展示方向，不默认替作者全面润色；必要时明确建议原样保留。

**经授权修改时**：另附原稿与候选路径，简述改动、代表性前后对照，以及对原稿是否完整保留的核验结果。报告不采用小数点文学评分，不设硬性问题数合格线。

## 与小说团队协作

Claude 的初稿不预先调用本 Skill。Kimi 负责文学修改和创意建议，可借此获得**疑点索引**；ChatGPT 负责事实与因果审计，两者尽量避免重复劳动；最终如何改写由主笔整合，重要文学取舍由项目负责人决定。换了作者/模型也适用相同原则。

不要要求每位作者读完后再交一份形式完美的检讨。**下一步最好的证据，是修改后更自然的正文。**

## 附属资料与验证

- `references/review-guide.md`：高风险模式、语境例外、写作与审校界限。
- `references/legacy-forbidden-language-rules.md`：旧规则原始归档（非现行禁令）。
- `references/regression-examples.md`：应提示与应保护的对照案例。
- `scripts/scan_prose.py`：只读静态扫描，Markdown / JSON 问题索引。
- `scripts/compare_revisions.py`：修订差异、哈希、扫描信号对照（不会写原文）。
- `tests/test_scan_prose.py`：标准库单元测试，`python3 -m unittest discover -s tests -v`。

- `scripts/prepare_candidate.py`：获授权后创建全新候选，输出修改前字节哈希。
- `scripts/safe_files.py`：标准库输入/输出保护工具。
- `tests/test_safety_regression.py`：自然中文、修辞、CLI 只读、链接别名、CRLF 哈希和基线回验。
