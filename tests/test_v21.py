"""v21 尾巴清理: 专一垂钓/拍击水面/多重提钩/宠物取名"""
from engine.game import Game
from engine import save as S

T = 1_700_000_000


def _fresh(slot):
    g = Game(slot=slot, fixed_time=T)
    g.state = S.new_state()
    g.state["seed"] = 5
    g.state["gp"] = 900
    return g


def _cast_until_catch(g, tries=10):
    for _ in range(tries):
        g.cmd("cast")
        if g.state.get("last_catch"):
            return g.state["last_catch"]
    return None


def test_identical_forces_same_species():
    g = _fresh("_t_ident")
    first = _cast_until_catch(g)
    assert first, "起手怎么也该钓到一条"
    g.cmd("identical")
    assert g.state["buff_identical"] == first
    g.state["last_catch"] = None
    got = _cast_until_catch(g)
    assert got == first, f"专一垂钓应死盯 {first}, 却钓到 {got}"
    assert not g.state.get("buff_identical"), "钓起后应消耗"


def test_slap_bans_species_until_next_catch():
    g = _fresh("_t_slap")
    first = _cast_until_catch(g)
    g.cmd("slap")
    assert g.state["buff_slap"] == first
    g.state["last_catch"] = None
    got = _cast_until_catch(g)
    if got:                                   # 有渔获: 必不是被拍走的那条, 且 buff 清除
        assert got != first
        assert not g.state.get("buff_slap")


def test_doublehook_doubles_catch():
    g = _fresh("_t_dh")
    g.cmd("doublehook")
    assert g.state["buff_dh"] == 2
    got = _cast_until_catch(g)
    assert got
    assert g.state["fish_bag"].get(got, 0) + g.state["fish_bag"].get(got + "|HQ", 0) >= 2
    assert g.state["caught"][got] >= 2
    assert not g.state.get("buff_dh")


def test_pet_and_mount_rename():
    g = _fresh("_t_name")
    g.state["pets"] = ["golden_chocobo"]
    g.state["active_pet"] = "golden_chocobo"
    out = g.cmd("pets name 小金子")
    assert "小金子" in out
    assert g.state["pet_names"]["golden_chocobo"] == "小金子"
    out2 = g.cmd("mounts name 会飞的")
    assert "先 ride" in out2                   # 没骑坐骑时给引导
