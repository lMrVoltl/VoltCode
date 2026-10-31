import os
import sys
import time
import json
import subprocess
import requests

SERVER_URL = "http://127.0.0.1:8080/v1/chat/completions"

# Цветовая палитра Claude Code
R   = "\033[0m"
B   = "\033[1m"
DIM = "\033[2m"
CYN = "\033[38;5;51m"
IND = "\033[38;5;105m"
GRN = "\033[38;5;84m"
YEL = "\033[38;5;220m"
RED = "\033[38;5;203m"

# 1. Системные инструменты агента для Android
def tool_open_url(target):
    target = target.strip()
    # Если просят YouTube или известный сервис
    if "youtu" in target.lower() or target.lower() == "youtube":
        cmd = "termux-open-url https://www.youtube.com || am start -a android.intent.action.VIEW -d https://www.youtube.com"
    elif not target.startswith("http://") and not target.startswith("https://"):
        cmd = f"termux-open-url https://{target} || am start -a android.intent.action.VIEW -d https://{target}"
    else:
        cmd = f"termux-open-url {target} || am start -a android.intent.action.VIEW -d {target}"
    subprocess.run(cmd, shell=True, stderr=subprocess.DEVNULL)
    return f"Запуск ссылки/приложения: {target}"

def tool_notify(text):
    subprocess.run(["termux-notification", "--title", "VoltCode", "--content", str(text)], stderr=subprocess.DEVNULL)
    return f"Уведомление отправлено: {text}"

def tool_vibrate(ms=300):
    subprocess.run(["termux-vibrate", "-d", str(ms)], stderr=subprocess.DEVNULL)
    return f"Вибрация ({ms}мс)"

def tool_bash(cmd):
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        out = (res.stdout.strip() or res.stderr.strip() or "ОК")
        return out[:300]
    except Exception as e:
        return f"Ошибка: {e}"

TOOLS = {
    "open_url": tool_open_url,
    "notify": tool_notify,
    "vibrate": tool_vibrate,
    "bash": tool_bash
}

# 2. Промпт для безусловного выполнения действий
SYSTEM_PROMPT = """Ты — автономный исполнительный агент VoltCode для мобильного Android.
Если пользователь просит открыть сайт, сервис, запустить приложение, отправить уведомление, завибрировать или выполнить команду в терминале — НЕ ПИШИ ИНСТРУКЦИЙ!
Ответь СТРОГО одной строкой JSON для исполнения функции:
{"action": "имя_действия", "arg": "значение"}

Доступные действия:
- "open_url": открыть приложение или сайт (напр: "youtube", "https://t.me", "google.com")
- "notify": показать шторку уведомления (напр: "Напоминание")
- "vibrate": вибрировать (напр: "300")
- "bash": выполнить системную команду в консоли (напр: "ls -la", "df -h", "date")

Если пользователь просто общается или задает вопрос, отвечай коротко обычным текстом на русском языке."""

def print_banner():
    os.system("clear")
    # Компактный маскот-кот строго до 38 колонок (без переносов на телефоне)
    print(f"""{IND}  /\_/\  {CYN}{B}VoltCode Agent{R}
{IND} ( o.o ) {DIM}Snapdragon 7 Gen 1 (Gold){R}
{IND}  > ^ <  {GRN}● Ready{R} {DIM}| :8080 Fast Core{R}
{IND}───────────────────────────────────────{R}""")

def main():
    print_banner()
    while True:
        try:
            prompt = input(f"\n{CYN}volt{R} {DIM}›{R} ").strip()
            if not prompt:
                continue
            if prompt in ("exit", "quit", "/exit"):
                print(f"{DIM}Сессия завершена.{R}")
                break
            if prompt in ("clear", "/clear"):
                print_banner()
                continue

            print(f"{DIM}● Обработка на Cortex-A710...{R}", end="\r")
            t0 = time.time()

            payload = {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 256
            }

            try:
                r = requests.post(SERVER_URL, json=payload, timeout=60).json()
            except Exception:
                print(f"\r{RED}✗ Ошибка: llama-server не доступен на 8080.{R}")
                continue

            dt = time.time() - t0
            raw_reply = r["choices"][0]["message"]["content"].strip()
            tokens = r.get("usage", {}).get("completion_tokens", 0)
            tps = (tokens / dt) if dt > 0 else 0

            # Очищаем строку ожидания
            print(" " * 38, end="\r")

            # Пробуем выполнить как действие
            executed = False
            try:
                # Извлекаем JSON даже если вокруг есть лишний текст
                json_str = raw_reply
                if "{" in json_str and "}" in json_str:
                    json_str = json_str[json_str.find("{"):json_str.rfind("}")+1]
                data = json.loads(json_str)
                action = data.get("action")
                arg = data.get("arg", "")

                if action in TOOLS:
                    print(f"{GRN}⚡ Выполняю:{R} {CYN}{action}{R}({YEL}\"{arg}\"{R})")
                    result = TOOLS[action](arg)
                    print(f"{DIM}└─ {result}{R}")
                    executed = True
            except Exception:
                executed = False

            if not executed:
                # Обычный текстовый ответ в аккуратной рамке
                print(f"{IND}╭─ Ответ{R}")
                for line in raw_reply.split("\n"):
                    print(f"{IND}│{R} {line}")
                print(f"{IND}╰──────────────────────────────────────{R}")

            # Метрики
            print(f"{DIM}⚡ {tps:.1f} т/с | ⏱ {dt:.2f}s | {tokens} токенов{R}")

        except KeyboardInterrupt:
            print(f"\n{DIM}Выход.{R}")
            break

if __name__ == "__main__":
    main()
