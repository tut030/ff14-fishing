"""
魔晶石数据构建器 (游戏原文, 不自制)
============================================================
生成 data/materia.json: 采集三系魔晶石(获得力/鉴别力/采集力GP)
各 12 个品级(I~XII), 每颗含真实中文名/英文名/数值/品级。

数据来源(GitHub, 缓存 data/raw/):
  - datamining-cn Materia.csv  (三系行: BaseParam 72/73/10)
  - datamining-cn Item.csv     (中文名, 已缓存)
  - teamcraft items.json       (英文名, 已缓存)

怎么跑: cd ff14-fishing && python tools/build_materia_data.py
"""

from __future__ import annotations
import csv
import io
import json
import urllib.request
from pathlib import Path

CN_BASE = ("https://raw.githubusercontent.com/thewakingsands/"
           "ffxiv-datamining-cn/master/")
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "materia.json"

PARAM_CN = {"72": "获得力", "73": "鉴别力", "10": "采集力"}


def _fetch(name: str) -> Path:
    p = RAW / name
    if not p.exists():
        print(f"  拉取 {name} ...")
        with urllib.request.urlopen(CN_BASE + name, timeout=300) as r:
            p.write_bytes(r.read())
    return p


def _rows(path: Path) -> list[list[str]]:
    return list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))))


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    rows = _rows(_fetch("Materia.csv"))
    h = rows[1]
    bp = h.index("BaseParam")
    item_cols = [i for i, c in enumerate(h) if c.startswith("Item[")]
    val_cols = [i for i, c in enumerate(h) if c.startswith("Value[")]

    need_ids = set()
    raw_list = []
    for r in rows[3:]:
        if not r or not r[0].isdecimal() or r[bp] not in PARAM_CN:
            continue
        for grade, (ic, vc) in enumerate(zip(item_cols, val_cols), start=1):
            iid = int(r[ic] or 0)
            val = int(r[vc] or 0)
            if iid <= 0 or val <= 0:
                continue
            need_ids.add(iid)
            raw_list.append({"id": iid, "param": PARAM_CN[r[bp]],
                             "value": val, "grade": grade})

    # 中文名(Item.csv 已缓存) + 英文名(teamcraft 已缓存)
    cn = {}
    for r in _rows(RAW / "Item.csv")[3:]:
        if r and r[0].isdecimal() and int(r[0]) in need_ids and len(r) > 10:
            cn[int(r[0])] = r[10]
    tc = json.loads((RAW / "tc_items.json").read_text(encoding="utf-8"))
    for m in raw_list:
        m["name"] = cn.get(m["id"], "")
        m["name_en"] = tc.get(str(m["id"]), {}).get("en", "")

    missing = [m for m in raw_list if not m["name"]]
    OUT.write_text(json.dumps(
        {"source": "datamining-cn Materia/Item + teamcraft(英文名)",
         "count": len(raw_list), "materia": raw_list},
        ensure_ascii=False), encoding="utf-8")
    print(f"OK: 写出 {OUT.name}  共 {len(raw_list)} 颗(三系×12品级)")
    if missing:
        print(f"  缺中文名: {[m['id'] for m in missing]}")
    for m in raw_list[:3] + raw_list[-3:]:
        print(f"  例: {m['name']}  {m['param']}+{m['value']}  {m['grade']}型")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
