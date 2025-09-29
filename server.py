import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import subprocess

# مقادیر خودتو اینجا بزار
API_ID = 26283124
API_HASH = "c643f9861f5ef105a7c1e68b0d3ed5d1"
BOT_TOKEN = "7897337548:AAGudjNDkUM5pUWx93mdc6kFBrSqusuj_NA"

app = Client("video_compressor_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# مسیر پوشه دانلود
DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)


# وقتی ویدیو فرستاده میشه
@app.on_message(filters.video)
async def video_handler(client, message):
    file_path = await message.download(DOWNLOAD_DIR)
    await message.reply_text(
        "کیفیت خروجی رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📹 720p", callback_data=f"compress|{file_path}|720")],
                [InlineKeyboardButton("📹 480p", callback_data=f"compress|{file_path}|480")]
            ]
        )
    )


# هندلر برای دکمه‌ها
@app.on_callback_query()
async def callback_handler(client, callback_query):
    data = callback_query.data.split("|")
    if data[0] == "compress":
        file_path = data[1]
        quality = data[2]

        await callback_query.message.edit_text(f"⏳ در حال فشرده‌سازی به {quality}p ...")

        output_path = f"{file_path}_{quality}p.mp4"

        # دستور ffmpeg
        if quality == "720":
            cmd = ["ffmpeg", "-i", file_path, "-vf", "scale=-1:720", "-c:v", "libx264", "-crf", "28", "-preset", "veryfast", output_path]
        elif quality == "480":
            cmd = ["ffmpeg", "-i", file_path, "-vf", "scale=-1:480", "-c:v", "libx264", "-crf", "28", "-preset", "veryfast", output_path]

        process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        await process.communicate()

        if os.path.exists(output_path):
            await client.send_video(
                chat_id=callback_query.message.chat.id,
                video=output_path,
                caption=f"✅ ویدیو فشرده شده در {quality}p"
            )
            os.remove(output_path)
        else:
            await callback_query.message.edit_text("❌ خطا در فشرده‌سازی")

        # پاک کردن فایل اصلی بعد از کار
        if os.path.exists(file_path):
            os.remove(file_path)


app.run()
