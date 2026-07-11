"""钓鱼手帐 校验 — python3 -m pytest tests/test_diary.py"""
import random

from engine.game import Game
from engine import save as S, diary as DY
from engine.fish import FISH

T = 1_700_000_000


def _fresh(slot="_t_dy"):
    g = Game(slot=slot, fixed_time=T)
    g.state = S.new_state()
    g.state["seed"] = 7
    g.state["level"] = 50
    return g


def _land(g, f, size=5.0, hq=False, bait="Lugworm"):
    g.state["location"] = f["location"]
    return g._land_fish(f, hq, size, random.Random(1), now=g._now(), used=[],
                        wait=3, tell="!", descr="", bait_name=bait)


_F = next(f for f in FISH if f.get("tug") != "Legendary")
_LEG = next(f for f in FISH if f.get("tug") == "Legendary")


def test_first_catch_writes_fact_entry():
    g = _fresh()
    r = _land(g, _F, size=7.7)
    assert r["diary_id"] == 1
    e = g.state["diary"][0]
    assert e["fish"] == _F["name"] and e["size"] == 7.7
    assert "first" in e["reasons"]
    assert e["weather"] and e["et"] and e["loc"] == _F["location"]  # 事实半齐全
    assert e["moods"] == []                                         # 心情半留白


def test_ordinary_repeat_not_logged():
    g = _fresh()
    _land(g, _F, size=7.7)
    r = _land(g, _F, size=3.0)          # 同种更小: 不新不破纪录
    assert r["diary_id"] is None and len(g.state["diary"]) == 1


def test_record_break_logs_with_prev():
    g = _fresh()
    _land(g, _F, size=7.7)
    r = _land(g, _F, size=9.9)
    assert r["diary_id"] == 2
    e = g.state["diary"][1]
    assert "record" in e["reasons"] and e["prev_rec"] == 7.7


def test_legendary_always_special():
    g = _fresh()
    g.state["records"][_LEG["name"]] = 99.0     # 既非新种(压掉first?)——是新种但也验鱼王标
    r = _land(g, _LEG, size=50.0)
    e = g.state["diary"][0]
    assert "legendary" in e["reasons"] and r["diary_id"] == 1


def test_mood_appends_never_overwrites():
    g = _fresh()
    _land(g, _F)
    g.cmd("diary mood 第一次翻看, 还在得意 | Cmaj7 → G6 · 84bpm")
    g.cmd("diary mood 1 第二次翻看, 想念那天的风")
    ms = g.state["diary"][0]["moods"]
    assert len(ms) == 2                                  # 只追加
    assert "得意" in ms[0]["text"] and "想念" in ms[1]["text"]
    out = g.cmd("diary 1")
    assert "Cmaj7" in out and "想念" in out              # 全览两笔都在


def test_diary_browse_and_filter():
    g = _fresh()
    _land(g, _F)
    _land(g, _LEG)
    out = g.cmd("diary")
    assert "共2条" in out
    out = g.cmd(f"diary {_LEG['name']}")
    assert "#2" in out and "#1" not in out               # 按鱼检索只出它


def test_game_never_writes_moods():
    g = _fresh()
    _land(g, _F, size=7.7)
    _land(g, _F, size=9.9)
    assert all(e["moods"] == [] for e in g.state["diary"])   # 心情永远留给玩家


def test_old_save_without_diary_key_safe():
    g = _fresh(slot="_t_dy_old")
    g.state.pop("diary", None)                           # 模拟老档
    r = _land(g, _F)
    assert r["diary_id"] == 1 and len(g.state["diary"]) == 1
