"""
钓场中文名映射构建器 (游戏原文, 不自制)
============================================================
生成 data/spot_names.json: {英文钓场名: 国服中文名}, 供 goto/spots 认中文。

原理: 我们的钓场名(fish.json 的 location)是国际服 PlaceName 英文原文;
      国服 datamining 的 PlaceName.csv 是同一套 ID 的中文名。
      拉国际服英文 PlaceName.csv, 按 ID 对接两边即可。

数据来源(GitHub 自动拉取, 缓存进 data/raw/):
  - ffxiv-teamcraft places.json  (英文名 -> PlaceName ID)
  - thewakingsands/ffxiv-datamining-cn PlaceName.csv (中文, 海钓工具已缓存)

怎么跑: cd ff14-fishing && python tools/build_spot_names.py
"""

from __future__ import annotations
import csv
import io
import json
import urllib.request
from pathlib import Path

EN_URL = ("https://raw.githubusercontent.com/ffxiv-teamcraft/ffxiv-teamcraft/"
          "master/libs/data/src/lib/json/places.json")
CN_URL = ("https://raw.githubusercontent.com/thewakingsands/"
          "ffxiv-datamining-cn/master/PlaceName.csv")
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "spot_names.json"


def _fetch(url: str, name: str) -> Path:
    p = RAW / name
    if not p.exists():
        print(f"  拉取 {name} ...")
        with urllib.request.urlopen(url, timeout=300) as r:
            p.write_bytes(r.read())
    return p


def _rows(path: Path) -> list[list[str]]:
    return list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))))


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    # 我们实际用到的钓场英文名(线钓+叉鱼全部 location)
    fish = json.loads((ROOT / "data" / "fish.json").read_text(encoding="utf-8"))
    need = {f["location"] for f in fish["fish"]}

    en_path = _fetch(EN_URL, "tc_places.json")
    places = json.loads(en_path.read_text(encoding="utf-8"))
    cn_rows = _rows(_fetch(CN_URL, "PlaceName.csv"))

    import re
    en_by_name = {}                     # 英文名 -> id (取第一个出现)
    for pid, v in places.items():
        en = re.sub(r"<[^>]+>", "", v.get("en", ""))   # 去 <i> 等HTML标签
        if en:
            en_by_name.setdefault(en, int(pid))
    cn_by_id = {}
    for r in cn_rows[3:]:
        if r and r[0].isdecimal() and len(r) > 1 and r[1]:
            cn_by_id[int(r[0])] = r[1]

    mapping, missing = {}, []
    for name in sorted(need):
        pid = en_by_name.get(name)
        cn = cn_by_id.get(pid, "") if pid else ""
        if cn:
            mapping[name] = cn
        else:
            missing.append(name)

    OUT.write_text(json.dumps(
        {"source": "PlaceName EN(xivapi) x CN(datamining-cn) 按ID对接",
         "count": len(mapping), "names": mapping},
        ensure_ascii=False), encoding="utf-8")
    print(f"OK: 写出 {OUT.name}  映射 {len(mapping)}/{len(need)} 个钓场")
    if missing:
        print(f"  未匹配({len(missing)}): {missing[:8]}{' ...' if len(missing) > 8 else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
