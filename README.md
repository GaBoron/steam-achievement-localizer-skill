简体中文 | [English](README_EN.md)

# Steam Achievement Localizer Skill

当前版本：`v0.1.2`

这是一个用于翻译 Steam 本地成就名称和描述的 Codex skill，处理`UserGameStatsSchema_*.bin` 文件。

你只需要提供游戏 ID 或 schema 文件路径、目标语言、以及翻译要求。这个 skill 会读取文件，导出成就文本供你检查，再把确认后的翻译写回指定语言字段，并在替换Steam 文件前做检查。

## 快速入口

- **查询已有投稿**：[打开用户共享翻译库索引](achievement-library/README.md)，可以直接搜索游戏名、Steam app ID 或语言代码。
- **提交翻译贡献**：[创建翻译投稿 issue](https://github.com/GaBoron/steam-achievement-localizer-skill/issues/new?template=translation_contribution_zh.yml)，上传 `UserGameStatsSchema_<game_id>.zip`。
- **反馈 skill 问题**：[创建 skill bug issue](https://github.com/GaBoron/steam-achievement-localizer-skill/issues/new?template=skill_bug_zh.yml)。

## 用户共享翻译库

这个仓库也包含用户投稿的 Steam 成就翻译库：

- 用户查找索引：`achievement-library/README.md`
- 机器可读索引：`achievement-library/index.json`
- 成就文件：`achievement-library/files/<game_id>/UserGameStatsSchema_<game_id>.bin`

如果你想分享已经翻译好的成就 schema，请使用上方翻译投稿入口，并上传对应的 `UserGameStatsSchema_<game_id>.zip` 文件。ZIP 内必须只包含一个`UserGameStatsSchema_<game_id>.bin` 文件。
后台机器人会检查 issue 中的游戏 ID、商店地址、文件名、Steam Binary KeyValues 格式，以及你选择的语言字段是否都存在。初审通过后，机器人会自动创建 PR，包含上传的成就文件，以及每个成就 ID 对应各语言成就名和描述的审核表格。

投稿前的查重方法和规范见 [CONTRIBUTING_CN.md](CONTRIBUTING_CN.md)。skill 本身的问题请使用单独的 skill bug issue 模板。

## 安装

### 让 Codex 安装

```text
Install the skill from https://github.com/GaBoron/steam-achievement-localizer-skill
```

安装后这样使用：

```text
使用 $steam-achievement-localizer 翻译这个 Steam 成就 schema。
```

### 手动安装

从 GitHub Releases 下载 `steam-achievement-localizer.zip`，解压到 Codex skills
文件夹：

```powershell
Expand-Archive .\steam-achievement-localizer.zip -DestinationPath "$env:USERPROFILE\.codex\skills" -Force
```

安装后的文件夹里应包含：

```text
steam-achievement-localizer\SKILL.md
```

## 版本检查

每次开始工作前，skill 会先检查本地版本。它也会检查 GitHub 最新 tag，但默认会
缓存 24 小时，避免每次都访问 GitHub。

```powershell
python <skill>\scripts\steam_bkv_tool.py version-check --warn-only
```

只有在你想立刻刷新 GitHub 检查时，才需要加 `--force`。

如果版本不一致，建议先更新 skill，再处理重要文件。

## 基本用法

### 1. 找到 Steam 游戏 ID

打开游戏的 Steam 商店页面，地址通常类似：

```text
https://store.steampowered.com/app/<游戏ID>/<游戏名>/
```

例如下面这个地址里，游戏 ID 是 `123456`：

```text
https://store.steampowered.com/app/123456/Game_Name/
```

### 2. 找到成就文件

Steam 通常把这类文件放在：

```text
<Steam 文件夹>\appcache\stats
```

文件名是：

```text
UserGameStatsSchema_<游戏ID>.bin
```

如果游戏 ID 是 `123456`，文件名就是：

```text
UserGameStatsSchema_123456.bin
```

如果你要求 Codex 自动查找文件，它可以运行：

```powershell
python <skill>\scripts\steam_bkv_tool.py find-schema --game-id 123456
```

这个查找是可选的。只有你要求自动查找时，Codex 才应该使用它。

### 3. 提出翻译请求

示例：

```text
使用 $steam-achievement-localizer 翻译这个 Steam 成就文件。

游戏 ID：123456
schema 文件：<UserGameStatsSchema_123456.bin 的路径>
目标语言：schinese
流程：先导出 CSV 给我检查，我确认后再写回
翻译要求：保留官方物品名，使用简洁自然的中文成就文案
```

你也可以提供术语表、官方翻译文本、Wiki 文本、已有翻译文件或风格说明。

## 可选流程

你可以要求 Codex：

- 先导出 CSV 给你检查；
- 使用你改好的 CSV 生成翻译后的副本；
- 只翻译缺少目标语言的成就；
- 自动查找文件并导出 CSV；
- 在你明确确认后，把翻译后的文件安装回 Steam。

默认只会自动做版本检查。其他自动化步骤必须在你要求后才执行。

### 可选：自动导出

如果你明确要求自动化，Codex 可以查找 schema 文件，把它复制到输出文件夹，导出
CSV，导出缺失语言 CSV，并运行检查：

```powershell
python <skill>\scripts\steam_bkv_tool.py workflow --game-id 123456 --target-language schinese --out-dir outputs
```

`*.missing.csv` 只列出还没有目标语言的成就。如果你要求批量翻译缺失项，Codex 可以
为每一行填写 `target_name` 和 `target_description`。

### 应用检查后的 CSV

```powershell
python <skill>\scripts\steam_bkv_tool.py workflow --game-id 123456 --target-language schinese --out-dir outputs --translations outputs\translations.csv --strict-no-latin
```

翻译文本应保持简单、单行。不要包含制表符、换行、原始转义符、NUL 字节或控制
字符。脚本会在写入前移除不安全字符，并报告有多少字段被清理过。

### 安装回 Steam

只有在你准备替换本地 Steam 文件时再执行：

```powershell
python <skill>\scripts\steam_bkv_tool.py workflow --game-id 123456 --target-language schinese --out-dir outputs --translations outputs\translations.csv --install
```

这个流程会先备份原文件，再检查安装后的文件是否和翻译副本一致。

## Skill 会检查什么

- 原始文件能否安全读取并原样写回。
- 翻译后的副本能否安全读取并原样写回。
- 成就是按稳定 ID 匹配，而不是按行号匹配。
- 缺失、多余或空白的翻译行会被报告。
- 翻译文本中的不安全字符会在写入前移除。

## 致谢

本项目参考了以下公开项目：

- [achievement_reconstructor](https://github.com/CommitteeOfZero/achievement_reconstructor)
- [SamRewritten](https://github.com/PaulCombal/SamRewritten)
- [SteamAchievementLocalizer](https://github.com/PanVena/SteamAchievementLocalizer)

感谢这些项目的作者和贡献者分享 Steam 成就文件和本地化流程相关研究。

本项目是独立实现。使用上述项目内容时，请遵守各项目的许可证。

## 许可证

MIT
