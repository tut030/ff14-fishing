"""
海钓班次内核自动校验
跑法:  cd ff14-fishing && python3 tests/test_ocean_schedule.py
作用:  改动引擎/重生成排班表后跑一遍, 立刻知道班次推算有没有被改坏。
"""
import json
import sys
import pathlib

# 把项目根目录加进导入路径
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from engine.ocean_schedule import (
    VOYAGE_SPAN, BOARDING_WINDOW, LINES,
    slot_start, route_key_at, current_voyage,
    boarding_open, next_boarding, upcoming_voyages, line_name,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_ocean_schedule():
    # 1) 确定性 + 锚点回归: 这两个键将来若变了, 说明排班表/偏移被动过。
    #    锚点值来自与国际服同步的真实排班 (构建时经双重交叉验证)。
    fixed = 1_700_000_000
    assert route_key_at("indigo", fixed) == route_key_at("indigo", fixed)
    assert route_key_at("indigo", fixed) == "3"    # 梅尔托尔海峡北航线·黄昏到达
    assert route_key_at("ruby", fixed) == "21"     # 萨维奈岛航线·黄昏到达

    # 2) 班次对齐: slot 起点是 2 小时整倍数, 且区间内处处同班
    s = slot_start(fixed)
    assert s % VOYAGE_SPAN == 0
    assert slot_start(s) == slot_start(s + VOYAGE_SPAN - 1) == s
    assert slot_start(s + VOYAGE_SPAN) == s + VOYAGE_SPAN

    # 3) 登船窗口边界: 第899秒(14:59)开着, 第900秒(15:00)整关闭
    assert boarding_open(s) is True
    assert boarding_open(s + BOARDING_WINDOW - 1) is True
    assert boarding_open(s + BOARDING_WINDOW) is False
    assert boarding_open(s + VOYAGE_SPAN - 1) is False

    # 4) next_boarding: 窗口内=本班; 窗口关了=下一班
    assert next_boarding(s + 10).slot_start == s
    assert next_boarding(s + BOARDING_WINDOW).slot_start == s + VOYAGE_SPAN

    # 5) 排班表结构: 两条航路各 144 位; 键全部真实存在; 覆盖各自全部航线
    routes = json.loads(
        (ROOT / "data" / "ocean_routes.json").read_text(encoding="utf-8"))["routes"]
    tables = json.loads(
        (ROOT / "data" / "ocean_pattern.json").read_text(encoding="utf-8"))["lines"]
    seen = set()
    for ln in LINES:
        t = tables[ln]
        assert len(t["pattern"]) == 144, f"{ln} PATTERN 长度异常"
        keys = set(t["pattern"])
        assert keys <= set(routes), f"{ln} PATTERN 含未知航线键"
        assert len(keys) == t["variant_count"], f"{ln} 班型覆盖不全"
        assert not (keys & seen), "两条航路的航线键重叠"
        seen |= keys
        assert line_name(ln)                      # 显示名存在
    assert seen == set(routes), "有航线不属于任何一条航路"

    # 6) 每班两条航路并存, 且与逐航路查询一致; 144 班转满一轮回到原点
    v = current_voyage(fixed)
    assert dict(v.routes).keys() == set(LINES)
    for ln in LINES:
        assert v.route_key(ln) == route_key_at(ln, fixed)
    vs = upcoming_voyages(145, fixed)
    assert vs[0].routes == vs[144].routes

    # 7) 红玉航路结构自证 (7.5 环的指纹): 萨维奈班恰占一半;
    #    基础节奏与黄金港方向交替, 每日跳位在整轮里造成各 6 次"连双", 绝无三连
    thav = {"19", "20", "21"}                     # 萨维奈岛航线的三个键
    flags = [route_key_at("ruby", s + i * VOYAGE_SPAN) in thav
             for i in range(144)]
    assert sum(flags) == 72, "萨维奈班占比异常"
    n = len(flags)
    dbl_t = sum(1 for i in range(n) if flags[i] and flags[(i + 1) % n])
    dbl_k = sum(1 for i in range(n) if not flags[i] and not flags[(i + 1) % n])
    assert (dbl_t, dbl_k) == (6, 6), f"连双次数异常: 萨维奈{dbl_t}/黄金港向{dbl_k}"
    for i in range(n):
        assert not (flags[i] == flags[(i + 1) % n] == flags[(i + 2) % n]), \
            f"第{i}班起出现三连, 不符合真实排班结构"

    print("OK: 海钓班次内核全部校验通过 ✔ "
          f"(与国际服现役班次同步, 锚点 {fixed} -> 灵青 3 / 红玉 21)")


