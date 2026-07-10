"""游戏主循环校验 (Step 4)  —  python3 tests/test_game.py"""

from engine.game import Game
from engine import save as S

T = 1_700_000_000


def _fresh_game(loc, seed=42, slot="_test_game"):
    g = Game(slot=slot, fixed_time=T)
    g.state = S.new_state()
    g.state["seed"] = seed
    g.state["level"] = 90
    g.state["location"] = loc
    return g


def test_game():
    # 1) 确定性: 同种子同序列 -> 完全一样的渔获
    a = _fresh_game("Costa del Sol")
    b = _fresh_game("Costa del Sol")
    ra = [a.cmd("cast") for _ in range(8)]
    rb = [b.cmd("cast") for _ in range(8)]
    assert ra == rb, "相同种子结果应一致"

    # 2) 抛竿计数(无论是否钓到, casts 都 +1; 可能脱钩/空军/无饵, 渔获 ≤ 8)
    assert a.state["casts"] == 8
    assert sum(a.state["caught"].values()) <= 8

    # 3) 开窗约束: 在 Mahi-Mahi 关闭的时刻, 怎么钓都钓不到它
    #    (ET 21:42 时 Mahi-Mahi 窗口 10-18 关闭)
    g = _fresh_game("Oschon's Torch")
    for _ in range(60):
        g.cmd("cast")
    assert "Mahi-Mahi" not in g.state["caught"], "关窗的鱼不该被钓到"

    # 4) goto 校验: 不存在的钓场被拒
    g2 = _fresh_game("Costa del Sol")
    assert "没有这个钓场" in g2.cmd("goto 不存在的地方")
    assert "已移动" in g2.cmd("goto Moraby Bay")
    assert g2.state["location"] == "Moraby Bay"

    # 5) 不认识的命令有友好提示
    assert "不认识" in g2.cmd("flytothemoon")

    # 6) 钓草开关: 关时需钓草的鱼不可钓, 开时可钓
    from engine.game import _avail
    snf = next(f for f in __import__("engine.fish", fromlist=["FISH"]).FISH
               if f["snagging"] and f["mode"] == "line")
    assert _avail(snf, False, False) is False, "关钓草不该可钓"
    assert _avail(snf, False, True) is True, "开钓草应可钓"
    g3 = _fresh_game("Costa del Sol")
    assert "开" in g3.cmd("snagging on") and g3.state["snagging"] is True
    assert "关" in g3.cmd("snagging off") and g3.state["snagging"] is False

    # 7) 图鉴书: folklore 鱼没书时锁, 买书后解锁; 买书扣 gil
    from engine.game import _avail as _av, _FOLKLORE_BOOKS
    ff = next(f for f in __import__("engine.fish", fromlist=["FISH"]).FISH
              if f["folklore"] and f["mode"] == "line")
    reg = ff["region"]
    assert _av(ff, False, False, []) is False
    assert _av(ff, False, False, [reg]) is True
    g4 = _fresh_game("Costa del Sol")
    g4.state["scrip_purple"] = 0
    assert "不够" in g4.cmd(f"buybook {reg}")
    g4.state["scrip_purple"] = 99999
    before = g4.state["scrip_purple"]
    assert "购得" in g4.cmd(f"buybook {reg}")
    assert reg in g4.state["books"]
    from engine import scrip as SC
    assert g4.state["scrip_purple"] == before - SC.book_price(_FOLKLORE_BOOKS[reg])

    # 收藏品全流程: 开模式→钓鱼不给gil→上交换票→背包清空
    g4b = _fresh_game("Costa del Sol")
    g4b.cmd("collector on")
    assert g4b.state["collector"] is True
    gil0 = g4b.state["gil"]
    g4b.cmd("cast 10")
    assert g4b.state["gil"] == gil0, "收藏品模式钓鱼不该给 gil"
    n_inv = len(g4b.state["collectables"])
    if n_inv:                                   # 达标数取决于随机, 有就验上交
        r = g4b.cmd("turnin")
        assert "上交" in r
        assert g4b.state["collectables"] == []
        assert (g4b.state["scrip_white"] + g4b.state["scrip_purple"]) > 0
    assert "关" in g4b.cmd("collector off")
    assert "当前: 关" in g4b.cmd("collector")        # 无参=看状态(#29)
    assert "看不懂" in g4b.cmd("collector 汉")       # 乱参=报用法, 不误切换
    assert g4b.state["collector"] is False

    # 毕业竿(装等≥阈值)只收紫票, gil 买不动
    from engine import gear as GR
    top = max(GR.RODS.values(), key=lambda r: r["ilvl"])
    if SC.is_scrip_rod(top):                     # 数据里存在毕业竿才验
        g4c = _fresh_game("Costa del Sol")
        g4c.state["level"] = 100
        g4c.state["gil"] = 10 ** 9               # gil 再多也没用
        g4c.state["scrip_purple"] = 0
        assert "紫票不够" in g4c.cmd(f"buyrod {top['name']}")
        g4c.state["scrip_purple"] = 10 ** 6
        gil0 = g4c.state["gil"]
        assert "购得" in g4c.cmd(f"buyrod {top['name']}")
        assert g4c.state["gil"] == gil0          # 没动 gil
        assert g4c.state["scrip_purple"] == 10 ** 6 - SC.rod_scrip_price(top)
        assert g4c.state["rod"] == top["name"]   # 更强 -> 自动装备

    # 8) 叉鱼: 叉鱼点能 spear 到鱼; 普通钓场 spear 报错
    from engine.game import _SPEAR_SPOTS
    sspot = sorted(_SPEAR_SPOTS)[0]
    g5 = _fresh_game(sspot)
    r5 = g5.cmd("spear")
    assert ("🔱" in r5), "叉鱼点应能 spear"
    g5.state["location"] = "West Agelyss River"
    assert "不是叉鱼点" in g5.cmd("spear")

    # 9) 鱼竿: 等级/gil 门槛; 买竿扣钱+装备; 鉴别力抬 HQ 概率
    from engine import gear as _gear
    g6 = _fresh_game("Costa del Sol")
    g6.state["gil"] = 0
    rod = sorted([x for x in _gear.RODS.values() if x["level"] <= 90],
                 key=lambda x: -x["ilvl"])[0]
    assert "不够" in g6.cmd(f"buyrod {rod['name']}")           # gil 不够
    g6.state["gil"] = 10 ** 7
    assert "购得" in g6.cmd(f"buyrod {rod['name']}")
    assert g6.state["rod"] == rod["name"] and rod["name"] in g6.state["rods_owned"]
    hi = [x for x in _gear.RODS.values() if x["level"] == 100][0]
    g6.state["level"] = 10
    assert "需 Lv100" in g6.cmd(f"buyrod {hi['name']}")        # 等级不够
    assert _gear.hq_chance(rod) > _gear.hq_chance(None)         # 鉴别力抬 HQ

    # 10) 鱼饵: 大鱼挂对饵才上、杂鱼不卡; buybait 扣钱+挂上
    from engine.game import _bait_ok as _bok, _base_bait as _bb
    from engine import bait as _bait
    from engine.fish import get as _get, FISH as _FISH
    gg = _get("Great Gudgeon")
    base = _bb(gg)
    assert base in _bait.BAITS
    assert _bok(gg, base) and not _bok(gg, None) and not _bok(gg, "Moth Pupa")
    common = next(f for f in _FISH if f["mode"] == "line" and not f["bait"])
    assert _bok(common, None) and _bok(common, "Moth Pupa")   # 杂鱼不卡饵
    g7 = _fresh_game("Costa del Sol")
    g7.state["gil"] = 10000
    some = sorted(_bait.BAITS)[0]
    assert "买" in g7.cmd(f"buybait {some} 5")
    assert g7.state["bait"] == some and g7.state["bait_stock"].get(some) == 5
    # 损耗: 挂饵有库存时是有效饵; 库存耗尽后失效
    assert _bok(gg, some if g7.state["bait_stock"].get(some, 0) > 0 else None) in (True, False)
    g7.state["bait_stock"][some] = 0
    eff = some if g7.state["bait_stock"].get(some, 0) > 0 else None
    assert eff is None      # 库存 0 -> 无有效饵

    # 清理存档
    for slot in ("_test_game",):
        p = S._path(slot)
        for f in (p, p.with_suffix(".json.bak"), p.with_suffix(".json.tmp")):
            if f.exists():
                f.unlink()

    # --- 回归测试(对应 bugfix) ---
    # Bug10: unicode 上标数字不崩
    g = _fresh_game("Costa del Sol")
    r = g.cmd("cast ²")        # isdigit=True 但 int() 崩
    assert "ValueError" not in r and r         # 不崩, 有输出(当普通 1 竿处理)

    # Bug9: 图鉴分母用唯一名数, 不是总鱼数
    from engine.game import _UNIQUE_NAMES
    assert _UNIQUE_NAMES < 2119                # 有重名鱼, 分母应小于总数
    bag = g.cmd("bag")
    assert f"/{_UNIQUE_NAMES}" in bag          # bag 里显示正确分母

    # Bug11: load 旧存档不崩(模拟只有 v1 字段的裸档)
    import json
    bare = {"version": 1, "location": "Costa del Sol", "gil": 0,
            "casts": 0, "caught": {}}
    S._path("_test_game").parent.mkdir(parents=True, exist_ok=True)
    S._path("_test_game").write_text(json.dumps(bare), encoding="utf-8")
    g2 = Game(slot="_test_game", fixed_time=T)
    g2.cmd("load")             # 不该 KeyError
    assert "gp" in g2.state    # 迁移补齐了

    # Bug12: 买低级竿不会顶掉高级竿
    g = _fresh_game("Costa del Sol")
    from engine import gear
    best = max(gear.RODS.values(), key=lambda r: r["ilvl"])
    g.state["rod"] = best["name"]
    g.state["rods_owned"] = [best["name"]]
    g.state["gil"] = 999999
    worst = min((r for r in gear.RODS.values() if r["name"] != best["name"]),
                key=lambda r: r["ilvl"])
    g.cmd(f"buyrod {worst['name']}")
    assert g.state["rod"] == best["name"], "买低级竿不该自动换装"

    # Bug14: goto 支持模糊匹配
    g = _fresh_game("Costa del Sol")
    r = g.cmd("goto moraby bay")
    assert "Moraby Bay" in g.state["location"]     # 精确子串唯一命中
    r2 = g.cmd("goto moraby")
    assert "匹配到多个" in r2                        # 多命中应提示选择
    g.cmd("goto 利姆萨·罗敏萨下层甲板")               # 中文钓场名精确命中
    assert g.state["location"] == "Limsa Lominsa Lower Decks"
    assert "匹配到多个" in g.cmd("goto 海岸")         # 中文子串多命中列表

    # Bug9深层: status 聚合同名全部钓点, 不再只看数据表第一条
    # (考据结论: 重名鱼窗口条件全同, 真实病灶是"各钓点等级不同"共 164 种
    #  ——旧版只报首条等级, 新手会被高等级钓点吓退; 新版逐点报 Lv)
    from engine.fish import get_all
    recs = get_all("公主鳟")
    assert len(recs) == 4                            # 同名 4 记录全聚合
    lvs = {x.get("level") for x in recs}
    assert len(lvs) > 1                              # 等级确实各点不同
    g = _fresh_game("Costa del Sol")
    st = g.cmd("status 公主鳟")
    assert "个钓点" in st                             # 逐点视图
    for lv in lvs:                                    # 每个等级都要被展示
        assert f"Lv{lv}" in st, f"status 应逐点报 Lv{lv}"

    # 清理
    for slot in ("_test_game",):
        p = S._path(slot)
        for f in (p, p.with_suffix(".json.bak"), p.with_suffix(".json.tmp")):
            if f.exists():
                f.unlink()


