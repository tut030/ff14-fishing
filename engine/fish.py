"""
FF14 鱼模块 (Step 2) —— 拉诺西亚
------------------------------------------------------------
读取 data/fish_la_noscea.json, 提供:
  - FISH            : 全部鱼(列表)
  - by_location(区) : 某钓场的鱼
  - get(名字)       : 按名字找一条鱼
  - describe(鱼)    : 把这条鱼的开窗条件翻成中文一段话

注意: 这一步只"描述"条件, 还不判断此刻能不能钓(那是 Step 3)。
数据来源: data/fish_la_noscea.json (由 tools/build_fish_data.py 生成)
"""

from __future__ import annotations
import json
from pathlib import Path

try:
    from .weather import WEATHER_NAMES
except ImportError:
    from weather import WEATHER_NAMES

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "fish.json"
_TEXT_PATH = Path(__file__).resolve().parent.parent / "data" / "fish_text.json"

# 英文天气名 -> 中文 (取自 weather 模块)
_EN2CN = {en: cn for (en, _ja, cn) in WEATHER_NAMES.values()}


def _load():
    fish = json.loads(_DATA_PATH.read_text(encoding="utf-8"))["fish"]
    # 合并文案文件(身份/多语言名/官方图鉴/手写 flavor); 没有就用空值
    text = {}
    if _TEXT_PATH.exists():
        text = json.loads(_TEXT_PATH.read_text(encoding="utf-8")).get("fish", {})
    for f in fish:
        # ── tug 大小写统一: "light"→"Light", "medium"→"Medium", "heavy"→"Heavy" ──
        # fish.json 里混着大小写, 全部统一成首字母大写, 下游 _TUG_WEIGHT 等不用管了
        if f.get("tug"):
            f["tug"] = f["tug"].capitalize()
        t = text.get(f["name"], {})
        f["id"] = t.get("id")
        f["names"] = t.get("names") or {"en": f["name"]}
        f["desc_official"] = t.get("desc_official") or {}
        f["flavor"] = t.get("flavor") or ""
        f["flavor_en"] = t.get("flavor_en") or ""
        # —— 显示名修订层: cn_fix/en_fix 覆盖显示名, 官方原名保留为可搜别名 ——
        cn_fix = t.get("cn_fix") or ""
        en_fix = t.get("en_fix") or ""
        if cn_fix:
            f["cn_alias"] = f["names"].get("cn") or ""
            f["names"]["cn"] = cn_fix
        if en_fix:
            f["en_alias"] = f["name"]          # SE 原始英文名 → 别名(仍可搜)
            f["names"]["en"] = en_fix
    return fish


FISH = _load()


def by_location(location: str) -> list:
    return [f for f in FISH if f["location"].lower() == location.lower()]


_NAME_INDEX = None


def _build_name_index():
    global _NAME_INDEX
    _NAME_INDEX = {}
    for f in FISH:
        _NAME_INDEX.setdefault(f["name"].lower(), f)
        for v in (f.get("names") or {}).values():
            if v:
                _NAME_INDEX.setdefault(str(v).lower(), f)
        # 修订前的原名也要能搜到(cn_alias=国服原名, en_alias=SE原名)
        for alias_key in ("cn_alias", "en_alias"):
            alias = f.get(alias_key)
            if alias:
                _NAME_INDEX.setdefault(alias.lower(), f)


def get(name: str):
    """按 英文名 / 中文名 / 日文名 / "中文/English" 组合 查鱼。"""
    if not name:
        return None
    if _NAME_INDEX is None:
        _build_name_index()
    q = name.strip().lower()
    if q in _NAME_INDEX:
        return _NAME_INDEX[q]
    if "/" in q:                     # 处理 look/bag 里 "中文/English" 形式
        for part in q.split("/"):
            part = part.strip()
            if part in _NAME_INDEX:
                return _NAME_INDEX[part]
    return None


def get_all(name: str) -> list:
    """同名鱼的全部记录(同一条鱼在多个钓点各有一条记录)。
    真实游戏图鉴按鱼算一条, 但窗口/等级按钓点各不同 —— status 聚合用。"""
    f = get(name)
    if not f:
        return []
    return [x for x in FISH if x["name"] == f["name"]]


def _w(names: list) -> str:
    """一组英文天气名 -> '碧空/小雨' 这样的中文串。"""
    return "/".join(_EN2CN.get(n, n) for n in names)


def _hm(h) -> str:
    """小时(可能带小数) -> 'HH:MM'。18.5 -> '18:30'。"""
    h = float(h)
    H = int(h)
    M = int(round((h - H) * 60))
    if M == 60:
        H, M = H + 1, 0
    return f"{H:02d}:{M:02d}"


def time_text(start, end) -> str:
    if (float(start), float(end)) in [(0.0, 24.0), (0.0, 0.0)]:
        return "全天"
    return f"ET {_hm(start)}–{_hm(end)}"


def describe(fish: dict) -> str:
    """把一条鱼的条件翻成中文一段话。"""
    cn = (fish.get("names") or {}).get("cn")
    title = f"{cn} / {fish['name']}" if cn else fish["name"]
    lines = [f"🐟 {title}  @ {fish['location']}"]
    lines.append(f"   时段: {time_text(fish['startHour'], fish['endHour'])}")
    if fish["weatherSet"]:
        lines.append(f"   天气: {_w(fish['weatherSet'])}")
    if fish["previousWeatherSet"]:
        lines.append(f"   前置天气(上一时段需是): {_w(fish['previousWeatherSet'])}")
    if fish["predators"]:
        chain = "、".join(f"{k}×{v}" for k, v in fish["predators"].items())
        lines.append(f"   拟饵链(需先钓): {chain}")
    if fish["bait"]:
        flat = []
        for b in fish["bait"]:
            if isinstance(b, list):
                flat.append("(" + "/".join(map(str, b)) + ")")
            else:
                flat.append(str(b))
        lines.append(f"   鱼饵/路径: {' → '.join(flat)}")
    flags = []
    if fish["fishEyes"]:
        flags.append("需鱼眼")
    if fish["folklore"]:
        flags.append("需鱼类学指南")
    if flags:
        lines.append(f"   额外: {'、'.join(flags)}")
    official = (fish.get("desc_official") or {}).get("cn")
    if official:
        lines.append(f"   📖 {official}")
    if fish.get("flavor"):
        lines.append(f"   ✍ {fish['flavor']}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(f"拉诺西亚共 {len(FISH)} 条鱼\n")

    print("=== 某钓场(Costa del Sol)的鱼 ===")
    for f in by_location("Costa del Sol"):
        print(f"  - {f['name']}")

    print("\n=== 举例描述: 一条普通鱼 ===")
    print(describe(get("Nautilus")))

    print("\n=== 举例描述: 一条卡时段的鱼 ===")
    print(describe(get("Mahi-Mahi")))

    print("\n=== 举例描述: 一条带拟饵链的鱼 ===")
    moocher = next((f for f in FISH if f["predators"]), None)
    if moocher:
        print(describe(moocher))
