"""
开窗判定自动校验 (Step 3)
跑法:  cd ff14-fishing && python3 tests/test_window.py
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from engine.fish import FISH, get
from engine.window import is_catchable, next_window, catchable_now, _in_time_window
from engine.time_kernel import eorzea_time

T = 1_700_000_000   # 固定锚点 (ET 21:42)


def test_window():
    # 1) is_catchable 对每条鱼都返回布尔, 不抛错
    for f in FISH:
        assert isinstance(is_catchable(f, T), bool)

    # 2) 锚点回归: 此刻开窗数固定 (变了说明判定逻辑被动过)
    assert len(catchable_now(T)) == 1755

    # 3) next_window 边界正确: 返回时刻可钓, 前 1 秒不可钓; 且落在鱼的时段
    mahi = get("Mahi-Mahi")
    nw = next_window(mahi, T)
    assert is_catchable(mahi, nw) and not is_catchable(mahi, nw - 1)
    et = eorzea_time(nw)
    assert (et.hour, et.minute) == (10, 0)

    # 4) 跨午夜时段判定 (如 23:30–01:05)
    assert _in_time_window(0.5, 23.5, 1.0833)     # 00:30 在窗内
    assert _in_time_window(23.9, 23.5, 1.0833)    # 23:54 在窗内
    assert not _in_time_window(12.0, 23.5, 1.0833)  # 12:00 不在窗内

    # 5) 确定性
    assert is_catchable(mahi, T) == is_catchable(mahi, T)

    print(f"OK: 开窗判定全部校验通过 ✔  (锚点此刻 {len(catchable_now(T))} 条开窗)")


