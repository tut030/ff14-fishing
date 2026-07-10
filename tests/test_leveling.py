"""升级系统校验  —  python3 tests/test_leveling.py"""

from engine import leveling as L
from engine import save as S
from engine.game import Game, _LOC_LEVEL

T = 1_700_000_000


def test_leveling():
    # 1) 经验曲线递增
    assert L.xp_to_next(1) < L.xp_to_next(50) < L.xp_to_next(99)

    # 2) 加经验会升级(可连升); 满级不再涨
    st = {"level": 1, "xp": 0}
    gained = L.add_xp(st, 10000)
    assert st["level"] > 1 and gained[0] == 2
    st2 = {"level": L.LEVEL_CAP, "xp": 0}
    assert L.add_xp(st2, 9999) == [] and st2["level"] == L.LEVEL_CAP

    # 3) 高级鱼给的经验 >= 低级鱼
    assert L.xp_gain(90, 90) >= L.xp_gain(10, 90)

    # 4) 等级门槛: 等级不够时 cast 被拦, 够了能钓
    #    找一个等级>1 的钓场
    loc, lv = next((l, v) for l, v in _LOC_LEVEL.items() if v and v >= 10)
    g = Game(slot="_test_lv", fixed_time=T)
    g.state = S.new_state()          # Lv1
    g.state["location"] = loc
    assert g.state["level"] == 1
    assert "🔒" in g.cmd("cast"), "等级不够应被拦"
    assert g.state["casts"] == 0, "被拦不该消耗抛竿数"

    g.state["level"] = lv            # 提到门槛
    r = g.cmd("cast")
    assert "🔒" not in r, "够等级不该被拦"

    # 清理
    p = S._path("_test_lv")
    for f in (p, p.with_suffix(".json.bak"), p.with_suffix(".json.tmp")):
        if f.exists():
            f.unlink()


