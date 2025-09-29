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
    
    // همچنین در فایل لاگ هم ذخیره شود
    file_put_contents(TMP_DIR . 'bot.log', "[$timestamp] $message\n", FILE_APPEND);
}

// بررسی زمان اجرا
function should_continue_running() {
    $elapsed = time() - START_TIME;
    return $elapsed < (MAX_RUNTIME * 60); // تبدیل به ثانیه
}
?>
