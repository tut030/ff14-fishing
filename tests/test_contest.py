"""萌宠大赛(v43) —— python3 -m pytest tests/test_contest.py"""
from engine.game import Game
from engine import save as S
from engine import contest as contest_mod

T = 1_700_000_000


def _fresh(slot="_t_contest"):
    g = Game(slot=slot, fixed_time=T)
    g.state = S.new_state()
    g.state["seed"] = 7
    return g


def _with_pet(g, pid="star_crab"):
    g.state.setdefault("pets", []).append(pid)
    g.state["active_pet"] = pid


def test_lobby_shows_rules_without_pet():
    g = _fresh()
    out = g.cmd("contest")
    assert "萌宠大赛" in out and "summon" in out
    out2 = g.cmd("contest start")            # 没跟宠不能报名
    assert "summon" in out2 and "contest" not in g.state


def test_full_flow_reward_and_stats():
    g = _fresh()
    _with_pet(g)
    mgp0 = g.state.get("mgp", 0)
    out = g.cmd("contest start")
    assert "第1轮·亮相" in out and "star" not in out    # 显示中文名而非id
    g.cmd("contest steady")
    g.cmd("contest steady")
    out = g.cmd("contest steady")             # 第三轮打完自动终评
    assert "终评" in out and "最终榜单" in out and "名次奖" in out
    assert "contest" not in g.state           # 赛后清场
    assert g.state["contest_last_end"] == T   # 冷却计时落账
    st = g.state["contest_stats"]
    assert st["played"] == 1
    assert 3 * contest_mod.STEADY_LO <= st["best"] <= 3 * contest_mod.STEADY_HI
    assert g.state["mgp"] - mgp0 in set(contest_mod.REWARD_MGP.values())


def test_cooldown_blocks_restart():
    g = _fresh()
    _with_pet(g)
    g.cmd("contest start")
    g.cmd("contest 稳; contest 稳; contest 稳")   # 中文别名+分号串联
    out = g.cmd("contest start")
    assert "布景" in out and "contest" not in g.state


def test_quit_sets_cooldown_without_reward():
    g = _fresh()
    _with_pet(g, "otter_pup")
    mgp0 = g.state.get("mgp", 0)
    g.cmd("contest start")
    out = g.cmd("contest quit")
    assert "退了场" in out
    assert "contest" not in g.state
    assert g.state["contest_last_end"] == T
    assert g.state.get("mgp", 0) == mgp0
    assert "contest_stats" not in g.state     # 弃权不计战绩


def test_bond_bonus_is_capped():
    g = _fresh()
    _with_pet(g)
    g.state["pet_bond"] = {"star_crab": 999}
    g.cmd("contest start")
    out = g.cmd("contest steady; contest steady; contest steady")
    assert f"默契加分: +{contest_mod.BOND_CAP}" in out
    lo = 3 * contest_mod.STEADY_LO + contest_mod.BOND_CAP
    hi = 3 * contest_mod.STEADY_HI + contest_mod.BOND_CAP
    assert lo <= g.state["contest_stats"]["best"] <= hi


def test_treat_and_interact_grow_bond():
    g = _fresh()
    _with_pet(g, "otter_pup")
    g.state["gil"] = 100
    g.cmd("pet treat")
    g.cmd("pet 投喂")                          # 中文别名
    assert g.state["pet_bond"]["otter_pup"] == 4     # 投喂每次+2
    assert g.state["gil"] == 100 - 2 * 5
    g.cmd("pet")
    assert g.state["pet_bond"]["otter_pup"] == 5     # 摸摸+1


def test_choice_aliases_and_auto():
    g = _fresh()
    _with_pet(g, "fisher_sprite")
    g.cmd("contest start")
    out = g.cmd("contest 炫")
    assert "本轮 +" in out and "第2轮·才艺" not in out.split("👉")[0][:20]
    out = g.cmd("contest auto")
    assert "它自己拿主意" in out
    out = g.cmd("contest 偏")
    assert "终评" in out


def test_champion_title_fires_end_to_end():
    g = _fresh()
    _with_pet(g)
    g.cmd("contest start")
    for rv in g.state["contest"]["rivals"]:   # 压低对手, 制造必胜局
        rv["rounds"] = [1, 1, 1]
    out = g.cmd("contest steady; contest steady; contest steady")
    assert "冠军" in out
    assert g.state["contest_stats"]["wins"] == 1
    assert "萌力冠军" in out                   # 里程碑称号同步播报
    assert "萌力冠军" in g.state.get("titles", [])


def test_unknown_move_prompts_without_consuming_round():
    g = _fresh()
    _with_pet(g)
    g.cmd("contest start")
    out = g.cmd("contest 翻跟头")
    assert "steady" in out
    assert g.state["contest"]["round"] == 1   # 没消耗轮次
    assert g.state["contest"]["score"] == 0


def test_tie_ranks_player_first_on_board():
    """v43.1回归: 总分并列时榜单「你」在前, 与冠军播报一致。"""
    g = _fresh("_t_tiefix")
    _with_pet(g)
    cs = {"pet": "star_crab", "nick": "星星", "round": 3, "score": 21,
          "rounds": [7, 7, 7],
          "rivals": [
              {"owner": "驿站大姐", "pet": "团子", "flavor": "", "rounds": [7, 7, 7]},
              {"owner": "甜品师", "pet": "泡芙", "flavor": "", "rounds": [5, 5, 5]},
              {"owner": "吟游诗人", "pet": "半音", "flavor": "", "rounds": [4, 4, 4]},
              {"owner": "修竿大婶", "pet": "锉刀", "flavor": "", "rounds": [3, 3, 3]}]}
    out = contest_mod._settle(g.state, cs, now=float(T))
    assert "冠军" in out
    first = [l for l in out.splitlines() if " 1. " in l][0]
    assert "星星" in first and "▶" in first          # 并列时玩家排第1行


def test_settle_writes_diary_event():
    """v43.1: 终评自动进手帐(通用事件条目), diary 命令可翻到。"""
    g = _fresh("_t_cdiary")
    _with_pet(g)
    g.cmd("contest start")
    for _ in range(3):
        g.cmd("contest steady")
    book = g.state.get("diary", [])
    assert book and book[-1].get("kind") == "event"
    assert "萌宠大赛" in book[-1]["text"]
    out = g.cmd("diary")
    assert "萌宠大赛" in out and "金碟游乐场" in out


def test_contest_achievement_debut_broadcast():
    """v43.1: 首场大赛当场播报「初登台」成就并入账 shore_ach。"""
    g = _fresh("_t_cach")
    _with_pet(g)
    g.cmd("contest start")
    g.cmd("contest steady")
    g.cmd("contest steady")
    out = g.cmd("contest steady")
    assert "初登台" in out
    assert "contest_debut" in g.state.get("shore_ach", [])
