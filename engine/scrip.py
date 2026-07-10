"""
FF14 钓鱼 票据/收藏品模块 (采集票据 Scrips)
------------------------------------------------------------
真实机制 -> 命令行的翻译:
  收藏品模式  collector on/off 开关; 开着时钓到的鱼不卖 gil,
              而是判"收藏价值"——达标进收藏品背包, 不达标只能放生(真实之痛)
  上交换票    turnin 一键上交全部收藏品:
              低级鱼(等级 < PURPLE_MIN_LEVEL) 换 🎫白票,
              高级鱼换 🎟紫票; 价值越高换得越多
  票据用途    图鉴书改用紫票购买(真实经济); 以后接毕业装/魔晶石商店
  海钓产出    航次结算按渔分附送票据(真实: 海钓给采集票据)

★ 想调经济手感, 改下面的常量即可, 不用动逻辑 ★
"""

from __future__ import annotations

# ===== 可调常量 =============================================
PURPLE_MIN_LEVEL = 61        # 鱼等级 ≥ 此值 -> 上交得紫票, 否则白票
COLLECT_CAP = 100            # 收藏品背包容量(满了再钓只能放生)
COLLECT_MIN = 30             # 收藏价值达标线(低于只能放生, 一无所获)

# 收藏价值基础(按竿感): 越稀有的鱼价值越高
_VALUE_BY_TUG = {"Light": 26, "Medium": 48, "Heavy": 80, "Legendary": 130}
_VALUE_DEFAULT = 30
HQ_VALUE_MULT = 1.5          # HQ 收藏价值 ×1.5

WHITE_DIV = 8                # 白票 = 收藏价值 // 此值
PURPLE_DIV = 12              # 紫票 = 收藏价值 // 此值(高级鱼)

BOOK_PRICE_DIV = 100         # 图鉴书票价 = 原gil价 // 此值 (紫票, 至少10张)
BOOK_PRICE_MIN = 10

OCEAN_WHITE_DIV = 120        # 海钓结算: 白票 = 渔分 // 此值
OCEAN_PURPLE_DIV = 400       # 海钓结算: 紫票 = 渔分 // 此值

SCRIP_ROD_MIN_ILVL = 700     # 装等 ≥ 此值的竿是"毕业竿", 只收🎟紫票(真实经济)
ROD_PRICE_BASE = 620         # 毕业竿紫票价 = max(下限, ilvl - 此值)
ROD_PRICE_MIN = 60
# ===========================================================


def is_scrip_rod(rod: dict) -> bool:
    """这把竿是不是毕业竿(票据专卖, gil 买不到)。"""
    return (rod.get("ilvl") or 0) >= SCRIP_ROD_MIN_ILVL


def rod_scrip_price(rod: dict) -> int:
    """毕业竿的紫票价格。"""
    return max(ROD_PRICE_MIN, (rod.get("ilvl") or 0) - ROD_PRICE_BASE)


PERCEPTION_VALUE_COEF = 0.0015   # 每点鉴别力 +0.15% 收藏价值(原作: 鉴别力↔收藏价值) ★可调


def roll_value(rng, fish: dict, hq: bool, perception: int = 0) -> int:
    """一条鱼在收藏品模式下的收藏价值(带随机浮动; 鉴别力抬高价值)。"""
    base = _VALUE_BY_TUG.get(fish.get("tug"), _VALUE_DEFAULT)
    v = base * rng.uniform(0.7, 1.3) * (1 + perception * PERCEPTION_VALUE_COEF)
    if hq:
        v *= HQ_VALUE_MULT
    return int(v)


def scrip_kind(fish: dict) -> str:
    """这条鱼上交换哪种票: 'purple' / 'white'。"""
    return "purple" if (fish.get("level") or 1) >= PURPLE_MIN_LEVEL else "white"


def turnin(state: dict) -> tuple[int, int, int]:
    """上交全部收藏品, 返回 (件数, 白票增量, 紫票增量); 原地清空背包。"""
    items = state.get("collectables", [])
    white = purple = 0
    for it in items:
        if it["kind"] == "purple":
            purple += max(1, it["value"] // PURPLE_DIV)
        else:
            white += max(1, it["value"] // WHITE_DIV)
    n = len(items)
    state["collectables"] = []
    state["scrip_white"] = state.get("scrip_white", 0) + white
    state["scrip_purple"] = state.get("scrip_purple", 0) + purple
    return n, white, purple


def book_price(gil_price: int) -> int:
    """图鉴书的紫票价格(由原 gil 价换算)。"""
    return max(BOOK_PRICE_MIN, gil_price // BOOK_PRICE_DIV)


def ocean_award(points: int) -> tuple[int, int]:
    """海钓结算按渔分给票: 返回 (白票, 紫票)。"""
    return points // OCEAN_WHITE_DIV, points // OCEAN_PURPLE_DIV
