<?php
// تنظیمات ربات
define('BOT_TOKEN', getenv('BOT_TOKEN') ?: 'YOUR_BOT_TOKEN');
define('API_URL', 'https://api.telegram.org/bot' . BOT_TOKEN . '/');
define('MAX_FILE_SIZE', 2 * 1024 * 1024 * 1024); // 2GB
define('MAX_RUNTIME', getenv('MAX_RUNTIME') ?: 360); // 6 ساعت

// دایرکتوری‌های موقت
define('TMP_DIR', sys_get_temp_dir() . '/telegram_bot/');
if (!file_exists(TMP_DIR)) {
    mkdir(TMP_DIR, 0755, true);
}

// زمان شروع اجرا
define('START_TIME', time());

// تابع لاگ
function log_message($message) {
    $timestamp = date('Y-m-d H:i:s');
    echo "[$timestamp] $message\n";
    file_put_contents(TMP_DIR . 'bot.log', "[$timestamp] $message\n", FILE_APPEND);
}

// بررسی زمان اجرا
function should_continue_running() {
    $elapsed = time() - START_TIME;
    return $elapsed < (MAX_RUNTIME * 60);
}

// تابع format حجم
function format_size($bytes) {
    if ($bytes >= 1073741824) {
        return number_format($bytes / 1073741824, 2) . ' GB';
    } elseif ($bytes >= 1048576) {
        return number_format($bytes / 1048576, 1) . ' MB';
    } elseif ($bytes >= 1024) {
        return number_format($bytes / 1024, 1) . ' KB';
    } else {
        return $bytes . ' B';
    }
}

// ایجاد نوار پیشرفت
function create_progress_bar($percentage, $length = 20) {
    $filled = round(($percentage / 100) * $length);
    $empty = $length - $filled;
    
    $bar = '█' . str_repeat('█', $filled) . str_repeat('▒', $empty);
    return $bar . ' ' . round($percentage, 1) . '%';
}
?>
