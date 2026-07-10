"""
时间内核自动校验 (Step 1a)
跑法:  cd ff14-fishing && python3 tests/test_time_kernel.py
作用:  改动引擎后跑一遍, 立刻知道时间/天气内核有没有被改坏。
"""
import sys
import pathlib

# 把项目根目录加进导入路径
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from engine.time_kernel import (
    eorzea_time, forecast_target, weather_window_start,
    upcoming_targets, _WEATHER_SPAN,
)


def test_time_kernel():
    # 1) 确定性 + 锚点回归: 这个数将来若变了, 说明算法被动过
    assert forecast_target(1_700_000_000) == 53
    assert forecast_target(1_700_000_000) == forecast_target(1_700_000_000)

    # 2) ET 必须落在合法范围
    et = eorzea_time(1_700_000_000)
    assert 0 <= et.hour <= 23 and 0 <= et.minute <= 59

    # 3) 天气窗口起点: 是窗口长度的整数倍, 且不晚于该时刻
    t = 1_700_000_000
    start = weather_window_start(t)
    assert start % _WEATHER_SPAN == 0 and start <= t

    # 4) 预测值恒在 0-99
    for _, tgt in upcoming_targets(20, t):
        assert 0 <= tgt <= 99



