# 贡献 Steam Achievement Localizer Skill

简体中文 | [English](CONTRIBUTING_EN.md)

本仓库维护 Codex skill、本地运行脚本和安装文档。

## 可以提交到本仓库的内容

- `SKILL.md` 中的使用流程、约束或版本检查规则。
- `scripts/steam_bkv_tool.py` 的 Binary KeyValues 解析、导出、写入、校验、查找或安装回写逻辑。
- README、安装说明、release 打包说明或 skill bug 模板。
- 不包含具体游戏翻译数据的测试样例或回归用例。

## 开发检查

修改脚本后，至少运行快速校验：

```powershell
python scripts/steam_bkv_tool.py version-check --warn-only
```

如果改动影响解析、导出或写入流程，请用真实或测试 schema 在副本上验证 roundtrip，并确认不会覆盖用户原始 Steam 文件。

## 安全边界

- 默认只处理用户提供的 schema 副本或输出目录中的文件。
- 不要在未明确确认时写回 Steam `appcache/stats`。
- 不要提交密钥、令牌、个人路径、Steam 账号数据或私有本地配置。
