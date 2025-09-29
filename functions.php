<?php
// تابع درخواست به تلگرام با تلاش مجدد
function sendTelegramRequest($method, $params = [], $retries = 3) {
    $url = API_URL . $method;
    
    for ($attempt = 1; $attempt <= $retries; $attempt++) {
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $params);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, 60); // افزایش timeout
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_USERAGENT, 'Telegram Bot (PHP)');
        
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
        
        log_message("Attempt $attempt failed: HTTP $http_code - $error");
        
        if ($attempt < $retries) {
            sleep(2); // صبر قبل از تلاش مجدد
        }
    }
    
    return null;
}

// دریافت updates
function getUpdates($offset = 0) {
    $params = [
        'offset' => $offset,
        'limit' => 10, // کاهش limit برای عملکرد بهتر
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
    
    log_message("Starting download: $file_url -> $destination");
    
    $ch = curl_init();
    $file_handle = fopen($destination, 'w+');
    
    curl_setopt($ch, CURLOPT_URL, $file_url);
    curl_setopt($ch, CURLOPT_FILE, $file_handle);
    curl_setopt($ch, CURLOPT_TIMEOUT, 300);
    curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    curl_setopt($ch, CURLOPT_USERAGENT, 'Telegram Bot Downloader');
    curl_setopt($ch, CURLOPT_NOPROGRESS, false);
    
    // تابع callback برای پیشرفت
    curl_setopt($ch, CURLOPT_PROGRESSFUNCTION, function($resource, $download_size, $downloaded, $upload_size, $uploaded) use ($chat_id, $message_id, $file_size) {
        static $last_update = 0;
        
        if ($download_size > 0 && $downloaded > 0) {
            $percentage = ($downloaded / $download_size) * 100;
            $current_time = time();
            
            // فقط هر 2 ثانیه آپدیت کن
            if ($current_time - $last_update >= 2 || $percentage >= 100) {
                $progress_bar = create_progress_bar($percentage);
                $text = "📥 <b>در حال دانلود ویدیو...</b>\n\n"
                      . "$progress_bar\n"
                      . "📊 " . format_size($downloaded) . " / " . format_size($download_size);
                
                try {
                    editMessageText($chat_id, $message_id, $text);
                } catch (Exception $e) {
                    // ignore errors during progress updates
                }
                
                $last_update = $current_time;
            }
        }
        
        return 0;
    });
    
    $result = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $error = curl_error($ch);
    
    curl_close($ch);
    fclose($file_handle);
    
    if ($http_code !== 200 || !file_exists($destination)) {
        log_message("Download failed: HTTP $http_code - $error");
        return false;
    }
    
    $downloaded_size = filesize($destination);
    log_message("Download completed: " . format_size($downloaded_size));
    
    return $downloaded_size > 0;
}

// فشرده‌سازی ویدیو با پیشرفت
function compressVideoWithProgress($input_path, $output_path, $chat_id, $message_id) {
    log_message("Starting compression: $input_path -> $output_path");
    
    $input_size = filesize($input_path);
    
    // دستور ffmpeg با loglevel برای ردیابی پیشرفت
    $command = "ffmpeg -i " . escapeshellarg($input_path) . 
               " -vcodec libx264 -crf 28 -preset medium" .
               " -acodec aac -b:a 128k -movflags +faststart" .
               " -y " . escapeshellarg($output_path) . 
               " -progress pipe:1 2>&1";
    
    log_message("Executing: $command");
    
    $descriptorspec = [
        0 => ["pipe", "r"],  // stdin
        1 => ["pipe", "w"],  // stdout
        2 => ["pipe", "w"]   // stderr
    ];
    
    $process = proc_open($command, $descriptorspec, $pipes);
    
    if (!is_resource($process)) {
        return ['success' => false, 'error' => 'Could not start ffmpeg process'];
    }
    
    $start_time = time();
    $last_update = 0;
    
    // خواندن خروجی پیشرفت
    while ($line = fgets($pipes[1])) {
        $line = trim($line);
        
        if (strpos($line, 'out_time=') === 0) {
            $current_time = time();
            
            // فقط هر 5 ثانیه آپدیت کن
            if ($current_time - $last_update >= 5) {
                $time_str = substr($line, 9); // حذف 'out_time='
                $seconds = time_to_seconds($time_str);
                
                // تخمین پیشرفت بر اساس زمان (ساده)
                if ($seconds > 0) {
                    $total_estimate = $seconds * 2; // تخمین ساده
                    $percentage = min(95, ($seconds / $total_estimate) * 100);
                    
                    $progress_bar = create_progress_bar($percentage);
                    $text = "🔄 <b>در حال فشرده‌سازی ویدیو...</b>\n\n"
                          . "$progress_bar\n"
                          . "⏱️ زمان سپری شده: " . format_duration($seconds);
                    
                    try {
                        editMessageText($chat_id, $message_id, $text);
                    } catch (Exception $e) {
                        // ignore errors during progress updates
                    }
                    
                    $last_update = $current_time;
                }
            }
        }
    }
    
    // خواندن خطاها
    $stderr = stream_get_contents($pipes[2]);
    
    fclose($pipes[0]);
    fclose($pipes[1]);
    fclose($pipes[2]);
    
    $return_code = proc_close($process);
    
    if ($return_code !== 0) {
        log_message("FFmpeg error (code: $return_code): $stderr");
        return [
            'success' => false, 
            'error' => 'FFmpeg failed: ' . extract_error_info($stderr)
        ];
    }
    
    if (!file_exists($output_path) || filesize($output_path) === 0) {
        return ['success' => false, 'error' => 'Output file not created'];
    }
    
    return ['success' => true];
}

// تبدیل زمان به ثانیه
function time_to_seconds($time_str) {
    $parts = explode(':', $time_str);
    $seconds = 0;
    $multiplier = 1;
    
    for ($i = count($parts) - 1; $i >= 0; $i--) {
        $seconds += floatval($parts[$i]) * $multiplier;
        $multiplier *= 60;
    }
    
    return $seconds;
}

// فرمت مدت زمان
function format_duration($seconds) {
    $hours = floor($seconds / 3600);
    $minutes = floor(($seconds % 3600) / 60);
    $seconds = $seconds % 60;
    
    if ($hours > 0) {
        return sprintf("%d:%02d:%02d", $hours, $minutes, $seconds);
    } else {
        return sprintf("%02d:%02d", $minutes, $seconds);
    }
}

// استخراج اطلاعات خطا از خروجی ffmpeg
function extract_error_info($stderr) {
    $lines = explode("\n", $stderr);
    
    // پیدا کردن خطوط خطا
    $error_lines = [];
    foreach ($lines as $line) {
        if (strpos($line, 'Error') !== false || strpos($line, 'error') !== false) {
            $error_lines[] = trim($line);
        }
    }
    
    if (count($error_lines) > 0) {
        return implode('; ', array_slice($error_lines, 0, 3));
    }
    
    return 'Unknown error';
}

// ارسال ویدیو
function sendVideo($chat_id, $video_path, $caption = '') {
    if (!file_exists($video_path)) {
        log_message("Video file not found: $video_path");
        return ['ok' => false];
    }
    
    $file_size = filesize($video_path);
    log_message("Uploading video: " . format_size($file_size));
    
    $params = [
        'chat_id' => $chat_id,
        'caption' => $caption,
        'video' => new CURLFile(realpath($video_path))
    ];
    
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, API_URL . 'sendVideo');
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $params);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 300);
    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    
    $response = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    if ($http_code !== 200) {
        log_message("Upload failed. HTTP Code: $http_code");
        return ['ok' => false];
    }
    
    return json_decode($response, true);
}
?>
