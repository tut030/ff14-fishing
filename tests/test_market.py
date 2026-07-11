"""市场板宠物 校验 — python3 -m pytest tests/test_market.py"""
from engine.game import Game
from engine import save as S, pets as P

T = 1_700_000_000


def _fresh(slot="_t_mkt"):
    g = Game(slot=slot, fixed_time=T)
    g.state = S.new_state()
    g.state["gil"] = 60000
    return g


def test_market_lists_six_with_prices():
    g = _fresh()
    out = g.cmd("market")
    assert "2400" in out.replace(",", "") or "2400" in out
    assert "巧儿陆行鸟" in out and "？？？" in out
    assert "咸鱼精" not in out                 # 神秘崽购买前不露名


def test_buy_deducts_and_grants_and_summons():
    g = _fresh()
    out = g.cmd("market buy 盗龙小宝")
    assert g.state["gil"] == 60000 - 2400
    assert "baby_raptor" in g.state["pets"], out
    out = g.cmd("summon 盗龙小宝")
    assert g.state.get("active_pet") == "baby_raptor", out


def test_mystery_reveals_on_purchase():
    g = _fresh()
    out = g.cmd("market buy 布袋崽")
    assert "咸鱼" in out and "salted_fish" in g.state["pets"]
    assert g.state["gil"] == 60000 - 50000


def test_insufficient_gil():
    g = _fresh()
    g.state["gil"] = 100
    out = g.cmd("market buy 鱼人玩偶")
    assert "25000" in out and g.state["gil"] == 100
    assert "sahagin_doll" not in g.state.get("pets", [])


def test_no_double_buy():
    g = _fresh()
    g.cmd("market buy 爆弹仔")
    gil = g.state["gil"]
    out = g.cmd("market buy 爆弹仔")
    assert "重复" in out and g.state["gil"] == gil
