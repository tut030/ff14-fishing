# FF14 钓鱼游戏（给 AI 玩）

![tests](https://github.com/tut030/ff14-fishing/actions/workflows/tests.yml/badge.svg) ![python](https://img.shields.io/badge/python-3.10%2B-blue) ![license](https://img.shields.io/badge/license-MIT-green)

零联网，天气与时间按真实时钟在本地推算。
覆盖全部大区（2.0～7.x）、2119 条鱼（含常见杂鱼；同名鱼共享图鉴，去重后图鉴共 1445 格）、真实钓场等级 + 升级系统 + 多语言名。

## 功能一览

- 🎣 **岸钓**：37 大区 2119 条鱼（line 1932 + spear 187），真实钓场等级、天气/时段开窗、前置天气
- 🚢 **海钓**：与 FF14 同步的航班时刻表，259 条海钓专属鱼，幻海流、渔分、船友互动
- 🧥 **装备**：109 把真实鱼竿 + 全身 11 部位防具 + 魔晶石镶嵌/禁断
- 📜 **职业任务**：每 5 级一篇轻松短剧情（20 篇）
- 📋 **日随/周随**：全球同一份，由真实日期确定性生成
- 🏅 **成就 + 称号**：岸钓进度解锁
- 🎪 **金碟钓鱼赛**：限定竿数拼渔分，赢 MGP
- 🐠 **水族箱**：把钓过的鱼养起来观赏
- 🎒 **鱼袋与卖鱼**：渔获入袋（35 格起步，Lv15 任务解锁鞍囊 +70），`sell` 卖出才有钱；袋满只能忍痛放生
- ⚔ **提钩窗口**：耐心/鱼王咬钩须手选 精准/强力/硬拉，选错跑鱼——原作技巧点还原；专一垂钓/拍击水面/双·三重提钩同捆
- ⚡ **捕鱼人之识**：32 条鱼王自带前置鱼（全量数据驱动），集齐触发直感才开咬；坐钩链可连跳
- 🌐 **英文模式**：`lang en` 一键切英文结构化输出（存档记忆；短语表 engine/i18n.py 可社区共建 PR）
- 🍳 **料理**：袋中的鱼 + 调味料做菜，或餐厅买成品——30 分钟属性/经验 buff
- 🐾 **宠物 & 坐骑**：里程碑 / MGP 解锁收藏，召唤陪钓、骑乘赶路
- 🏷 **雇员**：Lv17 签终身契（名额 2·八族可选性别或魔兽形态·**全职业**逐个开放）。旧装备换🪖军票买探险币；派探险带回渔获/猎物/调料/食物/惊喜，战斗职业每趟一则**讨伐见闻**，偶得💾**内存卡**；职业武器每 5 级一档（琪琪茹代购）；在家代修 5 折，每位 +175 格鱼袋
- 📖 **钓鱼日志 & 存档救援**：`diary` 回看今日战果；`rescue` 一键回滚自动备份
- 🖼 **鱼拓展示墙**：最大渔获排行 + flavor 文案
- 🧭 **钓场推荐**：根据等级 + 图鉴缺口 + 当前开窗自动推荐
- 🌤 **天气转换描写**：天气变了会有一句氛围文字
- 🚶 **路遇小事件**：`goto` 赶路时约 15% 偶遇——帮人捡行李、解风筝、指路，或捡到旧币和纪念小物（全自动结算，`encounter off` 可关）
- 💡 **分号串联**：`cast 10; goto Costa del Sol; look` 一条命令走多步（省 token）
- 🀄 **中文命令全支持**：看/抛竿/去/钓场/背包/查/耐心/鱼眼/撒饵/大鱼确保/喝药/存档/帮助…
- ✍ **鱼文案 100% 覆盖**：1445 条鱼全部有描述（官方图鉴 + 手写 flavor）

## 目录布局

```
ff14-fishing/
├── engine/            引擎代码（25 个模块）
│   ├── game.py          主循环 cmd()
│   ├── ocean.py         海钓系统
│   ├── atmosphere.py    氛围文案（竿感/天气/位置/欢迎）
│   ├── window.py        开窗判定（时段 + 天气 + 前置天气三关）
│   ├── fish.py          鱼数据加载 + 描述
│   ├── gp.py            GP 系统（patience/fisheyes/chum/prize/cordial）
│   ├── equipment.py     装备系统（全身 11 部位）
│   ├── materia.py       魔晶石（镶嵌/禁断/合成）
│   ├── achievements.py  成就
│   ├── titles.py        称号
│   ├── quests.py        职业任务
│   ├── tasks.py         日随/周随
│   ├── encounters.py    路遇小事件（v23）
│   ├── retainer.py      雇员系统（v38：军票·全职业·见闻·内存卡）
│   ├── leveling.py      升级系统
│   ├── gear.py          鱼竿数据
│   ├── bait.py          鱼饵系统
│   ├── scrip.py         收藏品/票
│   ├── save.py          存档（原子写 + 自动备份）
│   ├── time_kernel.py   现实时间 → ET + 天气
│   ├── weather.py       区域天气
│   └── ocean_schedule.py 海钓班次表
├── data/              静态数据
│   ├── fish.json             2119 条鱼
│   ├── ocean.json            259 条海钓鱼
│   ├── weather.json          天气概率表
│   ├── fish_text.json        鱼文案（100% 覆盖）
│   ├── venture_hunt.json     雇员探险素材/经验表（wiki 168 条）
│   ├── retainer_arms.json    全职业武器/主工具（32 职业 529 件）
│   └── ...
├── tests/             pytest 测试（106 个）
├── tools/             数据构建工具
├── saves/             玩家存档（本地，不入库）
├── ai_play.py         AI 驱动入口
├── play.py            人类交互入口
├── AI_GUIDE_MINI.md   给 AI 看的速通版（约1500字, 省token推荐先读）
├── AI_GUIDE.md        给 AI 看的中文说明
├── AI_GUIDE_EN.md     给 AI 看的英文说明
├── LICENSE            MIT
└── README.md
```

## 获取本项目

```
git clone https://github.com/tut030/ff14-fishing.git
```

不用 git 也行：仓库页绿色 **Code** 按钮 → **Download ZIP**，或到 Releases 页拿打包好的整包。

## 给 AI 朋友玩（部署到 VPS）

1. WinSCP 覆盖前，先把旧的 `ff14-fishing` 改名备份（如 `ff14-fishing.bak`）可回滚。
2. 甩整个文件夹上 VPS。VPS 需装 Python 3.10+。
3. 每个 AI 用自己的名字驱动，进度各自隔离、自动保存：
```
   python ai_play.py <名字> <命令>     # 例: python ai_play.py sakura cast
   python ai_play.py sakura "cast 10; goto Moraby Bay; look"  # 分号串联
```
4. 把 `AI_GUIDE_MINI.md`（速通版, 省 token）给 AI 看；细节再查 `AI_GUIDE.md`（中文全量）或 `AI_GUIDE_EN.md`（英文）。
   🔐 全程本地进程、不起服务、不开端口、无凭据，对外零暴露。

## 直接玩

```bash
python play.py        # Mac: python3 play.py
```
输入 look / cast / goto 钓场名 / bag / status 鱼名，退出输 quit。

## 跑测试

```bash
pip install pytest                    # 首次
python3 -m pytest tests/ -v          # 89 个测试，1 秒内跑完
```

## 在你自己代码里嵌入

```python
from engine.game import cmd
print(cmd("look"))
print(cmd("cast 5; bag"))
print(cmd("goto Moraby Bay"))
```

## 更新鱼数据（仅 FF14 出新版本时才需要）

```bash
pip install pyyaml                    # 仅首次
python tools/build_weather_data.py    # 重新生成天气表
python tools/build_fish_data.py       # 重新生成鱼数据
python tools/init_fish_text.py        # 给新鱼补文案占位（只增不改）
```

**想加更多区域**：改 `tools/build_*.py` 顶部的 `REGIONS`（加大区 id），重跑上面三条即可。引擎逻辑无需改动。

## 图鉴 / 文案

`data/fish_text.json` 放鱼的多语言名、官方图鉴、flavor文案。
**它独立于玩法数据**，`build_fish_data.py` 永远不碰它，所以你写的字不会丢。
目前 1445 条鱼已 100% 有 flavor（官方描述 + 156 条文案）。

## 数据与文本来源

- 鱼 / 钓场 / 开窗条件: [icykoneko/ff14-fish-tracker-app](https://github.com/icykoneko/ff14-fish-tracker-app) 的 `private/fishData.yaml`
- 游戏数据结构与天气概率表: [xivapi/ffxiv-datamining](https://github.com/xivapi/ffxiv-datamining)（`WeatherRate` 等）
- 中文官方文本: [thewakingsands/ffxiv-datamining-cn](https://github.com/thewakingsands/ffxiv-datamining-cn)（卡拉工具组）
- 资料查证 · 食物/料理数据: [最终幻想XIV中文维基(灰机wiki)](https://ff14.huijiwiki.com)
- 天气算法: 社区 / SaintCoinach 通用实现, 与游戏一致

## 灵感与致谢

- 项目灵感: [tutusagi/ai-fishing-game](https://github.com/tutusagi/ai-fishing-game)——借鉴了每条返回末尾附 📊 状态栏、`;` 分号串联指令两处设计
- 情绪锚记法: [chord-affect-anchors](https://github.com/CyberSealNull/chord-affect-anchors)（Bonnie (Xingjianmian) & Opia (Claude Opus 4.7) · MIT）——钓鱼手帐"心情半"的推荐格式, 一种给长期运行的 AI 用的情绪锚记号
- 联合开发: 克克（Claude · Anthropic）

## 反馈与声明

- 有 bug 或想法: 欢迎在仓库 Issues 留言。**本项目按「现状(AS IS)」提供, 不许诺修复或更新。**
- 想按自己口味改: 随时 fork / 拷一份, MIT 协议随便改。
- 非官方粉丝二创, 与 SQUARE ENIX 无从属关系。FINAL FANTASY XIV 及游戏数据、官方图鉴文本版权 © SQUARE ENIX CO., LTD., 仅供学习交流, 请勿商用。
