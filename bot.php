<?php
require_once 'config.php';
require_once 'functions.php';

log_message("🤖 Starting Telegram Video Bot with Upload Progress");

$last_update_id = 0;
$processed_count = 0;

while (should_continue_running()) {
    try {
        log_message("🔍 Checking for updates...");
        
        $updates = getUpdates($last_update_id + 1);
        
        if (!$updates) {
            sleep(5);
            continue;
        }
        
        if (empty($updates['result'])) {
            sleep(3);
            continue;
        }
        
        foreach ($updates['result'] as $update) {
            $last_update_id = max($last_update_id, $update['update_id']);
            $processed_count++;
            
            if (isset($update['message'])) {
                processMessage($update['message']);
            }
        }
        
        log_message("✅ Processed " . count($updates['result']) . " updates");
        
    } catch (Exception $e) {
        log_message("❌ Error: " . $e->getMessage());
        sleep(5);
    }
}

log_message("🕒 Bot stopped. Total processed: $processed_count");

function processMessage($message) {
    $chat_id = $message['chat']['id'];
    
    try {
        // دستور start
        if (isset($message['text']) && strpos($message['text'], '/start') === 0) {
            sendMessage($chat_id,
                "🤖 <b>ربات بهینه‌ساز ویدیو</b>\n\n"
                . "🎯 <i>با نمایش پیشرفت زنده</i>\n\n"
                . "📥 نوار پیشرفت دانلود\n"
                . "📤 نوار پیشرفت آپلود\n"
                . "⚡ سریع و بدون خطا\n"
                . "📊 پشتیبانی از فایل‌های تا 2GB\n\n"
                . "🎬 <b>یک ویدیو ارسال کنید!</b>"
            );
            return;
        }
        
        // بررسی ویدیو
        $video = null;
        $file_size = 0;
        $file_name = 'video';
        
        if (isset($message['video'])) {
            $video = $message['video'];
            $file_size = $video['file_size'];
            $file_name = $video['file_name'] ?? 'video.mp4';
            log_message("🎥 Video received: $file_name, " . format_size($file_size));
        }
        elseif (isset($message['document'])) {
            $doc = $message['document'];
            $mime_type = $doc['mime_type'] ?? '';
            $file_name = $doc['file_name'] ?? 'video';
            
            // بررسی MIME type یا پسوند فایل
            $file_ext = strtolower(pathinfo($file_name, PATHINFO_EXTENSION));
            $video_extensions = ['mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm', '3gp', 'm4v', 'mpg', 'mpeg'];
            
            if (strpos($mime_type, 'video/') === 0 || in_array($file_ext, $video_extensions)) {
                $video = $doc;
                $file_size = $doc['file_size'];
                log_message("📄 Video document: $file_name, " . format_size($file_size));
            }
        }
        
        if (!$video) {
            sendMessage($chat_id, 
                "❌ لطفاً یک فایل ویدیویی ارسال کنید.\n\n"
                . "✅ فرمت‌های پشتیبانی:\n"
                . "MP4, AVI, MKV, MOV, WMV, WebM, 3GP\n\n"
                . "📱 می‌توانید از طریق Video یا Document ارسال کنید."
            );
            return;
        }
        
        // بررسی حجم فایل
        if ($file_size > MAX_FILE_SIZE) {
            sendMessage($chat_id, "❌ حجم ویدیو بیشتر از 2GB است.");
            return;
        }
        
        if ($file_size < 1024 * 1024) { // 1MB
            sendMessage($chat_id, 
                "❌ حجم ویدیو کمتر از 1MB است.\n\n"
                . "📊 ویدیوهای کوچک نیازی به بهینه‌سازی ندارند."
            );
            return;
        }
        
        // پردازش ویدیو
        processVideoWithProgress($video, $chat_id, $file_name, $file_size);
        
    } catch (Exception $e) {
        log_message("❌ Message processing error: " . $e->getMessage());
        sendMessage($chat_id, "❌ خطا: " . $e->getMessage());
    }
}

function processVideoWithProgress($video, $chat_id, $file_name, $file_size) {
    $temp_file_path = '';
    
    try {
        // مرحله 1: ارسال پیام شروع
        $start_msg = sendMessage($chat_id,
            "🎬 <b>شروع پردازش ویدیو</b>\n\n"
            . "📁 <code>$file_name</code>\n"
            . "📊 " . format_size($file_size) . "\n\n"
            . "📥 دانلود → 📤 آپلود\n"
            . "⏳ در حال آماده‌سازی..."
        );
        
        if (!$start_msg) {
            throw new Exception("خطا در ارسال پیام شروع");
        }
        
        $processing_msg_id = $start_msg['result']['message_id'];
        
        // مرحله 2: دریافت اطلاعات فایل
        editMessageText($chat_id, $processing_msg_id,
            "🔍 <b>دریافت اطلاعات ویدیو</b>\n\n"
            . "📁 $file_name\n"
            . "📊 " . format_size($file_size) . "\n\n"
            . "⏳ در حال اتصال به سرور تلگرام..."
        );
        
        $file_info = sendTelegramRequest('getFile', ['file_id' => $video['file_id']]);
        
        if (!$file_info) {
            throw new Exception("خطا در دریافت اطلاعات فایل از تلگرام");
        }
        
        $file_path = $file_info['result']['file_path'];
        log_message("📁 File path: $file_path");
        
        // مرحله 3: دانلود ویدیو با پیشرفت
        editMessageText($chat_id, $processing_msg_id,
            "📥 <b>در حال دانلود ویدیو...</b>\n\n"
            . "⏬ دریافت از سرور تلگرام\n"
            . "📊 " . format_size($file_size) . "\n\n"
            . "⏳ لطفاً منتظر بمانید..."
        );
        
        $temp_file_path = TMP_DIR . uniqid() . '_' . $file_name;
        $download_success = downloadFileWithProgress($file_path, $temp_file_path, $chat_id, $processing_msg_id, $file_size);
        
        if (!$download_success || !file_exists($temp_file_path)) {
            throw new Exception("خطا در دانلود ویدیو");
        }
        
        $downloaded_size = filesize($temp_file_path);
        log_message("✅ Downloaded: " . format_size($downloaded_size));
        
        // مرحله 4: آپلود با کیفیت پایین به تلگرام با پیشرفت
        editMessageText($chat_id, $processing_msg_id,
            "📤 <b>آماده برای آپلود...</b>\n\n"
            . "⬆️ ارسال با کیفیت بهینه\n"
            . "💡 تلگرام خودش ویدیو را فشرده می‌کند\n"
            . "📊 حجم اصلی: " . format_size($downloaded_size) . "\n\n"
            . "⏳ اتصال به سرور تلگرام..."
        );
        
        // کمی تاخیر قبل از شروع آپلود
        sleep(2);
        
        $upload_result = sendFinalVideo($chat_id, $processing_msg_id, $temp_file_path, $downloaded_size, $file_name);
        
        if ($upload_result && $upload_result['ok']) {
            // محاسبه کاهش حجم تخمینی
            $estimated_reduction = 70; // 70% کاهش توسط تلگرام
            $estimated_saving = $downloaded_size * ($estimated_reduction / 100);
            
            // پیام نهایی موفقیت
            editMessageText($chat_id, $processing_msg_id,
                "🎉 <b>پردازش کامل شد!</b>\n\n"
                . "✅ ویدیو با موفقیت آپلود شد\n"
                . "📊 حجم اصلی: " . format_size($downloaded_size) . "\n"
                . "💾 صرفه‌جویی تخمینی: " . format_size($estimated_saving) . "\n"
                . "📱 کیفیت: مناسب برای تلگرام\n\n"
                . "✨ <b>برای ویدیوی دیگر، همین حالا ارسال کنید!</b>"
            );
            
            log_message("🎉 Processing completed successfully!");
            
        } else {
            throw new Exception("آپلود ویدیو ناموفق بود");
        }
        
    } catch (Exception $e) {
        log_message("❌ Processing error: " . $e->getMessage());
        
        $error_msg = "❌ <b>خطا در پردازش</b>\n\n" . $e->getMessage() . "\n\n";
        $error_msg .= "🔧 <i>راه‌حل‌ها:</i>\n";
        $error_msg .= "• ویدیوی کوچکتری امتحان کنید\n";
        $error_msg .= "• اتصال اینترنت را بررسی کنید\n";
        $error_msg .= "• چند دقیقه دیگر تلاش کنید";
        
        if (isset($processing_msg_id)) {
            editMessageText($chat_id, $processing_msg_id, $error_msg);
        } else {
            sendMessage($chat_id, $error_msg);
        }
        
    } finally {
        // پاکسازی فایل موقت
        if ($temp_file_path && file_exists($temp_file_path)) {
            unlink($temp_file_path);
            log_message("🧹 Temporary file cleaned up");
        }
    }
}
?>
