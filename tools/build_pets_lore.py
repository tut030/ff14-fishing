"""从 ffxiv-datamining-cn 构建宠物官方数据层 data/pets_lore.json。
数据来源(致谢):
  - 结构参考: https://github.com/xivapi/ffxiv-datamining
  - 中文文本: https://github.com/thewakingsands/ffxiv-datamining-cn
  - 官方文本版权 © SQUARE ENIX CO., LTD. 本项目为非商业玩家二创。
用法: python tools/build_pets_lore.py  (需联网)
"""
import csv, io, json, urllib.request, pathlib

BASE = "https://raw.githubusercontent.com/thewakingsands/ffxiv-datamining-cn/master/"


def fetch(name):
    with urllib.request.urlopen(BASE + name, timeout=30) as r:
        return list(csv.reader(io.StringIO(r.read().decode("utf-8-sig"))))


# 裁定: 宠物本体不拟人, 指代宠物的他/她→它(仅限下表, 人类/剧情指代保留)
PRONOUN_FIX = {
    "13":  [("由他去吧", "由它去吧")],
    "82":  [("成为她的活祭", "成为它的活祭")],
    "86":  [("他会为你哭为你死", "它会为你哭为你死"),
            ("因为他而哭", "因为它而哭")],
    "87":  [("他从小就立志", "它从小就立志"),
            ("可惜他的大胡子老爸", "可惜它的大胡子老爸")],
    "90":  [("她一心只想", "它一心只想")],
    "256": [("他会吃了你的", "它会吃了你的")],
    "317": [("希望我能让她打起精神", "希望我能让它打起精神")],
    "474": [("不过她有点害羞呢", "不过它有点害羞呢")],
}



# ══ 581条人工审校 · 规则表(她逐条犁过的, 一字不差执行) ══════
# 逐条精修(先跑)
KEY_EDITS = {
    "43":  [("让他们领教", "让对面领教")],
    "71":  [("我只是给他们点", "我只是为诸位点")],
    "72":  [("我只是给他们点", "我只是为诸位点")],
    "73":  [("我只是给他们点", "我只是为诸位点")],
    "74":  [("我只是给他们点", "我只是为诸位点")],
    "75":  [("陆行鸟之王", "陆行鸟男王")],
    "87":  [("主妇闲话", "家长闲话")],
    "89":  [("声称国王是", "声称男王是")],
    "95":  [("他们显然没", "这帮人显然没")],
    "125": [("是他做了", "是这位做了")],
    "164": [("我可不是什么王子", "我可不是什么王男")],
    "183": [("拥有父辈", "拥有母辈父辈")],
    "191": [("拉拉队姑娘", "拉拉队小朋友"), ("——拉拉队小姑娘", "——拉拉队小朋友")],
    "203": [("公主", "王储")],
    "227": [("圣女", "圣者")],
    "260": [("十岁的小姑娘", "十岁的小孩子")],
    "287": [("年轻王子", "年轻王储")],
    "433": [("自由之身的王子", "自由之身的王男")],
    "441": [("大英雄", "英雌")],
    "447": [("门奴专属奴仆", "门仆专属仆从")],
    "463": [("——迷人的地灵族女孩", "——地灵族小孩")],
}
# 整段重写
DESC_REWRITE = {
    "90":  "和番茄男王出于政治因素联姻。",
    "150": "再也没有物品使得她要遮遮掩掩的活着。",
}
# 名字改判
NAME_EDITS = {
    "86": "洋葱王男",
    "75": "巧儿陆行鸟王男", "89": "番茄男王", "164": "企鹅王男",
    "191": "拉拉队小朋友", "203": "吹雪王储", "287": "常风王储",
    "433": "月面仙人刺王男", "447": "门小仆",
}
# 全局字替换(逐条精修后跑, 含名字)
GLOBAL_EDITS = [
    ("洋葱王子", "洋葱王男"),
    ("妖", "殀"), ("英雄", "英杰"), ("其他", "其它"), ("他们", "这些人"),
    ("他人", "别人"), ("妈呀", "天啊"), ("奴仆", "仆从"), ("妨碍", "阻碍"),
    ("娇小", "小巧"), ("撒娇", "撒嗲"), ("先生", "男士"), ("母鸟", "雌鸟"),
]
_TXT_FIELDS = ("desc_official", "tooltip_official")


def _apply_edits(key, entry):
    if key in DESC_REWRITE:
        entry["desc_official"] = DESC_REWRITE[key]
    for old, new in KEY_EDITS.get(key, []):
        for f in _TXT_FIELDS:
            if entry.get(f):
                entry[f] = entry[f].replace(old, new)
    if key in NAME_EDITS:
        entry["name_cn"] = NAME_EDITS[key]
    for old, new in GLOBAL_EDITS:
        entry["name_cn"] = entry["name_cn"].replace(old, new)
        for f in _TXT_FIELDS:
            if entry.get(f):
                entry[f] = entry[f].replace(old, new)
        sp = entry.get("special_official")
        if sp:
            sp["名"] = sp["名"].replace(old, new)
            sp["述"] = sp["述"].replace(old, new)


# 裁定: 人形角色偶(npc_doll)不进游戏侧萌感池(惊喜池/图鉴浏览默认过滤)
# 规则: 迷你/袖珍前缀 或 人偶后缀 → 标记, 但下列"其实是可爱生物"的除外
_DOLL_PAT = __import__("re").compile(r"^(迷你|袖珍)|(人偶)$")
_CREATURE_EXCEPT = {
    # 迷你系里的非人形: 魔物/龙/机械/雏鸟/仙人掌/石像/兔道具屋...
    "迷你奥尔特罗斯", "迷你海魔", "迷你鲶鱼精", "迷你奇美拉", "迷你食肉者",
    "迷你尼德霍格", "迷你赫拉斯瓦尔格", "迷你法夫纳", "迷你弗栗多",
    "迷你亚历山大", "迷你欧米茄", "迷你欧米茄M", "迷你欧米茄F", "迷你阿尔法",
    "迷你伊甸", "迷你莫艾石像", "迷你巨人掌", "迷你库洛", "迷你浮士德",
    "迷你武装重甲", "迷你命名威", "迷你斯卡米留尼", "迷你埃里克特翁尼亚斯",
    "迷你凯纳槽", "迷你工程小车", "迷你零", "迷你赤红XIII", "迷你普利修",
    "迷你遗光", "迷你古鲁加加",
}
# 娃娃系默认是吉祥物(莫古力/凯特西/地灵/妖精)不标, 但梦魔娃娃是人形→标
_DOLL_FORCE = {"梦魔娃娃", "非正宗调查员", "光之战偶", "发条索鲁斯",
    # 大网复查补抓: 不带迷你/人偶马甲的角色偶
    "光之战士", "小小吉尔伽美什", "小小古代人", "小小守护者", "小小艾奇德娜"}
# 裁定捞回: 唯一官方明星(码头是她家的)
_DOLL_PARDON = {"袖珍梅尔维布"}


def _tag_doll(entry):
    n = entry["name_cn"]
    if n in _DOLL_PARDON:
        return
    if n in _DOLL_FORCE or (_DOLL_PAT.search(n) and n not in _CREATURE_EXCEPT):
        entry["npc_doll"] = True


def _fix_pronouns(key, entry):
    for old, new in PRONOUN_FIX.get(key, []):
        for f in ("desc_official", "tooltip_official"):
            if f in entry and old in entry[f]:
                entry[f] = entry[f].replace(old, new)


def main():
    comp = fetch("Companion.csv")
    tran = fetch("CompanionTransient.csv")
    tmap = {r[0]: r for r in tran[3:] if r}
    out = {"_source": {
        "结构参考": "https://github.com/xivapi/ffxiv-datamining",
        "中文文本": "https://github.com/thewakingsands/ffxiv-datamining-cn",
        "版权": "官方图鉴文本 © SQUARE ENIX CO., LTD. 非商业玩家二创, 仅供学习交流。"},
        "pets": {}}
    for r in comp[3:]:
        if not r or not r[1].strip():
            continue
        key, name = r[0], r[1].strip()
        t = tmap.get(key)
        entry = {"name_cn": name}
        if t:
            desc = (t[1] or "").strip()
            # 第一行是"召唤出宠物"操作说明, 图鉴正文在其后
            lines = [x for x in desc.splitlines() if x.strip()]
            entry["desc_official"] = "\n".join(lines[1:]) if len(lines) > 1 else desc
            entry["tooltip_official"] = (t[3] or "").strip()
            if len(t) > 5 and (t[4] or "").strip():
                entry["special_official"] = {"名": t[4].strip(),
                                             "述": (t[5] or "").strip()}
            try:
                entry["lom"] = {"攻": int(t[6]), "防": int(t[7]), "速": int(t[8])}
            except (ValueError, IndexError):
                pass
        _fix_pronouns(key, entry)
        _apply_edits(key, entry)
        _tag_doll(entry)
        out["pets"][key] = entry
    p = pathlib.Path(__file__).resolve().parent.parent / "data" / "pets_lore.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ 写入 {p.name}: {len(out['pets'])} 只宠物(官方名+图鉴+萌宠之王三维)")


if __name__ == "__main__":
    main()
