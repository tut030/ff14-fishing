"""提钩窗口(甲+) 校验 — python3 -m pytest tests/test_hookset.py"""
from engine.game import Game
from engine import save as S, gp
from engine.fish import FISH, get

T = 1_700_000_000


def _fresh(slot="_t_hook"):
    g = Game(slot=slot, fixed_time=T)
    g.state = S.new_state()
    g.state["seed"] = 42
    g.state["gp"] = 400
    return g


def _pend(g, name, patience=True):
    g.state["hook_pending"] = {"name": name, "cast_no": 1, "patience": patience,
                               "wait": 5, "used": ["耐心"] if patience else [],
                               "chum": False, "perception": 0,
                               "bait_out": False, "bait_name": None}


def test_precision_on_light_always_lands():
    g = _fresh()
    f = next(x for x in FISH if x.get("tug") == "Light" and x.get("mode") != "spear")
    _pend(g, f["name"])
    out = g.cmd("precision")
    assert g.state["caught"].get(f["name"]) == 1, out
    assert g.state["gp"] == 400 - gp.HOOKSET_COST
    assert g.state.get("hook_pending") is None


def test_powerful_on_medium_always_lands():
    g = _fresh()
    f = next(x for x in FISH if x.get("tug") == "Medium" and x.get("mode") != "spear")
    _pend(g, f["name"])
    g.cmd("powerful")
    assert g.state["caught"].get(f["name"]) == 1
    assert g.state["gp"] == 400 - gp.HOOKSET_COST


def test_gp_short_keeps_window_open():
    g = _fresh()
    g.state["gp"] = 10
    f = next(x for x in FISH if x.get("tug") == "Light" and x.get("mode") != "spear")
    _pend(g, f["name"])
    out = g.cmd("precision")
    assert "不够" in out
    assert g.state.get("hook_pending"), "GP 不足时窗口应保持"
    assert g.state["caught"] == {}


def test_distraction_loses_fish():
    g = _fresh()
    f = next(x for x in FISH if x.get("tug") == "Light" and x.get("mode") != "spear")
    _pend(g, f["name"])
    esc0 = g.state.get("escapes", 0)
    out = g.cmd("look")
    assert "分神" in out
    assert g.state.get("hook_pending") is None
    assert g.state.get("escapes", 0) == esc0 + 1
    assert g.state["caught"] == {}


def test_patience_blocks_batch_and_counts_down():
    g = _fresh()
    g.state["level"] = 90
    g.state["location"] = "Costa del Sol"
    g.state["bait"] = "Pill Bug"
    g.state["bait_stock"] = {"Pill Bug": 99}
    g.cmd("patience")
    assert g.state["patience_casts"] == 3
    out = g.cmd("cast 10")
    assert "一竿一竿" in out, "耐心状态应拒绝批量"
    g.cmd("cast")
    assert g.state["patience_casts"] == 2


def test_resolve_without_window():
    g = _fresh()
    out = g.cmd("powerful")
    assert "没有咬钩" in out
