简体中文 | [English](README_EN.md)

# Steam Achievement Localizer Skill

当前版本：`v1.1.0`

用于研究、翻译和验证 Steam `UserGameStatsSchema_*.bin` 成就文本的 Codex skill。它会无损解析 Binary KeyValues、把源文件中的全部语言放进同一份翻译表，并在可联网时优先使用与成就有关的网络语境、参考资料和经核实的已有翻译，最终只修改指定语言字段。

## 与相关仓库的分工

- [Steam 成就翻译库](https://github.com/GaBoron/steam-achievement-translation-library)：保存社区翻译 BIN、索引和投稿流程。准备项目时，本 skill 会联网查询该库；若存在匹配条目，会校验并保存主版本作为参考。
- [Steam 成就翻译安装器](https://github.com/GaBoron/steam-achievement-translation-installer)：负责扫描、预览、安装、备份和恢复；本 skill 生成供其使用的标准 BIN/ZIP。
- 本仓库：负责多语言语境研究、翻译草稿、无损写入、验证，以及生成兼容上述两个仓库的标准 BIN/ZIP。

## 安装

安装时以 [Latest Release](https://github.com/GaBoron/steam-achievement-localizer-skill/releases/latest) 的 `steam-achievement-localizer.zip` 为内容来源。AI 应下载该资产，并按压缩包内的目录结构完整安装：

```text
Install $steam-achievement-localizer from the latest GitHub Release asset at https://github.com/GaBoron/steam-achievement-localizer-skill/releases/latest. Use only the files contained in steam-achievement-localizer.zip and preserve its directory structure.
```

Release 资产包含：

```text
steam-achievement-localizer/
├── SKILL.md
├── VERSION
├── LICENSE
├── agents/
│   └── openai.yaml
└── scripts/
    ├── steam_bkv_tool.py
    └── steam_localizer/
        └── *.py
```

安装后调用：

```text
使用 $steam-achievement-localizer 翻译这个 Steam 成就 schema。
```

## 命令

使用以下运行时命令：

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

## 翻译要求

`work/translations.csv` 会为源 schema 中的每一种语言生成 `<language>_name` 和 `<language>_description` 列。翻译时必须逐一比较这些列，不能只看英文。联网可用时，网络研究是高权重的翻译依据：应使用游戏名配合成就原文或 API ID 搜索，并继续核对相关角色、物品、地点、任务、机制、剧情、双关和系列术语。

证据优先级依次为官方游戏内本地化及开发者/商店等第一方资料；同一游戏、同一成就的经核实已有翻译（包括匹配的翻译库 schema）；可信 Wiki、攻略、数据库和稳定的社区用法；最后才是 schema 多语言文本和一般语言推断。已有翻译属于强参考，但必须核对成就 ID、游戏版本、原意、字段结构、占位符和目标语言术语，不能机械照抄。把实际使用的链接写入 `work/sources.json`，并在备注中说明它支持了什么语境或措辞；证据冲突时，在 `translation_notes` 中说明取舍。

名称和描述按“每个成就、每个字段”分别对应：只要某项成就的名称在一种语言中非空，它就必须在所有语言中非空；描述同理。如果某字段在所有语言中都为空，目标语言也应保持为空。因此，同一个 schema 可以有 9 项成就同时包含名称和描述，另 1 项只有名称；翻译只需保持相同的字段组合，不要求把空缺字段补满。

`apply` 会检查：

- 是否确认查阅了源 schema 的所有语言；
- 联网可用时是否记录了在线来源；
- 成就 API ID 是否完整且无额外项；
- 每项成就的名称和描述是否分别在所有语言中保持“全部非空或全部为空”，且非空文本为单行并无控制字符；
- 是否只改变目标语言字段；
- 源文件和最终文件是否都能字节级 roundtrip；
- 最终 ZIP 是否仅包含根目录下的同名 BIN。

## 开发检查

```powershell
python -m compileall -q scripts tests
python -m unittest discover -s tests -v
python C:\Users\<user>\.codex\skills\.system\skill-creator\scripts\quick_validate.py .
```

## 支持

如需联系支持，请发送邮件至 [SATLI.support@proton.me](mailto:SATLI.support@proton.me)。

## 致谢

Binary KeyValues 研究参考：

- [achievement_reconstructor](https://github.com/CommitteeOfZero/achievement_reconstructor)
- [SamRewritten](https://github.com/PaulCombal/SamRewritten)
- [SteamAchievementLocalizer](https://github.com/PanVena/SteamAchievementLocalizer)
