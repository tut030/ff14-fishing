"""
FF14 钓鱼 鱼饵模块
------------------------------------------------------------
读 data/bait.json(可买鱼饵: 真实价 + 中文名)。
玩法(选项①): 大鱼要挂对饵才咬钩; 杂鱼见饵就上; 买不到饵的特殊大鱼不卡饵。
数据来源: 游戏原文(shops/items/datamining-cn)。
"""

from __future__ import annotations
import json
from pathlib import Path

_P = Path(__file__).resolve().parent.parent / "data" / "bait.json"
BAITS = json.loads(_P.read_text(encoding="utf-8"))["baits"]     # {en: {id, price, cn}}

# ═══ 饵料经济总开关(实测反馈: 中级消耗饵入不敷出) ══════════
# 拟饵家族 = 永久渔具: 买一次终身用, 不随抛竿消耗(万能拟饵原作同款)
LURE_KEYWORDS = ("Fly", "Minnow", "Lure", "Jig", "Spinner", "Spoon", "Plug")
# 消耗饵限价: ≤起点原价; 超出部分打折并封顶 —— 61g赤虫→35g档
SQUASH_FROM = 17
SQUASH_K = 0.4
SQUASH_CAP = 120
# 断线叼饵: 提钩失手时, 挂着的拟饵有概率被鱼带走(所以老钓手备2~3个)
SNAP_LEGEND = 0.25        # 鱼王(Legendary)失手
SNAP_WEAK = 0.12          # 获得力 < 鱼等级×SNAP_WEAK_FACTOR 还硬拉
SNAP_BASE = 0.03          # 正常失手的倒霉概率
SNAP_WEAK_FACTOR = 5
# ═══════════════════════════════════════════════════════════


def is_lure(name: str) -> bool:
    """拟饵/亮片/铁板类 = 永久渔具(不消耗)。"""
    return name in BAITS and any(k in name for k in LURE_KEYWORDS)


def raw_price(name: str) -> int:
    """官方原始价(内部档位判定用, 不受限价影响)。"""
    return BAITS.get(name, {}).get("price", 0)


def price(name: str) -> int:
    """商店售价: 拟饵=原价(一次性投资); 消耗饵过限价曲线。"""
    p = raw_price(name)
    if is_lure(name) or p <= SQUASH_FROM:
        return p
    return min(SQUASH_CAP, SQUASH_FROM + int((p - SQUASH_FROM) * SQUASH_K))


def disp(name: str) -> str:
    cn = BAITS.get(name, {}).get("cn")
    return f"{cn}/{name}" if cn else name


def bait_level(name: str) -> int:
    """鱼饵的"适用等级"(基于价格推算)。低级便宜饵在高级钓场会降低上钩率。
    1-3g → Lv1, 4-8g → Lv10, 9-15g → Lv20, 16-60g → Lv35,
    61-100g → Lv50, 101-400g → Lv60, 400g+ → Lv80。"""
    p = raw_price(name)
    if p <= 3:
        return 1
    if p <= 8:
        return 10
    if p <= 15:
        return 20
    if p <= 60:
        return 35
    if p <= 100:
        return 50
    if p <= 400:
        return 60
    return 80


def bait_penalty(bait_name: str, spot_level: int) -> float:
    """低级饵在高级钓场的权重惩罚系数(0.05~1.0)。
    等级差 ≤5 无惩罚; 差距越大惩罚越重; 最低 5% 上钩率。"""
    bl = bait_level(bait_name) if bait_name else 1
    gap = spot_level - bl
    if gap <= 5:
        return 1.0
    return max(0.05, 1.0 - (gap - 5) * 0.04)


def match(arg: str):
    """按 英文饵名 / 中文饵名 / "中文/English" 查, 返回英文饵名 or None。"""
    a = (arg or "").strip().lower()
    if not a:
        return None
    for part in ([a] + (a.split("/") if "/" in a else [])):
        part = part.strip()
        for en, info in BAITS.items():
            if en.lower() == part or (info.get("cn") and info["cn"].lower() == part):
                return en
    return None


def maybe_snap(state: dict, bait_name: str, tug: str, fish_level: int,
               gathering: int, rng) -> str | None:
    """提钩失手 → 拟饵可能被叼走。返回断线台词或 None。消耗饵不走这里(咬钩已耗)。"""
    if not bait_name or not is_lure(bait_name):
        return None
    if tug == "Legendary":
        p = SNAP_LEGEND
    elif gathering < fish_level * SNAP_WEAK_FACTOR:
        p = SNAP_WEAK
    else:
        p = SNAP_BASE
    if rng.random() >= p:
        return None
    st = state.setdefault("bait_stock", {})
    st[bait_name] = st.get(bait_name, 1) - 1
    left = st.get(bait_name, 0)
    if left <= 0:
        st.pop(bait_name, None)
    tail = (f" (还剩{left}个)" if left > 0
            else " (这是最后一个……老钓手都备2~3个)")
    return f"\n💥 鱼线\"啪\"地断了——「{disp(bait_name)}」也被叼进了深处!{tail}"
