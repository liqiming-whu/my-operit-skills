# my-operit-skills

一组在 [Operit](https://github.com/AAswordman/Operit)（Android AI Agent）上开发的 Agent Skills 合集。

## 仓库定位

这些 skill 在 Operit 上开发和验证，但**不依赖 Operit 专属功能**——它们遵循通用的 Agent Skill 结构（`SKILL.md` + frontmatter + `references/` + `scripts/`），**不限制在其他平台使用**（如 Claude Code、其他支持 SKILL 结构的 Agent 宿主）。

**移植提示**：在其他平台安装使用时，可能需要做必要的**路径与工具调用替换**。例如：
- 示例中的 `/sdcard/Download/...` 等 Android 路径需替换为目标平台的工作区路径
- 文件读写（`read_file`/`edit_file`/`create_file`/`delete_file`）与终端执行等工具调用，需对齐目标平台实际提供的工具名称与能力
- 脚本运行方式以目标平台的终端/Shell 能力为准（脚本均为纯标准库实现，无第三方依赖）

除上述环境适配外，skill 的流程与规则本身与平台无关。

## 包含的 Skill

| Skill | 说明 |
|-------|------|
| `byted-ark-seedream-skill` | 豆包 Seedream AI 图片生成（火山引擎方舟）。支持连贯组图、流式输出、提示词优化。需 Node.js 18+ 与方舟 API 访问。 |
| `chinese-prose-review` | 成稿后的中文小说文风审校。默认只读，修订另存，字节哈希与差异回验；Python 3.9+ 标准库，不设机械禁词分数。 |
| `rp-prose-polisher` | 中文文章优化器。对工作区正文文件（`正文.md`/`第＊＊章.md`/用户指定文件）做内容自查、去AI味、去八股文三段润色，附 Python 脚本验证与编辑前自动备份。 |

## 目录结构

```
skills/
  <skill-name>/
    SKILL.md          # 入口（含 frontmatter：name / description / metadata）
    references/       # 参考指南
    scripts/          # 辅助脚本（Python3 / Node，标准库）
```

## 使用

1. 将目标 skill 目录放入你的 Agent 宿主的 skills 目录（Operit 为 `/sdcard/Download/Operit/skills/`）。
2. 按上方「移植提示」做必要的路径与工具调用适配（如目标平台非 Operit）。
3. 重启 / 重新扫描 skills 后，通过 Skill 的 description 或 `metadata.trigger` 关键词触发。

各 skill 的具体用法见其 `SKILL.md`。

## License

各 skill 的许可证以其目录内的声明为准；`byted-ark-seedream-skill` 见 `references/LICENSE`（MIT）。
