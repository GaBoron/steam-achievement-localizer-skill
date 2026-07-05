简体中文 | [English](README_EN.md)

# Steam Achievement Localizer Skill

当前版本：`v0.1.2`

Steam Achievement Localizer 是一个用于本地化 Steam 成就名称和描述的 Codex skill。它读取 `UserGameStatsSchema_*.bin`，按 Steam Binary KeyValues 格式做无损解析，导出可审核的成就文本，并只把确认后的翻译写入指定语言字段。

这个仓库同时维护一个社区共享成就翻译库。skill 的运行脚本和仓库维护脚本已经分开：`scripts/` 只放随 skill 分发的运行时脚本，`workflow-scripts/` 只放 GitHub Actions 使用的投稿审核和索引维护脚本。

## 快速入口

- **安装 skill**：让 Codex 从 `https://github.com/GaBoron/steam-achievement-localizer-skill` 安装，或从 GitHub Releases 下载 `steam-achievement-localizer.zip` 手动安装。
- **查找已有翻译**：打开 [社区成就翻译库](achievement-library/README.md)，按游戏名、Steam app ID、贡献者或语言代码搜索。
- **提交翻译文件**：创建 [翻译投稿 issue](https://github.com/GaBoron/steam-achievement-localizer-skill/issues/new?template=translation_contribution_zh.yml)，上传 `UserGameStatsSchema_<game_id>.zip`。
- **反馈 skill 问题**：创建 [skill bug issue](https://github.com/GaBoron/steam-achievement-localizer-skill/issues/new?template=skill_bug_zh.yml)。
- **更新投稿文件**：在来源 issue 或生成的 PR 中评论 `/update`，并把新的 ZIP 作为评论附件上传；不需要在命令后粘贴附件链接。

## 目录结构

```text
.
├── SKILL.md
├── VERSION
├── scripts/
│   └── steam_bkv_tool.py
├── workflow-scripts/
│   ├── github_issue_guard.py
│   ├── library_submission_bot.py
│   └── translation_pr_maintenance.py
├── achievement-library/
│   ├── README.md
│   ├── README_EN.md
│   ├── index.json
│   └── files/
├── README.md
├── README_EN.md
├── CONTRIBUTING_CN.md
└── CONTRIBUTING.md
```

`scripts/steam_bkv_tool.py` 是 skill 用户流程的唯一脚本入口，负责版本检查、schema 查找、导出、翻译写入、校验和可选安装。`workflow-scripts/` 是仓库维护入口，只服务 GitHub Actions 的 issue 审核、PR 刷新、索引生成和合并后维护，不随普通 skill 使用流程执行。

## 安装

让 Codex 安装：

```text
Install the skill from https://github.com/GaBoron/steam-achievement-localizer-skill
```

安装后这样调用：

```text
使用 $steam-achievement-localizer 翻译这个 Steam 成就 schema。
```

手动安装时，从 GitHub Releases 下载 `steam-achievement-localizer.zip`，解压到 Codex skills 文件夹：

```powershell
Expand-Archive .\steam-achievement-localizer.zip -DestinationPath "$env:USERPROFILE\.codex\skills" -Force
```

安装后的 skill 目录至少应包含：

```text
steam-achievement-localizer\SKILL.md
steam-achievement-localizer\VERSION
steam-achievement-localizer\scripts\steam_bkv_tool.py
```

## 版本检查

每次本地化任务开始前，skill 会运行缓存式版本检查。它每次读取本地 `VERSION`，并默认最多缓存 24 小时的 GitHub 最新 tag 查询结果，避免重复访问网络。

```powershell
python <skill>\scripts\steam_bkv_tool.py version-check --warn-only
```

只有在刚更新 skill、准备执行安装回写、排查版本问题，或需要立即刷新远程结果时，才使用 `--force`。

## 基本流程

### 1. 找到 Steam app ID

Steam 商店地址通常形如：

```text
https://store.steampowered.com/app/<game_id>/<game_name>/
```

例如 `https://store.steampowered.com/app/123456/Game_Name/` 中的 app ID 是 `123456`。

### 2. 找到成就 schema

Steam 通常把成就 schema 放在：

```text
<Steam 文件夹>\appcache\stats\UserGameStatsSchema_<game_id>.bin
```

如果你明确要求 Codex 自动查找，它可以运行：

```powershell
python <skill>\scripts\steam_bkv_tool.py find-schema --game-id 123456
```

自动查找是可选动作。除版本检查外，skill 不会默认执行文件发现、批量翻译、安装回写或完整 workflow 自动化。

### 3. 提出翻译请求

推荐请求格式：

```text
使用 $steam-achievement-localizer 翻译这个 Steam 成就文件。

游戏 ID：123456
schema 文件：<UserGameStatsSchema_123456.bin 的路径>
目标语言：schinese
流程：先导出 CSV 给我检查，我确认后再写回
翻译要求：保留官方物品名，使用简洁自然的中文成就文案
```

你可以同时提供术语表、官方本地化文本、Wiki 文本、已有翻译文件、社区翻译库条目或风格说明。Codex 应优先使用你提供或明确认可的来源。

## 可选自动化

当你明确要求自动化机械步骤时，可以使用完整 workflow：

```powershell
python <skill>\scripts\steam_bkv_tool.py workflow --game-id 123456 --target-language schinese --out-dir outputs
```

这个命令会运行版本检查、查找 schema、复制到输出目录、导出成就 CSV、导出缺失语言 CSV、生成报告并保持原始 Steam 文件不变。`*.missing.csv` 只列出尚未包含目标语言的成就，只有在你要求批量翻译缺失项时才应填充 `target_name` 和 `target_description`。

应用已经审核过的 CSV：

```powershell
python <skill>\scripts\steam_bkv_tool.py workflow --game-id 123456 --target-language schinese --out-dir outputs --translations outputs\translations.csv --strict-no-latin
```

翻译文本应保持干净、单行，不包含制表符、换行、原始转义符、NUL 字节或控制字符。脚本会在写入前清理不安全字符，并报告 `translation_text_sanitized_count`。

只有在你明确确认要替换本地 Steam 文件时，才安装回 Steam：

```powershell
python <skill>\scripts\steam_bkv_tool.py workflow --game-id 123456 --target-language schinese --out-dir outputs --translations outputs\translations.csv --install
```

安装流程会先备份原文件，再验证安装后的文件哈希是否与本地化副本一致。

## Skill 校验内容

- 原始文件能否解析并字节级无损写回。
- 本地化副本能否解析并字节级无损写回。
- 翻译是否按稳定成就 ID 匹配，而不是按行号或英文名匹配。
- 目标语言字段是否覆盖所有成就名和描述。
- 是否存在缺失、额外、空白或疑似残留源语言文本。
- 写入前是否清理了不安全字符。

## 社区翻译库

社区翻译库位于 `achievement-library/`，包含 GitHub 浏览用索引、机器可读索引和用户投稿的 schema 文件。用户提交翻译贡献时应使用翻译投稿 issue 模板，并上传只包含一个 `UserGameStatsSchema_<game_id>.bin` 的 ZIP 文件。

投稿机器人会检查 issue 字段、Steam 商店地址、文件名、ZIP 结构、Steam Binary KeyValues roundtrip、所选语言覆盖率和重复投稿。初审通过后，机器人会创建 PR；维护者最终审核合并后，仓库会更新 `achievement-library/index.json` 和两个 Markdown 索引。

投稿规范和维护命令见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 致谢

本项目参考了以下公开项目：

- [achievement_reconstructor](https://github.com/CommitteeOfZero/achievement_reconstructor)
- [SamRewritten](https://github.com/PaulCombal/SamRewritten)
- [SteamAchievementLocalizer](https://github.com/PanVena/SteamAchievementLocalizer)

感谢这些项目的作者和贡献者分享 Steam 成就文件与本地化流程相关研究。本项目是独立实现；使用上述项目内容时，请遵守各项目许可证。

## 许可证

MIT
