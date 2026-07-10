"""
中文鱼名提取器 (国服数据, 只增不改)
============================================================
从 GitHub 国服数据仓库的 Item.csv 取中文物品名, 填进 data/fish_text.json 的 cn 槽位。
只填"当前为空"的 cn(你手写过的任何中文名/文案永不被覆盖)。

数据来源: thewakingsands/ffxiv-datamining-cn : Item.csv
  列结构: key=物品id, 第9列=Name(中文名)

怎么跑: cd ff14-fishing && python tools/build_cn_names.py
"""

from __future__ import annotations
import csv
import io
import json
import urllib.request
from pathlib import Path

CSV_URL = ("https://raw.githubusercontent.com/thewakingsands/"
           "ffxiv-datamining-cn/master/Item.csv")
# Item.csv 数据行有偏移: row[0]=物品id, 之后 col0..colN = row[1..N+1]
# 官方列 Description=col8=row[9], Name=col9=row[10]
NAME_COL = 10     # 中文名
DESC_COL = 9      # 中文简介(图鉴)

ROOT = Path(__file__).resolve().parent.parent
FISH = ROOT / "data" / "fish.json"
TEXT = ROOT / "data" / "fish_text.json"


def main() -> int:
    gameplay = json.loads(FISH.read_text(encoding="utf-8"))["fish"]
    doc = json.loads(TEXT.read_text(encoding="utf-8"))
    entries = doc.get("fish", {})

    # 鱼名(en) -> 物品id
    name2id = {}
    for f in gameplay:
        if f["name"] not in name2id and f.get("id"):
            name2id[f["name"]] = f["id"]
    want_ids = set(name2id.values())

    print(f"下载国服 Item.csv (约 19MB) ...")
    with urllib.request.urlopen(CSV_URL, timeout=120) as r:
        data = r.read().decode("utf-8", errors="replace")

    # 解析 CSV: 前三行是列号/列名/类型, 之后是数据; row[0]=物品id
    id2cn, id2desc = {}, {}
    reader = csv.reader(io.StringIO(data))
    rows = iter(reader)
    next(rows, None)
    next(rows, None)
    next(rows, None)
    for row in rows:
        if not row:
            continue
        try:
            iid = int(row[0])
        except ValueError:
            continue
        if iid not in want_ids:
            continue
        if len(row) > NAME_COL and row[NAME_COL].strip():
            id2cn[iid] = row[NAME_COL].strip()
        if len(row) > DESC_COL and row[DESC_COL].strip():
            id2desc[iid] = row[DESC_COL].strip().replace("\r\n", " ").replace("\n", " ")

    filled_n = filled_d = 0
    for name, iid in name2id.items():
        e = entries.get(name)
        if not e:
            continue
        if not e["names"].get("cn") and id2cn.get(iid):
            e["names"]["cn"] = id2cn[iid]
            filled_n += 1
        if isinstance(e.get("desc_official"), dict) and not e["desc_official"].get("cn") \
                and id2desc.get(iid):
            e["desc_official"]["cn"] = id2desc[iid]
            filled_d += 1

    TEXT.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"完成: 中文名 {filled_n} 条 / 中文简介 {filled_d} 条 -> {TEXT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
