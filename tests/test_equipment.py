"""
全身装备系统自动校验
跑法:  cd ff14-fishing && python3 tests/test_equipment.py
作用:  改动装备/GP/定价后跑一遍, 立刻知道有没有改坏。
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from engine import equipment as eq
from engine import gp
from engine import save as save_mod
from engine.game import Game

SLOT = "_eqtest"
SAVE = pathlib.Path(__file__).resolve().parent.parent / "saves" / f"{SLOT}.json"


def _fresh(level=70):
    for p in (SAVE, SAVE.with_suffix(".json.bak")):
        if p.exists():
            p.unlink()
    g = Game(slot=SLOT, fixed_time=1_700_000_000)
    g.state["seed"] = 7
    g.state["level"] = level
    return g


def test_equipment():
    # 1) 数据: 589 件, 全部有三维, 部位/稀有度字段齐
    assert len(eq.ITEMS) == 589
    for it in eq.ITEMS.values():
        assert it["stats"] and it["slot"] and it["rarity"] in (1, 2, 3, 4)

    # 2) 定价规则: 蓝装按等级分层收票; 白/绿装收gil; 紫装非卖
    for it in eq.ITEMS.values():
        cur, amt = eq.price(it)
        if it["rarity"] >= 4:
            assert cur is None
        elif it["rarity"] == 3:
            expect = "purple" if it["level"] >= eq.BLUE_PURPLE_MIN_LEVEL else "white"
            assert cur == expect and amt > 0
        else:
            assert cur == "gil" and amt > 0
        assert eq.price(it) == (cur, amt)          # 抖动是确定性的(可复现)

    # 3) 波动: 同稀有度同等级的两件, 价格不该整齐划一
    blues70 = [it for it in eq.ITEMS.values()
               if it["rarity"] == 3 and it["level"] == 70]
    prices = {eq.price(it)[1] for it in blues70}
    assert len(prices) > 1, "同档价格应有波动"

    # 4) 购买/穿戴/GP联动
    g = _fresh(level=70)
    g.state["scrip_white"] = 0
    assert "不够" in g.cmd("ebuy 大地之峰钓竿")
    g.state["scrip_white"] = 500
    assert "购得" in g.cmd("ebuy 大地之峰钓竿")
    assert "穿上" in g.cmd("wear 大地之峰钓竿")
    base_cap = gp.max_gp(g.state)
    g.state["scrip_white"] = 500
    g.cmd("ebuy 大地之峰手环")
    g.cmd("wear 大地之峰手环")
    assert gp.max_gp(g.state) == base_cap + 74     # 手环采集力+74 → GP上限+74

    # 5) 旧竿回退: 主手空槽时, 旧鱼竿数值仍生效
    g2 = _fresh(level=50)
    from engine import gear
    best = max((r for r in gear.RODS.values() if r["level"] <= 50),
               key=lambda r: r["ilvl"])
    g2.state["rod"] = best["name"]
    g2.state["rods_owned"] = [best["name"]]
    t = eq.stats_total(g2.state)
    assert t["获得力"] == best["gathering"] and t["鉴别力"] == best["perception"]

    # 6) 戒指双槽: 连买两枚落在 戒指1/戒指2
    g3 = _fresh(level=70)
    g3.state["scrip_white"] = 9999
    g3.state["gil"] = 99999                        # 白/绿装收 gil
    rings = [it for it in eq.ITEMS.values()
             if it["slot"] == "戒指" and it["level"] <= 70][:2]
    assert len(rings) == 2
    for r in rings:
        g3.cmd(f"ebuy {r['name']}")
        g3.cmd(f"wear {r['name']}")
    assert g3.state["equip"].get("戒指1") and g3.state["equip"].get("戒指2")

    # 7) 回收: 穿着的不许分解; 分解后移除+产出在上限内
    g4 = _fresh(level=70)
    g4.state["gil"] = 99999
    g4.cmd("ebuy 榉木钓竿")
    g4.cmd("wear 榉木钓竿")
    assert "先换下来" in g4.cmd("recycle 榉木钓竿")
    g4.cmd("ebuy 阿拉米格钓竿")                     # 买一件不穿
    gil0 = g4.state["gil"]
    r = g4.cmd("recycle 阿拉米格钓竿")
    assert "分解" in r
    assert 0 <= g4.state["gil"] - gil0 <= eq.RECYCLE_GIL_MAX
    assert eq.match("阿拉米格钓竿")["id"] not in g4.state["equip_owned"]

    # 7.5) eshop: 低等级查饰品部位应报"最低LvX"而非"没有这个部位"(测1回归)
    g6 = _fresh(level=5)
    r = g6.cmd("eshop 手镯")
    assert "没有这个部位" not in r and "最低 Lv" in r
    assert "没有这个部位" in g6.cmd("eshop 帽子")   # 真不存在的名字才报这个

    # 8) 旧档迁移: 裸档读入后有穿戴字段
    import json
    bare = {"version": 1, "location": "Costa del Sol", "gil": 0,
            "casts": 0, "caught": {}}
    SAVE.parent.mkdir(parents=True, exist_ok=True)
    SAVE.write_text(json.dumps(bare), encoding="utf-8")
    g5 = Game(slot=SLOT, fixed_time=1_700_000_000)
    assert "equip" in g5.state and "materia_shards" in g5.state

    for p in (SAVE, SAVE.with_suffix(".json.bak")):
        if p.exists():
            p.unlink()


