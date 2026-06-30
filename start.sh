#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
nohup python main.py > bot.log 2>&1 &
echo $! > bot.pid
echo "Бот запущен, PID: $(cat bot.pid)"
echo "Логи: tail -f bot.log"
