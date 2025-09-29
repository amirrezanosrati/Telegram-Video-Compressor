<?php
require_once 'config.php';
require_once 'functions.php';

log_message("🤖 Starting PHP Telegram Bot (Polling Mode)");

$last_update_id = 0;
$processed_updates = 0;

while (should_continue_running()) {
    try {
        log_message("🔍 Checking for updates... (offset: " . ($last_update_id + 1) . ")");
        
        $updates = getUpdates($last_update_id + 1);
        
        if (!$updates) {
            log_message("❌ No updates received or request failed");
            sleep(5);
            continue;
        }
        
        if (empty($updates['result'])) {
            sleep(3);
            continue;
        }
        
        foreach ($updates['result'] as $update) {
            $last_update_id = max($last_update_id, $update['update_id']);
            $processed_updates++;
            
            if (isset($update['message'])) {
                processMessage($update['message']);
            }
        }
        
        log_message("✅ Processed " . count($updates['result']) . " updates");
        
    } catch (Exception $e) {
        log_message("❌ Error in main loop: " . $e->getMessage());
        sleep(5);
    }
}

log_message("🕒 Maximum runtime reached. Total updates: $processed_updates");

function processMessage($message) {
    $chat_id = $message['chat']['id'];
    
    try {
        // دستور start
        if (isset($message['text']) && strpos($message['text'], '/start') === 0) {
            sendMessage($chat_id,
                "🤖 <b>ربات فشرده‌ساز ویدیو</b>\n\n"
                . "✅ پشتیبانی از فایل‌های تا 2GB\n"
                . "📊 نمایش پیشرفت دانلود و فشرده‌سازی\n"
                . "⚡ فشرده‌سازی هوشمند\n\n"
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
            log_message("Video detected: $file_name, " . format_size($file_size));
        }
        elseif (isset($message['document'])) {
            $doc = $message['document'];
            $mime_type = $doc['mime_type'] ?? '';
            $file_name = $doc['file_name'] ?? 'video';
            
            // بررسی MIME type یا پسوند فایل
            $file_ext = strtolower(pathinfo($file_name, PATHINFO_EXTENSION));
            $video_extensions = ['mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm', '3gp', 'm4v'];
            
            if (strpos($mime_type, 'video/') === 0 || in_array($file_ext, $video_extensions)) {
                $video = $doc;
                $file_size = $doc['file_size'];
                log_message("Video document detected: $file_name, " . format_size($file_size));
            }
        }
        
        if (!$video) {
            sendMessage($chat_id, "❌ لطفاً یک فایل ویدیویی ارسال کنید.");
            return;
        }
        
        // بررسی حجم فایل
        if ($file_size > MAX_FILE_SIZE) {
            sendMessage($chat_id, "❌ حجم ویدیو بیشتر از 2GB است.");
            return;
        }
        
        if ($file_size < 50 * 1024) { // 50KB
            sendMessage($chat_id, "❌ حجم ویدیو بسیار کوچک است.");
            return;
        }
        
        // پردازش ویدیو
        processVideo($video, $chat_id, $file_name, $file_size);
        
    } catch (Exception $e) {
        log_message("Error processing message: " . $e->getMessage());
        sendMessage($chat_id, "❌ خطا: " . $e->getMessage());
    }
}

function processVideo($video, $chat_id, $file_name, $file_size) {
    $input_path = '';
    $output_path = '';
    
    try {
        // ارسال پیام شروع
        $size_text = format_size($file_size);
        $start_msg = sendMessage($chat_id, 
            "🎬 <b>شروع پردازش ویدیو</b>\n\n"
            . "📁 <b>$file_name</b>\n"
            . "📊 <b>$size_text</b>\n\n"
            . "⏳ در حال آماده‌سازی..."
        );
        
        if (!$start_msg) {
            throw new Exception("Failed to send start message");
        }
        
        $processing_msg_id = $start_msg['result']['message_id'];
        
        // مرحله 1: دریافت اطلاعات فایل
        editMessageText($chat_id, $processing_msg_id, 
            "🔍 <b>دریافت اطلاعات ویدیو</b>\n\n"
            . "📁 $file_name\n"
            . "📊 $size_text\n\n"
            . "⏳ در حال اتصال به سرور..."
        );
        
        $file_info = sendTelegramRequest('getFile', ['file_id' => $video['file_id']], 5);
        
        if (!$file_info) {
            throw new Exception("خطا در دریافت اطلاعات فایل از تلگرام. لطفاً دوباره تلاش کنید.");
        }
        
        $file_path = $file_info['result']['file_path'];
        log_message("File path received: $file_path");
        
        // مرحله 2: دانلود با پیشرفت
        $input_path = TMP_DIR . uniqid() . '_original.mp4';
        
        editMessageText($chat_id, $processing_msg_id, 
            "📥 <b>در حال دانلود ویدیو...</b>\n\n"
            . "⏬ اتصال به سرور تلگرام\n"
            . "📊 " . format_size($file_size) . "\n\n"
            . "⏳ لطفاً منتظر بمانید..."
        );
        
        $download_success = downloadFileWithProgress($file_path, $input_path, $chat_id, $processing_msg_id, $file_size);
        
        if (!$download_success || !file_exists($input_path)) {
            throw new Exception("خطا در دانلود ویدیو. ممکن است فایل بسیار بزرگ باشد.");
        }
        
        $downloaded_size = filesize($input_path);
        log_message("Download verified: " . format_size($downloaded_size));
        
        // مرحله 3: فشرده‌سازی با پیشرفت
        editMessageText($chat_id, $processing_msg_id, 
            "🔄 <b>در حال فشرده‌سازی ویدیو...</b>\n\n"
            . "⚙️ بهینه‌سازی ویدیو\n"
            . "📊 " . format_size($downloaded_size) . "\n\n"
            . "⏳ این مرحله ممکن است چند دقیقه طول بکشد..."
        );
        
        $output_path = TMP_DIR . uniqid() . '_compressed.mp4';
        $compress_result = compressVideoWithProgress($input_path, $output_path, $chat_id, $processing_msg_id);
        
        if (!$compress_result['success']) {
            throw new Exception("فشرده‌سازی ناموفق: " . $compress_result['error']);
        }
        
        // مرحله 4: آپلود
        $original_size = filesize($input_path);
        $compressed_size = filesize($output_path);
        $reduction = (($original_size - $compressed_size) / $original_size) * 100;
        
        editMessageText($chat_id, $processing_msg_id, 
            "📤 <b>در حال آپلود ویدیو فشرده شده</b>\n\n"
            . "✅ فشرده‌سازی تکمیل شد!\n"
            . "📊 کاهش حجم: " . round($reduction, 1) . "%\n\n"
            . "⬆️ در حال ارسال..."
        );
        
        $caption = "✅ ویدیو فشرده شده\n"
                 . "📊 کاهش حجم: " . round($reduction, 1) . "%\n"
                 . "📁 " . format_size($original_size) . " → " . format_size($compressed_size);
        
        $upload_result = sendVideo($chat_id, $output_path, $caption);
        
        if ($upload_result && $upload_result['ok']) {
            editMessageText($chat_id, $processing_msg_id,
                "🎉 <b>پردازش کامل شد!</b>\n\n"
                . "✅ ویدیو با موفقیت فشرده شد\n"
                . "📊 کاهش حجم: <b>" . round($reduction, 1) . "%</b>\n"
                . "💾 صرفه‌جویی: " . format_size($original_size - $compressed_size) . "\n"
                . "📁 " . format_size($original_size) . " → " . format_size($compressed_size) . "\n\n"
                . "✨ برای ویدیوی دیگر، همین حالا ارسال کنید!"
            );
            
            log_message("🎉 Processing completed successfully! Reduction: " . round($reduction, 1) . "%");
        } else {
            throw new Exception("آپلود ویدیو ناموفق بود. ممکن است فایل خروجی بسیار بزرگ باشد.");
        }
        
    } catch (Exception $e) {
        log_message("❌ Error in processVideo: " . $e->getMessage());
        
        $error_message = "❌ <b>خطا در پردازش</b>\n\n" . $e->getMessage() . "\n\n";
        $error_message .= "🔧 <i>راه‌حل‌ها:</i>\n";
        $error_message .= "• ویدیوی کوچکتری ارسال کنید\n";
        $error_message .= "• فرمت MP4 استفاده کنید\n";
        $error_message .= "• چند دقیقه دیگر تلاش کنید";
        
        if (isset($processing_msg_id)) {
            editMessageText($chat_id, $processing_msg_id, $error_message);
        } else {
            sendMessage($chat_id, $error_message);
        }
    } finally {
        // پاکسازی
        if ($input_path && file_exists($input_path)) {
            unlink($input_path);
        }
        if ($output_path && file_exists($output_path)) {
            unlink($output_path);
        }
    }
}
?>
