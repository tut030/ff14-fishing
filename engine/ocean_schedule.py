"""
海钓班次内核 (Ocean Fishing Schedule · 与国际服现役班次同步)
------------------------------------------------------------
把"现实时间"换算成海钓班次:
  1) 每 2 现实小时一班船 (锚定 Unix 纪元), 每班同时有两条航路可选:
     灵青航路(indigo, 12 种班型) / 红玉航路(ruby, 9 种班型)
  2) 每班开头 15 分钟是登船窗口, 错过等下一班 (与真实一致)
  3) 航线 = PATTERN[(发船槽 + 偏移) % 144], 排班表来自 data/ocean_pattern.json,
     由 tools/build_ocean_pattern.py 生成并经双重交叉验证 ——
     与此刻现实 FF14 国际服的班次是同一张表。

特点: 只用标准库、纯函数、零联网 (排班表在本地数据文件里)。
      同一个 unix 时间戳 -> 永远算出同一班船 (确定性, 全世界一致)。
"""

from __future__ import annotations
import json
import time
from dataclasses import dataclass
from pathlib import Path

# --- 常量 --------------------------------------------------
VOYAGE_SPAN = 2 * 60 * 60      # 一班船占据的现实秒数 (2小时)
BOARDING_WINDOW = 15 * 60      # 每班开头的登船窗口 (15分钟), 与真实一致
LINES = ("indigo", "ruby")     # 两条航路

_PATTERN_FILE = Path(__file__).resolve().parent.parent / "data" / "ocean_pattern.json"
_cache: dict | None = None


def _tables() -> dict:
    """加载排班表 (仅首次读盘)。"""
    global _cache
    if _cache is None:
        _cache = json.loads(_PATTERN_FILE.read_text(encoding="utf-8"))
    return _cache


def line_name(line: str) -> str:
    """航路显示名, 如 indigo -> 灵青航路。"""
    return _tables()["line_names"][line]


@dataclass(frozen=True)
class Voyage:
    slot_start: int        # 本班船的起始 unix 秒 (登船窗口开门时刻)
    routes: tuple          # ((航路, 航线键), ...) 两条航路本班各开哪条航线

    @property
    def boarding_end(self) -> int:
        """登船窗口关闭时刻 (unix 秒), 到点即发船。"""
        return self.slot_start + BOARDING_WINDOW

    def route_key(self, line: str) -> str:
        return dict(self.routes)[line]


def slot_start(unix_seconds: float | None = None) -> int:
    """现实 unix 秒 -> 所在班次的起始 unix 秒 (2小时对齐)。"""
    if unix_seconds is None:
        unix_seconds = time.time()
    return (int(unix_seconds) // VOYAGE_SPAN) * VOYAGE_SPAN


def route_key_at(line: str, unix_seconds: float | None = None) -> str:
    """现实 unix 秒 + 航路 -> 该班次的航线键 (确定性, 与现实服一致)。"""
    t = _tables()["lines"][line]
    k = slot_start(unix_seconds) // VOYAGE_SPAN
    return t["pattern"][(k + t["offset"]) % len(t["pattern"])]


def current_voyage(unix_seconds: float | None = None) -> Voyage:
    """此刻所在班次 (无论登船窗口是否已关), 含两条航路各自的航线。"""
    start = slot_start(unix_seconds)
    return Voyage(start, tuple((ln, route_key_at(ln, start)) for ln in LINES))


def boarding_open(unix_seconds: float | None = None) -> bool:
    """此刻能不能登船 (在本班次的前 15 分钟内)。"""
    if unix_seconds is None:
        unix_seconds = time.time()
    return int(unix_seconds) - slot_start(unix_seconds) < BOARDING_WINDOW


def next_boarding(unix_seconds: float | None = None) -> Voyage:
    """下一个可登船的班次: 窗口还开着算本班, 否则是下一班。"""
    if unix_seconds is None:
        unix_seconds = time.time()
    if boarding_open(unix_seconds):
        return current_voyage(unix_seconds)
    return current_voyage(slot_start(unix_seconds) + VOYAGE_SPAN)


def upcoming_voyages(count: int = 8,
                     unix_seconds: float | None = None) -> list[Voyage]:
    """从当前班次起、往后 count 班的班次表 (做时刻表/蹲鱼倒计时用)。"""
    start = slot_start(unix_seconds)
    return [current_voyage(s)
            for s in range(start, start + count * VOYAGE_SPAN, VOYAGE_SPAN)]


if __name__ == "__main__":
    routes_data = json.loads(
        (Path(__file__).resolve().parent.parent / "data" /
         "ocean_routes.json").read_text(encoding="utf-8"))["routes"]

    def _desc(key: str) -> str:
        r = routes_data[key]
        return f"{r['name']}({r['stops'][-1]['time']}到达)"

    now = time.time()
    v = current_voyage(now)
    print("现实时间 (unix):", int(now))
    print("登船窗口:", "开放中" if boarding_open(now) else "已关闭")
    for ln, key in v.routes:
        print(f"  本班 {line_name(ln)}: {_desc(key)}")
    nb = next_boarding(now)
    wait = nb.slot_start - int(now)
    if wait > 0:
        print(f"下一班还有 {wait // 60} 分 {wait % 60} 秒:")
        for ln, key in nb.routes:
            print(f"  {line_name(ln)}: {_desc(key)}")
    print("\n接下来 6 班 (与现实国际服同步):")
    for vy in upcoming_voyages(6, now):
        pair = " | ".join(f"{line_name(ln)}: {_desc(k)}" for ln, k in vy.routes)
        print(f"  slot={vy.slot_start}  {pair}")
