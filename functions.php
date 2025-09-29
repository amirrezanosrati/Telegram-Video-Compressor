<?php
// تابع درخواست به تلگرام
function sendTelegramRequest($method, $params = []) {
    $url = API_URL . $method;
    
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $params);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 30);
    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    
    $response = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    if ($http_code !== 200) {
        log_message("HTTP Error: $http_code");
        return null;
    }
    
    return json_decode($response, true);
}

// دریافت updates
function getUpdates($offset = 0) {
    $params = [
        'offset' => $offset,
        'limit' => 100,
        'timeout' => 30,
        'allowed_updates' => json_encode(['message'])
    ];
    
    return sendTelegramRequest('getUpdates', $params);
}

// ارسال پیام
function sendMessage($chat_id, $text, $reply_markup = null) {
    $params = [
        'chat_id' => $chat_id,
        'text' => $text,
        'parse_mode' => 'HTML'
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
        'parse_mode' => 'HTML'
    ];
    
    return sendTelegramRequest('editMessageText', $params);
}

// دانلود فایل از تلگرام
function downloadFile($file_path, $destination) {
    $file_url = "https://api.telegram.org/file/bot" . BOT_TOKEN . "/" . $file_path;
    
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $file_url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 300);
    curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    
    $data = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    if ($http_code === 200 && $data) {
        return file_put_contents($destination, $data) !== false;
    }
    
    log_message("Download failed. HTTP Code: $http_code");
    return false;
}

// فشرده‌سازی ویدیو
function compressVideo($input_path, $output_path) {
    $command = "ffmpeg -i " . escapeshellarg($input_path) . 
               " -vcodec libx264 -crf 28 -preset medium" .
               " -acodec aac -b:a 128k -movflags +faststart -y " . 
               escapeshellarg($output_path) . " 2>&1";
    
    log_message("Executing: $command");
    
    exec($command, $output, $return_code);
    
    if ($return_code !== 0) {
        log_message("FFmpeg error: " . implode("\n", $output));
        return [
            'success' => false,
            'error' => implode("\n", array_slice($output, -10)) // آخرین 10 خط
        ];
    }
    
    if (!file_exists($output_path) || filesize($output_path) === 0) {
        return [
            'success' => false,
            'error' => 'Output file not created or empty'
        ];
    }
    
    return ['success' => true];
}

// ارسال ویدیو
function sendVideo($chat_id, $video_path, $caption = '') {
    if (!file_exists($video_path)) {
        log_message("Video file not found: $video_path");
        return ['ok' => false];
    }
    
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
