"""
FF14 钓鱼 鱼竿装备模块
------------------------------------------------------------
读 data/gear.json(真实鱼竿: 装备等级/品级/采集力/鉴别力)。
装备鱼竿给被动加成:
  鉴别力(Perception) -> 提高 HQ 概率(贴合游戏: 鉴别力本来就管 HQ)
  采集力(Gathering)  -> 提高稀有鱼概率(游戏对钓鱼此项作用不明确, 这是我们的温和取用)

★ 想调手感, 改下面几个数 ★
数据来源: Teamcraft(游戏原文), 由 tools/build_gear_data.py 生成。
"""

from __future__ import annotations
import json
from pathlib import Path

_P = Path(__file__).resolve().parent.parent / "data" / "gear.json"
_D = json.loads(_P.read_text(encoding="utf-8"))
RODS = {r["name"]: r for r in _D["rods"]}     # 名字 -> 鱼竿

# ===== 数值(随便调) =====================================
HQ_BASE = 0.12            # 无鱼竿时的 HQ 基础概率
HQ_CAP = 0.60             # HQ 概率上限
PERCEPTION_HQ = 0.0003    # 每点鉴别力 +多少 HQ 概率
GATHERING_RARE = 0.0005   # 每点采集力, 对稀有鱼权重的加成系数
PRICE_PER_ILVL = 40       # 定价 = max(200, ilvl*该值) — 平衡数字, 非游戏真实售价
# ========================================================


def price(rod: dict) -> int:
    return max(200, rod["ilvl"] * PRICE_PER_ILVL)


def match(arg: str):
    a = (arg or "").strip().lower()
    if not a:
        return None
    for n, r in RODS.items():
        if n.lower() == a:
            return r
    for n, r in RODS.items():
        if a in n.lower():
            return r
    return None


def hq_chance(rod) -> float:
    p = rod["perception"] if rod else 0
    return min(HQ_CAP, HQ_BASE + p * PERCEPTION_HQ)


def hq_chance_from(perception: int) -> float:
    """按(全身聚合的)鉴别力数值算 HQ 概率。"""
    return min(HQ_CAP, HQ_BASE + perception * PERCEPTION_HQ)
