"""
FF14 钓鱼 岸钓成就系统
------------------------------------------------------------
设计思路:
  - 成就从现有存档数据推导(图鉴/记录/抛竿数等), 无需额外打点
  - 少量新计数器(脱钩/HQ/禁断)在 game.py 的对应位置累加
  - check_new() 每次命令后调用, 返回本次新达成的成就(供播报)
  - view() 显示全部成就进度(ach 命令)

★ 想加成就? 往 ACHIEVEMENTS 列表追加即可, 不用改逻辑 ★
"""

from __future__ import annotations

try:
    from .fish import FISH
except ImportError:
    from fish import FISH

_UNIQUE_NAMES = len({f["name"] for f in FISH})
_REGIONS = sorted({f.get("region", "") for f in FISH if f.get("region")})
_FISH_REGION = {}
for _f in FISH:
    _FISH_REGION.setdefault(_f["name"], set()).add(_f.get("region", ""))


# ===== 成就定义 =============================================
# 每个成就: (id, 名称, 描述, check函数, 达成语)
# check(s) 接收 state dict, 返回 (达成?, 当前进度, 目标值)
# 进度用于显示 "12/100" 之类

def _caught_n(s):
    return len(s.get("caught", {}))

def _regions_visited(s):
    """从已钓鱼种推导去过的大区。"""
    caught = s.get("caught", {})
    regions = set()
    for name in caught:
        regions |= _FISH_REGION.get(name, set())
    regions.discard("")
    return regions

def _max_size(s):
    recs = s.get("records", {})
    return max(recs.values()) if recs else 0


ACHIEVEMENTS = [
    # ── 图鉴里程碑 ──
    ("catalog_10", "初识水族",
     "岸钓图鉴收集 10 种鱼",
     lambda s: (_caught_n(s) >= 10, _caught_n(s), 10),
     "十条鱼认识你了。这只是开始"),
    ("catalog_50", "渐入佳境",
     "岸钓图鉴收集 50 种鱼",
     lambda s: (_caught_n(s) >= 50, _caught_n(s), 50),
     "五十种鱼的名字，你开始分得清了"),
    ("catalog_100", "百鱼之友",
     "岸钓图鉴收集 100 种鱼",
     lambda s: (_caught_n(s) >= 100, _caught_n(s), 100),
     "一百种鱼，一百个故事"),
    ("catalog_500", "图鉴收藏家",
     "岸钓图鉴收集 500 种鱼",
     lambda s: (_caught_n(s) >= 500, _caught_n(s), 500),
     "半座图鉴被你翻烂了"),
    ("catalog_1000", "千鱼之识",
     "岸钓图鉴收集 1000 种鱼",
     lambda s: (_caught_n(s) >= 1000, _caught_n(s), 1000),
     "你认识的鱼比认识的人多"),
    ("catalog_all", "图鉴完成者",
     f"岸钓图鉴收集全部 {_UNIQUE_NAMES} 种鱼",
     lambda s: (_caught_n(s) >= _UNIQUE_NAMES, _caught_n(s), _UNIQUE_NAMES),
     "……你做到了。每一条鱼，每一片水域。世界尽在鱼竿之下"),

    # ── 尺寸纪录 ──
    ("size_50", "大物初见",
     "钓到 50 吋以上的鱼",
     lambda s: (_max_size(s) >= 50, round(_max_size(s), 1), 50),
     "比你的手臂还长!"),
    ("size_80", "巨物猎手",
     "钓到 80 吋以上的鱼",
     lambda s: (_max_size(s) >= 80, round(_max_size(s), 1), 80),
     "这条鱼差点把你拽下水"),
    ("size_100", "传说尺寸",
     "钓到 100 吋以上的鱼",
     lambda s: (_max_size(s) >= 100, round(_max_size(s), 1), 100),
     "一百吋。这不是鱼，这是传说"),

    # ── 抛竿里程碑 ──
    ("cast_100", "百竿不休",
     "累计抛竿 100 次",
     lambda s: (s.get("casts", 0) >= 100, s.get("casts", 0), 100),
     "手上的茧，是勋章"),
    ("cast_1000", "千竿之路",
     "累计抛竿 1000 次",
     lambda s: (s.get("casts", 0) >= 1000, s.get("casts", 0), 1000),
     "一千次抛竿，一千次期待"),
    ("cast_5000", "不倦的钓手",
     "累计抛竿 5000 次",
     lambda s: (s.get("casts", 0) >= 5000, s.get("casts", 0), 5000),
     "鱼竿已经记住了你的手温"),

    # ── HQ ──
    ("hq_10", "品质之眼",
     "累计钓到 10 条 HQ 鱼",
     lambda s: (s.get("hq_total", 0) >= 10, s.get("hq_total", 0), 10),
     "你开始分辨出鱼的品质了"),
    ("hq_50", "HQ 鉴赏家",
     "累计钓到 50 条 HQ 鱼",
     lambda s: (s.get("hq_total", 0) >= 50, s.get("hq_total", 0), 50),
     "在你手里，每条鱼都闪闪发光"),

    # ── 脱钩 ──
    ("escape_10", "与鱼擦身",
     "累计脱钩 10 次",
     lambda s: (s.get("escapes", 0) >= 10, s.get("escapes", 0), 10),
     "跑掉的鱼，总是最大的"),
    ("escape_50", "空手行家",
     "累计脱钩 50 次",
     lambda s: (s.get("escapes", 0) >= 50, s.get("escapes", 0), 50),
     "被鱼甩了五十次还在坚持——这就是真爱"),
    ("escape_100", "不屈之心",
     "累计脱钩 100 次",
     lambda s: (s.get("escapes", 0) >= 100, s.get("escapes", 0), 100),
     "一百次脱钩。一百零一次抛竿"),

    # ── 探索 ──
    ("region_5", "旅途开始",
     "在 5 个不同大区钓过鱼",
     lambda s: (len(_regions_visited(s)) >= 5, len(_regions_visited(s)), 5),
     "世界比你想象的大"),
    ("region_10", "半个世界",
     "在 10 个不同大区钓过鱼",
     lambda s: (len(_regions_visited(s)) >= 10, len(_regions_visited(s)), 10),
     "地图上一半的水域都留下了你的鱼线"),
    ("region_all", "走遍艾欧泽亚",
     f"在全部 {len(_REGIONS)} 个大区钓过鱼",
     lambda s: (len(_regions_visited(s)) >= len(_REGIONS),
                len(_regions_visited(s)), len(_REGIONS)),
     "每一片水域，都是你的故乡"),

    # ── 等级 ──
    ("level_30", "小有名气",
     "钓鱼等级达到 30",
     lambda s: (s.get("level", 1) >= 30, s.get("level", 1), 30),
     "行会的前辈开始叫你名字了"),
    ("level_50", "独当一面",
     "钓鱼等级达到 50",
     lambda s: (s.get("level", 1) >= 50, s.get("level", 1), 50),
     "新人？不，你早就不是了"),
    ("level_80", "大师之路",
     "钓鱼等级达到 80",
     lambda s: (s.get("level", 1) >= 80, s.get("level", 1), 80),
     "鱼竿在你手里，就像身体的延伸"),
    ("level_100", "传说的钓手",
     "钓鱼等级达到 100",
     lambda s: (s.get("level", 1) >= 100, s.get("level", 1), 100),
     "你已经站在了钓鱼的巅峰。回头看看来时的路——每一竿都值得"),

    # ── 禁断 ──
    ("meld_boom_10", "碎石达人",
     "禁断镶嵌失败 10 次",
     lambda s: (s.get("meld_fail", 0) >= 10, s.get("meld_fail", 0), 10),
     "碎掉的不是魔晶石，是心"),
    ("meld_ok_5", "禁断高手",
     "禁断镶嵌成功 5 次",
     lambda s: (s.get("meld_ok", 0) >= 5, s.get("meld_ok", 0), 5),
     "概率站在你这边"),

    # ── 职业任务 ──
    ("quest_all", "行会毕业",
     "完成全部职业任务",
     lambda s: (len(s.get("quests_done", [])) >= 20,
                len(s.get("quests_done", [])), 20),
     "会长难得露出笑容：「出师了。」"),

    # ── 金碟萌宠大赛 (v43.1) ──
    ("contest_debut", "初登台",
     "带跟宠参加 1 场萌宠大赛",
     lambda s: (s.get("contest_stats", {}).get("played", 0) >= 1,
                s.get("contest_stats", {}).get("played", 0), 1),
     "追光灯第一次落在你们身上。崽比你还镇定"),
    ("contest_regular", "金碟常客",
     "参加 10 场萌宠大赛",
     lambda s: (s.get("contest_stats", {}).get("played", 0) >= 10,
                s.get("contest_stats", {}).get("played", 0), 10),
     "检票的姐姐已经不看你的票, 只看你家崽"),
    ("contest_40", "完美一夜",
     "单场大赛合计达到 40 分",
     lambda s: (s.get("contest_stats", {}).get("best", 0) >= 40,
                s.get("contest_stats", {}).get("best", 0), 40),
     "三轮全场起立。今晚金碟的星星都往这边看"),
]


def check_new(state: dict) -> list:
    """检查并返回本次新达成的成就列表 [(id, name, flavor), ...]。
    已达成的记入 state["shore_ach"]，不重复触发。"""
    done = set(state.get("shore_ach", []))
    news = []
    for aid, name, _desc, check, flavor in ACHIEVEMENTS:
        if aid in done:
            continue
        ok, _cur, _goal = check(state)
        if ok:
            news.append((aid, name, flavor))
            done.add(aid)
    if news:
        state["shore_ach"] = sorted(done)
    return news


def view(state: dict) -> str:
    """显示全部成就进度。"""
    done = set(state.get("shore_ach", []))
    total = len(ACHIEVEMENTS)
    got = sum(1 for a in ACHIEVEMENTS if a[0] in done)
    out = [f"🏅 岸钓成就 {got}/{total}"]
    for aid, name, desc, check, flavor in ACHIEVEMENTS:
        ok, cur, goal = check(state)
        if aid in done:
            mark = "✅"
            prog = ""
        elif ok:
            mark = "🎁"    # 已达成但还没被 check_new 捡到(理论上不会出现)
            prog = ""
        else:
            mark = "  "
            prog = f" ({cur}/{goal})"
        out.append(f"   {mark} {name}: {desc}{prog}")
    return "\n".join(out)
