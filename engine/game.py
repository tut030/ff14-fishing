"""
FF14 钓鱼 游戏主循环 (Step 4)
------------------------------------------------------------
单一入口 cmd("命令"), 发指令、回文字。给 AI 玩, 也能你自己玩。

命令:
  look            此刻这片钓场: 时间/天气/能钓的鱼
  cast            抛竿一次(在当前开窗的鱼里按稀有度抽)
  goto <钓场>     移动到某个钓场
  spots           列出可去的钓场
  bag             渔获/图鉴/点数
  status <鱼名>   某条鱼现在能不能钓, 下一个窗口几点
  save / load     存档 / 读档
  help            帮助

确定性: 抽鱼用 (存档种子 + 抛竿数) 播种, 同档同序列结果可复现。
开窗判定按真实时间/天气, 所以"你钓不到的鱼, AI 也钓不到"。
"""

from __future__ import annotations
import random
import zlib

from . import i18n as i18n_mod
import time

try:
    from .window import is_catchable, status_text, next_window
    from .weather import current_weather
    from .fish import FISH, get, get_all, time_text, _w
    from .time_kernel import eorzea_time
    from . import save as save_mod
    from . import gp as gp
    from . import leveling
    from . import gear
    from . import bait as bait_mod
    from . import ocean as ocean_mod
    from . import scrip as scrip_mod
    from . import equipment as eq_mod
    from . import materia as mat_mod
    from . import quests as quest_mod
    from . import atmosphere as atmo
    from . import tasks as tasks_mod
    from . import achievements as ach_mod
    from . import titles as title_mod
    from . import pets as pet_mod
    from . import food as food_mod
    from . import encounters as enc_mod
except ImportError:
    from window import is_catchable, status_text, next_window
    from weather import current_weather
    from fish import FISH, get, get_all, time_text, _w
    from time_kernel import eorzea_time
    import save as save_mod
    import gp as gp
    import leveling
    import gear
    import bait as bait_mod
    import ocean as ocean_mod
    import scrip as scrip_mod
    import equipment as eq_mod
    import materia as mat_mod
    import quests as quest_mod
    import tasks as tasks_mod
    import achievements as ach_mod
    import titles as title_mod
    import atmosphere as atmo
    import pets as pet_mod
    import food as food_mod
    import encounters as enc_mod

# tug(竿感) -> 抽取权重: 越稀有权重越低
_TUG_WEIGHT = {"Light": 100, "Medium": 40, "Heavy": 15, "Legendary": 3}
_SPOTS = sorted({f["location"] for f in FISH})
_UNIQUE_NAMES = len({f["name"] for f in FISH})   # 图鉴分母(同名鱼共享一条图鉴)
# 钓场中文名映射(data/spot_names.json, 由 tools/build_spot_names.py 生成)
import json as _json
import pathlib as _pathlib
try:
    _SPOT_CN = _json.loads(
        (_pathlib.Path(__file__).resolve().parent.parent / "data" /
         "spot_names.json").read_text(encoding="utf-8"))["names"]
except FileNotFoundError:
    _SPOT_CN = {}
_SPOT_EN_BY_CN = {cn: en for en, cn in _SPOT_CN.items()}
_ZONE_OF = {f["location"]: f["zone"] for f in FISH}
# 钓场等级(取该钓场任一鱼的等级; 同钓场共享)
_LOC_LEVEL = {}
for _f in FISH:
    if _f["location"] not in _LOC_LEVEL and _f.get("level"):
        _LOC_LEVEL[_f["location"]] = _f["level"]
# 钓点 -> 大区
_LOC_REGION = {f["location"]: f.get("region", "") for f in FISH}
# 区域/大区 最低 line 钓场等级(给无等级数据的叉鱼点定级代理)
_ZONE_LEVEL, _REGION_LEVEL = {}, {}
for _f in FISH:
    if _f["mode"] == "line" and _f.get("level"):
        _z, _r, _lv = _f["zone"], _f.get("region", ""), _f["level"]
        _ZONE_LEVEL[_z] = min(_ZONE_LEVEL.get(_z, 999), _lv)
        _REGION_LEVEL[_r] = min(_REGION_LEVEL.get(_r, 999), _lv)
# 大区 -> line 钓场等级区间(给图鉴书店标注)
_REGION_RANGE = {}
for _f in FISH:
    if _f["mode"] == "line" and _f.get("level"):
        _r, _lv = _f.get("region", ""), _f["level"]
        lo, hi = _REGION_RANGE.get(_r, (999, 0))
        _REGION_RANGE[_r] = (min(lo, _lv), max(hi, _lv))


def _spear_level(loc: str) -> int:
    """叉鱼点等级 = 同区最低 line 钓场等级(代理; 无则同大区; 再无则 1)。"""
    z = _ZONE_OF.get(loc)
    r = _LOC_REGION.get(loc, "")
    if z in _ZONE_LEVEL:
        return _ZONE_LEVEL[z]
    return _REGION_LEVEL.get(r, 1)


def _spot_req_level(loc: str) -> int:
    """该钓点(岸钓/叉鱼)需要的等级。"""
    if loc in _SPEAR_SPOTS:
        return _spear_level(loc)
    return _LOC_LEVEL.get(loc, 1)

# 图鉴书: 有 folklore 鱼的大区 -> 售价(按该区最低级鱼 *100)
_FOLKLORE_BOOKS = {}
for _f in FISH:
    if _f["folklore"] and _f["mode"] == "line" and _f.get("region"):
        _price = max(1000, (_f.get("level") or 1) * 100)
        _r = _f["region"]
        if _r not in _FOLKLORE_BOOKS or _price < _FOLKLORE_BOOKS[_r]:
            _FOLKLORE_BOOKS[_r] = _price


# 上钩提示(按竿感): 感叹号符号(用于批量汇总等简短场景)
_TUG_TELL = {
    "Light": ("!", "轻轻一点"),
    "Medium": ("!!", "有力一扯"),
    "Heavy": ("!!!", "沉重猛拽"),
    "Legendary": ("!!!", "天崩地裂般的巨力"),
}
# 尺寸范围(吋): 竿感越重、鱼影越大 -> 越大(咱数据无真实尺寸, 按稀有度生成)
_SIZE_TUG = {"Light": (3, 14), "Medium": (8, 28), "Heavy": (20, 55),
             "Legendary": (35, 110), None: (5, 20)}
_SIZE_GIG = {"Small": (4, 14), "Normal": (9, 26), "Large": (28, 75), "UNKNOWN": (8, 24)}
_HQ_CHANCE = 0.12          # 高品质(HQ)概率; HQ 卖价翻倍
# 抛竿氛围(40% 概率出现, 从 atmosphere 模块取)
_CAST_FLAVOR = atmo.CAST_FLAVOR
# 脱钩(空手而归)概率: 越稀有越容易跑; 普通鱼偶尔也脱钩。
# 想改成"一律固定概率"(选项②), 把下面几个值设成一样即可。
_ESCAPE = {"Light": 0.08, "Medium": 0.15, "Heavy": 0.25, "Legendary": 0.35}
_ESCAPE_DEFAULT = 0.10

# ── 捕鱼人之识(直感): 鱼王前置机制, 全量数据驱动(fish.json 的 predators) ──
INTUITION_CASTS = 8            # 直感持续竿数(跨钓场存活, 前置跨场也来得及赶路)
_PRED_KINGS = [f for f in FISH if f.get("predators")]
_PRED_SPECIES = {p for f in _PRED_KINGS for p in f["predators"]}

# ── 鱼袋(方案B): 渔获入袋, sell 卖出才有钱 ──────────────
BAG_BASE_SLOTS = 35        # 随身鱼袋 = 原作 140 格背包的"其中一页"(其余三页是装备杂物, 不模拟)
BAG_SADDLE_SLOTS = 70      # 陆行鸟鞍囊(原作真实数值; Lv15 职业任务交差解锁, 免费)
BAG_RETAINER_SLOTS = 175   # 雇员每位(原作真实数值; 雇员系统预留, 未开通)
SADDLE_QUEST_LV = 15       # 交差此等级职业任务 → 解锁鞍囊


def _bag_key(name: str, hq: bool) -> str:
    """袋内格子键: 一格 = 一种鱼 × 一档品质, 同格无限叠(原作一格999, 文字版叠满)。"""
    return f"{name}|HQ" if hq else name


def _bag_split(key: str):
    return (key[:-3], True) if key.endswith("|HQ") else (key, False)


def _unit_price(f: dict, hq: bool) -> int:
    """一条鱼的收购价: 叉鱼按鱼影大小, 岸钓按竿感稀有度; HQ 翻倍。"""
    if f.get("mode") == "spear":
        base = _GIG_GIL.get(_gig(f), 40)
    else:
        base = _gil(f)
    return base * 2 if hq else base


def _roll_details(rng, f, hq_chance=_HQ_CHANCE):
    """返回 (提示符, 描述, 尺寸吋, 是否HQ)。hq_chance 可由鱼竿鉴别力抬高。"""
    if f["mode"] == "spear":
        lo, hi = _SIZE_GIG.get(_gig(f), (8, 24))
        tell, descr = "", ""
    else:
        tug = f.get("tug")
        lo, hi = _SIZE_TUG.get(tug, (5, 20))
        tell, descr = _TUG_TELL.get(tug, ("!", "一点动静"))
    size = round(rng.uniform(lo, hi), 1)
    hq = rng.random() < hq_chance
    return tell, descr, size, hq


# 叉鱼点 + 鱼影大小(gig) -> 权重/gil/经验(叉鱼不锁等级、几乎无窗口)
_SPEAR_SPOTS = {f["location"] for f in FISH if f["mode"] == "spear"}
_GIG_WEIGHT = {"Small": 100, "Normal": 40, "UNKNOWN": 40, "Large": 12}
_GIG_GIL = {"Small": 20, "Normal": 50, "UNKNOWN": 40, "Large": 120}
_GIG_XP = {"Small": 8, "Normal": 15, "UNKNOWN": 12, "Large": 28}
_GIG_CN = {"Large": "大", "Normal": "中", "Small": "小", "UNKNOWN": "?"}

# 坐钩(Mooch)关系表: bait 字段第 2+ 个元素若是鱼名 = 坐钩步骤
# _MOOCH_BAIT_AT[钓场][饵鱼名] = [目标鱼dict, ...]
_FISH_NAMES = {f["name"] for f in FISH}
_MOOCH_BAIT_AT = {}
for _f in FISH:
    _bait = _f.get("bait", [])
    if len(_bait) >= 2:
        mooch_fish_name = _bait[-1]                  # 链最后一环 = 坐钩饵鱼
        if mooch_fish_name in _FISH_NAMES and mooch_fish_name not in bait_mod.BAITS:
            _MOOCH_BAIT_AT.setdefault(_f["location"], {}).setdefault(
                mooch_fish_name, []).append(_f)


def _mooch_targets(loc: str, fish_name: str) -> list:
    """在这个钓场, 用这条鱼坐钩能钓到什么。返回目标鱼列表(可能为空)。"""
    return _MOOCH_BAIT_AT.get(loc, {}).get(fish_name, [])


def _gig(f: dict) -> str:
    return f.get("gig") or "UNKNOWN"


def _base_bait(f: dict):
    if not f.get("bait"):
        return None
    b = f["bait"][0]
    return b[0] if isinstance(b, list) else b


def _bait_ok(f: dict, equipped) -> bool:
    """选项①: 杂鱼见饵就上; 买不到饵的特殊大鱼不卡; 其余大鱼要挂对饵。"""
    base = _base_bait(f)
    if base is None:                      # 杂鱼(无饵数据)
        return True
    if base not in bait_mod.BAITS:        # 特殊饵/以鱼作饵(买不到) -> 不卡
        return True
    return equipped == base               # 需挂对饵(没挂或挂错都不上)


# ── 岸钓随机偶遇事件(打破"跑步机感") ──────────────────
_SHORE_EVENTS = [
    # ── 路人互动(丰富版: 不同外观/职业/性格的NPC) ──
    ("🧑‍🌾 一位穿着七彩幻化铠甲的捕鱼人走过来: \"你的鱼竿不错。\"她递给你一个鱼饵就走了。", "bait_gift", 3),
    ("👩 一位没穿鞋的冒险者在你旁边坐下来。她什么都没说，就是看着海。过了一会儿她走了。", None, 0),
    ("👧 一位扎双马尾的采矿工路过，瞟了一眼你的鱼桶: \"哇，好多鱼!\"", None, 0),
    ("🧝 一位精灵族的织工蹲在你旁边看你钓鱼。看了五分钟之后: \"好想学。\"", "xp", 10),
    ("👩‍🍳 一位穿着白围裙的烹调师闻到了你的鱼: \"这条鱼如果烤一下的话……\"\"不行，这是我的图鉴鱼。\"", None, 0),
    ("🎀 一位穿着粉色洛丽塔裙的冒险者跑过来: \"你的宠物好可爱！！\"——你还没来得及回应她就跑了。", None, 0),
    ("🧓 一位年老的捕鱼人递过来一杯热茶: \"年轻人，钓鱼这事急不得。\"", "gp", 40),
    ("🐈 一位牵着卡巴兽散步的召唤师路过。卡巴兽看了你一眼，打了个哈欠。", None, 0),
    ("👩‍⚕️ 一位穿白袍的占星术士望了望天空: \"今天的星象……适合钓传说鱼。\"——她说完就走了，留你在原地犹豫要不要信。", None, 0),
    ("🛡 一位全身盔甲的骑士在你旁边金属哐当哐当地坐了下来: \"别笑,我也有钓鱼证的。\"", None, 0),
    ("💰 一位商人模样的人路过，扔下一句: \"那条鱼在市场上值不少。\"然后留下了几枚金币。", "gil", 60),
    ("🎵 一位吟游诗人坐在树下弹琴。旋律让鱼跳出了水面——然后又落回去了。", None, 0),
    ("🧒 两个小孩子跑过来看你钓鱼。\"姐姐好厉害!\"其中一个说。另一个偷偷摸了你的鱼桶。", "gil", -5),
    ("🎁 一位路过的冒险者打开背包翻了翻: \"这个你要吗?我用不上了。\"她留下了一些旧装备材料。", "gil", 40),
    ("🌂 一位撑着阳伞的贵妇人路过。她看了你一眼: \"在太阳底下钓鱼?你们冒险者真有活力。\"", None, 0),
    # ── 原有自然/动物事件 ──
    ("🐦 一只海鸥俯冲下来叼走了你的鱼饵! 它回头看了你一眼——好像在笑。", "bait_loss", 1),
    ("🧓 旁边的老钓友递过来一把鱼饵: \"年轻人，用这个试试。\"", "bait_gift", 5),
    ("🐱 一只野猫蹭到你脚边，盯着你的鱼桶看。你摸了摸它的头。", None, 0),
    ("🌊 一个巨浪打上来，你的鞋湿了。但水退了之后沙滩上多了一枚硬币。", "gil", 50),
    ("🐚 你在水边捡到一个漂亮的贝壳。没什么用——但很好看。", None, 0),
    ("🧒 一个小孩子跑过来: \"姐姐/哥哥好厉害!能教我钓鱼吗?\" 你演示了一下抛竿。", "xp", 15),
    ("🦀 一只螃蟹夹住了你的鱼线! 你花了好一会儿才把它解开。", None, 0),
    ("💫 你打了个盹——醒来发现鱼竿差点被拖走了!", None, 0),
    ("🎵 远处传来悠扬的笛声。不知道是谁在吹，但让人心情变好了。", "gp", 30),
    ("🍙 你从背包里翻出一个忘了吃的饭团。味道……还行。体力恢复了一点。", "gp", 20),
    ("🐕 一只不知道从哪来的狗叼着一条鱼放在你面前。——你确定这不是偷来的?", "gil", 30),
    ("🌈 天边出现了一道彩虹。好像什么好事要发生了。", None, 0),
    ("🎣 旁边的钓友突然大叫: \"上了上了上了!!!\" 然后……脱钩了。你默默移开了视线。", None, 0),
    ("🦅 一只鹰在头顶盘旋了好久，最后一个俯冲——叼走了水面上一条鱼。那本来是你的。", None, 0),
    ("💎 你的鱼线挂到了什么东西——拉上来一看，是个生锈的小盒子。里面有几枚旧币。", "gil", 80),
    ("🐢 一只海龟缓缓游过你的浮标。它看了你一眼，又缓缓游走了。仿佛在说:\"别急。\"", None, 0),
    ("📖 你在石缝里捡到了一本被水泡过的钓鱼日记。最后一页写着:\"明天一定能钓到的。\"", None, 0),
    ("🌸 一片花瓣飘落在你的浮标上。水面一瞬间变得很安静。", None, 0),
    ("👩‍🌾 一位路过的冒险者看见你在钓鱼: \"你运气真好，我上次在这蹲了三天都没钓到。\" 然后走了。", None, 0),
    ("🐟 水面突然跳出一条鱼——它跃过你的头顶, 溅了你一脸水, 然后消失了。", None, 0),
    ("🪨 你坐的石头上刻着字: \"某年某月某日，XXX在此钓到一条巨鱼。\" 下面还刻着一行小字: \"……然后脱钩了。\"", None, 0),
    ("🎒 你整理背包时发现了角落里的几枚金币——上次卖鱼的时候多找的。", "gil", 25),
    ("🌙 月光在水面上画了一条银色的线。你突然觉得，钓不钓到鱼其实没那么重要。", None, 0),
]
_EVENT_CHANCE = 0.08   # 每竿 8% 概率触发偶遇


def _roll_event(rng: random.Random, state: dict, now: float | None = None) -> str | None:
    """掷骰: 是否触发岸钓偶遇事件。返回事件文本(含效果)或 None。"""
    if rng.random() > _EVENT_CHANCE:
        return None
    text, etype, val = rng.choice(_SHORE_EVENTS)
    effect = ""
    if etype == "gil":
        state["gil"] = state.get("gil", 0) + val
        effect = f"  (+{val} gil)"
    elif etype == "xp":
        from engine import leveling
        leveling.add_xp(state, val)
        effect = f"  (+{val} xp)"
    elif etype == "gp":
        from engine import gp as gp_mod
        state["gp"] = min(state["gp"] + val, gp_mod.max_gp(state, now))
        effect = f"  (+{val} GP)"
    elif etype == "bait_gift":
        bt = state.get("bait")
        if bt:
            stock = state.setdefault("bait_stock", {})
            stock[bt] = stock.get(bt, 0) + val
            effect = f"  (+{val} {bait_mod.disp(bt)})"
    elif etype == "bait_loss":
        bt = state.get("bait")
        if bt:
            stock = state.setdefault("bait_stock", {})
            lost = min(val, stock.get(bt, 0))
            if lost > 0:
                stock[bt] = stock.get(bt, 0) - lost
                effect = f"  (-{lost} {bait_mod.disp(bt)})"
    return f"\n🎲 {text}{effect}"


def _recommend_bait(loc: str, here: list, equipped: str | None, spot_lv: int) -> str:
    """根据钓场鱼的 base_bait 统计, 推荐最适合的饵料。"""
    from collections import Counter
    bait_counts = Counter()
    for f in here:
        if f.get("mode") != "line":
            continue
        bb = _base_bait(f)
        if bb:
            bait_counts[bb] += 1
    if not bait_counts:
        return ""
    best_bait, best_count = bait_counts.most_common(1)[0]
    total = len([f for f in here if f.get("mode") == "line"])
    info = bait_mod.BAITS.get(best_bait, {})
    cn = info.get("cn", "")
    disp = f"{cn}/{best_bait}" if cn else best_bait
    price = info.get("price")
    price_str = f"({price}g)" if price else ""
    if equipped == best_bait:
        return f"你挂的 {disp} 就是此处最佳饵! 覆盖 {best_count}/{total} 种鱼"
    # 推荐第二名
    if len(bait_counts) > 1:
        second, s_count = bait_counts.most_common(2)[1]
        s_info = bait_mod.BAITS.get(second, {})
        s_cn = s_info.get("cn", "")
        s_disp = f"{s_cn}/{second}" if s_cn else second
        return (f"{disp}{price_str} 覆盖 {best_count}/{total} 种鱼"
                f"（次选: {s_disp} 覆盖 {s_count} 种）")
    return f"{disp}{price_str} 覆盖 {best_count}/{total} 种鱼"


def _weather_transition(old_w: str, new_w: str) -> str:
    """天气切换时的一句氛围描写。"""
    _TRANS = {
        ("晴朗", "多云"): "太阳躲进了云层，光线柔和了下来。",
        ("晴朗", "阴天"): "天色暗了下来，云层压得很低。",
        ("晴朗", "小雨"): "天空突然暗了——雨点落下来了。",
        ("晴朗", "暴雨"): "晴空一秒变脸——暴雨倾盆而下！",
        ("多云", "晴朗"): "云散了。阳光从缝隙里洒下来，水面亮了起来。",
        ("多云", "小雨"): "云层越积越厚——终于落了雨。",
        ("小雨", "晴朗"): "雨停了。空气里有泥土和青草的味道。",
        ("小雨", "暴雨"): "雨越来越大——从淅沥变成了倾盆！",
        ("暴雨", "晴朗"): "暴雨突然停了。阳光穿破云层，水面上冒着蒸汽。",
        ("暴雨", "多云"): "雨终于小了。天还阴着，但至少不用再被淋了。",
        ("暴雨", "小雨"): "暴风雨渐渐平息，变成了细细的小雨。",
        ("雷雨", "晴朗"): "最后一道闷雷滚过天边，然后——安静了。阳光回来了。",
        ("阴天", "晴朗"): "云层裂开一条缝，阳光倾泻下来。水面上的鱼鳞在闪光。",
        ("碧空", "晴朗"): "碧蓝的天空柔和了一些。还是好天气。",
        ("晴朗", "碧空"): "天空蓝得不像话。一朵云都没有。",
        ("薄雾", "晴朗"): "雾散了。眼前的钓场比你想象的开阔。",
        ("晴朗", "薄雾"): "一层薄雾从水面上升起来，浮标变得模糊了。",
    }
    specific = _TRANS.get((old_w, new_w))
    if specific:
        return f"🌤 {specific}"
    return f"🌤 天气变了——从{old_w}变成了{new_w}。"


def _avail(f: dict, fisheyes_active: bool, snagging_active: bool = False,
           books=()) -> bool:
    """当前机制下这条鱼是否可参与钓(不含时段/天气)。
    叉鱼: 机制待做, 暂锁。 folklore鱼: 需拥有该大区图鉴书。
    钓草鱼: 需开启 snagging。 鱼眼鱼: 需鱼眼 buff。"""
    if f["mode"] != "line":
        return False
    if f["folklore"] and f.get("region") not in books:
        return False
    if f["snagging"] and not snagging_active:
        return False
    if f["fishEyes"] and not fisheyes_active:
        return False
    return True


def _weight(f: dict) -> int:
    return _TUG_WEIGHT.get(f.get("tug"), 60)


def _gil(f: dict) -> int:
    """卖价: 基于稀有度(竿感) + 鱼等级浮动, 传说鱼值大钱, 新手鱼值零花钱。"""
    base = max(5, 1500 // _weight(f))          # 越稀有基础越高
    lv = f.get("level") or 1
    lv_mult = 0.5 + lv / 50                    # Lv1 → ×0.52, Lv50 → ×1.5, Lv90 → ×2.3
    return max(3, int(base * lv_mult))


def _disp(f: dict) -> str:
    cn = (f.get("names") or {}).get("cn")
    return f"{cn}/{f['name']}" if cn else f["name"]


_BUFF_CN = {"gathering": "获得力", "perception": "鉴别力", "gp": "GP", "xp": "经验"}

class Game:
    def __init__(self, slot: str = "default", fixed_time: float | None = None):
        self.slot = slot
        self.fixed_time = fixed_time
        self.state = save_mod.load(slot)
        self._migrate()
        # ── 欢迎回来: 首条命令时显示, 沉浸式开场 ──
        self._welcomed = False
        self._welcome_msg, self._rest_xp = self._make_welcome()

    def _make_welcome(self) -> tuple[str, int]:
        """预生成欢迎消息: 对比 last_seen 决定要不要触发。"""
        s = self.state
        now = self._now()
        last = s.get("last_seen", 0)
        first_time = (last == 0)
        elapsed = now - last if last else 0
        # 当前 ET 和天气
        et = eorzea_time(now)
        et_hour = et.hour if hasattr(et, 'hour') else int(str(et).split(":")[0])
        loc = s.get("location", "")
        zone = _ZONE_OF.get(loc, "")
        w = current_weather(zone, now) if zone else "碧空"
        # 等级差
        lv = s.get("level", 1)
        spot_lv = _spot_req_level(loc) if loc else 1
        diff = lv - spot_lv
        return atmo.generate_welcome(
            elapsed, et_hour, w, diff, lv, first_time, zone=zone)

    def _migrate(self):
        """补齐新版字段(旧存档自动迁移),__init__ 和 load_cmd 都走这里。"""
        s = self.state
        s.setdefault("seed", random.randint(1, 10**9))
        s.setdefault("gp", gp.GP_MAX)
        s.setdefault("gp_at", self._now())
        s.setdefault("cordial_at", 0)
        s.setdefault("level", 1)
        s.setdefault("xp", 0)
        s.setdefault("snagging", False)
        s.setdefault("books", [])
        s.setdefault("records", {})
        s.setdefault("rod", None)
        s.setdefault("rods_owned", [])
        s.setdefault("bait", None)
        s.setdefault("bait_stock", {})
        s.setdefault("ocean", None)
        s.setdefault("ocean_caught", {})
        s.setdefault("ocean_trips", 0)
        s.setdefault("ocean_points_total", 0)
        s.setdefault("ocean_slot_used", 0)
        s.setdefault("scrip_white", 0)
        s.setdefault("scrip_purple", 0)
        s.setdefault("collector", False)
        s.setdefault("collectables", [])
        s.setdefault("equip", {})            # 11部位穿戴 {槽: 装备id}
        s.setdefault("equip_owned", [])      # 拥有的装备id列表
        s.setdefault("materia_shards", 0)    # 魔晶石碎片(回收分解产出)
        s.setdefault("materia_inv", {})      # 魔晶石库存 {id: 数量}
        s.setdefault("melds", {})            # 镶嵌记录 {装备id: [魔晶石id...]}
        s.setdefault("quests_done", [])      # 已完成的职业任务等级
        s.setdefault("tasks", {})            # 每日/每周任务(周期滚动区)
        s.setdefault("shore_ach", [])        # 岸钓成就(已达成id列表)
        s.setdefault("escapes", 0)           # 累计脱钩次数(成就用)
        s.setdefault("hq_total", 0)          # 累计HQ钓获数(成就用)
        s.setdefault("meld_ok", 0)           # 禁断成功次数(成就用)
        s.setdefault("meld_fail", 0)         # 禁断失败次数(成就用)
        s.setdefault("mooch_pending", None)  # 待坐钩鱼名(钓到后下一命令前有效)
        s.setdefault("titles", [])           # 已解锁称号列表
        s.setdefault("active_title", None)   # 当前佩戴的称号
        # 旧存档若是 baits_owned 列表, 转成库存(每种给 20)
        if isinstance(s.get("baits_owned"), list) and not s["bait_stock"]:
            s["bait_stock"] = {b: 20 for b in s.pop("baits_owned")}

    def _now(self) -> float:
        return self.fixed_time if self.fixed_time is not None else time.time()

    def _autosave(self):
        return save_mod.save(self.state, self.slot)

    # --- 命令 ---------------------------------------------
    # ── 鱼袋(方案B) ──────────────────────────────
    def _bag_cap(self) -> int:
        """鱼袋总格数 = 随身 + 鞍囊(Lv15任务解锁) + 雇员(预留)。"""
        cap = BAG_BASE_SLOTS
        if SADDLE_QUEST_LV in self.state.get("quests_done", []):
            cap += BAG_SADDLE_SLOTS
        cap += BAG_RETAINER_SLOTS * len(self.state.get("retainers", []))
        return cap

    def _bag_add(self, name: str, hq: bool) -> bool:
        """渔获入袋。同种同品质叠放不占新格; 需新格且袋满 → False(只能放生)。"""
        bag = self.state.setdefault("fish_bag", {})
        key = _bag_key(name, hq)
        if key not in bag and len(bag) >= self._bag_cap():
            return False
        bag[key] = bag.get(key, 0) + 1
        return True

    def _bag_take(self, name: str) -> bool:
        """从袋中取出一条(做菜/坐钩活饵用), NQ 优先。"""
        bag = self.state.get("fish_bag", {})
        for key in (_bag_key(name, False), _bag_key(name, True)):
            if bag.get(key, 0) > 0:
                bag[key] -= 1
                if bag[key] <= 0:
                    bag.pop(key, None)
                return True
        return False

    def _bag_view(self, short: bool = False) -> str:
        bag = self.state.get("fish_bag", {})
        cap = self._bag_cap()
        if SADDLE_QUEST_LV in self.state.get("quests_done", []):
            note = "已含鞍囊"
        else:
            note = f"Lv{SADDLE_QUEST_LV}职业任务交差解锁鞍囊+{BAG_SADDLE_SLOTS}格"
        head = f"   —— 🎒鱼袋 {len(bag)}/{cap} 格（{note}）——"
        if not bag:
            return head + "\n   （空空如也, cast 去钓）"
        lines = [head]
        total = 0
        keys = sorted(bag)
        show = keys[:10] if short else keys
        for key in show:
            nm, hq = _bag_split(key)
            f = get(nm)
            p = _unit_price(f, hq) if f else 3
            total += p * bag[key]
            disp = _disp(f) if f else nm
            lines.append(f"   {disp}{' ✨HQ' if hq else ''} ×{bag[key]}（{p}g/条）")
        if short and len(keys) > 10:
            hidden = keys[10:]
            for key in hidden:
                nm, hq = _bag_split(key)
                f = get(nm)
                total += (_unit_price(f, hq) if f else 3) * bag[key]
            lines.append(f"   …还有 {len(hidden)} 格(bag 看全部)")
        lines.append(f"   估价合计 {total}g —— sell <鱼名>/all/light 卖出")
        return "\n".join(lines)

    def _intuition_on_catch(self, name: str) -> str:
        """渔获计入直感前置进度; 任一鱼王前置集齐 → 触发捕鱼人之识。"""
        if name not in _PRED_SPECIES:
            return ""
        prog = self.state.setdefault("intuition_progress", {})
        prog[name] = prog.get(name, 0) + 1
        for k in _PRED_KINGS:
            req = k["predators"]
            if all(prog.get(pn, 0) >= c for pn, c in req.items()):
                for pn, c in req.items():
                    prog[pn] = prog.get(pn, 0) - c
                    if prog[pn] <= 0:
                        prog.pop(pn, None)
                self.state["intuition_casts"] = INTUITION_CASTS
                return (f"\n⚡ 捕鱼人之识! 水面之下, 有什么正注视着你……"
                        f"(持续 {INTUITION_CASTS} 竿, 换场赶路也不清除)")
        return ""

    def sell(self, arg: str = "") -> str:
        """卖鱼: sell <鱼名> [N|all] / sell all / sell light(只卖轻杆杂鱼)。"""
        bag = self.state.setdefault("fish_bag", {})
        a = arg.strip()
        if not bag:
            return "🎒 鱼袋是空的——先钓几条再来。"

        def _sold(items):
            total = 0
            lines = []
            for key, n in items:
                nm, hq = _bag_split(key)
                f = get(nm)
                p = _unit_price(f, hq) if f else 3
                total += p * n
                disp = _disp(f) if f else nm
                lines.append(f"   {disp}{' ✨HQ' if hq else ''} ×{n} → +{p * n}g")
                bag[key] -= n
                if bag[key] <= 0:
                    bag.pop(key, None)
            self.state["gil"] += total
            import datetime as _dt
            _td = _dt.datetime.fromtimestamp(self._now()).strftime("%Y-%m-%d")
            _dl = self.state.setdefault("diary_log", {}).setdefault(_td,
                  {"casts": 0, "caught": 0, "new_fish": [], "spots": [], "gil": 0, "xp": 0})
            _dl["gil"] += total
            return lines, total

        low = a.lower()
        if low in ("all", "全部", "全卖"):
            lines, total = _sold(sorted(bag.items()))
            self._autosave()
            return "💰 清仓!\n" + "\n".join(lines) + f"\n   合计 +{total} gil, 鱼袋清空。"
        if low in ("light", "杂鱼", "轻杆"):
            items = [(k, n) for k, n in sorted(bag.items())
                     if (lambda ff: ff and ff.get("mode") != "spear"
                         and ff.get("tug", "Light") == "Light")(get(_bag_split(k)[0]))]
            if not items:
                return "🎒 袋里没有轻杆[!]杂鱼。sell all 可全卖。"
            lines, total = _sold(items)
            self._autosave()
            return "💰 清掉杂鱼!\n" + "\n".join(lines) + f"\n   合计 +{total} gil。"
        if not a:
            return ("用法: sell <鱼名> [数量|all] / sell all(全卖) / sell light(只卖[!]杂鱼)\n"
                    + self._bag_view(short=True))
        parts = a.rsplit(maxsplit=1)
        qty = None
        fname_arg = a
        if len(parts) == 2:
            tail = parts[1].lower()
            if tail.isdecimal():
                fname_arg, qty = parts[0], int(parts[1])
            elif tail in ("all", "全部"):
                fname_arg = parts[0]
        if qty is not None and qty < 1:
            return "数量得是正整数哦。"
        f = get(fname_arg)
        if not f:
            return f"不认识这种鱼: {fname_arg}（中英文都认; status 可先查）"
        name = f["name"]
        order = [_bag_key(name, False), _bag_key(name, True)]   # NQ 先卖, HQ 留后
        have = sum(bag.get(k, 0) for k in order)
        if not have:
            return f"🎒 袋里没有 {_disp(f)}。(bag 看库存)"
        want = have if qty is None else min(qty, have)
        items = []
        left = want
        for k in order:
            n = min(left, bag.get(k, 0))
            if n:
                items.append((k, n))
                left -= n
        lines, total = _sold(items)
        self._autosave()
        note = f"（袋中还剩 {have - want} 条）" if want < have else ""
        return f"💰 卖出 {_disp(f)} ×{want}{note}\n" + "\n".join(lines) + f"\n   合计 +{total} gil"

    _HOOKSET_CATCH = {   # (手法, 竿感) -> 上鱼率(甲+判定表)
        ("precision", "Light"): 1.0, ("precision", "Medium"): 0.30,
        ("precision", "Heavy"): 0.15, ("precision", "Legendary"): 0.05,
        ("powerful", "Light"): 0.40, ("powerful", "Medium"): 1.0,
        ("powerful", "Heavy"): 1.0, ("powerful", "Legendary"): 0.88,
    }

    def resolve_hook(self, kind: str) -> str:
        """提钩窗口结算: hook(硬拉·免费) / precision / powerful(各50GP)。"""
        pend = self.state.get("hook_pending")
        if not pend:
            return "现在没有咬钩的鱼——precision/powerful 只在提钩窗口用。cast 抛竿去~"
        f = get(pend["name"])
        tug = f.get("tug", "Light")
        if kind in ("precision", "powerful"):
            cn = {"precision": "精准提钩", "powerful": "强力提钩"}[kind]
            if self.state["gp"] < gp.HOOKSET_COST:
                return (f"GP 不够（{cn}需 {gp.HOOKSET_COST}，现有 {self.state['gp']}）——"
                        f"鱼还咬着! cordial 喝药, 或 hook 硬拉赌一把。")
            self.state["gp"] -= gp.HOOKSET_COST
            rate = self._HOOKSET_CATCH[(kind, tug)]
        else:
            rate = 0.40 if pend.get("patience") else 1 - _ESCAPE.get(tug, _ESCAPE_DEFAULT)
        self.state["hook_pending"] = None
        rng = random.Random(self.state["seed"] * 7654321 + pend["cast_no"])
        if rng.random() > rate:
            self.state["escapes"] = self.state.get("escapes", 0) + 1
            self._autosave()
            fail = {"precision": "🎯 手腕一抖——力道却全然不对! 线一松, 水底只剩一圈嘲弄的涟漪。",
                    "powerful": "💪 猛地扬竿——用力过猛! 空钩飞出水面, 鱼影早已不见。",
                    "hook": "🎣 你咬牙硬拉——线绷得吱呀作响, 啪! 脱钩了。"}[kind]
            return fail + "\n   （竿感和手法要对路: [!]配精准, [!!]/[!!!]配强力）"
        hqc = (gear.hq_chance_from(pend.get("perception", 0))
               * (2.0 if pend.get("chum") else 1.0)
               * (3.0 if pend.get("patience") else 1.0))
        tell, descr, size, hq = _roll_details(rng, f, hqc)
        r = self._land_fish(f, hq, size, rng, now=self._now(),
                            used=pend.get("used", []), wait=pend.get("wait", 0),
                            tell=tell, descr=descr, bait_out=pend.get("bait_out"),
                            bait_name=pend.get("bait_name"), hookset=kind)
        self._autosave()
        return self._fmt_cast(r)

    def rescue_cmd(self) -> str:
        """存档救援: 回滚到上一份自动备份(.bak)。"""
        if not save_mod.restore_backup(self.slot):
            return "🛟 没有找到备份档——存过两次档之后才会有 .bak 备份。"
        self.state = save_mod.load(self.slot)
        return "🛟 已从自动备份回档!（当前进度被备份内容覆盖; bag/look 核对一下）"

    def look(self) -> str:
        now = self._now()
        loc = self.state["location"]
        zone = _ZONE_OF.get(loc)
        w = current_weather(zone, now) if zone else "?"
        lv = self.state.get("level", 1)
        # 叉鱼点
        if loc in _SPEAR_SPOTS:
            allsp = [f for f in FISH if f["location"] == loc and f["mode"] == "spear"]
            spf = [f for f in allsp if is_catchable(f, now)]
            out = [f"📍 {loc}（{zone}·🔱叉鱼点）  游戏 {eorzea_time(now)}  天气 {w}",
                   f"   你 Lv{lv}   水下 {len(allsp)} 种，此刻可叉 {len(spf)} 种（用 spear）："]
            if spf:
                for f in spf:
                    out.append(f"     🔱[{_GIG_CN.get(_gig(f), '?')}影] {_disp(f)}")
            else:
                out.append("     （此刻水里没有可叉的鱼）")
            return "\n".join(out)
        # 普通钓场
        fe = self.state.get("buff_fisheyes", False)
        sn = self.state.get("snagging", False)
        bk = self.state.get("books", [])
        bt = self.state.get("bait")
        nbait = self.state.get("bait_stock", {}).get(bt, 0)
        eff = bt if (bt and nbait > 0) else None
        here = [f for f in FISH if f["location"] == loc]
        openf = [f for f in here if _avail(f, fe, sn, bk) and _bait_ok(f, eff)
                 and is_catchable(f, now)]
        spot_lv = _LOC_LEVEL.get(loc, 1)
        lock = "" if lv >= spot_lv else f"  🔒需 Lv{spot_lv}"
        sntag = "  🪝钓草:开" if sn else ""
        baittag = f"  🪱{bait_mod.disp(bt)}×{nbait}" if eff else "  🪱无饵"
        buffs = []
        if self.state.get("patience_casts", 0) > 0:
            buffs.append(f"🧘耐心(剩{self.state['patience_casts']}竿)")
        if self.state.get("intuition_casts", 0) > 0:
            buffs.append(f"⚡直感(剩{self.state['intuition_casts']}竿)")
        if self.state.get("buff_fisheyes"):
            buffs.append("👁鱼眼")
        if self.state.get("buff_chum"):
            buffs.append("🐟撒饵")
        if self.state.get("buff_prize"):
            buffs.append("🐟大鱼确保")
        if self.state.get("buff_identical"):
            buffs.append("🎯专一")
        if self.state.get("buff_slap"):
            buffs.append("👋拍击")
        if self.state.get("buff_dh"):
            buffs.append(f"🪝×{self.state['buff_dh']}")
        bufftag = ("  待生效:" + "".join(buffs)) if buffs else ""
        caught = set(self.state.get("caught", {}).keys())
        here_caught = sum(1 for f in here if f["name"] in caught)
        out = [f"📍 {loc}（{zone}·Lv{spot_lv}）{lock}{sntag}{baittag}{bufftag}  游戏 {eorzea_time(now)}  天气 {w}",
               f"   你 Lv{lv}  XP {self.state.get('xp', 0)}/{leveling.xp_to_next(lv)}"
               f"   GP {self.state['gp']}/{gp.max_gp(self.state, self._now())}"
               f" {gp.bar(self.state['gp'], gp.max_gp(self.state, self._now()))}",
               f"   此处 {len(here)} 种鱼，已钓 {here_caught} 种，此刻可钓 {len(openf)} 种："]
        if openf:
            for f in openf:
                tug = f.get("tug")
                tag = {"Light": "!", "Medium": "!!", "Heavy": "!!!", "Legendary": "!!!!"}
                tug_disp = f"[{tag.get(tug, '?')}]" if tug else ""
                mooch = "🐟" if _mooch_targets(loc, f["name"]) else ""
                caught_mark = "" if f["name"] in caught else " ✨新"
                intu = ("" if not f.get("predators")
                        else ("⚡" if self.state.get("intuition_casts", 0) > 0 else "⚡🔒"))
                out.append(f"     ✅ {_disp(f)} {tug_disp}{intu}{mooch}{caught_mark}")
        else:
            out.append("     （此刻无鱼咬钩，换时间/钓场，或看 status <鱼名>）")
        # 未钓到的鱼(关窗的): 标注原因
        uncaught_closed = [f for f in here if f["name"] not in caught
                           and f not in openf and f.get("mode") == "line"]
        if uncaught_closed:
            out.append(f"   ❌ 还差 {len(uncaught_closed)} 种(此刻关窗)：")
            for f in uncaught_closed[:6]:
                reasons = []
                if f.get("predators") and self.state.get("intuition_casts", 0) <= 0:
                    reasons.append("⚡需直感(status 查前置)")
                if not _avail(f, fe, sn, bk):
                    if f.get("folklore"):
                        reasons.append("需图鉴书")
                    if f.get("snagging") and not sn:
                        reasons.append("需钓草")
                elif not is_catchable(f, now):
                    ws = f.get("weatherSet")
                    ts = f.get("startHour") is not None
                    if ws:
                        reasons.append(f"天气:{'/'.join(ws[:2])}")
                    if ts:
                        reasons.append(f"时段:ET {f.get('startHour')}–{f.get('endHour')}")
                if not _bait_ok(f, eff) and not reasons:
                    bb = _base_bait(f)
                    reasons.append(f"需饵:{bb}" if bb else "坐钩鱼")
                if _base_bait(f) and _base_bait(f) != (eff or ""):
                    bname = _base_bait(f)
                    if bname and "需饵" not in str(reasons):
                        pass  # 已在 _bait_ok 判断里
                reason_str = "(" + "、".join(reasons) + ")" if reasons else ""
                out.append(f"     ❌ {_disp(f)} {reason_str}")
            if len(uncaught_closed) > 6:
                out.append(f"     …还有 {len(uncaught_closed) - 6} 种(status <鱼名> 查详情)")
        # 饵料推荐
        bait_rec = _recommend_bait(loc, here, eff, spot_lv)
        if bait_rec:
            out.append(f"   🪱 饵料建议: {bait_rec}")
        return "\n".join(out)

    def _cast_once(self, now):
        """钓一竿的核心, 返回结果 dict(不做格式化, 供单竿/批量共用)。"""
        loc = self.state["location"]
        lv = self.state.get("level", 1)
        fe = self.state.get("buff_fisheyes", False)
        sn = self.state.get("snagging", False)
        bk = self.state.get("books", [])
        bt = self.state.get("bait")
        stock = self.state.get("bait_stock", {})
        eff_bait = bt if (bt and stock.get(bt, 0) > 0) else None    # 有效饵=挂着且有库存
        intuit = self.state.get("intuition_casts", 0) > 0
        pool = [f for f in FISH if f["location"] == loc and _avail(f, fe, sn, bk)
                and _bait_ok(f, eff_bait)
                and is_catchable(f, now, ignore_time=(fe and f.get("tug") != "Legendary"))
                and (not f.get("predators") or intuit)
                and f["name"] != self.state.get("buff_slap")]
        self.state["casts"] += 1
        # 耐心(甲+): 计竿制, 抛竿即耗(空军/脱钩也算, 对应原作按时长烧)
        pat = self.state.get("patience_casts", 0) > 0
        if pat:
            self.state["patience_casts"] -= 1
        if intuit:
            self.state["intuition_casts"] -= 1
        # 日志: 记录今日抛竿数
        import datetime as _dt
        _td2 = _dt.datetime.fromtimestamp(now).strftime("%Y-%m-%d")
        _dl2 = self.state.setdefault("diary_log", {}).setdefault(_td2,
               {"casts": 0, "caught": 0, "new_fish": [], "spots": [], "gil": 0, "xp": 0})
        _dl2["casts"] += 1
        if not pool:
            reasons = set()
            for b in [f for f in FISH if f["location"] == loc
                      and is_catchable(f, now) and not (_avail(f, fe, sn, bk) and _bait_ok(f, eff_bait))]:
                if not _avail(b, fe, sn, bk):
                    if b["mode"] == "spear":
                        reasons.add("叉鱼(用 spear 命令)")
                    elif b["folklore"]:
                        reasons.add(f"图鉴书《{b.get('region')}》")
                    elif b["snagging"] and not sn:
                        reasons.add("钓草(可开 snagging)")
                    elif b["fishEyes"]:
                        reasons.add("鱼眼(可用 fisheyes)")
                elif not _bait_ok(b, eff_bait):
                    if bt and stock.get(bt, 0) <= 0:
                        reasons.add(f"补货鱼饵({bait_mod.disp(bt)}用完了, buybait)")
                    else:
                        reasons.add("挂对鱼饵(baits/buybait, 见 status)")
            if not intuit and any(x.get("predators") and is_catchable(x, now)
                                  for x in FISH if x["location"] == loc):
                reasons.add("⚡捕鱼人之识(鱼王开窗但前置未集齐, status <鱼名> 查)")
            return {"status": "empty", "reasons": reasons}
        totals = eq_mod.stats_total(self.state)   # 全身三维(空主手回退旧竿)
        # ── 食物 buff 加成(绝对值, 叠加到装备属性上) ──
        _fb = food_mod.get_active_buff(self.state, now)
        if _fb:
            for _fk, _ck in (("gathering", "获得力"), ("perception", "鉴别力"), ("gp", "采集力")):
                if _fk in _fb:
                    totals[_ck] = totals.get(_ck, 0) + _fb[_fk]
        # ── 大鱼确保(岸钓 Prize Catch): 只保留 Heavy/Legendary ──
        if self.state.get("buff_prize"):
            heavy_pool = [x for x in pool if x.get("tug") in ("Heavy", "Legendary")]
            if heavy_pool:
                pool = heavy_pool               # 有大鱼就只抽大鱼
            # 即使没有大鱼, buff 也消耗(真实规则: 没大鱼就浪费了)
        if pat:
            weights = [max(1, 300 // _weight(x)) for x in pool]
        else:
            weights = [_weight(x) for x in pool]
        if totals.get("获得力"):
            boost = 1 + totals["获得力"] * gear.GATHERING_RARE
            weights = [w * boost if _weight(x) <= 15 else w for x, w in zip(pool, weights)]
        # ── 鱼饵等级惩罚: 低级饵在高级钓场 → 大概率空竿 ──
        spot_lv = _LOC_LEVEL.get(loc, 1)
        bait_pen = bait_mod.bait_penalty(eff_bait, spot_lv)
        bait_hint = ""
        if bait_pen < 0.5:
            bait_hint = ("🪱 这里的鱼似乎对你的饵不太感兴趣……"
                         "试试更高级的饵？(baits 看饵店)")
        rng = random.Random(self.state["seed"] * 1000003 + self.state["casts"])
        # 低级饵空竿判定: penalty=0.05 时 95% 概率什么都不咬
        if bait_pen < 1.0 and rng.random() > bait_pen:
            return {"status": "empty", "reasons": set(),
                    "bait_hint": bait_hint}
        ident = self.state.get("buff_identical")
        _tgt = next((x for x in pool if x["name"] == ident), None) if ident else None
        f = _tgt if _tgt else rng.choices(pool, weights=weights, k=1)[0]
        bait_out = False
        if eff_bait:                      # 咬钩即损耗 1 个鱼饵
            stock[eff_bait] = stock.get(eff_bait, 0) - 1
            if stock[eff_bait] <= 0:
                stock.pop(eff_bait, None)
                bait_out = True
        wait = rng.randint(2, 28)
        # ── 提钩窗口(甲+): 耐心期间每次咬钩 / 鱼王咬钩(比赛除外) → 必须亲手提钩 ──
        tug_w = f.get("tug", "Light")
        if (pat or tug_w == "Legendary") and not self.state.get("tournament"):
            usedw = []
            if pat:
                usedw.append("耐心")
            if self.state.pop("buff_fisheyes", False):
                usedw.append("鱼眼")
            if self.state.pop("buff_prize", False):
                usedw.append("大鱼确保")
            chum_w = bool(self.state.pop("buff_chum", False))
            if chum_w:
                usedw.append("撒饵")
            t_w = _TUG_TELL.get(tug_w, ("!", "一点动静"))
            self.state["hook_pending"] = {
                "name": f["name"], "cast_no": self.state["casts"],
                "patience": pat, "wait": wait, "used": usedw, "chum": chum_w,
                "perception": totals.get("鉴别力", 0),
                "bait_out": bait_out, "bait_name": eff_bait}
            return {"status": "hook_window", "fish": f, "wait": wait,
                    "tell": t_w[0], "descr": t_w[1], "patience": pat,
                    "bait_out": bait_out, "bait_name": eff_bait,
                    "bait_hint": bait_hint}
        # 脱钩判定: 越稀有越容易跑。脱钩不消耗 buff(耐心/鱼眼保留到下一竿)、不计渔获。
        if rng.random() < _ESCAPE.get(f.get("tug"), _ESCAPE_DEFAULT):
            self.state["escapes"] = self.state.get("escapes", 0) + 1
            t = _TUG_TELL.get(f.get("tug"), ("!", "一点动静"))
            return {"status": "escaped", "fish": f, "wait": wait, "tell": t[0],
                    "descr": t[1], "bait_out": bait_out, "bait_name": eff_bait,
                    "bait_hint": bait_hint}
        tell, descr, size, hq = _roll_details(
            rng, f, gear.hq_chance_from(totals.get("鉴别力", 0))
            * (2.0 if self.state.get("buff_chum") else 1.0)     # 撒饵: HQ 概率翻倍
            * (3.0 if pat else 1.0))                            # 耐心: HQ 概率×3
        used = []
        if pat:
            used.append("耐心")
        if self.state.pop("buff_fisheyes", False):
            used.append("鱼眼")
        if self.state.pop("buff_prize", False):
            used.append("大鱼确保")
        if self.state.pop("buff_chum", False):
            used.append("撒饵")
        return self._land_fish(f, hq, size, rng, now=now, used=used,
                               wait=wait, tell=tell, descr=descr,
                               bait_out=bait_out, bait_name=eff_bait,
                               bait_hint=bait_hint)

    def _land_fish(self, f, hq, size, rng, *, now, used, wait, tell, descr,
                   bait_out=False, bait_name=None, bait_hint="", hookset=None):
        """渔获落地全流程(入袋/图鉴/收藏品/经验/纪录/日志/称号/坐钩检测)。
        _cast_once 与 resolve_hook(提钩窗口) 共用。"""
        lv = self.state.get("level", 1)
        loc = self.state["location"]
        name = f["name"]
        # ── 鱼袋(方案B): 收藏品模式走收藏品袋; 普通渔获需袋中有位, 满袋=白钓一竿 ──
        if not self.state.get("collector") and not self._bag_add(name, hq):
            return {"status": "bag_full", "fish": f, "name": name, "hq": hq,
                    "size": size, "wait": wait, "tell": tell, "descr": descr,
                    "used": used, "bait_out": bait_out, "bait_name": bait_name,
                    "bait_hint": bait_hint, "hookset": hookset}
        self.state["caught"][name] = self.state["caught"].get(name, 0) + 1
        first = self.state["caught"][name] == 1
        intuition_note = self._intuition_on_catch(name)
        # ── 双重/三重提钩: 一竿多条(袋子不够放多少算多少) ──
        extra_n = 0
        _dhn = self.state.pop("buff_dh", 0)
        if _dhn and not self.state.get("collector"):
            for _ in range(_dhn - 1):
                if self._bag_add(name, hq):
                    extra_n += 1
                    self.state["caught"][name] += 1
                    intuition_note = intuition_note or self._intuition_on_catch(name)
        # 拍击水面/专一垂钓: 真正钓起一条鱼后失效(原作规则)
        self.state.pop("buff_slap", None)
        self.state.pop("buff_identical", None)
        self.state["last_catch"] = name
        # 收藏品模式: 判收藏价值, 达标进背包换票, 不达标/背包满只能放生(不给gil)
        collect = None                        # None=普通 / dict=收藏结果
        g = 0
        if self.state.get("collector"):
            _per = eq_mod.stats_total(self.state).get("鉴别力", 0)
            _fbp = food_mod.get_active_buff(self.state, now)
            if _fbp and "perception" in _fbp:
                _per += _fbp["perception"]
            val = scrip_mod.roll_value(rng, f, hq, _per)
            inv = self.state.setdefault("collectables", [])
            if val < scrip_mod.COLLECT_MIN:
                collect = {"ok": False, "value": val, "why": "价值不足"}
            elif len(inv) >= scrip_mod.COLLECT_CAP:
                collect = {"ok": False, "value": val, "why": "背包已满"}
            else:
                kind = scrip_mod.scrip_kind(f)
                inv.append({"name": name, "value": val, "kind": kind})
                collect = {"ok": True, "value": val, "kind": kind, "n": len(inv)}
        # （方案B: 渔获已入袋, gil 在 sell 卖出时才结算）
        xp = int(leveling.xp_gain(f.get("level"), lv) * food_mod.xp_multiplier(self.state, now))
        gained = leveling.add_xp(self.state, xp)
        prev = self.state.setdefault("records", {}).get(name, 0)
        rec = size > prev
        recdiff = round(prev - size, 1) if (prev and not rec) else 0.0
        if rec:
            self.state["records"][name] = size
        flav = _CAST_FLAVOR[rng.randrange(len(_CAST_FLAVOR))] if rng.random() < 0.4 else None
        tasks_mod.record(self.state, now, "catch", 1, region=f.get("region"))
        # 日志: 钓获/经验/新图鉴(卖钱记在 sell 时)
        import datetime as _dt
        _td = _dt.datetime.fromtimestamp(now).strftime("%Y-%m-%d")
        _dl = self.state.setdefault("diary_log", {}).setdefault(_td,
              {"casts": 0, "caught": 0, "new_fish": [], "spots": [], "gil": 0, "xp": 0})
        _dl["caught"] += 1
        _dl["xp"] += xp
        if first and name not in _dl["new_fish"]:
            _dl["new_fish"].append(name)
        if hq:
            tasks_mod.record(self.state, now, "hq", 1)
            self.state["hq_total"] = self.state.get("hq_total", 0) + 1
        # 称号检查: 传说鱼首次钓到可解锁称号
        new_title = None
        if first:
            new_title = title_mod.check_fish_title(self.state, name)
        # 坐钩(Mooch)检测: 这条鱼在当前钓场能坐钩别的鱼吗?
        mooch_avail = _mooch_targets(loc, name)
        if mooch_avail:
            self.state["mooch_pending"] = name
        else:
            self.state["mooch_pending"] = None
        return {"status": "caught", "fish": f, "name": name, "gil": g, "xp": xp,
                "hq": hq, "size": size, "rec": rec, "recdiff": recdiff,
                "gained": gained, "used": used, "wait": wait, "tell": tell,
                "descr": descr, "first": first, "flavor": flav,
                "bait_out": bait_out, "bait_name": bait_name, "collect": collect,
                "bait_hint": bait_hint, "new_title": new_title, "hookset": hookset,
                "intuition_note": intuition_note, "extra_n": extra_n}

    def cast(self, arg: str = "") -> str:
        now = self._now()
        loc = self.state["location"]
        lv = self.state.get("level", 1)
        spot_lv = _LOC_LEVEL.get(loc, 1)
        if lv < spot_lv:
            return f"🔒 这片钓场需 Lv {spot_lv}，你才 Lv {lv}。先去低级钓场练级。"
        # 解析: cast [N] [stop=rare] —— stop=rare 遇稀有自动暂停
        a = arg.strip()
        stop_rare = False
        num_str = ""
        for tok in a.split():
            if tok.lower().startswith("stop="):
                if tok.split("=", 1)[1].lower() in ("rare", "稀有"):
                    stop_rare = True
            elif not num_str:
                num_str = tok
        if stop_rare and not num_str:
            num_str = "30"            # stop=rare 不带数字 → 默认上限
        if num_str and num_str.lstrip("-").isdecimal() and int(num_str) < 1:
            return "次数得是正整数哦（先按 1 竿也行）。"
        req = int(num_str) if (num_str and num_str.lstrip("-").isdecimal()) else 1
        n = min(30, max(1, req))     # cast N: 一次多竿(上限30)
        if n > 1 and self.state.get("patience_casts", 0) > 0:
            return "🧘 耐心状态手感全开——一竿一竿来(cast 不带数字), 咬钩后亲手提钩。"
        if n == 1:
            r = self._cast_once(now)
            self._autosave()
            return self._fmt_cast(r)
        # 批量: 每竿推进 15s(模拟真实间隔); 饵耗尽/稀有鱼触发可中断
        results = []
        interrupted = None      # None / "bait" / "rare"
        for i in range(n):
            t = now + i * 15    # 每竿间隔 ≈15 现实秒
            r = self._cast_once(t)
            results.append(r)
            if r.get("bait_out"):
                interrupted = "bait"
                break
            if r["status"] == "bag_full":
                interrupted = "bagfull"
                break
            if r["status"] == "hook_window":
                break
            if (stop_rare and r["status"] == "caught"
                    and _weight(r["fish"]) <= 15):
                interrupted = "rare"
                break
        self._autosave()
        return self._fmt_batch(results, n, req, interrupted)

    def mooch(self) -> str:
        """以鱼钓鱼: 用刚钓到的鱼当活饵, 钓更稀有的目标鱼。"""
        pending = self.state.get("mooch_pending")
        if not pending:
            return "没有可以坐钩的鱼——先 cast 钓一条能当活饵的鱼。"
        loc = self.state["location"]
        targets = _mooch_targets(loc, pending)
        if not targets:
            self.state["mooch_pending"] = None
            return f"这里没有能用 {_disp(get(pending))} 坐钩的目标鱼。"
        now = self._now()
        # 消耗饵鱼: 从鱼袋取出那条活饵(方案B: 鱼真的在袋里, 真的会被用掉)
        self.state["mooch_pending"] = None
        if not self._bag_take(pending):
            return f"🐟 你翻了翻鱼袋——{_disp(get(pending))} 已经不在了(卖掉或下锅了?), 没法坐钩。"
        self.state["casts"] += 1
        # 从坐钩目标池里抽(天气/时段仍需满足)
        pool = [t for t in targets if is_catchable(t, now)]
        if not pool:
            rng = random.Random(self.state["seed"] * 1000003 + self.state["casts"])
            esc = atmo.escape_text("Heavy", rng)
            return (f"🐟 你把 {_disp(get(pending))} 挂上鱼钩, 抛入水中……\n"
                    f"   等了很久。没有动静。{esc}\n"
                    f"   活饵被消耗了, 但目标鱼此刻不开窗。（status <鱼名> 查窗口）")
        rng = random.Random(self.state["seed"] * 1000003 + self.state["casts"])
        weights = [max(1, 300 // _weight(t)) for t in pool]  # 坐钩时默认偏稀有
        f = rng.choices(pool, weights=weights, k=1)[0]
        # 脱钩概率比正常高一点(坐钩本来就难)
        if rng.random() < _ESCAPE.get(f.get("tug"), _ESCAPE_DEFAULT) * 1.3:
            _esc_rng = random.Random(hash((f["name"], self.state["casts"])))
            esc = atmo.escape_text(f.get("tug", "Heavy"), _esc_rng)
            self.state["escapes"] = self.state.get("escapes", 0) + 1
            return (f"🐟 你把 {_disp(get(pending))} 挂上鱼钩, 抛入水中……\n"
                    f"   水下猛地一沉! 有大家伙!\n"
                    f"   —— {esc} 活饵也被叼走了。")
        tell, descr, size, hq = _roll_details(rng, f)
        name = f["name"]
        # ── 鱼袋检查: 满袋只能放生, 活饵白搭(疼) ──
        if not self._bag_add(name, hq):
            return (f"🐟 你把 {_disp(get(pending))} 挂上鱼钩, 抛入水中……\n"
                    f"   水面炸开! 拉上来一条【{_disp(f)}】——\n"
                    f"   🎒💥 鱼袋满了! 只能忍痛放生, 活饵也搭进去了。(sell 卖鱼腾格子)")
        self.state["caught"][name] = self.state["caught"].get(name, 0) + 1
        first = self.state["caught"][name] == 1
        _int_note = self._intuition_on_catch(name)
        lv = self.state.get("level", 1)
        xp = int(leveling.xp_gain(f.get("level"), lv) * 2
                 * food_mod.xp_multiplier(self.state, now))   # 坐钩经验×2(食物buff也生效)
        # ── 坐钩链二跳: 坐钩渔获若还能当活饵, 链不断! ──
        if _mooch_targets(loc, name):
            self.state["mooch_pending"] = name
            _chain_hint = (f"\n   🐟🐟 链未断! 这条 {_disp(f)} 还能继续当活饵"
                           f"——mooch 再来, 链越深鱼越稀!")
        else:
            _chain_hint = ""
        self.state["last_catch"] = name
        gained = leveling.add_xp(self.state, xp)
        prev = self.state.setdefault("records", {}).get(name, 0)
        rec = size > prev
        if rec:
            self.state["records"][name] = size
        if hq:
            self.state["hq_total"] = self.state.get("hq_total", 0) + 1
        tasks_mod.record(self.state, self._now(), "catch", 1, region=f.get("region"))
        # 日志追踪
        import datetime as _dt
        _td = _dt.datetime.fromtimestamp(self._now()).strftime("%Y-%m-%d")
        _dl = self.state.setdefault("diary_log", {}).setdefault(_td,
              {"casts": 0, "caught": 0, "new_fish": [], "spots": [], "gil": 0, "xp": 0})
        _dl["caught"] += 1
        _dl["xp"] += xp
        if first and name not in _dl["new_fish"]:
            _dl["new_fish"].append(name)
        first_tag = "✨新图鉴! " if first else ""
        hqtag = " ✨HQ" if hq else ""
        rectag = " ★破纪录!" if rec else ""
        _mrng = random.Random(hash((name, size)))
        rich_desc = atmo.tug_text(f.get("tug", "Heavy"), _mrng)
        bait_disp = _disp(get(pending)) if get(pending) else pending
        out = (f"🐟 你把 {bait_disp} 挂上鱼钩, 抛入水中……\n"
               f"   ——水面炸开了! {rich_desc}！\n"
               f"   以鱼钓鱼成功! {first_tag}"
               f"【{_disp(f)}】{hqtag}（{size} 吋）{rectag}"
               f"  (入袋 🎒, +{xp} xp)" + _int_note + _chain_hint)
        for L in gained:
            out += f"\n🎉 升级! 现在 Lv {L}"
        self._autosave()
        return out

    def _fmt_cast(self, r) -> str:
        if r["status"] == "empty":
            hint = r.get("bait_hint", "")
            if r["reasons"]:
                out = "🎣 空军……此刻这片的鱼需要: " + "、".join(sorted(r["reasons"])) + "。"
            else:
                out = "🎣 抛竿……此刻这片没有鱼咬钩（空军）。"
            if hint:
                out += f"\n   {hint}"
            return out
        if r["status"] == "hook_window":
            f = r["fish"]
            _rng = random.Random(hash((f["name"], r["wait"])))
            tug = f.get("tug", "Light")
            out = (f"🎣 抛竿入水…静候 {r['wait']}s…\n"
                   f"   {atmo.tug_text(tug, _rng)}！竿感 [{r['tell']}]——{r['descr']}!")
            if tug == "Legendary":
                out += f"\n   {atmo.ceremony_text(_rng)}"
            out += ("\n   ⚔ 提钩窗口! 下一条命令定生死:\n"
                    f"      precision(精准) / powerful(强力) 各 {gp.HOOKSET_COST} GP · hook(硬拉·免费)\n"
                    "      看清竿感再动手——选错或分神, 鱼就没了。")
            if r.get("bait_out"):
                out += f"\n   🪱 {bait_mod.disp(r['bait_name'])} 用完了！buybait 补货。"
            return out
        if r["status"] == "bag_full":
            f = r["fish"]
            _rng = random.Random(hash((f["name"], r["wait"])))
            out = (f"🎣 抛竿入水…静候 {r['wait']}s…\n"
                   f"   {atmo.tug_text(f.get('tug', 'Light'), _rng)}！拉上来了——\n"
                   f"   🎒💥 鱼袋满了! 只能眼睁睁看着【{_disp(f)}】"
                   f"{'✨HQ ' if r.get('hq') else ''}摆尾游走……\n"
                   f"   （不计图鉴不计经验。sell 卖鱼腾格子 / bag 看袋子）")
            if r.get("bait_out"):
                out += f"\n   🪱 {bait_mod.disp(r['bait_name'])} 用完了！buybait 补货。"
            return out
        if r["status"] == "escaped":
            tug = r["fish"].get("tug", "Light")
            _esc_rng = random.Random(hash((r["fish"]["name"], r["wait"])))
            rich_desc = atmo.tug_text(tug, _esc_rng)
            esc_desc = atmo.escape_text(tug, _esc_rng)
            out = (f"🎣 抛竿入水…静候 {r['wait']}s…\n"
                   f"   {rich_desc}！\n"
                   f"   —— {esc_desc} 空手而归。")
            if r.get("bait_out"):
                out += f"\n   🪱 {bait_mod.disp(r['bait_name'])} 用完了！buybait 补货。"
            # 脱钩不消耗 buff, 提示玩家(防 AI 误判重开)
            held = [b for b, k in [("鱼眼", "buff_fisheyes"),
                                    ("撒饵", "buff_chum"), ("大鱼确保", "buff_prize"),
                                    ("专一垂钓", "buff_identical"), ("拍击水面", "buff_slap"),
                                    ("多重提钩", "buff_dh")]
                    if self.state.get(k)]
            if self.state.get("patience_casts", 0) > 0:
                held.insert(0, f"耐心(剩{self.state['patience_casts']}竿)")
            if held:
                out += f"\n   （{'、'.join(held)}仍在，下一竿继续生效）"
            if r.get("bait_hint"):
                out += f"\n   {r['bait_hint']}"
            return out
        f = r["fish"]
        tug = f.get("tug", "Light")
        is_legend = (tug == "Legendary")
        first = "✨新图鉴! " if r["first"] else ""
        note = f"（{'+'.join(r['used'])}生效）" if r["used"] else ""
        hqtag = " ✨HQ" if r["hq"] else ""
        if r["rec"]:
            sizetag = f"（{r['size']} 吋）★破纪录!"
        elif r["recdiff"] and r["recdiff"] <= 1.0:
            sizetag = f"（{r['size']} 吋，就差 {r['recdiff']} 吋破纪录!）"
        elif r["recdiff"]:
            sizetag = f"（{r['size']} 吋，比你的纪录小 {r['recdiff']} 吋）"
        else:
            sizetag = f"（{r['size']} 吋）"
        # ── 竿感描写 ──
        rng = random.Random(hash((_disp(f), r["size"])))
        rich_desc = atmo.tug_text(tug, rng)
        hs = r.get("hookset")
        if hs:
            head = {"precision": "🎯 你手腕轻巧一抖, 精准提钩——手感完美!",
                    "powerful": "💪 你腰马合一, 猛地扬竿——稳了!",
                    "hook": "🎣 你咬牙硬拉——居然真拉住了!"}[hs]
        else:
            head = f"🎣 抛竿入水…静候 {r['wait']}s…"
        if r["flavor"]:
            head += " " + r["flavor"]
        if is_legend:
            # 传说级仪式: 竿感 → 仪式揭晓 → 鱼名
            reveal = atmo.ceremony_text(rng)
            line = (f"{head}\n   {rich_desc}！\n"
                    f"   {reveal}  {first}{note}"
                    f"【{_disp(f)}】{hqtag}{sizetag}")
        else:
            line = (f"{head}\n   {rich_desc}！—— 上钩! {first}{note}"
                    f"{_disp(f)}{hqtag}{sizetag}")
        c = r.get("collect")
        if c is None:
            line += f"  (入袋 🎒, +{r['xp']} xp)"
        elif c["ok"]:
            icon = "🎟" if c["kind"] == "purple" else "🎫"
            line += (f"  📦收藏品! 价值 {c['value']}({icon}系) "
                     f"背包 {c['n']}/{scrip_mod.COLLECT_CAP}  (+{r['xp']} xp)")
        else:
            line += f"  💨{c['why']}(价值 {c['value']}), 只能放生……  (+{r['xp']} xp)"
        _fl = (f.get("flavor_en") if (self.state.get("lang") == "en" and f.get("flavor_en"))
               else f.get("flavor"))
        if _fl:
            line += "\n   " + _fl
        if r.get("bait_out"):
            line += f"\n   🪱 {bait_mod.disp(r['bait_name'])} 用完了！buybait 补货。"
        for L in r["gained"]:
            line += f"\n🎉 升级! 现在 Lv {L}"
        if r.get("bait_hint"):
            line += f"\n   {r['bait_hint']}"
        # 称号解锁
        if r.get("new_title"):
            t_name, t_flavor = r["new_title"]
            line += f"\n🎖 称号解锁!「{t_name}」—— {t_flavor}"
        if r.get("extra_n"):
            line += f"\n   🪝 多重提钩! 这一竿一共拽上来 {r['extra_n'] + 1} 条!"
        if r.get("intuition_note"):
            line += r["intuition_note"]
        # 坐钩提示
        mooch = self.state.get("mooch_pending")
        if mooch and mooch == r["name"]:
            targets = _mooch_targets(self.state["location"], mooch)
            names = "、".join(_disp(t) for t in targets[:3])
            more = f"…等 {len(targets)} 种" if len(targets) > 3 else ""
            line += (f"\n   🐟 这条鱼可以当活饵! 输入 mooch 以鱼钓鱼"
                     f"（目标: {names}{more}）")
        # 宠物反应(钓到鱼时20%概率)
        if r["status"] == "caught":
            pet_rng = random.Random(hash(("pet", r["name"], r["size"])))
            pet_react = pet_mod.catch_reaction(self.state, pet_rng)
            if pet_react:
                line += pet_react
        # 岸钓随机偶遇事件
        if not self.state.get("ocean"):
            evt_rng = random.Random(zlib.crc32(r.get("name", "").encode("utf-8")) * 1000003
                                    + self.state.get("casts", 0))
            evt = _roll_event(evt_rng, self.state, self._now())
            if evt:
                line += evt
        return line

    def _fmt_batch(self, results, n, req=None, interrupted=None) -> str:
        ran = len(results)                     # 实际执行竿数(可能被中断)
        window = results[-1] if (results and results[-1]["status"] == "hook_window") else None
        if window:
            pre = self._fmt_batch(results[:-1], ran - 1, None, None) if results[:-1] else ""
            tail = self._fmt_cast(window)
            note = f"\n   ⏸ 批量中止(剩余 {n - ran} 竿取消)——此刻, 只有你和它。"
            return (pre + "\n" + "─" * 30 + "\n" + tail + note) if pre else (tail + note)
        caught = [r for r in results if r["status"] == "caught"]
        escaped = sum(1 for r in results if r["status"] == "escaped")
        empty = sum(1 for r in results if r["status"] == "empty")
        full = sum(1 for r in results if r["status"] == "bag_full")
        if not caught:
            reasons = set()
            hints = set()
            for r in results:
                reasons |= r.get("reasons", set())
                if r.get("bait_hint"):
                    hints.add(r["bait_hint"])
            if reasons:
                out = f"🎣 抛竿 {ran} 次……一条没上。此处的鱼需要: " + "、".join(sorted(reasons)) + "。"
            else:
                extra = f"、🎒袋满放生 {full}——sell 腾格子!" if full else ""
                out = f"🎣 抛竿 {ran} 次……一条没上（脱钩 {escaped}、空军 {empty}{extra}）。"
            if hints:
                out += f"\n   {next(iter(hints))}"
            return out
        from collections import Counter
        total_xp = sum(r["xp"] for r in caught)
        gained = [L for r in caught for L in r["gained"]]
        news = [r for r in caught if r["first"]]
        recs = [r for r in caught if r["rec"]]
        hqs = [r for r in caught if r["hq"]]
        usedbuffs = sorted({b for r in caught for b in r.get("used", [])})
        biggest = max(caught, key=lambda r: r["size"])
        cnt = Counter(r["name"] for r in caught)
        name2fish = {r["name"]: r["fish"] for r in caught}
        miss = (([f"脱钩 {escaped}"] if escaped else []) + ([f"空军 {empty}"] if empty else [])
                + ([f"🎒袋满放生 {full}"] if full else []))
        head = f"🎣 抛竿 {ran} 次：钓到 {len(caught)} 条" + ("，" + "、".join(miss) if miss else "")
        if req and req > 30:
            head += "（单次上限30）"
        out = [head]
        bagged = sum(1 for r in caught if not r.get("collect"))
        out.append(f"   收获 +{total_xp} xp"
                   + (f", 入袋 {bagged} 条 (🎒{len(self.state.get('fish_bag', {}))}"
                      f"/{self._bag_cap()})" if bagged else "")
                   + (f"，🎉升到 Lv{gained[-1]}!" if gained else "")
                   + self._quest_hint(gained))
        collects = [r["collect"] for r in caught if r.get("collect")]
        if collects:
            okc = [c for c in collects if c["ok"]]
            miss_c = len(collects) - len(okc)
            inv_n = len(self.state.get("collectables", []))
            line = (f"   📦收藏品 +{len(okc)}(共价值 {sum(c['value'] for c in okc)})"
                    f"  背包 {inv_n}/{scrip_mod.COLLECT_CAP}")
            if miss_c:
                line += f"  💨放生 {miss_c} 条(价值不足/包满)"
            out.append(line + "  → turnin 换票")
        if usedbuffs:
            out.append(f"   （{'+'.join(usedbuffs)} 已生效于其中一竿）")
        if news:
            names = "、".join(_disp(r["fish"]) for r in news[:6]) + ("…" if len(news) > 6 else "")
            out.append(f"   ✨新图鉴 {len(news)} 种: {names}")
        if recs:
            out.append(f"   ★破纪录 {len(recs)} 条")
        if full:
            out.append(f"   🎒💥 有 {full} 条因袋满被放生——sell 卖鱼腾格子!")
        if any(r.get("intuition_note") for r in caught):
            out.append("   ⚡ 捕鱼人之识触发! 水面之下, 有什么正注视着你……")
        if hqs:
            out.append(f"   ✨HQ {len(hqs)} 条")
        out.append(f"   最大: {_disp(biggest['fish'])} {biggest['size']} 吋")
        detail = "、".join(f"{_disp(name2fish[nm])}×{c}" for nm, c in cnt.most_common(6))
        out.append(f"   渔获: {detail}" + ("…" if len(cnt) > 6 else ""))
        # 中断原因(鱼饵耗尽 / 稀有鱼暂停)
        remaining = n - ran
        if interrupted == "bait":
            out.append(f"   🪱 第 {ran} 竿后鱼饵用完! 剩余 {remaining} 竿未执行。buybait 补货。")
        elif interrupted == "bagfull":
            out.append(f"   🎒💥 鱼袋满了! 剩余 {remaining} 竿自动停止——sell 腾格子再继续。")
        elif interrupted == "rare":
            last = results[-1]
            out.append(f"   🎯 稀有鱼! {_disp(last['fish'])} 上钩 ——"
                       f" 自动暂停(还剩 {remaining} 竿额度)。")
        elif any(r.get("bait_out") for r in results):
            out.append("   🪱 鱼饵中途用完了！buybait 补货再继续。")
        # 鱼饵提示(批量模式也要显示!)
        hints = [r.get("bait_hint") for r in results if r.get("bait_hint")]
        if hints:
            out.append(f"   {hints[0]}")
        # 岸钓批量偶遇: 在整批结果中掷一次
        if not self.state.get("ocean"):
            evt_rng = random.Random(zlib.crc32(b"batch") * 1000003
                                    + self.state.get("casts", 0) * 31 + ran)
            evt = _roll_event(evt_rng, self.state, self._now())
            if evt:
                out.append(evt)
        return "\n".join(out)

    def _spear_once(self, now):
        loc = self.state["location"]
        pool = [f for f in FISH if f["location"] == loc and f["mode"] == "spear"
                and is_catchable(f, now)]
        self.state["casts"] += 1
        if not pool:
            return {"status": "empty"}
        rng = random.Random(self.state["seed"] * 1000003 + self.state["casts"])
        f = rng.choices(pool, weights=[_GIG_WEIGHT.get(_gig(x), 40) for x in pool], k=1)[0]
        size = _gig(f)
        _, _, inches, hq = _roll_details(rng, f)
        name = f["name"]
        if not self._bag_add(name, hq):
            return {"status": "bag_full", "fish": f, "name": name, "hq": hq,
                    "size": size, "inches": inches}
        self.state["caught"][name] = self.state["caught"].get(name, 0) + 1
        first = self.state["caught"][name] == 1
        xp = int(_GIG_XP.get(size, 12) * food_mod.xp_multiplier(self.state, now))
        gained = leveling.add_xp(self.state, xp)
        rec = inches > self.state.setdefault("records", {}).get(name, 0)
        if rec:
            self.state["records"][name] = inches
        tasks_mod.record(self.state, self._now(), "spear", 1)
        return {"status": "caught", "fish": f, "name": name, "size": size, "inches": inches,
                "hq": hq, "gil": 0, "xp": xp, "rec": rec, "gained": gained, "first": first,
                "intuition_note": self._intuition_on_catch(name)}

    def spear(self, arg: str = "") -> str:
        now = self._now()
        loc = self.state["location"]
        if loc not in _SPEAR_SPOTS:
            return "这里不是叉鱼点。用 spots 找带 🔱 的叉鱼点，goto 过去再 spear。"
        lv = self.state.get("level", 1)
        need = _spear_level(loc)
        if lv < need:
            return f"🔒 这个叉鱼点需 Lv {need}（同区水平），你才 Lv {lv}。先练级。"
        a = arg.strip()
        if a and a.lstrip("-").isdecimal() and int(a) < 1:
            return "次数得是正整数哦（先按 1 次也行）。"
        req = int(a) if a.lstrip("-").isdecimal() else 1
        n = min(30, max(1, req))
        if n == 1:
            r = self._spear_once(now)
            self._autosave()
            if r["status"] == "empty":
                return atmo.spear_miss_text(random.Random())
            if r["status"] == "bag_full":
                return (f"🔱 叉中一条 {_disp(r['fish'])}——\n"
                        f"   🎒💥 鱼袋满了! 只能放生。(sell 卖鱼腾格子)")
            f = r["fish"]
            first = "✨新图鉴! " if r["first"] else ""
            hqtag = " ✨HQ" if r["hq"] else ""
            rectag = " ★破纪录!" if r["rec"] else ""
            _srng = random.Random(hash((r["name"], r["inches"])))
            dive = atmo.spear_dive_text(_srng)
            hit = atmo.spear_hit_text(r["size"], _srng)
            line = (f"🔱 {dive}\n"
                    f"   {hit}！\n"
                    f"   {first}{_disp(f)}{hqtag}（{r['inches']} 吋）{rectag}"
                    f"  (入袋 🎒, +{r['xp']} xp)" + (r.get("intuition_note") or ""))
            _fl = (f.get("flavor_en") if (self.state.get("lang") == "en" and f.get("flavor_en"))
                   else f.get("flavor"))
            if _fl:
                line += "\n   " + _fl
            for L in r["gained"]:
                line += f"\n🎉 升级! 现在 Lv {L}"
            return line
        results = []
        for i in range(n):
            t = now + i * 15    # 每竿间隔 ≈15 现实秒(和 cast 一致)
            results.append(self._spear_once(t))
        self._autosave()
        caught = [r for r in results if r["status"] == "caught"]
        full = sum(1 for r in results if r["status"] == "bag_full")
        empty = len(results) - len(caught) - full
        if not caught:
            if full:
                return f"🔱 潜 {n} 次……🎒袋满放生 {full} 条, 空手 {empty}。sell 腾格子!"
            return f"🔱 潜 {n} 次……啥也没叉到。"
        from collections import Counter
        tx = sum(r["xp"] for r in caught)
        gained = [L for r in caught for L in r["gained"]]
        news = [r for r in caught if r["first"]]
        recs = sum(1 for r in caught if r["rec"])
        biggest = max(caught, key=lambda r: r["inches"])
        cnt = Counter(r["name"] for r in caught)
        n2f = {r["name"]: r["fish"] for r in caught}
        out = [f"🔱 叉鱼 {n} 次：叉中 {len(caught)} 条" + (f"，空手 {empty}" if empty else "")
               + (f"，🎒袋满放生 {full}" if full else "")]
        if req > 30:
            out[0] += "（单次上限30）"
        out.append(f"   收获 +{tx} xp, 入袋 {len(caught)} 条"
                   f" (🎒{len(self.state.get('fish_bag', {}))}/{self._bag_cap()})"
                   + (f"，🎉升到 Lv{gained[-1]}!" if gained else "")
                   + self._quest_hint(gained))
        if news:
            out.append(f"   ✨新图鉴 {len(news)} 种: "
                       + "、".join(_disp(r["fish"]) for r in news[:6]) + ("…" if len(news) > 6 else ""))
        if recs:
            out.append(f"   ★破纪录 {recs} 条")
        out.append(f"   最大: {_disp(biggest['fish'])} {biggest['inches']} 吋")
        out.append("   渔获: " + "、".join(f"{_disp(n2f[nm])}×{c}" for nm, c in cnt.most_common(6))
                   + ("…" if len(cnt) > 6 else ""))
        return "\n".join(out)

    def baits(self) -> str:
        stock = self.state.get("bait_stock", {})
        eq = self.state.get("bait")
        gil_ = self.state["gil"]
        out = [f"🪱 鱼饵店（大鱼要挂对饵才咬，饵会损耗）  💰{gil_} gil"]
        if eq and stock.get(eq, 0) > 0:
            out.append(f"   当前: 🪱{bait_mod.disp(eq)}×{stock[eq]}")
        for name, info in sorted(bait_mod.BAITS.items(), key=lambda x: x[1]["price"]):
            p = info["price"]
            have = stock.get(name, 0)
            tag = f"存{have}" if have > 0 else (f"{p}g/个" if gil_ >= p else f"🔒{p}g")
            star = "⭐" if name == eq else "  "
            out.append(f"   {star}{tag:>9}  {bait_mod.disp(name)}")
        out.append("   买饵: buybait <饵名> [数量,默认20]  /  换饵: bait <饵名>")
        return "\n".join(out)

    def buybait(self, arg: str) -> str:
        qty = 20
        name_arg = arg.strip()
        parts = name_arg.rsplit(" ", 1)
        if len(parts) == 2 and parts[1].isdecimal():
            qty = min(999, max(1, int(parts[1])))
            name_arg = parts[0]
        b = bait_mod.match(name_arg)
        if not b:
            return f"没这种鱼饵：{arg}。用 baits 看饵店。"
        cost = bait_mod.price(b) * qty
        if self.state["gil"] < cost:
            return f"gil 不够（{qty} 个需 {cost}，你有 {self.state['gil']}）。"
        self.state["gil"] -= cost
        st = self.state.setdefault("bait_stock", {})
        st[b] = st.get(b, 0) + qty
        self.state["bait"] = b
        self._autosave()
        return (f"🪱 买 {qty} 个 {bait_mod.disp(b)} 并挂上！"
                f"(-{cost}g，剩 {self.state['gil']}) 库存 {st[b]}")

    def equipbait(self, arg: str) -> str:
        stock = self.state.get("bait_stock", {})
        if not arg.strip():
            cur = self.state.get("bait")
            n = stock.get(cur, 0)
            return f"当前鱼饵: {bait_mod.disp(cur)}×{n}" if (cur and n > 0) else "当前没挂鱼饵。bait <饵名> 挂上。"
        b = bait_mod.match(arg)
        if not b:
            return f"没这种鱼饵：{arg}。"
        if stock.get(b, 0) <= 0:
            return f"你没有 {bait_mod.disp(b)} 的库存，先 buybait 补货。"
        self.state["bait"] = b
        self._autosave()
        return f"已挂上 {bait_mod.disp(b)}×{stock[b]}。"

    def rods(self) -> str:
        lv = self.state.get("level", 1)
        gil_ = self.state["gil"]
        owned = set(self.state.get("rods_owned", []))
        eq = self.state.get("rod")
        out = [f"🎣 鱼竿店  你 Lv{lv}  💰{gil_} gil"]
        if eq and eq in gear.RODS:
            r = gear.RODS[eq]
            out.append(f"   当前: ⭐{eq}（采集{r['gathering']} 鉴别{r['perception']}）")
        usable = sorted([r for r in gear.RODS.values() if r["level"] <= lv],
                        key=lambda r: -r["ilvl"])
        out.append("   你等级可用（强→弱，前 10）：")
        for r in usable[:10]:
            scrip_rod = scrip_mod.is_scrip_rod(r)
            if scrip_rod:
                p = scrip_mod.rod_scrip_price(r)
                have = self.state.get("scrip_purple", 0)
                unit = "🎟"
            else:
                p = gear.price(r)
                have = gil_
                unit = "g"
            if r["name"] in owned:
                tag = "✅已有"
            elif have >= p:
                tag = f"{'🎟' if scrip_rod else ''}{p}{'' if scrip_rod else 'g'}"
            else:
                tag = f"🔒{'🎟' if scrip_rod else ''}{p}{'' if scrip_rod else 'g'}"
            star = "⭐" if r["name"] == eq else "  "
            grad = "👑" if scrip_rod else "  "
            out.append(f"   {star}{grad}Lv{r['level']:>3} 采集{r['gathering']:>4} 鉴别{r['perception']:>4}"
                       f"  {r['name']}  [{tag}]")
        higher = [r for r in gear.RODS.values() if r["level"] > lv]
        if higher:
            out.append(f"   （还有 {len(higher)} 把更高级的，升级后解锁）")
        out.append("   buyrod <名字> 买  /  equiprod <名字> 换装")
        out.append(f"   👑=毕业竿(装等≥{scrip_mod.SCRIP_ROD_MIN_ILVL}), 只收🎟紫票"
                   f"——collector/海钓攒票来换")
        return "\n".join(out)

    def buyrod(self, arg: str) -> str:
        r = gear.match(arg)
        if not r:
            return f"没找到这把鱼竿：{arg}。用 rods 看列表。"
        if r["name"] in self.state.get("rods_owned", []):
            return f"《{r['name']}》你已有了，equiprod 装备它。"
        if r["level"] > self.state.get("level", 1):
            return f"《{r['name']}》需 Lv{r['level']}，你才 Lv{self.state.get('level', 1)}。"
        scrip_rod = scrip_mod.is_scrip_rod(r)
        if scrip_rod:
            p = scrip_mod.rod_scrip_price(r)
            have = self.state.get("scrip_purple", 0)
            if have < p:
                return (f"🎟紫票不够（需 {p}，你有 {have}）。"
                        f"👑毕业竿只收票——collector 模式上交高级鱼, 或海钓攒渔分。")
            self.state["scrip_purple"] = have - p
            paid = f"-🎟{p}，剩 {self.state['scrip_purple']}"
        else:
            p = gear.price(r)
            if self.state["gil"] < p:
                return f"gil 不够（需 {p}，你有 {self.state['gil']}）。多钓点鱼卖钱。"
            self.state["gil"] -= p
            paid = f"-{p}g，剩 {self.state['gil']}"
        self.state.setdefault("rods_owned", []).append(r["name"])
        # 只在比当前竿更强(ilvl)或空手时才自动装上; 否则入包不动, 防静默降级
        cur = gear.RODS.get(self.state.get("rod"))
        crown = "👑" if scrip_rod else ""
        if not cur or r["ilvl"] >= cur["ilvl"]:
            self.state["rod"] = r["name"]
            self._autosave()
            return (f"🎣 购得并装备{crown}《{r['name']}》！({paid})\n"
                    f"   采集{r['gathering']}(稀有鱼↑) 鉴别{r['perception']}(HQ↑)")
        self._autosave()
        return (f"🎣 购得{crown}《{r['name']}》！({paid})\n"
                f"   已入包（当前装备更强，equiprod 可换）。")

    def equiprod(self, arg: str) -> str:
        r = gear.match(arg)
        if not r:
            return f"没找到这把鱼竿：{arg}。"
        if r["name"] not in self.state.get("rods_owned", []):
            return f"你还没有《{r['name']}》，先 buyrod 买。"
        if r["level"] > self.state.get("level", 1):
            return f"《{r['name']}》需 Lv{r['level']}。"
        self.state["rod"] = r["name"]
        self._autosave()
        return f"已装备《{r['name']}》（采集{r['gathering']} 鉴别{r['perception']}）。"

    def records(self) -> str:
        r = self.state.get("records", {})
        if not r:
            return "还没有尺寸记录。钓几条鱼看看。"
        top = sorted(r.items(), key=lambda x: -x[1])[:12]
        out = ["🏆 你的最大尺寸记录（前 12）:"]
        for name, inch in top:
            ff = get(name)
            out.append(f"   {inch:>6} 吋  {_disp(ff) if ff else name}")
        return "\n".join(out)

    def snagging(self, arg: str = "") -> str:
        cur = self.state.get("snagging", False)
        a = arg.strip().lower()
        if a in ("on", "开", "1", "true"):
            cur = True
        elif a in ("off", "关", "0", "false"):
            cur = False
        else:
            cur = not cur
        self.state["snagging"] = cur
        self._autosave()
        return f"🪝 钓草(snagging): {'开' if cur else '关'}。（开启后可钓需钓草的鱼）"

    def collector(self, arg: str = "") -> str:
        cur = self.state.get("collector", False)
        a = arg.strip().lower()
        if not a:                                  # 无参: 只看状态, 不误切换(#29)
            n = len(self.state.get("collectables", []))
            return (f"📦 收藏品模式当前: {'开' if cur else '关'}"
                    f"（背包 {n}/{scrip_mod.COLLECT_CAP}）。"
                    f"collector on 开 / collector off 关。")
        if a in ("on", "开", "1", "true"):
            cur = True
        elif a in ("off", "关", "0", "false"):
            cur = False
        else:
            return f"看不懂的参数: {arg}。用法: collector on / collector off。"
        self.state["collector"] = cur
        self._autosave()
        if cur:
            return (f"📦 收藏品模式: 开。钓到的鱼判收藏价值(≥{scrip_mod.COLLECT_MIN} 达标),"
                    f"达标进背包(容量 {scrip_mod.COLLECT_CAP}),turnin 换票;"
                    f"不达标只能放生——不给 gil, 就是这么心痛。")
        return "📦 收藏品模式: 关。回到普通钓鱼(卖 gil)。"

    def turnin(self) -> str:
        inv = self.state.get("collectables", [])
        if not inv:
            return "收藏品背包是空的。collector 开模式去钓些高价值的鱼吧。"
        n, white, purple = scrip_mod.turnin(self.state)
        tasks_mod.record(self.state, self._now(), "collect", n)
        self._autosave()
        parts = []
        if white:
            parts.append(f"🎫白票 +{white}")
        if purple:
            parts.append(f"🎟紫票 +{purple}")
        return (f"📦 上交 {n} 件收藏品: " + "、".join(parts)
                + f"\n   现有: 🎫{self.state['scrip_white']} 🎟{self.state['scrip_purple']}"
                + "  (books 看图鉴书票价)")

    # ---------- 全身装备(11部位) ----------
    def eshop(self, arg: str = "") -> str:
        lv = self.state.get("level", 1)
        a = arg.strip()
        if not a:
            lines = [f"🛒 装备店(全身11部位, 你 Lv{lv})——eshop <部位> 看货, 如 eshop 身体"]
            lines.append("   部位: " + " / ".join(
                s for s in eq_mod.SLOTS if not s.startswith("戒指")) + " / 戒指")
            lines.append("   蓝装=毕业装收票(Lv<90🎫白票, ≥90🎟紫票); 白/绿装收gil; 价格随物品浮动")
            lines.append("   ebuy <名字> 买 / wear <名字> 穿 / gearset 看全身 / recycle <名字> 分解")
            return "\n".join(lines)
        slot = "戒指" if a.startswith("戒指") else a
        valid = {it["slot"] for it in eq_mod.ITEMS.values()}
        if slot not in valid:
            return f"没有这个部位: {a}。eshop 看部位列表。"
        pool = [it for it in eq_mod.ITEMS.values()
                if it["slot"] == slot and it["level"] <= lv
                and eq_mod.price(it)[0] is not None]
        if not pool:
            min_lv = min(it["level"] for it in eq_mod.ITEMS.values()
                         if it["slot"] == slot)
            return (f"[{slot}] 暂时没有你等级(Lv{lv})可穿的货——"
                    f"这个部位最低 Lv{min_lv}, 练上去再来逛~")
        pool.sort(key=lambda it: -it["ilvl"])
        owned = set(self.state.get("equip_owned", []))
        out = [f"🛒 {slot}(你等级可穿, 强→弱, 前8)  "
               f"💰{self.state['gil']}g 🎫{self.state.get('scrip_white', 0)}"
               f" 🎟{self.state.get('scrip_purple', 0)}"]
        for it in pool[:8]:
            tag = "✅已有" if it["id"] in owned else eq_mod.price_disp(it)
            rar = {1: "⬜", 2: "🟩", 3: "🟦", 4: "🟪"}.get(it["rarity"], "")
            om = f"{it['sockets']}孔" + ("·可禁断" if it["overmeld"] else "")
            st = " ".join(f"{k}+{v}" for k, v in it["stats"].items())
            out.append(f"   {rar}Lv{it['level']:>3} 装等{it['ilvl']:>3}"
                       f"  {it['name']}  {st}  [{om}]  [{tag}]")
        return "\n".join(out)

    def _eq_find(self, arg: str):
        """找装备; 多命中时返回 (None, 提示文本)。"""
        it = eq_mod.match(arg)
        if it:
            return it, None
        subs = eq_mod.match_all(arg)
        if 2 <= len(subs) <= 8:
            names = "、".join(f"{x['name']}({x['slot']})" for x in subs[:8])
            return None, f"匹配到多件装备, 请写全名: {names}"
        return None, f"没找到这件装备: {arg}。eshop <部位> 看货。"

    def ebuy(self, arg: str) -> str:
        it, err = self._eq_find(arg)
        if err:
            return err
        if it["id"] in self.state.get("equip_owned", []):
            return f"《{it['name']}》你已有了, wear 穿上它。"
        if it["level"] > self.state.get("level", 1):
            return f"《{it['name']}》需 Lv{it['level']}, 你才 Lv{self.state.get('level', 1)}。"
        cur, amt = eq_mod.price(it)
        if cur is None:
            return f"《{it['name']}》是非卖品(古武类), 商店不出售。"
        wallet = {"gil": "gil", "white": "scrip_white", "purple": "scrip_purple"}[cur]
        名 = {"gil": "gil", "white": "🎫白票", "purple": "🎟紫票"}[cur]
        have = self.state.get(wallet, 0)
        if have < amt:
            return f"{名}不够(需 {amt}, 你有 {have})。"
        self.state[wallet] = have - amt
        self.state.setdefault("equip_owned", []).append(it["id"])
        self._autosave()
        return (f"🛒 购得《{it['name']}》! (-{名}{amt}, 剩 {self.state[wallet]})\n"
                f"   wear {it['name']} 穿上它。")

    def wear(self, arg: str) -> str:
        it, err = self._eq_find(arg)
        if err:
            return err
        if it["id"] not in self.state.get("equip_owned", []):
            return f"你还没有《{it['name']}》, 先 ebuy 买。"
        if it["level"] > self.state.get("level", 1):
            return f"《{it['name']}》需 Lv{it['level']}。"
        slot = eq_mod.slot_key_of(it, self.state)
        old = self.state.setdefault("equip", {}).get(slot)
        self.state["equip"][slot] = it["id"]
        # GP 上限可能变小: 现有 GP 立即封到新上限
        self.state["gp"] = min(self.state.get("gp", 0), gp.max_gp(self.state, self._now()))
        self._autosave()
        oldname = f"(替下《{eq_mod.ITEMS[old]['name']}》)" if old else ""
        st = " ".join(f"{k}+{v}" for k, v in it["stats"].items())
        t = eq_mod.stats_total(self.state)
        return (f"🧥 [{slot}] 穿上《{it['name']}》{oldname}  {st}\n"
                f"   全身: 获得力{t['获得力']} 鉴别力{t['鉴别力']}"
                f" 采集力{t['采集力']} → GP上限 {gp.max_gp(self.state, self._now())}")

    def gearset(self) -> str:
        eq = self.state.get("equip", {})
        out = [f"🧥 全身装备(GP上限 {gp.max_gp(self.state, self._now())}):"]
        for slot in eq_mod.SLOTS:
            it = eq_mod.ITEMS.get(eq.get(slot) or 0)
            if it:
                st = " ".join(f"{k}+{v}" for k, v in it["stats"].items())
                out.append(f"   [{slot}] {it['name']}  {st}")
            elif slot == "主手" and self.state.get("rod"):
                out.append(f"   [主手] (旧竿){self.state['rod']} —— eshop 主手 可换新体系")
            else:
                out.append(f"   [{slot}] —")
        t = eq_mod.stats_total(self.state)
        out.append(f"   合计: 获得力{t['获得力']} 鉴别力{t['鉴别力']} 采集力{t['采集力']}")
        return "\n".join(out)

    def recycle(self, arg: str) -> str:
        it, err = self._eq_find(arg)
        if err:
            return err
        owned = self.state.get("equip_owned", [])
        if it["id"] not in owned:
            return f"你没有《{it['name']}》, 无从分解。"
        if it["id"] in (self.state.get("equip") or {}).values():
            return f"《{it['name']}》正穿在身上——先换下来再分解(防手滑)。"
        owned.remove(it["id"])
        self.state["casts"] = self.state.get("casts", 0) + 1   # 推进确定性rng
        rng = random.Random(self.state["seed"] * 1000003 + self.state["casts"])
        got = eq_mod.recycle_roll(rng, it)
        self.state["gil"] += got["gil"]
        self.state["scrip_white"] = self.state.get("scrip_white", 0) + got["white"]
        self.state["scrip_purple"] = self.state.get("scrip_purple", 0) + got["purple"]
        parts = [f"+{got['gil']}g"]
        if got["white"]:
            parts.append(f"🎫+{got['white']}")
        if got["purple"]:
            parts.append(f"🎟+{got['purple']}")
        if got["shard"]:
            self.state["materia_shards"] = self.state.get("materia_shards", 0) + 1
            parts.append(f"💎魔晶石碎片+1(共{self.state['materia_shards']})")
        self._autosave()
        return f"♻️ 分解《{it['name']}》: " + " ".join(parts)

    # ---------- 魔晶石(镶嵌+禁断) ----------
    def mshop(self) -> str:
        inv = self.state.get("materia_inv", {})
        out = [f"💎 魔晶石商店  🎫{self.state.get('scrip_white', 0)}"
               f" 🎟{self.state.get('scrip_purple', 0)}"
               f" 碎片{self.state.get('materia_shards', 0)}"]
        by_param = {}
        for m in mat_mod.MATERIA.values():
            by_param.setdefault(m["param"], []).append(m)
        for param, ms in by_param.items():
            out.append(f"   —— {param} ——")
            for m in sorted(ms, key=lambda x: x["grade"]):
                cur, amt = mat_mod.price(m)
                tag = f"{'🎟' if cur == 'purple' else '🎫'}{amt}"
                have = inv.get(str(m["id"]), 0)
                hv = f" ×{have}" if have else ""
                out.append(f"     {m['name']}  {param}+{m['value']}"
                           f"  [{tag} 或 碎片×{mat_mod.shard_cost(m)}]{hv}")
        out.append("   mbuy <名>(票买) / mcraft <名>(碎片合成) / "
                   "meld <装备名> <魔晶石名>(镶嵌)")
        return "\n".join(out)

    def _mat_find(self, arg: str):
        m = mat_mod.match(arg)
        if m:
            return m, None
        subs = mat_mod.match_all(arg)
        if 2 <= len(subs) <= 8:
            names = "、".join(x["name"] for x in subs[:8])
            return None, f"匹配到多颗魔晶石, 请写全名: {names}"
        return None, f"没有这种魔晶石: {arg}。mshop 看列表。"

    def mbuy(self, arg: str) -> str:
        m, err = self._mat_find(arg)
        if err:
            return err
        cur, amt = mat_mod.price(m)
        wallet = "scrip_purple" if cur == "purple" else "scrip_white"
        名 = "🎟紫票" if cur == "purple" else "🎫白票"
        have = self.state.get(wallet, 0)
        if have < amt:
            return f"{名}不够(需 {amt}, 你有 {have})。"
        self.state[wallet] = have - amt
        inv = self.state.setdefault("materia_inv", {})
        inv[str(m["id"])] = inv.get(str(m["id"]), 0) + 1
        self._autosave()
        return (f"💎 购得《{m['name']}》({m['param']}+{m['value']})"
                f" -{名}{amt}, 现有 ×{inv[str(m['id'])]}")

    def mcraft(self, arg: str) -> str:
        m, err = self._mat_find(arg)
        if err:
            return err
        need = mat_mod.shard_cost(m)
        have = self.state.get("materia_shards", 0)
        if have < need:
            return (f"碎片不够(需 {need}, 你有 {have})。"
                    f"♻️ recycle 分解装备有机率掉碎片。")
        self.state["materia_shards"] = have - need
        inv = self.state.setdefault("materia_inv", {})
        inv[str(m["id"])] = inv.get(str(m["id"]), 0) + 1
        self._autosave()
        return (f"💎 碎片×{need} 合成《{m['name']}》!"
                f" 剩碎片 {self.state['materia_shards']}, 现有 ×{inv[str(m['id'])]}")

    def meld(self, arg: str) -> str:
        # 用法: meld <装备名> <魔晶石名> —— 从右往左找魔晶石, 剩下的是装备名
        a = arg.strip()
        it = m = None
        for cut in range(len(a), 0, -1):           # 尝试各切分点
            left, right = a[:cut].strip(), a[cut:].strip()
            if not right:
                continue
            mm = mat_mod.match(right)
            ii = eq_mod.match(left)
            if mm and ii:
                it, m = ii, mm
                break
        if not it or not m:
            return "用法: meld <装备名> <魔晶石名>  例: meld 榉木钓竿 达识魔晶石伍型"
        if it["id"] not in self.state.get("equip_owned", []):
            return f"你没有《{it['name']}》, 先 ebuy 买。"
        inv = self.state.setdefault("materia_inv", {})
        if inv.get(str(m["id"]), 0) <= 0:
            return f"你没有《{m['name']}》, mbuy/mcraft 先弄一颗。"
        melds = self.state.setdefault("melds", {}).setdefault(str(it["id"]), [])
        ok, is_over, over_slot, why = mat_mod.meld_plan(it, len(melds))
        if not ok:
            return f"⛔ {why}"
        # 消耗魔晶石(成败都耗——真实规则)
        inv[str(m["id"])] -= 1
        if inv[str(m["id"])] <= 0:
            inv.pop(str(m["id"]), None)
        self.state["casts"] = self.state.get("casts", 0) + 1
        rng = random.Random(self.state["seed"] * 1000003 + self.state["casts"])
        slots_disp = f"{len(melds)}/{it['sockets']}保底" + \
                     (f"+禁断至{mat_mod.MAX_MELDS}" if it["overmeld"] else "")
        if is_over:
            rate = mat_mod.overmeld_rate(m, over_slot)
            roll_ok = rng.random() * 100 < rate
            if not roll_ok:
                self.state["meld_fail"] = self.state.get("meld_fail", 0) + 1
                self._autosave()
                boom = mat_mod.BOOM_FLAVOR[rng.randrange(len(mat_mod.BOOM_FLAVOR))]
                return (f"💥 禁断第 {over_slot} 颗(成功率 {rate}%)……失败!!\n"
                        f"   {boom}\n"
                        f"   《{m['name']}》没了。装备现况: {slots_disp}")
            melds.append(m["id"])
            self.state["meld_ok"] = self.state.get("meld_ok", 0) + 1
            self._autosave()
            okf = mat_mod.MELD_OK_FLAVOR[rng.randrange(len(mat_mod.MELD_OK_FLAVOR))]
            t = eq_mod.stats_total(self.state)
            return (f"🔥 禁断第 {over_slot} 颗(成功率 {rate}%)……成功!!\n"
                    f"   {okf}\n"
                    f"   《{it['name']}》+{m['param']}+{m['value']}"
                    f" (已嵌 {len(melds)}/{mat_mod.MAX_MELDS})"
                    f"  全身获得{t['获得力']}/鉴别{t['鉴别力']}/采集{t['采集力']}")
        melds.append(m["id"])
        self._autosave()
        t = eq_mod.stats_total(self.state)
        return (f"✨ 保底孔镶嵌成功: 《{it['name']}》+{m['param']}+{m['value']}"
                f" (已嵌 {len(melds)}, 保底 {it['sockets']} 孔)"
                f"  全身获得{t['获得力']}/鉴别{t['鉴别力']}/采集{t['采集力']}")

    # ---------- 职业任务(剧情提醒, 不绑技能) ----------
    def _quest_hint(self, gained) -> str:
        ls = quest_mod.newly_unlocked(gained)
        if not ls:
            return ""
        return f"\n   📜 Lv{ls[-1]} 职业任务解锁了! quests 看剧情(不做也不影响玩)"

    def quest_cmd(self, arg: str = "") -> str:
        s = self.state
        lv = s.get("level", 1)
        done = s.get("quests_done", [])
        a = arg.strip().lower()
        # quest done: 交差最低一档已达成的任务
        if a in ("done", "交差", "complete"):
            for q in quest_mod.available(lv, done):
                qlv, title, story, fname, loc = q
                if fname in s.get("caught", {}):
                    r = quest_mod.reward_of(qlv)
                    s["gil"] += r["gil"]
                    s["scrip_white"] = s.get("scrip_white", 0) + r["white"]
                    gained = leveling.add_xp(s, r["xp"])
                    done.append(qlv)
                    saddle = ""
                    if qlv == SADDLE_QUEST_LV:
                        saddle = (f"\n   🐦 会长把一只鞍囊挂上你的陆行鸟:「装鱼用的, 拿去。」"
                                  f"—— 鱼袋 +{BAG_SADDLE_SLOTS} 格(现在共 {self._bag_cap()} 格)!")
                    self._autosave()
                    f = get(fname)
                    return (f"📜 交差《{title}》(Lv{qlv}) —— 你掏出那条 {_disp(f)}。\n"
                            f"   会长满意地点头。奖励: +{r['gil']}g +{r['xp']}xp"
                            f" 🎫+{r['white']}"
                            + (f"  🎉升到 Lv{gained[-1]}!" if gained else "")
                            + self._quest_hint(gained) + saddle)
            return "还没有可交差的任务——先把任务鱼钓进图鉴(quests 看要钓什么)。"
        # quests: 总览
        if not a:
            out = [f"📜 职业任务(你 Lv{lv}; 纯剧情, 不绑技能):"]
            for qlv, title, _story, fname, loc in quest_mod.QUESTS:
                if qlv in done:
                    mark = "✅"
                elif qlv <= lv:
                    mark = "⭐可交差" if fname in self.state.get("caught", {}) else "🔓"
                else:
                    mark = "🔒"
                out.append(f"   {mark} Lv{qlv:>2}《{title}》")
            out.append("   quest <等级> 看剧情 / quest done 交差")
            return "\n".join(out)
        # quest <等级>: 看剧情
        if a.isdecimal():
            qlv = int(a)
            q = next((x for x in quest_mod.QUESTS if x[0] == qlv), None)
            if not q:
                return f"没有 Lv{qlv} 的职业任务。quests 看列表。"
            if qlv > lv:
                return f"Lv{qlv} 任务还没解锁(你 Lv{lv})。先练级~"
            _lv, title, story, fname, loc = q
            f = get(fname)
            st = "✅已完成" if qlv in done else (
                "⭐鱼已在图鉴, quest done 可交差!"
                if fname in self.state.get("caught", {}) else
                f"任务: 钓到 {_disp(f)}（钓场: {loc}, status 可查窗口）")
            return f"📜 Lv{qlv}《{title}》\n{story}\n   {st}"
        return "用法: quests(列表) / quest <等级>(看剧情) / quest done(交差)"

    def _match_region(self, arg: str):
        a = arg.strip().lower()
        if not a:
            return None
        for r in _FOLKLORE_BOOKS:
            if r.lower() == a:
                return r
        for r in _FOLKLORE_BOOKS:
            if a in r.lower():
                return r
        return None

    def books(self) -> str:
        owned = set(self.state.get("books", []))
        pp = self.state.get("scrip_purple", 0)
        out = [f"📖 图鉴书（用🎟紫票买，解锁该大区的稀有鱼）  你的紫票: {pp}"]
        for r, gil_price in sorted(_FOLKLORE_BOOKS.items(), key=lambda x: x[1]):
            n = sum(1 for f in FISH if f["folklore"] and f.get("region") == r)
            price = scrip_mod.book_price(gil_price)
            tag = "✅已有" if r in owned else f"🎟{price}"
            rng = _REGION_RANGE.get(r)
            lvinfo = f"（钓场 Lv{rng[0]}-{rng[1]}）" if rng else ""
            out.append(f"   {tag:>9}  《{r}》{lvinfo} 解锁 {n} 条")
        out.append("   买书: buybook <大区名>   例: buybook Dravania")
        out.append("   🎟紫票来源: collector 模式钓高级鱼(Lv≥"
                   f"{scrip_mod.PURPLE_MIN_LEVEL}) turnin 上交, 或海钓结算")
        return "\n".join(out)

    def buybook(self, arg: str) -> str:
        r = self._match_region(arg)
        if not r:
            return f"没有这本书：{arg}。用 books 看有哪些。"
        if r in self.state.get("books", []):
            return f"《{r}》图鉴书你已经有了。"
        price = scrip_mod.book_price(_FOLKLORE_BOOKS[r])
        pp = self.state.get("scrip_purple", 0)
        if pp < price:
            return (f"🎟紫票不够（需 {price}，你有 {pp}）。"
                    f"collector 模式钓高级鱼上交, 或去海钓攒渔分。")
        self.state["scrip_purple"] = pp - price
        self.state.setdefault("books", []).append(r)
        self._autosave()
        n = sum(1 for f in FISH if f["folklore"] and f.get("region") == r)
        return (f"📖 购得《{r}》图鉴书！(-🎟{price}，剩 {self.state['scrip_purple']})"
                f" 解锁 {n} 条稀有鱼。")

    def gp_status(self) -> str:
        s, now = self.state, self._now()
        out = [f"GP {s['gp']}/{gp.max_gp(s, self._now())}  {gp.bar(s['gp'], gp.max_gp(s, self._now()))}"]
        if gp.cordial_ready(s, now):
            out.append("药(Cordial): 可用 ✅")
        else:
            out.append(f"药(Cordial): 冷却中，{gp.cordial_remaining(s, now)} 秒后可用")
        buffs = [b for b, k in [("鱼眼", "buff_fisheyes"),
                                  ("撒饵", "buff_chum"), ("大鱼确保", "buff_prize"),
                                  ("专一垂钓", "buff_identical"), ("拍击水面", "buff_slap"),
                                  ("多重提钩", "buff_dh")]
                 if s.get(k)]
        if s.get("patience_casts", 0) > 0:
            buffs.insert(0, f"耐心(剩{s['patience_casts']}竿)")
        if s.get("intuition_casts", 0) > 0:
            buffs.insert(0, f"直感(剩{s['intuition_casts']}竿)")
        if buffs:
            out.append("待生效: " + "、".join(buffs))
        out.append(f"（每{gp.GP_REGEN_EVERY}秒回{gp.GP_REGEN_AMOUNT}; "
                   f"patience {gp.PATIENCE_COST} / fisheyes {gp.FISHEYES_COST}"
                   f" / chum {gp.CHUM_COST} / prize {gp.PRIZE_COST}）")
        return "\n".join(out)

    def forecast_cmd(self) -> str:
        """天气预报: 显示当前钓场未来 8 个天气窗口 + 哪些鱼会因此开窗。"""
        from .weather import forecast as _wf
        from .time_kernel import _WEATHER_SPAN
        now = self._now()
        loc = self.state["location"]
        zone = _ZONE_OF.get(loc)
        if not zone:
            return "这里没有天气数据。"
        lv = self.state.get("level", 1)
        fe = self.state.get("buff_fisheyes", False)
        sn = self.state.get("snagging", False)
        bk = self.state.get("books", [])
        # 本钓场需要特定天气的鱼
        weather_fish = {}
        for f in FISH:
            if f["location"] == loc and f["weatherSet"] and _avail(f, fe, sn, bk):
                for w in f["weatherSet"]:
                    weather_fish.setdefault(w, []).append(f)
        windows = _wf(zone, 10, now)
        out = [f"🌤 天气预报 {loc}（{zone}）  每窗 ≈23 分钟"]
        for i, (t, et, w_name) in enumerate(windows):
            elapsed = t - int(now)
            if elapsed <= 0:
                tag = "◀ 现在"
            else:
                m = elapsed // 60
                tag = f"+{m}分钟" if m < 60 else f"+{m//60}h{m%60:02d}m"
            # 这个天气窗口能开哪些特殊鱼？
            bonus = []
            for w_en, fishes in weather_fish.items():
                from .weather import EN2CN
                w_cn = EN2CN.get(w_en, w_en)
                if w_cn == w_name or w_en == w_name:
                    for f in fishes[:3]:
                        bonus.append(_disp(f))
            fish_note = f"  → {'、'.join(bonus[:3])}" if bonus else ""
            marker = "🌟" if bonus else "  "
            out.append(f"   {marker}{tag:>9}  {et}  {w_name}{fish_note}")
        if not weather_fish:
            out.append("   （此处无天气限定鱼，天气仅供赏景）")
        else:
            n = sum(len(v) for v in weather_fish.values())
            out.append(f"   🌟 = 有天气限定鱼开窗（此处共 {n} 种天气鱼）")
        return "\n".join(out)

    def patience(self) -> str:
        s = self.state
        if s["gp"] < gp.PATIENCE_COST:
            return f"GP 不够（需 {gp.PATIENCE_COST}，现有 {s['gp']}）。等回或喝 cordial。"
        s["gp"] -= gp.PATIENCE_COST
        s["patience_casts"] = 3
        self._autosave()
        return (f"🧘 耐心开启(-{gp.PATIENCE_COST} GP，剩 {s['gp']})：接下来 3 竿——\n"
                f"   HQ 概率×3、大幅偏向稀有, 但鱼变得警觉, 咬钩后必须亲手提钩:\n"
                f"   [!]→precision(精准) / [!!][!!!]→powerful(强力), 各 {gp.HOOKSET_COST} GP; 选错=跑鱼。\n"
                f"   (耐心状态只能单竿 cast, 空军/脱钩也算竿数)")

    def identical(self) -> str:
        """专一垂钓: 下一竿死盯刚钓到的鱼种(它开窗就必中; 钓起才消耗)。"""
        s = self.state
        last = s.get("last_catch")
        if not last:
            return "还没有'刚钓到的鱼'——先钓一条再专一。"
        if s["gp"] < gp.IDENTICAL_COST:
            return f"GP 不够（需 {gp.IDENTICAL_COST}，现有 {s['gp']}）。等回或喝 cordial。"
        s["gp"] -= gp.IDENTICAL_COST
        s["buff_identical"] = last
        self._autosave()
        return (f"🎯 专一垂钓(-{gp.IDENTICAL_COST} GP，剩 {s['gp']}): 死盯 "
                f"{_disp(get(last))}——它开窗就必是它咬钩; 不开窗则白等(脱钩不消耗)。")

    def surfaceslap(self) -> str:
        """拍击水面: 把刚钓的鱼种吓跑, 直到钓起下一条鱼为止。"""
        s = self.state
        last = s.get("last_catch")
        if not last:
            return "还没有'刚钓到的鱼'——拍谁的水面呢?"
        if s["gp"] < gp.SLAP_COST:
            return f"GP 不够（需 {gp.SLAP_COST}，现有 {s['gp']}）。等回或喝 cordial。"
        s["gp"] -= gp.SLAP_COST
        s["buff_slap"] = last
        self._autosave()
        return (f"👋 拍击水面(-{gp.SLAP_COST} GP，剩 {s['gp']}): "
                f"{_disp(get(last))} 被吓跑了——在你钓起下一条鱼之前, 它不会再咬钩。")

    def doublehook(self, n: int = 2) -> str:
        """双重/三重提钩: 下一条真正钓起的渔获 ×N。"""
        s = self.state
        cost = gp.DH_COST if n == 2 else gp.TH_COST
        if s["gp"] < cost:
            return f"GP 不够（需 {cost}，现有 {s['gp']}）。等回或喝 cordial。"
        s["gp"] -= cost
        s["buff_dh"] = n
        self._autosave()
        return (f"🪝 {'双' if n == 2 else '三'}重提钩(-{cost} GP，剩 {s['gp']}): "
                f"下一条钓起的渔获 ×{n}——袋子记得留位!")

    def fisheyes(self) -> str:
        s = self.state
        if s["gp"] < gp.FISHEYES_COST:
            return f"GP 不够（需 {gp.FISHEYES_COST}，现有 {s['gp']}）。等回或喝 cordial。"
        s["gp"] -= gp.FISHEYES_COST
        s["buff_fisheyes"] = True
        self._autosave()
        return (f"👁 鱼眼：下一竿无视时段限制（天气仍需满足; 对鱼王无效——原作 5.0 规则）。"
                f"(-{gp.FISHEYES_COST} GP，剩 {s['gp']})")

    def chum(self) -> str:
        """撒饵: 花 GP, 下一竿 HQ 概率翻倍。"""
        s = self.state
        if s["gp"] < gp.CHUM_COST:
            return f"GP 不够（需 {gp.CHUM_COST}，现有 {s['gp']}）。等回或喝 cordial。"
        s["gp"] -= gp.CHUM_COST
        s["buff_chum"] = True
        self._autosave()
        return f"🐟 撒饵：下一竿 HQ 概率翻倍!（-{gp.CHUM_COST} GP，剩 {s['gp']}）"

    def prize(self) -> str:
        """大鱼确保(岸钓): 花 GP, 下一竿只从 Heavy/Legendary 池里抽。"""
        s = self.state
        if s["gp"] < gp.PRIZE_COST:
            return f"GP 不够（需 {gp.PRIZE_COST}，现有 {s['gp']}）。等回或喝 cordial。"
        s["gp"] -= gp.PRIZE_COST
        s["buff_prize"] = True
        self._autosave()
        return (f"🐟 大鱼确保：下一竿只钓大鱼(Heavy/Legendary)!"
                f"（-{gp.PRIZE_COST} GP，剩 {s['gp']}）"
                f"\n   ⚠️ 如果此处没有大鱼, buff 会浪费——先 look 确认有重竿感的鱼。")

    def cordial(self) -> str:
        s, now = self.state, self._now()
        if not gp.cordial_ready(s, now):
            return f"药还在冷却，{gp.cordial_remaining(s, now)} 秒后可喝。"
        before = s["gp"]
        s["gp"] = min(gp.max_gp(s, self._now()), s["gp"] + gp.CORDIAL_RESTORE)
        s["cordial_at"] = now
        self._autosave()
        return f"🧪 喝药：GP {before} → {s['gp']}。(CD {gp.CORDIAL_CD}s)"

    def goto(self, spot: str) -> str:
        a = spot.strip()
        if not a:
            return "goto 后面跟钓场名(中英文都认), 如 goto 太阳海岸。用 spots 查。"
        al = a.lower()
        # 精确匹配: 英文 or 中文
        exact = next((s for s in _SPOTS if s.lower() == al), None)
        if not exact and a in _SPOT_EN_BY_CN:
            en = _SPOT_EN_BY_CN[a]
            exact = en if en in _SPOTS else None
        if exact:
            self.state["location"] = exact
            self._autosave()
            travel = ""
            if self.state.get("active_mount"):
                t_rng = random.Random(hash((exact, self._now())))
                travel = pet_mod.travel_text(self.state, t_rng)
            enc_rng = random.Random(zlib.crc32(exact.encode("utf-8")) * 7919
                                    + int(self._now()))
            enc = enc_mod.roll(self.state, enc_rng, self._now())
            return travel + enc + "已移动。\n" + self.look()
        # 子串模糊匹配: 英文名 + 中文名一起搜
        hits = [s for s in _SPOTS
                if al in s.lower() or a in _SPOT_CN.get(s, "")]
        if len(hits) == 1:
            self.state["location"] = hits[0]
            self._autosave()
            travel = ""
            if self.state.get("active_mount"):
                t_rng = random.Random(hash((hits[0], self._now())))
                travel = pet_mod.travel_text(self.state, t_rng)
            enc_rng = random.Random(zlib.crc32(hits[0].encode("utf-8")) * 7919
                                    + int(self._now()))
            enc = enc_mod.roll(self.state, enc_rng, self._now())
            return travel + enc + "已移动。\n" + self.look()
        if len(hits) > 1:
            names = "\n".join(f"   {s}（{_SPOT_CN.get(s, '?')}）" for s in hits[:8])
            more = f"\n   …还有 {len(hits) - 8} 个" if len(hits) > 8 else ""
            return f"匹配到多个钓场, 请更精确一点:\n{names}{more}"
        return f"没有这个钓场：{spot}。用 spots 看可去的地方(中英文名都认)。"

    def spots(self, arg: str = "") -> str:
        lv = self.state.get("level", 1)
        show_all = arg.strip().lower() in ("all", "全部", "全")
        allspots = sorted(_SPOTS, key=lambda x: (_ZONE_OF[x], _spot_req_level(x), x))
        if show_all:
            shown = allspots
            out = [f"全部钓场（你 Lv{lv}；🔒=等级不够，🔱=叉鱼点）："]
        else:
            shown = [s for s in allspots if _spot_req_level(s) <= lv + 5]
            out = [f"可去的钓场（你 Lv{lv}；含高你≤5级的；共 {len(allspots)} 处，"
                   f"spots all 看全部）："]
        last = None
        for s in shown:
            if _ZONE_OF[s] != last:
                last = _ZONE_OF[s]
                out.append(f"  【{last}】")
            mark = "  ← 你在这" if s == self.state["location"] else ""
            rlv = _spot_req_level(s)
            lock = "🔒" if lv < rlv else "  "
            tag = f"🔱Lv{rlv:>3}" if s in _SPEAR_SPOTS else f"Lv{rlv:>3}"
            cn = _SPOT_CN.get(s, "")
            cn_disp = f"｜{cn}" if cn else ""
            out.append(f"     {lock}{tag}  {s}{cn_disp}{mark}")
        return "\n".join(out)

    def bag(self) -> str:
        c = self.state["caught"]
        lv = self.state.get("level", 1)
        out = [f"🎣 Lv{lv}  XP {self.state.get('xp', 0)}/{leveling.xp_to_next(lv)} ｜ "
               f"💰 {self.state['gil']} gil ｜ 抛竿 {self.state['casts']} ｜ "
               f"图鉴 {len(c)}/{_UNIQUE_NAMES}"]
        rodname = self.state.get("rod")
        if rodname and rodname in gear.RODS:
            r = gear.RODS[rodname]
            out.append(f"   🎣鱼竿: {rodname}（采集{r['gathering']} 鉴别{r['perception']}）")
        else:
            out.append("   🎣鱼竿: 徒手（无鱼竿，rods 逛店买一把）")
        bt = self.state.get("bait")
        nb = self.state.get("bait_stock", {}).get(bt, 0)
        out.append(f"   🪱鱼饵: {bait_mod.disp(bt)}×{nb}" if (bt and nb > 0)
                   else "   🪱鱼饵: 无（baits 买饵）")
        oc = self.state.get("ocean_caught", {})
        inv_n = len(self.state.get("collectables", []))
        cmode = "开" if self.state.get("collector") else "关"
        out.append(f"   🎫白票 {self.state.get('scrip_white', 0)} ｜ "
                   f"🎟紫票 {self.state.get('scrip_purple', 0)} ｜ "
                   f"📦收藏品 {inv_n}/{scrip_mod.COLLECT_CAP}(模式:{cmode})")
        out.append(f"   🚢海钓: 图鉴 {len(oc)}/259 ｜ 航次 {self.state.get('ocean_trips', 0)}"
                   f" ｜ 累计渔分 {self.state.get('ocean_points_total', 0)}"
                   + ("（在船上!）" if self.state.get("ocean") else ""))
        out.append(self._bag_view())
        if c:
            out.append("   —— 岸钓图鉴（累计钓获·荣誉记录, 只增不减; 库存看上面🎒鱼袋）——")
            for name in sorted(c):
                f = get(name)
                out.append(f"   {_disp(f) if f else name} ×{c[name]}")
        else:
            out.append("   （还没岸钓过，cast 试试）")
        if oc:
            out.append(f"   —— 海钓图鉴（{len(oc)}/259）——")
            for name in sorted(oc):
                out.append(f"   🚢 {name} ×{oc[name]}")
        ks = self.state.get("keepsakes", [])
        if ks:
            out.append("   🎁 路上的纪念小物: " + "、".join(ks))
        return "\n".join(out)

    def status(self, name: str) -> str:
        f = get(name)
        if not f:
            o = ocean_mod.fish_status(self, name)      # 试试是不是海钓鱼
            return o if o else f"没有这条鱼：{name}"
        now = self._now()
        recs = get_all(name)
        line_recs = [x for x in recs if x["mode"] == "line"]
        spear_recs = [x for x in recs if x["mode"] == "spear"]
        cur = self.state.get("location")
        out = [f"🐟 {_disp(f)}"]
        if f.get("predators"):
            plist = "、".join(f"{_disp(get(pn)) if get(pn) else pn} ×{c}"
                              for pn, c in f["predators"].items())
            prog = self.state.get("intuition_progress", {})
            it = self.state.get("intuition_casts", 0)
            if it > 0:
                ptxt = f"⚡直感生效中(剩 {it} 竿)——就是现在!"
            else:
                ptxt = "进度 " + " ".join(f"{prog.get(pn, 0)}/{c}"
                                          for pn, c in f["predators"].items())
            out.append(f"   ⚡ 前置(捕鱼人之识): 先钓 {plist} —— {ptxt}")
            out.append(f"      集齐瞬间触发直感({INTUITION_CASTS} 竿), 期间它才肯咬钩; 换钓场不清进度")
        # 逐钓点状态: 任一处开窗就算"现在能钓"(修复: 不再只看数据表第一条)
        if line_recs:
            open_n = sum(1 for x in line_recs if is_catchable(x, now))
            if open_n:
                out.append(f"   ✅ 现在能钓!（{open_n}/{len(line_recs)} 个钓点开窗）")
            else:
                out.append(f"   ❌ 此刻 {len(line_recs)} 个钓点都关窗")
            show = sorted(line_recs, key=lambda x: (x["location"] != cur, x["location"]))
            for x in show[:8]:
                here = "→" if x["location"] == cur else " "
                if is_catchable(x, now):
                    st = "✅开窗中"
                else:
                    nxt = next_window(x, now)
                    if nxt is None:
                        st = "❌近期无窗口"
                    else:
                        mins = int((nxt - now) / 60)
                        st = f"⏳{mins} 分钟后开" if mins > 0 else "⏳马上开"
                cond = time_text(x["startHour"], x["endHour"])
                if x["weatherSet"]:
                    cond += " + " + _w(x["weatherSet"])
                out.append(f"   {here}{x['location']}（Lv{x.get('level') or '?'}）"
                           f" {st}  [{cond}]")
            if len(line_recs) > 8:
                out.append(f"    …还有 {len(line_recs) - 8} 个钓点")
        if spear_recs:
            locs = sorted({x["location"] for x in spear_recs})
            out.append("   🔱 也可叉鱼获得: " + "、".join(locs[:4])
                       + ("…" if len(locs) > 4 else ""))
        # 机制/鱼饵需求(同名鱼共享)
        needs = []
        if f["folklore"] and f.get("region") not in self.state.get("books", []):
            needs.append(f"图鉴书《{f.get('region')}》")
        if f["snagging"]:
            needs.append("钓草")
        if f["fishEyes"]:
            needs.append("鱼眼")
        base = _base_bait(f)
        if base:
            if base in bait_mod.BAITS:
                out.append(f"   鱼饵: {bait_mod.disp(base)}"
                           f"（{bait_mod.price(base)}g，buybait 买）")
            else:
                out.append(f"   鱼饵: {base}（特殊饵/以鱼作饵，暂不卡）")
        if needs:
            out.append(f"   需要: {'、'.join(needs)}")
        # 坐钩链展示: bait 字段若含鱼名 = 坐钩路径
        bait_chain = f.get("bait", [])
        if len(bait_chain) >= 2:
            chain_parts = []
            for b in bait_chain:
                if isinstance(b, list):
                    chain_parts.append("(" + "/".join(str(x) for x in b) + ")")
                else:
                    bf = get(str(b))
                    chain_parts.append(_disp(bf) if bf else str(b))
            out.append("   🐟 坐钩链: " + " → ".join(chain_parts) + f" → 【{_disp(f)}】")
        # 这条鱼本身能被用来坐钩吗?
        for loc_name in sorted({x["location"] for x in line_recs}):
            targets = _mooch_targets(loc_name, f["name"])
            if targets:
                tnames = "、".join(_disp(t) for t in targets[:4])
                more = f"…等 {len(targets)} 种" if len(targets) > 4 else ""
                out.append(f"   🐟 在 {loc_name} 可坐钩: {tnames}{more}")
        # flavor 文案
        _fl = (f.get("flavor_en") if (self.state.get("lang") == "en" and f.get("flavor_en"))
               else f.get("flavor"))
        if _fl:
            out.append(f"   ✍ {_fl}")
        return "\n".join(out)

    # ── 金碟钓鱼赛 (Tournament) ──────────────────────
    _TOURNEY_CASTS = 15          # 限 15 竿
    _TOURNEY_MGP_BASE = 50       # 每分渔分对应 MGP
    _TOURNEY_BONUS_THRESHOLD = 5 # 钓到 5+ 种 → 多样性奖金

    def tournament(self, arg: str = "") -> str:
        """金碟钓鱼赛: 限定竿数内拼总渔分。start 开赛, cast 抛竿, end 提前结束。"""
        a = arg.strip().lower()
        ts = self.state.get("tournament")
        if a in ("start", "开始", "报名"):
            if ts and not ts.get("done"):
                return "你已经在比赛中了! tournament cast 继续, tournament end 结束。"
            self.state["tournament"] = {
                "casts": 0, "max": self._TOURNEY_CASTS,
                "score": 0, "fish": {}, "done": False,
                "loc": self.state["location"],
            }
            self._autosave()
            return (f"🎪 金碟钓鱼赛·开始!\n"
                    f"   规则: {self._TOURNEY_CASTS} 竿内拼总渔分。"
                    f"钓场固定在 {self.state['location']}。\n"
                    f"   tournament cast 抛竿 / tournament end 结束\n"
                    f"   多钓不同种类有多样性奖金!")
        if not ts or ts.get("done"):
            return ("🎪 金碟钓鱼赛\n"
                    "   tournament start —— 在当前钓场开一局限定赛!\n"
                    "   限定竿数内拼总渔分, 奖 MGP(金碟币)。")
        # 比赛中
        if a in ("cast", "c", "抛竿", "钓"):
            if ts["casts"] >= ts["max"]:
                return self._tourney_settle()
            # 用当前位置(锁定在开赛点)
            if self.state["location"] != ts["loc"]:
                self.state["location"] = ts["loc"]
            r = self._cast_once(self._now())
            ts["casts"] += 1
            if r["status"] == "caught":
                name = r["name"]
                size = r["size"]
                pts = max(1, int(size * (500 / _weight(r["fish"]))))  # 稀有鱼高分
                ts["score"] += pts
                ts["fish"][name] = ts["fish"].get(name, 0) + 1
                disp = _disp(r["fish"])
                hq = " ✨HQ" if r["hq"] else ""
                remaining = ts["max"] - ts["casts"]
                out = (f"🎪 [{ts['casts']}/{ts['max']}] {disp}{hq}"
                       f"  {size}吋  +{pts}分  累计{ts['score']}分"
                       f"  剩余{remaining}竿")
                if remaining == 0:
                    out += "\n" + self._tourney_settle()
                return out
            elif r["status"] == "escaped":
                remaining = ts["max"] - ts["casts"]
                return (f"🎪 [{ts['casts']}/{ts['max']}] 脱钩! "
                        f"累计{ts['score']}分  剩余{remaining}竿")
            else:
                remaining = ts["max"] - ts["casts"]
                return (f"🎪 [{ts['casts']}/{ts['max']}] 空竿… "
                        f"累计{ts['score']}分  剩余{remaining}竿")
        if a in ("end", "结束", "弃权"):
            return self._tourney_settle()
        if a in ("", "status", "状态"):
            remaining = ts["max"] - ts["casts"]
            species = len(ts["fish"])
            return (f"🎪 比赛进行中  {ts['casts']}/{ts['max']}竿"
                    f"  累计{ts['score']}分  {species}种鱼\n"
                    f"   tournament cast 继续 / tournament end 结束")
        return "tournament start/cast/end"

    def _tourney_settle(self) -> str:
        """结算钓鱼赛。"""
        ts = self.state["tournament"]
        ts["done"] = True
        score = ts["score"]
        species = len(ts["fish"])
        # 多样性奖金
        bonus = 0
        if species >= self._TOURNEY_BONUS_THRESHOLD:
            bonus = species * 20
        mgp = score * self._TOURNEY_MGP_BASE + bonus
        self.state["mgp"] = self.state.get("mgp", 0) + mgp
        self._autosave()
        out = [f"🎪 ═══ 金碟钓鱼赛·结算 ═══",
               f"   抛竿: {ts['casts']}竿  渔分: {score}",
               f"   钓获: {sum(ts['fish'].values())}条 {species}种"]
        if bonus:
            out.append(f"   🌈 多样性奖金: +{bonus} MGP ({species}种鱼)")
        out.append(f"   💰 获得 {mgp} MGP!  (累计 {self.state['mgp']} MGP)")
        # 按分排名给称谓
        if score >= 200:
            out.append("   🏆 「金碟渔王」—— 你征服了这片海!")
        elif score >= 100:
            out.append("   🥈 「银碟好手」—— 相当出色的表现!")
        elif score >= 50:
            out.append("   🥉 「铜碟新秀」—— 再接再厉!")
        out.append("   tournament start 再来一局!")
        return "\n".join(out)

    # ── 水族箱 (Aquarium) ─────────────────────────────
    _AQUARIUM_CAP = 20          # 最多养 20 条

    def aquarium(self, arg: str = "") -> str:
        """水族箱: add/remove/name 管理。"""
        tank = self.state.setdefault("aquarium", [])
        nicknames = self.state.setdefault("aquarium_names", {})
        a = arg.strip()
        if not a:
            if not tank:
                return ("🐠 水族箱 —— 空的\n"
                        "   用 aquarium add <鱼名> 把你钓过的鱼放进来!")
            out = [f"🐠 水族箱 ({len(tank)}/{self._AQUARIUM_CAP})"]
            for i, name in enumerate(tank, 1):
                f = get(name)
                disp = _disp(f) if f else name
                nick = nicknames.get(name)
                nick_disp = f" 「{nick}」" if nick else ""
                flav = ""
                if f and f.get("flavor"):
                    flav = f" —— {f['flavor'][:40]}{'…' if len(f.get('flavor',''))>40 else ''}"
                out.append(f"   {i}. {disp}{nick_disp}{flav}")
            out.append("   aquarium add/remove/name <鱼名> [昵称] 管理")
            return "\n".join(out)
        parts = a.split(maxsplit=1)
        sub = parts[0].lower()
        name_arg = parts[1].strip() if len(parts) > 1 else ""
        if sub in ("add", "放", "加"):
            if not name_arg:
                return "aquarium add <鱼名> —— 把钓过的鱼放进水族箱。"
            f = get(name_arg)
            if not f:
                return f"没找到这条鱼: {name_arg}"
            if f["name"] not in self.state.get("caught", {}):
                return f"你还没钓到过 {_disp(f)}。先去钓一条!"
            if f["name"] in tank:
                return f"{_disp(f)} 已经在水族箱里了。"
            if len(tank) >= self._AQUARIUM_CAP:
                return f"水族箱满了({self._AQUARIUM_CAP}条)! 先 aquarium remove 腾位置。"
            tank.append(f["name"])
            self._autosave()
            flav = f"\n   ✍ {f['flavor']}" if f.get("flavor") else ""
            return (f"🐠 把 {_disp(f)} 放进了水族箱!{flav}\n"
                    f"   ({len(tank)}/{self._AQUARIUM_CAP})"
                    f"\n   💡 aquarium name {f['name']} <昵称> 可以给它起名字!")
        if sub in ("remove", "拿", "移除"):
            if not name_arg:
                return "aquarium remove <鱼名> —— 从水族箱里拿走一条鱼。"
            f = get(name_arg)
            key = f["name"] if f else name_arg
            if key not in tank:
                return f"{name_arg} 不在水族箱里。"
            tank.remove(key)
            nicknames.pop(key, None)
            self._autosave()
            return f"🐠 把 {_disp(f) if f else key} 从水族箱里拿出来了。({len(tank)}/{self._AQUARIUM_CAP})"
        if sub in ("name", "起名", "昵称", "叫"):
            if not name_arg:
                return "aquarium name <鱼名> <昵称> —— 给水族箱里的鱼起名字。"
            # 最长优先匹配鱼名: 尝试整个 name_arg, 然后逐词缩短
            words = name_arg.split()
            f, new_nick = None, ""
            for i in range(len(words), 0, -1):
                candidate = " ".join(words[:i])
                f = get(candidate)
                if f and f["name"] in tank:
                    new_nick = " ".join(words[i:]).strip()
                    break
            if not f or f["name"] not in tank:
                # 也试试单词匹配
                f = get(words[0])
                new_nick = " ".join(words[1:]).strip()
            key = f["name"] if f else name_arg
            if key not in tank:
                return f"{fish_key} 不在水族箱里。先 aquarium add 放进来。"
            if not new_nick:
                nicknames.pop(key, None)
                self._autosave()
                return f"🐠 清除了 {_disp(f) if f else key} 的昵称。"
            nicknames[key] = new_nick
            self._autosave()
            return f"🐠 {_disp(f) if f else key} 现在叫「{new_nick}」了!"
        return "aquarium add/remove/name <鱼名>，或不带参数查看水族箱。"

    def gallery(self, arg: str = "") -> str:
        """鱼拓展示墙: 展示你钓过的最大 N 条鱼, 附 flavor 文案。"""
        recs = self.state.get("records", {})
        if not recs:
            return "🖼 你的鱼拓展示墙空空如也。先去钓几条鱼吧!"
        n = 10
        if arg.strip().isdigit():
            n = max(1, min(30, int(arg.strip())))
        top = sorted(recs.items(), key=lambda x: -x[1])[:n]
        out = [f"🖼 鱼拓展示墙 —— 你的 Top {len(top)} 最大渔获"]
        for rank, (name, size) in enumerate(top, 1):
            f = get(name)
            disp = _disp(f) if f else name
            tug = f.get("tug", "?") if f else "?"
            tag = {"Light": "!", "Medium": "!!", "Heavy": "!!!", "Legendary": "!!!!"}
            tug_disp = tag.get(tug, "?")
            hq_n = self.state.get("hq_records", {}).get(name, 0)
            hq_tag = " ✨" if hq_n else ""
            line = f"   {rank:>2}. {disp} [{tug_disp}]  {size} 吋{hq_tag}"
            out.append(line)
            if f and f.get("flavor"):
                out.append(f"       ✍ {f['flavor']}")
        total = len(recs)
        out.append(f"   ——共 {total} 种鱼拓(gallery 20 看更多)")
        return "\n".join(out)




    # ── 食物系统 ──────────────────────────────────────
    def foodshop_cmd(self, arg: str = "") -> str:
        """食物商店: 按价格排序 + 分页(一次10道, 省 token)。"""
        foods = sorted(food_mod.SHOP_FOOD, key=lambda x: x["price"])
        per = 10
        pages = (len(foods) + per - 1) // per
        try:
            page = max(1, min(pages, int(arg.strip() or 1)))
        except ValueError:
            page = 1
        out = [f"🍽 食物商店（按价格排序 · 第 {page}/{pages} 页, foodshop <页码> 翻页）"]
        for f in foods[(page - 1) * per: page * per]:
            out.append(f"   {f['name']}/{f['en']}  {f['price']}g  [{food_mod.fmt_food_buff(f)}]")
            out.append(f"     {f['flavor']}")
        out.append(f"   💰你有 {self.state['gil']} gil"
                   " ｜ eat <菜名> 购买并吃掉 / cook 自己做(更便宜)")
        return "\n".join(out)

    def seasoning_cmd(self, arg: str = "") -> str:
        """调味料商店。"""
        a = arg.strip()
        if a:
            # 买调味料
            cn, info = food_mod.find_seasoning(a)
            if not info:
                return f"没找到这种调味料: {a}。seasoning 查看列表。"
            price = info["price"]
            if self.state["gil"] < price:
                return f"gil 不够（需 {price}g，你有 {self.state['gil']}g）。"
            self.state["gil"] -= price
            stock = self.state.setdefault("seasoning_stock", {})
            stock[info["id"]] = stock.get(info["id"], 0) + 1
            self._autosave()
            return f"🧂 买了 {cn}! (-{price}g) 库存: {stock[info['id']]}份\n   {info['desc']}"
        out = ["🧂 调味料商店"]
        stock = self.state.get("seasoning_stock", {})
        for cn, info in food_mod.SEASONINGS.items():
            n = stock.get(info["id"], 0)
            out.append(f"   {cn}  {info['price']}g  库存×{n}")
            out.append(f"     {info['desc']}")
        out.append(f"   💰你有 {self.state['gil']} gil")
        out.append("   seasoning <名字> 购买 / cook <菜名> 用调味料做菜")
        return "\n".join(out)

    def cook_cmd(self, arg: str = "") -> str:
        """烹饪: 你的鱼 + 调味料 → 料理。"""
        a = arg.strip()
        if not a:
            out = ["🍳 烹饪菜单（你的鱼 + 调味料 → 料理）"]
            bag = self.state.get("fish_bag", {})
            stock = self.state.get("seasoning_stock", {})
            for r in food_mod.FISH_RECIPES:
                have_fish = bag.get(r["fish"], 0) > 0 or bag.get(r["fish"] + "|HQ", 0) > 0
                have_sea = stock.get(r["seasoning"], 0) > 0
                fish_tag = "✅" if have_fish else "❌"
                sea_tag = "✅" if have_sea else "❌"
                sea_name = next((cn for cn, i in food_mod.SEASONINGS.items() if i["id"] == r["seasoning"]), r["seasoning"])
                out.append(f"   {r['name']}/{r['en']}  [{food_mod.fmt_food_buff(r)}]")
                out.append(f"     鱼:{fish_tag}{r['fish']}  调味:{sea_tag}{sea_name}")
            out.append("   cook <菜名> 开始做!")
            return "\n".join(out)
        recipe = food_mod.find_recipe(a)
        if not recipe:
            return f"没找到这道菜: {a}。cook 查看菜单。"
        fish_name = recipe["fish"]
        bag = self.state.get("fish_bag", {})
        if bag.get(fish_name, 0) <= 0 and bag.get(fish_name + "|HQ", 0) <= 0:
            return (f"🎒 袋里没有 {fish_name}! 先钓一条——"
                    f"图鉴里有≠袋里有, 做菜用的是袋里的鱼。")
        stock = self.state.get("seasoning_stock", {})
        if stock.get(recipe["seasoning"], 0) <= 0:
            sea_name = next((cn for cn, i in food_mod.SEASONINGS.items() if i["id"] == recipe["seasoning"]), recipe["seasoning"])
            return f"缺少 {sea_name}! seasoning {sea_name} 去买一份。"
        # 消耗材料(从鱼袋取, NQ 优先; 图鉴只增不减)
        self._bag_take(fish_name)
        stock[recipe["seasoning"]] -= 1
        if stock[recipe["seasoning"]] <= 0:
            stock.pop(recipe["seasoning"], None)
        # 做好了, 放进背包
        inventory = self.state.setdefault("food_inventory", {})
        inventory[recipe["name"]] = inventory.get(recipe["name"], 0) + 1
        self._autosave()
        return (f"🍳 做好了! 【{recipe['name']}】\n"
                f"   {recipe['flavor']}\n"
                f"   → 已放入背包(×{inventory[recipe['name']]})  eat {recipe['name']} 开吃!")

    def eat_cmd(self, arg: str = "") -> str:
        """吃东西: 从背包吃自己做的菜, 或从商店买成品直接吃。"""
        a = arg.strip()
        if not a:
            inv = self.state.get("food_inventory", {})
            buff = food_mod.get_active_buff(self.state, self._now())
            out = ["🍽 你的食物"]
            if buff:
                remain = int(buff["expires"] - self._now())
                out.append(f"   当前 buff: {buff['food_name']} (剩余 {remain//60}分{remain%60}秒)")
            if inv:
                for name, n in inv.items():
                    out.append(f"   📦 {name} ×{n}")
            else:
                out.append("   背包里没有食物。cook 做菜 / foodshop 买成品")
            out.append("   eat <菜名> 吃掉(会覆盖当前 buff)")
            return "\n".join(out)
        # 先查背包里的自制食物
        inv = self.state.get("food_inventory", {})
        recipe = food_mod.find_recipe(a)
        if recipe and inv.get(recipe["name"], 0) > 0:
            inv[recipe["name"]] -= 1
            if inv[recipe["name"]] <= 0:
                inv.pop(recipe["name"], None)
            food_mod.apply_buff(self.state, recipe, self._now())
            self._autosave()
            return (f"🍽 你开始吃 {recipe['name']}——\n"
                    f"   {recipe['eat']}\n"
                    f"   ✨ buff 生效! {food_mod.fmt_food_buff(recipe)}  (持续30分钟)")
        # 再查商店成品
        shop = food_mod.find_shop_food(a)
        if shop:
            if self.state["gil"] < shop["price"]:
                return f"gil 不够（需 {shop['price']}g，你有 {self.state['gil']}g）。"
            self.state["gil"] -= shop["price"]
            food_mod.apply_buff(self.state, shop, self._now())
            self._autosave()
            return (f"🍽 你花 {shop['price']}g 买了 {shop['name']}——\n"
                    f"   {shop['eat']}\n"
                    f"   ✨ buff 生效! {food_mod.fmt_food_buff(shop)}  (持续30分钟)")
        # 也找背包里其它自制的
        if a in inv and inv[a] > 0:
            recipe = food_mod.find_recipe(a)
            if recipe:
                return self.eat_cmd(recipe["name"])
        return f"找不到 {a}。eat 查看背包 / foodshop 看商店 / cook 看菜单。"

    # ── 宠物 & 坐骑 ──────────────────────────────────
    def pets_cmd(self, arg: str = "") -> str:
        """查看宠物收藏。"""
        owned = set(self.state.get("pets", []))
        active = self.state.get("active_pet")
        nicknames = self.state.get("pet_names", {})
        _a = arg.strip()
        if _a.lower().startswith(("name ", "取名 ", "改名 ")):
            nick = _a.split(maxsplit=1)[1].strip()[:12]
            act = self.state.get("active_pet")
            if not act:
                return "先 summon 召唤一只宠物, 再给它取名~"
            self.state.setdefault("pet_names", {})[act] = nick
            self._autosave()
            p0 = pet_mod.get_pet(act)
            return f"🐾 好名字! 从今天起, {p0['name']} 就叫「{nick}」了。"
        if _a.lower().startswith(("buy ", "兑换 ", "买 ")):
            arg = _a.split(maxsplit=1)[1]      # `pets buy <id>` 与 `pets <id>` 等效
        if arg.strip().lower() in ("buy", "兑换", "买"):
            # MGP 兑换列表
            mgp = self.state.get("mgp", 0)
            shop = [p for p in pet_mod.PETS if p["source"] == "mgp"]
            out = [f"🎪 宠物兑换(MGP: {mgp})"]
            for p in shop:
                if p["id"] in owned:
                    out.append(f"   ✅ {p['name']} —— 已拥有")
                else:
                    out.append(f"   🔒 {p['name']}（{p['mgp_cost']} MGP）—— {p['desc']}")
                    out.append(f"      pets buy {p['id']}")
            return "\n".join(out)
        if arg.strip():
            # 尝试 MGP 购买
            pid = arg.strip()
            result = pet_mod.buy_pet(self.state, pid)
            if result:
                self._autosave()
                p = pet_mod.get_pet(pid)
                return f"🐾 花 {p['mgp_cost']} MGP 兑换了宠物「{result}」!\n   {p['desc']}\n   💡 summon {result} 召唤!"
            return f"兑换失败——可能已拥有、MGP 不够或 id 不对。pets buy 查看可兑换列表。"
        # 总览
        out = ["🐾 宠物收藏"]
        for p in pet_mod.PETS:
            if p["id"] in owned:
                nick = nicknames.get(p["id"])
                nick_d = f"「{nick}」" if nick else ""
                act = " ← 当前跟随" if p["id"] == active else ""
                out.append(f"   ✅ {p['name']}{nick_d} —— {p['desc'][:30]}…{act}")
            else:
                if p["source"] == "fish":
                    lock = f"钓到 {p['fish']}"
                elif p["source"] == "ach":
                    req = p.get("req_caught") or p.get("req_ocean", 0)
                    lock = f"图鉴 {req} 种"
                else:
                    lock = f"{p.get('mgp_cost', '?')} MGP"
                out.append(f"   🔒 ??? —— {lock}")
        out.append(f"   共 {len(owned)}/{len(pet_mod.PETS)}  summon <名字> 召唤 / pet 互动")
        return "\n".join(out)

    def mounts_cmd(self, arg: str = "") -> str:
        """查看坐骑收藏。"""
        owned = set(self.state.get("mounts", []))
        active = self.state.get("active_mount")
        nicknames = self.state.get("mount_names", {})
        _a = arg.strip()
        if _a.lower().startswith(("name ", "取名 ", "改名 ")):
            nick = _a.split(maxsplit=1)[1].strip()[:12]
            act = self.state.get("active_mount")
            if not act:
                return "先 ride 骑上一头坐骑, 再给它取名~"
            self.state.setdefault("mount_names", {})[act] = nick
            self._autosave()
            m0 = pet_mod.get_mount(act)
            return f"🐎 好名字! 从今天起, {m0['name']} 就叫「{nick}」了。"
        if _a.lower().startswith(("buy ", "兑换 ", "买 ")):
            arg = _a.split(maxsplit=1)[1]      # `mounts buy <id>` 与 `mounts <id>` 等效
        if arg.strip().lower() in ("buy", "兑换", "买"):
            mgp = self.state.get("mgp", 0)
            shop = [m for m in pet_mod.MOUNTS if m["source"] == "mgp"]
            out = [f"🎪 坐骑兑换(MGP: {mgp})"]
            for m in shop:
                if m["id"] in owned:
                    out.append(f"   ✅ {m['name']} —— 已拥有")
                else:
                    out.append(f"   🔒 {m['name']}（{m['mgp_cost']} MGP）—— {m['desc']}")
                    out.append(f"      mounts buy {m['id']}")
            return "\n".join(out)
        if arg.strip():
            mid = arg.strip()
            result = pet_mod.buy_mount(self.state, mid)
            if result:
                self._autosave()
                m = pet_mod.get_mount(mid)
                return f"🐎 花 {m['mgp_cost']} MGP 兑换了坐骑「{result}」!\n   {m['desc']}\n   💡 ride {result} 骑上出发!"
            return f"兑换失败。mounts buy 查看可兑换列表。"
        out = ["🐎 坐骑收藏"]
        for m in pet_mod.MOUNTS:
            if m["id"] in owned:
                nick = nicknames.get(m["id"])
                nick_d = f"「{nick}」" if nick else ""
                act = " ← 当前骑乘" if m["id"] == active else ""
                out.append(f"   ✅ {m['name']}{nick_d} —— {m['desc'][:30]}…{act}")
            else:
                if m["source"] == "ach":
                    req = m.get("req_caught") or m.get("req_ocean", 0)
                    lock = f"图鉴 {req} 种"
                else:
                    lock = f"{m.get('mgp_cost', '?')} MGP"
                out.append(f"   🔒 ??? —— {lock}")
        out.append(f"   共 {len(owned)}/{len(pet_mod.MOUNTS)}  ride <名字> 骑乘 / dismount 下马")
        return "\n".join(out)

    def summon_cmd(self, arg: str = "") -> str:
        """召唤宠物。"""
        if not arg.strip():
            if self.state.get("active_pet"):
                p = pet_mod.get_pet(self.state["active_pet"])
                nick = self.state.get("pet_names", {}).get(self.state["active_pet"], p["name"] if p else "?")
                return f"🐾 当前宠物:「{nick}」。summon <名字> 切换, summon off 收起。"
            return "summon <宠物名> 召唤一只宠物跟着你! pets 查看拥有的宠物。"
        if arg.strip().lower() in ("off", "收起", "取消"):
            self.state["active_pet"] = None
            self._autosave()
            return "🐾 宠物收起了。"
        p = pet_mod.find_pet(arg.strip())
        if not p:
            return f"找不到这只宠物: {arg.strip()}"
        if p["id"] not in self.state.get("pets", []):
            return f"你还没有「{p['name']}」。pets 查看如何获得。"
        self.state["active_pet"] = p["id"]
        self._autosave()
        nick = self.state.get("pet_names", {}).get(p["id"], p["name"])
        return f"🐾 「{nick}」来到了你身边! {p['desc']}\n   💡 pet 和它互动 / summon off 收起"

    def ride_cmd(self, arg: str = "") -> str:
        """骑坐骑。"""
        if not arg.strip():
            if self.state.get("active_mount"):
                m = pet_mod.get_mount(self.state["active_mount"])
                nick = self.state.get("mount_names", {}).get(self.state["active_mount"], m["name"] if m else "?")
                return f"🐎 当前坐骑:「{nick}」。ride <名字> 切换, dismount 下马。"
            return "ride <坐骑名> 骑上出发! mounts 查看拥有的坐骑。"
        m = pet_mod.find_mount(arg.strip())
        if not m:
            return f"找不到这个坐骑: {arg.strip()}"
        if m["id"] not in self.state.get("mounts", []):
            return f"你还没有「{m['name']}」。mounts 查看如何获得。"
        self.state["active_mount"] = m["id"]
        self._autosave()
        nick = self.state.get("mount_names", {}).get(m["id"], m["name"])
        return f"🐎 你骑上了「{nick}」! {m['desc']}\n   💡 goto 移动时会有旅行描写 / dismount 下马"

    def diary(self) -> str:
        """钓鱼日志: 今日/本次 session 的活动回顾。"""
        import datetime
        now = self._now()
        today = datetime.datetime.fromtimestamp(now).strftime("%Y-%m-%d")
        s = self.state
        log = s.get("diary_log", {})
        entry = log.get(today, {})
        if not entry:
            return (f"📖 钓鱼日志 · {today}\n"
                    f"   今天还没钓过鱼呢! cast 开始吧。")
        casts = entry.get("casts", 0)
        caught_n = entry.get("caught", 0)
        new_fish = entry.get("new_fish", [])
        spots = entry.get("spots", [])
        gil = entry.get("gil", 0)
        xp = entry.get("xp", 0)
        out = [f"📖 钓鱼日志 · {today}"]
        out.append(f"   抛竿 {casts} 次  钓获 {caught_n} 条  +{gil}g +{xp}xp")
        if new_fish:
            names = "、".join(new_fish[:8])
            more = f"…等 {len(new_fish)} 种" if len(new_fish) > 8 else ""
            out.append(f"   ✨新图鉴 {len(new_fish)} 种: {names}{more}")
        if spots:
            out.append(f"   📍 去过: {'、'.join(spots[:6])}")
        last_loc = s.get("location", "?")
        out.append(f"   现在在: {last_loc}")
        return "\n".join(out)

    def recommend(self) -> str:
        """钓场推荐: 根据等级 + 图鉴缺口 + 当前开窗, 推荐去哪里最划算。"""
        now = self._now()
        lv = self.state.get("level", 1)
        caught = set(self.state.get("caught", {}).keys())
        fe = self.state.get("buff_fisheyes", False)
        sn = self.state.get("snagging", False)
        bk = self.state.get("books", [])
        # 每个钓场: 统计此刻能钓到的鱼数 + 新图鉴数
        scores = []
        seen = set()
        for loc in _SPOTS:
            if loc in _SPEAR_SPOTS:
                continue
            req_lv = _spot_req_level(loc)
            if req_lv > lv + 3:                    # 超太多级就跳过
                continue
            if loc in seen:
                continue
            seen.add(loc)
            here = [f for f in FISH if f["location"] == loc]
            openf = [f for f in here if _avail(f, fe, sn, bk) and is_catchable(f, now)]
            new = [f for f in openf if f["name"] not in caught]
            if not openf:
                continue
            # 得分: 新图鉴数 × 10 + 开窗鱼数 + 有大鱼加分
            big = sum(1 for f in openf if f.get("tug") in ("Heavy", "Legendary"))
            score = len(new) * 10 + len(openf) + big * 5
            zone = _ZONE_OF.get(loc, "")
            cn = _SPOT_CN.get(loc, "")
            scores.append((score, loc, cn, zone, req_lv, len(openf), len(new), big))
        if not scores:
            return "暂时没有推荐——所有你等级可去的钓场都没鱼开窗。换个时间再来?"
        scores.sort(key=lambda x: -x[0])
        out = [f"🧭 钓场推荐（你 Lv{lv}，基于此刻开窗 + 图鉴缺口）："]
        for i, (sc, loc, cn, zone, rlv, n_open, n_new, n_big) in enumerate(scores[:5]):
            cn_disp = f"｜{cn}" if cn else ""
            tags = []
            if n_new:
                tags.append(f"✨新图鉴×{n_new}")
            if n_big:
                tags.append(f"🐟大鱼×{n_big}")
            tag = "  ".join(tags)
            mark = " ← 你在这" if loc == self.state["location"] else ""
            out.append(f"   {i+1}. Lv{rlv} {loc}{cn_disp}（{zone}）"
                       f" 开窗{n_open}种  {tag}{mark}")
        out.append("   goto <钓场名> 出发!")
        return "\n".join(out)

    def save_cmd(self) -> str:
        p = self._autosave()
        return f"已存档 -> {p.name}"

    def load_cmd(self) -> str:
        self.state = save_mod.load(self.slot)
        self._migrate()
        return "已读档。\n" + self.bag()

    def help(self) -> str:
        if self.state.get("lang") == "en":
            return (
                "Commands: look / cast [N] [stop=rare] / mooch(live-bait, chains) / spear / "
                "goto <spot> / spots [all] / bag / records / status <fish> / summary / "
                "recommend / diary\n"
                "      🎒 sell <fish> [N|all] / sell all / sell light — catches go to the bag; "
                "selling is your income; a full bag releases new species!\n"
                "      ⚔ precision([!]) / powerful([!!][!!!], 50GP each) / hook(free) — hookset "
                "window under Patience or on any legendary bite; distraction loses the fish\n"
                "      ⚡ Big fish need predators first: status <fish> shows list & progress; "
                "completing the set triggers Intuition (8 casts, survives travel)\n"
                "      identical(350GP·lock next bite to last catch) / slap(150GP·ban last catch) / "
                "doublehook·triplehook(400/700GP·next catch ×2/×3) / pets|mounts name <nick>\n"
                "      gp / forecast / patience(3 casts·HQ×3·manual hooksets) / fisheyes / chum / "
                "prize / snagging / cordial / books / buybook <region> / rods / buyrod / equiprod / "
                "baits / buybait / bait <name> / save / load / rescue\n"
                "      collector on|off / turnin · eshop [slot] / ebuy / wear / gearset / recycle · "
                "mshop / mbuy / mcraft / meld\n"
                "      🍳 foodshop [page] / seasoning / cook [dish] / eat [dish] · 🐾 pets / mounts / "
                "summon / ride / dismount / pet\n"
                "      quests / quest <lv> / quest done(Lv15 grants saddlebag) · tasks [claim] · "
                "ach · title · gallery · aquarium · tournament · ocean ...\n"
                "      💡 chain with semicolons: cast 10; sell all; look · lang cn = Chinese")
        return ("命令: look(看此处·含稀有度标签) / cast [N] [stop=rare](抛竿,可批量) / "
                "mooch(以鱼钓鱼·坐钩·活饵从鱼袋消耗) / "
                "spear(叉鱼) / goto <钓场> / "
                "spots [all](钓场) / bag(🎒鱼袋+图鉴+点数) / records(尺寸记录) / "
                "status <鱼名>(含坐钩链) / summary(成果回顾) / recommend(钓场推荐) / "
                "diary(今日日志)\n"
                "      🎒 sell <鱼名> [N|all] / sell all(全卖) / sell light(只卖[!]杂鱼) —— "
                "渔获入袋, 卖出才有钱; 袋满钓到新鱼种只能放生!\n"
                "      ⚔ precision(精准·配[!]) / powerful(强力·配[!!][!!!], 各50GP) / hook(硬拉免费)"
                " —— 耐心中或鱼王咬钩的提钩窗口, 分神=跑鱼\n"
                "      ⚡ 鱼王多有前置: 先钓齐前置鱼触发捕鱼人之识(8竿), status <鱼王> 查清单进度\n"
                "      identical(专一垂钓·350GP·下竿必中刚钓的鱼种) / slap(拍击水面·150GP·踢走某鱼) / "
                "doublehook·triplehook(双/三重提钩·400/700GP·一竿多条) / "
                "pets|mounts name <昵称>(给宠物坐骑取名)\n"
                "      gp(看精力) / forecast(天气预报·蹲鱼利器) / patience(耐心·3竿HQ×3偏稀有·须手动提钩) / "
                "fisheyes(无视时段) / chum(撒饵·HQ翻倍) / prize(大鱼确保·只钓大鱼) / "
                "snagging(钓草开关) / cordial(喝药) / books(图鉴书) / "
                "buybook <大区>(买书) / rods(鱼竿店) / buyrod <名字> / equiprod <名字> / "
                "baits(鱼饵店) / buybait <饵名> / bait <饵名>(换饵) / "
                "save / load / rescue(存档坏了回滚备份)\n"
                "      collector on/off(收藏品模式·钓鱼换票) / turnin(上交收藏品) / "
                "books 现用🎟紫票购买\n"
                "      eshop [部位](装备店·全身11部位) / ebuy <名> / wear <名>(穿) / "
                "gearset(全身一览) / recycle <名>(分解回收)\n"
                "      mshop(魔晶石店) / mbuy <名> / mcraft <名>(碎片合成) / "
                "meld <装备> <魔晶石>(镶嵌·禁断🎆)\n"
                "      🍳 foodshop [页](食物店·分页) / seasoning [名](调味料店) / "
                "cook [菜名](袋中鱼+调味料→料理) / eat [菜名](吃·30分钟buff)\n"
                "      🐾 pets [buy <id>](宠物收藏/兑换) / mounts [buy <id>](坐骑) / "
                "summon <名>(召唤) / ride <名>(骑) / dismount(下马) / pet(摸摸互动)\n"
                "      quests(职业任务·Lv15交差送鞍囊🎒+70格) / quest <等级>(看剧情) / "
                "quest done(交差)\n"
                "      tasks(日随/周随·全球同一份·真实时钟刷新) / tasks claim(领奖)\n"
                "      🚶 encounter [on|off](路遇小事件·goto赶路时偶遇互助/拾遗, 默认开)\n"
                "      ach(岸钓成就·进度一览) / title(称号·佩戴/查看)\n"
                "      gallery [N](鱼拓展示墙·最大渔获排行) / "
                "aquarium [add|remove <鱼名>](水族箱·养鱼观赏)\n"
                "      tournament [start|cast|end](🎪金碟钓鱼赛·限定竿数拼渔分·赢MGP)\n"
                "      ocean(海钓班次/状态) / ocean board <indigo|ruby>(登船) / "
                "ocean cast [N] / ocean bait <饵名> / ocean routes / ocean quit\n"
                "      💡 分号串联: cast 10; sell all; look ——"
                "一条命令走多步, 省 token\n"
                "      💡 中文全支持: 看/抛竿/卖鱼/去/钓场/背包/查/耐心/鱼眼/撒饵/大鱼确保/"
                "喝药/做菜/吃/存档/帮助…")

    def _bar(self) -> str:
        """一行状态栏: AI 每次命令后都能看到关键数据, 不用额外 bag。"""
        s = self.state
        lv = s.get("level", 1)
        bt = s.get("bait")
        nb = s.get("bait_stock", {}).get(bt, 0)
        bait_disp = f"🪱×{nb}" if bt and nb > 0 else "🪱无饵"
        caught_n = len(s.get("caught", {}))
        oc_n = len(s.get("ocean_caught", {}))
        oc_tag = f"+🚢{oc_n}" if oc_n else ""
        food_tag = food_mod.buff_summary(s, self._now())
        if food_tag:
            food_tag = " " + food_tag
        return (f"📊 Lv{lv} {s.get('xp', 0)}/{leveling.xp_to_next(lv)}xp"
                f" | 💰{s['gil']}g | 🎒{len(s.get('fish_bag', {}))}/{self._bag_cap()} | {bait_disp}"
                f" | GP {s['gp']}/{gp.max_gp(s, self._now())}"
                f" | 图鉴 {caught_n}{oc_tag}/{_UNIQUE_NAMES}"
                + (f" | 🎖{s['active_title']}" if s.get("active_title") else ""))

    def summary(self) -> str:
        """本次 session 成果回顾(基于存档累计数据)。"""
        s = self.state
        lv = s.get("level", 1)
        c = s.get("caught", {})
        oc = s.get("ocean_caught", {})
        total_fish = sum(c.values())
        total_ocean = sum(oc.values())
        out = [f"📋 成果回顾:"]
        out.append(f"   等级 Lv{lv}  经验 {s.get('xp', 0)}/{leveling.xp_to_next(lv)}")
        out.append(f"   💰 {s['gil']} gil  🎫{s.get('scrip_white', 0)}"
                   f" 🎟{s.get('scrip_purple', 0)}"
                   + (f"  🎪{s.get('mgp', 0)} MGP" if s.get('mgp') else ""))
        out.append(f"   总抛竿 {s.get('casts', 0)} 次  岸钓图鉴 {len(c)}/{_UNIQUE_NAMES}"
                   f"  海钓图鉴 {len(oc)}/259")
        out.append(f"   累计钓获 {total_fish} 条(岸)  {total_ocean} 条(海)"
                   f"  航次 {s.get('ocean_trips', 0)}")
        recs = s.get("records", {})
        if recs:
            top = sorted(recs.items(), key=lambda x: -x[1])[:3]
            names = "、".join(f"{nm} {inch}吋" for nm, inch in top)
            out.append(f"   🏆 尺寸三甲: {names}")
        return "\n".join(out)

    # --- 解析分发 -----------------------------------------
    def _loc(self, out: str) -> str:
        """输出本地化: lang=en 时过一遍 i18n 短语表(engine/i18n.py, 欢迎补词条)。"""
        if self.state.get("lang") == "en":
            return i18n_mod.translate(out)
        return out

    def cmd(self, text: str) -> str:
        text = (text or "").strip()
        # ── 分号串联: "cast 10; goto Costa del Sol; look" 一次走多步 ──
        # 省 token 利器——AI 玩家一条命令做三件事
        if ";" in text:
            parts = [p.strip() for p in text.split(";") if p.strip()]
            if len(parts) > 1:
                results = []
                for i, sub in enumerate(parts):
                    results.append(self._cmd_single(sub))
                return self._loc(("\n" + "─" * 36 + "\n").join(results))
            # 只有一段(前后带分号): 当成普通命令
            text = parts[0] if parts else ""
        return self._loc(self._cmd_single(text))

    def _cmd_single(self, text: str) -> str:
        """执行单条命令(从 cmd 拆出, 供分号串联逐条调用)。"""
        text = (text or "").strip()
        if not self.state.get("ocean"):
            gp.sync(self.state, self._now())
        if not text:
            return self.help()
        # ── 天气转换检测(非船上时, 天气变了就播一句氛围) ──
        weather_note = ""
        if not self.state.get("ocean"):
            loc = self.state.get("location", "")
            zone = _ZONE_OF.get(loc)
            if zone:
                now_w = current_weather(zone, self._now())
                last_w = self.state.get("_last_weather")
                if last_w and now_w != last_w:
                    weather_note = _weather_transition(last_w, now_w) + "\n"
                self.state["_last_weather"] = now_w
        # ── 欢迎回来(session 首条命令) ──
        welcome = ""
        if not self._welcomed:
            self._welcomed = True
            if self._welcome_msg:
                welcome = self._welcome_msg + "\n\n"
                if self._rest_xp > 0:
                    leveling.add_xp(self.state, self._rest_xp)
        result = self._check_hook_distraction(text) + self._cmd_inner(text)
        # ── 成就检查(每条命令后) ──
        ach_news = ach_mod.check_new(self.state)
        ach_lines = ""
        if ach_news:
            for _aid, aname, aflav in ach_news:
                ach_lines += f"\n🏅 成就达成! 「{aname}」—— {aflav}"
        # ── 宠物/坐骑里程碑解锁 ──
        for p_new, p_reason in pet_mod.check_new_pets(self.state):
            ach_lines += f"\n🐾 获得宠物!「{p_new['name']}」—— {p_new['desc']}"
            ach_lines += f"\n   💡 summon {p_new['name']} 召唤它跟着你!"
        for m_new, m_reason in pet_mod.check_new_mounts(self.state):
            ach_lines += f"\n🐎 获得坐骑!「{m_new['name']}」—— {m_new['desc']}"
            ach_lines += f"\n   💡 ride {m_new['name']} 骑上出发!"
        # ── 里程碑称号检查(和成就一起) ──
        title_news = title_mod.check_milestones(self.state)
        for tname, tflav in title_news:
            ach_lines += f"\n🎖 称号解锁!「{tname}」—— {tflav}"
        # ── 更新 last_seen(下次启动用) + 确保存盘(AI模式每命令独立进程) ──
        self.state["last_seen"] = self._now()
        # ── 钓鱼日志: 记录今日去过的钓场 ──
        import datetime as _dt
        _today = _dt.datetime.fromtimestamp(self._now()).strftime("%Y-%m-%d")
        _dlog = self.state.setdefault("diary_log", {}).setdefault(_today,
                {"casts": 0, "caught": 0, "new_fish": [], "spots": [], "gil": 0, "xp": 0})
        _loc = self.state.get("location", "")
        if _loc and _loc not in _dlog["spots"]:
            _dlog["spots"].append(_loc)
        self._autosave()
        # help 不附状态栏(已经有命令列表); 其余一律附
        verb = text.split()[0].lower()
        if verb in ("help", "h", "帮助"):
            return weather_note + welcome + result + ach_lines
        return weather_note + welcome + result + ach_lines + "\n" + self._bar()

    def _check_hook_distraction(self, text: str) -> str:
        """提钩窗口纪律: 发无关命令 = 分神, 鱼跑了。"""
        if not self.state.get("hook_pending"):
            return ""
        parts = text.split()
        verb = parts[0].lower() if parts else ""
        safe = ("hook", "提钩", "硬拉", "precision", "精准", "精准提钩",
                "powerful", "强力", "强力提钩", "cordial", "喝药",
                "gp", "精力", "help", "h", "帮助")
        if verb in safe:
            return ""
        lost = self.state["hook_pending"]
        self.state["hook_pending"] = None
        self.state["escapes"] = self.state.get("escapes", 0) + 1
        lf = get(lost["name"])
        return (f"🎣💨 你分神了——竿尖一轻，"
                f"【{_disp(lf) if lf else lost['name']}】吐钩而去……\n\n")

    def _cmd_inner(self, text: str) -> str:
        """实际分发(cmd() 负责 gp.sync + 追加 _bar, 这里只管路由)。"""
        parts = text.split(maxsplit=1)
        verb = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        # 非 mooch 命令时清除坐钩窗口(坐钩只在"刚钓到鱼"那一刻有效)
        if verb not in ("mooch", "坐钩"):
            self.state["mooch_pending"] = None
        if verb in ("ocean", "sail", "海钓"):
            return ocean_mod.handle(self, arg)
        if self.state.get("ocean"):               # 在船上: 转接/拦截
            if verb in ("cast", "c"):
                return ocean_mod.handle(self, f"cast {arg}".strip())
            if verb in ("look", "l"):
                return ocean_mod.handle(self, "")
            if verb in ("goto", "go", "spear", "gig"):
                return "🚢 你在「不倦号」上, 四面都是海。ocean cast 继续钓, 或 ocean quit 弃船。"
            if verb in ("patience", "fisheyes", "chum", "prize"):
                return "🚢 你在船上，岸钓技能在这里不管用。海上用 ocean dh / ocean th / ocean prize。"
        table = {
            "look": self.look, "l": self.look, "看": self.look,
            "bag": self.bag, "inv": self.bag, "inventory": self.bag,
            "背包": self.bag, "渔获": self.bag,
            "records": self.records, "record": self.records, "记录": self.records,
            "rods": self.rods, "鱼竿": self.rods, "竿店": self.rods,
            "baits": self.baits, "baitshop": self.baits, "鱼饵": self.baits, "饵店": self.baits,
            "gp": self.gp_status, "精力": self.gp_status,
            "forecast": self.forecast_cmd, "天气": self.forecast_cmd, "预报": self.forecast_cmd,
            "books": self.books, "图鉴书": self.books,
            "patience": self.patience, "耐心": self.patience,
            "fisheyes": self.fisheyes, "鱼眼": self.fisheyes,
            "chum": self.chum, "撒饵": self.chum,
            "prize": self.prize, "大鱼确保": self.prize, "大鱼": self.prize,
            "cordial": self.cordial, "喝药": self.cordial,
            "save": self.save_cmd, "存档": self.save_cmd,
            "load": self.load_cmd, "读档": self.load_cmd,
            "help": self.help, "h": self.help, "帮助": self.help,
            "summary": self.summary, "回顾": self.summary,
        }
        if verb in ("encounter", "encounters", "路遇"):
            return enc_mod.toggle(self.state, arg)
        if verb in ("ach", "achievements", "成就"):
            return ach_mod.view(self.state)
        if verb in ("mooch", "坐钩"):
            return self.mooch()
        if verb in ("title", "称号"):
            if arg:
                return title_mod.equip(self.state, arg)
            return title_mod.view(self.state)
        if verb in ("cast", "c", "抛竿", "钓"):
            return self.cast(arg)
        if verb in ("spear", "gig", "叉", "叉鱼"):
            return self.spear(arg)
        if verb in ("spots", "where", "钓场"):
            return self.spots(arg)
        if verb in ("goto", "go", "去", "前往"):
            return self.goto(arg)
        if verb in ("status", "st", "查", "查询"):
            return self.status(arg)
        if verb in ("snagging", "snag", "钓草"):
            return self.snagging(arg)
        if verb in ("collector", "collect", "收藏"):
            return self.collector(arg)
        if verb in ("turnin", "上交"):
            return self.turnin()
        if verb in ("sell", "卖", "卖鱼"):
            return self.sell(arg)
        if verb in ("rescue", "回档", "救档"):
            return self.rescue_cmd()
        if verb in ("lang", "language", "语言"):
            a = arg.strip().lower()
            if a in ("en", "english", "英文"):
                self.state["lang"] = "en"
                self._autosave()
                return ("🌐 Output language: English. Structural text is translated; "
                        "flavor/story lines stay Chinese for now (fish flavor uses "
                        "English where available). `lang cn` switches back. "
                        "Phrase table: engine/i18n.py — PRs welcome!")
            if a in ("cn", "zh", "中文"):
                self.state.pop("lang", None)
                self._autosave()
                return "🌐 输出语言已切回中文。(lang en 可换英文)"
            cur = "en" if self.state.get("lang") == "en" else "cn"
            return f"🌐 当前语言: {cur}。用法: lang en / lang cn"
        if verb in ("hook", "提钩", "硬拉"):
            return self.resolve_hook("hook")
        if verb in ("precision", "精准", "精准提钩"):
            return self.resolve_hook("precision")
        if verb in ("powerful", "强力", "强力提钩"):
            return self.resolve_hook("powerful")
        if verb in ("identical", "专一垂钓", "专一"):
            return self.identical()
        if verb in ("slap", "surfaceslap", "拍击水面", "拍击"):
            return self.surfaceslap()
        if verb in ("doublehook", "dh", "双重提钩"):
            return self.doublehook(2)
        if verb in ("triplehook", "th", "三重提钩"):
            return self.doublehook(3)
        if verb in ("eshop", "装备店"):
            return self.eshop(arg)
        if verb in ("ebuy",):
            return self.ebuy(arg)
        if verb in ("wear", "穿"):
            return self.wear(arg)
        if verb in ("gearset", "全身"):
            return self.gearset()
        if verb in ("recycle", "分解"):
            return self.recycle(arg)
        if verb in ("mshop", "魔晶石店"):
            return self.mshop()
        if verb in ("mbuy",):
            return self.mbuy(arg)
        if verb in ("mcraft", "合成"):
            return self.mcraft(arg)
        if verb in ("meld", "镶嵌", "禁断"):
            return self.meld(arg)
        if verb in ("quests", "quest", "任务"):
            return self.quest_cmd(arg)
        if verb in ("tasks", "daily", "日随"):
            if arg.strip().lower() in ("claim", "领取", "领"):
                out = tasks_mod.claim(self.state, self._now())
                self._autosave()
                return out
            return tasks_mod.view(self.state, self._now())
        if verb in ("buybook", "book", "买书"):
            return self.buybook(arg)
        if verb in ("buyrod", "买竿"):
            return self.buyrod(arg)
        if verb in ("equiprod", "equip", "换竿"):
            return self.equiprod(arg)
        if verb in ("buybait", "买饵"):
            return self.buybait(arg)
        if verb in ("equipbait", "bait", "换饵", "挂饵"):
            return self.equipbait(arg)
        if verb in ("recommend", "推荐", "guide"):
            return self.recommend()
        if verb in ("diary", "日志", "今日"):
            return self.diary()
        if verb in ("pets", "宠物"):
            return self.pets_cmd(arg)
        if verb in ("mounts", "坐骑"):
            return self.mounts_cmd(arg)
        if verb in ("summon", "召唤"):
            return self.summon_cmd(arg)
        if verb in ("ride", "骑"):
            return self.ride_cmd(arg)
        if verb in ("dismount", "下马"):
            self.state["active_mount"] = None
            self._autosave()
            return "🐎 你跳下了坐骑。"
        if verb in ("cook", "烹饪", "做菜"):
            return self.cook_cmd(arg)
        if verb in ("eat", "吃"):
            return self.eat_cmd(arg)
        if verb in ("foodshop", "餐厅", "食物店", "菜单"):
            return self.foodshop_cmd(arg)
        if verb in ("seasoning", "调味料"):
            return self.seasoning_cmd(arg)
        if verb in ("pet", "摸", "互动"):
            rng = random.Random(hash(("pet_interact", self._now())))
            return pet_mod.interact(self.state, rng)
        if verb in ("gallery", "鱼拓", "展示墙"):
            return self.gallery(arg)
        if verb in ("aquarium", "水族箱", "鱼缸"):
            return self.aquarium(arg)
        if verb in ("tournament", "比赛", "钓鱼赛"):
            return self.tournament(arg)
        if verb in table:
            return table[verb]()
        # ── did-you-mean: 打错命令时猜最接近的 ──
        guess = _did_you_mean(verb)
        if guess:
            return f"不认识的命令：{verb}——你是不是想说 {guess}？"
        return f"不认识的命令：{verb}（试试 help）"


# --- did-you-mean: 打错命令时猜最接近的 --------------------
_KNOWN_VERBS = [
    "look", "cast", "spear", "goto", "spots", "bag", "records",
    "status", "gp", "patience", "fisheyes", "chum", "prize",
    "snagging", "cordial",
    "collector", "turnin", "eshop", "ebuy", "wear", "gearset",
    "recycle", "mshop", "mbuy", "mcraft", "meld", "quests", "quest",
    "tasks", "books", "buybook", "baits", "buybait", "bait",
    "rods", "buyrod", "equiprod", "save", "load", "help", "ocean",
    "summary", "ach", "forecast", "mooch", "title", "recommend",
    "gallery", "aquarium", "tournament", "diary",
    "pets", "mounts", "summon", "ride", "dismount", "pet",
    "cook", "eat", "foodshop", "seasoning",
    "sell", "rescue", "hook", "precision", "powerful",
    "identical", "slap", "doublehook", "triplehook", "lang",
]


def _did_you_mean(verb: str) -> str:
    """打错命令时返回最接近的合法命令, 编辑距离>2 或无命中返回空。"""
    v = verb.lower()
    # 前缀匹配优先(唯一命中才提示)
    prefix = [k for k in _KNOWN_VERBS if k.startswith(v)]
    if len(prefix) == 1:
        return prefix[0]

    # Levenshtein 编辑距离
    def _dist(a, b):
        if len(a) > len(b):
            a, b = b, a
        d = list(range(len(a) + 1))
        for j, cb in enumerate(b, 1):
            nd = [j]
            for i, ca in enumerate(a, 1):
                nd.append(min(d[i] + 1, nd[-1] + 1, d[i - 1] + (ca != cb)))
            d = nd
        return d[-1]

    best = min(_KNOWN_VERBS, key=lambda k: _dist(v, k))
    return best if _dist(v, best) <= 2 else ""


# --- 给 AI / 你的便捷单例 ---------------------------------
_game = None
_game_slot = None          # 记住当前单例绑定的存档名


def cmd(text: str, slot: str = "default") -> str:
    """便捷入口: 自动管理单例 Game, slot 变了就重建(防串档)。"""
    global _game, _game_slot
    if _game is None or _game_slot != slot:
        _game = Game(slot=slot)
        _game_slot = slot
    return _game.cmd(text)


if __name__ == "__main__":
    g = Game(slot="_demo", fixed_time=1_700_000_000)
    g.state = save_mod.new_state()
    g.state["seed"] = 42
    g.state["level"] = 40            # 演示: 设个等级好进钓场
    g.state["location"] = "Costa del Sol"

    print(g.cmd("look")); print()
    print("—— 抛竿几次(看经验/升级) ——")
    for _ in range(4):
        print(g.cmd("cast"))
    print()
    print(g.cmd("bag")); print()
    print(g.cmd("status Mahi-Mahi"))
