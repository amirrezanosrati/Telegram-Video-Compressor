<?php
// تابع درخواست به تلگرام
function sendTelegramRequest($method, $params = [], $retries = 3) {
    $url = API_URL . $method;
    
    for ($attempt = 1; $attempt <= $retries; $attempt++) {
        $ch = curl_init();
        curl_setopt_array($ch, [
            CURLOPT_URL => $url,
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => $params,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => 300,
            CURLOPT_SSL_VERIFYPEER => false,
            CURLOPT_USERAGENT => 'TelegramBot/1.0'
        ]);
        
        $response = curl_exec($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $error = curl_error($ch);
        curl_close($ch);
        
        if ($http_code === 200 && $response) {
            $result = json_decode($response, true);
            if ($result && isset($result['ok']) && $result['ok']) {
                return $result;
            }
        }
        
        log_message("⚠️ Attempt $attempt failed: HTTP $http_code - $error");
        
        if ($attempt < $retries) {
            sleep(2);
        }
    }
    
    return null;
}

// دریافت updates
function getUpdates($offset = 0) {
    $params = [
        'offset' => $offset,
        'limit' => 10,
        'timeout' => 10,
        'allowed_updates' => json_encode(['message'])
    ];
    
    return sendTelegramRequest('getUpdates', $params);
}

// ارسال پیام
function sendMessage($chat_id, $text, $reply_markup = null) {
    $params = [
        'chat_id' => $chat_id,
        'text' => $text,
        'parse_mode' => 'HTML',
        'disable_web_page_preview' => true
    ];
    
    if ($reply_markup) {
        $params['reply_markup'] = json_encode($reply_markup);
    }
    
    return sendTelegramRequest('sendMessage', $params);
}

// ویرایش پیام
function editMessageText($chat_id, $message_id, $text) {
    $params = [
        'chat_id' => $chat_id,
        'message_id' => $message_id,
        'text' => $text,
        'parse_mode' => 'HTML',
        'disable_web_page_preview' => true
    ];
    
    return sendTelegramRequest('editMessageText', $params);
}

// دانلود فایل با پیشرفت
function downloadFileWithProgress($file_path, $destination, $chat_id, $message_id, $file_size) {
    $file_url = "https://api.telegram.org/file/bot" . BOT_TOKEN . "/" . $file_path;
    
    log_message("📥 Starting download: " . format_size($file_size));
    
    $ch = curl_init();
    $file_handle = fopen($destination, 'w+');
    
    if (!$file_handle) {
        throw new Exception("نمیتوان فایل موقت ایجاد کرد");
    }
    
    $start_time = time();
    $last_update_time = 0;
    
    curl_setopt_array($ch, [
        CURLOPT_URL => $file_url,
        CURLOPT_FILE => $file_handle,
        CURLOPT_TIMEOUT => 600,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_SSL_VERIFYPEER => false,
        CURLOPT_NOPROGRESS => false,
    ]);
    
    // تابع callback برای پیشرفت دانلود
    curl_setopt($ch, CURLOPT_PROGRESSFUNCTION, function($resource, $download_size, $downloaded, $upload_size, $uploaded) 
        use ($chat_id, $message_id, $file_size, &$last_update_time, $start_time) {
        
        if ($download_size > 0 && $downloaded > 0) {
            $percentage = min(100, ($downloaded / $download_size) * 100);
            $current_time = time();
            
            if ($current_time - $last_update_time >= 2 || $percentage >= 100) {
                $progress_bar = create_progress_bar($percentage);
                $elapsed = $current_time - $start_time;
                $speed = $elapsed > 0 ? $downloaded / $elapsed : 0;
                
                $remaining_time = $speed > 0 ? ($download_size - $downloaded) / $speed : 0;
                
                $text = "📥 <b>در حال دانلود ویدیو...</b>\n\n"
                      . "$progress_bar\n"
                      . "📊 " . format_size($downloaded) . " / " . format_size($download_size) . "\n"
                      . "🚀 سرعت: " . format_size($speed) . "/s\n"
                      . "⏱️ زمان باقی: " . format_duration($remaining_time);
                
                try {
                    editMessageText($chat_id, $message_id, $text);
                } catch (Exception $e) {
                    // ignore errors
                }
                
                $last_update_time = $current_time;
            }
        }
        
        return 0;
    });
    
    $result = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $error = curl_error($ch);
    
    curl_close($ch);
    fclose($file_handle);
    
    if ($http_code !== 200) {
        log_message("❌ Download failed: HTTP $http_code");
        if (file_exists($destination)) {
            unlink($destination);
        }
        return false;
    }
    
    if (!file_exists($destination)) {
        log_message("❌ Download failed: File not created");
        return false;
    }
    
    $downloaded_size = filesize($destination);
    log_message("✅ Download completed: " . format_size($downloaded_size));
    
    return true;
}

// آپلود ویدیو با نوار پیشرفت
function uploadVideoWithProgress($chat_id, $message_id, $video_path, $original_size, $file_name) {
    if (!file_exists($video_path)) {
        throw new Exception("فایل ویدیو یافت نشد");
    }
    
    $file_size = filesize($video_path);
    log_message("📤 Starting upload: " . format_size($file_size));
    
    $caption = "🎯 ویدیو با کیفیت بهینه‌شده\n" .
               "📊 حجم اصلی: " . format_size($original_size) . "\n" .
               "📱 کیفیت: مناسب برای تلگرام\n" .
               "⚡ توسط تلگرام فشرده شد";
    
    $params = [
        'chat_id' => $chat_id,
        'caption' => $caption,
        'video' => new CURLFile(realpath($video_path)),
        'disable_notification' => false,
        'supports_streaming' => true
    ];
    
    $ch = curl_init();
    curl_setopt_array($ch, [
        CURLOPT_URL => API_URL . 'sendVideo',
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => $params,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 600,
        CURLOPT_SSL_VERIFYPEER => false,
        CURLOPT_NOPROGRESS => false,
    ]);
    
    $start_time = time();
    $last_update_time = 0;
    
    // تابع callback برای پیشرفت آپلود
    curl_setopt($ch, CURLOPT_PROGRESSFUNCTION, function($resource, $download_size, $downloaded, $upload_size, $uploaded) 
        use ($chat_id, $message_id, $file_size, &$last_update_time, $start_time) {
        
        if ($upload_size > 0 && $uploaded > 0) {
            $percentage = min(100, ($uploaded / $upload_size) * 100);
            $current_time = time();
            
            // فقط هر 3 ثانیه آپدیت کن یا وقتی نزدیک به پایان است
            if ($current_time - $last_update_time >= 3 || $percentage >= 95) {
                $progress_bar = create_progress_bar($percentage);
                $elapsed = $current_time - $start_time;
                $speed = $elapsed > 0 ? $uploaded / $elapsed : 0;
                
                $remaining_time = $speed > 0 ? ($upload_size - $uploaded) / $speed : 0;
                
                $text = "📤 <b>در حال آپلود به تلگرام...</b>\n\n"
                      . "$progress_bar\n"
                      . "📊 " . format_size($uploaded) . " / " . format_size($upload_size) . "\n"
                      . "🚀 سرعت: " . format_size($speed) . "/s\n"
                      . "⏱️ زمان باقی: " . format_duration($remaining_time) . "\n\n"
                      . "💡 تلگرام خودش ویدیو را فشرده می‌کند";
                
                try {
                    editMessageText($chat_id, $message_id, $text);
                } catch (Exception $e) {
                    // ignore errors during progress updates
                }
                
                $last_update_time = $current_time;
                
                // وقتی آپلود کامل شد، یک پیام نهایی بفرست
                if ($percentage >= 100) {
                    $final_text = "✅ <b>آپلود کامل شد!</b>\n\n"
                                . "📊 حجم آپلود شده: " . format_size($upload_size) . "\n"
                                . "⏱️ زمان کل: " . format_duration($elapsed) . "\n"
                                . "🚀 سرعت متوسط: " . format_size($speed) . "/s\n\n"
                                . "🔄 در حال پردازش نهایی توسط تلگرام...";
                    
                    try {
                        editMessageText($chat_id, $message_id, $final_text);
                    } catch (Exception $e) {
                        // ignore
                    }
                }
            }
        }
        
        return 0;
    });
    
    $response = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $error = curl_error($ch);
    
    curl_close($ch);
    
    if ($http_code !== 200) {
        log_message("❌ Upload failed: HTTP $http_code - $error");
        throw new Exception("خطا در آپلود به تلگرام: کد HTTP $http_code");
    }
    
    $result = json_decode($response, true);
    
    if (!$result || !$result['ok']) {
        $error_desc = $result['description'] ?? 'خطای ناشناخته';
        log_message("❌ Telegram API error: $error_desc");
        throw new Exception("خطا از تلگرام: $error_desc");
    }
    
    $upload_time = time() - $start_time;
    log_message("✅ Upload completed in {$upload_time}s");
    
    return $result;
}

// ارسال ویدیو نهایی با پیشرفت
function sendFinalVideo($chat_id, $message_id, $video_path, $original_size, $file_name) {
    return uploadVideoWithProgress($chat_id, $message_id, $video_path, $original_size, $file_name);
}
?>
