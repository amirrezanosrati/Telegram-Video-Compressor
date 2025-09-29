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

# تنظیمات لاگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# توکن ربات - از متغیرهای محیطی دریافت می‌شود
BOT_TOKEN = os.environ.get('BOT_TOKEN')

class ProgressTracker:
    """کلاس برای ردیابی پیشرفت دانلود و آپلود"""
    
    def __init__(self):
        self.start_time = None
        self.last_update_time = None
        
    def create_progress_bar(self, percentage: float, bar_length: int = 10) -> str:
        """ایجاد نوار پیشرفت متنی"""
        filled_length = int(bar_length * percentage // 100)
        bar = '█' * filled_length + '▒' * (bar_length - filled_length)
        return f"[{bar}] {percentage:.1f}%"
    
    def format_speed(self, bytes_processed: float, elapsed_time: float) -> str:
        """فرمت‌بندی سرعت انتقال"""
        if elapsed_time == 0:
            return "0 B/s"
        
        speed = bytes_processed / elapsed_time
        units = ['B/s', 'KB/s', 'MB/s']
        unit_index = 0
        
        while speed > 1024 and unit_index < len(units) - 1:
            speed /= 1024
            unit_index += 1
            
        return f"{speed:.1f} {units[unit_index]}"
    
    def format_time_remaining(self, bytes_processed: float, total_bytes: float, elapsed_time: float) -> str:
        """فرمت‌بندی زمان باقی‌مانده"""
        if bytes_processed == 0:
            return "نامشخص"
        
        bytes_remaining = total_bytes - bytes_processed
        speed = bytes_processed / elapsed_time
        time_remaining = bytes_remaining / speed if speed > 0 else 0
        
        if time_remaining > 3600:
            return f"{time_remaining/3600:.1f} ساعت"
        elif time_remaining > 60:
            return f"{time_remaining/60:.1f} دقیقه"
        else:
            return f"{time_remaining:.0f} ثانیه"

async def download_with_progress(file, file_path, progress_callback=None):
    """دانلود فایل با نمایش پیشرفت"""
    total_size = file.file_size
    downloaded = 0
    start_time = time.time()
    last_callback_time = start_time
    
    # ایجاد فایل برای دانلود
    with open(file_path, 'wb') as f:
        async for chunk in file.iter_bytes():
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                
                # فراخوانی callback هر 500ms
                current_time = time.time()
                if current_time - last_callback_time > 0.5 and progress_callback:
                    progress_callback(downloaded, total_size, current_time - start_time)
                    last_callback_time = current_time
        
        # فراخوانی نهایی برای اطمینان از نمایش 100%
        if progress_callback:
            progress_callback(downloaded, total_size, time.time() - start_time)

async def compress_video(input_path: str, output_path: str) -> Tuple[bool, str]:
    """تابع برای فشرده‌سازی ویدیو با FFmpeg"""
    try:
        # دستور FFmpeg برای فشرده‌سازی ویدیو
        command = [
            'ffmpeg',
            '-i', input_path,
            '-vcodec', 'libx264',
            '-crf', '28',
            '-preset', 'medium',
            '-acodec', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            '-y',
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode()
            logger.error(f"FFmpeg error: {error_msg}")
            return False, error_msg
        
        return True, "فشرده‌سازی با موفقیت انجام شد"
    except Exception as e:
        logger.error(f"Error in compress_video: {e}")
        return False, str(e)

async def handle_video(update: Update, context: CallbackContext):
    """Handler برای مدیریت ویدیوهای دریافتی"""
    user = update.message.from_user
    logger.info(f"Received video from user {user.id}")
    
    # متغیرهای پیام‌ها
    download_msg = None
    compress_msg = None
    upload_msg = None
    
    input_path = None
    output_path = None
    
    try:
        # ارسال پیام شروع
        start_msg = await update.message.reply_text(
            "🎬 شروع پردازش ویدیو...",
            parse_mode=ParseMode.HTML
        )
        
        # دریافت فایل ویدیو
        video_file = await update.message.video.get_file()
        file_size = video_file.file_size
        
        # ایجاد فایل‌های موقت
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as input_file:
            input_path = input_file.name
        
        with tempfile.NamedTemporaryFile(suffix='_compressed.mp4', delete=False) as output_file:
            output_path = output_file.name
        
        # تابع callback برای پیشرفت دانلود
        async def download_progress_callback(downloaded, total, elapsed):
            nonlocal download_msg
            percentage = (downloaded / total) * 100
            
            progress_tracker = ProgressTracker()
            progress_bar = progress_tracker.create_progress_bar(percentage)
            speed = progress_tracker.format_speed(downloaded, elapsed)
            time_remaining = progress_tracker.format_time_remaining(downloaded, total, elapsed)
            
            text = (
                f"📥 <b>در حال دانلود ویدیو...</b>\n\n"
                f"{progress_bar}\n"
                f"📊 حجم: {downloaded/1024/1024:.1f}MB / {total/1024/1024:.1f}MB\n"
                f"🚀 سرعت: {speed}\n"
                f"⏱️ زمان باقی‌مانده: {time_remaining}"
            )
            
            if download_msg:
                await download_msg.edit_text(text, parse_mode=ParseMode.HTML)
            else:
                download_msg = await start_msg.edit_text(text, parse_mode=ParseMode.HTML)
        
        # دانلود ویدیو با نمایش پیشرفت
        await download_with_progress(
            video_file, 
            input_path, 
            download_progress_callback
        )
        
        # پیام فشرده‌سازی
        compress_msg = await download_msg.edit_text(
            "🔄 <b>در حال فشرده‌سازی ویدیو...</b>\n\n"
            "این مرحله ممکن است چند دقیقه طول بکشد...",
            parse_mode=ParseMode.HTML
        )
        
        # فشرده‌سازی ویدیو
        compression_success, compression_message = await compress_video(input_path, output_path)
        
        if not compression_success:
            await compress_msg.edit_text(
                "❌ <b>خطا در فشرده‌سازی ویدیو</b>\n\n"
                "لطفاً یک ویدیوی معتبر ارسال کنید.",
                parse_mode=ParseMode.HTML
            )
            return
        
        if not os.path.exists(output_path):
            await compress_msg.edit_text(
                "❌ <b>خطا در ایجاد فایل فشرده</b>",
                parse_mode=ParseMode.HTML
            )
            return
        
        # محاسبه کاهش حجم
        original_size = os.path.getsize(input_path)
        compressed_size = os.path.getsize(output_path)
        reduction = ((original_size - compressed_size) / original_size) * 100
        
        # نمایش اطلاعات فشرده‌سازی
        compress_info = await compress_msg.edit_text(
            f"✅ <b>فشرده‌سازی تکمیل شد!</b>\n\n"
            f"📊 کاهش حجم: <b>{reduction:.1f}%</b>\n"
            f"📁 حجم اصلی: <b>{original_size/1024/1024:.1f}MB</b>\n"
            f"📁 حجم جدید: <b>{compressed_size/1024/1024:.1f}MB</b>\n\n"
            f"📤 در حال آپلود ویدیو فشرده شده...",
            parse_mode=ParseMode.HTML
        )
        
        # تابع callback برای پیشرفت آپلود
        class UploadProgress:
            def __init__(self):
                self.uploaded = 0
                self.total_size = compressed_size
                self.start_time = time.time()
                self.last_update_time = self.start_time
                self.message = None
                self.progress_tracker = ProgressTracker()
            
            async def callback(self, current, total):
                self.uploaded = current
                self.total_size = total
                current_time = time.time()
                
                # به روزرسانی هر 500ms
                if current_time - self.last_update_time > 0.5:
                    percentage = (current / total) * 100
                    progress_bar = self.progress_tracker.create_progress_bar(percentage)
                    speed = self.progress_tracker.format_speed(current, current_time - self.start_time)
                    time_remaining = self.progress_tracker.format_time_remaining(current, total, current_time - self.start_time)
                    
                    text = (
                        f"📤 <b>در حال آپلود ویدیو...</b>\n\n"
                        f"{progress_bar}\n"
                        f"📊 حجم: {current/1024/1024:.1f}MB / {total/1024/1024:.1f}MB\n"
                        f"🚀 سرعت: {speed}\n"
                        f"⏱️ زمان باقی‌مانده: {time_remaining}"
                    )
                    
                    if self.message:
                        await self.message.edit_text(text, parse_mode=ParseMode.HTML)
                    else:
                        self.message = await compress_info.edit_text(text, parse_mode=ParseMode.HTML)
                    
                    self.last_update_time = current_time
        
        upload_progress = UploadProgress()
        
        # آپلود ویدیو فشرده شده
        with open(output_path, 'rb') as video_file_obj:
            # استفاده از upload_document برای فایل‌های بزرگتر
            await update.message.reply_video(
                video=video_file_obj,
                caption=(
                    f"✅ ویدیو فشرده شده\n"
                    f"📊 کاهش حجم: {reduction:.1f}%\n"
                    f"📁 حجم اصلی: {original_size/1024/1024:.1f}MB\n"
                    f"📁 حجم جدید: {compressed_size/1024/1024:.1f}MB"
                ),
                filename="compressed_video.mp4",
                read_timeout=60,
                write_timeout=60,
                connect_timeout=60,
                pool_timeout=60
            )
        
        # پیام تکمیل
        success_msg = (
            f"🎉 <b>پردازش کامل شد!</b>\n\n"
            f"✅ ویدیو با موفقیت فشرده و آپلود شد\n"
            f"📊 کاهش حجم: <b>{reduction:.1f}%</b>\n"
            f"💾 صرفه‌جویی در فضای ذخیره‌سازی: <b>{(original_size - compressed_size)/1024/1024:.1f}MB</b>"
        )
        
        if upload_progress.message:
            await upload_progress.message.edit_text(success_msg, parse_mode=ParseMode.HTML)
        else:
            await compress_info.edit_text(success_msg, parse_mode=ParseMode.HTML)
        
        logger.info(f"Video processing completed for user {user.id}. Reduction: {reduction:.1f}%")
    
    except Exception as e:
        logger.error(f"Error in handle_video: {e}")
        error_msg = await update.message.reply_text(
            "❌ <b>خطا در پردازش ویدیو</b>\n\n"
            "لطفاً دوباره تلاش کنید یا یک ویدیوی معتبر ارسال کنید.",
            parse_mode=ParseMode.HTML
        )
    
    finally:
        # پاکسازی فایل‌های موقت
        try:
            if input_path and os.path.exists(input_path):
                os.unlink(input_path)
            if output_path and os.path.exists(output_path):
                os.unlink(output_path)
        except Exception as e:
            logger.error(f"Error cleaning up temp files: {e}")

async def start_command(update: Update, context: CallbackContext):
    """دستور start"""
    await update.message.reply_text(
        "🤖 <b>ربات فشرده‌ساز ویدیو</b>\n\n"
        "یک ویدیو ارسال کنید تا آن را فشرده کرده و حجم آن را کاهش دهم.\n\n"
        "📹 <i>ویژگی‌ها:</i>\n"
        "• کاهش حجم ویدیو\n"
        "• نمایش نوار پیشرفت\n"
        "• حفظ کیفیت قابل قبول\n"
        "• پشتیبانی از فرمت‌های مختلف\n\n"
        "⚠️ <i>توجه: ویدیوهای بزرگ ممکن است چند دقیقه زمان ببرند.</i>",
        parse_mode=ParseMode.HTML
    )

async def error_handler(update: Update, context: CallbackContext):
    """Handler برای مدیریت خطاها"""
    logger.error(f"Update {update} caused error {context.error}")

def main():
    """تابع اصلی برای اجرای ربات"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is not set!")
        return
    
    # ایجاد برنامه
    application = Application.builder().token(BOT_TOKEN).build()
    
    # اضافه کردن handlerها
    application.add_handler(MessageHandler(filters.VIDEO, handle_video))
    application.add_handler(MessageHandler(filters.COMMAND & filters.Regex('start'), start_command))
    
    # اضافه کردن error handler
    application.add_error_handler(error_handler)
    
    # شروع ربات
    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
