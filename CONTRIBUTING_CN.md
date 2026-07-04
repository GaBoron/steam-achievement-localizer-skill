# 贡献共享成就翻译

[English](CONTRIBUTING.md)

本仓库接受用户投稿的 Steam 成就 schema 文件，用于维护 `achievement-library/` 中的公开翻译库。

## 提交前检查

请先确认相同 Steam app ID 是否已经存在：

- 在 `achievement-library/README.md` 中搜索数字 Steam app ID 或游戏名。
- 检查开放 PR 中是否已有相同 app ID 或 `UserGameStatsSchema_<game_id>.bin`。
- 检查带有 `translation-contribution` 标签的开放 issue。

如果同一个游戏已经在库中、已经处于 PR 审核中，或已经在开放投稿 issue 中，请不要重复提交。

## 投稿规范

- 上传名为 `UserGameStatsSchema_<game_id>.zip` 的 ZIP，因为 GitHub issue 不能直接上传 `.bin` 附件。
- ZIP 内必须只包含一个真实 Steam schema 文件，文件名必须是 `UserGameStatsSchema_<game_id>.bin`。
- issue 中的游戏 ID、Steam 商店地址、上传文件名必须一致。
- 只选择上传文件中已经完整包含的语言。
- 每个选择的语言都必须为每个成就包含成就名和成就描述字段。
- 保持 schema 文件为 Steam Binary KeyValues 格式。不要先转换成 JSON、CSV 或文本再压缩。
- 不要上传包含私人账号数据、密钥或无关本地文件的内容。

## 审核流程

使用英文或中文翻译投稿 issue 模板并附上 `.zip` 文件。GitHub Action 会：

- 下载上传的文件；
- 检查 Steam 商店地址、游戏 ID、ZIP 文件名和 schema 文件名是否匹配；
- 解压 ZIP，并要求其中只有一个 schema 文件；
- 按 Steam Binary KeyValues 解析文件，并要求序列化后字节完全一致；
- 检查所选语言字段是否覆盖所有成就；
- 检查游戏是否已经在库中，或是否已有开放投稿；
- 为翻译投稿 issue 补上 `translation-contribution` 标签，并冻结 issue 标题和正文，防止提交后修改已提交字段；
- 初审通过后自动创建 PR；
- 在 PR 准备好后祝贺投稿人并关闭 issue。

生成的 PR 会包含更新后的用户索引、机器索引、投稿 schema 文件，以及每个成就 ID 对应各投稿语言成就名和描述的审核表格。最终是否合并仍由维护者审核决定。

如果机器人发现 ZIP 文件名、schema 文件名或 schema 文件内容问题，它会保留 issue，并说明具体失败原因。翻译投稿 issue 提交后会冻结标题和正文，投稿人不能再编辑已提交字段，但仍可以评论。请在新评论中附上修正后的 ZIP，并写：

```text
/update <附件链接>
```

机器人会用这个新 ZIP 链接重新检查文件。如果非维护者尝试修改 issue 标题或正文，机器人会还原更改。如果问题不是替换文件能解决的，例如重复投稿或 Steam app 元数据不匹配，机器人会说明原因并直接关闭 issue。

管理员可以在投稿 issue 中评论：

```text
/force-review
```

这个命令会忽略开放 PR 或开放投稿 issue 这类重复检查警告，直接进入后续 PR 生成流程。它不会跳过已入库重复、Steam app 元数据不匹配、文件名错误、Steam Binary KeyValues 解析失败、语言字段缺失等硬错误。非管理员使用此命令时，机器人会拒绝并保持普通审核流程不变。

维护者 approve 生成的审核 PR 后，机器人会先感谢投稿人，然后 squash merge 这个 PR，并删除投稿分支。

## 标签区分

- 翻译库投稿：使用 `translation-contribution` 标签。只有这个标签会触发投稿机器人审核。
- skill 问题反馈：使用 `skill-bug` 标签。此类 issue 不会触发翻译文件审核。

如果 GitHub issue 模板没有自动打上标签，Actions 会按模板内容主动创建并补上对应标签。

## 翻译库结构

```text
achievement-library/
├── README.md
├── README_EN.md
├── index.json
└── files/
    └── <game_id>/
        └── UserGameStatsSchema_<game_id>.bin
```

`achievement-library/README.md` 是中文默认用户索引，`achievement-library/README_EN.md` 是英文索引。两者都可以直接在 GitHub 页面中搜索游戏名、Steam app ID 或语言代码。`index.json` 是给脚本和自动化读取的机器索引。
