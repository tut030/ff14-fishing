"""
一键开玩 —— 命令行里跑:  python play.py   (Mac: python3 play.py)
然后像聊天一样输入命令, 回车即可:
    look           看此处: 时间/天气/能钓的鱼
    cast           抛竿
    goto 钓场名     换钓场     (例: goto Moraby Bay)
    spots          可去的钓场
    bag            渔获/点数
    status 鱼名     某鱼几点开 (例: status Mahi-Mahi)
    quit           退出(进度已自动存)
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from engine.game import Game


def main():
    g = Game(slot="player")          # 进度存在 saves/player.json, 自动备份
    print("🎣  FF14 钓鱼 · 拉诺西亚")
    print("（输入命令回车; 不知道玩啥就输 help; 退出输 quit）\n")
    print(g.cmd("look"))
    while True:
        try:
            text = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见! 进度已存。")
            break
        if text.lower() in ("quit", "exit", "q"):
            print("再见! 进度已存。")
            break
        print(g.cmd(text))


if __name__ == "__main__":
    main()
