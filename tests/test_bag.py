"""鱼袋 / 卖鱼 / 烹饪(方案B) 校验 — python3 -m pytest tests/test_bag.py"""
from engine.game import Game, BAG_BASE_SLOTS, BAG_SADDLE_SLOTS, _unit_price
from engine import save as S
from engine.fish import get

T = 1_700_000_000


def _fresh(slot="_t_bag"):
    g = Game(slot=slot, fixed_time=T)
    g.state = S.new_state()
    g.state["seed"] = 42
    return g


def test_bag_capacity_and_stacking():
    g = _fresh()
    # 同种同品质叠放, 不占新格
    assert g._bag_add("Chub", False)
    assert g._bag_add("Chub", False)
    assert g.state["fish_bag"]["Chub"] == 2
    assert len(g.state["fish_bag"]) == 1
    # NQ / HQ 分格
    assert g._bag_add("Chub", True)
    assert g.state["fish_bag"]["Chub|HQ"] == 1
    # 填满 → 新鱼种被拒, 老格照叠
    for i in range(BAG_BASE_SLOTS - 2):
        assert g._bag_add(f"fake{i}", False)
    assert len(g.state["fish_bag"]) == BAG_BASE_SLOTS
    assert not g._bag_add("Newcomer", False)
    assert g._bag_add("Chub", False)


def test_saddlebag_unlock():
    g = _fresh()
    assert g._bag_cap() == BAG_BASE_SLOTS
    g.state["quests_done"] = [5, 10, 15]
    assert g._bag_cap() == BAG_BASE_SLOTS + BAG_SADDLE_SLOTS


def test_bag_full_cast_is_wasted_cast():
    """满袋钓到新鱼种: 不计图鉴、不给经验(白钓一竿)。"""
    g = _fresh()
    g.state["level"] = 40
    g.state["location"] = "Costa del Sol"
    g.state["bait_stock"] = {"Crayfish Ball": 99}
    for i in range(BAG_BASE_SLOTS):
        g._bag_add(f"fake{i}", False)
    xp0, lv0 = g.state["xp"], g.state["level"]
    out = g.cmd("cast 12")
    assert g.state["caught"] == {}, "满袋渔获不应计入图鉴"
    assert (g.state["level"], g.state["xp"]) == (lv0, xp0), "满袋渔获不应给经验"
    assert "袋满" in out


def test_sell_and_pokedex_untouched():
    g = _fresh()
    g.state["fish_bag"] = {"Chub": 2, "Chub|HQ": 1}
    g.state["caught"] = {"Chub": 3}
    f = get("Chub")
    expect = _unit_price(f, False) * 2 + _unit_price(f, True)
    g.cmd("sell Chub all")
    assert g.state["gil"] == expect
    assert g.state["fish_bag"] == {}
    assert g.state["caught"] == {"Chub": 3}, "卖鱼不应动图鉴"


def test_sell_light_and_all():
    g = _fresh()
    f = get("Chub")
    g.state["fish_bag"] = {"Chub": 2}
    out = g.cmd("sell light")
    if f.get("tug", "Light") == "Light":
        assert g.state["fish_bag"] == {}
    else:
        assert "没有轻杆" in out
        g.cmd("sell all")
        assert g.state["fish_bag"] == {}


def test_sell_partial_keeps_rest():
    g = _fresh()
    g.state["fish_bag"] = {"Chub": 5}
    g.cmd("sell Chub 2")
    assert g.state["fish_bag"]["Chub"] == 3


def test_cook_eats_bag_not_pokedex():
    """回归测试(原 v18 bug): 烹饪只吃鱼袋, 图鉴只增不减。"""
    g = _fresh()
    g.state["fish_bag"] = {"Maiden Carp": 1}
    g.state["caught"] = {"Maiden Carp": 1}
    g.state.setdefault("seasoning_stock", {})["light"] = 1
    out = g.cmd("cook 烤鲤鱼")
    assert "做好了" in out
    assert g.state["caught"] == {"Maiden Carp": 1}, "图鉴被烹饪吃掉了!"
    assert g.state["fish_bag"] == {}
    g.state["seasoning_stock"]["light"] = 1
    out2 = g.cmd("cook 烤鲤鱼")
    assert "袋里没有" in out2


def test_mooch_consumes_live_bait_from_bag():
    g = _fresh()
    g.state["fish_bag"] = {"Chub": 1}
    assert g._bag_take("Chub")
    assert g.state["fish_bag"] == {}
    assert not g._bag_take("Chub")
