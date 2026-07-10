"""
海钓数据构建器 (游戏原文, 不自制)
============================================================
把海钓(Ocean Fishing)所需的全部数据合并成一份 data/ocean.json:
  站点(平时/幻海流两套鱼表) + 259条海钓鱼属性 + 加分目标表 + 海钓饵。

数据来源:
  - data/raw/data-json-BpnImEDf.js  鱼糕(ff14fish)数据模块 —— 需手动放置, 无法自动下载。
      变量 m: 259条海钓鱼(渔分/触发鱼/蓝鱼/咬钩时间/双提钩...)
      变量 d: 鱼参数表(oceanStars 星级)
      变量 g: 62条加分目标(含成就id, 供以后成就系统)
  - thewakingsands/ffxiv-datamining-cn (GitHub 自动拉取, 缓存进 data/raw/):
      IKDSpot.csv     站 -> SpotMain(平时鱼表)/SpotSub(幻海流鱼表)/PlaceName
      FishingSpot.csv 钓场 -> 10条鱼的 itemId
      PlaceName.csv   站的中文名
      Item.csv        海钓鱼/饵的中文名 (约20MB, 仅首次下载)
  - ffxiv-teamcraft items.json  英文名 (约18MB, 仅首次下载)

怎么跑: cd ff14-fishing && python tools/build_ocean_data.py
注意: 航线表已单独在 data/ocean_routes.json, 本工具不动它。
"""

from __future__ import annotations
import csv
import io
import json
import re
import urllib.request
from pathlib import Path

CN_BASE = ("https://raw.githubusercontent.com/thewakingsands/"
           "ffxiv-datamining-cn/master/")
TC_ITEMS = ("https://raw.githubusercontent.com/ffxiv-teamcraft/ffxiv-teamcraft/"
            "master/libs/data/src/lib/json/items.json")
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
YUGAO_JS = RAW / "data-json-BpnImEDf.js"
OUT = ROOT / "data" / "ocean.json"

# 海钓专用饵 (versatile lure 等三种, 船上商店有售; itemId 为游戏原始id)
OCEAN_BAIT_IDS = [29714, 29715, 29716]


def _fetch(name: str) -> Path:
    """下载 datamining-cn 的 CSV 到 data/raw/ (已存在则直接用缓存)。"""
    p = RAW / name
    if not p.exists():
        print(f"  拉取 {name} ...")
        with urllib.request.urlopen(CN_BASE + name, timeout=300) as r:
            p.write_bytes(r.read())
    return p


def _csv_rows(path: Path) -> list[list[str]]:
    text = path.read_text(encoding="utf-8-sig")
    return list(csv.reader(io.StringIO(text)))


def _extract_js_var(src: str, varname: str):
    """从鱼糕 js 模块里取出 varname=JSON.parse('...') 的数据块。"""
    m = re.search(re.escape(varname) + r"=JSON\.parse\('", src)
    if not m:
        raise KeyError(f"鱼糕模块里找不到变量 {varname}")
    start = m.end()
    i = start
    while True:                       # 找到未被转义的收尾单引号
        i = src.find("'", i)
        backslashes, j = 0, i - 1
        while src[j] == "\\":
            backslashes += 1
            j -= 1
        if backslashes % 2 == 0:
            break
        i += 1
    raw = src[start:i].replace("\\'", "'").replace("\\\\", "\\")
    return json.loads(raw)


def main() -> int:
    if not YUGAO_JS.exists():
        print(f"缺少鱼糕数据文件: {YUGAO_JS}")
        print("请把 data-json-*.js 放到 data/raw/ 后重跑。")
        return 1
    RAW.mkdir(parents=True, exist_ok=True)

    # ---------- 1) 鱼糕: 海钓鱼 / 星级 / 加分目标 ----------
    src = YUGAO_JS.read_text(encoding="utf-8")
    ocean_fish = _extract_js_var(src, "m")      # 259 条
    fish_params = _extract_js_var(src, "d")     # oceanStars
    bonuses = _extract_js_var(src, "g")         # 62 条加分目标

    stars_by_param = {f["id"]: f.get("oceanStars", 0) for f in fish_params}
    fish_by_item = {}
    for f in ocean_fish:
        f = dict(f)
        f["stars"] = stars_by_param.get(f["fishParameterId"], 0)
        fish_by_item[f["itemId"]] = f

    # ---------- 2) 国服 CSV: 站 -> 两套鱼表 ----------
    ikd_rows = _csv_rows(_fetch("IKDSpot.csv"))
    spot_rows = _csv_rows(_fetch("FishingSpot.csv"))
    place_rows = _csv_rows(_fetch("PlaceName.csv"))

    header = spot_rows[1]
    item_cols = [i for i, h in enumerate(header) if h.startswith("Item")]
    fishing_spot = {}                      # FishingSpot key -> [itemId...]
    for r in spot_rows[3:]:
        if not r or not r[0].isdigit():
            continue
        items = [int(r[i]) for i in item_cols if r[i].isdigit() and int(r[i]) > 0]
        fishing_spot[int(r[0])] = items

    place_cn = {}                          # PlaceName key -> 中文名
    for r in place_rows[3:]:
        if r and r[0].isdigit() and len(r) > 1:
            place_cn[int(r[0])] = r[1]

    spots = {}
    for r in ikd_rows[3:]:
        if not r or not r[0].isdigit() or int(r[0]) == 0:
            continue
        sid, main, sub, place = (int(r[0]), int(r[1]), int(r[2]), int(r[3]))
        spots[str(sid)] = {
            "name": place_cn.get(place, f"站{sid}"),
            "normal": fishing_spot.get(main, []),
            "spectral": fishing_spot.get(sub, []),
        }

    # ---------- 3) 中文名 (Item.csv 第10列) + 英文名 (teamcraft) ----------
    need_ids = set(fish_by_item) | set(OCEAN_BAIT_IDS)
    cn_names = {}
    for r in _csv_rows(_fetch("Item.csv"))[3:]:
        if r and r[0].isdigit() and int(r[0]) in need_ids and len(r) > 10:
            cn_names[int(r[0])] = r[10]

    print("  拉取 teamcraft items.json (英文名) ...")
    tc_cache = RAW / "tc_items.json"
    if not tc_cache.exists():
        with urllib.request.urlopen(TC_ITEMS, timeout=300) as resp:
            tc_cache.write_bytes(resp.read())
    tc = json.loads(tc_cache.read_text(encoding="utf-8"))
    en_names = {i: tc[str(i)]["en"] for i in need_ids if str(i) in tc}

    for item_id, f in fish_by_item.items():
        f["name_cn"] = cn_names.get(item_id, "")
        f["name_en"] = en_names.get(item_id, "")

    # ---------- 4) 校验 ----------
    mapped = set()
    for s in spots.values():
        mapped |= set(s["normal"]) | set(s["spectral"])
    missing_in_spots = sorted(set(fish_by_item) - mapped)
    missing_in_yugao = sorted(mapped - set(fish_by_item))
    no_cn = [i for i in fish_by_item if not fish_by_item[i]["name_cn"]]
    trigger = sum(1 for f in fish_by_item.values() if f["isSpectralFish"])
    blue = sum(1 for f in fish_by_item.values() if f["isBlueFish"])

    out = {
        "source": ("鱼糕(ff14fish) + datamining-cn "
                   "IKDSpot/FishingSpot/PlaceName/Item + teamcraft"),
        "count_fish": len(fish_by_item),
        "count_spots": len(spots),
        "count_trigger": trigger,
        "count_blue": blue,
        "spots": spots,
        "fish": {str(k): v for k, v in fish_by_item.items()},
        "bonuses": bonuses,
        "bait_ids": OCEAN_BAIT_IDS,
        "bait_names": {str(i): {"cn": cn_names.get(i, ""),
                                "en": en_names.get(i, "")}
                       for i in OCEAN_BAIT_IDS},
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")

    print(f"OK: 写出 {OUT.name}")
    print(f"  海钓鱼 {len(fish_by_item)} | 站 {len(spots)}"
          f" | 触发鱼 {trigger} | 蓝鱼 {blue}")
    print(f"  鱼糕有但站里没有: {missing_in_spots or '无'}")
    print(f"  站里有但鱼糕没有: {missing_in_yugao or '无'}")
    print(f"  缺中文名: {no_cn or '无'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
