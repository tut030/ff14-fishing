"""雇员系统(3a) 校验 — python3 -m pytest tests/test_retainer.py"""
from engine.game import Game
from engine import save as S, retainer as R, durability as D

T = 1_700_000_000
H = 3600


def _fresh(slot="_t_ret", level=17, gil=5000):
    g = Game(slot=slot, fixed_time=T)
    g.state = S.new_state()
    g.state["seed"] = 7
    g.state["level"] = level
    g.state["gil"] = gil
    g.state.setdefault("equip", {})          # game.py 运行时注入, 夹具手动补齐
    g.state.setdefault("equip_owned", [])
    return g


def _hired(slot="_t_ret_h", cls="捕鱼人"):
    g = _fresh(slot)
    g.cmd(f"hire 小雨 猫魅族 {cls}")
    g.state["seals"] = 9 * R.COIN_SEALS
    g.cmd("venture buy 9")
    return g


# ── 雇佣 ─────────────────────────────────────────────────
def test_hire_level_gate():
    g = _fresh(level=16)
    out = g.cmd("hire 小雨 猫魅族 捕鱼人")
    assert f"Lv{R.HIRE_LV}" in out and not g.state["retainers"]


def test_hire_signs_and_bag_grows():
    g = _fresh()
    cap0 = g._bag_cap()
    out = g.cmd("hire 小雨 猫魅族 捕鱼人")
    assert "小雨" in out and "终身契" in out
    r = g.state["retainers"][0]
    assert r["form_kind"] == "race" and r["cls"] == "fisher" and r["level"] == 1
    assert g._bag_cap() == cap0 + 175


def test_hire_beast_form_uses_moe_pool():
    g = _fresh()
    out = g.cmd("hire 阿咕 青鸟 烹调师")
    r = g.state["retainers"][0]
    assert r["form_kind"] == "beast" and r["form"] in R.MOE
    assert "它" in out                        # 魔兽形态用"它"


def test_hire_rejects_npc_doll_form():
    g = _fresh()
    doll = next(v["name_cn"] for v in R._ALL_LORE.values() if v.get("npc_doll"))
    out = g.cmd(f"hire 小影 {doll} 捕鱼人")
    assert not g.state["retainers"] and "没有" in out


def test_hire_slots_capped_at_two():
    g = _fresh()
    g.cmd("hire 小雨 猫魅族 捕鱼人")
    g.cmd("hire 阿咕 青鸟 烹调师")
    out = g.cmd("hire 三号 人族 捕鱼人")
    assert "名额满" in out and len(g.state["retainers"]) == R.MAX_RETAINERS


# ── 军票经济(旧装备→军票→探险币, gil直购已下架) ──────────
def test_coin_buy_costs_seals_not_gil():
    g = _fresh()
    g.state["seals"] = 3 * R.COIN_SEALS
    g.cmd("venture buy 3")
    assert g.state["venture_coins"] == 3
    assert g.state["seals"] == 0 and g.state["gil"] == 5000   # gil 一分没动


def test_buy_without_seals_hints_trade():
    g = _fresh()
    out = g.cmd("venture buy 1")
    assert "军票" in out and "trade" in out and g.state["venture_coins"] == 0


def test_trade_gear_for_seals():
    g = _fresh()
    from engine import equipment as eq
    it = next(i for i in eq.ITEMS.values() if i["rarity"] < 3 and i["level"] >= 50)
    g.state["equip_owned"].append(it["id"])
    out = g.cmd(f"venture trade {it['name']}")
    got = R._seal_value(it["level"], it["id"])
    assert str(got) in out and g.state["seals"] == got
    assert it["id"] not in g.state["equip_owned"]             # 换掉就没了
    assert got >= R.SEAL_BASE                                 # 低级也有几百保底


def test_trade_refuses_worn_gear():
    g = _fresh()
    from engine import equipment as eq
    it = next(i for i in eq.ITEMS.values() if i["rarity"] < 3)
    g.state["equip_owned"].append(it["id"])
    g.state.setdefault("equip", {})[it["slot"]] = it["id"]    # 穿在身上
    out = g.cmd(f"venture trade {it['name']}")
    assert "穿" in out and g.state.get("seals", 0) == 0


def test_venture_needs_coins():
    g = _fresh()
    g.cmd("hire 小雨 猫魅族 捕鱼人")
    out = g.cmd("venture 小雨 short")
    assert "探险币" in out and g.state["retainers"][0]["venture"] is None
    assert "军票" in out                                      # 指路军票


# ── 派遣与结算 ───────────────────────────────────────────
def test_short_venture_full_cycle():
    g = _hired()
    out = g.cmd("venture 小雨 short")
    assert "出发" in out and g.state["venture_coins"] == 9 - 1
    # 在外时不许再派
    assert "还在外面" in g.cmd("venture 小雨 long")
    # 到点: 任意命令冒一条归队提醒(只提醒一次)
    g.fixed_time = T + H + 60
    assert "回来了" in g.cmd("bag")
    assert "回来了" not in g.cmd("bag")
    # 结算: 有渔获入袋 + 经验 + 出勤数
    out = g.cmd("venture")
    r = g.state["retainers"][0]
    assert "归来" in out and g.state["fish_bag"]
    assert r["venture"] is None and r["trips"] == 1 and (r["xp"] > 0 or r["level"] > 1)


def test_settle_is_deterministic():
    r = {"name": "小雨", "cls": "fisher", "level": 8}
    state = {"seed": 7}
    a = R._roll_fish(R._rng_for(state, r, T + H), r, "short")
    b = R._roll_fish(R._rng_for(state, r, T + H), r, "short")
    assert a == b and a                       # 同一趟结果可复现


def test_level_capped_by_player():
    g = _hired(slot="_t_ret_cap")
    g.state["level"] = 3                      # 雇主只有 Lv3
    g.cmd("venture 小雨 long")
    g.fixed_time = T + 18 * H + 60
    g.cmd("venture")
    assert g.state["retainers"][0]["level"] <= 3


def test_free_exploration_needs_retainer_lv10():
    g = _hired(slot="_t_ret_free")
    out = g.cmd("venture 小雨 free")
    assert f"Lv{R.FREE_MIN_LV}" in out
    assert g.state["retainers"][0]["venture"] is None


def test_surprise_draws_from_moe_only(monkeypatch):
    g = _hired(slot="_t_ret_sup")
    g.state["retainers"][0]["level"] = 10
    monkeypatch.setitem(R.SURPRISE_P, "free", 1.0)     # 必出惊喜
    g.cmd("venture 小雨 free")
    g.fixed_time = T + H + 60
    out = g.cmd("venture")
    got = g.state["lore_pets"]
    assert len(got) == 1 and got[0] in R.MOE           # 萌池内, 角色偶进不来
    assert "惊喜" in out
    assert R.MOE[got[0]]["name_cn"] in g.cmd("retainer dex")


def test_dex_empty_message():
    g = _fresh()
    assert "0/" in g.cmd("retainer dex")


# ── 在家代修(出门大婶兜底) ───────────────────────────────
def test_repair_home_half_price_and_away_fallback():
    g = _hired(slot="_t_ret_fix")
    # 换把有价竿, 磨掉一半
    g.state["rods_owned"].append("Yew Fishing Rod")
    g.state["rod"] = "Yew Fishing Rod"
    g.state.setdefault("rod_dur", {})["Yew Fishing Rod"] = 500
    full, half = D.mender_cost(g.state), D.home_cost(g.state)
    assert half == full // 2 and half > 0
    gil0 = g.state["gil"]
    out = g.cmd("repair home")
    assert "小雨" in out and D.get(g.state) == D.MAX
    assert g.state["gil"] == gil0 - half
    # 派出门后: 代修由大婶兜底
    g.state.setdefault("rod_dur", {})["Yew Fishing Rod"] = 500
    g.cmd("venture 小雨 long")
    out = g.cmd("repair home")
    assert "大婶" in out and D.get(g.state) == 500


# ── 雇员装备(旧装备传给雇员 → 收获数量档) ────────────────
def test_give_gear_raises_tier_and_haul():
    g = _hired(slot="_t_ret_gear")
    from engine import equipment as eq
    r = g.state["retainers"][0]
    assert R.gear_tier(r) == 0 and R._tier_qty(r) == 5        # 裸装=最低档
    # 塞满11槽高品级装备 → 顶到最高档
    picks, used = [], set()
    for it in sorted(eq.ITEMS.values(), key=lambda i: -i["ilvl"]):
        slot = it["slot"] if it["slot"] != "戒指" else "戒指1"
        if slot not in used:
            used.add(slot); picks.append(it)
        if len(used) == 11:
            break
    for it in picks:
        g.state["equip_owned"].append(it["id"])
        g.cmd(f"retainer give 小雨 {it['name']}")
    assert R.gear_tier(r) == 4 and R._tier_qty(r) == 15
    # 短途结算 = 满档 15 条鱼
    g.cmd("venture 小雨 short")
    g.fixed_time = T + H + 60
    g.cmd("venture")
    assert sum(g.state["fish_bag"].values()) == 15


def test_give_swaps_old_piece_back():
    g = _hired(slot="_t_ret_swap")
    from engine import equipment as eq
    a, b = [i for i in eq.ITEMS.values() if i["slot"] == "头部"][:2]
    g.state["equip_owned"] += [a["id"], b["id"]]
    g.cmd(f"retainer give 小雨 {a['name']}")
    g.cmd(f"retainer give 小雨 {b['name']}")
    assert g.state["retainers"][0]["gear"]["头部"] == b["id"]
    assert a["id"] in g.state["equip_owned"]                  # 换下的回行囊


# ── 性别与性格 ───────────────────────────────────────────
def test_gender_default_is_ta_neutral():
    g = _fresh()
    out = g.cmd("hire 小云 精灵族 捕鱼人")
    assert g.state["retainers"][0]["gender"] is None
    assert "它就是你的雇员了" in out                          # 默认它


def test_gender_female_and_male():
    g = _fresh()
    out_f = g.cmd("hire 小雨 猫魅族 捕鱼人 女")
    out_m = g.cmd("hire 阿岩 鲁加族 烹调师 男 稳重")
    rs = {r["name"]: r for r in g.state["retainers"]}
    assert rs["小雨"]["gender"] == "f" and "她就是你的雇员了" in out_f
    assert rs["阿岩"]["gender"] == "m" and rs["阿岩"]["personality"] == "稳重"
    assert "向你稳稳地鞠了一躬" in out_m                     # 性格词生效


def test_personality_wish_and_default():
    g = _fresh()
    out = g.cmd("hire 小影 敖龙族 捕鱼人 急切")
    r = g.state["retainers"][0]
    assert r["personality"] == "急切" and "急急地敬了个不太标准的礼" in out
    g2 = _fresh(slot="_t_ret_p2")
    g2.cmd("hire 小影 敖龙族 捕鱼人")                          # 不许愿→随缘但可复现
    assert g2.state["retainers"][0]["personality"] in R.PERSONALITIES


# ── 经验表(wiki官方数据·同一台压缩机) ────────────────────
def test_xp_uses_wiki_table_with_floor_fallback():
    from engine.leveling import _compress
    assert R._venture_xp("long", 17) == max(10, int(_compress(174000) * R.XP_MULT["long"]))
    assert R._hunt_at(R._EXP, 50) == R._EXP[49]               # 缺档向下取
    assert R._venture_xp("short", 1) < R._venture_xp("long", 1)


# ── 全职业(3c): 战斗职业猎获+见闻, 采集生产不带鱼 ────────
def test_combat_job_hunts_and_tells_tales():
    g = _fresh(slot="_t_ret_war")
    g.state["seals"] = 2 * R.COIN_SEALS
    g.cmd("hire 阿刃 鲁加族 暗黑骑士 女")
    r = g.state["retainers"][0]
    assert r["cls"] == "暗黑骑士" and R._cat(r) == "combat"
    g.cmd("venture buy 2")
    g.cmd("venture 阿刃 short")
    g.fixed_time = T + H + 60
    out = g.cmd("venture")
    assert "近郊讨伐" in out                       # 讨伐口径
    assert "🗡 猎获" in out and "📖 见闻" in out    # 素材+见闻
    assert sum(g.state["hunt_stock"].values()) == 5  # 裸装档=5件
    assert sum(g.state["fish_bag"].values()) == 0    # 战斗职业不带鱼
    assert any(t in out for t in R.TALES)


def test_gatherer_no_fish_more_seasonings():
    g = _fresh(slot="_t_ret_btn")
    g.state["seals"] = 2 * R.COIN_SEALS
    g.cmd("hire 小苗 拉拉菲尔族 园艺工")
    g.cmd("venture buy 2")
    g.cmd("venture 小苗 long")
    g.fixed_time = T + 18 * H + 60
    out = g.cmd("venture")
    assert sum(g.state["fish_bag"].values()) == 0
    assert "🧂 调料" in out                        # 调料是主业


def test_jobs_list_covers_all():
    g = _fresh(slot="_t_ret_jobs")
    out = g.cmd("retainer jobs")
    for j in ("骑士", "贤者", "蝰蛇剑士", "绘灵法师", "园艺工", "炼金术士"):
        assert j in out


# ── 职业武器(琪琪茹代购, 旧武器折军票) ───────────────────
def test_arms_buy_equip_and_fold_old():
    g = _fresh(slot="_t_ret_arm", gil=99999)
    g.cmd("hire 阿刃 鲁加族 暗黑骑士")
    lst = R.ARMS["暗黑骑士"]
    a0, a1 = lst[0], lst[1]
    r = g.state["retainers"][0]
    # 等级门: 够不着的武器买不了
    out = g.cmd(f"retainer give 阿刃 {a1['name_cn']}")
    assert "需要 Lv" in out and r.get("arm") is None
    out = g.cmd(f"retainer give 阿刃 {a0['name_cn']}")
    assert r["arm"] == a0["name_cn"] and "-" in out
    assert g.state["gil"] == 99999 - R._arm_price(a0)
    # 练上去换第二把: 旧的自动折军票
    g.state["level"] = 99
    r["level"] = a1["level"]
    out = g.cmd(f"retainer give 阿刃 {a1['name_cn']}")
    assert r["arm"] == a1["name_cn"] and "折了" in out
    assert g.state["seals"] > 0


def test_arms_wrong_job_refused():
    g = _fresh(slot="_t_ret_armx", gil=99999)
    g.cmd("hire 小雨 猫魅族 白魔法师")
    axe = R.ARMS["战士"][0]
    out = g.cmd(f"retainer give 小雨 {axe['name_cn']}")
    assert "使不了" in out and g.state["retainers"][0].get("arm") is None


def test_combat_mainhand_locked_for_fishing_gear():
    g = _fresh(slot="_t_ret_lock")
    from engine import equipment as eq
    g.cmd("hire 阿刃 鲁加族 骑士")
    mh = next(i for i in eq.ITEMS.values() if i["slot"] == "主手")
    g.state["equip_owned"].append(mh["id"])
    out = g.cmd(f"retainer give 阿刃 {mh['name']}")
    assert "主手位归职业武器" in out
    assert g.state["retainers"][0]["gear"].get("主手") is None


# ── 内存卡(3b): 现实联动补给品 ──────────────────────────
def test_memory_card_drop_and_viewer(monkeypatch):
    g = _hired(slot="_t_ret_mem")
    monkeypatch.setitem(R.MEMCARD_P, "short", 1.0)   # 必掉便于验证
    g.cmd("venture 小雨 short")
    g.fixed_time = T + H + 60
    out = g.cmd("venture")
    assert "💾 内存卡" in out and sum(g.state["memory_cards"].values()) == 1
    view = g.cmd("retainer card")
    assert "内存卡收藏(1张" in view


def test_male_pronoun_uses_name():
    g = _fresh(slot="_t_ret_he")
    out = g.cmd("hire 阿岩 鲁加族 锻铁匠 男")
    r = g.state["retainers"][0]
    assert R._pron(r) == "阿岩"                      # 男性代词位=名字
    assert "阿岩就是你的雇员了" in out
