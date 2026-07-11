"""
FF14 钓鱼 全身装备模块 (11 部位)
------------------------------------------------------------
读 data/equipment.json(589 件真实捕鱼人装备: 中文名/部位/三维/
稀有度/魔晶石孔数/可否禁断——全部游戏原文字段)。

真实规则的落地:
  三维生效   全身求和: 获得力→稀有鱼概率↑  鉴别力→HQ概率↑
             采集力→GP 上限(毕业装直接喂养海钓双提钩的弹药池)
  货币分层   蓝装(稀有度3)=票据毕业装: 穿戴等级<90 收🎫白票, ≥90 收🎟紫票
             白/绿装(稀有度1/2) 收 gil, 价格按等级浮动(低等级≈1500g, 暂定)
             紫装(稀有度4, 古武类) 非卖品, 以后另接
  价格波动   同档不齐价: 按物品 id 做确定性 ±10% 抖动(不是随机, 可复现)
  回收分解   recycle: 返一点 gil(0~1000) + 一点票 + 偶尔魔晶石碎片(③伏笔)
  主手兼容   未穿新体系主手时, 沿用旧鱼竿(gear.py)的数值, 老档零破坏

★ 想调经济手感, 改下面常量即可 ★
"""

from __future__ import annotations
import json
from pathlib import Path

try:
    from . import gear as _gear
except ImportError:
    import gear as _gear

_P = Path(__file__).resolve().parent.parent / "data" / "equipment.json"
_D = json.loads(_P.read_text(encoding="utf-8"))
ITEMS = {it["id"]: it for it in _D["items"]}          # id -> 装备
_BY_CN = {}
for _it in _D["items"]:
    _BY_CN.setdefault(_it["name"], _it)               # 重名取先出现

# 穿戴槽位(戒指两枚)
SLOTS = ["主手", "头部", "身体", "手部", "腿部", "脚部",
         "耳饰", "项链", "手镯", "戒指1", "戒指2"]

# ===== 可调常量 =============================================
BLUE_PURPLE_MIN_LEVEL = 90   # 蓝装穿戴等级 ≥ 此值收紫票, 否则白票
WHITE_PRICE_DIV = 4          # 蓝装白票价 = max(下限, ilvl // 此值)
WHITE_PRICE_MIN = 20
PURPLE_PRICE_BASE = 560      # 蓝装紫票价 = max(下限, ilvl - 此值)
PURPLE_PRICE_MIN = 60
GIL_PER_LEVEL = 30           # 白/绿装 gil 价 = max(下限, 等级*此值) → Lv50≈1500
GIL_PRICE_MIN = 300
PRICE_JITTER = 0.10          # 同档价格 ±10% 确定性抖动(按id, 可复现)

RECYCLE_GIL_MAX = 1000       # 回收: gil 随机 0~此值
RECYCLE_WHITE_MAX = 4        # 回收: 白票随机 0~此值
RECYCLE_PURPLE_MAX = 2       # 回收: 紫票随机 0~此值(仅高级蓝装)
RECYCLE_SHARD_P = 0.20       # 回收: 魔晶石碎片掉率(③魔晶石系统的原料)
# ===========================================================


def match(q: str):
    """按中文名/英文名找装备: 精确优先, 唯一子串次之; 找不到返回 None。"""
    q = (q or "").strip()
    if not q:
        return None
    if q in _BY_CN:
        return _BY_CN[q]
    ql = q.lower()
    for it in ITEMS.values():
        if it.get("name_en", "").lower() == ql:
            return it
    subs = [it for it in ITEMS.values()
            if q in it["name"] or (ql and ql in it.get("name_en", "").lower())]
    return subs[0] if len(subs) == 1 else None


def match_all(q: str) -> list:
    """子串命中的全部装备(供多命中列表)。"""
    q = (q or "").strip()
    ql = q.lower()
    return [it for it in ITEMS.values()
            if q and (q in it["name"] or ql in it.get("name_en", "").lower())]


def _jitter(item_id: int) -> float:
    """按 id 的确定性价格抖动: -10% ~ +10%。"""
    return 1.0 + ((item_id * 2654435761) % 21 - 10) / 100 * (PRICE_JITTER * 10)


def price(it: dict):
    """(货币, 数额): 货币 ∈ 'gil'/'white'/'purple'/None(非卖品)。
    白/绿装: 优先使用官方 NPC 买价(price_mid); 无官方价则回退公式。
    蓝装: 票据定价(白票/紫票)。紫装: 非卖品。"""
    j = _jitter(it["id"])
    if it["rarity"] >= 4:
        return None, 0
    if it["rarity"] == 3:                             # 蓝装 = 票据毕业装
        if it["level"] >= BLUE_PURPLE_MIN_LEVEL:
            return "purple", int(max(PURPLE_PRICE_MIN,
                                     it["ilvl"] - PURPLE_PRICE_BASE) * j)
        return "white", int(max(WHITE_PRICE_MIN,
                                it["ilvl"] // WHITE_PRICE_DIV) * j)
    # 白/绿装: 优先官方 NPC 买价
    mid = it.get("price_mid", 0)
    if mid and mid > 2:                               # price_mid=2 通常是非NPC商品
        return "gil", int(mid * j)
    return "gil", int(max(GIL_PRICE_MIN, it["level"] * GIL_PER_LEVEL) * j)


CURRENCY_DISP = {"gil": "g", "white": "🎫", "purple": "🎟"}


def price_disp(it: dict) -> str:
    cur, amt = price(it)
    if cur is None:
        return "非卖品"
    return f"{CURRENCY_DISP[cur]}{amt}" if cur != "gil" else f"{amt}g"


def slot_key_of(it: dict, state: dict) -> str:
    """这件装备应落在哪个槽(戒指优先落空槽, 都满落戒指1)。"""
    if it["slot"] != "戒指":
        return it["slot"]
    eq = state.get("equip", {})
    if not eq.get("戒指1"):
        return "戒指1"
    if not eq.get("戒指2"):
        return "戒指2"
    return "戒指1"


def stats_total(state: dict) -> dict:
    """全身三维求和(含镶嵌魔晶石); 主手空槽时回退旧鱼竿(gear.py)数值。"""
    try:
        from . import materia as _mat
    except ImportError:
        import materia as _mat
    total = {"获得力": 0, "鉴别力": 0, "采集力": 0}
    eq = state.get("equip", {}) or {}
    melds = state.get("melds", {}) or {}
    for slot in SLOTS:
        iid = eq.get(slot)
        it = ITEMS.get(iid) if iid else None
        if it:
            for k, v in it["stats"].items():
                total[k] = total.get(k, 0) + v
            for mid in melds.get(str(iid), []):        # 镶嵌加成
                m = _mat.MATERIA.get(mid)
                if m:
                    total[m["param"]] = total.get(m["param"], 0) + m["value"]
    if not eq.get("主手"):                             # 旧鱼竿兼容
        rod = _gear.RODS.get(state.get("rod") or "")
        if rod:
            total["获得力"] += rod.get("gathering", 0)
            total["鉴别力"] += rod.get("perception", 0)
    # ── 竿耐久惩罚: ≤20% 采集/鉴别减半, =0% 归零 ──
    try:
        from . import durability as _dur
    except ImportError:
        import durability as _dur
    _f = _dur.stat_factor(state)
    if _f < 1.0:
        total["获得力"] = int(total["获得力"] * _f)
        total["鉴别力"] = int(total["鉴别力"] * _f)
    return total


def gp_bonus(state: dict) -> int:
    """装备提供的 GP 上限加成(=全身采集力之和)。"""
    return stats_total(state).get("采集力", 0)


def recycle_roll(rng, it: dict) -> dict:
    """分解一件装备的产出(确定性 rng 由调用方给)。"""
    out = {"gil": rng.randint(0, RECYCLE_GIL_MAX),
           "white": 0, "purple": 0, "shard": False}
    if it["rarity"] >= 3:
        out["white"] = rng.randint(0, RECYCLE_WHITE_MAX)
        if it["level"] >= BLUE_PURPLE_MIN_LEVEL:
            out["purple"] = rng.randint(0, RECYCLE_PURPLE_MAX)
    else:
        out["white"] = rng.randint(0, max(1, RECYCLE_WHITE_MAX // 2))
    out["shard"] = rng.random() < RECYCLE_SHARD_P
    return out
