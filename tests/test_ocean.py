"""
海钓模块自动校验
跑法:  cd ff14-fishing && python3 tests/test_ocean.py
作用:  改动海钓/主循环后跑一遍, 立刻知道登船门禁/航程推进/结算有没有被改坏。
说明:  全部用固定时间+固定种子, 不依赖真实时钟, 结果可复现。
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from engine.ocean_schedule import slot_start, route_key_at, BOARDING_WINDOW
from engine import ocean
from engine import save as save_mod
from engine.game import Game

SLOT = "_oceantest"
SAVE = pathlib.Path(__file__).resolve().parent.parent / "saves" / f"{SLOT}.json"


def _fresh(fixed_time, seed=7, level=5):
    """全新存档的 Game(固定时间/种子, 结果可复现)。"""
    for p in (SAVE, SAVE.with_suffix(".json.bak")):
        if p.exists():
            p.unlink()
    g = Game(slot=SLOT, fixed_time=fixed_time)
    g.state["seed"] = seed
    g.state["level"] = level
    return g


def test_ocean():
    base = slot_start(1_700_000_000)

    # 1) 班次门禁: 窗口关了(第15分钟起)登不了船; 窗口内可以
    g = _fresh(base + BOARDING_WINDOW + 5)
    out = g.cmd("ocean board indigo")
    assert "错过" in out and g.state["ocean"] is None
    # 判断顺序: 窗口关+乱打航路名 -> 先报名字错, 不误报错过
    assert "哪条航路" in g.cmd("ocean board 瞎打的")

    g = _fresh(base + 60)
    out = g.cmd("ocean board 灵青")
    assert g.state["ocean"] is not None
    ses = g.state["ocean"]
    assert ses["route_key"] == route_key_at("indigo", base + 60)   # 航线来自真实排班
    assert len(ses["crew"]) == ocean.CREW_SIZE
    assert len(set(ses["crew"])) == ocean.CREW_SIZE                # 船友名不重复
    assert ses["budget"] == float(ocean.CASTS_PER_STATION)

    # 2) 在船上: goto/spear 被拦, look 转接海上状态
    assert "不倦号" in g.cmd("goto Costa del Sol")
    assert "站" in g.cmd("look")

    # 3) 重复登船被拒; 存档持久化(新进程接着玩)
    assert "已经在船上" in g.cmd("ocean board ruby")
    g2 = Game(slot=SLOT, fixed_time=base + 60)
    assert g2.state["ocean"] and g2.state["ocean"]["route_key"] == ses["route_key"]

    # 4) 整航次: 预算 15竿x3站, 幻海流半价竿只会多不会少 -> 90 竿内必定结算
    g = _fresh(base + 60)
    g.cmd("ocean board indigo")
    for _ in range(3):
        g.cmd("ocean cast 30")
        if g.state["ocean"] is None:
            break
    assert g.state["ocean"] is None, "90 竿后航次仍未结算"
    assert g.state["ocean_trips"] == 1
    assert g.state["ocean_points_total"] > 0
    assert g.state["ocean_caught"], "整航次一条鱼都没钓到, 概率上不可能"
    for name in g.state["ocean_caught"]:                 # 图鉴名都能对回鱼表
        assert name in ocean._FISH_BY_CN, f"图鉴里有未知鱼名: {name}"
    assert g.state["xp"] > 0 or g.state["level"] > 5    # 结算给了经验

    # 5) 确定性: 同种子+同时间, 两次从零重放, 首竿输出逐字一致
    a = _fresh(base + 60); a.cmd("ocean board indigo")
    b = _fresh(base + 60); b.cmd("ocean board indigo")
    assert a.cmd("ocean cast") == b.cmd("ocean cast")

    # 6) 换饵: 船上供应饵可换; 没库存的世界饵被拒
    g = _fresh(base + 60)
    g.cmd("ocean board indigo")
    assert "石沙蚕" in g.cmd("ocean bait 石沙蚕")
    assert g.state["ocean"]["bait"] != ocean.DEFAULT_BAIT
    assert "库存" in g.cmd("ocean bait Rat Tail")        # 特殊饵要出发前买好

    # 7) 弃船: 会话清空、渔分作废(航次数不涨)
    trips = g.state["ocean_trips"]
    assert "作废" in g.cmd("ocean quit")
    assert g.state["ocean"] is None and g.state["ocean_trips"] == trips

    # 8) 海钓鱼档案(status 转接): 属性/需求/出狱倒计时
    g = _fresh(base + 60)
    r = g.cmd("status 索蒂斯")
    assert "海钓" in r and "蓝鱼" in r and "幻海流" in r     # 属性齐全
    assert "机会" in r or "牢底" in r                        # 有倒计时或明示无窗
    r2 = g.cmd("status 幻光")
    assert "匹配到多条" in r2                                # 模糊多命中列候选
    r3 = g.cmd("status Spectral Bass")                       # 英文名也认
    assert "触发鱼" in r3
    assert "没有这条鱼" in g.cmd("status 不存在的鱼")          # 兜底不变

    # 9) 成就系统: 整航次结算后有成就存档+查看命令能用
    g = _fresh(base + 60, level=40)
    g.cmd("ocean board indigo")
    for _ in range(3):
        g.cmd("ocean cast 30")
        if not g.state.get("ocean"):
            break
    ach = g.state.get("achievements", [])
    assert len(ach) > 0, "一整航次应至少达成一个成就(如珍鱼/丰渔)"
    r = g.cmd("ocean ach")
    assert "海钓成就" in r and "✅" in r                      # 查看命令能用且有达成标记
    assert g.state.get("scrip_white", 0) > 0, "海钓结算应给白票"

    # 9.5) #26回归: 分类成就按精确计数, 不再被鱼种数虚增
    fake = {"score": 0, "max_star": 0, "spectral_catches": 0,
            "self_triggered": False,
            "spot_species": {"1": ["拉诺西亚水母", "海荨麻", "浮游碟鱼"]},
            "_cat_counts": {"15": 3}}          # 3种水母各1只=共3只
    hit_ids = {b["id"] for b in ocean._check_bonuses(fake)}
    assert 15 not in hit_ids, "水母狂魔需6只, 3只不该达成(#26虚增回归)"
    fake["_cat_counts"]["15"] = 6
    assert 15 in {b["id"] for b in ocean._check_bonuses(fake)}

    # 9.6) #27回归: 船上GP随抛竿回复且不吃现实挂机; 下船对表
    g = _fresh(base + 60)
    g.cmd("ocean board indigo")
    g.state["gp"] = 0
    g.cmd("ocean cast")
    assert g.state["gp"] >= ocean.OCEAN_GP_PER_CAST - 1   # 泡泡按竿回复
    for _ in range(3):
        g.cmd("ocean cast 30")
        if not g.state.get("ocean"):
            break
    assert abs(g.state["gp_at"] - (base + 60)) < 2        # 下船对表到"现在"

    # 10) 反刷分: 同一班次只能坐一次(结算后窗口没关也不能再上)
    assert "坐过" in g.cmd("ocean board indigo")
    # 弃船同样烧掉本班资格
    g = _fresh(base + 60)
    g.cmd("ocean board ruby")
    g.cmd("ocean quit")
    assert "坐过" in g.cmd("ocean board ruby")

    # 清理测试档
    for p in (SAVE, SAVE.with_suffix(".json.bak")):
        if p.exists():
            p.unlink()


