"""
鱼数据更新脚本 (全地图 + 真实等级 + 常见杂鱼)
============================================================
生成 data/fish.json:
  - 全部大区 (REGIONS = None)
  - 大鱼/值得追的鱼: 来自 Fish Tracker (带时段/天气/拟饵链)
  - 常见杂鱼: 来自 Teamcraft 每个钓场的全鱼列表(标 common, 全天可钓, 竿感轻)
  - 每条鱼带真实钓场等级 level + 物品 id(供填多语言名)
  - 区分 line 钓鱼 / spear 叉鱼

怎么跑:
    cd ff14-fishing
    pip install pyyaml
    python tools/build_fish_data.py

数据来源:
  - icykoneko/ff14-fish-tracker-app : fishData.yaml, data.js
  - ffxiv-teamcraft/ffxiv-teamcraft : fishing-spots.json(等级+全鱼), items.json(名字)
"""

from __future__ import annotations
import json
import re
import urllib.request
from pathlib import Path

FT = "https://raw.githubusercontent.com/icykoneko/ff14-fish-tracker-app/master"
TC = "https://raw.githubusercontent.com/ffxiv-teamcraft/ffxiv-teamcraft/master/libs/data/src/lib/json"
YAML_URL = f"{FT}/private/fishData.yaml"
DATAJS_URL = f"{FT}/js/app/data.js"
TC_SPOTS_URL = f"{TC}/fishing-spots.json"
TC_ITEMS_URL = f"{TC}/items.json"

REGIONS = None    # None = 全部大区

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "data" / "fish.json"


def _fetch(url: str) -> str:
    print(f"  拉取 {url.rsplit('/', 1)[-1]} ...")
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read().decode("utf-8")


def _extract(text: str, key: str) -> dict:
    i = text.index(key + ":")
    i = text.index("{", i)
    depth, j, in_str, esc = 0, i, False, False
    while j < len(text):
        c = text[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[i:j + 1])
        j += 1
    raise ValueError(f"未找到 {key}")


def _to_hours(v) -> float:
    if isinstance(v, str) and ":" in v:
        hh, mm = v.split(":")
        return round(int(hh) + int(mm) / 60, 4)
    return float(v)


def main() -> int:
    try:
        import yaml
    except ImportError:
        print("缺少 PyYAML, 请先: pip install pyyaml")
        return 1

    print("从 GitHub 拉取数据:")
    datajs = _fetch(DATAJS_URL)
    yaml_text = _fetch(YAML_URL)
    tc = json.loads(_fetch(TC_SPOTS_URL))
    items = json.loads(_fetch(TC_ITEMS_URL))

    spots = _extract(datajs, "FISHING_SPOTS")
    spear = _extract(datajs, "SPEARFISHING_SPOTS")
    rates = _extract(datajs, "WEATHER_RATES")
    zones = _extract(datajs, "ZONES")
    regions = _extract(datajs, "REGIONS")

    want = None if REGIONS is None else set(REGIONS)
    terr_zone = {int(k): zones.get(str(v["zone_id"]), {}).get("name_en")
                 for k, v in rates.items() if want is None or v["region_id"] in want}
    terr_region = {int(k): regions.get(str(v["region_id"]), {}).get("name_en", "")
                   for k, v in rates.items() if want is None or v["region_id"] in want}
    tc_level = {s["id"]: s["level"] for s in tc}

    # 物品 id <-> 英文名
    id2en = {int(i): n.get("en") for i, n in items.items() if n.get("en")}
    en2id = {}
    for i, n in items.items():
        en = n.get("en")
        if en:
            en2id.setdefault(en.lower(), int(i))

    def reg(spot_dict, is_spear):
        out = {}
        for s in spot_dict.values():
            if s["territory_id"] not in terr_zone:
                continue
            out[s["name_en"]] = {"id": s["_id"], "terr": s["territory_id"], "spear": is_spear}
        return out
    line_reg = reg(spots, False)
    spear_reg = reg(spear, True)

    # ---- 第1步: Fish Tracker 的大鱼/值得追的鱼 ----
    yaml_text = re.sub(r'(?m)^(\s*(?:startHour|endHour):\s*)(\d{1,2}:\d{2})\s*$',
                       r'\1"\2"', yaml_text)
    all_fish = yaml.safe_load(yaml_text)
    fish, skipped = [], 0
    for f in all_fish:
        loc = f.get("location")
        info = line_reg.get(loc) or spear_reg.get(loc)
        if info is None:
            skipped += 1
            continue
        zone = terr_zone.get(info["terr"])
        if zone is None:
            skipped += 1
            continue
        fish.append({
            "name": f["name"], "location": loc, "zone": zone,
            "region": terr_region.get(info["terr"], ""),
            "mode": "spear" if (info["spear"] or f.get("gig")) else "line",
            "level": tc_level.get(info["id"]),
            "id": en2id.get(f["name"].lower()),
            "startHour": _to_hours(f.get("startHour", 0)),
            "endHour": _to_hours(f.get("endHour", 24)),
            "weatherSet": f.get("weatherSet") or [],
            "previousWeatherSet": f.get("previousWeatherSet") or [],
            "predators": f.get("predators") or {},
            "bait": f.get("bestCatchPath") or [],
            "tug": f.get("tug"), "hookset": f.get("hookset"),
            "snagging": bool(f.get("snagging")), "folklore": bool(f.get("folklore")),
            "fishEyes": bool(f.get("fishEyes")), "gig": f.get("gig"),
            "patch": f.get("patch"), "common": False,
        })
    n_notable = len(fish)

    # ---- 第2步: 常见杂鱼(Teamcraft 每钓场全鱼列表里, 我们还没有的) ----
    have_ids = {f["id"] for f in fish if f.get("id")}
    have_names = {f["name"].lower() for f in fish}
    spot_meta = {s["_id"]: (s["name_en"], s["territory_id"]) for s in spots.values()}
    seen = set()
    for s in tc:
        meta = spot_meta.get(s["id"])
        if not meta:
            continue
        name_en, terr = meta
        zone = terr_zone.get(terr)
        if zone is None:
            continue
        for fid in s["fishes"]:
            if fid in have_ids:
                continue
            en = id2en.get(fid)
            if not en or en.lower() in have_names:
                continue
            key = (name_en, fid)
            if key in seen:
                continue
            seen.add(key)
            fish.append({
                "name": en, "location": name_en, "zone": zone,
                "region": terr_region.get(terr, ""), "mode": "line",
                "level": s.get("level"), "id": fid,
                "startHour": 0.0, "endHour": 24.0,
                "weatherSet": [], "previousWeatherSet": [],
                "predators": {}, "bait": [], "tug": "Light", "hookset": None,
                "snagging": False, "folklore": False, "fishEyes": False,
                "gig": None, "patch": None, "common": True,
            })

    # 叉鱼大小: 从本地 data/spear_sizes.json 补(来源鱼糕, 一次性抽好, 重生成不丢)
    _ss_path = ROOT / "data" / "spear_sizes.json"
    if _ss_path.exists():
        _ss = json.loads(_ss_path.read_text(encoding="utf-8"))
        for f in fish:
            if f["mode"] == "spear" and (f.get("gig") in (None, "UNKNOWN")) \
                    and str(f.get("id")) in _ss:
                f["gig"] = _ss[str(f["id"])]

    fish.sort(key=lambda x: (x["level"] is None, x["level"] or 0, x["zone"], x["name"]))
    n_line = sum(1 for f in fish if f["mode"] == "line")
    n_common = sum(1 for f in fish if f["common"])
    matched = sum(1 for f in fish if f.get("id"))
    out = {
        "regions": "all" if REGIONS is None else REGIONS,
        "source": "fish-tracker(notable) + teamcraft(levels/common/names)",
        "count": len(fish), "count_line": n_line,
        "count_spear": len(fish) - n_line, "count_common": n_common,
        "fish": fish,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成: 共 {len(fish)} 条 (值得追 {n_notable} / 常见 {n_common} / "
          f"叉鱼 {len(fish)-n_line}), id匹配率 {matched}/{len(fish)}")
    print(f"  -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
