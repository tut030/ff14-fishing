"""
FF14 钓鱼 魔晶石模块 (镶嵌 + 禁断)
------------------------------------------------------------
读 data/materia.json(采集三系×12品级, 真实名字/数值)。

真实规则的落地:
  保底孔    装备的 sockets 数量内镶嵌 100% 成功
  禁断      仅 overmeld=True 的装备(白/绿装为主)可镶到 5 颗;
            超出保底孔的每一颗按"禁断成功率"判定, 失败 = 魔晶石当场炸掉 🎆
  成功率    高品级(5型+)用社区长期实测表(奇数型 17/10/7/5%, 偶数型 45/24/14/8%);
            1~4型是自制宽松档(老式低级石, 游戏后期已边缘化) —— 都在常量区可调
  获取      🎫/🎟票据购买(低品级白票/高品级紫票), 或用♻️分解出的碎片合成

★ 想调手感, 改下面常量即可 ★
"""

from __future__ import annotations
import json
from pathlib import Path

_P = Path(__file__).resolve().parent.parent / "data" / "materia.json"
_D = json.loads(_P.read_text(encoding="utf-8"))
MATERIA = {m["id"]: m for m in _D["materia"]}
_BY_CN = {m["name"]: m for m in _D["materia"]}

# ===== 可调常量 =============================================
MAX_MELDS = 5                # 禁断上限: 一件装备最多 5 颗
PURPLE_MIN_GRADE = 7         # 品级 ≥ 此值收🎟紫票, 否则🎫白票
WHITE_PRICE_PER_GRADE = 5    # 白票价 = 品级 × 此值
PURPLE_PRICE_PER_GRADE = 12  # 紫票价 = (品级-6) × 此值 + 20
SHARD_COST_LOW = 3           # 碎片合成: 品级 ≤6 需碎片数
SHARD_COST_HIGH = 6          # 碎片合成: 品级 ≥7 需碎片数

# 禁断成功率(%): 超出保底孔后的第 1/2/3/4 颗
# 5型及以上: 社区长期实测表(全球通用数值); 1~4型: 自制宽松档(可调)
OVERMELD_RATES_ODD = (17, 10, 7, 5)     # 奇数型(5/7/9/11)
OVERMELD_RATES_EVEN = (45, 24, 14, 8)   # 偶数型(6/8/10/12)
OVERMELD_RATES_LOW = (80, 60, 40, 20)   # 1~4型(自制)
# ===========================================================

# 禁断的烟花现场(失败文案池, 结算时随机抽)
BOOM_FLAVOR = [
    "🎆 砰!!魔晶石化作一团绚烂的粉尘——今晚的烟花由你赞助。",
    "🎆 一道闪光。你手里只剩下装备,和一颗碎掉的心。",
    "🎆 禁断失败!!附近的水晶商人露出了欣慰的微笑。",
    "🎆 石头炸了。你听见钱包也跟着炸了一声。",
    "🎆 失败……但烟花真的很好看。真的。",
]
MELD_OK_FLAVOR = [
    "✨ 咔——严丝合缝!装备泛起微光。",
    "✨ 成功!这一刻你是全艾欧泽亚最稳的手。",
    "✨ 稳稳嵌入。深藏功与名。",
]


def match(q: str):
    """按中文名/英文名找魔晶石: 精确优先, 唯一子串次之。"""
    q = (q or "").strip()
    if not q:
        return None
    if q in _BY_CN:
        return _BY_CN[q]
    ql = q.lower()
    for m in MATERIA.values():
        if m.get("name_en", "").lower() == ql:
            return m
    subs = [m for m in MATERIA.values()
            if q in m["name"] or (ql and ql in m.get("name_en", "").lower())]
    return subs[0] if len(subs) == 1 else None


def match_all(q: str) -> list:
    q = (q or "").strip()
    ql = q.lower()
    return [m for m in MATERIA.values()
            if q and (q in m["name"] or ql in m.get("name_en", "").lower())]


def price(m: dict):
    """(货币, 数额): 低品级白票, 高品级紫票。"""
    if m["grade"] >= PURPLE_MIN_GRADE:
        return "purple", (m["grade"] - 6) * PURPLE_PRICE_PER_GRADE + 20
    return "white", m["grade"] * WHITE_PRICE_PER_GRADE


def shard_cost(m: dict) -> int:
    return SHARD_COST_HIGH if m["grade"] >= PURPLE_MIN_GRADE else SHARD_COST_LOW


def overmeld_rate(m: dict, overmeld_slot: int) -> int:
    """禁断第 overmeld_slot(1基) 颗的成功率(%)。"""
    i = min(4, max(1, overmeld_slot)) - 1
    if m["grade"] <= 4:
        return OVERMELD_RATES_LOW[i]
    if m["grade"] % 2 == 0:
        return OVERMELD_RATES_EVEN[i]
    return OVERMELD_RATES_ODD[i]


def meld_plan(gear_item: dict, current_melds: int):
    """这件装备还能不能再嵌一颗?
    返回 (可否, 是否禁断, 禁断第几颗/0, 拒绝原因文本)。"""
    if current_melds < gear_item["sockets"]:
        return True, False, 0, ""
    if not gear_item["overmeld"]:
        if gear_item["sockets"] == 0:
            return False, False, 0, "这件装备没有魔晶石孔, 且不可禁断(蓝装/毕业装普遍如此)。"
        return False, False, 0, f"保底 {gear_item['sockets']} 孔已满, 这件装备不可禁断。"
    if current_melds >= MAX_MELDS:
        return False, False, 0, f"已嵌满 {MAX_MELDS} 颗(禁断上限)。"
    return True, True, current_melds - gear_item["sockets"] + 1, ""
