"""
每日/每周任务自动校验
跑法:  cd ff14-fishing && python3 tests/test_tasks.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from engine import tasks
from engine.game import Game

SLOT = "_dttest"
SAVE = pathlib.Path(__file__).resolve().parent.parent / "saves" / f"{SLOT}.json"


def _fresh(fixed_time):
    for p in (SAVE, SAVE.with_suffix(".json.bak")):
        if p.exists():
            p.unlink()
    g = Game(slot=SLOT, fixed_time=fixed_time)
    g.state["seed"] = 7
    g.state["level"] = 50
    return g


def test_tasks():
    T = 1_700_000_000

    # 1) 确定性: 同 key 同任务(全球同一份); 不同 key 大概率不同
    dk = tasks.day_key(T)
    assert tasks.gen_daily(dk) == tasks.gen_daily(dk)
    assert tasks.gen_weekly(tasks.week_key(T)) == tasks.gen_weekly(tasks.week_key(T))
    assert any(tasks.gen_daily(dk) != tasks.gen_daily(dk + i) for i in (1, 2, 3))

    # 2) 刷新边界: 每日 15:00 UTC / 每周二 08:00 UTC, 前后一秒分属两期
    import time as _t
    nd = tasks.next_daily_reset(T)
    assert _t.gmtime(nd).tm_hour == 15 and _t.gmtime(nd).tm_min == 0
    assert tasks.day_key(nd - 1) + 1 == tasks.day_key(nd)
    nw = tasks.next_weekly_reset(T)
    assert _t.gmtime(nw).tm_wday == 1 and _t.gmtime(nw).tm_hour == 8   # 周二=1
    assert tasks.week_key(nw - 1) + 1 == tasks.week_key(nw)

    # 3) 打点: 每种日随类型喂对应事件, 进度精确+封顶
    g = _fresh(T)
    t = tasks.ensure(g.state, T)
    for i, task in enumerate(tasks.gen_daily(t["day_key"])):
        ev = {"catch_any": ("catch", None), "hq": ("hq", None),
              "collect": ("collect", None), "spear": ("spear", None),
              "catch_region": ("catch", task["region"])}[task["type"]]
        tasks.record(g.state, T, ev[0], task["need"] + 5, region=ev[1])
        assert t["day_prog"][str(i)] == task["need"]        # 封顶不过量

    # 4) 领奖: 发钱发票+防重复
    gil0, w0 = g.state["gil"], g.state.get("scrip_white", 0)
    r = g.cmd("tasks claim")
    assert "领取" in r
    n_day = tasks.DAILY_COUNT
    assert g.state["gil"] == gil0 + n_day * tasks.DAILY_REWARD["gil"]
    assert g.state["scrip_white"] == w0 + n_day * tasks.DAILY_REWARD["white"]
    assert "没有可领" in g.cmd("tasks claim")               # 不能重复领

    # 5) 滚动清零: 时间跨过刷新点, 进度与领取记录归零
    g2 = Game(slot=SLOT, fixed_time=tasks.next_daily_reset(T) + 60)
    out = g2.cmd("tasks")
    assert "✅已领" not in out.split("周随")[0]              # 新一天日随全新

    # 6) 游戏内打点连通: 找一个日随含"钓到N条鱼(任意)"的日子, 去那天钓
    dk0 = tasks.day_key(T)
    hit_day = next(d for d in range(dk0, dk0 + 30)
                   if any(x["type"] == "catch_any" for x in tasks.gen_daily(d)))
    T2 = hit_day * tasks.DAY_SEC + tasks.DAILY_RESET_OFFSET + 3600
    g3 = _fresh(T2)
    g3.state["location"] = "Costa del Sol"
    g3.state["bait"] = "Pill Bug"               # 给饵, 确保能钓到鱼
    g3.state["bait_stock"] = {"Pill Bug": 99}
    g3.cmd("cast 5")
    t3 = tasks.ensure(g3.state, T2)             # 确保 tasks 子结构已初始化
    idx = next(str(i) for i, x in enumerate(tasks.gen_daily(hit_day))
               if x["type"] == "catch_any")
    # cast 可能空军/脱钩, 但只要 cast 过就应该有进度(至少 casts 已推进)
    prog = t3.get("day_prog", {}).get(idx, 0)
    if sum(g3.state.get("caught", {}).values()) > 0:
        assert prog > 0, "钓到鱼后 catch_any 进度应增长"

    for p in (SAVE, SAVE.with_suffix(".json.bak")):
        if p.exists():
            p.unlink()


