"""
鱼文案文件 生成/扩展 + 多语言名填充
============================================================
data/fish_text.json 是你放"多语言名 / 官方图鉴 / 手写环境描述"的地方。

本工具做两件事, 都 **只增不改**(你写过的字永不丢/永不被覆盖):
  1) 给缺失的鱼补空骨架
  2) 用 Teamcraft items.json 填英/日/德/法名字 —— 只填"当前为空"的槽位
     (中文名是另一个滞后源, 这里不动; 你手填的任何字段也不动)

build_fish_data.py 永远不碰本文件。

怎么跑:
    cd ff14-fishing
    python tools/init_fish_text.py
"""

from __future__ import annotations
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAMEPLAY = ROOT / "data" / "fish.json"
TEXT = ROOT / "data" / "fish_text.json"
TC_ITEMS_URL = ("https://raw.githubusercontent.com/ffxiv-teamcraft/ffxiv-teamcraft/"
                "master/libs/data/src/lib/json/items.json")

LANGS = ["en", "ja", "de", "fr", "cn"]
FILL_LANGS = ["en", "ja", "de", "fr"]     # 可从 items.json 填的; cn 另说


def _blank_entry(name_en: str, iid) -> dict:
    return {
        "id": iid,
        "names": {lang: (name_en if lang == "en" else None) for lang in LANGS},
        "desc_official": {"en": None, "ja": None, "cn": None},
        "flavor": "",
    }


def main() -> int:
    gameplay = json.loads(GAMEPLAY.read_text(encoding="utf-8"))["fish"]

    print("拉取 items.json(多语言名)...")
    with urllib.request.urlopen(TC_ITEMS_URL, timeout=60) as r:
        items = json.loads(r.read().decode("utf-8"))

    if TEXT.exists():
        doc = json.loads(TEXT.read_text(encoding="utf-8"))
    else:
        doc = {"_note": "图鉴/多语言/手写文案。可放心手写, build/update 不会覆盖本文件。",
               "fish": {}}
    entries = doc.setdefault("fish", {})

    # 鱼名 -> 物品 id (来自 fish.json)
    name2id = {}
    for f in gameplay:
        if f["name"] not in name2id and f.get("id"):
            name2id[f["name"]] = f["id"]

    added = kept = filled = 0
    for f in gameplay:
        name = f["name"]
        iid = name2id.get(name)
        if name not in entries:
            entries[name] = _blank_entry(name, iid)
            added += 1
        else:
            kept += 1
            if entries[name].get("id") is None and iid is not None:
                entries[name]["id"] = iid

        # 只填空槽位(保留手写)
        e = entries[name]
        loc = items.get(str(e.get("id")), {}) if e.get("id") else {}
        for lang in FILL_LANGS:
            if not e["names"].get(lang) and loc.get(lang):
                e["names"][lang] = loc[lang]
                filled += 1

    TEXT.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"完成: 保留 {kept} / 新增 {added} / 填入多语言名 {filled} 处 -> {TEXT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
