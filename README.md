简体中文 | [English](README_EN.md)

# Steam Achievement Localizer Skill

当前版本：`v1.1.0`

用于研究、翻译和验证 Steam 成就文本的 skill，可从真实 `UserGameStatsSchema_*.bin` 或公开 App ID 开始。两条路线均输出可独立投稿的翻译库 JSON；真实 BIN 项目同时保留无损 BIN 和标准 ZIP 输出。翻译时对照所有已获取语言，并结合成就语境研究和经核实的已有翻译。

## 与相关仓库的分工

- [Steam 成就翻译库](https://github.com/GaBoron/steam-achievement-translation-library)：保存 BIN 和 JSON-only 译本并接收投稿。准备项目时查询当前目录，存在匹配参考时会校验后保存。
- [SATLI](https://github.com/GaBoron/SATLI)：负责 BIN 的预览、安装、备份和恢复。[SATLI lite](https://github.com/GaBoron/SATLI-lite) 0.2.0+ 可直接显示独立 JSON 译文。
- 本仓库：负责多语言研究、翻译草稿、校验和输出，不使用公开数据合成 BIN。

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

# 无 BIN、无需拥有游戏：获取公开成就原文
python <skill>\scripts\steam_bkv_tool.py prepare `
  --app-id 123456 --target-language schinese `
  --source-languages english,japanese

# 完成研究和翻译后生成最终文件
python <skill>\scripts\steam_bkv_tool.py apply `
  --workspace "localization\123456-schinese"
```

`--schema` 与 `--app-id` 二选一。公开路线默认获取 `english`；用 `--source-languages` 指定其他相关语言，不可获取的语言会记录原因，实际获取到的语言必须逐一审阅。`--variant-id` 选择翻译库版本，默认为 `default`。只有真实 BIN 项目在无法联网或用户明确禁止联网时才使用 `--offline`。

公开路线匿名读取 Steam 成就页面的结构化数据，无需 API 密钥。没有可用原文时会报出原因；不同语言的成就 ID 集合不一致、字段缺漏，或与所选翻译库版本冲突时，会阻止正式导出。公开列表不能证明游戏版本、隐藏成就或完整客户端 schema 均已核实。

## 文件布局

每个游戏和目标语言只使用一个项目目录：

```text
localization/123456-schinese/
├── input/
│   └── UserGameStatsSchema_123456.bin  # 或 public-achievements.json
├── work/
│   ├── manifest.json
│   ├── sources.json
│   ├── translations.csv
│   └── references/
└── final/
    ├── UserGameStatsSchema_123456.json
    ├── UserGameStatsSchema_123456.bin  # 仅真实 BIN 路线
    ├── UserGameStatsSchema_123456.zip  # 仅真实 BIN 路线
    └── report.json
```

- `input/`：保存真实 BIN 副本，或包含获取来源的公开文本快照。
- `work/`：只保存翻译过程文件、研究来源和经校验的参考文件。
- `final/`：保存独立 JSON 和报告；真实 BIN 项目另含 BIN 和标准投稿 ZIP。

两条路线均导出[格式 2 JSON](https://github.com/GaBoron/steam-achievement-translation-library/blob/main/docs/translation-json.md)，使用稳定的 API name 排序、排序后的语言列表、UTF-8、LF 和结尾换行。文件只有五个顶层字段，不含 `source_sha256`；真实 BIN 的校验信息保留在项目报告中，公开快照使用独立的内容校验字段。来源和限制保留在研究清单与报告中。可把 JSON 直接上传翻译库的 JSON 投稿表单，并在投稿备注提供实际来源。JSON 只包含显示文本，不能作为 BIN 安装。

## 翻译要求

`work/translations.csv` 会为每种已获取的源语言（包括公开数据）生成 `<language>_name` 和 `<language>_description` 列。翻译时必须逐一比较这些列，不能只看英文。联网可用时，网络研究是高权重的翻译依据：应使用游戏名配合成就原文或 API ID 搜索，并继续核对相关角色、物品、地点、任务、机制、剧情、双关和系列术语。

证据优先级依次为官方游戏内本地化及开发者/商店等第一方资料；同一游戏、同一成就的经核实已有翻译（包括匹配的翻译库 schema）；可信 Wiki、攻略、数据库和稳定的社区用法；最后才是 schema 多语言文本和一般语言推断。已有翻译属于强参考，但必须核对成就 ID、游戏版本、原意、字段结构、占位符和目标语言术语，不能机械照抄。把实际使用的链接写入 `work/sources.json`，并在备注中说明它支持了什么语境或措辞；证据冲突时，在 `translation_notes` 中说明取舍。

名称和描述按“每个成就、每个字段”分别对应：只要某项成就的名称在一种语言中非空，它就必须在所有语言中非空；描述同理。如果某字段在所有语言中都为空，目标语言也应保持为空。因此，同一个 schema 可以有 9 项成就同时包含名称和描述，另 1 项只有名称；翻译只需保持相同的字段组合，不要求把空缺字段补满。

`apply` 会检查：

- 是否通过 `consulted_schema_languages` 确认审阅了全部已获取语言；
- 联网可用时是否记录了在线来源；
- 成就 API ID 是否完整且无额外项；
- 每项成就的名称和描述是否分别在所有语言中保持“全部非空或全部为空”，且非空文本为单行并无控制字符；
- 目标占位符是否与原文字段一致，以及 JSON 的 ID、语言、结构和大小限制是否合规；
- 真实 BIN 项目是否只改变目标语言字段，并保持源文件和最终文件字节级 roundtrip；
- BIN 路线的 ZIP 是否仅包含根目录下的同名 BIN。

报告区分 `BIN-derived` 与 `public-data-derived`，并说明是否满足正式 JSON 的来源和结构校验要求。通过校验不代表译文准确或真实客户端显示有效，仍需审阅和验收；公开项目不会声明通过 BIN roundtrip 或安装验证。

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
