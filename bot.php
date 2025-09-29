<?php
// بارگذاری فایل‌های مورد نیاز
require_once 'config.php';
require_once 'functions.php';

log_message("🤖 Starting PHP Telegram Bot (Polling Mode)");

// آخرین update_id
$last_update_id = 0;
$processed_updates = 0;

// حلقه اصلی ربات
while (should_continue_running()) {
    try {
        log_message("🔍 Checking for updates... (offset: " . ($last_update_id + 1) . ")");
        
        // دریافت updates
        $updates = getUpdates($last_update_id + 1);
        
        if (!$updates || !$updates['ok']) {
            log_message("❌ Failed to get updates or no updates available");
            sleep(5);
            continue;
        }
        
        // پردازش هر update
        foreach ($updates['result'] as $update) {
            $last_update_id = max($last_update_id, $update['update_id']);
            $processed_updates++;
            
            if (isset($update['message'])) {
                processMessage($update['message']);
            }
        }
        
        log_message("✅ Processed " . count($updates['result']) . " updates. Total: $processed_updates");
        
        // اگر update جدیدی نبود، کمی صبر کن
        if (empty($updates['result'])) {
            sleep(2);
        }
        
    } catch (Exception $e) {
        log_message("❌ Error in main loop: " . $e->getMessage());
        sleep(5);
    }
}

log_message("🕒 Maximum runtime reached. Stopping bot after processing $processed_updates updates.");

function processMessage($message) {
    $chat_id = $message['chat']['id'];
    
    try {
        // دستور start
        if (isset($message['text']) && strpos($message['text'], '/start') === 0) {
            sendMessage($chat_id,
                "🤖 <b>ربات فشرده‌ساز ویدیو (PHP)</b>\n\n"
                . "یک ویدیو ارسال کنید تا آن را فشرده کرده و حجم آن را کاهش دهم.\n\n"
                . "📹 پشتیبانی از فایل‌های تا 2GB\n"
                . "⏱️ اجرا روی GitHub Actions\n"
                . "🔧 نسخه PHP\n\n"
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
            log_message("Video detected: $file_name, Size: $file_size");
        }
        elseif (isset($message['document'])) {
            $doc = $message['document'];
            $mime_type = $doc['mime_type'] ?? '';
            
            if (strpos($mime_type, 'video/') === 0) {
                $video = $doc;
                $file_size = $doc['file_size'];
                $file_name = $doc['file_name'] ?? 'video';
                log_message("Video document detected: $file_name, Size: $file_size");
            }
        }
        
        if (!$video) {
            sendMessage($chat_id, "❌ لطفاً یک ویدیو ارسال کنید.");
            return;
        }
        
        // بررسی حجم فایل
        if ($file_size > MAX_FILE_SIZE) {
            sendMessage($chat_id, "❌ حجم ویدیو بیشتر از 2GB است.");
            return;
        }
        
        if ($file_size < 10240) { // 10KB
            sendMessage($chat_id, "❌ حجم ویدیو بسیار کوچک است.");
            return;
        }
        
        // شروع پردازش
        processVideo($video, $chat_id, $file_name);
        
    } catch (Exception $e) {
        log_message("Error processing message: " . $e->getMessage());
        sendMessage($chat_id, "❌ خطا در پردازش پیام: " . $e->getMessage());
    }
}

function processVideo($video, $chat_id, $file_name) {
    $input_path = '';
    $output_path = '';
    
    try {
        // ارسال پیام شروع
        $processing_msg = sendMessage($chat_id, "🎬 <b>شروع پردازش ویدیو</b>\n\n📁 $file_name\n⏳ لطفاً منتظر بمانید...");
        $processing_msg_id = $processing_msg['result']['message_id'];
        
        // مرحله 1: دریافت اطلاعات فایل
        editMessageText($chat_id, $processing_msg_id, "📥 <b>دریافت اطلاعات ویدیو</b>\n\n🔍 در حال آماده‌سازی...");
        
        $file_info = sendTelegramRequest('getFile', ['file_id' => $video['file_id']]);
        if (!$file_info || !$file_info['ok']) {
            throw new Exception("خطا در دریافت اطلاعات فایل از تلگرام");
        }
        
        $file_path = $file_info['result']['file_path'];
        
        // مرحله 2: دانلود
        editMessageText($chat_id, $processing_msg_id, "📥 <b>در حال دانلود ویدیو</b>\n\n⏬ دریافت فایل از سرور...");
        
        $input_path = TMP_DIR . uniqid() . '_original.mp4';
        if (!downloadFile($file_path, $input_path)) {
            throw new Exception("خطا در دانلود ویدیو");
        }
        
        $downloaded_size = filesize($input_path);
        log_message("Download completed: $downloaded_size bytes");
        
        // مرحله 3: فشرده‌سازی
        editMessageText($chat_id, $processing_msg_id, "🔄 <b>در حال فشرده‌سازی ویدیو</b>\n\n⚙️ این مرحله ممکن است چند دقیقه طول بکشد...");
        
        $output_path = TMP_DIR . uniqid() . '_compressed.mp4';
        $compress_result = compressVideo($input_path, $output_path);
        
        if (!$compress_result['success']) {
            throw new Exception("فشرده‌سازی ناموفق: " . $compress_result['error']);
        }
        
        // مرحله 4: آپلود
        editMessageText($chat_id, $processing_msg_id, "📤 <b>در حال آپلود ویدیو فشرده شده</b>\n\n⬆️ ارسال به تلگرام...");
        
        $original_size = filesize($input_path);
        $compressed_size = filesize($output_path);
        $reduction = (($original_size - $compressed_size) / $original_size) * 100;
        
        $caption = "✅ ویدیو فشرده شده\n📊 کاهش حجم: " . round($reduction, 1) . "%";
        
        $upload_result = sendVideo($chat_id, $output_path, $caption);
        
        if ($upload_result && $upload_result['ok']) {
            editMessageText($chat_id, $processing_msg_id,
                "🎉 <b>پردازش کامل شد!</b>\n\n"
                . "✅ ویدیو با موفقیت فشرده شد\n"
                . "📊 کاهش حجم: <b>" . round($reduction, 1) . "%</b>\n"
                . "💾 صرفه‌جویی: " . round(($original_size - $compressed_size) / 1024 / 1024, 1) . "MB\n\n"
                . "✨ برای ویدیوی دیگر، همین حالا ارسال کنید!"
            );
            log_message("Video processing completed successfully. Reduction: " . round($reduction, 1) . "%");
        } else {
            throw new Exception("آپلود ویدیو ناموفق بود");
        }
        
    } catch (Exception $e) {
        log_message("Error in processVideo: " . $e->getMessage());
        
        if (isset($processing_msg_id)) {
            editMessageText($chat_id, $processing_msg_id, "❌ <b>خطا در پردازش</b>\n\n" . $e->getMessage());
        } else {
            sendMessage($chat_id, "❌ خطا در پردازش ویدیو: " . $e->getMessage());
        }
    } finally {
        // پاکسازی فایل‌های موقت
        if ($input_path && file_exists($input_path)) {
            unlink($input_path);
        }
        if ($output_path && file_exists($output_path)) {
            unlink($output_path);
        }
    }
}
?>
