"""
FF14 钓鱼 每日/每周任务模块
------------------------------------------------------------
设计约定(和船长聊定的):
  - 刷新走真实时钟, 锚点与真实游戏一致:
      每日 15:00 UTC(国服 23:00) / 每周二 08:00 UTC(国服 16:00)
  - 任务由"日期/周数"确定性生成 —— 全世界玩家同一天领到同一份任务
    (与天气/海钓班次同一血统: 此刻钓不到的鱼谁也钓不到, 今天的日随谁做都一样)
  - 内容从真实数据滚(大区来自鱼表), 奖励 = gil + 票据
  - 纯可选: 不做不影响任何玩法

★ 想调任务池/奖励手感, 改下面常量即可 ★
"""

from __future__ import annotations
import random

try:
    from .fish import FISH
except ImportError:
    from fish import FISH

# ===== 刷新锚点(真实游戏同款) ================================
DAY_SEC = 86400
WEEK_SEC = 7 * DAY_SEC
DAILY_RESET_OFFSET = 15 * 3600            # 每日 15:00 UTC
WEEKLY_RESET_OFFSET = 5 * DAY_SEC + 8 * 3600   # 纪元是周四, +5天=周二 08:00 UTC

# ===== 可调常量 =============================================
DAILY_COUNT = 3            # 每天几个日随
WEEKLY_COUNT = 2           # 每周几个周随
DAILY_REWARD = {"gil": 500, "white": 8}
WEEKLY_REWARD = {"gil": 1500, "purple": 20}
# ===========================================================

_REGIONS = sorted({f["region"] for f in FISH if f.get("region")})

# 日随任务池: (类型, 描述模板, 需求量范围)
_DAILY_POOL = [
    ("catch_any", "钓到 {need} 条鱼(任意)", (20, 40)),
    ("catch_region", "在 {region} 大区钓到 {need} 条鱼", (10, 20)),
    ("hq", "钓到 {need} 条 HQ 鱼", (3, 6)),
    ("collect", "上交 {need} 件收藏品(turnin)", (5, 10)),
    ("spear", "叉到 {need} 条鱼(🔱叉鱼点)", (5, 10)),
]
_WEEKLY_POOL = [
    ("ocean_trips", "完成 {need} 班海钓航次", (2, 3)),
    ("ocean_points", "海钓累计获得 {need} 渔分", (4000, 8000)),
    ("catch_any", "钓到 {need} 条鱼(任意)", (150, 250)),
    ("collect", "上交 {need} 件收藏品(turnin)", (20, 30)),
]


def day_key(now: float) -> int:
    return int(now - DAILY_RESET_OFFSET) // DAY_SEC


def week_key(now: float) -> int:
    return int(now - WEEKLY_RESET_OFFSET) // WEEK_SEC


def next_daily_reset(now: float) -> int:
    return (day_key(now) + 1) * DAY_SEC + DAILY_RESET_OFFSET


def next_weekly_reset(now: float) -> int:
    return (week_key(now) + 1) * WEEK_SEC + WEEKLY_RESET_OFFSET


def _gen(pool, count, seed_key: int) -> list:
    """从任务池确定性生成 count 个任务(同 key 全球一致)。"""
    rng = random.Random(seed_key * 2654435761 + 42)
    picks = rng.sample(pool, k=min(count, len(pool)))
    out = []
    for typ, tmpl, (lo, hi) in picks:
        need = rng.randint(lo, hi)
        region = rng.choice(_REGIONS) if typ == "catch_region" else None
        desc = tmpl.format(need=need, region=region or "")
        out.append({"type": typ, "need": need, "region": region, "desc": desc})
    return out


def gen_daily(dkey: int) -> list:
    return _gen(_DAILY_POOL, DAILY_COUNT, dkey)


def gen_weekly(wkey: int) -> list:
    return _gen(_WEEKLY_POOL, WEEKLY_COUNT, wkey * 7919)


def ensure(state: dict, now: float) -> dict:
    """滚动到当前周期: key 变了就清进度/领取记录。返回任务存档区。"""
    t = state.setdefault("tasks", {})
    dk, wk = day_key(now), week_key(now)
    if t.get("day_key") != dk:
        t["day_key"] = dk
        t["day_prog"] = {}
        t["day_claimed"] = []
    if t.get("week_key") != wk:
        t["week_key"] = wk
        t["week_prog"] = {}
        t["week_claimed"] = []
    return t


def record(state: dict, now: float, event: str,
           amount: int = 1, region: str | None = None) -> None:
    """进度打点: event ∈ catch/hq/collect/spear/ocean_trip/ocean_points。"""
    t = ensure(state, now)
    for scope, tasks in (("day", gen_daily(t["day_key"])),
                         ("week", gen_weekly(t["week_key"]))):
        prog = t[f"{scope}_prog"]
        for i, task in enumerate(tasks):
            typ = task["type"]
            hit = (
                (event == "catch" and typ == "catch_any")
                or (event == "catch" and typ == "catch_region"
                    and region == task["region"])
                or (event == "hq" and typ == "hq")
                or (event == "collect" and typ == "collect")
                or (event == "spear" and typ in ("spear", "catch_any"))
                or (event == "ocean_trip" and typ == "ocean_trips")
                or (event == "ocean_points" and typ == "ocean_points")
            )
            if hit:
                k = str(i)
                prog[k] = min(task["need"], prog.get(k, 0) + amount)


# 大区 -> 最低钓场等级(给日随标🔒用)
_REGION_MIN_LV = {}
for _f in FISH:
    r = _f.get("region", "")
    lv = _f.get("level")
    if r and lv and _f["mode"] == "line":
        _REGION_MIN_LV[r] = min(_REGION_MIN_LV.get(r, 999), lv)


def _fmt(scope: str, tasks: list, t: dict, player_lv: int = 100) -> list:
    prog = t[f"{scope}_prog"]
    claimed = t[f"{scope}_claimed"]
    out = []
    for i, task in enumerate(tasks):
        p = prog.get(str(i), 0)
        # 区域任务: 检查玩家等级是否够
        region = task.get("region")
        need_lv = _REGION_MIN_LV.get(region, 0) if region else 0
        locked = need_lv > player_lv + 5
        if i in claimed:
            mark = "✅已领"
        elif locked:
            mark = f"🔒Lv{need_lv}"
        elif p >= task["need"]:
            mark = "🎁可领!"
        else:
            mark = f"{p}/{task['need']}"
        out.append(f"   [{mark}] {task['desc']}")
    return out


def view(state: dict, now: float) -> str:
    t = ensure(state, now)
    lv = state.get("level", 1)
    dr = int(next_daily_reset(now) - now)
    wr = int(next_weekly_reset(now) - now)
    out = [f"📋 日随(全球同一份; {dr // 3600}h{dr % 3600 // 60:02d}m 后刷新, "
           f"奖励各 {DAILY_REWARD['gil']}g+🎫{DAILY_REWARD['white']}):"]
    out += _fmt("day", gen_daily(t["day_key"]), t, lv)
    out.append(f"📋 周随({wr // 86400}天{wr % 86400 // 3600}h 后刷新, "
               f"奖励各 {WEEKLY_REWARD['gil']}g+🎟{WEEKLY_REWARD['purple']}):")
    out += _fmt("week", gen_weekly(t["week_key"]), t, lv)
    out.append("   tasks claim 一键领取全部已完成的")
    return "\n".join(out)


def claim(state: dict, now: float) -> str:
    t = ensure(state, now)
    gil = white = purple = got = 0
    for scope, tasks, reward in (("day", gen_daily(t["day_key"]), DAILY_REWARD),
                                 ("week", gen_weekly(t["week_key"]), WEEKLY_REWARD)):
        prog, claimed = t[f"{scope}_prog"], t[f"{scope}_claimed"]
        for i, task in enumerate(tasks):
            if i in claimed or prog.get(str(i), 0) < task["need"]:
                continue
            claimed.append(i)
            got += 1
            gil += reward["gil"]
            white += reward.get("white", 0)
            purple += reward.get("purple", 0)
    if not got:
        return "没有可领的任务奖励。tasks 看进度~"
    state["gil"] = state.get("gil", 0) + gil
    state["scrip_white"] = state.get("scrip_white", 0) + white
    state["scrip_purple"] = state.get("scrip_purple", 0) + purple
    parts = [f"+{gil}g"]
    if white:
        parts.append(f"🎫+{white}")
    if purple:
        parts.append(f"🎟+{purple}")
    return f"🎁 领取 {got} 个任务奖励: " + " ".join(parts)
