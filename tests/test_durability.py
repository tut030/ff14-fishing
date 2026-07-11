"""耐久与修理 校验 — python3 -m pytest tests/test_durability.py"""
from engine.game import Game
from engine import save as S, durability as D
from engine import equipment as eq

T = 1_700_000_000


def _fresh(slot="_t_dur"):
    g = Game(slot=slot, fixed_time=T)
    g.state = S.new_state()
    g.state["seed"] = 7
    g.state["gil"] = 50000
    return g


def test_cast_wears_rod():
    g = _fresh()
    before = D.get(g.state)
    g.cmd("cast 5")
    assert D.get(g.state) == before - 5 * D.WEAR_CAST


def test_no_bait_no_wear():
    g = _fresh()
    g.state["bait"] = None
    g.state["bait_stock"] = {}
    before = D.get(g.state)
    g.cmd("cast 5")                       # 被无饵闸门拦下
    assert D.get(g.state) == before


def test_threshold_note_fires_once():
    g = _fresh()
    g.state.setdefault("rod_dur", {})[D._rod_key(g.state)] = 801
    out1 = g.cmd("cast 1")
    assert "裂纹" in out1                 # 跨800阈值提醒
    out2 = g.cmd("cast 1")
    assert "裂纹" not in out2             # 同档不重复唠叨


def test_stat_penalty_tiers():
    g = _fresh()
    g.state.setdefault("rod_dur", {})[D._rod_key(g.state)] = 500
    full = eq.stats_total(g.state)["获得力"]
    g.state["rod_dur"][D._rod_key(g.state)] = 100
    assert eq.stats_total(g.state)["获得力"] == int(full * 0.5)
    g.state["rod_dur"][D._rod_key(g.state)] = 0
    assert eq.stats_total(g.state)["获得力"] == 0


def test_mender_repairs_to_full_and_charges():
    g = _fresh()
    g.state["rod"] = "Maple Fishing Rod"          # 有价竿(320g)
    g.state["rod_dur"] = {"Maple Fishing Rod": 0}
    gil = g.state["gil"]
    out = g.cmd("repair go")
    assert D.get(g.state) == D.MAX, out
    from engine import gear
    exp = max(D.MENDER_FLOOR, int(gear.price(gear.RODS["Maple Fishing Rod"]) * D.MENDER_RATE))
    assert gil - g.state["gil"] == exp


def test_starter_rod_free():
    g = _fresh()
    g.state["rod_dur"] = {"Weathered Fishing Rod": 0}
    gil = g.state["gil"]
    g.cmd("repair go")
    assert D.get(g.state) == D.MAX and g.state["gil"] == gil


def test_quest_flow_and_self_repair():
    g = _fresh()
    g.state["level"] = 30
    out = g.cmd("repair")
    assert g.state["mender_quest"] == 1 and "工具车" in out
    assert "自己的竿" not in out
    # 自修未解锁时被拒
    assert "还不会" in g.cmd("repair self")
    # 买三份成品食物(走真实foodshop商品)
    from engine import food as F
    dish = F.SHOP_FOOD[0]["name"] if hasattr(F, "SHOP_FOOD") else None
    if dish:
        for _ in range(3):
            g.cmd(f"eat {dish}")
    else:                                          # 兜底: 直接计数
        g.state["mender_food"] = 3
    out = g.cmd("repair")
    assert g.state["mender_quest"] == 2, out
    assert g.state["dark_matter"].get("G1暗物质") == 2
    # 自修: 199%
    g.state.setdefault("rod_dur", {})[D._rod_key(g.state)] = 300
    out = g.cmd("repair self")
    assert D.get(g.state) == D.SELF_MAX, out
    assert g.state["dark_matter"]["G1暗物质"] == 1


def test_dark_matter_grade_and_buy():
    g = _fresh()
    g.state["mender_quest"] = 2
    assert D.grade_for(45) == ("G1暗物质", 50)
    assert D.grade_for(60) == ("G2暗物质", 300)
    assert D.grade_for(80) == ("G3暗物质", 1000)
    gil = g.state["gil"]
    g.cmd("repair buy 2")
    assert g.state["dark_matter"].get("G1暗物质") == 2
    assert g.state["gil"] == gil - 100


def test_old_save_compat():
    g = _fresh()
    for k in ("rod_dur", "dark_matter", "mender_quest", "mender_food"):
        g.state.pop(k, None)
    out = g.cmd("bag")                    # 老档任意命令不炸, 自动补默认
    assert "耐久" in out
    assert D.get(g.state) == D.MAX
