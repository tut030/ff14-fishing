"""
天气模块自动校验 (Step 1b)
跑法:  cd ff14-fishing && python3 tests/test_weather.py
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from engine.weather import (
    WEATHER_RATES, ZONES, weather_id_at, current_weather, forecast,
)


def test_weather():
    # 1) 每个区的概率表: 上限严格递增, 且末项 <=100
    #    (个别房区如 Empyreum 末项为90, 属游戏数据本身如此; weather_id_at 有兜底)
    for zone, rates in WEATHER_RATES.items():
        uppers = [u for _, u in rates]
        assert uppers == sorted(uppers) and len(set(uppers)) == len(uppers), f"{zone} 上限未严格递增"
        assert 0 < uppers[-1] <= 100, f"{zone} 末项异常"

    # 2) 0-99 任意预测值, 每个区都能落到某个天气
    for zone in ZONES:
        for target in range(100):
            wid = weather_id_at(zone, target)
            assert isinstance(wid, int)

    # 3) 锚点回归: 这个结果若变了, 说明天气表或算法被动过
    assert current_weather("Lower La Noscea", 1_700_000_000, "en") == "Fair Skies"

    # 4) 预报: 数量正确, 且窗口起点 ET 一定落在 8 小时边界(分钟=0, 小时是8的倍数)
    fc = forecast("Limsa Lominsa Lower Decks", 8, 1_700_000_000)
    assert len(fc) == 8
    for _, et, _w in fc:
        assert et.minute == 0 and et.hour % 8 == 0, f"窗口起点 ET 不在边界: {et}"

    # 5) 确定性
    assert current_weather("Outer La Noscea", 1_700_000_000) == current_weather("Outer La Noscea", 1_700_000_000)



