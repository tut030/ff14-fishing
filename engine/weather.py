"""
FF14 天气模块 (数据驱动版)
------------------------------------------------------------
从 data/weather.json 读各区天气概率表, 把"天气预测值(0-99)"翻成具体天气。
做法: 每区一张 [[天气id, 累积上限], ...] (累积到100), 取第一个 预测值<上限 的天气。

天气数据来源: data/weather.json (由 tools/build_weather_data.py 生成)
算法与 Fish Tracker 一致, 输出 = 该站显示的天气。
中文天气名在本文件维护(国际版客户端无中文)。
"""

from __future__ import annotations
import json
import time
from pathlib import Path

try:
    from .time_kernel import forecast_target, eorzea_time, weather_window_start, _WEATHER_SPAN
except ImportError:
    from time_kernel import forecast_target, eorzea_time, weather_window_start, _WEATHER_SPAN

_W_PATH = Path(__file__).resolve().parent.parent / "data" / "weather.json"
_W = json.loads(_W_PATH.read_text(encoding="utf-8"))

# 区域名 -> 概率表
WEATHER_RATES = {zone: info["rates"] for zone, info in _W["zones"].items()}
ZONES = list(WEATHER_RATES)
# 区域名 -> 所属大区
ZONE_REGION = {zone: info.get("region", "") for zone, info in _W["zones"].items()}

# 天气 id -> 英/日 (来自数据文件)
_W_EN = {int(k): v["en"] for k, v in _W["weather_types"].items()}
_W_JA = {int(k): v.get("ja", "") for k, v in _W["weather_types"].items()}

# 天气 id -> 中文 (本文件维护; 多备几个以防扩区域)
WEATHER_CN = {
    1: "碧空", 2: "晴朗", 3: "阴云", 4: "薄雾", 5: "微风", 6: "强风",
    7: "小雨", 8: "暴雨", 9: "打雷", 10: "雷雨", 11: "扬沙", 14: "热浪",
    15: "降雪", 16: "暴雪", 17: "殀雾", 49: "灵风",
    # 50/148/149 等罕见天气暂用英文名(拿不准的不硬译)
}

# 兼容旧接口: id -> (en, ja, cn)
WEATHER_NAMES = {i: (_W_EN[i], _W_JA.get(i, ""), WEATHER_CN.get(i, _W_EN[i])) for i in _W_EN}
# 英文名 -> 中文 (给鱼模块翻译 weatherSet 用)
EN2CN = {en: WEATHER_CN.get(i, en) for i, en in _W_EN.items()}


def _resolve(zone: str) -> str:
    for z in WEATHER_RATES:
        if z.lower() == zone.lower():
            return z
    raise KeyError(f"未知区域: {zone!r}")


def weather_name(weather_id: int, lang: str = "cn") -> str:
    names = WEATHER_NAMES.get(weather_id)
    if names is None:
        return f"#{weather_id}"
    return {"en": names[0], "ja": names[1], "cn": names[2]}.get(lang, names[0])


def weather_id_at(zone: str, target: int) -> int:
    rates = WEATHER_RATES[_resolve(zone)]
    for wid, upper in rates:
        if target < upper:
            return wid
    return rates[-1][0]


def current_weather(zone: str, unix_seconds: float | None = None, lang: str = "cn") -> str:
    if unix_seconds is None:
        unix_seconds = time.time()
    return weather_name(weather_id_at(zone, forecast_target(unix_seconds)), lang)


def forecast(zone: str, count: int = 8, unix_seconds: float | None = None, lang: str = "cn"):
    zone = _resolve(zone)
    start = weather_window_start(unix_seconds)
    out = []
    for i in range(count):
        t = start + i * _WEATHER_SPAN
        out.append((t, eorzea_time(t), weather_name(weather_id_at(zone, forecast_target(t)), lang)))
    return out


if __name__ == "__main__":
    now = time.time()
    print(f"共 {len(ZONES)} 个天气区\n各区此刻天气:")
    last = None
    for z in sorted(ZONES, key=lambda x: (ZONE_REGION[x], x)):
        if ZONE_REGION[z] != last:
            last = ZONE_REGION[z]
            print(f"  【{last}】")
        print(f"     {current_weather(z, now):<4} {z}")
