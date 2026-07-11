"""wiki 狩猎探险表 → data/venture_hunt.json
用法: python3 tools/build_venture_hunt.py
产出三块:
  items         素材全表(官方原名保留, 供 3c 战斗雇员用)
  req_by_level  各等级的平均品级门槛 [5档] (数量 5/7/10/12/15 的达标线)
  exp_by_level  各等级探险经验(官方原值, 游戏内再过 leveling._compress 压缩)
缺档等级(如85/87)查询时取往下最近一档。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QTY = [5, 7, 10, 12, 15]

items, req, exp = [], {}, {}
for line in (ROOT / "tools" / "raw_venture_hunt.tsv").read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    lv_s, name, _qty, req_s, exp_s = line.split("\t")
    lv = int(lv_s)
    items.append({"level": lv, "name_cn": name})
    req.setdefault(str(lv), [int(x) for x in req_s.split(" / ")])
    exp.setdefault(str(lv), int(exp_s))

out = {"qty_tiers": QTY, "items": items,
       "req_by_level": req, "exp_by_level": exp}
(ROOT / "data" / "venture_hunt.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"✅ {len(items)} 素材 · 等级 {min(int(k) for k in exp)}-{max(int(k) for k in exp)} → data/venture_hunt.json")
