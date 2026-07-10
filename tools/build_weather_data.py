"""
天气数据生成器 (扩区域)
============================================================
从 GitHub 提取指定大区的: 天气概率表 + 区域名 + 天气名,
生成 data/weather.json 供引擎读取。

想加/减区域: 改下面 REGIONS 这一行, 重跑即可。

怎么跑:
    cd ff14-fishing
    python tools/build_weather_data.py

数据来源: icykoneko/ff14-fish-tracker-app 的 js/app/data.js
          (WEATHER_RATES / WEATHER_TYPES / REGIONS / ZONES)
"""

from __future__ import annotations
import json
import urllib.request
from pathlib import Path

DATAJS_URL = ("https://raw.githubusercontent.com/icykoneko/"
              "ff14-fish-tracker-app/master/js/app/data.js")

# 要包含的大区: None = 全部大区; 或列出 id 如 [22, 23, 24]
REGIONS = None

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "weather.json"


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


def main() -> int:
    print(f"拉取 data.js ...")
    with urllib.request.urlopen(DATAJS_URL, timeout=30) as r:
        txt = r.read().decode("utf-8")

    RATES = _extract(txt, "WEATHER_RATES")
    WT = _extract(txt, "WEATHER_TYPES")
    REG = _extract(txt, "REGIONS")
    ZONES = _extract(txt, "ZONES")

    want = None if REGIONS is None else set(REGIONS)
    zones_out, used_weather = {}, set()
    for v in RATES.values():
        if want is not None and v["region_id"] not in want:
            continue
        zid = v["zone_id"]
        zname = ZONES.get(str(zid), {}).get("name_en")
        if not zname:
            continue
        zones_out[zname] = {
            "region_id": v["region_id"],
            "region": REG.get(str(v["region_id"]), {}).get("name_en", ""),
            "rates": v["weather_rates"],
        }
        for w, _ in v["weather_rates"]:
            used_weather.add(w)

    weather_types = {str(i): {"en": WT[str(i)]["name_en"],
                              "ja": WT[str(i)].get("name_ja", "")}
                     for i in sorted(used_weather)}

    out = {
        "regions_included": REGIONS,
        "source": "icykoneko/ff14-fish-tracker-app : js/app/data.js",
        "weather_types": weather_types,
        "zones": zones_out,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"完成: {len(zones_out)} 个天气区 / {len(weather_types)} 种天气 -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
