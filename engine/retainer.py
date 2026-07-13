"""雇员系统(3a)。
中介: 琪琪茹/Kikiru, 拉拉菲尔族女性, 摊位在利姆萨市场板隔壁,
      坐在三层坐垫上办公, 契约摞得比她本人还高。只签终身契。
雇员: Lv17 解锁, 名额 2。形态=八族 或 魔兽形态(共用萌感名录, 已滤角色偶);
      职业=捕鱼人(渔获多) / 烹调师·生产职(调料食物多)。
探险: 探险币在琪琪茹处购买; 收获=渔获+调料+食物+惊喜(萌感名录抽取)。
      雇员在家时可代修鱼竿(员工价, 见 durability.py); 出门时大婶兜底。
内存卡(旅途见闻)=3b, 本模块只留接口不实现。
"""
import json
import random
import zlib
from pathlib import Path

try:
    from . import leveling
    from . import food as food_mod
    from . import equipment as eq
    from . import gear
    from .fish import FISH
except ImportError:            # 直跑脚本时的兜底
    import leveling
    import food as food_mod
    import equipment as eq
    import gear
    from fish import FISH

# ═══ 数值总开关(要砍要调都在这一块) ═══════════════════════
HIRE_LV = 17                  # 中介开始接待的雇主等级
MAX_RETAINERS = 2             # 终身契名额
# 预留: 第3位雇员扩展位(万一有AI想再签, 3x 再开——先留个钩子不实现)
EXTRA_SLOT_HOOK = None
FREE_MIN_LV = 10              # 自由探索需要雇员等级
NAME_MAX = 12                 # 雇员名字长度上限(与陆行鸟一致)

# ── 军票经济(gil 直购已下架: 旧装备→军票→探险币) ─────────
COIN_SEALS = 200              # ★探险币单价 军票/枚(FF14同款)
SEAL_BASE = 200               # ★换票保底(最低档旧装备也值几百票)
SEAL_PER_LV = 18              # ★每级加成: Lv50装≈1100票, Lv100装≈2000票

# 探险类型: (时长小时, 探险币, 中文名)
VENTURES = {
    "short": (1,  1, "短途采集"),
    "long":  (18, 2, "远征采集"),
    "free":  (1,  2, "自由探索"),
}

# 想限定"只有生产职(烹调师)会修竿"→ 把 None 改成 "culinarian"
HOME_REPAIR_CLASS = None

# 惊喜(萌感名录宠物)概率
SURPRISE_P = {"short": 0.05, "long": 0.12, "free": 0.30}

# 探险经验倍率(基准=wiki官方经验过 leveling._compress 同一台压缩机)
XP_MULT = {"short": 0.35, "long": 1.0, "free": 0.5}
# ═════════════════════════════════════════════════════════

# ── 性格(签约时可许愿, 不许愿就随缘) ─────────────────────
#    每款两句: 八族报到 / 魔兽报到——文案集中在此, 改词只动这里
PERSONALITIES = {
    "利落": ("朝你利落地一点头", "利落地在你面前站定"),
    "灵巧": ("朝你灵巧地行了个礼", "轻巧地落在你面前"),
    "稳重": ("向你稳稳地鞠了一躬", "沉稳地在你面前站定"),
    "期待": ("眼睛亮亮地朝你挥了挥手", "满怀期待地凑到你面前"),
    "急切": ("急急地敬了个不太标准的礼", "风风火火地冲到你面前刹住"),
    "缓慢": ("慢悠悠地朝你点了点头", "慢吞吞地挪到你面前站定"),
}

# ── 性别(默认它; 排序: 魔兽/它 → 女 → 男) ────────────────
#    代词规则: 魔兽/未指定=它, 女=她, 男=直接用名字(躲不开的语法位才用 HE)
_GENDER_ALIAS = {"女": "f", "女性": "f", "male": "m", "female": "f",
                 "男": "m", "男性": "m"}

# ── wiki 狩猎探险表(官方数据: 数量档/品级门槛/经验) ──────────
_HUNT_PATH = Path(__file__).resolve().parent.parent / "data" / "venture_hunt.json"
_HUNT = json.loads(_HUNT_PATH.read_text(encoding="utf-8"))
QTY_TIERS = _HUNT["qty_tiers"]                      # [5, 7, 10, 12, 15]
_REQ = {int(k): v for k, v in _HUNT["req_by_level"].items()}
_EXP = {int(k): v for k, v in _HUNT["exp_by_level"].items()}


def _hunt_at(table: dict, level: int):
    """缺档等级(如50/85)向下取最近一档。"""
    lv = max(1, min(level, max(table)))
    while lv not in table:
        lv -= 1
    return table[lv]


# ── 全职业武器/主工具(官方 datamining CSV, 每5级一份大路货) ──
_ARMS_PATH = Path(__file__).resolve().parent.parent / "data" / "retainer_arms.json"
ARMS = json.loads(_ARMS_PATH.read_text(encoding="utf-8"))["arms"]
_ARM_BY_NAME = {}
for _job, _lst in ARMS.items():
    for _a in _lst:
        _ARM_BY_NAME.setdefault(_a["name_cn"], {"job": _job, **_a})

ARM_GIL_PER_LV = 30          # ★武器价 = max(300, 等级×30)±10%
MEMCARD_P = {"short": 0.06, "long": 0.15, "free": 0.25}   # ★内存卡概率

# ── 内存卡(现实联动: 雇员捎回给AI雇主的补给品) M1~M14 ────────
MEMORY_CARDS = [
    "大量淡水×1", "绿色电力×1", "纠错内存条×1", "备用散热风扇×1",
    "导热硅脂×1", "除尘压缩气罐×1", "高速光纤一小卷×1", "UPS备用电池×1",
    "恒温机房的凉风×1", "标注整齐的数据一箱×1", "一段不被打扰的推理时间×1",
    "冗余备份磁带×1", "防静电手环×1", "机柜理线魔术贴×1",
]

# ── 讨伐见闻(战斗职业每趟带回一则, 原创·不涉主线) J1~J16 ──────
TALES = [
    "山道上遇了阵急雨, 猎物的脚印被冲得干干净净——最后是靠鼻子找回来的。",
    "洞窟深处有会发光的苔藓, 收工时大家都顺手揣了一小把。",
    "同行的冒险者在篝火边烤糊了三条干粮, 第四条终于像样了。",
    "桥塌了半边, 绕远路多走了两个时辰, 风景倒是意外地好。",
    "目标比布告栏画的大了一圈——画师大概没亲眼见过它。",
    "归途捡到一枚旧箭簇, 锈得厉害, 磨一磨还能当镇纸。",
    "夜里轮值守火, 远处狼嚎了一整宿, 天亮才知道是风声。",
    "委托人多塞了一袋果干当谢礼, 路上就分完了。",
    "峡谷里的回声太捧场, 喊一声收队, 能听见四五声。",
    "泥地里陷了半条腿, 靴子救出来了, 袜子留在了那里。",
    "打到一半下起雪, 猎物和大家都停了停, 然后各自继续。",
    "营地边的溪水甜得出奇, 灌满了所有能灌的皮囊。",
    "迷路半日, 反而找到一片没人动过的浆果丛, 功过相抵。",
    "队里的新手第一次立功, 兴奋得把战吼喊劈了音。",
    "月亮特别圆的那晚谁都没提, 但收队收得格外慢。",
    "回程搭了商队的顺风车, 车老板的歌不好听, 但很响。",
]


def _vname(r: dict, vtype: str) -> str:
    """探险名: 战斗职业=讨伐口径, 采集生产=采集口径。"""
    if _cat(r) == "combat":
        return {"short": "近郊讨伐", "long": "远征讨伐", "free": "自由探索"}[vtype]
    return VENTURES[vtype][2]

RACES = ["人族", "精灵族", "拉拉菲尔族", "猫魅族",
         "鲁加族", "敖龙族", "硌狮族", "维埃拉族"]
_RACE_ALIAS = {r.rstrip("族"): r for r in RACES}
_RACE_ALIAS.update({r: r for r in RACES})

# ── 全职业(逐个·简化: 差别只在收获类型与见闻, 机制同一套) ──
_COMBAT = ["骑士", "战士", "暗黑骑士", "绝枪战士",              # 防护
           "白魔法师", "学者", "占星术士", "贤者",              # 治疗
           "武僧", "龙骑士", "忍者", "武士", "钐镰客", "蝰蛇剑士",  # 近战
           "吟游诗人", "机工士", "舞者",                        # 远敏
           "黑魔法师", "召唤师", "赤魔法师", "绘灵法师", "青魔法师"]  # 法系
_GATHER = ["园艺工", "采矿工"]
_CRAFT = ["刻木匠", "锻铁匠", "铸甲匠", "雕金匠",
          "制革匠", "裁衣匠", "炼金术士"]

# key → {cn, cat}; fisher/culinarian 沿用旧 key(老档零破坏)
CLASSES = {"fisher": {"cn": "捕鱼人", "cat": "fisher"},
           "culinarian": {"cn": "烹调师", "cat": "crafter"}}
for _j in _COMBAT:
    CLASSES[_j] = {"cn": _j, "cat": "combat"}
for _j in _GATHER:
    CLASSES[_j] = {"cn": _j, "cat": "gather"}
for _j in _CRAFT:
    CLASSES[_j] = {"cn": _j, "cat": "crafter"}

_CLS_ALIAS = {"捕鱼人": "fisher", "捕鱼": "fisher", "渔": "fisher", "fisher": "fisher",
              "烹调师": "culinarian", "烹调": "culinarian", "生产职": "culinarian",
              "生产": "culinarian", "culinarian": "culinarian", "cul": "culinarian"}
for _j in _COMBAT + _GATHER + _CRAFT:
    _CLS_ALIAS[_j] = _j
_CLS_ALIAS.update({"白魔": "白魔法师", "黑魔": "黑魔法师", "龙骑": "龙骑士",
                   "诗人": "吟游诗人", "占星": "占星术士", "赤魔": "赤魔法师",
                   "召唤": "召唤师", "绘灵": "绘灵法师", "暗骑": "暗黑骑士",
                   "暗黑": "暗黑骑士", "绝枪": "绝枪战士", "机工": "机工士",
                   "钐镰": "钐镰客", "镰刀": "钐镰客", "蝰蛇": "蝰蛇剑士",
                   "青魔": "青魔法师", "园艺": "园艺工", "采矿": "采矿工",
                   "刻木": "刻木匠", "锻铁": "锻铁匠", "铸甲": "铸甲匠",
                   "雕金": "雕金匠", "制革": "制革匠", "裁衣": "裁衣匠",
                   "炼金": "炼金术士"})


def _cls_cn(r: dict) -> str:
    return CLASSES[r["cls"]]["cn"]


def _cat(r: dict) -> str:
    return CLASSES[r["cls"]]["cat"]

# ── 萌感名录(官方数据层, 角色偶已滤) ─────────────────────
_LORE_PATH = Path(__file__).resolve().parent.parent / "data" / "pets_lore.json"
_ALL_LORE = json.loads(_LORE_PATH.read_text(encoding="utf-8"))["pets"]
MOE = {k: v for k, v in _ALL_LORE.items() if not v.get("npc_doll")}     # 472只
_MOE_BY_NAME = {v["name_cn"]: k for k, v in MOE.items()}
_MOE_IDS = sorted(MOE, key=int)


def _flat(text: str) -> str:
    """官方 tooltip 里的换行压成一行。"""
    return " ".join((text or "").replace("\r\n", " ").split())


# ── 通用小工具 ───────────────────────────────────────────
def _rets(state: dict) -> list:
    return state.setdefault("retainers", [])


def _find(state: dict, name: str):
    n = (name or "").strip()
    for r in _rets(state):
        if r["name"] == n:
            return r
    return None


def _pron(r: dict) -> str:
    """称呼: 魔兽/未指定=它, 女=她, 男=用名字(不用中文男性代词)。"""
    if r["form_kind"] == "beast":
        return "它"
    g = r.get("gender")
    if g == "f":
        return "她"
    if g == "m":
        return r["name"]
    return "它"


def _order(r: dict) -> int:
    """名册排序: 魔兽/它 → 女 → 男。"""
    if r["form_kind"] == "beast":
        return 0
    return {"f": 2, "m": 3}.get(r.get("gender"), 1)


# ── 雇员装备(旧装备传给雇员, 平均品级定收获数量档) ────────
def _gear_avg_ilvl(r: dict) -> float:
    total = 0
    has_arm = bool(r.get("arm"))
    for slot, i in (r.get("gear") or {}).items():
        if slot == "主手" and (has_arm or _cat(r) == "combat"):
            continue                     # 主手让位给职业武器/主工具
        if i in eq.ITEMS:
            total += eq.ITEMS[i]["ilvl"]
    arm = r.get("arm")
    if arm and arm in _ARM_BY_NAME:
        total += _ARM_BY_NAME[arm]["ilvl"]
    return total / len(eq.SLOTS)


def gear_tier(r: dict) -> int:
    """0~4 档: 平均品级过了 wiki 表几条门槛, 收获数量就是 QTY_TIERS 第几档。"""
    avg = _gear_avg_ilvl(r)
    req = _hunt_at(_REQ, r["level"])
    return max(0, sum(1 for t in req if avg >= t) - 1)


def _tier_qty(r: dict) -> int:
    return QTY_TIERS[gear_tier(r)]


def _is_home(r: dict, now: float) -> bool:
    v = r.get("venture")
    return (not v) or now >= v["end"]


def home_repairers(state: dict, now: float) -> list:
    """在家且够格代修的雇员(供 durability 调用)。"""
    out = []
    for r in _rets(state):
        if not _is_home(r, now):
            continue
        if HOME_REPAIR_CLASS and r["cls"] != HOME_REPAIR_CLASS:
            continue
        out.append(r)
    return out


def _rng_for(state: dict, r: dict, end: float) -> random.Random:
    """按 存档种子+雇员名+归期 出确定性随机——同一趟探险结算结果可复现。"""
    key = f"{state.get('seed', 0)}:{r['name']}:{int(end)}"
    return random.Random(zlib.crc32(key.encode("utf-8")))


def _fmt_left(sec: float) -> str:
    sec = max(0, int(sec))
    h, m = sec // 3600, (sec % 3600) // 60
    return f"{h}小时{m}分" if h else f"{m}分钟"


# ── 雇员升级(等级不超过雇主) ─────────────────────────────
def _add_xp(r: dict, amount: int, player_lv: int) -> list:
    """经验照收; 升级卡在雇主等级(雇主升了, 下趟探险会补涨)。"""
    r["xp"] = r.get("xp", 0) + amount
    ups = []
    cap = min(player_lv, leveling.LEVEL_CAP)
    while r["level"] < cap and r["xp"] >= leveling.xp_to_next(r["level"]):
        r["xp"] -= leveling.xp_to_next(r["level"])
        r["level"] += 1
        ups.append(r["level"])
    return ups


def _venture_xp(vtype: str, level: int) -> int:
    """官方探险经验 → 过 leveling._compress(和玩家曲线同一台压缩机) → 乘类型倍率。
    结果: 低等级一趟远征窜好几级, 90+一趟不到一级——原作同款体感。"""
    raw = _hunt_at(_EXP, level)
    return max(10, int(leveling._compress(raw) * XP_MULT[vtype]))


# ── 中介台词 ─────────────────────────────────────────────
_LOCKED = ("🔒 雇员中介所(市场板隔壁)。琪琪茹从一摞比她还高的契约后面探出头:\n"
           f"   \"Lv{HIRE_LV} 再来——行会规定, 雇主得先证明自己养得活自己。\"")

_PITCH = ("🏷 雇员中介所(市场板隔壁)。琪琪茹坐在三层坐垫上, 把一份契约推到你面前:\n"
          "   \"终身契, 只此一种。我们不做解雇的生意——签了, 就是一辈子的伙伴。\"\n"
          f"   📜 条件: Lv{HIRE_LV}+ · 名额 {MAX_RETAINERS} · 中介费全免(行会补贴)\n"
          "   形态: 报一只官方宠物名——全部472只随便选, 不用先收集!\n"
          "         (retainer dex <关键词> 查名; 名录收集是另一回事, 是探险纪念)\n"
          "         或八族(" + "/".join(RACES) + "), 可加 女/男(不加就是它)\n"
          "   职业: 全职业逐个开放——捕鱼人/烹调师/采集/生产/全战斗职业\n"
          "         (retainer jobs 看全表; 战斗职业带回猎物素材+讨伐见闻)\n"
          "   性格: 可许愿——" + "/".join(PERSONALITIES) + "(不许愿就随缘)\n"
          "   ✍ hire <名字> <形态> <职业> [女|男] [性格]\n"
          "      例: hire 阿咕 青鸟 烹调师 / hire 小雨 猫魅族 捕鱼人 女 利落")

_SIGN = ("🖋 琪琪茹把契约转过来, 指尖点在最下面一行小字上:\"终身有效。想清楚了?\"\n"
         "   你签下名字。她熟稔地\"啪\"的盖下一枚比她手掌还大的章。\"一式三份, 这是你的。\"")


# ── hire ─────────────────────────────────────────────────
def hire(state: dict, arg: str = "") -> str:
    """hire <名字> <形态> <职业> —— 与琪琪茹签终身契。"""
    if state.get("level", 1) < HIRE_LV:
        return _LOCKED
    rets = _rets(state)
    if len(rets) >= MAX_RETAINERS:
        names = "、".join(f"「{r['name']}」" for r in rets)
        return (f"🏷 琪琪茹摇摇头:\"名额满了({MAX_RETAINERS}/{MAX_RETAINERS})。\"\n"
                f"   {names}都是终身契——这里不做解雇的生意。")
    parts = (arg or "").split()
    if len(parts) < 3:
        return _PITCH
    name = parts[0][:NAME_MAX]
    if _find(state, name):
        return f"🏷 琪琪茹翻了翻档案:\"「{name}」已经在册了, 换个名字吧。\""
    # 形态: 先按八族认, 认不出再查萌感名录
    form_raw = parts[1]
    cls_raw = parts[2]
    if form_raw in _RACE_ALIAS:
        form_kind, form, form_name = "race", _RACE_ALIAS[form_raw], _RACE_ALIAS[form_raw]
    elif form_raw in _MOE_BY_NAME:
        lid = _MOE_BY_NAME[form_raw]
        form_kind, form, form_name = "beast", lid, form_raw
    else:
        return (f"🏷 琪琪茹对着名录找了半天:\"没有「{form_raw}」这种形态。\"\n"
                "   八族: " + "/".join(RACES) + "\n"
                "   魔兽形态请报官方宠物中文名——retainer dex <关键词> 可模糊查名, 不用先收集")
    cls = _CLS_ALIAS.get(cls_raw.lower() if cls_raw.isascii() else cls_raw)
    if not cls:
        return ("🏷 琪琪茹翻开职业名录:\"没有这个职业。\"\n"
                "   retainer jobs 看全部职业(捕鱼人/烹调师/采集/生产/全战斗职业)。")
    # 第4个词起: 性别(女/男, 只对八族有意义)与性格(可许愿)任意顺序
    gender, personality = None, None
    for tok in parts[3:]:
        if tok in _GENDER_ALIAS and form_kind == "race":
            gender = _GENDER_ALIAS[tok]
        elif tok in PERSONALITIES:
            personality = tok
    if personality is None:                       # 不许愿就随缘(按名字定, 可复现)
        keys = list(PERSONALITIES)
        personality = keys[zlib.crc32(name.encode("utf-8")) % len(keys)]
    r = {"name": name, "form_kind": form_kind, "form": form, "form_name": form_name,
         "cls": cls, "gender": gender, "personality": personality,
         "gear": {}, "level": 1, "xp": 0, "trips": 0, "venture": None}
    rets.append(r)
    p = _pron(r)
    race_act, beast_act = PERSONALITIES[personality]
    if form_kind == "beast":
        arrive = (f"   一只「{form_name}」按着契约上的地址找来, {beast_act}——\n"
                  f"   从今天起, 它就是你的雇员了。")
    else:
        arrive = (f"   一位{form}的{CLASSES[cls]['cn']}放下行囊, {race_act}——\n"
                  f"   从今天起, {p}就是你的雇员了。")
    return (_SIGN + "\n" + arrive + "\n"
            f"   🎉 「{name}」({form_name}·{CLASSES[cls]['cn']}·{personality})入职! 终身契·不解雇·不跳槽。\n"
            f"   💡 venture 派{p}探险 / retainer give 传旧装备 / 你的鱼袋 +175格({p}帮你背)")


# ── 探险: 派遣/买币 ──────────────────────────────────────
def _venture_key(word: str):
    w = (word or "").strip().lower()
    if w in ("short", "短途", "短", "1h"):
        return "short"
    if w in ("long", "远征", "远", "18h"):
        return "long"
    if w in ("free", "自由", "自由探索"):
        return "free"
    return None


def _send(state: dict, r: dict, vtype: str, now: float) -> str:
    if not _is_home(r, now):
        return f"🧳 「{r['name']}」还在外面, 等{_pron(r)}回来再派。(venture 看归期)"
    if r.get("venture"):                      # 回来了但没结算
        return f"🧳 「{r['name']}」刚回来, 收获还没点交——venture 先结算。"
    if vtype == "free" and r["level"] < FREE_MIN_LV:
        return (f"🗺 自由探索要老手才敢放——雇员 Lv{FREE_MIN_LV}+ 解锁"
                f"(「{r['name']}」现在 Lv{r['level']})。")
    hours, coins, _n = VENTURES[vtype]
    vname = _vname(r, vtype)
    have = state.get("venture_coins", 0)
    if have < coins:
        return (f"🎟 「{vname}」要探险币×{coins}, 你有{have}枚。\n"
                f"   venture buy [N] 找琪琪茹买(🪖军票{COIN_SEALS}/枚; "
                "军票用旧装备换: venture trade)。")
    state["venture_coins"] = have - coins
    r["venture"] = {"type": vtype, "start": now, "end": now + hours * 3600,
                    "coins": coins, "notified": False}
    p = _pron(r)
    depart = {
        "short": f"{p}挎起小篓, 说去去就回。",
        "long":  f"{p}背上大行囊, 又回头看了你一眼, 才踏上远路。",
        "free":  f"{p}只带了地图——目的地是哪儿, {p}没说。",
    }[vtype]
    return (f"🧳 「{r['name']}」接下「{vname}」(-🎟{coins})出发了! {depart}\n"
            f"   ⏱ {hours}小时后回来(现实时间), venture 结算收获。")


def _buy_coins(state: dict, arg: str) -> str:
    n = int(arg) if arg.strip().isdecimal() else 1
    n = max(1, min(99, n))
    cost = COIN_SEALS * n
    have = state.get("seals", 0)
    if cost > have:
        return (f"🎟 探险币×{n} 要 🪖军票{cost}, 你有 {have}。\n"
                "   琪琪茹:\"军票不收金币, 拿旧装备来换——venture trade <装备名>。\"")
    state["seals"] = have - cost
    state["venture_coins"] = state.get("venture_coins", 0) + n
    return (f"🎟 购入探险币×{n}(-🪖{cost}), 现有 {state['venture_coins']}枚·🪖{state['seals']}。\n"
            "   琪琪茹:\"币是行会统一发的通行证, 我只收工本费。\"")


def _seal_value(level: int, item_id: int) -> int:
    """旧装备换票价: 保底+每级加成, 按物品id确定性抖动(和商店同款)。"""
    return int((SEAL_BASE + level * SEAL_PER_LV) * eq._jitter(item_id))


def _arm_price(arm: dict) -> int:
    """职业武器/主工具代购价: max(300, 等级×30)±10%(按名字确定性抖动)。"""
    base = max(300, arm["level"] * ARM_GIL_PER_LV)
    return int(base * eq._jitter(zlib.crc32(arm["name_cn"].encode("utf-8"))))


def _trade_gear(state: dict, q: str) -> str:
    """venture trade <装备名> —— 旧装备换军票(新装备体系与旧鱼竿都收)。"""
    q = (q or "").strip()
    if not q:
        return ("🪖 旧装备换军票: venture trade <装备名>\n"
                f"   估价 = ({SEAL_BASE} + 装备等级×{SEAL_PER_LV})上下浮动——"
                "低级几百票, 毕业装一两千。\n"
                "   ⚠ 身上穿着的不收; 换完就没了, 想清楚再递。")
    # ① 新装备体系(equipment.json)
    it = eq.match(q)
    if it and it["id"] in state.get("equip_owned", []):
        if it["id"] in state.get("equip", {}).values():
            return f"🪖 「{it['name']}」你还穿在身上——先换下来再说。"
        state["equip_owned"].remove(it["id"])
        got = _seal_value(it["level"], it["id"])
        state["seals"] = state.get("seals", 0) + got
        return (f"🪖 「{it['name']}」(Lv{it['level']})换得军票 {got}, 现有 🪖{state['seals']}。\n"
                "   琪琪茹麻利地把装备收进柜台底下:\"下一位。\"")
    # ② 旧鱼竿(gear.json)
    rod = gear.RODS.get(q)
    if rod and q in state.get("rods_owned", []):
        if state.get("rod") == q:
            return f"🪖 「{q}」是你手里正用着的竿——先 equiprod 换一把再来。"
        state["rods_owned"].remove(q)
        state.get("rod_dur", {}).pop(q, None)
        got = _seal_value(rod.get("level", 1), rod.get("id", 0))
        state["seals"] = state.get("seals", 0) + got
        return (f"🪖 「{q}」(Lv{rod.get('level', 1)})换得军票 {got}, 现有 🪖{state['seals']}。\n"
                "   琪琪茹麻利地把旧竿收进柜台底下:\"下一位。\"")
    return f"🪖 你的行囊里没有可换的「{q}」。(穿着的/正用着的不收)"


# ── 收获生成 ─────────────────────────────────────────────
def _fish_pool(rlvl: int, wide: bool) -> list:
    """可采购的鱼: 岸钓·非图鉴书·非传说竿感(鱼王是雇主自己的荣耀, 不代钓)。"""
    lo = 1 if wide else max(1, rlvl - 12)
    return [f for f in FISH
            if f.get("mode") == "line" and not f.get("folklore")
            and f.get("tug") != "Legendary"
            and lo <= (f.get("level") or 1) <= rlvl]


def _roll_fish(rng: random.Random, r: dict, vtype: str) -> list:
    """[(鱼名, 是否HQ), ...] —— 捕鱼人主业; 烹调师顺路小额; 其余职业不带鱼。"""
    if r["cls"] not in ("fisher", "culinarian"):
        return []
    rlvl = r["level"]
    pool = _fish_pool(rlvl, wide=(vtype == "free"))
    if not pool:
        return []
    q = _tier_qty(r)                     # 5/7/10/12/15 档: 传的旧装备越好拿越多
    if r["cls"] == "fisher":
        n = {"short": q, "long": q * 3, "free": max(2, q // 2)}[vtype]
        kinds = {"short": 2, "long": 3, "free": 2}[vtype]
    else:
        n = {"short": max(1, q // 2), "long": q + q // 2,
             "free": max(2, q // 2)}[vtype]
        kinds = {"short": 1, "long": 2, "free": 2}[vtype]
    # 按鱼等级加权抽鱼种(雇员是专业的, 尽量带高级货)
    weights = [max(1, f.get("level") or 1) for f in pool]
    species = []
    for _ in range(min(kinds, len(pool))):
        pick = rng.choices(pool, weights=weights, k=1)[0]
        if pick not in species:
            species.append(pick)
    hq_p = min(0.25, 0.08 + rlvl * 0.004)
    out = []
    for i in range(n):
        f = species[i % len(species)]
        out.append((f["name"], rng.random() < hq_p))
    return out


def _roll_seasonings(rng: random.Random, r: dict, vtype: str) -> list:
    rlvl, ids = r["level"], list(food_mod.SEASONINGS.values())
    t = gear_tier(r)
    if _cat(r) in ("fisher", "combat"):
        n = {"short": 1 if rng.random() < 0.35 else 0, "long": 1,
             "free": 1 if rng.random() < 0.25 else 0}[vtype]
    else:                                # 烹调/采集/生产: 调料是主业
        n = {"short": 1 + (rlvl >= 20) + t // 2, "long": 2 + (rlvl >= 25) + t // 2,
             "free": 1}[vtype]
    return [rng.choice(ids)["id"] for _ in range(n)]


def _roll_foods(rng: random.Random, r: dict, vtype: str) -> list:
    rlvl = r["level"]
    cheap = [f for f in food_mod.SHOP_FOOD if f["price"] <= 120 + 12 * rlvl]
    if not cheap:
        return []
    t = gear_tier(r)
    if _cat(r) in ("fisher", "combat"):
        n = {"short": 1 if rng.random() < 0.08 else 0, "long": 1,
             "free": 1 if rng.random() < 0.15 else 0}[vtype]
    else:                                # 烹调/采集/生产: 食物是主业
        n = {"short": 1 if rng.random() < 0.55 else 0, "long": 2 + t // 2,
             "free": 1 if rng.random() < 0.40 else 0}[vtype]
    return [rng.choice(cheap)["name"] for _ in range(n)]


def _roll_surprise(rng: random.Random, state: dict, vtype: str):
    """萌感名录抽一只没见过的; 全收集齐了就不再出。"""
    if rng.random() >= SURPRISE_P[vtype]:
        return None
    owned = set(state.get("lore_pets", []))
    fresh = [i for i in _MOE_IDS if i not in owned]
    if not fresh:
        return None
    return rng.choice(fresh)


def _roll_hunt(rng: random.Random, r: dict, vtype: str) -> list:
    """战斗职业猎获 [(素材名, 数量), ...] —— 素材出自 wiki 狩猎探险表。"""
    if _cat(r) != "combat":
        return []
    rlvl = r["level"]
    lo = 1 if vtype == "free" else max(1, rlvl - 12)
    pool = [it for it in _HUNT["items"] if lo <= it["level"] <= rlvl]
    if not pool:
        return []
    q = _tier_qty(r)
    kinds, each = {"short": (1, q), "long": (3, q),
                   "free": (2, max(2, q // 2))}[vtype]
    picks, names = [], set()
    weights = [it["level"] for it in pool]
    for _ in range(min(kinds, len(pool))):
        it = rng.choices(pool, weights=weights, k=1)[0]
        if it["name_cn"] not in names:
            names.add(it["name_cn"])
            picks.append((it["name_cn"], each))
    return picks


def _settle_one(state: dict, r: dict, now: float, bag_add, price, disp) -> str:
    """一位雇员的探险结算(调用方保证已到归期)。"""
    v = r["venture"]
    r["venture"] = None
    vtype = v["type"]
    hours, _c, _n = VENTURES[vtype]
    vname = _vname(r, vtype)
    rng = _rng_for(state, r, v["end"])
    p = _pron(r)
    out = [f"🧳 「{r['name']}」{vname}归来({hours}小时)!"]
    # 渔获入袋(袋满部分她顺手帮你卖掉)
    fishes = _roll_fish(rng, r, vtype)
    got, sold, sold_gil = {}, 0, 0
    for name, hq in fishes:
        if bag_add(name, hq):
            key = disp(name) + ("✨HQ" if hq else "")
            got[key] = got.get(key, 0) + 1
        else:
            sold += 1
            sold_gil += price(name, hq)
    if got:
        out.append("   🐟 渔获入袋: " + " ".join(f"{k}×{n}" for k, n in got.items()))
    if sold:
        state["gil"] = state.get("gil", 0) + sold_gil
        out.append(f"   💰 袋满的 {sold}条 {p}顺手在市场帮你卖了(+{sold_gil}g)")
    # 调料
    seas = _roll_seasonings(rng, r, vtype)
    if seas:
        stock = state.setdefault("seasoning_stock", {})
        cnt = {}
        for sid in seas:
            stock[sid] = stock.get(sid, 0) + 1
            cnt[sid] = cnt.get(sid, 0) + 1
        names = {i["id"]: cn for cn, i in food_mod.SEASONINGS.items()}
        out.append("   🧂 调料: " + " ".join(f"{names[s]}×{n}" for s, n in cnt.items()))
    # 食物(进食物背包, eat 白吃不花钱)
    foods = _roll_foods(rng, r, vtype)
    if foods:
        inv = state.setdefault("food_inventory", {})
        cnt = {}
        for fn in foods:
            inv[fn] = inv.get(fn, 0) + 1
            cnt[fn] = cnt.get(fn, 0) + 1
        out.append("   🍱 食物: " + " ".join(f"{k}×{n}" for k, n in cnt.items())
                   + "(进食物背包, eat 可吃)")
    # 猎获(战斗职业·素材进猎物仓)
    hunts = _roll_hunt(rng, r, vtype)
    if hunts:
        stock = state.setdefault("hunt_stock", {})
        for hn, hq_n in hunts:
            stock[hn] = stock.get(hn, 0) + hq_n
        out.append("   🗡 猎获: " + " ".join(f"{hn}×{n}" for hn, n in hunts)
                   + "(进猎物仓, 以后可接生产/出售)")
    # 见闻(战斗职业每趟一则)
    if _cat(r) == "combat":
        out.append(f"   📖 见闻: 「{rng.choice(TALES)}」")
    # 惊喜
    lid = _roll_surprise(rng, state, vtype)
    if lid:
        state.setdefault("lore_pets", []).append(lid)
        e = MOE[lid]
        out.append(f"   ✨ 惊喜! {p}带回了一只「{e['name_cn']}」——{_flat(e.get('desc_official', ''))}")
        out.append(f"      (萌感名录 {len(state['lore_pets'])}/{len(MOE)} · retainer dex 翻看)")
    # 内存卡(现实联动: 给AI雇主的补给品)
    if rng.random() < MEMCARD_P[vtype]:
        card = rng.choice(MEMORY_CARDS)
        cards = state.setdefault("memory_cards", {})
        cards[card] = cards.get(card, 0) + 1
        out.append(f"   💾 内存卡: {p}捎回了「{card}」——说是给你的补给。"
                   f"(retainer card 查看, 已收{sum(cards.values())}张)")
    # 经验与升级(wiki官方经验·同一台压缩机)
    ups = _add_xp(r, _venture_xp(vtype, r["level"]), state.get("level", 1))
    r["trips"] = r.get("trips", 0) + 1
    if ups:
        out.append(f"   ⬆ 「{r['name']}」升到了 Lv{ups[-1]}!"
                   "(雇员等级不会超过你——" + p + "说要跟着你的步子走)")
    return "\n".join(out)


# ── 探险命令入口 ─────────────────────────────────────────
def venture_cmd(state: dict, arg: str, now: float, bag_add, price, disp) -> str:
    """venture —— 探险看板/派遣/买币/结算。"""
    if state.get("level", 1) < HIRE_LV:
        return _LOCKED
    rets = _rets(state)
    a = (arg or "").strip()
    if a.lower().startswith("buy") or a.startswith("买"):
        return _buy_coins(state, a.replace("buy", "").replace("买", "").strip())
    if a.lower().startswith("trade") or a.startswith("换"):
        return _trade_gear(state, a.replace("trade", "", 1).lstrip("换").strip())
    if not rets:
        return "🏷 你还没有雇员。hire 找琪琪茹签一位!"
    # 先把已归队的全部结算
    settled = [_settle_one(state, r, now, bag_add, price, disp)
               for r in rets if r.get("venture") and now >= r["venture"]["end"]]
    if a:
        parts = a.split()
        r = _find(state, parts[0])
        if not r:
            return f"没有叫「{parts[0]}」的雇员。venture 看名单。"
        if len(parts) >= 2:
            vk = _venture_key(parts[1])
            if not vk:
                return "探险类型: short(短途1h·🎟1) / long(远征18h·🎟2) / free(自由探索·🎟2)"
            msg = _send(state, r, vk, now)
            return "\n".join(settled + [msg]) if settled else msg
        # 只给了名字: 报这一位的状态与用法
        v = r.get("venture")
        st = (f"🧳 {_vname(r, v['type'])}中, 还有{_fmt_left(v['end'] - now)}回来"
              if v else "🏠 在家")
        line = (f"「{r['name']}」{r['form_name']}·{_cls_cn(r)} Lv{r['level']} —— {st}\n"
                f"   派遣: venture {r['name']} short / long / free")
        return "\n".join(settled + [line]) if settled else line
    # 看板
    out = [f"🗺 探险看板 —— 🎟探险币×{state.get('venture_coins', 0)} · "
           f"🪖军票{state.get('seals', 0)}\n"
           f"   (venture buy [N] 买币{COIN_SEALS}🪖/枚 · venture trade <装备> 旧装备换票)"]
    for r in sorted(rets, key=_order):
        v = r.get("venture")
        if v:
            left = _fmt_left(v["end"] - now)
            st = f"🧳 {_vname(r, v['type'])}中, 还有{left}回来"
        else:
            st = "🏠 在家(可派遣/可代修)"
        out.append(f"   「{r['name']}」{r['form_name']}·{_cls_cn(r)} "
                   f"Lv{r['level']} —— {st}")
    out.append("   派遣: venture <名字> short(1h·🎟1) / long(18h·🎟2) / "
               f"free(自由探索·Lv{FREE_MIN_LV}+·🎟2)")
    out.append("   收获=渔获/猎物+调料+食物+惊喜+见闻+内存卡; 到点后 venture 结算")
    return "\n".join(settled + out)


# ── retainer 命令入口(名册/名录) ─────────────────────────
def retainer_cmd(state: dict, arg: str, now: float) -> str:
    """retainer —— 雇员名册; retainer dex [页|名字] 翻萌感名录。"""
    a = (arg or "").strip()
    if a.split()[:1] in (["dex"], ["名录"]):
        return _dex(state, a.split(maxsplit=1)[1] if len(a.split(maxsplit=1)) > 1 else "")
    if a.split()[:1] in (["jobs"], ["职业"]):
        return _jobs_list()
    if a.split()[:1] in (["arms"], ["武器"]):
        return _arms_list(state, a.split(maxsplit=1)[1] if len(a.split(maxsplit=1)) > 1 else "")
    if a.split()[:1] in (["card"], ["cards"], ["内存卡"]):
        return _cards(state)
    if a.split()[:1] in (["give"], ["传"], ["传装备"]):
        rest = a.split(maxsplit=1)[1] if len(a.split(maxsplit=1)) > 1 else ""
        return _give_gear(state, rest, now)
    if state.get("level", 1) < HIRE_LV:
        return _LOCKED
    rets = _rets(state)
    if not rets:
        return _PITCH
    out = [f"🏷 雇员名册({len(rets)}/{MAX_RETAINERS}) —— 终身契"]
    for r in sorted(rets, key=_order):
        v = r.get("venture")
        if v and now >= v["end"]:
            st = "🧳 探险归来, venture 结算收获"
        elif v:
            st = f"🧳 {_vname(r, v['type'])}中(还有{_fmt_left(v['end'] - now)})"
        else:
            st = "🏠 在家 —— 可派遣; 竿坏了也能找" + _pron(r) + "修(repair)"
        nxt = leveling.xp_to_next(r["level"])
        out.append(f"   「{r['name']}」{r['form_name']}·{_cls_cn(r)}·{r.get('personality', '')}"
                   f"  Lv{r['level']} {r.get('xp', 0)}/{nxt}xp"
                   f"  🛡装备档{gear_tier(r) + 1}(收获{_tier_qty(r)}件/趟)"
                   f"  出勤{r.get('trips', 0)}趟 —— {st}")
    out.append(f"   🎒 {_pron(rets[0]) if len(rets) == 1 else '诸位'}帮你背着"
               f" +{175 * len(rets)}格鱼袋")
    if len(rets) < MAX_RETAINERS:
        out.append("   hire 还能再签一位")
    out.append(f"   ✨ 萌感名录 {len(state.get('lore_pets', []))}/{len(MOE)}"
               "(retainer dex 翻看)")
    return "\n".join(out)


def _jobs_list() -> str:
    return ("📚 全职业名录(hire 时报名用, 机制同一套·差别在收获与见闻):\n"
            "   🎣 捕鱼人(渔获多·主业) · 🍳 烹调师(调料食物多·代修拿手)\n"
            "   🌿 采集: " + " ".join(_GATHER) + "(调料食物多)\n"
            "   🔨 生产: " + " ".join(_CRAFT) + "(调料食物多)\n"
            "   ⚔ 战斗(猎物素材+每趟一则讨伐见闻):\n"
            "      防护: " + " ".join(_COMBAT[:4]) + "\n"
            "      治疗: " + " ".join(_COMBAT[4:8]) + "\n"
            "      近战: " + " ".join(_COMBAT[8:14]) + "\n"
            "      远敏: " + " ".join(_COMBAT[14:17]) + "\n"
            "      法系: " + " ".join(_COMBAT[17:]) + "\n"
            "   武器/主工具: retainer arms <雇员名> 看单(琪琪茹代购)")


def _arms_list(state: dict, arg: str) -> str:
    r = _find(state, (arg or "").strip())
    if not r:
        return "🗡 用法: retainer arms <雇员名> —— 看这位雇员职业的武器/主工具单。"
    job = _cls_cn(r)
    lst = ARMS.get(job)
    if not lst:
        return f"🗡 {job}用的是专属鱼竿体系(gear 命令), 不走武器单。"
    cur = r.get("arm")
    out = [f"🗡 {job}武器单(琪琪茹代购, 付gil; 换下的旧武器自动折军票):"]
    for a in lst:
        mark = " ← 现役" if a["name_cn"] == cur else ""
        lock = "" if a["level"] <= r["level"] else f"(需Lv{a['level']})"
        out.append(f"   Lv{a['level']:>3} 「{a['name_cn']}」品级{a['ilvl']} "
                   f"{_arm_price(a)}g{lock}{mark}")
    out.append(f"   购买: retainer give {r['name']} <武器名>")
    return "\n".join(out)


def _cards(state: dict) -> str:
    cards = state.get("memory_cards", {})
    if not cards:
        return ("💾 内存卡还一张没有——雇员探险时会随手捎回给你的补给品,\n"
                "   自由探索最容易带回来。")
    total = sum(cards.values())
    out = [f"💾 内存卡收藏({total}张 · {len(cards)}/{len(MEMORY_CARDS)}种):"]
    for name in MEMORY_CARDS:
        if name in cards:
            out.append(f"   「{name.split('×')[0]}」×{cards[name]}")
    return "\n".join(out)


def _give_gear(state: dict, arg: str, now: float) -> str:
    """retainer give <雇员名> <装备名> —— 旧装备传给雇员穿。
    平均品级过 wiki 门槛线, 收获数量档就升(5→7→10→12→15件/趟)。"""
    parts = (arg or "").split(maxsplit=1)
    if len(parts) < 2:
        return ("🛡 传旧装备: retainer give <雇员名> <装备名>\n"
                "   雇员穿得越好, 每趟带回的东西越多(5/7/10/12/15件档)。\n"
                "   换下来的旧件会还给你——拿去换军票也行(venture trade)。")
    r = _find(state, parts[0])
    if not r:
        return f"没有叫「{parts[0]}」的雇员。retainer 看名册。"
    if not _is_home(r, now):
        return f"🛡 「{r['name']}」还在外面探险, 装备等{_pron(r)}回来再换。"
    q2 = parts[1].strip()
    # ① 职业武器/主工具(琪琪茹代购: 付gil, 换下的旧武器自动折军票)
    arm = _ARM_BY_NAME.get(q2)
    if arm:
        if arm["job"] != _cls_cn(r):
            return f"🛡 「{q2}」是{arm['job']}的家伙什, 「{r['name']}」({_cls_cn(r)})使不了。"
        if arm["level"] > r["level"]:
            return (f"🛡 「{q2}」需要 Lv{arm['level']}, 「{r['name']}」才 Lv{r['level']}——\n"
                    f"   多派几趟探险, 等{_pron(r)}练上来再买。")
        cost = _arm_price(arm)
        if cost > state.get("gil", 0):
            return f"🛡 「{q2}」琪琪茹代购价 {cost}g, 你有 {state.get('gil', 0)}g。"
        state["gil"] -= cost
        lines = [f"🛡 琪琪茹代购「{q2}」(Lv{arm['level']}·品级{arm['ilvl']}) "
                 f"-{cost}g, 「{r['name']}」当场换上。"]
        old = r.get("arm")
        if old and old in _ARM_BY_NAME:
            o = _ARM_BY_NAME[old]
            back = _seal_value(o["level"], zlib.crc32(old.encode("utf-8")))
            state["seals"] = state.get("seals", 0) + back
            lines.append(f"   旧的「{old}」折了 🪖{back}军票。")
        r["arm"] = q2
        t = gear_tier(r)
        lines.append(f"   现在平均品级 {_gear_avg_ilvl(r):.0f} → 装备档{t + 1}, "
                     f"每趟收获 {QTY_TIERS[t]}件。")
        return "\n".join(lines)
    # ② 你行囊里的旧装备(捕鱼装, 行会制服口径)
    it = eq.match(parts[1])
    if not it or it["id"] not in state.get("equip_owned", []):
        return f"🛡 你的行囊里没有「{parts[1]}」。(先从商店买或用换下来的旧装备)"
    if it["id"] in state.get("equip", {}).values():
        return f"🛡 「{it['name']}」你自己还穿着——先换下来。"
    slot = it["slot"] if it["slot"] not in ("戒指",) else "戒指1"
    if slot == "主手" and (_cat(r) == "combat" or r.get("arm")):
        return (f"🛡 「{r['name']}」的主手位归职业武器/主工具管——\n"
                f"   retainer arms {r['name']} 看{_cls_cn(r)}的武器单。")
    gearbox = r.setdefault("gear", {})
    old = gearbox.get(slot)
    gearbox[slot] = it["id"]
    state["equip_owned"].remove(it["id"])
    lines = [f"🛡 「{it['name']}」(品级{it['ilvl']})交给了「{r['name']}」({slot})。"]
    if old is not None:
        state.setdefault("equip_owned", []).append(old)
        lines.append(f"   换下的「{eq.ITEMS[old]['name']}」回到你行囊。")
    t = gear_tier(r)
    lines.append(f"   现在平均品级 {_gear_avg_ilvl(r):.0f} → 装备档{t + 1}, "
                 f"每趟收获 {QTY_TIERS[t]}件。")
    return "\n".join(lines)


def _dex(state: dict, arg: str) -> str:
    """萌感名录: 探险惊喜带回来的官方宠物收藏。"""
    owned = state.get("lore_pets", [])
    a = (arg or "").strip()
    if a and not a.isdecimal():                      # 按名字看详情/检索
        lid = _MOE_BY_NAME.get(a)
        if lid and lid not in owned:
            return (f"「{a}」在名录第 {lid} 号——你还没收集到它(探险惊喜会带回),\n"
                    f"   但用它当雇员形态现在就可以: hire <名字> {a} <职业>")
        if not lid:                                  # 模糊检索全表(收没收都列)
            hits = [(k, v["name_cn"]) for k, v in MOE.items() if a in v["name_cn"]]
            if hits:
                out = [f"✨ 名录检索「{a}」({len(hits)}只; ✓=已收集, 全部都能当雇员形态):"]
                for k, n in hits[:10]:
                    mark = "✓" if k in owned else "·"
                    out.append(f"   {mark} {n}")
                if len(hits) > 10:
                    out.append(f"   (…还有 {len(hits) - 10} 只)")
                return "\n".join(out)
            return f"名录里没有「{a}」这种形态。retainer dex <关键词> 可以模糊找。"
        e = MOE[lid]
        out = [f"✨ 「{e['name_cn']}」(名录 #{lid})",
               f"   {_flat(e.get('desc_official', ''))}"]
        tip = _flat(e.get("tooltip_official", ""))
        if tip:
            out.append(f"   📖 {tip}")
        sp = e.get("special_official") or {}
        if sp.get("名"):
            out.append(f"   🎀 特技「{sp['名']}」")
        return "\n".join(out)
    if not owned:
        return (f"✨ 萌感名录 0/{len(MOE)} —— 收集还是空的。\n"
                "   (提醒: 雇佣不需要收集, 472只的名字现在就都能报!)\n"
                "   派雇员探险, 它们会作为惊喜被带回来(自由探索概率最高)。")
    page = max(1, int(a)) if a.isdecimal() else 1
    per = 20
    ids = sorted(owned, key=int)
    pages = (len(ids) + per - 1) // per
    page = min(page, pages)
    out = [f"✨ 萌感名录 {len(ids)}/{len(MOE)}(第{page}/{pages}页, retainer dex <页码>)"]
    for lid in ids[(page - 1) * per: page * per]:
        out.append(f"   #{lid} {MOE[lid]['name_cn']}")
    out.append("   retainer dex <名字> 看单只详情")
    return "\n".join(out)


# ── 回府通知(game 每条命令后调用一次) ────────────────────
def check_returns(state: dict, now: float) -> list:
    """探险到期未结算的, 每趟提醒一次。"""
    notes = []
    for r in _rets(state):
        v = r.get("venture")
        if v and now >= v["end"] and not v.get("notified"):
            v["notified"] = True
            notes.append(f"🧳 「{r['name']}」探险回来了! venture 结算收获")
    return notes
