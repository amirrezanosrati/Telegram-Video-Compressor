import os
import logging
from pyrogram import Client, filters
from flask import Flask
import subprocess

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "")

logging.basicConfig(level=logging.INFO)

# Flask app برای زنده نگه داشتن سرویس
app = Flask(__name__)

@app.route("/")
def home():
    return "🤖 Bot is running with GitHub Actions + ngrok"

# پوشه آپلود
if not os.path.exists("uploads"):
    os.makedirs("uploads")

# ساخت کلاینت تلگرام
bot = Client(
    "CompressorBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply("سلام 👋\nفایل یا ویدیو بفرست تا برات لینک دانلود عمومی بسازم ✅")

@bot.on_message(filters.document | filters.video | filters.audio)
async def handle_media(client, message):
    msg = await message.reply("⬇️ در حال دریافت فایل ...")

    file_path = await message.download(file_name="uploads/")
    filename = os.path.basename(file_path)

    # فشرده‌سازی با ffmpeg
    compressed_path = f"uploads/compressed_{filename}"
    await msg.edit("🎞 در حال فشرده‌سازی ...")
    try:
        subprocess.run(
            ["ffmpeg", "-i", file_path, "-vcodec", "libx264", "-crf", "28", compressed_path],
            check=True
        )
    except Exception as e:
        await msg.edit(f"❌ خطا در فشرده‌سازی: {e}")
        return

    # ساخت لینک
    download_url = f"{PUBLIC_URL}/uploads/compressed_{filename}"
    await msg.edit(f"✅ آماده شد!\n📥 [دانلود فایل فشرده]({download_url})", disable_web_page_preview=True)

# اجرای بات
bot.start()
