"""食物系统。
烹饪: 你的鱼(消耗1条渔获) + 调味料(商店买) → 料理
商店: 直接买成品(贵2~3倍)
Buff: 30分钟真实时间, +3%经验, 同时只能一种
v17: buff 改为绝对值(与装备一致), 接入实际钓鱼机制
v18: 53道商店食物(含47道新增), 数据来自灰机wiki
"""
import time as _time

BUFF_DURATION = 30 * 60   # 30 分钟(秒)
XP_BONUS = 0.03           # 所有食物 +3% 经验

# ── 调味料(商店买, 按味型分) ──────────────────────────
SEASONINGS = {
    "清淡调味套装": {"price": 15, "id": "light",
        "desc": "海盐、炭火、干净的水——让食材自己说话。"},
    "鲜美调味套装": {"price": 25, "id": "umami",
        "desc": "黄油、洋葱、蒜、荷兰芹——浓汤的灵魂全在这里。"},
    "香辣调味套装": {"price": 30, "id": "spicy",
        "desc": "黑胡椒、罗勒、咖喱粉、辣椒——点一把火在舌尖上。"},
    "酸甜调味套装": {"price": 25, "id": "sour",
        "desc": "柠檬、醋、蜂蜜——清爽和甜蜜的拉锯战。"},
    "甘甜调味套装": {"price": 20, "id": "sweet",
        "desc": "砂糖、奶油、肉桂、香草——温柔的甜。"},
}

# ── 鱼料理(需要鱼 + 调味料) ──────────────────────────
FISH_RECIPES = [
    {"name": "烤鲤鱼", "en": "Grilled Carp",
     "fish": "Maiden Carp", "seasoning": "light",
     "buff_type": "gathering", "buff_val": 20,
     "flavor": "只用盐，炭火慢烤。表皮焦脆，鱼肉嫩到一碰就散开，带着淡淡的河水清甜。",
     "eat": "你把烤鲤鱼掰开——热气和鲜香一起冒出来。第一口咬下去，外皮嘎吱作响，鱼肉在舌尖上化开。简单的盐味衬着鱼本身的甜。你闭上眼睛嚼了好久。"},
    {"name": "盐渍鳕鱼", "en": "Salt Cod",
     "fish": "Tiger Cod", "seasoning": "light",
     "buff_type": "gathering", "buff_val": 15,
     "flavor": "厚实的鳕鱼用海盐腌了整整一天。咸香中透着鱼肉本身的鲜味，越嚼越有味道。",
     "eat": "你撕下一条鳕鱼肉放进嘴里。盐粒在牙齿间嘎吱一声碎掉，然后是绵密紧实的鱼肉。咸、鲜、厚，越嚼越想嚼。"},
    {"name": "水煮鲷鱼", "en": "Boiled Bream",
     "fish": "Bianaq Bream", "seasoning": "umami",
     "buff_type": "perception", "buff_val": 30,
     "flavor": "洋葱、茄子和蒜在锅底熬成浓汤，鲷鱼切块放入。汤汁浓白，入口即化，暖到胃里。",
     "eat": "你舀起一块鲷鱼——它在汤里炖得太酥，筷子刚碰就碎了。连着浓白的汤汁一起喝下去，鲜味从喉咙一路暖到胃底。你不自觉地叹了口气。"},
    {"name": "金枪鱼串", "en": "Tuna Miq'abob",
     "fish": "Ash Tuna", "seasoning": "spicy",
     "buff_type": "gp", "buff_val": 15,
     "flavor": "金枪鱼和指虾穿成串，抹上罗勒橄榄油，炭火炙烤。外焦里嫩，配一挤柠檬汁——完美。",
     "eat": "你从签子上咬下一块鱼肉——表面焦香，里面还是粉嫩的。罗勒和橄榄油的香气在嘴里炸开。你挤了一点柠檬，酸味把所有味道都提亮了。"},
    {"name": "鱼汤", "en": "Fish Soup",
     "fish": "Bianaq Bream", "seasoning": "umami",
     "buff_type": "perception", "buff_val": 40,
     "flavor": "番茄和黄油打底，荷兰芹提香。鲷鱼在浓汤里炖得酥软。喝一口，从嗓子暖到脚尖。",
     "eat": "你端起碗喝了一口——浓稠的汤在舌面上铺开，番茄的微酸、黄油的醇厚、荷兰芹的清香层层叠叠。鲷鱼已经炖到看不见形状了，但它的鲜味融在每一滴汤里。暖的。"},
    {"name": "烤求雨鱼", "en": "Grilled Raincaller",
     "fish": "Raincaller", "seasoning": "light",
     "buff_type": "gathering", "buff_val": 40,
     "flavor": "整条鱼只撒盐，架在炭火上慢烤。蓝色的鳞片在火光下变成了金色。咬下去——满嘴鲜甜。",
     "eat": "你小心翼翼地拨开金色的鱼皮——热气携着鲜甜的香味扑面而来。第一口是惊艳：明明只放了盐，怎么会这么甜？是鱼本身的味道。你决定以后每次钓到求雨鱼都烤一条。"},
    {"name": "盐鳕泡芙", "en": "Salt Cod Puffs",
     "fish": "Tiger Cod", "seasoning": "sweet",
     "buff_type": "xp", "buff_val": 5,
     "flavor": "盐鳕鱼碎裹进面糊，炸到金黄酥脆。外面嘎吱嘎吱，里面绵软咸香。一口一个停不下来。",
     "eat": "你拿起一个——还烫手。咬下去的瞬间，酥脆的外壳碎裂，里面是绵软的鳕鱼馅。咸和甜在嘴里打架，最后谁也没赢。你又拿了一个。然后又一个。"},
    {"name": "醋渍鲱鱼", "en": "Pickled Herring",
     "fish": "Indigo Herring", "seasoning": "sour",
     "buff_type": "gp", "buff_val": 20,
     "flavor": "新鲜的鲱鱼用醋和柠檬腌制，再撒上细碎的芹菜叶。酸中带鲜，清爽到让人眼睛一亮。",
     "eat": "你夹起一片——半透明的鱼肉泛着醋的光泽。放进嘴里的瞬间酸味冲上来，紧跟着是鲱鱼的鲜和柠檬的清。像是有人在你嘴里按了一个刷新按钮。醒了。"},
]

# ── 商店成品(不用鱼, 直接买) ─────────────────────────
# 数据来源: 灰机wiki (ff14.huijiwiki.com), NQ 上限值
# 按品级排序, 价格按等级阶梯递增
SHOP_FOOD = [
    # ── 品级 9-22 (低级 50~80g) ──
    {"name": "清炖羊肉", "en": "Mutton Stew", "price": 50,
     "buff_type": "gp", "buff_val": 24, "buff2_type": "gathering", "buff2_val": 3,
     "flavor": "羊肉和蔬菜一起炖到酥烂。汤底浓厚，滚烫地喝下去，整个人都暖起来。最朴素的冬天味道。",
     "eat": "你端起碗喝了一口汤——烫的。但是停不下来。羊肉炖得一碰就散，蔬菜已经软到和汤融为一体。你用勺子把碗底刮干净了。围巾好像都不用了。"},
    {"name": "杂煮", "en": "Zoni", "price": 50,
     "buff_type": "gp", "buff_val": 24, "buff2_type": "perception", "buff2_val": 6,
     "flavor": "东方传来的一种汤菜，降神节必备。年糕软糯，清汤鲜美。据说喝了这碗汤，新的一年都会有好运。",
     "eat": "你端起碗——汤面上飘着一块白白胖胖的年糕和几片青菜。先喝了一口汤，清淡但鲜。然后去夹年糕——它从筷子间滑走了两次。终于咬到的时候，软糯的口感让你眯起了眼睛。新年快乐。"},
    {"name": "杰克南瓜灯", "en": "Jack-o'-lantern", "price": 50,
     "buff_type": "perception", "buff_val": 7,
     "flavor": "在煮熟的南瓜上刻出笑脸。不知道为什么吃刻了脸的南瓜好像更好吃？大概是因为可爱。",
     "eat": "你小心翼翼地掰下一块笑脸的额头——心里觉得有点对不起它。但是软糯的南瓜肉甜到你忘了这件事。甜的。暖的。在嘴里化掉了。"},
    {"name": "兔形派", "en": "Rabbit Pie", "price": 55,
     "buff_type": "gathering", "buff_val": 7, "buff2_type": "perception", "buff2_val": 3,
     "flavor": "森林之民传统的庆祝用点心。按照兔子的模样烤制——长耳朵那里最脆。",
     "eat": "你拿起一只兔形派——犹豫了一下从耳朵开始咬。嘎嘣一声，酥皮碎了一地。里面的馅是温热的，带着淡淡的香料味。你把碎掉的酥皮也捡起来吃了。"},
    {"name": "高山萝卜沙拉", "en": "Parsnip Salad", "price": 60,
     "buff_type": "perception", "buff_val": 7, "buff2_type": "gp", "buff2_val": 10,
     "flavor": "烤过的高山萝卜拌上橄榄油。萝卜经过烤制变得甜糯，橄榄油带来一层丝滑的润。",
     "eat": "你叉起一块萝卜——烤得外面微微焦黄，里面还是白嫩的。橄榄油让它在嘴里滑了一下，然后是萝卜本身的清甜。你意外地满足。明明只是萝卜。"},
    {"name": "烤仙人掌叶", "en": "Roasted Nopales", "price": 65,
     "buff_type": "perception", "buff_val": 8, "buff2_type": "gathering", "buff2_val": 3,
     "flavor": "加有蔬菜汁的仙人掌叶，烤起来就像肉排一样。外面焦脆里面多汁，不说的话真的猜不到是仙人掌。",
     "eat": "你切下一块——刀感确实像在切肉排。放进嘴里，外皮焦脆，里面冒出微微黏稠的汁水。味道很温和，有点像烤过的秋葵。你看了看手里的叉子又看了看盘子，决定接受仙人掌可以很好吃这个事实。"},
    {"name": "小扁豆煮山栗", "en": "Lentils and Chestnuts", "price": 70,
     "buff_type": "gp", "buff_val": 25, "buff2_type": "perception", "buff2_val": 3,
     "flavor": "小扁豆和山栗放到一起用红酒煮。扁豆绵软，山栗粉糯，红酒在锅底留下了微微的酸和甜。",
     "eat": "你舀了一勺——小扁豆已经煮得像泥一样绵软，山栗还保持着一点点形状。红酒的味道不明显了，但留下了一种说不上来的温厚。很适合在钓不到鱼的夜晚慢慢吃。"},
    {"name": "苹果挞", "en": "Apple Tart", "price": 75,
     "buff_type": "gathering", "buff_val": 9, "buff2_type": "gp", "buff2_val": 10,
     "flavor": "加入了苹果的圆形点心。焦糖化的苹果片铺在挞面上，甜里带着一点酸——闻起来就开心。",
     "eat": "你咬了一口——挞皮的酥、苹果的软、焦糖的脆，三种口感在一口里全了。甜味从焦糖来，酸味从苹果来，它们在你嘴里吵了一架，最后和好了。你把最后一点挞皮渣舔干净。"},
    {"name": "清炖羚羊肉", "en": "Antelope Stew", "price": 80,
     "buff_type": "gp", "buff_val": 26, "buff2_type": "gathering", "buff2_val": 4,
     "flavor": "羚羊肉炖蔬菜。比普通羊肉更瘦更嫩，汤底清爽不油腻。在树林里钓鱼的时候来一碗，刚好。",
     "eat": "你喝了一口汤——比羊肉的清淡，比牛肉的鲜。羚羊肉切成小块炖得很透，牙齿不怎么用力就咬开了。汤汁里有蔬菜慢慢渗出来的甜。你不自觉地连喝了三口。"},
    {"name": "煎菠菜", "en": "Spinach Saute", "price": 80,
     "buff_type": "perception", "buff_val": 10, "buff2_type": "gathering", "buff2_val": 4,
     "flavor": "黄油煎菠菜。听起来简单，但是好吃的程度和简单程度完全不成正比。",
     "eat": "你叉了一叠菠菜——黄油还在叶子上发着光。放进嘴里的时候先是滑，然后是黄油的香，最后是菠菜那种带着微微涩感的绿味。你开始理解为什么有些人可以顿顿吃菠菜了。"},
    {"name": "牧羊人派", "en": "Shepherd's Pie", "price": 80,
     "buff_type": "gathering", "buff_val": 10, "buff2_type": "perception", "buff2_val": 4,
     "flavor": "蜥蜴人独有风味的羚羊肉派。上层是土豆泥，下层是碎肉，烤到表面金黄焦脆。",
     "eat": "你用叉子戳进派的表面——嘎嘣一声之后，下面的碎肉和土豆泥混在一起涌出来。第一口是焦皮的脆，第二口是肉的咸鲜，第三口你放弃了分析味道，专心吃了。"},
    # ── 品级 25-55 (中低级 100~300g) ──
    {"name": "鳗鱼派", "en": "Eel Pie", "price": 100,
     "buff_type": "gathering", "buff_val": 11, "buff2_type": "perception", "buff2_val": 4,
     "flavor": "用黑鳗做馅的烤派。鳗鱼肉在派皮里闷到酥软，汁水全锁在里面。切开的瞬间香气扑面。",
     "eat": "你切开派皮——热气带着鳗鱼的鲜香呼一下冲出来。鱼肉已经和酱汁融为一体，绵密得像在吃一团有味道的云。派皮底部被汁水泡得微软，但边缘还是脆的。你把盘子上的汁也用派皮蘸了。"},
    {"name": "清炖鬼鮟鱇", "en": "Orobon Stew", "price": 120,
     "buff_type": "gp", "buff_val": 27, "buff2_type": "gathering", "buff2_val": 4,
     "flavor": "以鬼鮟鱇的肝为主料的炖菜，营养丰富。看着凶，吃着鲜。汤色浓白，一碗下去什么疲劳都没了。",
     "eat": "你鼓起勇气舀了一勺——外表虽然不太好看，但入口的瞬间你忘了一切。鱼肝化在嘴里，浓到不像是汤而像是酱。鲜味从舌尖一路淌到嗓子。你端起碗直接喝了。"},
    {"name": "鳄梨色拉", "en": "Alligator Salad", "price": 130,
     "buff_type": "perception", "buff_val": 12, "buff2_type": "gp", "buff2_val": 11,
     "flavor": "鳄梨切片做成的色拉，加入了黑果醋调味。绵密的果肉配上微酸的醋汁，清爽又有饱腹感。",
     "eat": "你叉起一片鳄梨——绿色的果肉绵软得几乎要从叉子上滑下去。放进嘴里，先是黑果醋的酸在舌尖上跳了一下，然后是鳄梨那种浓郁的、奶油般的润。你吃得很慢，因为不想让它结束。"},
    {"name": "血红奇异果挞", "en": "Blood Currant Tart", "price": 140,
     "buff_type": "gathering", "buff_val": 12, "buff2_type": "gp", "buff2_val": 11,
     "flavor": "加入了很多血红奇异果的酸甜点心。红色的果肉铺满了整个挞面，看着就像一小片宝石田。",
     "eat": "你咬下去的瞬间，酸味先到——很冲，像是在舌头上按了个开关。然后甜味慢慢追上来。挞皮在中间打圆场，酥酥的，把酸和甜都托住了。你看着剩下的半个挞，果断一口塞进去。"},
    {"name": "酸泡菜", "en": "Sauerkraut", "price": 160,
     "buff_type": "perception", "buff_val": 14, "buff2_type": "gp", "buff2_val": 11,
     "flavor": "用盐腌制的甘蓝细丝。脆生生的，酸得恰到好处。配什么都合适，单吃也停不下来。",
     "eat": "你夹了一筷子——甘蓝丝还是脆的，嚼下去嘎吱嘎吱的。酸味很直接，不拐弯。你本来想只吃一口试试，结果手已经在伸向第二筷了。就是那种——不惊艳，但你会一直吃的东西。"},
    {"name": "香烩时蔬", "en": "Ratatouille", "price": 170,
     "buff_type": "gp", "buff_val": 29, "buff2_type": "perception", "buff2_val": 6,
     "flavor": "用薰衣草油炒制多种蔬菜，再用鸡高汤慢慢熬熟。每种蔬菜都保持着自己的口感，但融在一起又特别和谐。",
     "eat": "你舀了一勺——茄子、番茄、西葫芦、洋葱，每一块都吸饱了汤汁。薰衣草油的香气藏在最底下，你吃到第三口才发现它。蔬菜们的味道在嘴里轮流报到。你好像在一口里尝到了一整个菜园。"},
    {"name": "包心球蓟", "en": "Stuffed Artichoke", "price": 190,
     "buff_type": "perception", "buff_val": 16, "buff2_type": "gathering", "buff2_val": 6,
     "flavor": "将蟹肉和奶酪填入球蓟中一起用火烧烤。外面是球蓟的微苦和纤维感，里面是融化的奶酪和蟹肉的鲜。",
     "eat": "你掰开球蓟的外层叶瓣——里面的奶酪正在缓缓拉丝。蟹肉碎混在其中，已经和奶酪融为一体了。第一口先是球蓟叶独特的苦和脆，紧跟着奶酪的咸香把苦味全部接住。你一瓣一瓣地吃，直到只剩中间最嫩的芯。"},
    {"name": "王冠蛋糕", "en": "Crowned Pie", "price": 250,
     "buff_type": "gathering", "buff_val": 17, "buff2_type": "gp", "buff2_val": 12,
     "flavor": "伊修加德风味庆祝用蛋糕，上面有个王冠。据说吃到藏在里面的小瓷偶的人会有好运。",
     "eat": "你切了一块——蛋糕体松软绵密，表面的糖霜微微脆。你嚼了两口突然咬到一个硬硬的东西——是小瓷偶！你今天运气不错。蛋糕甜而不腻，带着一点点杏仁的香。你戴着'王冠'把剩下的也吃了。"},
    {"name": "清炖牛肉", "en": "Beef Stew", "price": 250,
     "buff_type": "gp", "buff_val": 30, "buff2_type": "gathering", "buff2_val": 7,
     "flavor": "用红酒慢慢炖出来的水牛肉。肉炖到用勺子就能切开，汤汁浓稠发红。这是一道需要时间的菜。",
     "eat": "你用勺子按了一下牛肉——它就那么散开了。放进嘴里，红酒的余味和牛肉的醇厚缠在一起，分不清谁是谁。汤汁浓稠得能挂在勺子上。你慢慢吃完了，然后坐了一会儿，觉得人生也没那么赶。"},
    {"name": "猎人风味水蜥饼", "en": "Trapper's Quiche", "price": 250,
     "buff_type": "gathering", "buff_val": 17, "buff2_type": "perception", "buff2_val": 7,
     "flavor": "在馅饼坯中加入奶油奶酪、鸡蛋、水蜥肉等材料烤制而成。猎人们的快手午餐——顶饱，好带，冷了也好吃。",
     "eat": "你咬了一口——馅饼皮很扎实，奶油奶酪让内馅变得丝滑。水蜥肉的口感意外地像鸡肉，嫩嫩的，混在蛋液和奶酪里完全没有违和感。这是那种装在口袋里走一天、饿了随时掏出来啃的食物。"},
    {"name": "泽梅尔家风味焗菜", "en": "Dzemael Gratin", "price": 280,
     "buff_type": "gp", "buff_val": 31, "buff2_type": "perception", "buff2_val": 8,
     "flavor": "泽梅尔家的传统焗菜，食材为水蜥尾肉和新薯。焗到表面起了一层金黄的脆壳，挖开里面是绵软的。",
     "eat": "你用勺子敲破表面的脆壳——嘎嘣一声，里面冒出热气。水蜥尾肉和新薯已经炖到分不清彼此了，混着浓浓的奶酪。你挖了一大勺，吹了吹，塞进嘴里。……烫的。但是好吃到你不想等它凉。"},
    {"name": "陷阱草沙拉", "en": "Landtrap Salad", "price": 280,
     "buff_type": "perception", "buff_val": 19, "buff2_type": "gp", "buff2_val": 12,
     "flavor": "将还在活动的陷阱草的叶子拌上橄榄油制成的沙拉。你没看错，叶子还在动。但味道意外地清新。",
     "eat": "你用叉子按住一片正在试图卷曲的叶子——把它塞进嘴里之前，它还挣扎了一下。口感脆脆的，有点像生菜但更有嚼劲。橄榄油包裹着一种奇特的微甜。你决定不去想它刚才在动这件事。"},
    {"name": "番茄派", "en": "Tomato Pie", "price": 280,
     "buff_type": "gathering", "buff_val": 19, "buff2_type": "perception", "buff2_val": 8,
     "flavor": "格里达尼亚风味派，用的是从花田中挑选出来的西红柿。番茄烤过之后甜度翻倍，和派皮特别搭。",
     "eat": "你切了一角——番茄的汁水已经渗进派皮里，让底部变成了好看的红色。第一口全是番茄的酸甜，浓烈而直接。派皮提供了一点酥脆的平衡。你本来在纠结吃一角还是两角，身体已经替你切好了第二角。"},
    # ── 品级 70-160 (中级 300~450g) ──
    {"name": "菠菜乳蛋饼", "en": "Spinach Quiche", "price": 300,
     "buff_type": "gathering", "buff_val": 24, "buff2_type": "perception", "buff2_val": 10,
     "flavor": "用馅饼坯做容器，加入菠菜和奶酪等材料，之后烤熟制成的蛋饼。切开能看到绿色和金黄交错的横截面。",
     "eat": "你切了一角——蛋液凝固后有一种绵密的弹性，菠菜的绿点缀其中。奶酪在烤制时融化了，现在变成了一层咸香的底。你一口咬下去，蛋香、奶酪香、菠菜的微涩，三样东西按顺序报到。你又切了一角。"},
    {"name": "黑线鳕沙拉", "en": "Haddock Dip", "price": 330,
     "buff_type": "perception", "buff_val": 28, "buff2_type": "gp", "buff2_val": 12,
     "flavor": "将哈拉尔黑线鳕的鱼籽与新薯混合在一起。别样的风味，深受北洋出身的鲁加人喜爱。",
     "eat": "你挖了一勺——粉色的鱼籽和白色的薯泥搅在一起，颜色很好看。入口先是薯泥的绵软，然后鱼籽在牙齿间一颗一颗地爆开，每一颗都释放出一小滴咸鲜。你开始理解鲁加人为什么喜欢这个了。"},
    {"name": "菜包肉", "en": "Stuffed Cabbage Rolls", "price": 380,
     "buff_type": "perception", "buff_val": 32, "buff2_type": "gp", "buff2_val": 16,
     "flavor": "将肉末卷入用水焯过的包心菜中，煮制而成。翠绿的菜叶裹着粉色的肉馅，一口下去两个世界。",
     "eat": "你夹起一个卷——菜叶被汤汁炖得半透明了。咬开的瞬间，肉馅的油脂和菜叶的清甜同时涌出来。肉是实在的，菜是清爽的，它们在你嘴里达成了某种完美的平衡。你又夹了一个。然后不小心又夹了一个。"},
    {"name": "千层长颈驼焗野菜", "en": "Dhalmel Gratin", "price": 390,
     "buff_type": "gathering", "buff_val": 32, "buff2_type": "perception", "buff2_val": 13,
     "flavor": "将长颈驼肉与野菜重叠摆放焗制而成。一层肉一层菜，焗到金黄起泡。",
     "eat": "你挖了一勺——穿过焦黄的奶酪层、长颈驼肉层、嫩绿的蔬菜层，像在挖一个好吃的三明治地层。每一层的味道微微不同，但奶酪把所有层都粘在一起了。你决定下一勺挖深一点。"},
    {"name": "千层长颈驼炖野菜", "en": "Dhalmel Fricassee", "price": 400,
     "buff_type": "perception", "buff_val": 36, "buff2_type": "gathering", "buff2_val": 13,
     "flavor": "将长颈驼肉与野菜放在一起炖制而成。肉质紧实有嚼劲，野菜吸满了肉汁的鲜。",
     "eat": "你舀了一勺——长颈驼肉比想象中嫩得多，在汤里炖到微微颤抖。野菜完全变成了肉汤的颜色，根本分不出原来是什么菜了。一口下去全是肉汁的浓鲜，蔬菜在里面打了个配合。你想了想，还是问了一下长颈驼是什么……不，还是不问了。"},
    {"name": "包心卡贝基", "en": "Stuffed Chysahl", "price": 420,
     "buff_type": "gp", "buff_val": 38, "buff2_type": "perception", "buff2_val": 14,
     "flavor": "将俄刻阿尼斯肉塞入卡贝基野菜中，再配上库尔札斯青葱制成。寒地的菜，扎实暖胃。",
     "eat": "你掰开一颗——热气从中间涌出来。卡贝基的叶子炖得又软又甜，肉馅被菜叶的汁水浸润后特别嫩。库尔札斯青葱的辣在最后才出现，在舌根上暖暖地烧了一下。你缩了缩围巾，又掰了一颗。"},
    {"name": "鲜红罗兰莓派", "en": "Snurbleberry Tart", "price": 450,
     "buff_type": "gathering", "buff_val": 37, "buff2_type": "gp", "buff2_val": 19,
     "flavor": "放满鲜红罗兰莓的水果派。红色的果肉铺满了整个派面，亮晶晶的像刚下过雨。",
     "eat": "你叉起一块——果酱在叉子上微微颤抖。咬下去的一瞬间，莓果的酸甜在嘴里炸开了。这种酸不是那种让人皱眉的酸，而是甜味的弹跳板——酸完之后甜味弹得更高。派皮被果汁染成了粉红色，酥得掉渣。你吃得满手都是。"},
    # ── 品级 210-290 (中高级 500~700g) ──
    {"name": "炖鮟鱇", "en": "Angler Stew", "price": 500,
     "buff_type": "perception", "buff_val": 43, "buff2_type": "gathering", "buff2_val": 17,
     "flavor": "将整条祭司鱼直接下锅炖，不要留一点残渣。听起来粗犷，但味道异常细腻。",
     "eat": "你看了看碗里的东西——确实看不出这曾经是条完整的鱼了。舀一口汤，浓到几乎能拉丝。鱼肉化在汤里，每一口都带着胶质感。你不确定自己在喝汤还是在吃鱼，但无论如何碗已经空了。"},
    {"name": "田园番茄面", "en": "Pasta Ortolano", "price": 550,
     "buff_type": "gathering", "buff_val": 34, "buff2_type": "perception", "buff2_val": 34,
     "buff3_type": "gp", "buff3_val": 13,
     "flavor": "在番茄酱上点缀时蔬，与细面拌在一起食用。红色酱汁里藏着五颜六色的蔬菜丁，像一幅能吃的画。",
     "eat": "你卷起一叉子面——番茄酱把每根面条都裹得红彤彤的。蔬菜丁在面条间躲躲藏藏，你得用叉子去找它们。一口下去是番茄的微酸、蔬菜的清甜、面条的弹牙。你吃得满嘴红酱，像个开心的小孩。"},
    {"name": "荞麦糊", "en": "Kasha", "price": 600,
     "buff_type": "perception", "buff_val": 56, "buff2_type": "gp", "buff2_val": 21,
     "flavor": "将荞麦粒混合其它材料翻炒，再加进肉汤中熬制而成的糊糊。朴素得毫无卖点的食物，但暖胃程度堪比在冬天挨冻时有人送来炭火。",
     "eat": "你舀了一勺——稠稠的糊，看起来不怎么样。但放进嘴里的时候，荞麦的谷物香和肉汤的浓鲜同时铺开来。口感粗粗的，但这种粗糙感反而让你觉得在吃真正的食物。你一勺一勺地舀，碗见底的速度超出了预期。"},
    {"name": "煮杂菜", "en": "Gameni", "price": 620,
     "buff_type": "gp", "buff_val": 42, "buff2_type": "gathering", "buff2_val": 23,
     "flavor": "将红角犀鸟的胸肉与各种根菜分别煮熟，再混合到一起。每一种食材都保持着各自的味道，但汤把它们团结在了一起。",
     "eat": "你拿筷子在碗里翻了翻——胸肉、莲藕、牛蒡、胡萝卜，每一样都煮得透透的但还保持着形状。咬一口胸肉，肉汁饱满；吃一块藕，脆糯兼有。你开始一样一样地吃，像在做一场小型的味觉巡礼。"},
    {"name": "游牧民风味肉饼", "en": "Nomad Meat Pie", "price": 630,
     "buff_type": "gathering", "buff_val": 57, "buff2_type": "perception", "buff2_val": 23,
     "flavor": "用蔬菜包裹犏牛的牛肩肉后炸制而成。游牧民在草原上一边骑马一边吃的便携食物，外酥内嫩。",
     "eat": "你拿起一个——外面炸得金黄，还微微烫手。咬下去的时候酥壳碎裂的声音很响，里面的肉馅冒出了热气。犏牛肉比普通牛肉更紧实，嚼着很有满足感。蔬菜的汁水混在肉里，让每一口都不会太干。你把碎在手心里的酥皮倒进嘴里。"},
    {"name": "长颈骆焗菜", "en": "Jhammel Moussaka", "price": 650,
     "buff_type": "perception", "buff_val": 58, "buff2_type": "gathering", "buff2_val": 23,
     "flavor": "将长颈骆肉与茄子煮炖的近东风味焗菜。焗到表面起泡金黄，挖开是一层肉一层菜的千层结构。",
     "eat": "你用勺子挖下去——穿过焦黄的表皮、绵软的茄子层、入味的长颈骆肉层，又是茄子，又是肉，像在挖一座好吃的地层。每一层的味道微微不同，但奶酪和香料的味道贯穿始终。你一勺一勺地往下挖，像个执着的考古学家。"},
    # ── 品级 320-418 (高级·原有菜) ──
    {"name": "金平糖", "en": "Konpeito", "price": 200,
     "buff_type": "perception", "buff_val": 68, "buff2_type": "gp", "buff2_val": 21,
     "flavor": "五颜六色的结晶砂糖，甜得像在嘴里放了一颗星星。嘎嘣脆。东洲的孩子最爱的零食。",
     "eat": "你把一颗金平糖丢进嘴里——嘎嘣。甜味像小小的烟花在舌尖上炸开。你又倒了几颗到手心，挑了一颗蓝色的。这次没咬，含着。糖慢慢融化，甜味从一个点变成一整片。"},
    {"name": "煎蘑菇", "en": "Mushroom Saute", "price": 750,
     "buff_type": "gathering", "buff_val": 76, "buff2_type": "perception", "buff2_val": 38,
     "flavor": "奶油蘑菇在锅里嗞嗞作响。黄油的香气和蘑菇的鲜味混在一起。简单、温暖、让人安心。",
     "eat": "你叉起一片蘑菇——黄油还在上面微微颤抖。放进嘴里，鲜味像是被慢慢拧开的水龙头，一点一点地流出来。蘑菇的滑和黄油的润缠在一起。你闭上眼睛嚼了很久。安心。"},
    {"name": "胡椒土豆", "en": "Peppered Popotoes", "price": 750,
     "buff_type": "gp", "buff_val": 50, "buff2_type": "gathering", "buff2_val": 38,
     "flavor": "波波豆削皮切块，撒上粗磨黑胡椒，烤到表面微焦。朴素但好吃。咬一口能听到咔嚓声。",
     "eat": "你拿起一块——表面还微微冒着热气。咬下去的瞬间先是咔嚓的焦皮，然后是绵软的内里，最后是黑胡椒在舌根上炸开的辛辣。朴素。但你已经伸手去拿第二块了。"},
    {"name": "咖啡饼干", "en": "Coffee Biscuit", "price": 750,
     "buff_type": "perception", "buff_val": 77, "buff2_type": "gp", "buff2_val": 28,
     "flavor": "黄油饼干里揉进了研磨咖啡粉。咬下去先是酥，然后是微苦的咖啡香，最后是奶油的回甘。",
     "eat": "你掰开饼干——断面上能看到深色的咖啡颗粒。第一口是黄油的酥，第二口是咖啡的苦，第三口……什么都没了。已经吃完了。你看着空空的手，有点怅然。"},
    # ── 品级 460-590 (满级前 800~1100g) ──
    {"name": "乌贼墨汁炒饭", "en": "Arros Negre", "price": 850,
     "buff_type": "perception", "buff_val": 93, "buff2_type": "gathering", "buff2_val": 42,
     "flavor": "将贻贝与邦巴米用乌贼墨汁煸炒而成的黑色炒饭。卖相吓人，味道惊艳。一端上来就是全场焦点。",
     "eat": "你看着面前乌黑发亮的炒饭犹豫了零点三秒，然后铲了一大勺。入口的瞬间你就释然了——海鲜的鲜甜、墨汁的浓郁、米饭的焦香在嘴里层层展开。贻贝弹牙得恰到好处。你舔舔嘴巴，知道现在自己的牙缝一定是黑色的。"},
    {"name": "蟹饼", "en": "Crab Cakes", "price": 900,
     "buff_type": "gp", "buff_val": 55, "buff2_type": "perception", "buff2_val": 47,
     "flavor": "蓝蟹肉拆碎拌进面糊，煎到两面金黄。外皮酥脆，蟹肉鲜甜弹牙。蘸一点酱更好吃。",
     "eat": "你叉起一块蟹饼——外面金黄酥脆，叉子按下去的时候能感觉到里面的弹性。咬开，蟹肉的鲜甜和面糊的焦香混在一起。你蘸了一点酱。更好了。你又蘸了很多酱。"},
    {"name": "胡萝卜丝", "en": "Carrot Nibbles", "price": 950,
     "buff_type": "gathering", "buff_val": 95, "buff2_type": "perception", "buff2_val": 49,
     "flavor": "使用果醋给切成细丝的开心胡萝卜调味后做成的开胃菜。简单、爽脆、色彩鲜亮。吃一口心情就好了。",
     "eat": "你夹了一筷子——胡萝卜丝细得透光，裹着薄薄一层果醋。入口嘎吱脆，甜味从胡萝卜本身来，酸味从果醋来，它们在你嘴里手拉手跳了一支舞。你吃完了一碟，发现心情确实变好了。名字没骗人。"},
    {"name": "亚考牛慕沙卡", "en": "Yakow Moussaka", "price": 1000,
     "buff_type": "gp", "buff_val": 55, "buff2_type": "gathering", "buff2_val": 60,
     "flavor": "将亚考牛肉与茄子煮炖的近东风味焗菜。比长颈骆版的更浓厚、更扎实——毕竟是牛。",
     "eat": "你挖了一勺——表面的奶酪已经焗到起了焦黄的泡泡。亚考牛肉的纤维比长颈骆粗一些，嚼起来更有在吃肉的实感。茄子软烂到成了肉与奶酪之间的缓冲带。你吃到后面，开始用面包蘸盘底的酱汁。一滴都没浪费。"},
    {"name": "高山茶饼干", "en": "Sideritis Cookie", "price": 1000,
     "buff_type": "perception", "buff_val": 101, "buff2_type": "gp", "buff2_val": 30,
     "flavor": "散发着高山茶香味的甜点。饼干酥脆，茶香清幽。适合在钓鱼等鱼咬钩的漫长午后慢慢吃。",
     "eat": "你掰了半块——饼干断面上能看到细碎的茶叶。先是黄油的酥，然后是砂糖的甜，最后高山茶的清香从最后面追上来，在鼻腔里停留了很久。你闭着眼嚼完了，觉得风里好像都带了茶味。又掰了半块。"},
    {"name": "炸墨鱼圈", "en": "Kalamarakia Tiganita", "price": 1100,
     "buff_type": "perception", "buff_val": 124, "buff2_type": "gathering", "buff2_val": 64,
     "flavor": "将墨鱼圈蘸满裸麦粉之后用紫苏油高温炸制。外衣金黄酥脆，里面的墨鱼弹牙有嚼劲。",
     "eat": "你夹起一个墨鱼圈——面衣炸得蓬松，金黄色的，还在微微冒油。咬下去的一口：嘎嘣的面衣碎裂声、弹牙的墨鱼肉在牙齿间回弹。紫苏油的香气和海味在嘴里混成了一种让你想去海边的味道。你又夹了三个。停不下来是炸物的错。"},
    # ── 品级 620-750 (满级 1100~1500g) ──
    {"name": "虾咖喱", "en": "Jhinga Curry", "price": 1200,
     "buff_type": "gathering", "buff_val": 136, "buff2_type": "gp", "buff2_val": 31,
     "flavor": "大虾在椰奶咖喱里慢炖。酱汁浓稠金黄，辛香料的层次在舌尖上一层一层绽开。配饭绝了。",
     "eat": "你舀了一大勺咖喱浇在饭上。浓稠的金色酱汁缓缓铺开。第一口——椰奶的温柔。第二口——辛香料在舌尖上绽开，一层，又一层。虾肉弹牙，带着微微的焦香。你把碗里的饭吃得干干净净，用勺子刮了两遍。"},
    {"name": "图拉尔菠萝蛋糕", "en": "Turali Pineapple Ponzecake", "price": 1200,
     "buff_type": "gathering", "buff_val": 151, "buff2_type": "perception", "buff2_val": 78,
     "flavor": "将切片菠萝放在上面烤制而成的蛋糕。在尤卡图拉尔举办庆典时，这种象征太阳的装饰十分受欢迎。",
     "eat": "你切了一块——上面的菠萝片烤到边缘微微焦糖化了，像一个小太阳。蛋糕体湿润绵密，菠萝的果汁渗进每一寸。甜味热情而直接，酸味在尾巴上翘了个尾巴。你看着盘子里剩下的蛋糕，心想：庆典嘛，多吃一块也合理。"},
    {"name": "酱炒饭", "en": "Nasi Goreng", "price": 1250,
     "buff_type": "gp", "buff_val": 58, "buff2_type": "gathering", "buff2_val": 80,
     "flavor": "在米饭中加入辣酱和胡椒翻炒，最后放入虾肉和蛋花做点缀。每一粒米饭都裹着酱色，粒粒分明。",
     "eat": "你铲了一大勺——米饭炒得粒粒分明，每一颗都裹着深色的酱汁。辣味不是很冲，但从第二口开始慢慢积累，到第五口的时候额头微微冒汗。虾肉弹牙，蛋花嫩滑。你把碗底最后几粒焦饭刮起来吃了——那是全碗最香的部分。"},
    {"name": "酿柿子椒", "en": "Stuffed Peppers", "price": 1300,
     "buff_type": "perception", "buff_val": 157, "buff2_type": "gp", "buff2_val": 32,
     "flavor": "将非常碎的羊驼肉馅与其它食材搅拌在一起，填入柿子椒里烤制而成。彩色的柿子椒像一排小碗，每个都装满了料。",
     "eat": "你拿起一个——柿子椒的皮烤得微皱但还保持着形状。咬下去先是椒皮的脆和微甜，然后是满满的肉馅。羊驼肉碎到几乎像沙，但用了足够的调味让它湿润多汁。你吃了红的吃绿的，吃了绿的吃黄的，想比较出哪个颜色最好吃。结论是都好吃。"},
    {"name": "香煎面拖旗鱼", "en": "Cloudsail Meuniere", "price": 1400,
     "buff_type": "perception", "buff_val": 176, "buff2_type": "gathering", "buff2_val": 91,
     "flavor": "旗鱼裹上小麦面糊烹制成的美味佳肴。面衣薄薄一层，锁住了鱼肉全部的鲜甜。",
     "eat": "你切了一块——刀穿过薄薄的面衣，下面是雪白紧实的旗鱼肉。面衣煎得恰到好处，不抢味，只是给鱼肉穿了一件酥脆的外套。鱼肉本身的鲜甜在嘴里慢慢展开，完全不需要任何酱料。你决定这是你吃过最体面的一条鱼。"},
    {"name": "黄金鳗鱼派", "en": "Goldentail Pie", "price": 1500,
     "buff_type": "gathering", "buff_val": 188, "buff2_type": "perception", "buff2_val": 97,
     "flavor": "将黄金鳗包入派皮烤制成的鱼派。品级最高的采集食物——鳗鱼的油脂渗进派皮，金灿灿的，名副其实。",
     "eat": "你切开派皮的瞬间——金色的油脂涌了出来，整个空气都变得鲜美。黄金鳗的肉质比普通鳗鱼更细腻，入口即化但又留着一丝弹性。派皮吸满了鳗鱼的油脂，酥得已经不能用脆来形容了，更像是在嘴里融化。你吃完之后在原地坐了一会儿。你觉得这大概就是钓鱼的意义。"},
]


# ── 调味料查找 ──────────────────────────────────────
def find_seasoning(name: str):
    n = name.strip()
    for cn, info in SEASONINGS.items():
        if n in (cn, info["id"]):
            return cn, info
    for cn, info in SEASONINGS.items():
        if n in cn or n == info["id"]:
            return cn, info
    return None, None


def find_recipe(name: str):
    n = name.strip().lower()
    for r in FISH_RECIPES:
        if n in (r["name"].lower(), r["en"].lower()):
            return r
    for r in FISH_RECIPES:
        if n in r["name"].lower() or n in r["en"].lower():
            return r
    return None


def find_shop_food(name: str):
    n = name.strip().lower()
    for f in SHOP_FOOD:
        if n in (f["name"].lower(), f["en"].lower()):
            return f
    for f in SHOP_FOOD:
        if n in f["name"].lower() or n in f["en"].lower():
            return f
    return None


# ── buff 格式化 ──────────────────────────────────────
_BUFF_NAMES = {"gathering": "获得力", "perception": "鉴别力",
               "gp": "GP", "xp": "经验"}


def _fmt_one(bt, bv):
    if bt == "xp":
        return f"+{bv}%{_BUFF_NAMES.get(bt, bt)}"
    return f"+{bv} {_BUFF_NAMES.get(bt, bt)}"


def fmt_food_buff(food: dict) -> str:
    """把食物的 buff 格式化成一行文字。"""
    parts = [_fmt_one(food["buff_type"], food["buff_val"])]
    if food.get("buff2_type"):
        parts.append(_fmt_one(food["buff2_type"], food["buff2_val"]))
    if food.get("buff3_type"):
        parts.append(_fmt_one(food["buff3_type"], food["buff3_val"]))
    parts.append("+3%经验")
    return ", ".join(parts)


# ── buff 管理 ──────────────────────────────────────
def apply_buff(state: dict, food: dict, now: float):
    buff = {
        "food_name": food["name"],
        "expires": now + BUFF_DURATION,
        "xp_bonus": XP_BONUS,
    }
    buff[food["buff_type"]] = food["buff_val"]
    if food.get("buff2_type"):
        buff[food["buff2_type"]] = food.get("buff2_val", 0) + buff.get(food["buff2_type"], 0)
    if food.get("buff3_type"):
        buff[food["buff3_type"]] = food.get("buff3_val", 0) + buff.get(food["buff3_type"], 0)
    state["food_buff"] = buff


def get_active_buff(state: dict, now: float) -> dict | None:
    buff = state.get("food_buff")
    if not buff:
        return None
    if now > buff.get("expires", 0):
        state.pop("food_buff", None)
        return None
    return buff


def buff_summary(state: dict, now: float) -> str:
    buff = get_active_buff(state, now)
    if not buff:
        return ""
    remain = int(buff["expires"] - now)
    mins = remain // 60
    secs = remain % 60
    effects = []
    for k in ("gathering", "perception", "gp", "xp"):
        if k in buff and k != "xp_bonus":
            effects.append(_fmt_one(k, buff[k]))
    effects.append("+3%经验")
    return f"🍽{buff['food_name']}({', '.join(effects)}) {mins}:{secs:02d}"


def xp_multiplier(state: dict, now: float) -> float:
    buff = get_active_buff(state, now)
    if buff:
        return 1.0 + buff.get("xp_bonus", 0) + buff.get("xp", 0) / 100
    return 1.0


def gathering_bonus(state: dict, now: float) -> int:
    buff = get_active_buff(state, now)
    if buff:
        return buff.get("gathering", 0)
    return 0


def perception_bonus(state: dict, now: float) -> int:
    buff = get_active_buff(state, now)
    if buff:
        return buff.get("perception", 0)
    return 0


def gp_bonus(state: dict, now: float) -> int:
    buff = get_active_buff(state, now)
    if buff:
        return buff.get("gp", 0)
    return 0
