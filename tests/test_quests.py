"""
职业任务自动校验
跑法:  cd ff14-fishing && python3 tests/test_quests.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from engine import quests
from engine.fish import get
from engine.game import Game

SLOT = "_qstest"
SAVE = pathlib.Path(__file__).resolve().parent.parent / "saves" / f"{SLOT}.json"


def _fresh(level=1):
    for p in (SAVE, SAVE.with_suffix(".json.bak")):
        if p.exists():
            p.unlink()
    g = Game(slot=SLOT, fixed_time=1_700_000_000)
    g.state["seed"] = 7
    g.state["level"] = level
    return g


def test_quests():
    # 1) 数据: 20 个任务(每5级一篇), 等级递增, 任务鱼全部真实存在
    assert len(quests.QUESTS) == 20
    lvs = [q[0] for q in quests.QUESTS]
    assert lvs == sorted(lvs) and len(set(lvs)) == 20
    for _lv, _t, story, fname, _loc in quests.QUESTS:
        assert get(fname), f"任务鱼不存在: {fname}"
        assert story.strip()

    # 2) 解锁逻辑: 等级门槛 + 完成排除
    assert [q[0] for q in quests.available(12, [])] == [5, 10]
    assert [q[0] for q in quests.available(12, [5])] == [10]
    assert quests.newly_unlocked([4, 5, 6]) == [5]
    assert quests.newly_unlocked([7]) == []

    # 3) 流程: 未钓到不能交差; 钓到后交差发奖并标记
    g = _fresh(level=10)
    assert "🔒" in g.cmd("quests") and "🔓" in g.cmd("quests")
    assert "还没解锁" in g.cmd("quest 70")
    assert "还没有可交差" in g.cmd("quest done")
    g.state["caught"]["Brass Loach"] = 1          # Lv5 任务鱼进图鉴
    assert "可交差" in g.cmd("quest 5")
    gil0, w0 = g.state["gil"], g.state.get("scrip_white", 0)
    r = g.cmd("quest done")
    assert "交差" in r and 5 in g.state["quests_done"]
    rw = quests.reward_of(5)
    assert g.state["gil"] == gil0 + rw["gil"]
    assert g.state.get("scrip_white", 0) == w0 + rw["white"]
    assert "✅" in g.cmd("quests")                 # 列表里出现已完成标记
    assert "还没有可交差" in g.cmd("quest done")     # 不能重复交差

    # 4) 升级提醒: 跨过任务等级时播报出现
    g2 = _fresh(level=1)
    assert "职业任务解锁" in g2._quest_hint([4, 5])
    assert g2._quest_hint([6, 7]) == ""

    for p in (SAVE, SAVE.with_suffix(".json.bak")):
        if p.exists():
            p.unlink()


