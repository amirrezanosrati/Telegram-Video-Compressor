import os, subprocess, logging
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام 👋 من روی GitHub Actions ران شدم! ویدیو بفرست تا برات فشرده کنم.")

def compress_video(input_path, output_path):
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-c:a", "aac", "-b:a", "128k", output_path
    ]
    subprocess.run(cmd, check=True)

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video or update.message.document
    if not video:
        await update.message.reply_text("لطفاً فقط ویدیو بفرست 🙂")
        return

    file = await context.bot.get_file(video.file_id)
    in_file = "input.mp4"
    out_file = "output.mp4"
    await file.download_to_drive(in_file)

    await update.message.reply_text("⏳ در حال فشرده‌سازی...")
    compress_video(in_file, out_file)

    with open(out_file, "rb") as f:
        await context.bot.send_document(chat_id=update.effective_chat.id, document=InputFile(f, "compressed.mp4"))

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
