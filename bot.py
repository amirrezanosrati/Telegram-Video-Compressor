import os
from pyrogram import Client, filters
from pyrogram.types import Message

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
PUBLIC_URL = os.environ.get("PUBLIC_URL")  # URL عمومی cloudflared یا ngrok
UPLOAD_FOLDER = "uploads"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

bot = Client("file_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


def progress_bar(current, total, length=20):
    """برگرداندن درصد و نوار پیشرفت"""
    percent = current / total
    filled = int(length * percent)
    bar = "█" * filled + "-" * (length - filled)
    return f"[{bar}] {percent*100:.1f}%"


async def download_file(message: Message):
    file_name = os.path.join(UPLOAD_FOLDER, message.document.file_name)
    # پیام اولیه برای نوار پیشرفت
    status_message = await message.reply_text("⏳ شروع دانلود...")
    
    # دانلود با callback برای پیشرفت
    await message.download(
        file_name,
        progress=lambda d, t: update_progress(d, t, status_message)
    )

    # ارسال لینک عمومی بعد از اتمام
    file_url = f"{PUBLIC_URL}/{file_name}"
    await status_message.edit(f"✅ دانلود کامل شد!\n📎 لینک دانلود: {file_url}")


async def update_progress(downloaded, total, status_message):
    bar = progress_bar(downloaded, total)
    await status_message.edit(f"⏳ در حال دانلود...\n{bar}")


@bot.on_message(filters.document | filters.video)
async def handle_media(client, message):
    try:
        await download_file(message)
    except Exception as e:
        await message.reply_text(f"❌ خطا در پردازش فایل: {e}")


@bot.on_message(filters.command("start"))
async def start_command(client, message):
    await message.reply_text("🤖 ربات فعال شد! لطفا فایل یا ویدیو ارسال کنید.")


bot.run()
