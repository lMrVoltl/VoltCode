import os
import sys
import time
import json
import subprocess
import requests

SERVER_URL = "http://127.0.0.1:8080/v1/chat/completions"

R   = "\033[0m"
B   = "\033[1m"
DIM = "\033[2m"
CYN = "\033[38;5;51m"
IND = "\033[38;5;105m"
GRN = "\033[38;5;84m"
YEL = "\033[38;5;220m"
RED = "\033[38;5;203m"

# Популярные алиасы системных и сторонних приложений Android
APP_ALIASES = {
    "заметки": ["notes", "notepad", "keep"],
    "блокнот": ["notes", "notepad", "keep"],
    "камера": ["camera"],
    "галерея": ["gallery", "photos"],
    "фото": ["gallery", "photos"],
    "ютуб": ["com.google.android.youtube"],
    "youtube": ["com.google.android.youtube"],
    "телеграм": ["org.telegram.messenger", "org.thunderdog.challegram", "ayugram", "exteragram"],
    "тг": ["org.telegram.messenger", "org.thunderdog.challegram", "ayugram", "exteragram"],
    "калькулятор": ["calculator"],
    "настройки": ["com.android.settings"],
    "проводник": ["filemanager", "documentsui", "files"],
    "файлы": ["filemanager", "documentsui", "files"],
    "диктофон": ["soundrecorder", "recorder"],
    "хром": ["com.android.chrome"],
    "браузер": ["browser", "chrome"],
    "часы": ["deskclock", "alarm", "clock"],
    "будильник": ["deskclock", "alarm", "clock"],
    "вк": ["com.vkontakte.android"]
}

def tool_open_app(app_name):
    query = app_name.lower().strip()
    patterns = APP_ALIASES.get(query, [query])

    # Получаем список всех установленных пакетов на устройстве
    try:
        raw_pkgs = subprocess.check_output("pm list packages", shell=True, text=True, stderr=subprocess.DEVNULL)
        installed = [p.replace("package:", "").strip() for p in raw_pkgs.splitlines()]
    except Exception:
        installed = []

    target_pkg = None
    # 1. Поиск по алиасам
    for pat in patterns:
        for pkg in installed:
            if pat in pkg.lower():
                target_pkg = pkg
                break
        if target_pkg:
            break

    # 2. Если не найден в базе, ищем прямое вхождение слова
    if not target_pkg:
        for pkg in installed:
            if query in pkg.lower():
                target_pkg = pkg
                break

    if target_pkg:
        # Запуск приложения через системный Launcher Intent
        cmd = f"monkey -p {target_pkg} -c android.intent.category.LAUNCHER 1"
        subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Запущено приложение: {target_pkg}"
    
    # 3. Fallback: поиск через системный Intent
    subprocess.run(f"am start -a android.intent.action.MAIN -c android.intent.category.APP_{query.upper()}", 
                   shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f"Попытка запуска через Intent: {query}"

def tool_open_url(target):
    target = target.strip()
    if not target.startswith("http://") and not target.startswith("https://"):
        target = f"https://{target}"
    cmd = f"termux-open-url '{target}' || am start -a android.intent.action.VIEW -d '{target}'"
    subprocess.run(cmd, shell=True, stderr=subprocess.DEVNULL)
    return f"Открыта веб-страница: {target}"

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
    "open_app": tool_open_app,
    "open_url": tool_open_url,
    "notify": tool_notify,
    "vibrate": tool_vibrate,
    "bash": tool_bash
}

SYSTEM_PROMPT = """Ты — автономный исполнительный агент VoltCode для мобильного Android.
Если пользователь просит открыть приложение или запустить программу (заметки, камера, ютуб, телеграм, файлы и т.д.) — НЕ ПИШИ ИНСТРУКЦИЙ!
Ответь СТРОГО одной строкой JSON:
{"action": "open_app", "arg": "название_приложения"}

Доступные действия:
- "open_app": открыть установленное Android-приложение (напр: "заметки", "ютуб", "камера", "телеграм", "калькулятор", "галерея")
- "open_url": открыть именно веб-сайт в браузере (напр: "github.com", "google.com")
- "notify": показать уведомление (напр: "Привет!")
- "vibrate": завибрировать (напр: "300")
- "bash": выполнить команду Linux в Termux (напр: "ls", "df -h", "date")

Если пользователь просто общается, отвечай обычным текстом на русском языке."""

def print_banner():
    os.system("clear")
    print(f"""{IND}  /\\_/\\  {CYN}{B}VoltCode Agent{R}
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

            print(" " * 38, end="\r")

            executed = False
            try:
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
                print(f"{IND}╭─ Ответ{R}")
                for line in raw_reply.split("\n"):
                    print(f"{IND}│{R} {line}")
                print(f"{IND}╰──────────────────────────────────────{R}")

            print(f"{DIM}⚡ {tps:.1f} т/с | ⏱ {dt:.2f}s | {tokens} токенов{R}")

        except KeyboardInterrupt:
            print(f"\n{DIM}Выход.{R}")
            break

if __name__ == "__main__":
    main()
