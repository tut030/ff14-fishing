"""
鱼数据/模块自动校验 (Step 2)
跑法:  cd ff14-fishing && python3 tests/test_fish.py
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from engine.fish import FISH, get, by_location, describe, time_text


def test_fish():
    # 1) 有鱼, 且每条都带必需字段
    assert len(FISH) > 0, "没读到鱼"
    need = {"name", "location", "startHour", "endHour",
            "weatherSet", "previousWeatherSet", "predators", "bait"}
    for f in FISH:
        assert need <= set(f), f"{f.get('name')} 缺字段"
        assert 0 <= f["startHour"] <= 24 and 0 <= f["endHour"] <= 24
        # 文案占位已合并进来
        assert "flavor" in f and "names" in f and "id" in f
        assert f["names"].get("en")

    # 2) describe 对每条鱼都能跑通(不抛错)
    for f in FISH:
        assert isinstance(describe(f), str)

    # 3) 锚点回归: 这条鱼的时段若变了, 说明数据被动过
    mahi = get("Mahi-Mahi")
    assert mahi is not None and (mahi["startHour"], mahi["endHour"]) == (10, 18)

    # 4) 文案小检查
    assert time_text(0, 24) == "全天"
    assert "ET" in time_text(10, 18)

    # 5) 按钓场查能拿到东西
    assert len(by_location("Costa del Sol")) > 0

    # 多语言名: 已从 items.json 填入(如 Mahi-Mahi 有日文名)
    mahi = get("Mahi-Mahi")
    assert mahi["names"].get("ja"), "应已填多语言名"
    # 常见杂鱼: 已补充(低级钓场不再只有 1 条)
    assert any(f.get("common") for f in FISH), "应有 common 常见鱼"
    assert len(by_location("West Agelyss River")) >= 3, "低级钓场应已丰富"

    print(f"OK: 鱼模块全部校验通过 ✔  (共 {len(FISH)} 条鱼)")


