[English](README.md) | 简体中文

# Steam Achievement Localizer Skill

这是一个 Codex skill，用于安全地翻译 Steam 本地成就描述文件
`UserGameStatsSchema_*.bin`，并避免破坏 Steam Binary KeyValues 结构。

适用场景：某个 Steam 游戏的本地 appcache 成就 schema 只有英文名称和描述，
你希望添加 `schinese`、`tchinese`、`japanese`、`koreana` 等 Steam 语言字段。

## 功能

- 按 Steam Binary KeyValues 解析文件，保留节点顺序和重复键。
- 修改前先做解析/写回无损往返校验。
- 导出完整树 JSON 和成就文本 CSV。
- 按成就 ID/API 名称合并翻译 CSV。
- 只写入成就 `display/name` 和 `display/desc` 下的目标语言字段。
- 写入后再次解析和重序列化，确认本地化文件稳定。

这个工具不做全局字节替换。未修改文件必须逐字节无损往返。

## 安装

### 方式一：Release zip

从 GitHub Releases 下载 `steam-achievement-localizer.zip`，解压后把
`steam-achievement-localizer` 文件夹放到 Codex skills 目录：

```powershell
Expand-Archive .\steam-achievement-localizer.zip -DestinationPath "$env:USERPROFILE\.codex\skills" -Force
```

安装后目录应类似：

```text
%USERPROFILE%\.codex\skills\steam-achievement-localizer\SKILL.md
```

### 方式二：从仓库复制

克隆仓库后复制到 Codex skills 目录：

```powershell
git clone https://github.com/GaBoron/steam-achievement-localizer-skill.git
Copy-Item -Recurse .\steam-achievement-localizer-skill `
  "$env:USERPROFILE\.codex\skills\steam-achievement-localizer"
```

### 方式三：Codex prompt 安装

在 Codex 里输入：

```text
Install the skill from https://github.com/GaBoron/steam-achievement-localizer-skill
```

安装后让 Codex 使用：

```text
使用 $steam-achievement-localizer 翻译这个 Steam 成就 schema。
```

## 脚本用法

导出并验证原始 schema：

```bash
python scripts/steam_bkv_tool.py "C:/path/UserGameStatsSchema_123.bin" --out-dir outputs --target-language schinese
```

套用翻译：

```bash
python scripts/steam_bkv_tool.py "C:/path/UserGameStatsSchema_123.bin" \
  --out-dir outputs \
  --target-language schinese \
  --translations outputs/translations.csv \
  --localized-bin outputs/UserGameStatsSchema_123.schinese.bin \
  --strict-no-latin
```

验证已本地化文件：

```bash
python scripts/steam_bkv_tool.py outputs/UserGameStatsSchema_123.schinese.bin --out-dir outputs/verify --target-language schinese
```

## 翻译 CSV

可接受的 ID 列：

- `api_name`
- `id`
- `achievement_id`
- `name`

可接受的名称翻译列：

- `<language>_name`
- `target_name`
- `translated_name`
- `name_zh`
- `schinese_name`

可接受的描述翻译列：

- `<language>_description`
- `target_description`
- `translated_description`
- `description_zh`
- `schinese_description`

示例：

```csv
api_name,schinese_name,schinese_description
ACH_WIN_ONE_GAME,赢下一局,赢得一整局游戏
ACH_COLLECT_100,收藏家,收集100个物品
```

## 安全建议

- 覆盖 Steam 原文件前先备份。
- 本地化副本通过验证之前，不要直接改 Steam 原文件。
- 翻译来源应来自官方文本、游戏 wiki 或人工审核过的 CSV。
- 面向中日韩等目标语言时，`--strict-no-latin` 可以帮助发现残留英文。

## 仓库内容

- `SKILL.md`：Codex skill 说明。
- `scripts/steam_bkv_tool.py`：Binary KeyValues 解析、导出、写回和本地化工具。
- `README_CN.md`：中文说明。

## 许可证

MIT
