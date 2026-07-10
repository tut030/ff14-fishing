"""
FF14 钓鱼 升级系统
------------------------------------------------------------
玩家有钓鱼等级(1-100)和经验。钓到鱼给经验, 够了就升级。
钓场有等级门槛: 等级不够去不了高级钓场(见 game.py 的 cast 拦截)。

经验曲线基于 FF14 官方 ParamGrow.csv (ExpToNext), 压缩到文字游戏友好的节奏:
  低级(1-40):  ~8-15 竿/级   新手友好
  中级(40-55): ~15-30 竿/级  渐入佳境, Lv50→55 有断崖(官方扩展包入口)
  高级(55-80): ~30-67 竿/级  要肝, 海钓是主力练级手段
  终局(80-100):~80-133 竿/级 苦修, 真正的钓鱼佬才能走完

★ 想调升级节奏, 改 _COMPRESS 函数的指数和系数 ★
"""

from __future__ import annotations

LEVEL_CAP = 100

# FF14 官方每级升级经验 (ParamGrow.csv, Lv1-100 的 ExpToNext)
_OFFICIAL_XP = [
    100, 300, 450, 630, 970, 1440, 1940, 3000, 3920, 4970,
    5900, 7430, 8620, 10200, 11300, 13100, 15200, 17400, 19600, 21900,
    24300, 27400, 30600, 33900, 37300, 40800, 49200, 54600, 61900, 65600,
    68400, 74000, 82700, 88700, 95000, 102000, 113000, 121000, 133000, 142000,
    155000, 163000, 171000, 179000, 187000, 195000, 214000, 229000, 244000, 259000,
    421000, 500000, 580000, 663000, 749000, 837000, 927000, 1019000, 1114000, 1211000,
    1387000, 1456000, 1534000, 1621000, 1720000, 1834000, 1968000, 2126000, 2317000, 2550000,
    2923000, 3018000, 3153000, 3324000, 3532000, 3770600, 4066000, 4377000, 4777000, 5256000,
    5992000, 6171000, 6942000, 7205000, 7948000, 8287000, 9231000, 9529000, 10459000, 10838000,
    13278000, 13659000, 15348000, 15912000, 17534000, 18263000, 20322000, 20957000, 22979000, 23789000,
]


def _compress(official: int) -> int:
    """压缩官方经验值到文字游戏友好的范围。
    公式: max(60, official^0.6 × 1.5)
    保留了官方曲线的"形状"(Lv50→55 断崖), 同时压缩约 100-600 倍。"""
    return max(60, int(official ** 0.6 * 1.5))


def xp_to_next(level: int) -> int:
    """从 level 升到 level+1 需要多少经验。基于官方曲线压缩。"""
    if level < 1:
        return 60
    if level > LEVEL_CAP:
        return 99999
    idx = level - 1
    if idx < len(_OFFICIAL_XP):
        return _compress(_OFFICIAL_XP[idx])
    return _compress(_OFFICIAL_XP[-1])


def xp_gain(fish_level, player_level: int) -> int:
    """钓到一条鱼给多少经验。高级鱼给得多; 远低于自己等级的给得少。"""
    fl = fish_level or 1
    g = max(4, fl * 3)
    if fl <= player_level - 10:
        g = max(1, g // 3)
    return g


def add_xp(state: dict, amount: int) -> list:
    """加经验并处理连续升级; 返回这次升到的新等级列表(可能多级)。"""
    gained = []
    state["xp"] = state.get("xp", 0) + amount
    while state.get("level", 1) < LEVEL_CAP and state["xp"] >= xp_to_next(state["level"]):
        state["xp"] -= xp_to_next(state["level"])
        state["level"] = state.get("level", 1) + 1
        gained.append(state["level"])
    if state.get("level", 1) >= LEVEL_CAP:
        state["xp"] = 0
    return gained
