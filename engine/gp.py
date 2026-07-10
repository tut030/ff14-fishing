"""
FF14 钓鱼 GP(采集力)系统 (Step 4.5)
------------------------------------------------------------
GP 随真实时间慢慢回; 普通抛竿免费; 特殊动作花 GP 提高稀有鱼几率;
喝药(Cordial)回 GP 但有冷却。关游戏再开也按真实时钟续算。

★ 想调手感, 改下面这几个数就行 ★
"""

from __future__ import annotations

# ===== 数值(随便调) =========================================
GP_MAX = 400            # GP 上限
GP_REGEN_AMOUNT = 5     # 每次回多少
GP_REGEN_EVERY = 3      # 每多少秒回一次  (→ 每3秒+5)

CORDIAL_RESTORE = 150   # 喝药回多少 GP
CORDIAL_CD = 240        # 喝药冷却(秒)

HOOKSET_COST = 50   # 精准/强力提钩(原作同款: 50 GP)
IDENTICAL_COST = 350  # 专一垂钓(原作为渔师之魂系技能, GP 转译)
SLAP_COST = 150       # 拍击水面(同上)
DH_COST = 400         # 双重提钩(原作同款)
TH_COST = 700         # 三重提钩(原作同款)
PATIENCE_COST = 200     # 耐心: 花 GP, 大幅提高稀有鱼权重
FISHEYES_COST = 200     # 鱼眼: 花 GP, 本次无视时段限制(天气仍需满足)
CHUM_COST = 100         # 撒饵: 花 GP, 下一竿 HQ 概率翻倍
PRIZE_COST = 200        # 大鱼确保(岸钓): 花 GP, 下一竿只钓 Heavy/Legendary
# ===========================================================


def max_gp(state: dict, now: float = None) -> int:
    """GP 上限 = 基础 GP_MAX + 装备采集力 + 食物采集力加成。"""
    try:
        from . import equipment as _eq
        from . import food as _food
    except ImportError:
        import equipment as _eq
        import food as _food
    if now is None:
        import time as _t
        now = _t.time()
    return GP_MAX + _eq.gp_bonus(state) + _food.gp_bonus(state, now)


def sync(state: dict, now: float) -> None:
    """按真实时间把 GP 往上回; 原地修改 state。"""
    last = state.get("gp_at", now)
    ticks = int((now - last) // GP_REGEN_EVERY)
    if ticks > 0:
        cap = max_gp(state, now)
        state["gp"] = min(cap, state.get("gp", cap) + ticks * GP_REGEN_AMOUNT)
        state["gp_at"] = last + ticks * GP_REGEN_EVERY     # 留余数, 不丢零头


def cordial_ready(state: dict, now: float) -> bool:
    return now - state.get("cordial_at", 0) >= CORDIAL_CD


def cordial_remaining(state: dict, now: float) -> int:
    return max(0, int(CORDIAL_CD - (now - state.get("cordial_at", 0))))


def bar(gp: int, cap: int = GP_MAX, width: int = 20) -> str:
    cap = max(1, cap)
    gp = max(0, min(cap, gp))
    filled = int(round(gp / cap * width))
    return "█" * filled + "░" * (width - filled)
