"""鱼竿耐久与修理。
修理工: 斯塔薇布/Staelwyb, 推工具车的路格萨姆女性, 哪个钓场都能"正好路过"。
数值内部用"千分点"整数存(1000 = 100.0%), 避免浮点误差。
"""

MAX = 1000            # 常规满耐久 = 100.0%
SELF_MAX = 1990       # 自修上限 = 199.0%(原作: 自修可超到199%)
WEAR_CAST = 1         # 每竿 -0.1%
WEAR_SKILL = 2        # precision/powerful 额外 -0.2%(鱼王磨竿)
MENDER_RATE = 0.60    # 大婶费率: 竿价 60% × 损耗比例
MENDER_FLOOR = 100    # 修理费下限(有价竿)
FREE_RODS = {"Weathered Fishing Rod"}   # 初始破竿免费修(新手保护)

# 暗物质: (竿等级下限, 上限, 名称, 单价)
GRADES = [(1, 49, "G1暗物质", 50),
          (50, 69, "G2暗物质", 300),
          (70, 999, "G3暗物质", 1000)]

# 低耐久阈值(千分点) -> 提醒文案; 数字越小越严重
TIERS = [
    (0,   "💥 竿身彻底罢工了——属性归零! 它还能甩, 但那只是一根木棍。repair 求医。"),
    (200, "⚠ 竿子伤得不轻(≤20%): 采集/鉴别减半。再不修, 稀有鱼都懒得理你。"),
    (500, "🔧 竿子磨损过半了。斯塔薇布的工具车吱呀声仿佛就在附近……(repair)"),
    (800, "🎣 竿身出现了细小的裂纹。还能用, 但记得疼它。"),
]

CATCH_ALL = "咋又坏了, 没少到处扑腾吧。诶哟。"   # 大婶口头禅


# ── 基础读写 ─────────────────────────────────────────
def _rod_key(state: dict) -> str:
    """当前竿的名字(新装备系统主手优先, 回退旧竿, 再回退初始竿)。"""
    eq = state.get("equip", {}) or {}
    iid = eq.get("主手")
    if iid:
        try:
            from . import equipment as _eq
        except ImportError:
            import equipment as _eq
        it = _eq.ITEMS.get(iid)
        if it:
            return it.get("name", str(iid))
    return state.get("rod") or "Weathered Fishing Rod"


def get(state: dict) -> int:
    """当前竿的耐久(千分点)。新竿/首次见到 = 满。"""
    d = state.setdefault("rod_dur", {})
    return d.setdefault(_rod_key(state), MAX)


def _set(state: dict, val: int):
    state.setdefault("rod_dur", {})[_rod_key(state)] = max(0, min(SELF_MAX, val))


def pct(state: dict) -> int:
    """整数百分比(向下取整), 状态栏用。"""
    return get(state) * 100 // 1000


def _tier(dur: int) -> int:
    """当前所处阈值档(TIERS 下标; -1 = 健康)。"""
    for i, (lim, _msg) in enumerate(TIERS):
        if dur <= lim:
            return i
    return -1


def apply_wear(state: dict, amount: int):
    """磨损 amount 千分点。不产出文案(文案由 pending_note 统一发)。"""
    if amount <= 0:
        return
    _set(state, get(state) - amount)


def pending_note(state: dict) -> str:
    """若耐久已跌进新的阈值档且尚未提醒过, 返回一条提醒并记账; 否则空串。"""
    t = _tier(get(state))
    warned = state.get("dur_warned", -1)
    if t >= 0 and (warned < 0 or t < warned):
        state["dur_warned"] = t
        return TIERS[t][1]
    if t < 0:
        state["dur_warned"] = -1          # 修好后复位, 下次磨损重新提醒
    return ""


def stat_factor(state: dict) -> float:
    """耐久对竿属性的系数: >20% 全额; ≤20% 减半; =0 归零。"""
    d = get(state)
    if d <= 0:
        return 0.0
    if d <= 200:
        return 0.5
    return 1.0


# ── 价格与暗物质 ─────────────────────────────────────
def _rod_info(state: dict):
    """(竿名, 竿价gil或0, 竿等级)。票价竿按紫票基准折算gil参考价。"""
    name = _rod_key(state)
    try:
        from . import gear as _gear
    except ImportError:
        import gear as _gear
    rod = _gear.RODS.get(name)
    if rod:
        try:
            price = _gear.price(rod)             # 与竿店同一套定价
        except Exception:
            price = 0
        return name, price, rod.get("level", 1)
    return name, 0, state.get("level", 1)


def grade_for(rod_level: int):
    """竿等级 -> (暗物质名, 单价)。"""
    for lo, hi, gname, gprice in GRADES:
        if lo <= rod_level <= hi:
            return gname, gprice
    return GRADES[-1][2], GRADES[-1][3]


def mender_cost(state: dict) -> int:
    """大婶修到100%的报价。满耐久(含超修) = 0; 免费竿 = 0。"""
    name, price, _lv = _rod_info(state)
    d = get(state)
    if d >= MAX:
        return 0
    if name in FREE_RODS or price <= 0:
        return 0
    worn = (MAX - d) / MAX
    return max(MENDER_FLOOR, int(price * MENDER_RATE * worn))


# ── 学徒任务《大婶的工具车》────────────────────────────
QUEST_LV = 30
QUEST_FOOD_NEED = 3

QUEST_ACT1 = (
    "🛒 一辆吱呀作响的工具车不知何时停在了你身后。\n"
    "   你的竿在大婶面前\"啪\"一声, 叫的凄惨。\n"
    f"   大婶:\"{CATCH_ALL}\"\n"
    "   (仔细检查, 笃定的开口)\"我听懂了, 你的竿想跑路。\"\n"
    "   她边修边开课, 学费是跑腿: 她让你去她死对头泡泡莉那儿买三份食物回来。\n"
    "   大婶(沉稳的开口):\"……别说是我要的。\"\n"
    "   📜 接取《大婶的工具车》—— foodshop 买 3 份食物, 再来 repair 交差。")

QUEST_ACT3 = (
    "📜 交差《大婶的工具车》——你把顺路多带的三份食物递过去(自己吃掉的那几份不算, 她看得很紧)。\n"
    "   大婶接过, 表情没变, 耳朵动了动。\n"
    "   她塞来一块暗物质:\"出远门的时候得学会自己修啊。\"\n"
    "   → 解锁 repair self(自修至199%), 送 G1暗物质×2!")


def quest_stage(state: dict) -> int:
    """0=未接 1=进行中 2=已完成。"""
    return state.get("mender_quest", 0)


# ── repair 命令族 ────────────────────────────────────
def menu(state: dict, now: float | None = None) -> str:
    """repair —— 工具车菜单(耐久/报价/暗物质/自修状态)。"""
    name, price, rlv = _rod_info(state)
    d = get(state)
    gname, gprice = grade_for(rlv)
    stock = state.get("dark_matter", {}).get(gname, 0)
    out = ["🛒 斯塔薇布的工具车 \"竿是渔人的腰, 腰坏了人就完了。\"",
           f"   🎣 {name}  耐久 {d/10:.1f}%"]
    cost = mender_cost(state)
    if d >= MAX:
        out.append("   ✨ 好得很, 不用修。\"没事别乱花钱。\"")
    else:
        out.append(f"   🔧 repair go —— 大婶修到100%: {cost}g" +
                   ("(免费, 新手关怀)" if cost == 0 else ""))
    # ── 雇员在家代修(员工价; 出门时大婶兜底) ──
    _home = _home_repairers(state, now)
    if _home and d < MAX:
        hc = home_cost(state)
        out.append(f"   🧰 repair home —— 「{_home[0]['name']}」代修到100%: {hc}g(员工价)")
    elif state.get("retainers") and d < MAX:
        out.append("   🧰 雇员都出门探险了——这单还是大婶来。")
    st = quest_stage(state)
    if st == 2:
        out.append(f"   🪄 repair self —— 自修到199%: 耗{gname}×1(你有{stock})")
        out.append(f"   🧱 repair buy [N] —— 买{gname}: {gprice}g/块")
    elif st == 1:
        got = state.get("mender_food", 0)
        out.append(f"   📜 任务进行中: 泡泡莉家的食物 {got}/{QUEST_FOOD_NEED}"
                   "(foodshop 买, 买够再来)")
    else:
        out.append("   🔒 自修: 未学(Lv30后大婶会教你)")
    return "\n".join(out)


def repair_go(state: dict) -> str:
    """大婶修理: 修到100%。"""
    d = get(state)
    if d >= MAX:
        return "🛒 大婶瞥了一眼:\"好得很, 别浪费钱。\"(耐久≥100%不用修)"
    cost = mender_cost(state)
    if cost > state.get("gil", 0):
        return f"🛒 修到100%要 {cost}g, 你只有 {state.get('gil',0)}g。大婶:\"先去卖鱼吧。\""
    state["gil"] = state.get("gil", 0) - cost
    _set(state, MAX)
    state["dur_warned"] = -1
    tail = "免费给你修了, 下次疼着点用。" if cost == 0 else f"收你 {cost}g。"
    return (f"🔧 大婶三下五除二, 竿身焕然一新(100%)。\"{tail}\"\n"
            f"   \"{CATCH_ALL}\"")


def repair_self(state: dict) -> str:
    """自修: 耗对应等级暗物质×1, 修到199%。"""
    if quest_stage(state) != 2:
        return "🔒 你还不会自己修。(Lv30 后找推工具车的大婶拜师)"
    _n, _p, rlv = _rod_info(state)
    gname, _gp = grade_for(rlv)
    dm = state.setdefault("dark_matter", {})
    if dm.get(gname, 0) < 1:
        return f"🧱 需要 {gname}×1(你有0)。repair buy 找大婶买。"
    if get(state) >= SELF_MAX:
        return "✨ 已经是199%了, 再修竿要成精了。"
    dm[gname] -= 1
    _set(state, SELF_MAX)
    state["dur_warned"] = -1
    return (f"🪄 你按大婶教的手法抹上{gname}——竿身泛起微光, 比新的还结实(199%)!\n"
            "   \"出远门的时候得学会自己修啊。\"你想起她的话。")


def repair_buy(state: dict, arg: str = "") -> str:
    """买当前竿对应等级的暗物质。"""
    _n, _p, rlv = _rod_info(state)
    gname, gprice = grade_for(rlv)
    n = int(arg) if arg.strip().isdecimal() else 1
    n = max(1, min(99, n))
    cost = gprice * n
    if cost > state.get("gil", 0):
        return f"🧱 {gname}×{n} 要 {cost}g, 你只有 {state.get('gil',0)}g。"
    state["gil"] -= cost
    dm = state.setdefault("dark_matter", {})
    dm[gname] = dm.get(gname, 0) + n
    return f"🧱 购入 {gname}×{n}(-{cost}g)。库存 {dm[gname]}。大婶:\"省着点用。\""


# ── 雇员在家代修(v36; 出门时大婶兜底) ─────────────────
def _home_repairers(state: dict, now: float | None = None) -> list:
    """在家的雇员名单(懒加载 retainer, 避免环形导入)。"""
    if not state.get("retainers"):
        return []
    import time as _t
    try:
        from . import retainer as _ret
    except ImportError:
        import retainer as _ret
    return _ret.home_repairers(state, now if now is not None else _t.time())


def home_cost(state: dict) -> int:
    """雇员代修费 = 大婶报价的一半(员工价, 只收材料钱)。"""
    return mender_cost(state) // 2


def repair_home(state: dict, now: float | None = None) -> str:
    """在家的雇员代修到100%。"""
    home = _home_repairers(state, now)
    if not state.get("retainers"):
        return "🧰 你还没有雇员。(Lv17 后 hire 找中介琪琪茹签一位)"
    if not home:
        return "🧰 雇员都出门探险了——大婶兜底: repair go"
    d = get(state)
    if d >= MAX:
        return f"🧰 「{home[0]['name']}」看了看竿:\"好得很, 不用修。\""
    cost = home_cost(state)
    if cost > state.get("gil", 0):
        return f"🧰 材料费要 {cost}g, 你只有 {state.get('gil', 0)}g。"
    state["gil"] = state.get("gil", 0) - cost
    _set(state, MAX)
    state["dur_warned"] = -1
    r = home[0]
    tail = "员工价, 只收材料钱。" if cost else "这单不要钱。"
    return (f"🧰 「{r['name']}」接过你的竿, 三两下换好导环、上了油(100%)。\n"
            f"   \"{tail}路上小心。\"" + (f"(-{cost}g)" if cost else ""))


def handle(state: dict, arg: str = "", now: float | None = None) -> str:
    """repair 命令总入口(含任务推进)。"""
    a = (arg or "").strip().lower()
    st = quest_stage(state)
    # 任务①: Lv30+ 首次找修理 -> 演出+接任务
    if st == 0 and state.get("level", 1) >= QUEST_LV:
        state["mender_quest"] = 1
        state["mender_food"] = 0
        return QUEST_ACT1 + "\n" + menu(state, now)
    # 任务③: 食物买够 -> 交差
    if st == 1 and state.get("mender_food", 0) >= QUEST_FOOD_NEED:
        state["mender_quest"] = 2
        dm = state.setdefault("dark_matter", {})
        dm["G1暗物质"] = dm.get("G1暗物质", 0) + 2
        return QUEST_ACT3 + "\n" + menu(state, now)
    if a in ("go", "大婶", "修"):
        return repair_go(state)
    if a in ("home", "雇员", "代修"):
        return repair_home(state, now)
    if a in ("self", "自修"):
        return repair_self(state)
    if a.startswith("buy") or a.startswith("买"):
        return repair_buy(state, a.replace("buy", "").replace("买", ""))
    return menu(state, now)
