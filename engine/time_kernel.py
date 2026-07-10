"""
FF14 时间内核 (Step 1a)
------------------------------------------------------------
把"现实时间"换算成两样东西:
  1) 艾欧泽亚时间 ET —— 游戏内的钟 (时:分)
  2) 天气预测目标值 forecast_target (0-99) —— 决定天气的那个确定性数字

特点: 只用标准库、纯函数、零联网。
      同一个 unix 时间戳 -> 永远算出同一组结果 (确定性)。
算法来源: 社区/SaintCoinach 通用实现, 与游戏一致。
"""

from __future__ import annotations
import time
from dataclasses import dataclass

# --- 常量 --------------------------------------------------
# 1 ET 小时 = 175 现实秒;  1 ET 整天(24h) = 4200 现实秒(=70 分钟)
_REAL_PER_ET_HOUR = 175
_REAL_PER_ET_DAY = 4200
_U32 = 0xFFFFFFFF          # 模拟 32 位无符号运算, 与游戏/社区实现对齐
_WEATHER_SPAN = 175 * 8    # 天气每 8 ET 小时换一次 = 1400 现实秒 (23分20秒)


@dataclass(frozen=True)
class EorzeaTime:
    hour: int      # 0-23
    minute: int    # 0-59

    def __str__(self) -> str:
        return f"{self.hour:02d}:{self.minute:02d} ET"


def eorzea_time(unix_seconds: float | None = None) -> EorzeaTime:
    """现实 unix 秒 -> 艾欧泽亚时间。不传则取此刻。"""
    if unix_seconds is None:
        unix_seconds = time.time()
    et_seconds = int(unix_seconds * 3600 / _REAL_PER_ET_HOUR)  # ≈ ×20.5714
    return EorzeaTime((et_seconds // 3600) % 24, (et_seconds // 60) % 60)


def forecast_target(unix_seconds: float | None = None) -> int:
    """
    现实 unix 秒 -> 天气预测目标值 (0-99)。
    FF14 天气每 8 ET 小时(=23分20秒现实)一个窗口, 每窗口算一个 0-99 的数,
    再用"区域天气概率表"把这个数翻译成具体天气(那张表在 Step 1b 插进来)。
    """
    if unix_seconds is None:
        unix_seconds = time.time()
    epoch = int(unix_seconds)
    bell = epoch // _REAL_PER_ET_HOUR
    inc = (bell + 8 - (bell % 8)) % 24
    days = (epoch // _REAL_PER_ET_DAY) & _U32
    base = (days * 100 + inc) & _U32
    s1 = (((base << 11) & _U32) ^ base) & _U32
    s2 = ((s1 >> 8) ^ s1) & _U32
    return s2 % 100


def weather_window_start(unix_seconds: float | None = None) -> int:
    """当前天气窗口的起始现实 unix 秒 (做倒计时/找下一个窗口用)。"""
    if unix_seconds is None:
        unix_seconds = time.time()
    return (int(unix_seconds) // _WEATHER_SPAN) * _WEATHER_SPAN


def upcoming_targets(count: int = 8, unix_seconds: float | None = None):
    """返回从当前窗口起、往后 count 个窗口的 (窗口起始unix, 预测值)。"""
    start = weather_window_start(unix_seconds)
    return [(start + i * _WEATHER_SPAN, forecast_target(start + i * _WEATHER_SPAN))
            for i in range(count)]


if __name__ == "__main__":
    now = time.time()
    print("现实时间 (unix):", int(now))
    print("艾欧泽亚时间   :", eorzea_time(now))
    print("天气预测目标值 :", forecast_target(now), "(0-99)")
    print("\n接下来 8 个天气窗口 (每个 23分20秒):")
    for i, (t, tgt) in enumerate(upcoming_targets(8, now)):
        print(f"  +{i}  目标值={tgt:2d}   窗口起 unix={t}")

    # 确定性自证: 同一个时间戳算两次, 结果必须一致
    fixed = 1_700_000_000
    assert forecast_target(fixed) == forecast_target(fixed)
    print(f"\n确定性校验: forecast_target({fixed}) = {forecast_target(fixed)} (重复调用恒定)")
