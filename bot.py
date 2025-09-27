import os, subprocess, logging, threading, http.server, socketserver, time
from pathlib import Path
from tqdm import tqdm
from pyngrok import ngrok
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("TELEGRAM_TOKEN")
OUTPUT_DIR = Path("/tmp/videos")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PORT = 8080
ngrok.set_auth_token(os.getenv("NGROK_TOKEN"))  # توکن ngrok توی Secrets بذار
public_url = ngrok.connect(PORT, "http").public_url
logging.info(f"Ngrok URL: {public_url}")

# سرور HTTP برای سرو کردن فایل‌ها
def start_http_server():
    Handler = http.server.SimpleHTTPRequestHandler
    os.chdir(OUTPUT_DIR)
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        logging.info(f"Serving at port {PORT}")
        httpd.serve_forever()

threading.Thread(target=start_http_server, daemon=True).start()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام 👋 ویدیو بفرست تا فشرده کنم. لینک دانلود با ngrok برمی‌گردونم.")

def compress_with_progress(input_path: Path, output_path: Path):
    # اجرای ffmpeg با نوار ابزار
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-c:a", "aac", "-b:a", "128k", str(output_path)
    ]
    process = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True)
    pbar = tqdm(total=100, desc="Compressing", ncols=70)

    for line in process.stderr:
        if "time=" in line:
            # تقریبی: درصد رو شبیه‌سازی می‌کنیم
            pbar.update(1 if pbar.n < 100 else 0)
    process.wait()
    pbar.close()

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video or update.message.document
    if not video:
        await update.message.reply_text("لطفاً فقط ویدیو بفرست 🙂")
        return

    await update.message.reply_text("⏳ دریافت فایل...")
    file = await context.bot.get_file(video.file_id)
    in_file = OUTPUT_DIR / f"{video.file_id}.mp4"
    out_file = OUTPUT_DIR / f"{video.file_id}_compressed.mp4"
    await file.download_to_drive(str(in_file))

    await update.message.reply_text("🎬 در حال فشرده‌سازی (با نوار پیشرفت روی سرور)...")
    compress_with_progress(in_file, out_file)

    # لینک ngrok
    link = f"{public_url}/{out_file.name}"
    await update.message.reply_text(f"✅ فشرده‌سازی انجام شد.\nلینک دانلود:\n{link}")

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
