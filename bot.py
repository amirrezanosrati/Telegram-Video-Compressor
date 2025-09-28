# bot.py
import os
import uuid
import threading
import http.server
import socketserver
import logging
from pyrogram import Client, filters

logging.basicConfig(level=logging.INFO)

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
PORT = int(os.getenv("PORT", "8080"))

UPLOADS = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOADS, exist_ok=True)

# start simple threaded HTTP server to serve uploads
class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

def start_http_server():
    os.chdir(UPLOADS)
    handler = http.server.SimpleHTTPRequestHandler
    httpd = ThreadingHTTPServer(("", PORT), handler)
    logging.info(f"HTTP server started on port {PORT}, serving {UPLOADS}")
    httpd.serve_forever()

http_thread = threading.Thread(target=start_http_server, daemon=True)
http_thread.start()

# initialize pyrogram bot
app = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.command("start"))
async def start_cmd(c, m):
    await m.reply_text("سلام 👋 فایل یا ویدیو بفرست تا فشرده کنم و لینک بدم.")

@app.on_message(filters.document | filters.video | filters.audio | filters.photo)
async def handle_media(c, m):
    info = await m.reply_text("⬇️ دریافت فایل... لطفا صبر کن")
    try:
        # download media into uploads/ with unique name
        unique = uuid.uuid4().hex
        saved = await c.download_media(m, file_name=f"{unique}")
        if not saved:
            await info.edit_text("❌ دانلود ناموفق بود.")
            return

        # try to infer extension from original filename if present
        orig_name = (m.document.file_name if m.document else None) if m.document or m.video or m.audio else None
        if orig_name and "." in orig_name:
            ext = orig_name.split(".")[-1]
            saved_path = f"{saved}.{ext}"
            os.rename(saved, saved_path)
        else:
            saved_path = saved  # may have no extension

        # OPTIONAL: run ffmpeg compression here if you want (skip for now)
        # For demo we just keep original as "compressed" output
        compressed_name = f"out_{os.path.basename(saved_path)}"
        compressed_path = os.path.join(UPLOADS, compressed_name)
        os.replace(saved_path, compressed_path)  # move/rename

        if not PUBLIC_URL:
            await info.edit_text("⚠️ PUBLIC_URL تنظیم نشده؛ لینک عمومی در دسترس نیست.")
            return

        download_link = f"{PUBLIC_URL}/{compressed_name}"
        await info.edit_text(f"✅ آماده شد!\n🔗 لینک دانلود:\n{download_link}")
    except Exception as e:
        await info.edit_text(f"❌ خطا در پردازش: {e}")

if __name__ == "__main__":
    if API_ID == 0 or not API_HASH or not BOT_TOKEN:
        logging.error("Missing API_ID / API_HASH / BOT_TOKEN environment variables.")
        raise SystemExit(1)
    logging.info("Starting bot (Pyrogram)...")
    app.run()
