import os
import logging
import asyncio
import nest_asyncio
import subprocess
from pathlib import Path
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

# ────────────── تنظیمات ────────────── #
TOKEN = os.getenv("TELEGRAM_TOKEN")
OUTPUT_DIR = Path("/tmp/videos")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ────────────── دستور /start ────────────── #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ ربات فعال شد!\n🎥 لطفا یک ویدیو ارسال کن.")

# ────────────── فشرده‌سازی ویدیو ────────────── #
async def compress_video(input_path: Path, output_path: Path, update: Update, context: ContextTypes.DEFAULT_TYPE):
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-c:a", "aac", "-b:a", "128k", str(output_path)
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    progress_msg = await update.message.reply_text("⏳ شروع فشرده‌سازی...")

    total_updates = 0
    while True:
        line = await process.stderr.readline()
        if not line:
            break
        line = line.decode("utf-8", errors="ignore")
        if "time=" in line:
            total_updates += 1
            if total_updates % 5 == 0:
                await progress_msg.edit_text(f"🎬 در حال فشرده‌سازی...\nپیشرفت: {total_updates}%")

    await process.wait()
    await progress_msg.edit_text("✅ فشرده‌سازی تمام شد!")

# ────────────── هندل ویدیو ────────────── #
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video or update.message.document
    if not video:
        await update.message.reply_text("⚠️ لطفاً یک ویدیو ارسال کنید.")
        return

    await update.message.reply_text("⬇️ در حال دانلود ویدیو...")
    file = await context.bot.get_file(video.file_id)
    in_file = OUTPUT_DIR / f"{video.file_id}.mp4"
    out_file = OUTPUT_DIR / f"{video.file_id}_compressed.mp4"
    await file.download_to_drive(str(in_file))

    await compress_video(in_file, out_file, update, context)

    await update.message.reply_text("⬆️ در حال آپلود ویدیو...")
    await update.message.reply_video(video=open(out_file, "rb"))
    await update.message.reply_text("🎉 آماده شد!")

# ────────────── اجرای ربات ────────────── #
if __name__ == "__main__":
    nest_asyncio.apply()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))

    logger.info("🤖 ربات فعال شد و منتظر ویدیو است...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
