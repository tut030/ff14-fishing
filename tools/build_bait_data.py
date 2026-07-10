"""
鱼饵数据提取器 (游戏原文, 不自制)
============================================================
把"大鱼用到、且 NPC 用 gil 卖得到"的基础鱼饵, 连同真实售价+中文名, 生成 data/bait.json。
买不到的特殊饵/以鱼作饵(mooch)不收录 —— 那些大鱼在游戏里不卡饵(见 game.py)。

数据来源(全 GitHub 可达):
  - ffxiv-teamcraft: items.json(名) + shops.json(GilShop 售价, 货币id 1=gil)
  - thewakingsands/ffxiv-datamining-cn: Item.csv(中文名, 第10列)

怎么跑: cd ff14-fishing && python tools/build_bait_data.py
注意: 会下载较大文件(items/shops/Item.csv 合计约 38MB), 仅重生成时才需要。
"""

from __future__ import annotations
import csv
import io
import json
import urllib.request
from pathlib import Path

TC = "https://raw.githubusercontent.com/ffxiv-teamcraft/ffxiv-teamcraft/master/libs/data/src/lib/json"
CN_CSV = ("https://raw.githubusercontent.com/thewakingsands/"
          "ffxiv-datamining-cn/master/Item.csv")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "bait.json"


def _getjson(url, tag):
    print(f"  拉取 {tag} ...")
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def _base(f):
    b = f["bait"][0]
    return b[0] if isinstance(b, list) else b


def main() -> int:
    fish = json.loads((ROOT / "data" / "fish.json").read_text(encoding="utf-8"))["fish"]
    items = _getjson(f"{TC}/items.json", "items.json")
    shops = _getjson(f"{TC}/shops.json", "shops.json")

    baits = set(_base(f) for f in fish if f["mode"] == "line" and f["bait"])
    name2id = {n["en"].lower(): int(i) for i, n in items.items() if n.get("en")}
    gilprice = {}
    for shop in shops:
        for tr in shop.get("trades", []):
            if any(c.get("id") == 1 for c in tr.get("currencies", [])):
                price = next(c["amount"] for c in tr["currencies"] if c["id"] == 1)
                for it in tr.get("items", []):
                    iid = it.get("id")
                    if iid and (iid not in gilprice or price < gilprice[iid]):
                        gilprice[iid] = price

    sellable = {}
    for b in baits:
        iid = name2id.get(b.lower())
        if iid and iid in gilprice:
            sellable[b] = {"id": iid, "price": gilprice[iid], "cn": None}
    want = {v["id"] for v in sellable.values()}

    print("  拉取 Item.csv(中文名) ...")
    with urllib.request.urlopen(CN_CSV, timeout=180) as r:
        data = r.read().decode("utf-8", errors="replace")
    rows = iter(csv.reader(io.StringIO(data)))
    for _ in range(3):
        next(rows, None)
    id2cn = {}
    for row in rows:
        try:
            iid = int(row[0])
        except (ValueError, IndexError):
            continue
        if iid in want and len(row) > 10 and row[10].strip():
            id2cn[iid] = row[10].strip()
    for v in sellable.values():
        v["cn"] = id2cn.get(v["id"])

    OUT.write_text(json.dumps(
        {"source": "shops(价)+items(名)+datamining-cn(中文名)",
         "count": len(sellable), "baits": sellable},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"完成: {len(sellable)} 种可买鱼饵 -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
