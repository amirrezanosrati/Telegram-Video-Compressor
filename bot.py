# bot.py
import os
import time
import uuid
from pyrogram import Client, filters
from pyrogram.types import Message

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "").rstrip("/")
UPLOAD_FOLDER = "uploads"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

bot = Client("file_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

_last_update = {}

def progress_bar(current, total, length=20):
    if total == 0:
        return f"[{'-'*length}] 0.0% (0KB/0KB)"
    percent = current / total
    filled = int(length * percent)
    bar = "█" * filled + "-" * (length - filled)
    return f"[{bar}] {percent*100:.1f}% ({current//1024}KB/{total//1024}KB)"

async def _update_progress(chat_id, message_id, downloaded, total):
    key = f"{chat_id}:{message_id}"
    now = time.time()
    last = _last_update.get(key, 0)
    percent = 0 if total == 0 else (downloaded/total*100)
    # محدودسازی به هر 1 ثانیه یا هر 2 درصد
    if now - last < 1 and int(percent) % 2 != 0:
        return
    _last_update[key] = now
    text = f"⏳ در حال دانلود...\n{progress_bar(downloaded, total)}"
    try:
        await bot.edit_message_text(chat_id, message_id, text)
    except Exception:
        pass

async def download_with_progress(message: Message):
    # تعیین اسم فایل به صورت امن
    if message.document:
        orig = message.document.file_name
    elif message.video:
        orig = message.video.file_name or f"video_{message.video.file_id}.mp4"
    else:
        orig = f"file_{message.message_id}"

    safe_name = orig.replace("/", "_").replace("..", "_")
    local_path = os.path.join(UPLOAD_FOLDER, safe_name)

    # پیام وضعیت اولیه
    info = await message.reply_text("⏳ شروع دانلود...")
    chat_id = info.chat.id
    msg_id = info.message_id

    # callback برای Pyrogram
    def progress_callback(downloaded, total):
        # Pyrogram callback sync — schedule edit via bot.loop
        try:
            bot.loop.create_task(_update_progress(chat_id, msg_id, downloaded, total))
        except Exception:
            pass

    # دانلود
    saved_path = await message.download(file_name=local_path, progress=progress_callback)

    # در انتها لینک بساز
    if not PUBLIC_URL:
        await info.edit_text("⚠️ PUBLIC_URL تنظیم نشده — لینک عمومی در دسترس نیست.")
        return

    download_link = f"{PUBLIC_URL}/{os.path.basename(saved_path)}"
    await info.edit_text(f"✅ دانلود کامل شد!\n🔗 لینک دانلود:\n{download_link}")

@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    await message.reply_text("سلام! فایل یا ویدیو بفرست تا لینکش رو بدم.")

@bot.on_message(filters.document | filters.video | filters.audio | filters.photo)
async def handler(client, message):
    try:
        await download_with_progress(message)
    except Exception as e:
        await message.reply_text(f"❌ خطا در پردازش فایل: {e}")

if __name__ == "__main__":
    bot.run()
