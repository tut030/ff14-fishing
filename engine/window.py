"""
FF14 开窗判定 (Step 3) —— 拉诺西亚
------------------------------------------------------------
把"鱼的开窗条件"接上"此刻真实的 ET + 天气", 回答:
  - 这条鱼现在能不能钓?
  - 不能的话, 下一个窗口什么时候开?

判定三关(全过才算开窗):
  1) 现在 ET 落在鱼的时段 [startHour, endHour) 内
  2) 当前天气 ∈ 鱼要求的 weatherSet (空=不限)
  3) 上一时段天气 ∈ 鱼要求的 previousWeatherSet (空=不限)

数据/算法来源: 时间内核(time_kernel) + 天气表(weather) + 鱼表(fish)
"""

from __future__ import annotations
import time

try:
    from .time_kernel import eorzea_time, weather_window_start, _WEATHER_SPAN
    from .weather import current_weather, weather_id_at, weather_name, WEATHER_NAMES
    from .fish import FISH, get, describe, time_text, _w
    from .time_kernel import forecast_target
except ImportError:
    from time_kernel import eorzea_time, weather_window_start, _WEATHER_SPAN, forecast_target
    from weather import current_weather, weather_id_at, weather_name, WEATHER_NAMES
    from fish import FISH, get, describe, time_text, _w

# 中文天气名 -> 英文名 (鱼数据里的 weatherSet 用英文)
_CN2EN = {cn: en for (en, _ja, cn) in WEATHER_NAMES.values()}
_EN_SET = {en for (en, _ja, _cn) in WEATHER_NAMES.values()}


def _et_hours(unix_seconds: float) -> float:
    et = eorzea_time(unix_seconds)
    return et.hour + et.minute / 60


def _in_time_window(h: float, start: float, end: float) -> bool:
    if (start, end) in [(0.0, 24.0), (0.0, 0.0)]:
        return True
    if start <= end:
        return start <= h < end
    return h >= start or h < end          # 跨午夜, 如 23:30–01:05


def _weather_en_at(zone: str, unix_seconds: float) -> str:
    """某区某刻的天气, 返回英文名(好和鱼数据比对)。"""
    return weather_name(weather_id_at(zone, forecast_target(unix_seconds)), "en")


def is_catchable(fish: dict, unix_seconds: float | None = None,
                 ignore_time: bool = False) -> bool:
    """这条鱼此刻(或指定时刻)是否开窗。ignore_time=True 时跳过时段判定(鱼眼)。"""
    if unix_seconds is None:
        unix_seconds = time.time()
    zone = fish["zone"]
    # 关卡1: 时段 (鱼眼可跳过)
    if not ignore_time:
        if not _in_time_window(_et_hours(unix_seconds), fish["startHour"], fish["endHour"]):
            return False
    # 关卡2: 当前天气
    if fish["weatherSet"]:
        if _weather_en_at(zone, unix_seconds) not in set(fish["weatherSet"]):
            return False
    # 关卡3: 前置天气(上一个天气窗口)
    if fish["previousWeatherSet"]:
        prev_t = weather_window_start(unix_seconds) - _WEATHER_SPAN
        if _weather_en_at(zone, prev_t) not in set(fish["previousWeatherSet"]):
            return False
    return True


def next_window(fish: dict, unix_seconds: float | None = None, horizon_et_days: int = 40):
    """
    找下一个开窗时刻(现实 unix 秒); 在 horizon_et_days 个 ET 天内找不到则 None。
    做法: 以约 10 ET 分的细步长线性扫描, 命中后二分卡到精确开点。
    对"卡时段""卡天气""两者皆卡"的鱼都准确。
    """
    if unix_seconds is None:
        unix_seconds = time.time()
    base = int(unix_seconds)
    step = 30                                   # 现实秒, ≈10 ET 分
    horizon = int(horizon_et_days * 4200)       # 1 ET 天 = 4200 现实秒
    t = base
    while t <= base + horizon:
        if is_catchable(fish, t):
            # 二分: 在 (t-step, t] 里卡到刚开窗的那一刻
            lo, hi = max(base, t - step), t
            while lo < hi:
                mid = (lo + hi) // 2
                if is_catchable(fish, mid):
                    hi = mid
                else:
                    lo = mid + 1
            return lo
        t += step
    return None


def status_text(fish: dict, unix_seconds: float | None = None) -> str:
    """一句话说清这条鱼此刻状态。"""
    if unix_seconds is None:
        unix_seconds = time.time()
    if is_catchable(fish, unix_seconds):
        return f"✅ 现在能钓!  ({fish['name']} @ {fish['location']})"
    nxt = next_window(fish, unix_seconds)
    if nxt is None:
        return f"❌ 暂不可钓 ({fish['name']})，近期没算到窗口"
    # 还要多久(现实时间)
    mins = int((nxt - unix_seconds) / 60)
    et = eorzea_time(nxt)
    when = f"{mins} 分钟后" if mins > 0 else "马上"
    return (f"❌ 现在钓不到 {fish['name']}\n"
            f"   下一个窗口: {when}(现实) / 游戏 {et} 开\n"
            f"   条件: {time_text(fish['startHour'], fish['endHour'])}"
            + (f" + {_w(fish['weatherSet'])}" if fish['weatherSet'] else ""))


def catchable_now(unix_seconds: float | None = None) -> list:
    """此刻所有开窗的鱼。"""
    if unix_seconds is None:
        unix_seconds = time.time()
    return [f for f in FISH if is_catchable(f, unix_seconds)]


if __name__ == "__main__":
    now = time.time()
    print(f"现在: 游戏 {eorzea_time(now)}\n")

    print("=== 此刻拉诺西亚能钓的鱼 ===")
    now_fish = catchable_now(now)
    for f in now_fish[:15]:
        w = current_weather(f["zone"], now)
        print(f"  ✅ {f['name']:<22} @ {f['location']}  ({f['zone']} {w})")
    print(f"  ... 共 {len(now_fish)} 条开窗\n")

    print("=== 挑几条具体看状态 ===")
    for name in ["Mahi-Mahi", "Thundergut", "Cupfish", "The Captain's Chalice"]:
        f = get(name)
        if f:
            print(status_text(f, now))
            print()
