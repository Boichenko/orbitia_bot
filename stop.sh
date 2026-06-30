#!/bin/bash
cd "$(dirname "$0")"
if [ -f bot.pid ]; then
    PID=$(cat bot.pid)
    if kill "$PID" 2>/dev/null; then
        echo "Бот остановлен (PID $PID)"
    else
        echo "Процесс $PID уже не существует"
    fi
    rm bot.pid
else
    echo "Файл bot.pid не найден — возможно бот не запущен через start.sh"
fi
