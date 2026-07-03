[English](README.md) | 简体中文

# Steam Achievement Localizer Skill

这是一个用于翻译 Steam 本地成就名称和描述的 Codex skill，处理对象是
`UserGameStatsSchema_*.bin` 文件。它可以帮助 AI 助手读取 Steam 成就 schema、
整理翻译、并安全写回文件，避免破坏 Binary KeyValues 文件结构。

你不需要理解 Steam 的二进制格式。大多数情况下，只要提供游戏 ID、schema 文件
路径、目标语言，以及你的翻译要求或参考资料即可。

## 安装

### 方式一：让 Codex 安装

```text
Install the skill from https://github.com/GaBoron/steam-achievement-localizer-skill
```

安装后这样调用：

```text
使用 $steam-achievement-localizer 翻译这个 Steam 成就 schema。
```

### 方式二：手动安装

从 GitHub Releases 下载 `steam-achievement-localizer.zip`，解压到 Codex skills
目录：

```powershell
Expand-Archive .\steam-achievement-localizer.zip -DestinationPath "$env:USERPROFILE\.codex\skills" -Force
```

安装后的路径应类似：

```text
%USERPROFILE%\.codex\skills\steam-achievement-localizer\SKILL.md
```

## 版本检查

Skill 内包含本地 `VERSION` 文件。每次开始使用时，先让 Codex 检查本地版本是否和
GitHub 最新 tag 一致：

```text
使用 $steam-achievement-localizer，并先检查 skill 版本。
```

底层命令是：

```powershell
python <skill>\scripts\steam_bkv_tool.py version-check --warn-only
```

如果版本不一致，处理重要文件前建议先从最新 GitHub Release 更新 skill。

## 如何使用此 Skill 翻译成就

### 1. 确认 Steam 游戏 ID

打开你要翻译的游戏商店页面。地址栏通常是这种格式：

```text
https://store.steampowered.com/app/<游戏ID>/<游戏名>/
```

例如 `https://store.steampowered.com/app/123456/Game_Name/` 中，游戏 ID 就是
`123456`。

你也可以只告诉 AI 助手游戏名，让它自己查 ID；但游戏名可能重复或相似，因此更
推荐你从商店页面地址栏手动确认。

### 2. 找到本地成就 schema 文件

Steam 在 Windows 上的默认位置通常是：

```text
C:\Program Files (x86)\Steam\appcache\stats
```

如果你的 Steam 安装在其他位置，请进入：

```text
<你的 Steam 安装位置>\appcache\stats
```

在这个文件夹里找到：

```text
UserGameStatsSchema_<游戏ID>.bin
```

例如游戏 ID 是 `123456`，就找：

```text
UserGameStatsSchema_123456.bin
```

你也可以要求 AI 助手根据游戏名或你刚刚查询到的游戏 ID 来自动定位目标文件位置，但这往往不可靠。

### 3. 把文件路径和翻译要求发给 AI 助手

你可以直接粘贴完整路径，并说明目标语言和翻译要求。例如：

```text
使用 $steam-achievement-localizer 把这个文件翻译成简体中文：
C:\Program Files (x86)\Steam\appcache\stats\UserGameStatsSchema_123456.bin

请保留官方物品名，整体使用自然的中文成就文案，描述尽量简洁。
```

如果有参考资料，也可以一起提供，例如官方翻译、术语表、Wiki 文本、已有本地化
文件、角色名/道具名对照表，或你希望采用的语气和风格。

### 4. 选择翻译流程

你可以让 AI 助手：

- 翻译完成后直接生成可替换的本地化文件；
- 先生成一份 CSV 翻译对照表，等你确认无误后再写回文件；
- 使用你自己修改后的 CSV 作为最终翻译来源。

如果文件比较重要，推荐先生成 CSV 对照表进行审核，再让 AI 写回。

这个流程里的机械步骤可以自动化。例如已知游戏 ID 时，Codex 可以搜索常见 Steam
安装位置，把 live schema 复制到输出目录，导出 CSV，并执行安全检查：

```powershell
python <skill>\scripts\steam_bkv_tool.py workflow --game-id 123456 --target-language schinese --out-dir outputs
```

审核或编辑 CSV 后，Codex 可以应用翻译并生成已验证的本地化二进制文件：

```powershell
python <skill>\scripts\steam_bkv_tool.py workflow --game-id 123456 --target-language schinese --out-dir outputs --translations outputs\translations.csv --strict-no-latin
```

如果你明确要求安装回 Steam，这个 workflow 会先备份原文件再替换：

```powershell
python <skill>\scripts\steam_bkv_tool.py workflow --game-id 123456 --target-language schinese --out-dir outputs --translations outputs\translations.csv --install
```

### 5. 谨慎替换 Steam 原文件

替换前请先备份原始 `UserGameStatsSchema_<游戏ID>.bin` 文件。确认本地化文件已经
生成并通过验证后，再按你的需求替换原文件。

## 可直接复制的提示词模板

```text
使用 $steam-achievement-localizer 翻译 Steam 成就。

游戏 ID：<游戏ID>
schema 文件：<UserGameStatsSchema_<游戏ID>.bin 的完整路径>
目标语言：<schinese / tchinese / japanese / koreana / 等>
流程：先导出 CSV 给我审核，我确认后再写回
翻译要求：<术语表、风格、官方名称、参考资料或特殊规则>
```

## Skill 会在后台做什么

- 读取 Steam Binary KeyValues schema，并避免改动无关数据。
- 导出成就名称和描述，方便翻译或人工审核。
- 将翻译写入指定的 Steam 语言字段，例如 `schinese`、`tchinese`、`japanese`、
  `koreana`。
- 写入后再次验证文件，确认本地化后的 schema 仍可被正确解析。

## 致谢

本项目在开发过程中参考了以下开源项目对 Steam 成就 Schema、Binary KeyValues
格式及本地化处理方式的研究与实现：

- [achievement_reconstructor](https://github.com/CommitteeOfZero/achievement_reconstructor)
  为 Steam `UserGameStatsSchema_*.bin` 的解析、重建及可编辑化提供了重要参考。

- [SamRewritten](https://github.com/PaulCombal/SamRewritten)
  其 Binary KeyValues 解析实现帮助确认了数据类型编号、递归结构和字符串编码方式。

- [SteamAchievementLocalizer](https://github.com/PanVena/SteamAchievementLocalizer)
  为 Steam 成就多语言字段的识别、导入导出和本地化工作流提供了参考。

感谢这些项目的作者和贡献者对 Steam 数据格式进行研究并公开成果，使本项目得以在
已有社区经验的基础上完成独立实现。

本项目未声称拥有上述项目的代码或研究成果。各项目的版权和许可证归其原作者所有，
使用相关项目时请遵守各自仓库中的许可证条款。

## 许可证

MIT
