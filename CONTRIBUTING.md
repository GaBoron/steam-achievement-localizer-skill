# 贡献指南

本仓库只维护 Codex skill 和本地化项目工具。翻译数据请提交到 [Steam 成就翻译库](https://github.com/GaBoron/steam-achievement-translation-library)；面向用户的安装、备份和恢复逻辑请提交到 [Steam 成就翻译安装器](https://github.com/GaBoron/steam-achievement-translation-installer)。

修改本仓库时请保持以下边界：

- `scripts/steam_bkv_tool.py` 只负责命令组合。
- `scripts/steam_localizer/bkv.py` 只负责 Binary KeyValues 和 schema 结构。
- `translations.py` 负责翻译表与研究清单。
- `library.py` 负责只读的翻译库索引和参考文件校验。
- `project.py` 负责集中式项目目录和最终产物。
- `steam.py` 只负责本机 schema 定位。

提交前运行：

```powershell
python -m compileall -q scripts tests
python -m unittest discover -s tests -v
python C:\Users\<user>\.codex\skills\.system\skill-creator\scripts\quick_validate.py .
```

新增行为应包含独立单元测试。不得恢复默认版本联网检查、直接覆盖 Steam 文件、静默清理翻译文本或把过程文件散落到项目目录之外。
