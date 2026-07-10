"""
FF14 钓鱼 职业任务模块 (每 5 级一篇)
------------------------------------------------------------
设计约定(和船长聊定的):
  - 等级解锁, 只做剧情提醒, **不绑定任何技能**——不做也不影响玩
  - 剧情是原创轻松短篇(致敬行会众人的气质, 不照搬游戏原文), 藏点小彩蛋
  - 考验用真实存在的鱼: 钓到过(进图鉴)即可交差, 老手秒交
  - 奖励: gil + 经验 + 少量🎫白票

★ 想调奖励手感, 改下面常量即可 ★
"""

from __future__ import annotations

try:
    from .fish import get as _get_fish
except ImportError:
    from fish import get as _get_fish

# ===== 可调常量 =============================================
REWARD_GIL_PER_LV = 40       # gil 奖励 = 等级 × 此值
REWARD_XP_PER_LV = 18        # 经验奖励 = 等级 × 此值
REWARD_WHITE_PER_5LV = 1     # 白票奖励 = 等级 // 5 × 此值
# ===========================================================

# 每个任务: (等级, 标题, 剧情[原创], 任务鱼英文名, 钓场提示)
QUESTS = [
    (5, "入会试炼",
     "行会前台的猫咪头也不抬:「新人?先去钓条黄铜泥鳅回来。」\n"
     "你:「就这?」猫咪翻了个白眼:「上一个说'就这'的,现在还在码头哭。」",
     "Brass Loach", "The Vein"),
    (10, "虾兵蟹将",
     "会长一手端着果汁，一手托着老鹰:「听说过神盾虾吗?壳硬得能挡箭。」\n"
     "「我们不需要它挡箭。我们需要它下锅。」老鹰投来赞同的目光。",
     "Aegis Shrimp", "Lower Soot Creek"),
    (15, "骨中自有黄金屋",
     "「骨蝲蛄,浑身是刺,没什么肉。」前辈说。\n"
     "「那为什么要钓?」「因为菜单上写着'今日特供'。」",
     "Bone Crayfish", "The Mirror"),
    (20, "蜗牛的十二神巡礼",
     "十二神圣域的橡实螺,据说爬完一圈神像要三年。\n"
     "你的任务是在它功德圆满之前把它钓上来。罪过罪过。",
     "Acorn Snail", "Sanctum of the Twelve"),
    (25, "会爬树的鱼",
     "「攀鲈会上树。」「鱼会上树?」「所以才叫你去——\n"
     "行会赌了五万金币说它不会,输了你来付。」",
     "Climbing Perch", "Verdant Drop"),
    (30, "斗鱼",
     "阿拉米格斗鱼,鱼如其名,见谁咬谁。\n"
     "前辈递给你钓竿:「去吧。莫要停下来啊。」",
     "Ala Mhigan Fighting Fish", "Everschade"),
    (35, "永影的黑影",
     "希望之苗池的黑鬼鱼只在暗处游。\n"
     "「看不见怎么钓?」「用心钓。心也看不见,不影响你有。」",
     "Black Ghost", "Hopeseed Pond"),
    (40, "钉子户",
     "「巨钉(The Nail)那儿的阿巴拉提亚胡瓜鱼,十年没人钓走过。」\n"
     "「为什么?」「因为没人想爬那么高。今天有了。」",
     "Abalathian Smelt", "The Nail"),
    (45, "愤怒的狗鱼",
     "哭泣圣者湖的愤怒狗鱼,常年愤怒,原因不明。\n"
     "你的任务是钓上来问问。问不出来就红烧。",
     "Angry Pike", "The Weeping Saint"),
    (50, "盲眼蝠鲼",
     "「巫女之落的盲眼蝠鲼看不见鱼饵。」\n"
     "「那它咬什么?」「咬缘分。」——第一批到 50 级的人都听过这句。",
     "Blind Manta", "Witchdrop"),
    (55, "云端骑士",
     "索姆阿尔山顶,云涛之上,有鱼名曰翔云。\n"
     "会长:「带氧气。」你:「鱼要氧气?」会长:「你要。」",
     "Cloud Rider", "Sohm Al Summit"),
    (60, "以太之眼",
     "「以太眼,整片花海只有它看得见风。」\n"
     "前辈压低声音:「钓到它的人,都说听见了大海的低语。也可能是耳鸣。」",
     "Aether Eye", "The Pappus Tree"),
    (65, "银沟里淘金",
     "黄金港的银沟运河,游着一种黄铜鱼。\n"
     "「银沟里钓黄铜?」「对,这就是经济学。」",
     "Brassfish", "The Silver Canal"),
    (70, "珍珠之眼",
     "盐湖泽尔湖,珍珠眼。行会的最后一课。\n"
     "会长难得正经:「钓上它,你就出师了。」顿了顿:「饭钱AA。」",
     "Pearl-eye", "Loch Seld"),
    (75, "蝴蝶效应",
     "废船街的游末邦蝴蝶鱼,只在它心情好的时候咬钩。\n"
     "「跟游末邦的贵族一个脾气。」前辈耸肩。\n"
     "「那怎么让它心情好?」「你先让我心情好——把上次的饭钱结了。」",
     "Eulmore Butterfly", "The Derelicts"),
    (80, "食骨之宴",
     "行会来了封信。不是任务——是请帖。\n"
     "会长的字迹歪歪扭扭:「八十级了,回来坐坐。带条食骨虾,火锅缺主菜。」\n"
     "你看着信纸背面:「P.S. 老鹰说想你了。我没说。是它说的。」",
     "Skulleater", "Upper Watts River"),
    (85, "象鼻之福",
     "新大陆有条鱼,鼻子像象鼻。当地人叫它「被象祝福的鱼」。\n"
     "「钓到它能怎样?」「得到象的祝福。」\n"
     "「象在哪?」「不重要。重要的是你信不信。」你不太信。但你去了。",
     "Trunkblessed", "Meghaduta"),
    (90, "吞星者",
     "星海。真正的星海。你站在一颗不知名的星球上钓鱼。\n"
     "吞星鱼——据说咬钩的瞬间,整条鱼线会被星光照亮。\n"
     "前辈说这是钓鱼生涯的分水岭:「九十级之前是钓鱼,之后是修行。」",
     "Star Eater", "Apohelos 18-γ"),
    (95, "欧来欧来欧来",
     "「这条鱼叫什么?」「欧来欧来欧来。」「……你在叫它过来?」\n"
     "「不。它就叫这个名字。」「谁起的?」\n"
     "「第一个钓到它的人。当时太开心了,翻来覆去只会说这三个字。」",
     "Alright Alright Alright", "Chirwagur Lake"),
    (100, "最后的考验",
     "世界的边缘。边郊镇的壕沟里,藏着虎纹大狗鱼——你最后的对手。\n"
     "会长没有托鹰,没有写信,没有喊你去行会开会。\n"
     "行会门口只贴了一张纸条:「去吧。带条鱼回来。不带也行。\n"
     "回来就行。」",
     "Tiger Muskellunge", "Outskirts Shallows"),
]

# 导入时自检: 任务鱼必须真实存在(数据变动会当场报错, 不上线坏任务)
for _lv, _t, _s, _fname, _loc in QUESTS:
    assert _get_fish(_fname), f"职业任务鱼不存在: {_fname}"


def available(level: int, done: list) -> list:
    """当前等级已解锁且未完成的任务列表。"""
    return [q for q in QUESTS if q[0] <= level and q[0] not in done]


def newly_unlocked(gained_levels: list) -> list:
    """这次升级新解锁的任务等级(供升级播报提醒)。"""
    ls = {q[0] for q in QUESTS}
    return sorted(l for l in (gained_levels or []) if l in ls)


def reward_of(level: int) -> dict:
    return {"gil": level * REWARD_GIL_PER_LV,
            "xp": level * REWARD_XP_PER_LV,
            "white": level // 5 * REWARD_WHITE_PER_5LV}
