"""
FF14 钓鱼 海钓模块 (Ocean Fishing)
------------------------------------------------------------
真实机制 -> 回合制的翻译对照:
  班次      每 2 现实小时一班, 前 15 分钟登船, 错过等下一班 (engine/ocean_schedule)
  航线      与现实服同一张排班表; 每班可选 灵青航路 / 红玉航路
  一站7分钟  -> 每站 CASTS_PER_STATION 竿预算
  幻海流     钓到"幻光"触发鱼必定引发; 虚拟船友每竿也可能替你引发;
             期间换用幻海流鱼表、每竿只消耗 SPECTRAL_COST 竿预算(=咬钩翻倍),
             最多 SPECTRAL_MAX_CASTS 竿, 站预算耗尽会被一起掐断(真实之痛)
  渔分       每条鱼有官方 points; 航次结束按全船分数榜结算
  蓝鱼(传说) 需要主世界的特殊饵 —— 船上不卖, 要自己买好带上船(bait_stock)
  经验       按等级给基础量(海钓=练级利器), 渔分再给加成

确定性: 与主循环同一约定, rng = seed*1000003 + casts, 同档同序列可复现。
★ 想调手感, 改下面"可调常量"区即可, 不用动逻辑 ★
"""

from __future__ import annotations
import json
from pathlib import Path

try:
    from . import ocean_schedule as sched
    from . import bait as bait_mod
    from . import leveling
    from . import gp as gp_mod
    from . import scrip as scrip_mod
    from . import tasks as tasks_mod
except ImportError:
    import ocean_schedule as sched
    import bait as bait_mod
    import leveling
    import gp as gp_mod
    import scrip as scrip_mod
    import tasks as tasks_mod

# --- 数据 ---------------------------------------------------
_DATA = Path(__file__).resolve().parent.parent / "data"
OCEAN = json.loads((_DATA / "ocean.json").read_text(encoding="utf-8"))
ROUTES = json.loads((_DATA / "ocean_routes.json").read_text(encoding="utf-8"))["routes"]

_TIME_NUM = {"白天": 1, "黄昏": 2, "夜晚": 3}
_FISH_BY_ITEM = {int(k): v for k, v in OCEAN["fish"].items()}
# —— 海钓鱼显示名覆写(cn_fix/en_fix): 旧名保留为 cn_alias/en_alias 供搜索 ——
_OCEAN_NAME_FIXES = {
    "女王的使者": ("王室使者", None),      # Royal Handmaiden
    "女王的大使": ("王室宠儿", None),      # Royal Favorite
    "公主鲑":     ("幼王鲑", "Scion Salmon"),  # Princess Salmon
    "眼镜王蛇鱼": (None, None),           # King Cobrafish → 现实物种名豁免
}
for _f in _FISH_BY_ITEM.values():
    _fix = _OCEAN_NAME_FIXES.get(_f.get("name_cn", ""))
    if _fix:
        cn_fix, en_fix = _fix
        if cn_fix:
            _f["cn_alias"] = _f["name_cn"]
            _f["name_cn"] = cn_fix
        if en_fix:
            _f["en_alias"] = _f.get("name_en", "")
            _f["name_en"] = en_fix
_FISH_BY_CN = {v["name_cn"]: v for v in _FISH_BY_ITEM.values()}
# 旧中文名也能搜到(别名索引)
for _f in _FISH_BY_ITEM.values():
    _alias = _f.get("cn_alias")
    if _alias and _alias not in _FISH_BY_CN:
        _FISH_BY_CN[_alias] = _f
# 站 -> 两套鱼池(平时/幻海流), 直接存鱼 dict
_POOLS = {
    sid: {side: [_FISH_BY_ITEM[i] for i in s[side] if i in _FISH_BY_ITEM]
          for side in ("normal", "spectral")}
    for sid, s in OCEAN["spots"].items()
}
_SPOT_NAME = {sid: s["name"] for sid, s in OCEAN["spots"].items()}
# 船上免费供应的海钓饵 {itemId(int): 中文名}
_OCEAN_BAITS = {int(i): n["cn"] for i, n in OCEAN["bait_names"].items()}
# 主世界饵: itemId -> 英文名(对接 bait_stock 库存)
_WORLD_BAIT_BY_ID = {info["id"]: en for en, info in bait_mod.BAITS.items()}

# --- 可调常量 -----------------------------------------------
CASTS_PER_STATION = 15     # 每站竿数预算(真实一站≈7分钟≈15竿)
SPECTRAL_COST = 0.5        # 幻海流期间每竿只消耗的预算(=咬钩速度翻倍)
SPECTRAL_MAX_CASTS = 6     # 幻海流最多持续的竿数
MATE_TRIGGER_P = 0.05      # 每竿"虚拟船友替你引发幻海流"的概率
CHATTER_P = 0.22           # 每竿船友碎碎念的概率
ESCAPE_P = 0.07            # 海钓脱钩概率(海鱼咬得凶, 比岸钓低)
BAIT_BOOST = 3.0           # 挂对饵的权重倍率
STAR_WEIGHT = {0: 100, 1: 45, 2: 18, 3: 7, 4: 2, 5: 1}   # 星级->抽取权重
XP_BASE_FRACTION = 0.5     # 结算经验 = 升级所需 * (基础比例 + 渔分加成)
XP_POINT_SCALE = 8000      # 渔分加成 = min(0.5, 渔分/此值)
GIL_DIV = 5                # 每条鱼的 gil = max(2, 渔分//此值)
CREW_SIZE = 23             # 虚拟船友数(全船24人, 含你)
DEFAULT_BAIT = 29715       # 登船默认挂的饵(磷虾)

# 海钓 GP 技能
DOUBLE_HOOK_COST = 100     # 双提钩 GP 消耗(真实: 400, 按我们 GP_MAX=400 等比缩)
TRIPLE_HOOK_COST = 150     # 三提钩 GP 消耗(真实: 700→缩为 150)
PRIZE_CATCH_COST = 100     # 大鱼确保 GP 消耗(真实: 200→缩为 100)
PRIZE_CATCH_PTS_MULT = 1.5 # 大鱼确保: 本竿渔分 ×1.5
OCEAN_GP_PER_CAST = 10     # 时间泡泡里 GP 随抛竿回复(不吃现实挂机, 修#27)

# --- 虚拟船友(名字随机拼装, 不含任何真实人名) ---------------
_ADJ = ["打瞌睡的", "冒失的", "沉默的", "爱唱歌的", "晕船的", "干劲十足的",
        "神秘的", "吃不饱的", "乐观的", "较真的", "怕水的", "收藏癖的"]
_NOUN = ["鲷鱼", "海燕", "水母", "灯塔", "海风", "锚", "贝壳", "飞鱼",
         "浪花", "罗盘", "桅杆", "潮汐"]
_IDLE_CHATTER = [
    # ── 日常碎碎念 ──
    "我没带鱼饵……有人多带了吗？🥺",
    "包满了包满了，谁帮我记一下分！",
    "这站好安静啊。",
    "风好舒服~ 差点睡着。",
    "刚才那条也太大了吧！！",
    "下一站我一定要蹲到触发鱼。",
    "呜, 我的药还在冷却……",
    # ── 生活向 ──
    "有人带了饭团吗？好饿……",
    "海水溅到脸上了。咸的。",
    "甲板好滑——刚才差点摔了。",
    "太阳好大……帽子忘在码头了。",
    "你们有人知道这站有什么大鱼吗？",
    "上一班我渔分才 800，这次一定要翻身。",
    "我已经连续坐了三班船了……家人开始担心了。",
    # ── 观察向 ──
    "你看船尾那只海鸟，盯着我们的鱼桶看了好久。",
    "浪好大……我的浮标都看不清了。",
    "刚才水面上有什么一闪一闪的，是鱼鳞吗？",
    "远处那个岛上有灯塔诶。好想去看看。",
    "空气里有一股海草的味道。不难闻。",
    # ── 社交向 ──
    "咱们船上有没有人是第一次出海？",
    "有人要交换鱼饵吗？我多带了磷虾。",
    "记得帮我拍照！我要发冒险者手记！",
    "下船以后去酒馆坐坐？我请。",
    "这班船的运气好不好全看第一竿。",
    # ── 幻海流相关 ──
    "上一站怎么没触发幻海流……脸好黑。",
    "幻海流的时候手速要跟上啊！别犹豫！",
    "求求了，这站来一次幻海流吧……🙏",
    "听说连续三站都触发幻海流的概率比中彩票还低。",
]
_MATE_ESCAPE = [
    "鱼！！！脱钩了！！！我的鱼！！！！",
    "啊——差一点！！就差一点！！",
    "又跑了……今天第三次了……",
    "不……那条的分一定很高……",
    "手滑了！！怎么会手滑！！",
    "鱼线崩了！这破鱼线！！",
    "它回头看了我一眼。我发誓它看了我。",
    "算了……算了……深呼吸……",
]
_MATE_TRIGGER = "⚡⚡ 船友【{name}】钓起了一条闪光的鱼！！—— 幻海流来了！！"
_SELF_TRIGGER = "⚡⚡ 你钓起的{fish}泛着幻光 —— 幻海流被你亲手引来了！！"
_SPECTRAL_END = "…幻光散去，海面恢复了平静。(幻海流结束)"


def _crew(rng) -> list:
    """随机生成一船船友名(形容词+海洋词, 保证不重复)。"""
    pool = [a + n for a in _ADJ for n in _NOUN]
    rng.shuffle(pool)
    return pool[:CREW_SIZE]


# --- 小工具 -------------------------------------------------
def _route(key: str) -> dict:
    return ROUTES[key]


def _stop(session) -> dict:
    """当前站: {'spot_id', 'time'}。"""
    return _route(session["route_key"])["stops"][session["station"]]


def _stop_desc(session) -> str:
    st = _stop(session)
    return f"{_SPOT_NAME[str(st['spot_id'])]}·{st['time']}"


def _bait_disp(session) -> str:
    b = session["bait"]
    if b in _OCEAN_BAITS:
        return _OCEAN_BAITS[b]
    en = _WORLD_BAIT_BY_ID.get(b)
    return bait_mod.disp(en) if en else f"#{b}"


def _size_range(f: dict):
    base = {"light": (3, 14), "medium": (8, 28), "heavy": (20, 55)}
    lo, hi = base.get((f.get("tug") or "").lower(), (5, 20))
    if f.get("stars", 0) >= 4:                    # 高星鱼体型上调
        lo, hi = lo + 10, hi + 30
    return lo, hi


def _pool(session, state) -> list:
    """当前这一竿的候选鱼池(已按 时段/幻海流/蓝鱼特殊饵 过滤)。"""
    st = _stop(session)
    side = "spectral" if session["spectral_casts"] > 0 else "normal"
    tnum = _TIME_NUM[st["time"]]
    bait = session["bait"]
    out = []
    for f in _POOLS[str(st["spot_id"])][side]:
        if f["ikdTimes"] and tnum not in f["ikdTimes"]:
            continue
        if f["isBlueFish"] and bait not in f["baitIds"]:
            continue                              # 蓝鱼: 必须挂对特殊饵
        out.append(f)
    return out


def _weight(f: dict, bait: int) -> float:
    w = STAR_WEIGHT.get(f.get("stars", 0), 30)
    if bait in f.get("baitIds", []):
        w *= BAIT_BOOST
    return max(w, 0.5)


# --- 抛竿核心 -----------------------------------------------
def _cast_once(game, rng) -> dict:
    """海上钓一竿, 返回事件 dict(caught/escaped/…以及站/幻海流的推进)。"""
    s = game.state
    session = s["ocean"]
    ev = {"pre": [], "post": [], "settle": None}

    # 时间泡泡里, GP 不吃现实挂机, 改为随抛竿回复(每竿≈一段船上时间)  #27
    s["gp"] = min(gp_mod.max_gp(s), s.get("gp", 0) + OCEAN_GP_PER_CAST)
    # 技能 buff 在抛竿瞬间生效, 无论结果如何都消耗(empty 也吞)  #28
    buff_dh = session.pop("buff_dh", False)
    buff_th = session.pop("buff_th", False)
    buff_prize = session.pop("buff_prize", False)

    in_spectral = session["spectral_casts"] > 0
    # 船友碎碎念 / 船友引发幻海流(仅平时) —— 都发生在你抛竿之前
    if not in_spectral and rng.random() < MATE_TRIGGER_P:
        session["spectral_casts"] = SPECTRAL_MAX_CASTS
        in_spectral = True
        name = session["crew"][rng.randrange(len(session["crew"]))]
        ev["pre"].append(_MATE_TRIGGER.format(name=name))
    elif rng.random() < CHATTER_P:
        name = session["crew"][rng.randrange(len(session["crew"]))]
        pool = _IDLE_CHATTER + _MATE_ESCAPE
        ev["pre"].append(f"💬 {name}: {pool[rng.randrange(len(pool))]}")

    # 世界饵在船上照样损耗库存
    bait = session["bait"]
    if bait in _WORLD_BAIT_BY_ID:
        en = _WORLD_BAIT_BY_ID[bait]
        stock = s.setdefault("bait_stock", {})
        if stock.get(en, 0) <= 0:
            session["bait"] = DEFAULT_BAIT
            ev["pre"].append(f"🪱 {bait_mod.disp(en)} 用完了, 自动换回 "
                             f"{_OCEAN_BAITS[DEFAULT_BAIT]}(船上供应)。")
            bait = DEFAULT_BAIT
        else:
            stock[en] = stock[en] - 1
            if stock[en] <= 0:
                stock.pop(en, None)

    pool = _pool(session, s)
    if not pool:
        ev["kind"] = "empty"
    else:
        f = rng.choices(pool, weights=[_weight(x, bait) for x in pool], k=1)[0]
        if rng.random() < ESCAPE_P:
            ev["kind"] = "escaped"
            ev["fish"] = f
        else:
            ev["kind"] = "caught"
            ev["fish"] = f
            name = f["name_cn"]
            oc = s.setdefault("ocean_caught", {})
            # 双提钩/三提钩: 一竿多鱼
            dh_data = f.get("doubleHook", [])
            if buff_th and len(dh_data) >= 2:
                multi = dh_data[-1]               # 三提钩取最高档
            elif buff_th and dh_data:
                multi = dh_data[0]                 # 单档鱼: 效果同双提钩
                # #30: 三提钩打在单档鱼上, 自动退双/三差价
                refund = TRIPLE_HOOK_COST - DOUBLE_HOOK_COST
                s["gp"] = min(gp_mod.max_gp(s), s.get("gp", 0) + refund)
                ev["pre"].append(f"🎯 这条鱼只有单档——三提钩按双提钩结算, "
                                 f"退还 {refund} GP。")
            elif buff_dh and dh_data:
                multi = dh_data[0]                 # 双提钩取第一档
            else:
                multi = 1
            oc[name] = oc.get(name, 0) + multi
            ev["first"] = oc[name] == multi        # 第一次钓到这种鱼
            ev["multi"] = multi
            lo, hi = _size_range(f)
            size = round(rng.uniform(lo, hi), 1)
            ev["size"] = size
            rec = s.setdefault("records", {})
            ev["rec"] = size > rec.get(name, 0)
            if ev["rec"]:
                rec[name] = size
            pts = f["points"] * multi
            if buff_prize:
                pts = int(pts * PRIZE_CATCH_PTS_MULT)
                ev["prize"] = True
            session["score"] += pts
            session["catches"] += multi
            g = max(2, pts // GIL_DIV)
            s["gil"] += g
            ev["pts"], ev["gil"] = pts, g
            ev["buffs_used"] = []
            if buff_dh:
                ev["buffs_used"].append(f"双提钩×{multi}")
            if buff_th:
                ev["buffs_used"].append(f"三提钩×{multi}")
            if buff_prize:
                ev["buffs_used"].append("大鱼确保")
            # 成就追踪(全部用 .get 防旧档无字段崩溃 #21)
            session["max_star"] = max(session.get("max_star", 0), f.get("stars", 0))
            if in_spectral:
                session["spectral_catches"] = session.get("spectral_catches", 0) + multi
            # 分类渔获计数(供分类成就判定 #22: ikdContentBonusId → 计数)
            cbid = f.get("ikdContentBonusId", 0)
            if cbid:
                cc = session.setdefault("_cat_counts", {})
                cc[str(cbid)] = cc.get(str(cbid), 0) + multi
            st = _stop(session)
            sid = str(st["spot_id"])
            sp = session.setdefault("spot_species", {})
            if sid not in sp:
                sp[sid] = []
            if name not in sp[sid]:
                sp[sid].append(name)
            # 触发鱼: 平时钓到 -> 幻海流必定爆发
            if f["isSpectralFish"] and not in_spectral:
                session["spectral_casts"] = SPECTRAL_MAX_CASTS
                session["self_triggered"] = True
                ev["post"].append(_SELF_TRIGGER.format(fish=name))
                in_spectral = True

    # 预算与幻海流推进 (触发当竿即享半价, 数值差异极小、体感更爽)
    if in_spectral:
        session["budget"] -= SPECTRAL_COST
        session["spectral_casts"] -= 1
        if session["spectral_casts"] <= 0:
            ev["post"].append(_SPECTRAL_END)
    else:
        session["budget"] -= 1

    # 站推进 / 结算
    if session["budget"] <= 0:
        if session["spectral_casts"] > 0:
            ev["post"].append("⏱ 船要开了——幻海流跟着这一站被硬生生掐断……")
            session["spectral_casts"] = 0
        session["station"] += 1
        if session["station"] >= len(_route(session["route_key"])["stops"]):
            ev["settle"] = _settle(game, rng)
        else:
            session["budget"] = float(CASTS_PER_STATION)
            ev["post"].append(f"🚢 起锚——抵达第 {session['station'] + 1} 站: "
                              f"{_stop_desc(session)}(预算 {CASTS_PER_STATION} 竿)")
    return ev


# --- 成就判定 + 语气池(C风格: 随机抽) ----------------------------
import re as _re

_BONUSES = OCEAN["bonuses"]
# 丰渔目标预解析: {bonus_id: (spot_name, need_count)}
_PARTY_REQ = {}
for _b in _BONUSES:
    _m = _re.search(r'在(.+?)合计钓到(\d+)种', _b['requirement']['chs'])
    if _m:
        _PARTY_REQ[_b['id']] = (_m.group(1), int(_m.group(2)))


def _check_bonuses(session: dict) -> list:
    """根据航次数据判定达成了哪些加分目标, 返回达成列表。"""
    score = session["score"]
    max_star = session.get("max_star", 0)
    spec_catches = session.get("spectral_catches", 0)
    self_trig = session.get("self_triggered", False)
    spot_sp = session.get("spot_species", {})
    # 各站钓到的种类数(按站名汇总)
    species_by_name = {}
    for sid, names in spot_sp.items():
        sn = _SPOT_NAME.get(sid, "")
        species_by_name[sn] = len(names) if isinstance(names, list) else 0

    # 按分类统计本航次渔获数(直接取抛竿时的精确计数, 修#26虚增)
    bonus_counts = {int(k): v
                    for k, v in session.get("_cat_counts", {}).items()}

    # 小队系成就的单人缩放(原数÷24, 至少5)
    _SOLO_SCALE = {13: 6, 14: 8, 15: 6, 16: 5, 20: 10, 21: 10,
                   40: 14, 41: 16, 55: 12}
    # 个人系成就的原始门槛
    _PERSONAL = {22: 25, 42: 50, 56: 50}

    hit = []
    for b in _BONUSES:
        bid = b["id"]
        ok = False

        if bid == 1:                              # 千鱼祝福: 渔分≥2500
            ok = score >= 2500
        elif bid == 2:                            # 万鱼贺喜: 渔分≥5000
            ok = score >= 5000
        elif bid == 3:                            # 珍鱼: 钓到★★★★
            ok = max_star >= 4
        elif bid == 4:                            # 传说鱼: 钓到★★★★★
            ok = max_star >= 5
        elif bid == 5:                            # 瞬钓: 幻海流中钓15条
            ok = spec_catches >= 15
        elif bid == 6:                            # 爆钓王: 幻海流中钓35条
            ok = spec_catches >= 35
        elif bid == 11:                           # 传说大渔旗: 队伍钓3条★★★★★
            ok = False                            # 单人不可能, 从成就表隐藏
        elif bid == 12:                           # 宠爱之子: 自引幻海流
            ok = self_trig
        elif bid in _SOLO_SCALE:                  # 小队系分类成就(缩放到单人)
            ok = bonus_counts.get(bid, 0) >= _SOLO_SCALE[bid]
        elif bid in _PERSONAL:                    # 个人系分类成就
            ok = bonus_counts.get(bid, 0) >= _PERSONAL[bid]
        elif bid in (17, 18, 19):                 # 初/中/上级海钓师: 结尾算
            pass
        elif bid in _PARTY_REQ:                   # 丰渔: 某站≥N种
            sn, need = _PARTY_REQ[bid]
            ok = species_by_name.get(sn, 0) >= need

        if ok:
            hit.append(b)

    # 丰渔去重: 同一站只保留最高档(10>9>8)
    best_party = {}
    other = []
    for b in hit:
        if b["id"] in _PARTY_REQ:
            sn, need = _PARTY_REQ[b["id"]]
            if sn not in best_party or need > _PARTY_REQ[best_party[sn]["id"]][1]:
                best_party[sn] = b
        else:
            other.append(b)
    hit = other + list(best_party.values())

    # sub_done 用去重后的 hit 计数(修#23: 不再被三档膨胀)
    sub_done = len([b for b in hit if b["id"] not in (17, 18, 19)])

    # 回填初/中/上级海钓师
    for b in _BONUSES:
        if b["id"] == 17 and sub_done >= 1:
            hit.append(b)
        elif b["id"] == 18 and sub_done >= 2:
            hit.append(b)
        elif b["id"] == 19 and sub_done >= 3:
            hit.append(b)

    return hit


# 语气池: 特定成就 id -> [随机文案]; 命中时抽一条
_BONUS_FLAVOR = {
    1: ["终于不是在给海鸥喂饭了",
        "2500 分,船长微微点了点头",
        "海面上飘来了鱼的掌声……大概是"],
    2: ["5000 分。你已经不是普通的钓鱼佬了",
        "5000 分。你已经不是普通的钓客了",
        "全船的海鸥都对你行注目礼",
        "传说中的万鱼,传说中的你"],
    3: ["四星鱼到手,钓竿都在微微发抖",
        "稀有到连鱼自己都惊讶被你钓上来了",
        "这条鱼的身价比你这趟船票贵"],
    4: ["……你做到了。你真的做到了",
        "全船沉默了三秒,然后爆发出欢呼",
        "这条鱼比你的未来还亮"],
    5: ["幻海流里连钓 15 条,手速可以去打音游了",
        "鱼:我们是不是上错片场了?怎么排着队来",
        "海面:请不要吸我的鱼谢谢"],
    6: ["35 条。你不是在钓鱼,你是在收割",
        "幻海流结束时鱼都松了口气",
        "爆钓王之名,实至名归"],
    12: ["你亲手引来了幻海流。这一刻,海是你的",
         "全船喊你大佬的声音盖过了海浪声",
         "全船的欢呼声盖过了海浪声",
         "幻光系触发鱼到手——钓上来的不是鱼,是整片海的运气"],
}
_GENERIC_FLAVOR = [
    "又一个目标达成,集邮路上永不停歇",
    "成就 get! 虽然海鸥看起来不太在乎",
    "离全成就又近了一步",
    "这个成就值得截图发朋友圈(如果鱼有朋友圈的话)",
    "船友们投来了敬佩的目光……或许还夹杂了亿点点忮忌",
]


def _settle(game, rng) -> str:
    """航次结束: 成就判定 → 渔分加成 → 全船分数榜 → 经验/收尾。"""
    s = game.state
    session = s["ocean"]
    raw_score = session["score"]

    # ---- 成就判定 ----
    achieved = _check_bonuses(session)
    total_rate = sum(b["bonusRate"] for b in achieved)   # 加成百分比合计
    bonus_score = int(raw_score * (total_rate - 100 * len(achieved)) / 100) if achieved else 0
    my = raw_score + bonus_score

    # NPC 分数: 绝对基础分 + 锚定玩家的浮动, 让"变强"买得到名次
    # 高手数量泊松随机(平均3人), 某些航次可能0个高手 → 夺冠有望
    import math
    n_elites = min(CREW_SIZE, int(rng.expovariate(1 / 3)))  # 泊松近似, 平均3人
    npc = []
    for i, name in enumerate(session["crew"]):
        base = rng.randint(600, 2200)             # 绝对基础: NPC自己的实力
        anchor = my * rng.uniform(0.15, 0.5)      # 锚定: 跟着玩家走一部分
        if i < n_elites:                           # 高手: 额外加成
            base += rng.randint(600, 2000)
        score = max(100, int(base + anchor + rng.randint(-100, 100)))
        npc.append((name, score))
    board = sorted(npc + [("你", my)], key=lambda x: -x[1])
    rank = [n for n, _ in board].index("你") + 1
    lv = s.get("level", 1)
    xp = int(leveling.xp_to_next(lv)
             * (XP_BASE_FRACTION + min(0.5, my / XP_POINT_SCALE)))
    gained = leveling.add_xp(s, xp)
    s["ocean_trips"] = s.get("ocean_trips", 0) + 1
    s["ocean_points_total"] = s.get("ocean_points_total", 0) + my
    # 票据奖励(真实: 海钓按渔分给采集票据)
    sw, sp_ = scrip_mod.ocean_award(my)
    s["scrip_white"] = s.get("scrip_white", 0) + sw
    s["scrip_purple"] = s.get("scrip_purple", 0) + sp_
    # 累积成就存档
    all_ach = s.setdefault("achievements", [])
    for b in achieved:
        aid = b["id"]
        if aid not in all_ach:
            all_ach.append(aid)
    s["gp_at"] = game._now()                    # 下船对表: 泡泡里的现实时间不折现(#27)
    tasks_mod.record(s, game._now(), "ocean_trip", 1)
    tasks_mod.record(s, game._now(), "ocean_points", my)
    route_name = _route(session["route_key"])["name"]
    out = [f"⚓ 航次结束——{sched.line_name(session['line'])}·{route_name}"]
    # 成就播报(语气池随机)
    if achieved:
        out.append("   —— 航次加分目标 ——")
        for b in achieved:
            flavor = _BONUS_FLAVOR.get(b["id"])
            if flavor:
                quip = flavor[rng.randrange(len(flavor))]
            else:
                quip = _GENERIC_FLAVOR[rng.randrange(len(_GENERIC_FLAVOR))]
            out.append(f"   🏅 {b['objective']['chs']}（+{b['bonusRate']-100}%）"
                       f"  —— {quip}")
        out.append(f"   渔分 {raw_score} + 加成 {bonus_score} = {my}")
    else:
        out.append(f"   渔分: {my}（无加分目标达成）")
    out.append(f"   渔获 {session['catches']} 条  GP技能 {session.get('skills_used', 0)} 次"
               f"  全船排名: {rank}/{CREW_SIZE + 1}")
    out.append("   —— 全船分数榜(前5) ——")
    for i, (n, sc) in enumerate(board[:5], 1):
        star = " ←" if n == "你" else ""
        out.append(f"     {i}. {sc:>5} 分  {n}{star}")
    if rank > 5:
        out.append(f"     …  {my:>5} 分  你(第{rank}名)")
    if rank == 1:
        out.append("   🏆 全船第一!! 船友们围过来要你的合影!!")
    elif rank > 1 and board[rank - 2][1] - my <= 200:
        out.append(f"   😤 距上一名只差 {board[rank - 2][1] - my} 分……下船气得跺脚。")
    out.append(f"   经验 +{xp}" + (f"  🎉升到 Lv{gained[-1]}!" if gained else ""))
    if sw or sp_:
        out.append(f"   🎫白票 +{sw}  🎟紫票 +{sp_}"
                   f"（现有 🎫{s['scrip_white']} 🎟{s['scrip_purple']}）")
    s["ocean"] = None
    return "\n".join(out)


# --- 命令层 -------------------------------------------------
def _fmt_event(ev, session) -> str:
    """播报顺序: 竿前(碎碎念/船友触发) -> 本竿结果 -> 竿后(自己触发/幻光散去/到站) -> 结算。"""
    k = ev.get("kind")
    spec = "⚡" if (session and session["spectral_casts"] > 0) else ""
    if k == "empty":
        result = "🎣 抛竿……这一竿什么都没咬。(换换饵试试? ocean bait)"
    elif k == "escaped":
        result = f"🎣 {spec}有鱼咬钩——线一紧又松, 脱钩了!!"
    else:
        f = ev["fish"]
        star = "★" * f.get("stars", 0)
        first = "✨新图鉴! " if ev.get("first") else ""
        rec = " ★破纪录!" if ev.get("rec") else ""
        blue = " 💙蓝鱼!!" if f["isBlueFish"] else ""
        multi = ev.get("multi", 1)
        multi_tag = f"×{multi}" if multi > 1 else ""
        prize_tag = " 🐟大鱼确保!" if ev.get("prize") else ""
        buffs = ev.get("buffs_used", [])
        buff_tag = f"（{'＋'.join(buffs)}）" if buffs else ""
        result = (f"🎣 {spec}上钩! {first}{f['name_cn']}{star}{multi_tag}{blue}{prize_tag}"
                  f"（{ev['size']} 吋）{rec}  +{ev['pts']} 渔分, +{ev['gil']} gil"
                  f"{buff_tag}")
    lines = list(ev["pre"]) + [result] + list(ev["post"])
    if ev.get("settle"):
        lines.append(ev["settle"])
    return "\n".join(lines)


def _status(game) -> str:
    s = game.state
    now = game._now()
    session = s.get("ocean")
    if session:
        if session["spectral_casts"] > 0:
            spec = f"⚡幻海流中(剩 {session['spectral_casts']} 竿, 每竿仅耗 {SPECTRAL_COST} 预算!)"
        else:
            spec = "平静"
        lines = [
            f"🚢 {sched.line_name(session['line'])}·{_route(session['route_key'])['name']}"
            f"  ⏸时间泡泡(按竿数推进不过期; GP随抛竿回复+{OCEAN_GP_PER_CAST}/竿, 不吃现实挂机)",
            f"   第 {session['station'] + 1}/3 站: {_stop_desc(session)}   海况: {spec}",
            f"   本站预算: 剩 {session['budget']:g} 竿   渔分: {session['score']}"
            f"   渔获: {session['catches']} 条",
            f"   🪱 当前饵: {_bait_disp(session)}"
            f"（ocean bait <饵名> 换; 船上供应: "
            + "、".join(_OCEAN_BAITS.values()) + "）",
            "   继续: ocean cast [N] / 弃船: ocean quit",
            f"   🎯 GP 技能: ocean dh(双提钩 {DOUBLE_HOOK_COST}GP)"
            f" / ocean th(三提钩 {TRIPLE_HOOK_COST}GP)"
            f" / ocean prize(大鱼确保 {PRIZE_CATCH_COST}GP)"
            f"  当前 GP {s.get('gp', 0)}/{gp_mod.max_gp(s)}",
        ]
        return "\n".join(lines)
    v = sched.current_voyage(now)
    open_ = sched.boarding_open(now)
    out = ["🚢 利姆萨·罗敏萨码头 —— 出海垂钓(与现实服同班次)"]
    if open_:
        left = v.boarding_end - int(now)
        out.append(f"   ✅ 登船窗口开放中! 剩 {left // 60} 分 {left % 60} 秒 "
                   f"(ocean board indigo / ocean board ruby)")
        nb = v
    else:
        nb = sched.next_boarding(now)
        wait = nb.slot_start - int(now)
        out.append(f"   ❌ 本班登船已截止。下一班还有 {wait // 60} 分 {wait % 60} 秒:")
    for ln, key in nb.routes:
        r = _route(key)
        stops = " → ".join(f"{_SPOT_NAME[str(x['spot_id'])]}({x['time']})"
                           for x in r["stops"])
        out.append(f"   {sched.line_name(ln)}: {r['name']}  [{stops}]")
    out.append("   班次表: ocean routes   (每 2 小时一班, 开头 15 分钟可登船)")
    return "\n".join(out)


def _routes_view(game) -> str:
    now = game._now()
    out = ["🗓 未来 6 班(与现实国际服/国服同步; 错过等下班):"]
    for v in sched.upcoming_voyages(6, now):
        rel = v.slot_start - int(now)
        when = ("本班" if rel <= 0 else f"+{rel // 3600}h{(rel % 3600) // 60:02d}m")
        pair = " | ".join(
            f"{sched.line_name(ln)}: {_route(k)['name']}"
            f"({_route(k)['stops'][-1]['time']})" for ln, k in v.routes)
        out.append(f"   {when:>7}  {pair}")
    return "\n".join(out)


def _board(game, arg: str) -> str:
    s = game.state
    if s.get("ocean"):
        return "你已经在船上了! ocean 看当前状态, ocean quit 弃船。"
    # 先验航路名(玩家能控制的事优先报), 再验登船窗口
    a = arg.strip().lower()
    alias = {"indigo": "indigo", "灵青": "indigo", "青": "indigo",
             "ruby": "ruby", "红玉": "ruby", "红": "ruby"}
    line = alias.get(a)
    if not line:
        return "要坐哪条航路? ocean board indigo(灵青) 或 ocean board ruby(红玉)。"
    now = game._now()
    if not sched.boarding_open(now):
        nb = sched.next_boarding(now)
        wait = nb.slot_start - int(now)
        return (f"❌ 错过登船了!! 下一班还有 {wait // 60} 分 {wait % 60} 秒。\n"
                f"   (每 2 小时一班, 每班只有开头 15 分钟能登船——就是这么残忍)")
    v = sched.current_voyage(now)
    if s.get("ocean_slot_used") == v.slot_start:
        nxt = v.slot_start + sched.VOYAGE_SPAN
        wait = nxt - int(now)
        return (f"⛔ 这班船你已经坐过了(一个班次只能登记一次)。\n"
                f"   下一班还有 {wait // 60} 分 {wait % 60} 秒。")
    key = v.route_key(line)
    s["ocean_slot_used"] = v.slot_start        # 登船即消耗本班资格(弃船也不退)
    s["casts"] = s.get("casts", 0) + 1          # 用抛竿计数推进 rng, 保持确定性
    import random as _random
    rng = _random.Random(s["seed"] * 1000003 + s["casts"])
    s["ocean"] = {
        "line": line, "route_key": key, "slot_start": v.slot_start,
        "station": 0, "budget": float(CASTS_PER_STATION),
        "spectral_casts": 0, "score": 0, "catches": 0,
        "bait": DEFAULT_BAIT, "crew": _crew(rng),
        # 成就追踪
        "spectral_catches": 0,        # 幻海流中总钓获数
        "self_triggered": False,       # 是否自引过幻海流
        "max_star": 0,                 # 本航次钓到的最高星级
        "spot_species": {},            # {spot_id: set(鱼名)} 每站种类(JSON存储时转list)
    }
    game._autosave()
    r = _route(key)
    stops = " → ".join(f"{_SPOT_NAME[str(x['spot_id'])]}({x['time']})"
                       for x in r["stops"])
    return "\n".join([
        f"⚓ 登上「不倦号」—— {sched.line_name(line)}·{r['name']}",
        f"   航线: {stops}",
        f"   同船 {CREW_SIZE} 位船友。每站 {CASTS_PER_STATION} 竿预算, 共 3 站。",
        f"   🪱 船上供应海钓饵({'、'.join(_OCEAN_BAITS.values())}), 已挂"
        f" {_OCEAN_BAITS[DEFAULT_BAIT]}; 特殊饵得出发前自己买好(蓝鱼需要)。",
        f"   第 1 站: {_stop_desc(s['ocean'])} —— ocean cast 开钓!",
    ])


def _cast_cmd(game, arg: str) -> str:
    s = game.state
    session = s.get("ocean")
    if not session:
        return "你不在船上。ocean 看班次, 登船窗口内 ocean board <航路>。"
    a = arg.strip()
    if a and a.lstrip("-").isdecimal() and int(a) < 1:
        return "次数得是正整数哦。"
    req = int(a) if a.lstrip("-").isdecimal() else 1
    n = min(30, max(1, req))
    import random as _random
    out = []
    for _ in range(n):
        if not s.get("ocean"):
            break                                # 航次已结算, 忽略多余竿数
        s["casts"] += 1
        rng = _random.Random(s["seed"] * 1000003 + s["casts"])
        ev = _cast_once(game, rng)
        out.append(_fmt_event(ev, s.get("ocean")))
    game._autosave()
    return "\n".join(out)


def _bait_cmd(game, arg: str) -> str:
    s = game.state
    session = s.get("ocean")
    if not session:
        return "不在船上。海钓饵是登船后在船上换的。"
    a = arg.strip()
    if not a:
        return (f"当前饵: {_bait_disp(session)}。船上供应: "
                + "、".join(_OCEAN_BAITS.values())
                + "; 也可挂你带上船的库存饵(蓝鱼需要特殊饵)。")
    for i, cn in _OCEAN_BAITS.items():          # 船上免费饵
        if a == cn or a.lower() in cn.lower():
            session["bait"] = i
            game._autosave()
            return f"🪱 已挂 {cn}(船上供应, 不限量)。"
    en = bait_mod.match(a)                       # 你带上船的主世界饵
    if en:
        if s.get("bait_stock", {}).get(en, 0) <= 0:
            return f"你没有 {bait_mod.disp(en)} 的库存——特殊饵得出发前在岸上买好。"
        session["bait"] = bait_mod.BAITS[en]["id"]
        game._autosave()
        return (f"🪱 已挂 {bait_mod.disp(en)}×{s['bait_stock'][en]}"
                f"(自带库存, 每竿损耗 1)。")
    return f"没有这种饵: {arg}。"


def _skill_cmd(game, skill: str) -> str:
    """海钓 GP 技能: 下一竿生效。dh=双提钩 th=三提钩 prize=大鱼确保。"""
    s = game.state
    session = s.get("ocean")
    if not session:
        return "你不在船上。GP 技能只在海上有用。"
    costs = {"dh": DOUBLE_HOOK_COST, "th": TRIPLE_HOOK_COST, "prize": PRIZE_CATCH_COST}
    names = {"dh": "双提钩", "th": "三提钩", "prize": "大鱼确保"}
    descs = {
        "dh": f"下一竿一次钓多条!（消耗 {DOUBLE_HOOK_COST} GP）",
        "th": f"下一竿钓更多条!（消耗 {TRIPLE_HOOK_COST} GP, 比双提钩更强）",
        "prize": f"下一竿渔分 ×{PRIZE_CATCH_PTS_MULT}!（消耗 {PRIZE_CATCH_COST} GP）",
    }
    cost = costs[skill]
    gp = s.get("gp", 0)
    if gp < cost:
        return f"GP 不够（{names[skill]}需 {cost}，现有 {gp}）。等回或喝 cordial。"
    # 双提钩和三提钩互斥; 大鱼确保可叠加
    if skill in ("dh", "th"):
        session.pop("buff_dh", None)
        session.pop("buff_th", None)
        session[f"buff_{skill}"] = True
    else:
        session["buff_prize"] = True
    s["gp"] -= cost
    session["skills_used"] = session.get("skills_used", 0) + 1
    game._autosave()
    combo = ""
    if skill in ("dh", "th") and session.get("buff_prize"):
        combo = "  (已叠加大鱼确保! 下一竿: 多鱼+高分)"
    elif skill == "prize" and (session.get("buff_dh") or session.get("buff_th")):
        hook = "双提钩" if session.get("buff_dh") else "三提钩"
        combo = f"  (已叠加{hook}! 下一竿: 多鱼+高分)"
    return f"🎣 {names[skill]}: {descs[skill]}  GP {gp} → {s['gp']}{combo}"


def _achievements_view(game) -> str:
    ach = set(game.state.get("achievements", []))
    visible = [b for b in _BONUSES if b["id"] != 11]   # 传说大渔旗(24人)隐藏
    total = len(visible)
    got = sum(1 for b in visible if b["id"] in ach)
    out = [f"🏅 海钓成就 {got}/{total}"]
    for b in visible:
        mark = "✅" if b["id"] in ach else "  "
        out.append(f"   {mark} {b['objective']['chs']}（+{b['bonusRate']-100}%）"
                   f" {b['requirement']['chs'][:40]}")
    return "\n".join(out)


def _quit(game) -> str:
    if not game.state.get("ocean"):
        return "你不在船上。"
    game.state["gp_at"] = game._now()           # 下船对表(#27)
    game.state["ocean"] = None
    game._autosave()
    return "🏳 你跳上了返航的小艇……本航次渔分作废。(下一班见)"


# --- 海钓鱼档案 + 出狱倒计时 --------------------------------
def _find_fish(name: str):
    """按中文名/英文名(精确优先, 唯一子串次之)找海钓鱼。"""
    q = (name or "").strip()
    if not q:
        return None
    if q in _FISH_BY_CN:
        return _FISH_BY_CN[q]
    ql = q.lower()
    for f in _FISH_BY_ITEM.values():
        if f.get("name_en", "").lower() == ql:
            return f
    subs = [f for f in _FISH_BY_ITEM.values()
            if q in f["name_cn"] or ql in f.get("name_en", "").lower()
            or q in f.get("cn_alias", "") or ql in f.get("en_alias", "").lower()]
    return subs[0] if len(subs) == 1 else None


def _bait_name_of(item_id: int) -> str:
    if item_id in _OCEAN_BAITS:
        return _OCEAN_BAITS[item_id] + "(船上供应)"
    en = _WORLD_BAIT_BY_ID.get(item_id)
    if en:
        return f"{bait_mod.disp(en)}(岸上 buybait, 自己带上船!)"
    return f"#{item_id}(暂不可得)"


def _fmt_rel(seconds: int) -> str:
    d, r = divmod(max(0, seconds), 86400)
    h, r = divmod(r, 3600)
    m = r // 60
    if d:
        return f"{d} 天 {h} 小时"
    if h:
        return f"{h} 小时 {m:02d} 分"
    return f"{m} 分钟"


def fish_status(game, name: str) -> str | None:
    """海钓鱼的 status: 出现地点/需求/下一班能钓它的船。找不到返回 None。"""
    f = _find_fish(name)
    if not f:
        q = (name or "").strip()
        ql = q.lower()
        subs = [x for x in _FISH_BY_ITEM.values()
                if q and (q in x["name_cn"] or ql in x.get("name_en", "").lower())]
        if 2 <= len(subs) <= 10:                 # 命中多条: 列出让玩家选
            names = "、".join(x["name_cn"] for x in subs[:10])
            return f"匹配到多条海钓鱼, 请写全名: {names}"
        return None
    item_id = f["itemId"]
    # 这条鱼出现在哪些 (站, 哪套鱼表)
    spots = []            # [(spot_id:int, side)]
    for sid, s in OCEAN["spots"].items():
        for side in ("normal", "spectral"):
            if item_id in s[side]:
                spots.append((int(sid), side))
    times = set(f["ikdTimes"] or [1, 2, 3])
    time_cn = {1: "白天", 2: "黄昏", 3: "夜晚"}
    star = "★" * f.get("stars", 0)
    tags = []
    if f["isBlueFish"]:
        tags.append("💙蓝鱼(传说)")
    if f["isSpectralFish"]:
        tags.append("✨幻光触发鱼(钓到即引发幻海流)")
    out = [f"🐟 {f['name_cn']}{star}"
           + (f" / {f['name_en']}" if f.get("name_en") else "")
           + f"  【海钓】渔分 {f['points']}"
           + ("  " + " ".join(tags) if tags else "")]
    for sid, side in spots:
        need = "需⚡幻海流" if side == "spectral" else "平时可钓"
        tt = "、".join(time_cn[t] for t in sorted(times))
        out.append(f"   出没: {_SPOT_NAME[str(sid)]}（{need}, 时段: {tt}）")
    if f.get("baitIds"):
        out.append("   鱼饵: " + " / ".join(_bait_name_of(b) for b in f["baitIds"]))
    # 出狱倒计时: 未来班次里, 哪几班的哪一站能遇到它
    now = game._now()
    want = {(sid, t) for sid, _side in spots for t in times}
    hits = []
    for v in sched.upcoming_voyages(144, now):       # 扫 12 天 = 一整轮
        for ln, key in v.routes:
            for i, stop in enumerate(_route(key)["stops"]):
                if (stop["spot_id"], _TIME_NUM[stop["time"]]) in want:
                    hits.append((v.slot_start, ln, key, i))
        if len(hits) >= 3:
            break
    if not hits:
        out.append("   🗓 未来 12 天的班次都不经过它的站——真正的牢底坐穿。")
        return "\n".join(out)
    out.append("   🗓 最近的机会:")
    session = game.state.get("ocean")
    used_slot = game.state.get("ocean_slot_used", 0)
    for slot, ln, key, i in hits[:3]:
        rel = slot - int(now)
        import time as _time
        wall = _time.strftime("%m-%d %H:%M", _time.localtime(slot))
        if rel <= 0 and session and session.get("slot_start") == slot:
            when = "就是你现在坐的这班!!"
        elif rel <= 0 and used_slot == slot:
            when = "本班(你已坐过这班船😌)"
        elif rel <= 0 and sched.boarding_open(now):
            when = f"就是本班!! 登船窗口还剩 {_fmt_rel(slot + sched.BOARDING_WINDOW - int(now))}"
        elif rel <= 0:
            when = "本班(登船已截止😭)"
        else:
            when = f"{_fmt_rel(rel)}后 ({wall})"
        spec = " +蹲⚡" if all(side == "spectral" for _s, side in spots) else ""
        out.append(f"     {when}  {sched.line_name(ln)}·{_route(key)['name']}"
                   f" 第{i + 1}站{spec}")
    return "\n".join(out)


def handle(game, arg: str) -> str:
    """ocean 命令族入口。game 是 engine.game.Game 实例。"""
    parts = (arg or "").strip().split(maxsplit=1)
    sub = parts[0].lower() if parts else ""
    rest = parts[1] if len(parts) > 1 else ""
    if sub in ("", "status", "look"):
        return _status(game)
    if sub in ("board", "登船", "上船"):
        return _board(game, rest)
    if sub in ("cast", "c"):
        return _cast_cmd(game, rest)
    if sub in ("bait", "饵"):
        return _bait_cmd(game, rest)
    if sub in ("dh", "doublehook", "双提钩"):
        return _skill_cmd(game, "dh")
    if sub in ("th", "triplehook", "三提钩"):
        return _skill_cmd(game, "th")
    if sub in ("prize", "prizecatch", "大鱼确保"):
        return _skill_cmd(game, "prize")
    if sub in ("quit", "leave", "弃船"):
        return _quit(game)
    if sub in ("routes", "schedule", "班次"):
        return _routes_view(game)
    if sub in ("achievements", "ach", "成就"):
        return _achievements_view(game)
    return ("ocean 用法: ocean(状态/班次) / ocean board <indigo|ruby>(登船) / "
            "ocean cast [N](抛竿) / ocean bait <饵名>(换饵) / "
            "ocean dh(双提钩) / ocean th(三提钩) / ocean prize(大鱼确保) / "
            "ocean routes(班次表) / ocean ach(成就) / ocean quit(弃船)")
