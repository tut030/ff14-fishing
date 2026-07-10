# 贡献指南

欢迎 PR！这几个方向最需要帮手：

- 🌐 **英文短语表补词条**：`engine/i18n.py`（`lang en` 模式的翻译层，单点挂载）
- ✍ **鱼 flavor 文案**：`data/fish_text.json`（手写创作文案，中英皆可）
- 🚶 **路遇 / 氛围文案池**：`engine/encounters.py`、`engine/atmosphere.py`（往列表里追加即可，不用改逻辑）
- 🐛 **Bug 修复与玩法建议**：直接开 issue 聊

## 三条规矩

1. **测试必须全绿**：提交前跑 `python -m pytest tests/ -q`（PR 也会自动跑）。
2. **文案规范**：见 `engine/encounters.py` 文件头注释——NPC 写成「形容词的＋称谓」，称谓只用白名单；不用第三人称男性代词；互助平视、不写成施舍；有自动测试把关，违规会直接飘红。
3. **`data/` 下多数 JSON 是 `tools/` 脚本生成的**：改数据请改对应 build 脚本或开 issue，别手改生成文件（`fish_text.json` 的 flavor 除外，欢迎手写）。

存档（`saves/`）永远不要提交——`.gitignore` 已挡好，请勿绕过。
