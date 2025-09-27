import os
import subprocess
import logging
import threading
import http.server
import socketserver
from pathlib import Path
from tqdm import tqdm
from pyngrok import ngrok
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)
import asyncio
import nest_asyncio

# ──────────────────────────────── تنظیمات ──────────────────────────────── #

# گرفتن توکن‌ها
TOKEN = os.getenv("TELEGRAM_TOKEN")
NGROK_AUTH = os.getenv("NGROK_TOKEN")

# تنظیمات مسیر
OUTPUT_DIR = Path("/tmp/videos")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# تنظیمات سرور
PORT = 8080

# ──────────────────────────────── لاگ ──────────────────────────────── #
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ──────────────────────────────── ngrok ──────────────────────────────── #
ngrok.set_auth_token(NGROK_AUTH)
public_url = ngrok.connect(PORT, "http").public_url
logger.info(f"Ngrok URL: {public_url}")

# ──────────────────────────────── HTTP Server ──────────────────────────────── #
def start_http_server():
    Handler = http.server.SimpleHTTPRequestHandler
    os.chdir(OUTPUT_DIR)
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        logger.info(f"Serving at port {PORT}")
        httpd.serve_forever()

threading.Thread(target=start_http_server, daemon=True).start()

# ──────────────────────────────── Bot Command: /start ──────────────────────────────── #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 سلام! ویدیو بفرست تا فشرده کنم و لینک دانلود بدم.")

# ──────────────────────────────── فشرده‌سازی با tqdm ──────────────────────────────── #
def compress_with_progress(input_path: Path, output_path: Path):
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-c:a", "aac", "-b:a", "128k", str(output_path)
    ]
    process = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True)
    pbar = tqdm(total=100, desc="🎬 در حال فشرده‌سازی", ncols=70)

    for line in process.stderr:
        if "time=" in line:
            pbar.update(1 if pbar.n < 100 else 0)
    process.wait()
    pbar.close()

# ──────────────────────────────── هندل ویدیو ──────────────────────────────── #
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video or update.message.document
    if not video:
        await update.message.reply_text("⚠️ لطفاً یک ویدیو بفرست.")
        return

    await update.message.reply_text("⏳ دریافت فایل...")
    file = await context.bot.get_file(video.file_id)
    in_file = OUTPUT_DIR / f"{video.file_id}.mp4"
    out_file = OUTPUT_DIR / f"{video.file_id}_compressed.mp4"
    await file.download_to_drive(str(in_file))

    await update.message.reply_text("🎬 در حال فشرده‌سازی... لطفاً صبر کنید.")
    compress_with_progress(in_file, out_file)

    link = f"{public_url}/{out_file.name}"
    await update.message.reply_text(f"✅ فشرده‌سازی تمام شد!\n📥 لینک دانلود:\n{link}")

# ──────────────────────────────── main ──────────────────────────────── #
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
    await app.run_polling()

# ──────────────────────────────── اجرا ──────────────────────────────── #
if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())
