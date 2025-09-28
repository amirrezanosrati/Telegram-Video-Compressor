# Script.py
import asyncio
import threading
from bot import bot
from server import app

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# سرور Flask در یک Thread
threading.Thread(target=run_flask).start()

# ربات تلگرام
bot.run()
