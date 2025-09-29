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
import math

# تنظیمات لاگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')

class ProgressTracker:
    def __init__(self):
        self.start_time = None
        self.last_update_time = None
        
    def create_progress_bar(self, percentage: float, bar_length: int = 10) -> str:
        filled_length = int(bar_length * percentage // 100)
        bar = '█' * filled_length + '▒' * (bar_length - filled_length)
        return f"[{bar}] {percentage:.1f}%"
    
    def format_speed(self, bytes_processed: float, elapsed_time: float) -> str:
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
    
    try:
        async with aiofiles.open(file_path, 'wb') as f:
            async for chunk in file.iter_bytes(chunk_size=131072):  # 128KB chunks برای سرعت بیشتر
                if chunk:
                    await f.write(chunk)
                    downloaded += len(chunk)
                    
                    current_time = time.time()
                    if current_time - last_callback_time > 0.5 and progress_callback:
                        await progress_callback(downloaded, total_size, current_time - start_time)
                        last_callback_time = current_time
        
        if progress_callback:
            await progress_callback(downloaded, total_size, time.time() - start_time)
            
        return True
    except Exception as e:
        logger.error(f"Error in download_with_progress: {e}")
        return False

async def compress_video(input_path: str, output_path: str) -> Tuple[bool, str]:
    """تابع برای فشرده‌سازی ویدیو با FFmpeg"""
    try:
        # بررسی وجود فایل ورودی
        if not os.path.exists(input_path):
            return False, "فایل ورودی وجود ندارد"
        
        input_size = os.path.getsize(input_path)
        if input_size == 0:
            return False, "فایل ورودی خالی است"
        
        logger.info(f"Starting compression. Input size: {input_size/1024/1024:.2f} MB")
        
        # تنظیمات بهینه برای فایل‌های بزرگ
        crf_value = "28"  # فشرده‌سازی بیشتر برای فایل‌های بزرگ
        preset_value = "medium"
        
        if input_size > 500 * 1024 * 1024:  # بیش از 500MB
            crf_value = "30"
            preset_value = "fast"
        
        # دستور FFmpeg برای فشرده‌سازی ویدیو
        command = [
            'ffmpeg',
            '-i', input_path,
            '-vcodec', 'libx264',
            '-crf', crf_value,
            '-preset', preset_value,
            '-acodec', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            '-y',
            '-loglevel', 'info',
            '-threads', '0',  # استفاده از تمام cores
            output_path
        ]
        
        # اجرای FFmpeg با timeout بیشتر برای فایل‌های بزرگ
        timeout_seconds = max(600, int(input_size / (1024 * 1024) * 2))  # 2 ثانیه به ازای هر مگابایت
        logger.info(f"FFmpeg timeout set to {timeout_seconds} seconds")
        
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore')
                logger.error(f"FFmpeg error (return code: {process.returncode}): {error_msg}")
                return False, f"خطای FFmpeg: {error_msg[:200]}"
            
            # بررسی وجود فایل خروجی
            if not os.path.exists(output_path):
                return False, "فایل خروجی ایجاد نشد"
            
            output_size = os.path.getsize(output_path)
            if output_size == 0:
                return False, "فایل خروجی خالی است"
            
            logger.info(f"Compression successful. Output size: {output_size/1024/1024:.2f} MB")
            return True, "فشرده‌سازی با موفقیت انجام شد"
            
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            return False, "زمان فشرده‌سازی به پایان رسید"
            
    except Exception as e:
        logger.error(f"Error in compress_video: {e}")
        return False, f"خطای سیستمی: {str(e)}"

async def handle_video(update: Update, context: CallbackContext):
    """Handler برای مدیریت ویدیوهای دریافتی"""
    user = update.message.from_user
    logger.info(f"Received message from user {user.id}")
    
    download_msg = None
    input_path = None
    output_path = None
    
    try:
        # لاگ کامل پیام برای دیباگ
        logger.info(f"Message type: {update.message.content_type}")
        
        # بررسی انواع مختلف ویدیو
        video = None
        file_size = 0
        file_name = "video"
        
        if update.message.video:
            video = update.message.video
            file_size = video.file_size
            file_name = getattr(video, 'file_name', 'video.mp4')
            logger.info(f"Detected as video message. Size: {file_size}, File: {file_name}")
            
        elif update.message.document:
            # بررسی اینکه آیا document یک ویدیو است
            document = update.message.document
            mime_type = getattr(document, 'mime_type', '')
            file_name = getattr(document, 'file_name', 'video')
            
            logger.info(f"Detected as document. MIME: {mime_type}, File: {file_name}, Size: {document.file_size}")
            
            # لیست MIME type های قابل قبول
            video_mime_types = ['video/mp4', 'video/avi', 'video/mkv', 'video/mov', 'video/wmv', 
                              'video/flv', 'video/webm', 'video/3gp', 'video/mpeg']
            
            if mime_type and (mime_type.startswith('video/') or mime_type in video_mime_types):
                video = document
                file_size = document.file_size
                logger.info(f"Document is a video. Size: {file_size}")
            else:
                # حتی اگر MIME type ناشناخته باشد، بر اساس پسوند فایل بررسی کنیم
                file_ext = os.path.splitext(file_name)[1].lower()
                video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.3gp', '.mpeg', '.mpg']
                
                if file_ext in video_extensions:
                    video = document
                    file_size = document.file_size
                    logger.info(f"Document has video extension. Treating as video. Size: {file_size}")
                else:
                    await update.message.reply_text(
                        "❌ لطفاً یک فایل ویدیویی ارسال کنید.\n"
                        f"فرمت دریافتی: {mime_type or 'نامشخص'}\n"
                        f"پسوند فایل: {file_ext or 'نامشخص'}"
                    )
                    return
        else:
            await update.message.reply_text(
                "❌ لطفاً یک ویدیو ارسال کنید.\n"
                "می‌توانید ویدیو را به صورت مستقیم یا از طریق بخش Document ارسال کنید."
            )
            return
        
        if not video:
            await update.message.reply_text("❌ هیچ ویدیویی در پیام شناسایی نشد.")
            return
        
        # بررسی محدودیت حجم (تا 2GB)
        MAX_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
        MIN_SIZE = 10 * 1024  # 10KB
        
        if file_size > MAX_SIZE:
            await update.message.reply_text(
                f"❌ حجم ویدیو بسیار بزرگ است.\n"
                f"حداکثر حجم مجاز: {MAX_SIZE/1024/1024/1024:.1f}GB\n"
                f"حجم ویدیوی شما: {file_size/1024/1024/1024:.1f}GB"
            )
            return
        
        if file_size < MIN_SIZE:
            await update.message.reply_text(
                f"❌ حجم ویدیو بسیار کوچک است.\n"
                f"حداقل حجم مجاز: {MIN_SIZE/1024}KB\n"
                f"حجم ویدیوی شما: {file_size/1024:.1f}KB"
            )
            return
        
        # ارسال پیام شروع
        size_text = f"{file_size/1024/1024:.1f}MB" if file_size < 1024*1024*1024 else f"{file_size/1024/1024/1024:.1f}GB"
        start_msg = await update.message.reply_text(
            f"🎬 <b>شروع پردازش ویدیو</b>\n\n"
            f"📊 حجم ویدیو: <b>{size_text}</b>\n"
            f"📁 نام فایل: <b>{file_name}</b>\n\n"
            f"⏳ لطفاً منتظر بمانید...",
            parse_mode=ParseMode.HTML
        )
        
        # دریافت فایل ویدیو با تلاش بیشتر
        max_retries = 3
        video_file = None
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Attempt {attempt + 1} to get file object...")
                video_file = await video.get_file()
                
                # بررسی اطلاعات فایل
                if not video_file:
                    raise Exception("File object is None")
                
                logger.info(f"File object received. File ID: {video_file.file_id}, Size: {video_file.file_size}")
                
                # اگر سایزها متفاوت باشند، از سایز فایل object استفاده می‌کنیم
                if video_file.file_size and video_file.file_size > 0:
                    if video_file.file_size != file_size:
                        logger.warning(f"Size mismatch: message={file_size}, file_object={video_file.file_size}. Using file_object size.")
                        file_size = video_file.file_size
                    break
                else:
                    raise Exception("File size is zero or None")
                    
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)  # صبر 2 ثانیه قبل از تلاش مجدد
                else:
                    raise e
        
        if not video_file:
            await start_msg.edit_text(
                "❌ <b>خطا در دریافت اطلاعات ویدیو</b>\n\n"
                "لطفاً:\n"
                "• اتصال اینترنت خود را بررسی کنید\n"
                "• ویدیوی کوچکتری ارسال کنید\n"
                "• چند دقیقه دیگر تلاش کنید",
                parse_mode=ParseMode.HTML
            )
            return
        
        # ایجاد فایل‌های موقت
        try:
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as input_file:
                input_path = input_file.name
                logger.info(f"Input temp file created: {input_path}")
            
            with tempfile.NamedTemporaryFile(suffix='_compressed.mp4', delete=False) as output_file:
                output_path = output_file.name
                logger.info(f"Output temp file created: {output_path}")
        except Exception as e:
            logger.error(f"Error creating temp files: {e}")
            await start_msg.edit_text("❌ خطا در ایجاد فایل‌های موقت")
            return
        
        # تابع callback برای پیشرفت دانلود
        async def download_progress_callback(downloaded, total, elapsed):
            nonlocal download_msg
            percentage = (downloaded / total) * 100
            
            progress_tracker = ProgressTracker()
            progress_bar = progress_tracker.create_progress_bar(percentage)
            speed = progress_tracker.format_speed(downloaded, elapsed)
            time_remaining = progress_tracker.format_time_remaining(downloaded, total, elapsed)
            
            # فرمت حجم بر اساس اندازه
            if total < 1024*1024*1024:  # کمتر از 1GB
                size_text = f"{downloaded/1024/1024:.1f}MB / {total/1024/1024:.1f}MB"
            else:
                size_text = f"{downloaded/1024/1024/1024:.2f}GB / {total/1024/1024/1024:.2f}GB"
            
            text = (
                f"📥 <b>در حال دانلود ویدیو...</b>\n\n"
                f"{progress_bar}\n"
                f"📊 حجم: {size_text}\n"
                f"🚀 سرعت: {speed}\n"
                f"⏱️ زمان باقی‌مانده: {time_remaining}"
            )
            
            try:
                if download_msg:
                    await download_msg.edit_text(text, parse_mode=ParseMode.HTML)
                else:
                    download_msg = await start_msg.edit_text(text, parse_mode=ParseMode.HTML)
            except Exception as e:
                logger.error(f"Error updating progress: {e}")
        
        # دانلود ویدیو با نمایش پیشرفت
        logger.info("Starting download...")
        download_success = await download_with_progress(
            video_file, 
            input_path, 
            download_progress_callback
        )
        
        if not download_success:
            await start_msg.edit_text("❌ خطا در دانلود ویدیو")
            return
        
        # بررسی فایل دانلود شده
        if not os.path.exists(input_path):
            await start_msg.edit_text("❌ فایل دانلود شده وجود ندارد")
            return
        
        downloaded_size = os.path.getsize(input_path)
        logger.info(f"Download completed. File size: {downloaded_size/1024/1024:.2f} MB")
        
        if downloaded_size == 0:
            await start_msg.edit_text("❌ فایل دانلود شده خالی است")
            return
        
        if downloaded_size < MIN_SIZE:
            await start_msg.edit_text("❌ فایل دانلود شده بسیار کوچک است")
            return
        
        # پیام فشرده‌سازی
        compress_msg = await start_msg.edit_text(
            "🔄 <b>در حال فشرده‌سازی ویدیو...</b>\n\n"
            "این مرحله برای فایل‌های بزرگ ممکن است چند دقیقه طول بکشد...\n"
            "⏳ لطفاً شکیبا باشید...",
            parse_mode=ParseMode.HTML
        )
        
        # فشرده‌سازی ویدیو
        logger.info("Starting compression...")
        compression_success, compression_message = await compress_video(input_path, output_path)
        
        if not compression_success:
            error_text = f"❌ <b>خطا در فشرده‌سازی ویدیو</b>\n\n{compression_message}"
            await compress_msg.edit_text(error_text, parse_mode=ParseMode.HTML)
            logger.error(f"Compression failed: {compression_message}")
            return
        
        if not os.path.exists(output_path):
            await compress_msg.edit_text("❌ فایل فشرده شده ایجاد نشد")
            return
        
        # محاسبه کاهش حجم
        original_size = os.path.getsize(input_path)
        compressed_size = os.path.getsize(output_path)
        
        if compressed_size == 0:
            await compress_msg.edit_text("❌ فایل فشرده شده خالی است")
            return
        
        reduction = ((original_size - compressed_size) / original_size) * 100
        
        # نمایش اطلاعات فشرده‌سازی
        original_size_text = f"{original_size/1024/1024:.1f}MB" if original_size < 1024*1024*1024 else f"{original_size/1024/1024/1024:.2f}GB"
        compressed_size_text = f"{compressed_size/1024/1024:.1f}MB" if compressed_size < 1024*1024*1024 else f"{compressed_size/1024/1024/1024:.2f}GB"
        
        compress_info = await compress_msg.edit_text(
            f"✅ <b>فشرده‌سازی تکمیل شد!</b>\n\n"
            f"📊 کاهش حجم: <b>{reduction:.1f}%</b>\n"
            f"📁 حجم اصلی: <b>{original_size_text}</b>\n"
            f"📁 حجم جدید: <b>{compressed_size_text}</b>\n\n"
            f"📤 در حال آپلود ویدیو فشرده شده...",
            parse_mode=ParseMode.HTML
        )
        
        # آپلود ویدیو فشرده شده
        try:
            logger.info("Starting upload...")
            with open(output_path, 'rb') as video_file_obj:
                await update.message.reply_video(
                    video=video_file_obj,
                    caption=(
                        f"✅ ویدیو فشرده شده\n"
                        f"📊 کاهش حجم: {reduction:.1f}%\n"
                        f"📁 حجم اصلی: {original_size_text}\n"
                        f"📁 حجم جدید: {compressed_size_text}\n"
                        f"💾 صرفه‌جویی: {(original_size - compressed_size)/1024/1024:.1f}MB"
                    ),
                    filename=f"compressed_{file_name}",
                    read_timeout=300,
                    write_timeout=300,
                    connect_timeout=300,
                    pool_timeout=300
                )
            
            # پیام تکمیل
            success_msg = (
                f"🎉 <b>پردازش کامل شد!</b>\n\n"
                f"✅ ویدیو با موفقیت فشرده و آپلود شد\n"
                f"📊 کاهش حجم: <b>{reduction:.1f}%</b>\n"
                f"💾 صرفه‌جویی در فضای ذخیره‌سازی: <b>{(original_size - compressed_size)/1024/1024:.1f}MB</b>\n\n"
                f"✨ برای فشرده‌سازی ویدیوی دیگر، همین حالا ارسال کنید!"
            )
            
            await compress_info.edit_text(success_msg, parse_mode=ParseMode.HTML)
            logger.info(f"Video processing completed for user {user.id}. Reduction: {reduction:.1f}%")
            
        except Exception as upload_error:
            logger.error(f"Upload error: {upload_error}", exc_info=True)
            await compress_info.edit_text(
                "❌ خطا در آپلود ویدیو فشرده شده\n\n"
                "ویدیو فشرده شده با موفقیت ایجاد شد اما آپلود نشد.\n"
                "لطفاً دوباره تلاش کنید."
            )
    
    except Exception as e:
        logger.error(f"Unexpected error in handle_video: {e}", exc_info=True)
        try:
            await update.message.reply_text(
                "❌ <b>خطای غیرمنتظره در پردازش ویدیو</b>\n\n"
                "لطفاً:\n"
                "• ویدیوی کوچکتری ارسال کنید\n"
                "• اتصال اینترنت را بررسی کنید\n"
                "• چند دقیقه دیگر تلاش کنید\n\n"
                f"خطا: {str(e)[:100]}...",
                parse_mode=ParseMode.HTML
            )
        except:
            pass
    
    finally:
        # پاکسازی فایل‌های موقت
        try:
            if input_path and os.path.exists(input_path):
                os.unlink(input_path)
                logger.info(f"Cleaned up input file: {input_path}")
            if output_path and os.path.exists(output_path):
                os.unlink(output_path)
                logger.info(f"Cleaned up output file: {output_path}")
        except Exception as e:
            logger.error(f"Error cleaning up temp files: {e}")

async def start_command(update: Update, context: CallbackContext):
    """دستور start"""
    await update.message.reply_text(
        "🤖 <b>ربات فشرده‌ساز ویدیو</b>\n\n"
        "یک ویدیو ارسال کنید تا آن را فشرده کرده و حجم آن را کاهش دهم.\n\n"
        "📹 <i>نحوه ارسال ویدیو:</i>\n"
        "• به صورت مستقیم (Video)\n" 
        "• یا از طریق Document (فایل)\n\n"
        "⚠️ <i>محدودیت‌ها:</i>\n"
        "• حداکثر حجم: <b>2GB</b>\n"
        "• حداقل حجم: 10KB\n"
        "• زمان پردازش: 1-10 دقیقه\n\n"
        "🎬 <b>همین حالا یک ویدیو ارسال کنید!</b>",
        parse_mode=ParseMode.HTML
    )

async def help_command(update: Update, context: CallbackContext):
    """دستور help"""
    await update.message.reply_text(
        "📖 <b>راهنما</b>\n\n"
        "1. یک ویدیو ارسال کنید (تا 2GB)\n"
        "2. منتظر بمانید تا دانلود شود\n" 
        "3. ویدیو فشرده می‌شود\n"
        "4. ویدیو فشرده شده برای شما ارسال می‌شود\n\n"
        "🔧 <i>اگر مشکل دارید:</i>\n"
        "• از ویدیوهای با حجم کمتر شروع کنید\n"
        "• اتصال اینترنت پایدار داشته باشید\n"
        "• برای فایل‌های بزرگ چند دقیقه منتظر بمانید",
        parse_mode=ParseMode.HTML
    )

async def error_handler(update: Update, context: CallbackContext):
    """Handler برای مدیریت خطاها"""
    logger.error(f"Update {update} caused error {context.error}", exc_info=True)

def main():
    """تابع اصلی برای اجرای ربات"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is not set!")
        return
    
    # ایجاد برنامه با تنظیمات بهتر
    application = Application.builder().token(BOT_TOKEN).build()
    
    # اضافه کردن handlerها
    application.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, handle_video))
    application.add_handler(MessageHandler(filters.COMMAND & filters.Regex('start'), start_command))
    application.add_handler(MessageHandler(filters.COMMAND & filters.Regex('help'), help_command))
    
    # اضافه کردن error handler
    application.add_error_handler(error_handler)
    
    # شروع ربات
    logger.info("Bot is starting with 2GB support...")
    application.run_polling()

if __name__ == '__main__':
    main()
