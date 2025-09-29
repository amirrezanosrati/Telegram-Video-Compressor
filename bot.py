import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, CallbackContext
from telegram.constants import ParseMode
import subprocess
import tempfile
import time
from typing import Tuple
import aiofiles

# تنظیمات لاگ دقیق‌تر
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # تغییر به DEBUG برای اطلاعات بیشتر
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')

async def debug_file_download(file, file_path):
    """تابع دیباگ برای دانلود فایل"""
    try:
        logger.info(f"Starting download - File ID: {file.file_id}, Size: {file.file_size}")
        
        total_size = file.file_size
        downloaded = 0
        start_time = time.time()
        
        async with aiofiles.open(file_path, 'wb') as f:
            async for chunk in file.iter_bytes(chunk_size=65536):
                if chunk:
                    await f.write(chunk)
                    downloaded += len(chunk)
                    
                    # لاگ هر 5 ثانیه
                    if time.time() - start_time >= 5:
                        logger.info(f"Download progress: {downloaded}/{total_size} ({downloaded/total_size*100:.1f}%)")
                        start_time = time.time()
        
        logger.info(f"Download completed: {downloaded} bytes")
        return True
        
    except Exception as e:
        logger.error(f"Download error: {e}", exc_info=True)
        return False

async def handle_video(update: Update, context: CallbackContext):
    """Handler ساده‌شده برای تست"""
    user = update.message.from_user
    logger.info(f"Processing video from user {user.id}")
    
    try:
        # مرحله 1: تشخیص ویدیو
        video = None
        if update.message.video:
            video = update.message.video
            logger.info("Video detected via message.video")
        elif update.message.document:
            doc = update.message.document
            mime_type = getattr(doc, 'mime_type', '')
            if mime_type and mime_type.startswith('video/'):
                video = doc
                logger.info("Video detected via document with video MIME type")
        
        if not video:
            await update.message.reply_text("❌ لطفاً یک ویدیو ارسال کنید")
            return
        
        # ارسال پیام شروع
        start_msg = await update.message.reply_text("🔍 در حال بررسی ویدیو...")
        
        # مرحله 2: دریافت اطلاعات فایل
        try:
            file = await video.get_file()
            logger.info(f"File info - ID: {file.file_id}, Size: {file.file_size}")
            
            if file.file_size > 2 * 1024 * 1024 * 1024:  # 2GB
                await start_msg.edit_text("❌ حجم ویدیو بیشتر از 2GB است")
                return
                
        except Exception as e:
            logger.error(f"Error getting file: {e}", exc_info=True)
            await start_msg.edit_text("❌ خطا در دریافت اطلاعات ویدیو از تلگرام")
            return
        
        # مرحله 3: دانلود
        await start_msg.edit_text("📥 در حال دانلود ویدیو...")
        
        input_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                input_path = temp_file.name
            
            download_success = await debug_file_download(file, input_path)
            
            if not download_success or not os.path.exists(input_path):
                await start_msg.edit_text("❌ خطا در دانلود ویدیو")
                return
                
            file_size = os.path.getsize(input_path)
            logger.info(f"File downloaded successfully: {file_size} bytes")
            
        except Exception as e:
            logger.error(f"Error in download process: {e}", exc_info=True)
            await start_msg.edit_text("❌ خطا در فرآیند دانلود")
            return
        
        # مرحله 4: فشرده‌سازی
        await start_msg.edit_text("🔄 در حال فشرده‌سازی ویدیو...")
        
        output_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='_compressed.mp4', delete=False) as temp_file:
                output_path = temp_file.name
            
            # فشرده‌سازی ساده
            command = [
                'ffmpeg', '-i', input_path,
                '-vcodec', 'libx264', '-crf', '28', '-preset', 'medium',
                '-acodec', 'aac', '-b:a', '128k',
                '-y', output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore')
                logger.error(f"FFmpeg error: {error_msg}")
                await start_msg.edit_text("❌ خطا در فشرده‌سازی ویدیو")
                return
            
            # بررسی نتیجه
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                original_size = os.path.getsize(input_path)
                compressed_size = os.path.getsize(output_path)
                reduction = ((original_size - compressed_size) / original_size) * 100
                
                await start_msg.edit_text(f"✅ فشرده‌سازی موفق! کاهش حجم: {reduction:.1f}%")
                
                # آپلود
                with open(output_path, 'rb') as video_file:
                    await update.message.reply_video(
                        video=video_file,
                        caption=f"ویدیو فشرده شده - کاهش حجم: {reduction:.1f}%"
                    )
                
                logger.info("Video processing completed successfully")
            else:
                await start_msg.edit_text("❌ فایل فشرده شده ایجاد نشد")
                
        except asyncio.TimeoutError:
            await start_msg.edit_text("❌ زمان فشرده‌سازی به پایان رسید")
        except Exception as e:
            logger.error(f"Error in compression: {e}", exc_info=True)
            await start_msg.edit_text("❌ خطا در فرآیند فشرده‌سازی")
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ خطای غیرمنتظره\n\n"
            "لطفاً:\n"
            "• ویدیوی دیگری امتحان کنید\n"
            "• حجم ویدیو را کاهش دهید\n"
            "• چند دقیقه دیگر تلاش کنید"
        )
    
    finally:
        # پاکسازی
        try:
            if input_path and os.path.exists(input_path):
                os.unlink(input_path)
            if output_path and os.path.exists(output_path):
                os.unlink(output_path)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

async def start_command(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "🤖 ربات فشرده‌ساز ویدیو\n\n"
        "یک ویدیو ارسال کنید (تا 2GB)\n\n"
        "برای تست، لطفاً:\n"
        "• یک ویدیوی کوچک (کمتر از 50MB) ارسال کنید\n"
        "• از فرمت MP4 استفاده کنید\n"
        "• اتصال اینترنت stable داشته باشید"
    )

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set!")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # فقط handlerهای اصلی
    application.add_handler(MessageHandler(filters.VIDEO, handle_video))
    application.add_handler(MessageHandler(filters.Document.VIDEO, handle_video))
    application.add_handler(MessageHandler(filters.COMMAND & filters.Regex('start'), start_command))
    
    logger.info("Starting bot in debug mode...")
    application.run_polling()

if __name__ == '__main__':
    main()
