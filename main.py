"""
Fast-Food Bot Root Launcher
Delegates execution to fastfood_bot/bot.py
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FASTFOOD_BOT_DIR = os.path.join(BASE_DIR, "fastfood_bot")

if FASTFOOD_BOT_DIR not in sys.path:
    sys.path.insert(0, FASTFOOD_BOT_DIR)

os.chdir(FASTFOOD_BOT_DIR)

if __name__ == "__main__":
    import bot
