简体中文 | [English](README_EN.md)

# Steam Achievement Localizer Skill

当前版本：`v0.1.2`

用于研究、翻译和验证 Steam `UserGameStatsSchema_*.bin` 成就文本的 Codex skill。它会无损解析 Binary KeyValues、把源文件中的全部语言放进同一份翻译表，并在可联网时要求补充在线资料，最终只修改指定语言字段。

## 与相关仓库的分工

- [Steam 成就翻译库](https://github.com/GaBoron/steam-achievement-translation-library)：保存社区翻译 BIN、索引和投稿流程。准备项目时，本 skill 会联网查询该库；若存在匹配条目，会校验并保存主版本作为参考。
- [Steam 成就翻译安装器](https://github.com/GaBoron/steam-achievement-translation-installer)：负责扫描、预览、安装、备份和恢复。本 skill 不再直接覆盖 Steam 文件。
- 本仓库：负责多语言语境研究、翻译草稿、无损写入、验证，以及生成兼容上述两个仓库的标准 BIN/ZIP。

## 安装

让 Codex 从以下仓库安装：

```text
Install the skill from https://github.com/GaBoron/steam-achievement-localizer-skill
```

安装后调用：

```text
使用 $steam-achievement-localizer 翻译这个 Steam 成就 schema。
```

skill 目录需要同时保留 `SKILL.md`、`VERSION`、`agents/` 和完整的 `scripts/`。

## 精简后的命令

只保留三类运行时动作：

```powershell
# 可选：查找本机 schema
python <skill>\scripts\steam_bkv_tool.py find-schema --app-id 123456

# 创建集中式翻译项目，并默认联网查询翻译库
python <skill>\scripts\steam_bkv_tool.py prepare `
  --schema "C:\path\UserGameStatsSchema_123456.bin" `
  --target-language schinese

# 完成研究和翻译后生成最终文件
python <skill>\scripts\steam_bkv_tool.py apply `
  --workspace "localization\123456-schinese"
```

只有确实无法联网或用户明确禁止联网时才给 `prepare` 添加 `--offline`。

## 文件布局

每个游戏和目标语言只使用一个项目目录：

```text
localization/123456-schinese/
├── input/
│   └── UserGameStatsSchema_123456.bin
├── work/
│   ├── manifest.json
│   ├── sources.json
│   ├── translations.csv
│   └── references/
└── final/
    ├── UserGameStatsSchema_123456.bin
    ├── UserGameStatsSchema_123456.zip
    └── report.json
```

- `input/`：只保存本次任务使用的源文件副本。
- `work/`：只保存翻译过程文件、研究来源和经校验的参考文件。
- `final/`：只保存可交付 BIN、标准投稿 ZIP 和最终报告。

不再默认生成 roundtrip BIN、完整树 JSON、重复的导出 CSV、版本缓存或安装备份。

## 翻译要求

`work/translations.csv` 会为源 schema 中的每一种语言生成 `<language>_name` 和 `<language>_description` 列。翻译时必须逐一比较这些列，不能只看英文。联网可用时还必须搜索官方本地化、开发者资料、Steam 页面、可信 Wiki 或社区资料，并把实际使用的链接写入 `work/sources.json`。

`apply` 会检查：

- 是否确认查阅了源 schema 的所有语言；
- 联网可用时是否记录了在线来源；
- 成就 API ID 是否完整且无额外项；
- 所有目标名称和描述是否完整、单行且无控制字符；
- 是否只改变目标语言字段；
- 源文件和最终文件是否都能字节级 roundtrip；
- 最终 ZIP 是否仅包含根目录下的同名 BIN。

## 开发检查

```powershell
python -m compileall -q scripts tests
python -m unittest discover -s tests -v
python C:\Users\<user>\.codex\skills\.system\skill-creator\scripts\quick_validate.py .
```

## 致谢

Binary KeyValues 研究参考：

- [achievement_reconstructor](https://github.com/CommitteeOfZero/achievement_reconstructor)
- [SamRewritten](https://github.com/PaulCombal/SamRewritten)
- [SteamAchievementLocalizer](https://github.com/PanVena/SteamAchievementLocalizer)
