"""
魔晶石系统自动校验
跑法:  cd ff14-fishing && python3 tests/test_materia.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from engine import materia as mat
from engine import equipment as eq
from engine.game import Game

SLOT = "_mattest"
SAVE = pathlib.Path(__file__).resolve().parent.parent / "saves" / f"{SLOT}.json"


def _fresh(seed=7):
    for p in (SAVE, SAVE.with_suffix(".json.bak")):
        if p.exists():
            p.unlink()
    g = Game(slot=SLOT, fixed_time=1_700_000_000)
    g.state["seed"] = seed
    g.state["level"] = 70
    g.state["gil"] = 99999
    g.state["scrip_white"] = 9999
    g.state["scrip_purple"] = 9999
    g.state["materia_shards"] = 50
    return g


def test_materia():
    # 1) 数据: 三系×12品级=36颗, 名字数值齐全
    assert len(mat.MATERIA) == 36
    params = {m["param"] for m in mat.MATERIA.values()}
    assert params == {"获得力", "鉴别力", "采集力"}
    for m in mat.MATERIA.values():
        assert m["name"] and m["value"] > 0 and 1 <= m["grade"] <= 12

    # 2) 票价分层: 低品级白票, 高品级紫票
    for m in mat.MATERIA.values():
        cur, amt = mat.price(m)
        assert amt > 0
        assert cur == ("purple" if m["grade"] >= mat.PURPLE_MIN_GRADE else "white")

    # 3) 购买/碎片合成
    g = _fresh()
    assert "购得" in g.cmd("mbuy 达识魔晶石伍型")
    sh0 = g.state["materia_shards"]
    assert "合成" in g.cmd("mcraft 器识魔晶石叁型")
    assert g.state["materia_shards"] == sh0 - mat.SHARD_COST_LOW

    # 4) 保底孔镶嵌 100% 成功, 且穿上后进全身三维
    g.cmd("ebuy 榉木钓竿")                 # 绿装 1孔·可禁断
    g.cmd("wear 榉木钓竿")
    base = eq.stats_total(g.state)["获得力"]
    r = g.cmd("meld 榉木钓竿 达识魔晶石伍型")
    assert "保底孔镶嵌成功" in r
    assert eq.stats_total(g.state)["获得力"] == base + 10   # 伍型获得力+10

    # 5) 规则拒绝: 0孔且不可禁断的蓝装 / 超过5颗上限
    g.state["scrip_white"] = 9999
    g.cmd("ebuy 渔采钓竿")                 # 蓝装 0孔·不可禁断
    g.cmd("mbuy 达识魔晶石伍型")
    assert "⛔" in g.cmd("meld 渔采钓竿 达识魔晶石伍型")
    ok, is_over, slot, why = mat.meld_plan(
        {"sockets": 1, "overmeld": True}, mat.MAX_MELDS)
    assert not ok and "上限" in why

    # 6) 禁断: 消耗必然发生, 成功/失败两种结局都真实存在(扫种子)
    seen = set()
    for seed in range(1, 40):
        g2 = _fresh(seed=seed)
        g2.cmd("ebuy 榉木钓竿")
        g2.cmd("mbuy 达识魔晶石伍型")
        g2.cmd("meld 榉木钓竿 达识魔晶石伍型")     # 占掉保底孔
        g2.cmd("mbuy 达识魔晶石陆型")
        inv_before = dict(g2.state["materia_inv"])
        r = g2.cmd("meld 榉木钓竿 达识魔晶石陆型")  # 禁断第1颗(45%)
        assert "禁断" in r
        assert g2.state["materia_inv"].get(
            str(mat.match("达识魔晶石陆型")["id"]), 0) == \
            inv_before.get(str(mat.match("达识魔晶石陆型")["id"]), 1) - 1
        seen.add("失败" if "失败" in r else "成功")
        if seen == {"成功", "失败"}:
            break
    assert seen == {"成功", "失败"}, f"40个种子内应两种结局都出现, 只见到 {seen}"

    for p in (SAVE, SAVE.with_suffix(".json.bak")):
        if p.exists():
            p.unlink()


