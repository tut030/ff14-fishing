"""
捕鱼人全装备数据构建器 (游戏原文, 不自制)
============================================================
生成 data/gear_full.json: 捕鱼人可穿的全部位装备(主手/头/身/手/腿/脚/耳/颈/腕/戒),
含 中英文名/装等/穿戴等级/稀有度/魔晶石孔数/真实属性(获得力·鉴别力·GP)。

稀有度: 1=白装 2=绿装(可禁断) 3=蓝装(毕业装·票据) 4=紫装(古武等)
属性(国服叫法): BaseParam 72=获得力(Gathering) 73=鉴别力(Perception) 10=采集力(GP)

数据来源(GitHub 自动拉取, 缓存进 data/raw/):
  - thewakingsands/ffxiv-datamining-cn: Item.csv / BaseParam.csv / ClassJobCategory.csv
  - ffxiv-teamcraft items.json (英文名, 海钓工具已缓存为 tc_items.json)

怎么跑: cd ff14-fishing && python tools/build_gear_full.py
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
OUT = ROOT / "data" / "gear_full.json"

# Item.csv 关键列下标(以表头核对, 变了会报错)
COLS = {"Name": 10, "Level{Item}": 12, "Rarity": 13, "EquipSlotCategory": 18,
        "Level{Equip}": 41, "ClassJobCategory": 44, "MateriaSlotCount": 87}
BP_PAIRS = [(60, 61), (62, 63), (64, 65), (66, 67), (68, 69), (70, 71)]
PARAM = {"72": "gathering", "73": "perception", "10": "gp"}   # 获得/鉴别/GP
GATHER_CJC = {"19", "32", "35", "155"}    # 捕鱼人 / 大地使者 / 能工巧匠·大地使者
SLOT_NAME = {1: "rod", 3: "head", 4: "body", 5: "hands", 7: "legs",
             8: "feet", 9: "ears", 10: "neck", 11: "wrists", 12: "ring"}


def _fetch(name: str) -> Path:
    p = RAW / name
    if not p.exists():
        print(f"  拉取 {name} ...")
        with urllib.request.urlopen(CN_BASE + name, timeout=300) as r:
            p.write_bytes(r.read())
    return p


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    rows = list(csv.reader(io.StringIO(
        _fetch("Item.csv").read_text(encoding="utf-8-sig"))))
    header = rows[1]
    for k, i in COLS.items():                    # 表头核对, 上游变了立刻发现
        assert header[i] == k, f"Item.csv 列位变动: 期望第{i}列是{k}, 实为{header[i]}"

    tc = json.loads((RAW / "tc_items.json").read_text(encoding="utf-8"))

    gear = []
    for r in rows[3:]:
        if not r or not r[0].isdecimal():
            continue
        if r[COLS["ClassJobCategory"]] not in GATHER_CJC:
            continue
        esc = int(r[COLS["EquipSlotCategory"]] or 0)
        if esc not in SLOT_NAME:
            continue
        stats = {}
        for pi, vi in BP_PAIRS:
            p, v = r[pi], r[vi]
            if p in PARAM and v and v != "0":
                stats[PARAM[p]] = int(v)
        if not stats:                            # 无属性的时装类跳过
            continue
        iid = int(r[0])
        gear.append({
            "id": iid,
            "name_cn": r[COLS["Name"]],
            "name_en": tc.get(str(iid), {}).get("en", ""),
            "slot": SLOT_NAME[esc],
            "ilvl": int(r[COLS["Level{Item}"]]),
            "level": int(r[COLS["Level{Equip}"]]),
            "rarity": int(r[COLS["Rarity"]]),     # 1白 2绿 3蓝 4紫
            "materia_slots": int(r[COLS["MateriaSlotCount"]]),
            "stats": stats,
        })

    gear.sort(key=lambda g: (g["slot"], g["ilvl"]))
    from collections import Counter
    rar = Counter(g["rarity"] for g in gear)
    slots = Counter(g["slot"] for g in gear)
    no_en = sum(1 for g in gear if not g["name_en"])
    OUT.write_text(json.dumps(
        {"source": "datamining-cn Item/BaseParam/ClassJobCategory + teamcraft(EN)",
         "count": len(gear),
         "rarity_legend": {"1": "白装", "2": "绿装(可禁断)",
                           "3": "蓝装(毕业·票据)", "4": "紫装"},
         "gear": gear},
        ensure_ascii=False), encoding="utf-8")
    print(f"OK: 写出 {OUT.name}  共 {len(gear)} 件")
    print(f"  稀有度: 白{rar[1]} 绿{rar[2]} 蓝{rar[3]} 紫{rar[4]}")
    print(f"  部位: {dict(slots)}")
    print(f"  缺英文名: {no_en} 件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
