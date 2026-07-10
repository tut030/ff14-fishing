"""食物 buff / 食物店分页 / 宠物兑换解析 校验 — python3 -m pytest tests/test_food_pets.py"""
from engine.game import Game
from engine import save as S
from engine import food as food_mod

T = 1_700_000_000


def _fresh(slot="_t_food"):
    g = Game(slot=slot, fixed_time=T)
    g.state = S.new_state()
    g.state["seed"] = 7
    return g


def test_foodshop_sorted_and_paged():
    g = _fresh()
    out = g.cmd("foodshop")
    assert "第 1/" in out
    cheapest = min(food_mod.SHOP_FOOD, key=lambda x: x["price"])
    assert cheapest["name"] in out, "第一页应从最便宜的开始"
    pages = (len(food_mod.SHOP_FOOD) + 9) // 10
    out99 = g.cmd("foodshop 99")            # 越界页码自动夹到最后一页
    assert f"第 {pages}/{pages}" in out99


def test_eat_gives_active_buff_and_xp_mult():
    g = _fresh()
    g.state["gil"] = 10000
    cheapest = min(food_mod.SHOP_FOOD, key=lambda x: x["price"])
    g.cmd(f"eat {cheapest['name']}")
    assert food_mod.get_active_buff(g.state, g._now()) is not None
    assert food_mod.xp_multiplier(g.state, g._now()) > 1.0


def test_pets_mounts_buy_prefix_syntax():
    """回归测试(原 v18 bug): 游戏提示的 `pets buy <id>` 写法必须可用。"""
    g = _fresh()
    g.state["mgp"] = 99999
    out = g.cmd("pets buy golden_chocobo")
    assert "兑换了宠物" in out
    out2 = g.cmd("pets golden_chocobo")     # 已拥有 → 应报失败而不是重复兑换
    assert "失败" in out2
    out3 = g.cmd("mounts buy")              # 纯 buy → 显示兑换列表
    assert "MGP" in out3
