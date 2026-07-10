"""
捕鱼人全身装备构建器 (游戏原文, 不自制)
============================================================
生成 data/equipment.json: 捕鱼人可穿的全部装备, 每件含:
  中文名/英文名/部位/穿戴等级/装等/稀有度(白1绿2蓝3紫4)/
  魔晶石孔数/可否禁断(IsAdvancedMeldingPermitted)/
  三维(获得力/鉴别力/采集力GP)

真实规则由此还原:
  蓝装(稀有度3, 票据毕业装): 孔少(2-3), 不可禁断
  绿装/白装: 孔少但可禁断到 5 孔(游戏原生字段, 不是我们编的)

数据来源(GitHub, 缓存 data/raw/):
  - datamining-cn Item.csv / BaseParam.csv / ClassJobCategory.csv / EquipSlotCategory.csv
  - teamcraft items.json (英文名, 海钓工具已缓存)

怎么跑: cd ff14-fishing && python tools/build_equipment_data.py
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
OUT = ROOT / "data" / "equipment.json"

# 三维参数 id (BaseParam.csv 游戏原文)
PARAM_GATHERING = 72     # 获得力
PARAM_PERCEPTION = 73    # 鉴别力
PARAM_GP = 10            # 采集力(GP)


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

    # 1) 含捕鱼人的职业分类
    cjc = _rows(_fetch("ClassJobCategory.csv"))
    fsh_col = cjc[1].index("FSH")
    fsh_cats = {int(r[0]) for r in cjc[3:]
                if r and r[0].isdecimal() and len(r) > fsh_col
                and r[fsh_col] == "True"}

    # 2) 装备部位: EquipSlotCategory id -> 部位名
    esc = _rows(_fetch("EquipSlotCategory.csv"))
    slot_cols = esc[1]
    slot_cn = {"MainHand": "主手", "OffHand": "副手", "Head": "头部",
               "Body": "身体", "Gloves": "手部", "Legs": "腿部",
               "Feet": "脚部", "Ears": "耳饰", "Neck": "项链",
               "Wrists": "手镯", "FingerL": "戒指", "FingerR": "戒指"}
    esc_slot = {}
    for r in esc[3:]:
        if not r or not r[0].isdecimal():
            continue
        for i, col in enumerate(slot_cols):
            if col in slot_cn and i < len(r) and r[i] == "1":
                esc_slot[int(r[0])] = slot_cn[col]
                break

    # 3) Item.csv: 按表头名定位各列(不硬记下标)
    item_rows = _rows(RAW / "Item.csv")     # 海钓工具已缓存约20MB
    h = item_rows[1]
    col = {name: h.index(name) for name in (
        "Name", "Level{Item}", "Level{Equip}", "Rarity",
        "EquipSlotCategory", "ClassJobCategory",
        "MateriaSlotCount", "IsAdvancedMeldingPermitted")}
    p_cols = [(h.index(f"BaseParam[{i}]"), h.index(f"BaseParamValue[{i}]"))
              for i in range(6)]

    # 英文名(teamcraft, 海钓工具已缓存)
    tc = json.loads((RAW / "tc_items.json").read_text(encoding="utf-8"))

    items = []
    for r in item_rows[3:]:
        if not r or not r[0].isdecimal():
            continue
        try:
            cat = int(r[col["ClassJobCategory"]] or 0)
            slot_id = int(r[col["EquipSlotCategory"]] or 0)
        except ValueError:
            continue
        if cat not in fsh_cats or slot_id not in esc_slot:
            continue
        stats = {}
        for pc, vc in p_cols:
            try:
                pid, val = int(r[pc] or 0), int(r[vc] or 0)
            except ValueError:
                continue
            if pid == PARAM_GATHERING:
                stats["获得力"] = stats.get("获得力", 0) + val
            elif pid == PARAM_PERCEPTION:
                stats["鉴别力"] = stats.get("鉴别力", 0) + val
            elif pid == PARAM_GP:
                stats["采集力"] = stats.get("采集力", 0) + val
        if not stats:                         # 无三维的杂物(时装等)不进玩法
            continue
        iid = int(r[0])
        items.append({
            "id": iid,
            "name": r[col["Name"]],
            "name_en": tc.get(str(iid), {}).get("en", ""),
            "slot": esc_slot[slot_id],
            "level": int(r[col["Level{Equip}"]] or 1),
            "ilvl": int(r[col["Level{Item}"]] or 1),
            "rarity": int(r[col["Rarity"]] or 1),   # 1白 2绿 3蓝 4紫
            "sockets": int(r[col["MateriaSlotCount"]] or 0),
            "overmeld": r[col["IsAdvancedMeldingPermitted"]] == "True",
            "stats": stats,
        })

    rar = {1: 0, 2: 0, 3: 0, 4: 0}
    for it in items:
        rar[it["rarity"]] = rar.get(it["rarity"], 0) + 1
    slots = {}
    for it in items:
        slots[it["slot"]] = slots.get(it["slot"], 0) + 1

    OUT.write_text(json.dumps(
        {"source": "datamining-cn Item/BaseParam/ClassJobCategory/"
                   "EquipSlotCategory + teamcraft(英文名)",
         "count": len(items),
         "params": {"获得力": "稀有鱼概率↑", "鉴别力": "HQ概率↑",
                    "采集力": "GP上限"},
         "items": items},
        ensure_ascii=False), encoding="utf-8")
    print(f"OK: 写出 {OUT.name}  共 {len(items)} 件捕鱼人装备")
    print(f"  稀有度分布: 白{rar[1]} 绿{rar[2]} 蓝{rar[3]} 紫{rar.get(4, 0)}")
    print(f"  部位分布: {slots}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
