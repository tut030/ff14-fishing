"""v20 收尾项校验: 鉴别力↔收藏价值 / 鱼眼对鱼王无效 / 坐钩链二跳数据可达"""
import random
from engine import scrip
from engine.game import Game, _mooch_targets
from engine.fish import FISH
from engine import save as S

T = 1_700_000_000


def test_perception_raises_collect_value():
    v0 = scrip.roll_value(random.Random(9), {"tug": "Heavy"}, False, 0)
    v1 = scrip.roll_value(random.Random(9), {"tug": "Heavy"}, False, 400)
    assert v1 > v0, "同随机种子下, 鉴别力应抬高收藏价值"


def test_fisheyes_mentions_king_immunity():
    g = Game(slot="_t_v20", fixed_time=T)
    g.state = S.new_state()
    g.state["gp"] = 400
    assert "鱼王无效" in g.cmd("fisheyes")


def test_two_hop_mooch_chain_exists_in_data():
    """数据里应存在 A→B→C 的两跳坐钩链(AI_GUIDE 宣传的玩法)。"""
    hops = 0
    for f in FISH:
        loc = f.get("location")
        for b in _mooch_targets(loc, f["name"]):
            if _mooch_targets(loc, b["name"]):
                hops += 1
                break
        if hops:
            break
    assert hops, "数据中找不到任何两跳坐钩链"
