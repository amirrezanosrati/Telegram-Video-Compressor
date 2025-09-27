import os
import asyncio
from telethon import TelegramClient, events
from pathlib import Path
import subprocess

# ----------------- تنظیمات ----------------- #
api_id = int(os.getenv("API_ID"))      # از my.telegram.org
api_hash = os.getenv("API_HASH")       # از my.telegram.org
bot_token = os.getenv("BOT_TOKEN")     # توکن بات

OUTPUT_DIR = Path("/tmp/videos")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

client = TelegramClient('bot_session', api_id, api_hash).start(bot_token=bot_token)

# ----------------- دستور /start ----------------- #
@client.on(events.NewMessage(pattern="/start"))
async def start(event):
    await event.respond("✅ ربات فعال شد!\n🎥 لطفا یک ویدیو ارسال کن.")

# ----------------- فشرده‌سازی ویدیو ----------------- #
async def compress_video(input_path: Path, output_path: Path, event):
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

    msg = await event.respond("⏳ شروع فشرده‌سازی...")

    while True:
        line = await process.stderr.readline()
        if not line:
            break
        line = line.decode()
        if "time=" in line:
            await msg.edit("🎬 در حال فشرده‌سازی...")

    await process.wait()
    await msg.edit("✅ فشرده‌سازی تمام شد!")

# ----------------- هندل ویدیو ----------------- #
@client.on(events.NewMessage())
async def handle_video(event):
    if event.video or (event.document and event.document.mime_type.startswith("video")):
        await event.respond("⬇️ در حال دانلود ویدیو...")
        video = event.video or event.document
        in_file = OUTPUT_DIR / f"{video.id}.mp4"
        out_file = OUTPUT_DIR / f"{video.id}_compressed.mp4"

        await client.download_media(video, in_file)

        await compress_video(in_file, out_file, event)

        await event.respond("⬆️ در حال آپلود ویدیو...")
        await client.send_file(event.chat_id, out_file)
        await event.respond("🎉 آماده شد!")

# ----------------- اجرای ربات ----------------- #
print("🤖 ربات فعال شد و منتظر ویدیو است...")
client.run_until_disconnected()
