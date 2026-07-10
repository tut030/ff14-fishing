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


def price(name: str) -> int:
    return BAITS.get(name, {}).get("price", 0)


def disp(name: str) -> str:
    cn = BAITS.get(name, {}).get("cn")
    return f"{cn}/{name}" if cn else name


def bait_level(name: str) -> int:
    """鱼饵的"适用等级"(基于价格推算)。低级便宜饵在高级钓场会降低上钩率。
    1-3g → Lv1, 4-8g → Lv10, 9-15g → Lv20, 16-60g → Lv35,
    61-100g → Lv50, 101-400g → Lv60, 400g+ → Lv80。"""
    p = price(name)
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
