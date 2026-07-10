"""
海钓真实排班表构建器 (与国际服现役班次同步)
============================================================
生成 data/ocean_pattern.json: 灵青/红玉两条航路各 144 班的固定循环表 + 偏移。
排班算法(与真实一致): 发船槽 k = floor(unix秒/7200), 航线 = PATTERN[(k+偏移)%144]。

数据来源(全 GitHub 可达):
  - netsua92/OceanFishing (oceanfishing.boats 现役源码, 7.5版含萨维奈环):
      scripts/indigooceancalculator.js  灵青 PATTERN + 各班型三站序列
      scripts/rubyoceancalculator.js    红玉 PATTERN + 各班型三站序列
    注意: 该站渲染发船时刻时内置 +4 槽修正(源码 stopTime 行), 故其数组
    对"发船槽"而言的有效偏移 = 站内偏移 - 4 (灵青 88-4=84, 红玉 92-4=88)。

双重交叉验证(任一不过即报错, 不写出数据):
  1) Lulu's Tools 文档页公布的灵青 144 位静态表 (本文件内嵌), 逐位比对;
  2) Lulu 2023 生成式算法 (calculate-voyages.ts 的 Python 移植, 本文件内嵌),
     以"目的地环+时段环+每日跳位"从纪元直接推算, 逐槽比对。

怎么跑: cd ff14-fishing && python tools/build_ocean_pattern.py
依赖: data/ocean.json (站名, 先跑 build_ocean_data.py)
      data/ocean_routes.json (21 条航线的站序, 用于把班型对账成航线键)
"""

from __future__ import annotations
import json
import re
import urllib.request
from pathlib import Path

SRC_BASE = ("https://raw.githubusercontent.com/netsua92/OceanFishing/"
            "main/scripts/")
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "ocean_pattern.json"

VOYAGE_SPAN = 7200      # 2 小时一班 (unix 秒)
DISPLAY_SHIFT = 4       # boats 站渲染时刻的 +4 槽修正 (见文件头说明)

# 站名对照: oceanfishing.boats 的 destinationKey -> 国服站名 (data/ocean.json)
DEST_TO_CN = {
    "destination.galadionbay": "加拉迪翁湾",
    "destination.thesouthernstraitofmerlthor": "梅尔托尔海峡南",
    "destination.thenorthernstraitofmerlthor": "梅尔托尔海峡北",
    "destination.rhotanosea": "罗塔诺海",
    "destination.thecieldalaes": "谢尔达莱群岛",
    "destination.thebloodbrinesea": "绯汐海",
    "destination.therothlytsound": "罗斯利特湾",
    "destination.thesirensongsea": "殀歌海",
    "destination.kugane": "黄金港",
    "destination.therubysea": "红玉海",
    "destination.theoneriver": "无二江",
    "destination.unnamed": "无名岛",
    "destination.thavnair": "萨维奈岛",
}
TIME_TO_CN = {"table.day": "白天", "table.sunset": "黄昏", "table.night": "夜晚"}

# ---- 验证材料 1: Lulu's Tools 文档公布的灵青 144 位表 ----
# 代号 = 终点缩写+时段缩写; 约定: 发船槽 k 的航线 = 此表[(k+88)%144]
# B=绯汐海 T=罗斯利特湾 N=梅尔托尔海峡北 R=罗塔诺海; D=白天 S=黄昏 N=夜晚
LULU_INDIGO = (
    "BD TD ND RD BS TS NS RS BN TN NN RN "
    "TD ND RD BS TS NS RS BN TN NN RN BD "
    "ND RD BS TS NS RS BN TN NN RN BD TD "
    "RD BS TS NS RS BN TN NN RN BD TD ND "
    "BS TS NS RS BN TN NN RN BD TD ND RD "
    "TS NS RS BN TN NN RN BD TD ND RD BS "
    "NS RS BN TN NN RN BD TD ND RD BS TS "
    "RS BN TN NN RN BD TD ND RD BS TS NS "
    "BN TN NN RN BD TD ND RD BS TS NS RS "
    "TN NN RN BD TD ND RD BS TS NS RS BN "
    "NN RN BD TD ND RD BS TS NS RS BN TN "
    "RN BD TD ND RD BS TS NS RS BN TN NN"
).split()
LULU_OFFSET = 88
LULU_DEST = {"B": "绯汐海", "T": "罗斯利特湾", "N": "梅尔托尔海峡北", "R": "罗塔诺海"}
LULU_TIME = {"D": "白天", "S": "黄昏", "N": "夜晚"}

# ---- 验证材料 2: Lulu 2023 生成式算法 (calculate-voyages.ts 移植) ----
_9HR = 32400
_LULU_EPOCH = 1593270000 + _9HR      # 循环锚点 (JST 挂钟)
_GEN_DEST = ["绯汐海", "罗斯利特湾", "梅尔托尔海峡北", "罗塔诺海"]
_GEN_TIME = ["黄昏"] * 4 + ["夜晚"] * 4 + ["白天"] * 4


def _generative_indigo(dep_unix: int) -> tuple[str, str]:
    """发船槽起点 unix 秒 -> (终点站, 到达时段)。原样移植, 独立于任何静态表。"""
    adj = dep_unix + _9HR
    day = (adj - _LULU_EPOCH) // 86400
    hour = (adj % 86400) // 3600     # JST 挂钟小时, 发船槽必落在奇数时
    assert hour % 2 == 1, f"发船槽不在 JST 奇数时: {dep_unix}"
    voyage = hour >> 1
    return _GEN_DEST[(day + voyage) % 4], _GEN_TIME[(day + voyage) % 12]


def _fetch(name: str) -> str:
    p = RAW / name
    if not p.exists():
        print(f"  拉取 {name} ...")
        with urllib.request.urlopen(SRC_BASE + name, timeout=120) as r:
            p.write_bytes(r.read())
    return p.read_text(encoding="utf-8")


def _parse_calculator(src: str):
    """从计算器 js 里取: PATTERN(1基班型号数组), 站内偏移, 各班型三站序列。"""
    pat_m = re.search(r"var pattern = \[([\s\S]*?)\];", src)
    pattern = [int(x) for x in re.findall(r"\d+", pat_m.group(1))]
    offset = int(re.search(r"var offset = (\d+);", src).group(1))

    stops_m = re.search(r"var scheduleStopKeys = \[([\s\S]*?)\n\];", src)
    variants = []
    for block in re.findall(r"\[\s*((?:\{[^}]*\},?\s*){3})\]", stops_m.group(1)):
        stops = re.findall(
            r'destinationKey:\s*"([^"]+)",\s*timeKey:\s*"([^"]+)"', block)
        variants.append([(DEST_TO_CN[d], TIME_TO_CN[t]) for d, t in stops])
    return pattern, offset, variants


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    spots = json.loads(
        (ROOT / "data" / "ocean.json").read_text(encoding="utf-8"))["spots"]
    routes = json.loads(
        (ROOT / "data" / "ocean_routes.json").read_text(encoding="utf-8"))["routes"]
    name_of = {sid: s["name"] for sid, s in spots.items()}

    # 我们每条航线键的三站序列 (站名, 时段) —— 对账的"底账"
    route_seq = {
        key: tuple((name_of[str(st["spot_id"])], st["time"]) for st in r["stops"])
        for key, r in routes.items()
    }
    seq_to_key = {seq: key for key, seq in route_seq.items()}
    assert len(seq_to_key) == len(route_seq), "航线站序存在重复, 无法唯一对账"

    result = {}
    for line, fname in (("indigo", "indigooceancalculator.js"),
                        ("ruby", "rubyoceancalculator.js")):
        pattern, site_offset, variants = _parse_calculator(_fetch(fname))
        assert len(pattern) == 144, f"{line} PATTERN 长度异常: {len(pattern)}"

        # 班型号(1基) -> 我们的航线键: 用三站序列精确对账
        num_to_key = {}
        for i, seq in enumerate(variants, start=1):
            key = seq_to_key.get(tuple(seq))
            assert key is not None, f"{line} 班型{i}的站序在本地航线里找不到: {seq}"
            num_to_key[i] = key

        keys = [num_to_key[n] for n in pattern]
        assert set(num_to_key.values()) == set(keys), f"{line} 有班型从未在 PATTERN 出现"
        eff_offset = (site_offset - DISPLAY_SHIFT) % 144
        result[line] = {"offset": eff_offset, "pattern": keys,
                        "variant_count": len(variants)}
        print(f"  {line}: 班型 {len(variants)} 种, 站内偏移 {site_offset} -> "
              f"有效偏移 {eff_offset}, 覆盖航线键 {sorted(set(keys), key=int)}")

    # ---------- 交叉验证 1: 灵青逐位对照 Lulu 文档静态表 ----------
    final_of = {k: route_seq[k][-1] for k in route_seq}
    ind = result["indigo"]
    for k in range(144):
        got = final_of[ind["pattern"][(k + ind["offset"]) % 144]]
        expect_code = LULU_INDIGO[(k + LULU_OFFSET) % 144]
        expect = (LULU_DEST[expect_code[0]], LULU_TIME[expect_code[1]])
        assert got == expect, f"验证1失败: 槽{k} 本表={got} Lulu文档={expect}"
    print("  验证1: 灵青 144 槽与 Lulu's Tools 文档静态表逐槽一致 ✔")

    # ---------- 交叉验证 2: 灵青逐槽对照 2023 生成式算法 ----------
    base = (_LULU_EPOCH // VOYAGE_SPAN) * VOYAGE_SPAN   # 任取对齐起点, 扫两轮
    for k in range(288):
        dep = base + k * VOYAGE_SPAN
        got = final_of[ind["pattern"][(dep // VOYAGE_SPAN + ind["offset"]) % 144]]
        assert got == _generative_indigo(dep), f"验证2失败: 槽起 {dep}"
    print("  验证2: 灵青 288 连续槽与 2023 生成式算法逐槽一致 ✔")

    out = {
        "source": ("oceanfishing.boats 源码(netsua92/OceanFishing, 7.5含萨维奈环), "
                   "经 Lulu's Tools 静态表+生成式算法双重交叉验证; 与国际服现役班次同步"),
        "span_seconds": VOYAGE_SPAN,
        "algorithm": "发船槽 k=floor(unix秒/7200); 航线 = pattern[(k+offset)%144]",
        "line_names": {"indigo": "灵青航路", "ruby": "红玉航路"},
        "lines": result,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"OK: 写出 {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
