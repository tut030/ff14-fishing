"""陆行鸟领养/喂食 校验 — python3 -m pytest tests/test_chocobo.py"""
from engine.game import Game
from engine import save as S, pets as P

T = 1_700_000_000


def _fresh(slot="_t_choco"):
    g = Game(slot=slot, fixed_time=T)
    g.state = S.new_state()
    g.state["seed"] = 7
    return g


def test_adopt_level_gate():
    g = _fresh()
    g.state["level"] = 10
    assert "Lv20" in g.cmd("adopt")
    assert "chocobo" not in g.state.get("mounts", [])


def test_adopt_shows_terms_then_charges_and_names():
    g = _fresh()
    g.state["level"] = 20
    g.state["scrip_white"] = 12
    out = g.cmd("adopt")
    assert "白票" in out and "chocobo" not in g.state.get("mounts", [])
    out = g.cmd("adopt 阿金")
    assert g.state["scrip_white"] == 12 - P.ADOPT_COST_WHITE
    assert "chocobo" in g.state["mounts"]
    assert g.state["mount_names"]["chocobo"] == "阿金"
    assert "阿金" in out


def test_adopt_insufficient_scrip():
    g = _fresh()
    g.state["level"] = 20
    g.state["scrip_white"] = 3
    out = g.cmd("adopt 阿金")
    assert "不够" in out and "chocobo" not in g.state.get("mounts", [])
    assert g.state["scrip_white"] == 3


def test_adopt_only_once():
    g = _fresh()
    g.state["level"] = 20
    g.state["scrip_white"] = 25
    g.cmd("adopt 阿金")
    out = g.cmd("adopt 阿银")
    assert "家人" in out and g.state["scrip_white"] == 25 - P.ADOPT_COST_WHITE


def test_ride_adopted_chocobo():
    g = _fresh()
    g.state["level"] = 20
    g.state["scrip_white"] = 10
    g.cmd("adopt 阿金")
    out = g.cmd("ride 陆行鸟")
    assert g.state.get("active_mount") == "chocobo", out


def test_feed_costs_gil_and_bonds():
    g = _fresh()
    g.state["level"] = 20
    g.state["scrip_white"] = 10
    g.state["gil"] = 100
    assert "还没有" in g.cmd("feed")          # 未领养先拒
    g.cmd("adopt 阿金")
    out = g.cmd("feed")
    assert "阿金" in out
    assert g.state["gil"] == 100 - P.FEED_COST
    assert g.state["chocobo_bond"] == 1
    g.cmd("feed")
    assert g.state["chocobo_bond"] == 2


def test_mounts_list_shows_adopt_hint():
    g = _fresh()
    out = g.cmd("mounts")
    assert "领养" in out and "adopt" in out


def test_ride_by_nickname():
    g = _fresh()
    g.state["level"] = 20
    g.state["scrip_white"] = 10
    g.cmd("adopt 麦穗")
    out = g.cmd("ride 麦穗")
    assert g.state.get("active_mount") == "chocobo", out
