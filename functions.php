<?php
// تابع درخواست به تلگرام با تلاش مجدد
function sendTelegramRequest($method, $params = [], $retries = 5) {
    $url = API_URL . $method;
    
    for ($attempt = 1; $attempt <= $retries; $attempt++) {
        $ch = curl_init();
        curl_setopt_array($ch, [
            CURLOPT_URL => $url,
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => $params,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => 120, // افزایش قابل توجه timeout
            CURLOPT_SSL_VERIFYPEER => false,
            CURLOPT_USERAGENT => 'Mozilla/5.0 (compatible; TelegramBot/1.0)',
            CURLOPT_FOLLOWLOCATION => true,
            CURLOPT_MAXREDIRS => 10,
            CURLOPT_HTTPHEADER => [
                'Accept: application/json',
                'Connection: keep-alive'
            ]
        ]);
        
        $response = curl_exec($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $error = curl_error($ch);
        curl_close($ch);
        
        if ($http_code === 200 && $response) {
            $result = json_decode($response, true);
            if ($result && isset($result['ok']) && $result['ok']) {
                log_message("✅ Request successful: $method");
                return $result;
            }
        }
        
        log_message("⚠️ Attempt $attempt failed for $method: HTTP $http_code - $error");
        
        if ($attempt < $retries) {
            $wait_time = pow(2, $attempt); // Exponential backoff
            log_message("⏳ Waiting $wait_time seconds before retry...");
            sleep($wait_time);
        }
    }
    
    log_message("❌ All attempts failed for $method");
    return null;
}

// دریافت updates
function getUpdates($offset = 0) {
    $params = [
        'offset' => $offset,
        'limit' => 5, // کاهش بیشتر برای عملکرد بهتر
        'timeout' => 5,
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

// دانلود فایل با پیشرفت - نسخه بهبود یافته برای فایل‌های بزرگ
function downloadFileWithProgress($file_path, $destination, $chat_id, $message_id, $file_size) {
    $file_url = "https://api.telegram.org/file/bot" . BOT_TOKEN . "/" . $file_path;
    
    log_message("🚀 Starting download: " . format_size($file_size));
    
    // بررسی فضای دیسک
    if (!check_disk_space($file_size)) {
        throw new Exception("فضای کافی روی دیسک موجود نیست. حداقل " . format_size($file_size * 2) . " فضای آزاد نیاز است.");
    }
    
    $ch = curl_init();
    $file_handle = fopen($destination, 'w+');
    
    if (!$file_handle) {
        throw new Exception("Cannot create temporary file");
    }
    
    curl_setopt_array($ch, [
        CURLOPT_URL => $file_url,
        CURLOPT_FILE => $file_handle,
        CURLOPT_TIMEOUT => 600, // 10 دقیقه برای دانلود
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_SSL_VERIFYPEER => false,
        CURLOPT_USERAGENT => 'Mozilla/5.0 (compatible; TelegramBot/1.0)',
        CURLOPT_NOPROGRESS => false,
        CURLOPT_BUFFERSIZE => 262144, // 256KB buffer
    ]);
    
    // تابع callback برای پیشرفت
    $last_update_time = 0;
    $start_time = time();
    
    curl_setopt($ch, CURLOPT_PROGRESSFUNCTION, function($resource, $download_size, $downloaded, $upload_size, $uploaded) 
        use ($chat_id, $message_id, $file_size, &$last_update_time, $start_time) {
        
        if ($download_size > 0 && $downloaded > 0) {
            $percentage = min(100, ($downloaded / $download_size) * 100);
            $current_time = time();
            
            // فقط هر 3 ثانیه آپدیت کن یا وقتی درصد تغییر قابل توجهی دارد
            if ($current_time - $last_update_time >= 3 || $percentage >= 100) {
                $progress_bar = create_progress_bar($percentage);
                $elapsed = $current_time - $start_time;
                $speed = $elapsed > 0 ? $downloaded / $elapsed : 0;
                
                $text = "📥 <b>در حال دانلود ویدیو...</b>\n\n"
                      . "$progress_bar\n"
                      . "📊 " . format_size($downloaded) . " / " . format_size($download_size) . "\n"
                      . "🚀 سرعت: " . format_size($speed) . "/s\n"
                      . "⏱️ زمان: " . format_duration($elapsed);
                
                try {
                    editMessageText($chat_id, $message_id, $text);
                } catch (Exception $e) {
                    // ignore errors during progress updates
                }
                
                $last_update_time = $current_time;
            }
        }
        
        return 0;
    });
    
    $result = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $error = curl_error($ch);
    $download_speed = curl_getinfo($ch, CURLINFO_SPEED_DOWNLOAD);
    
    curl_close($ch);
    fclose($file_handle);
    
    if ($http_code !== 200) {
        log_message("❌ Download failed: HTTP $http_code - $error");
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
    $download_time = time() - $start_time;
    
    log_message("✅ Download completed: " . format_size($downloaded_size) . 
                " in " . $download_time . "s (" . format_size($download_speed) . "/s)");
    
    return $downloaded_size > 0;
}

// فشرده‌سازی ویدیو با تنظیمات بهینه برای فایل‌های بزرگ
function compressVideoWithProgress($input_path, $output_path, $chat_id, $message_id) {
    $input_size = filesize($input_path);
    log_message("🔧 Starting compression: " . format_size($input_size));
    
    // بررسی فضای دیسک
    if (!check_disk_space($input_size * 2)) {
        throw new Exception("فضای ناکافی برای فشرده‌سازی. نیاز به " . format_size($input_size * 2));
    }
    
    // تنظیمات ffmpeg بر اساس حجم فایل
    $crf = $input_size > 100 * 1024 * 1024 ? '30' : '28'; // فشرده‌سازی بیشتر برای فایل‌های بزرگ
    $preset = $input_size > 100 * 1024 * 1024 ? 'fast' : 'medium';
    
    $command = "ffmpeg -i " . escapeshellarg($input_path) . 
               " -vcodec libx264 -crf $crf -preset $preset" .
               " -acodec aac -b:a 128k -movflags +faststart" .
               " -threads 0 -y " . escapeshellarg($output_path) . 
               " -progress pipe:1 2>&1";
    
    log_message("⚙️ FFmpeg command: $command");
    
    $descriptorspec = [
        0 => ["pipe", "r"],  // stdin
        1 => ["pipe", "w"],  // stdout
        2 => ["pipe", "w"]   // stderr
    ];
    
    $process = proc_open($command, $descriptorspec, $pipes, null, [
        'PATH' => '/usr/local/bin:/usr/bin:/bin'
    ]);
    
    if (!is_resource($process)) {
        throw new Exception('Cannot start ffmpeg process');
    }
    
    $start_time = time();
    $last_update_time = 0;
    $duration_seconds = 0;
    
    // خواندن خروجی پیشرفت
    stream_set_blocking($pipes[1], false);
    
    while (true) {
        $status = proc_get_status($process);
        if (!$status['running']) {
            break;
        }
        
        // خواندن خط پیشرفت
        $line = fgets($pipes[1]);
        if ($line !== false) {
            $line = trim($line);
            
            if (strpos($line, 'out_time=') === 0) {
                $time_str = substr($line, 9);
                $current_seconds = time_to_seconds($time_str);
                $duration_seconds = max($duration_seconds, $current_seconds);
                
                // تخمین کل زمان بر اساس پیشرفت
                if ($current_seconds > 1) {
                    $elapsed_time = time() - $start_time;
                    $total_estimate = ($elapsed_time / $current_seconds) * 100;
                    $percentage = min(95, $total_estimate);
                    
                    $current_time = time();
                    if ($current_time - $last_update_time >= 5) {
                        $progress_bar = create_progress_bar($percentage);
                        $text = "🔄 <b>در حال فشرده‌سازی ویدیو...</b>\n\n"
                              . "$progress_bar\n"
                              . "⏱️ زمان سپری شده: " . format_duration($elapsed_time) . "\n"
                              . "⚙️ کیفیت: " . ($crf == '30' ? 'بهینه' : 'عالی');
                        
                        try {
                            editMessageText($chat_id, $message_id, $text);
                        } catch (Exception $e) {
                            // ignore
                        }
                        
                        $last_update_time = $current_time;
                    }
                }
            }
        }
        
        usleep(100000); // 100ms delay
    }
    
    // خواندن خطاها
    $stderr = stream_get_contents($pipes[2]);
    
    fclose($pipes[0]);
    fclose($pipes[1]);
    fclose($pipes[2]);
    
    $return_code = proc_close($process);
    
    if ($return_code !== 0) {
        log_message("❌ FFmpeg failed with code: $return_code");
        log_message("FFmpeg stderr: " . $stderr);
        throw new Exception('فشرده‌سازی ناموفق: ' . extract_error_info($stderr));
    }
    
    if (!file_exists($output_path) || filesize($output_path) === 0) {
        throw new Exception('فایل خروجی ایجاد نشد');
    }
    
    $output_size = filesize($output_path);
    $compression_time = time() - $start_time;
    
    log_message("✅ Compression completed: " . format_size($output_size) . 
                " in " . $compression_time . "s (" . 
                round(($input_size - $output_size) / $input_size * 100, 1) . "% reduction)");
    
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

// استخراج اطلاعات خطا
function extract_error_info($stderr) {
    $lines = explode("\n", $stderr);
    
    foreach ($lines as $line) {
        if (preg_match('/error|Error|ERROR|failed|Failed|Invalid/i', $line)) {
            $clean_line = trim($line);
            if (strlen($clean_line) > 10) {
                return substr($clean_line, 0, 100);
            }
        }
    }
    
    return 'خطای ناشناخته در پردازش ویدیو';
}

// ارسال ویدیو با تلاش مجدد
function sendVideo($chat_id, $video_path, $caption = '') {
    if (!file_exists($video_path)) {
        throw new Exception("فایل ویدیو یافت نشد");
    }
    
    $file_size = filesize($video_path);
    log_message("📤 Uploading video: " . format_size($file_size));
    
    // اگر فایل خیلی بزرگ است، از روش chunked استفاده کن
    if ($file_size > 50 * 1024 * 1024) {
        return sendVideoChunked($chat_id, $video_path, $caption);
    }
    
    $params = [
        'chat_id' => $chat_id,
        'caption' => $caption,
        'video' => new CURLFile(realpath($video_path))
    ];
    
    $ch = curl_init();
    curl_setopt_array($ch, [
        CURLOPT_URL => API_URL . 'sendVideo',
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => $params,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 300,
        CURLOPT_SSL_VERIFYPEER => false,
    ]);
    
    $response = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    if ($http_code !== 200) {
        throw new Exception("خطا در آپلود: کد HTTP $http_code");
    }
    
    $result = json_decode($response, true);
    
    if (!$result || !$result['ok']) {
        throw new Exception("پاسخ نامعتبر از تلگرام");
    }
    
    log_message("✅ Upload completed successfully");
    return $result;
}

// ارسال ویدیو به صورت تکه‌ای برای فایل‌های بسیار بزرگ
function sendVideoChunked($chat_id, $video_path, $caption) {
    // برای فایل‌های بسیار بزرگ، از روش ساده‌تری استفاده می‌کنیم
    $params = [
        'chat_id' => $chat_id,
        'caption' => $caption,
        'video' => new CURLFile(realpath($video_path))
    ];
    
    $ch = curl_init();
    curl_setopt_array($ch, [
        CURLOPT_URL => API_URL . 'sendVideo',
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => $params,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 600, // 10 دقیقه برای آپلود
        CURLOPT_SSL_VERIFYPEER => false,
        CURLOPT_HTTPHEADER => [
            'Content-Type: multipart/form-data'
        ]
    ]);
    
    $response = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    if ($http_code !== 200) {
        throw new Exception("خطا در آپلود فایل بزرگ: کد HTTP $http_code");
    }
    
    $result = json_decode($response, true);
    
    if (!$result || !$result['ok']) {
        throw new Exception("آپلود فایل بزرگ ناموفق بود");
    }
    
    log_message("✅ Large file upload completed");
    return $result;
}
?>
