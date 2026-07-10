"""
鱼竿数据提取器 (游戏原文, 不自制)
============================================================
从 GitHub(Teamcraft) 扒真实鱼竿: 名字 + 装备等级 + 品级(ilvl) + 采集力 + 鉴别力。
用 jobs=FSH + 主手 精确识别鱼竿(比按名字准)。生成 data/gear.json。

数据来源(全 GitHub 可达, 不碰 XIVAPI):
  - equipment.json   装备等级 level + 职业 jobs(FSH) + 部位
  - item-stats.json  属性(采集力=72 / 鉴别力=73)
  - ilvls.json       品级
  - items.json       多语言名

怎么跑: cd ff14-fishing && python tools/build_gear_data.py
"""

from __future__ import annotations
import json
import urllib.request
from pathlib import Path

TC = "https://raw.githubusercontent.com/ffxiv-teamcraft/ffxiv-teamcraft/master/libs/data/src/lib/json"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "gear.json"
STAT_GATHERING, STAT_PERCEPTION = 72, 73


def _get(name: str):
    print(f"  拉取 {name} ...")
    with urllib.request.urlopen(f"{TC}/{name}", timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def _ilvl(ilvls, iid: int) -> int:
    v = ilvls.get(str(iid))
    return int(v.get("ilvl", 0)) if isinstance(v, dict) else int(v or 0)


def main() -> int:
    print("从 GitHub 拉取数据:")
    items = _get("items.json")
    stats = _get("item-stats.json")
    ilvls = _get("ilvls.json")
    equip = _get("equipment.json")

    rods = []
    for i, e in equip.items():
        # 钓鱼主手 = 鱼竿
        if e.get("equipSlotCategory") != 1 or "FSH" not in (e.get("jobs") or []):
            continue
        en = items.get(str(i), {}).get("en")
        if not en:
            continue
        gathering = perception = 0
        for s in stats.get(str(i), []):
            if s.get("ID") == STAT_GATHERING:
                gathering = s.get("NQ", 0)
            elif s.get("ID") == STAT_PERCEPTION:
                perception = s.get("NQ", 0)
        rods.append({
            "id": int(i), "name": en,
            "level": int(e.get("level", 1)),       # 装备等级(游戏原文)
            "ilvl": _ilvl(ilvls, int(i)),
            "gathering": gathering, "perception": perception,
        })

    rods.sort(key=lambda x: (x["level"], x["ilvl"], x["name"]))
    out = {
        "source": "teamcraft: equipment(level/jobs)/item-stats/ilvls/items (游戏原文)",
        "stat_note": "level=装备等级, gathering=采集力(72), perception=鉴别力(73)",
        "count": len(rods), "rods": rods,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成: {len(rods)} 把鱼竿 -> {OUT}")
    if rods:
        print(f"  装备等级 {rods[0]['level']} ~ {rods[-1]['level']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
