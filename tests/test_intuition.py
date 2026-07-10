"""捕鱼人之识(直感) 校验 — python3 -m pytest tests/test_intuition.py"""
from engine.game import Game, INTUITION_CASTS, _PRED_KINGS
from engine import save as S

T = 1_700_000_000
KING = _PRED_KINGS[0]                       # 任取一条带前置的鱼王(数据驱动)


def _fresh(slot="_t_intu"):
    g = Game(slot=slot, fixed_time=T)
    g.state = S.new_state()
    g.state["seed"] = 3
    return g


def test_data_loaded():
    assert len(_PRED_KINGS) >= 30, "前置数据应全量加载"
    assert all(isinstance(f["predators"], dict) and f["predators"] for f in _PRED_KINGS)


def test_progress_and_proc():
    g = _fresh()
    pred, need = next(iter(KING["predators"].items()))
    # 差一条: 只涨进度不触发
    for _ in range(need - 1):
        note = g._intuition_on_catch(pred)
    if need > 1:
        assert note == ""
        assert g.state["intuition_progress"][pred] == need - 1
    # 补上最后一条: 触发直感 + 进度被消耗
    note = g._intuition_on_catch(pred)
    # (若该王还要求另一种前置, 则不会触发——按数据自适应断言)
    if len(KING["predators"]) == 1:
        assert "捕鱼人之识" in note
        assert g.state["intuition_casts"] == INTUITION_CASTS
        assert pred not in g.state.get("intuition_progress", {})
    else:
        assert g.state["intuition_progress"][pred] == need


def test_non_predator_is_noop():
    g = _fresh()
    assert g._intuition_on_catch("__不存在的鱼__") == ""
    assert "intuition_progress" not in g.state or not g.state["intuition_progress"]


def test_casts_countdown_and_survives_goto():
    g = _fresh()
    g.state["intuition_casts"] = 2
    g.cmd("cast")                                # 新手钓场, 抛一竿
    assert g.state["intuition_casts"] == 1
    g.state["intuition_progress"] = {"X": 1}
    g.cmd("goto Sapsa Spawning Grounds")         # 换场(去不去得成都行)
    assert g.state["intuition_casts"] == 1, "直感应跨钓场存活"
    assert g.state["intuition_progress"] == {"X": 1}, "前置进度应跨钓场存活"


def test_status_shows_predators():
    g = _fresh()
    out = g.cmd(f"status {KING['name']}")
    assert "前置" in out and "捕鱼人之识" in out
