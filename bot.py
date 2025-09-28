import os
import time
from pyrogram import Client, filters
from pyrogram.types import Message

# === متغیرهای محیطی ===
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
PUBLIC_URL = os.environ.get("PUBLIC_URL")  # لینک عمومی cloudflared/ngrok
UPLOAD_FOLDER = "uploads"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

bot = Client("file_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# === نوار پیشرفت متن محور ===
def progress_bar(current, total, length=20):
    percent = current / total
    filled = int(length * percent)
    bar = "█" * filled + "-" * (length - filled)
    # نمایش درصد و حجم دانلود شده
    return f"[{bar}] {percent*100:.1f}% ({current//1024}KB/{total//1024}KB)"

# === دانلود فایل با نوار پیشرفت واقعی ===
last_update_time = 0  # برای محدود کردن آپدیت پیام

async def update_progress(downloaded, total, status_message):
    global last_update_time
    now = time.time()
    percent = downloaded / total * 100

    # فقط هر 1 ثانیه یا هر 2 درصد آپدیت کن
    if now - last_update_time > 1 or int(percent) % 2 == 0:
        bar = progress_bar(downloaded, total)
        try:
            await status_message.edit(f"⏳ در حال دانلود...\n{bar}")
        except:
            pass  # اگر پیام حذف شد یا خطا گرفتیم، ignore
        last_update_time = now

async def download_file(message: Message):
    # تشخیص نوع فایل و نام فایل
    if message.document:
        file_name = message.document.file_name
    elif message.video:
        file_name = message.video.file_name or f"video_{message.video.file_id}.mp4"
    else:
        file_name = f"file_{message.message_id}"

    file_path = os.path.join(UPLOAD_FOLDER, file_name)

    # پیام اولیه برای نوار پیشرفت
    status_message = await message.reply_text("⏳ شروع دانلود...")

    # دانلود با callback برای پیشرفت
    await message.download(
        file_path,
        progress=lambda d, t: update_progress(d, t, status_message)
    )

    # ارسال لینک عمومی بعد از اتمام
    file_url = f"{PUBLIC_URL}/{file_name}"
    await status_message.edit(f"✅ دانلود کامل شد!\n📎 لینک دانلود: {file_url}")

# === هندلر پیام‌ها ===
@bot.on_message(filters.document | filters.video)
async def handle_media(client, message):
    try:
        await download_file(message)
    except Exception as e:
        await message.reply_text(f"❌ خطا در پردازش فایل: {e}")

@bot.on_message(filters.command("start"))
async def start_command(client, message):
    await message.reply_text("🤖 ربات فعال شد! لطفا فایل یا ویدیو ارسال کنید.")

# === اجرای ربات ===
if __name__ == "__main__":
    bot.run()
