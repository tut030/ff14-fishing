"""ffxiv-datamining-cn 的 Item.csv → data/retainer_arms.json
用法: 把 Item.csv 放到 /tmp/Item.csv 后 python3 tools/build_retainer_arms.py
取材原则"每5级一份大路货": 每职业每5级挑一件常见货
(优先普通稀有度, 同档取穿戴等级最高·品级最低的)。官方中文名原样保留。"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path("/tmp/Item.csv")

# ItemUICategory id → 职业(中文, 官方分类名→职业是常识映射)
CAT2JOB = {
    # 战斗职业
    "1": "武僧", "2": "骑士", "3": "战士", "4": "吟游诗人", "5": "龙骑士",
    "6": "黑魔法师", "7": "黑魔法师", "8": "白魔法师", "9": "白魔法师",
    "10": "召唤师", "98": "学者", "84": "忍者", "87": "暗黑骑士",
    "88": "机工士", "89": "占星术士", "96": "武士", "97": "赤魔法师",
    "105": "青魔法师", "106": "绝枪战士", "107": "舞者", "108": "钐镰客",
    "109": "贤者", "110": "蝰蛇剑士", "111": "绘灵法师",
    # 采集·生产(主工具; 捕鱼人已有专属鱼竿体系, 不在此表)
    "28": "采矿工", "30": "园艺工",
    "12": "刻木匠", "14": "锻铁匠", "16": "铸甲匠", "18": "雕金匠",
    "20": "制革匠", "22": "裁衣匠", "24": "炼金术士", "26": "烹调师",
}
I_NAME, I_ILVL, I_RARITY, I_CAT, I_EQLV = 10, 12, 13, 16, 41

best = {}                              # (job, band) -> 候选
with SRC.open(encoding="utf-8-sig", newline="") as f:
    for row in csv.reader(f):
        if not row or not row[0].isdigit() or len(row) <= I_EQLV:
            continue
        job = CAT2JOB.get(row[I_CAT])
        if not job:
            continue
        name = row[I_NAME].strip()
        eqlv = int(row[I_EQLV] or 0)
        if not name or eqlv < 1:
            continue
        ilvl, rar = int(row[I_ILVL] or 0), int(row[I_RARITY] or 1)
        band = (eqlv - 1) // 5         # 1-5, 6-10, ...每5级一档
        key = (job, band)
        cand = (rar if rar <= 2 else rar + 10, -eqlv, ilvl, name)   # 大路货优先
        if key not in best or cand < best[key][0]:
            best[key] = (cand, {"level": eqlv, "ilvl": ilvl, "name_cn": name})

arms = {}
for (job, _band), (_c, it) in sorted(best.items(), key=lambda kv: (kv[0][0], kv[0][1])):
    arms.setdefault(job, []).append(it)

(ROOT / "data" / "retainer_arms.json").write_text(
    json.dumps({"arms": arms}, ensure_ascii=False, indent=1), encoding="utf-8")
n = sum(len(v) for v in arms.values())
print(f"✅ {len(arms)} 职业 · {n} 件武器/主工具 → data/retainer_arms.json")
for j, v in arms.items():
    print(f"   {j}: {len(v)}档 Lv{v[0]['level']}~{v[-1]['level']} 例:{v[0]['name_cn']}")
