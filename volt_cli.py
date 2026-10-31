import os
import sys
import time
import json
import base64
import subprocess
import requests

FAST_URL = "http://127.0.0.1:8080/v1/chat/completions"
VISION_URL = "http://127.0.0.1:8081/v1/chat/completions"

R   = "\033[0m"
B   = "\033[1m"
DIM = "\033[2m"
CYN = "\033[38;5;51m"
IND = "\033[38;5;105m"
GRN = "\033[38;5;84m"
YEL = "\033[38;5;220m"
RED = "\033[38;5;203m"

# Расширенная база пакетов Android (включая Honor MagicOS, Xiaomi, Samsung, AOSP)
APP_DB = {
    "заметки": ["com.hihonor.notepad", "com.huawei.notepad", "com.google.android.keep", "com.miui.notes", "com.samsung.android.app.notes"],
    "блокнот": ["com.hihonor.notepad", "com.huawei.notepad", "com.google.android.keep"],
    "камера": ["com.hihonor.camera", "com.huawei.camera", "com.android.camera", "com.google.android.GoogleCamera"],
    "галерея": ["com.hihonor.photos", "com.huawei.photos", "com.google.android.apps.photos", "com.miui.gallery"],
    "фото": ["com.hihonor.photos", "com.google.android.apps.photos"],
    "ютуб": ["com.google.android.youtube"],
    "youtube": ["com.google.android.youtube"],
    "тг": ["org.telegram.messenger", "org.thunderdog.challegram", "com.exteragram", "com.ayugram"],
    "телеграм": ["org.telegram.messenger", "org.thunderdog.challegram", "com.exteragram", "com.ayugram"],
    "калькулятор": ["com.google.android.calculator", "com.hihonor.calculator", "com.miui.calculator"],
    "проводник": ["com.hihonor.filemanager", "com.huawei.hidisk", "com.google.android.documentsui"],
    "файлы": ["com.hihonor.filemanager", "com.google.android.documentsui"],
    "хром": ["com.android.chrome"],
    "браузер": ["com.android.chrome", "org.mozilla.firefox", "com.yandex.browser"],
    "настройки": ["com.android.settings"]
}

# 1. Запуск Android-приложений
def tool_open_app(app_name):
    query = app_name.lower().strip()
    
    # Поиск прямого пакета из базы
    candidates = APP_DB.get(query, [])
    
    # Получение списка реальных установленных пакетов через cmd/pm
    try:
        raw = subprocess.check_output("cmd package list packages || pm list packages", shell=True, text=True, stderr=subprocess.DEVNULL)
        installed = [p.replace("package:", "").strip() for p in raw.splitlines()]
    except Exception:
        installed = []

    # 1. Поиск в установленных по нашей базе
    for pkg in candidates:
        if pkg in installed:
            subprocess.run(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"Запущено приложение: {pkg}"

    # 2. Нечеткий поиск по совпадению подстроки
    for pkg in installed:
        if query in pkg.lower():
            subprocess.run(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"Запущено найденное приложение: {pkg}"

    # 3. Запуск через стандартные системные Intent категории Android
    intent_map = {
        "заметки": "android.intent.action.CREATE_NOTE",
        "камера": "android.media.action.IMAGE_CAPTURE",
        "калькулятор": "android.intent.category.APP_CALCULATOR",
        "галерея": "android.intent.category.APP_GALLERY",
        "браузер": "android.intent.category.APP_BROWSER"
    }
    
    if query in intent_map:
        val = intent_map[query]
        if "action" in val:
            subprocess.run(f"am start -a {val}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(f"am start -a android.intent.action.MAIN -c {val}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Запущено через системный Intent ({query})"

    return f"Приложение '{app_name}' не найдено среди установленных пакетов."

# 2. Получение и зрительный анализ происходящего на экране (Vision Core)
def tool_see_screen(question="Что сейчас отображается на экране?"):
    scr_path = "/data/data/com.termux/files/home/screen.png"
    scr_jpg = "/data/data/com.termux/files/home/screen_opt.jpg"
    
    # Попытка сделать скриншот через screencap или adb
    cmd = f"screencap -p {scr_path} 2>/dev/null || su -c screencap -p {scr_path} 2>/dev/null || adb exec-out screencap -p > {scr_path} 2>/dev/null"
    subprocess.run(cmd, shell=True)

    if not os.path.exists(scr_path) or os.path.getsize(scr_path) == 0:
        return "Не удалось захватить экран. Нужен доступ screencap/adb или отладка по Wi-Fi."

    # Быстрый ресайз средствами Python до 448 px (чтобы Vision Core не тормозил)
    try:
        from PIL import Image
        img = Image.open(scr_path)
        img.thumbnail((448, 448))
        img.convert("RGB").save(scr_jpg, "JPEG", quality=85)
    except Exception:
        # Если PIL нет — отправляем напрямую
        scr_jpg = scr_path

    with open(scr_jpg, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    # Запрос к зрительному ядру Qwen2-VL на порт 8081
    payload = {
        "messages": [
            {
                "role": "system",
                "content": "Ты зрительный модуль агента VoltCode. Опиши кратко, что открыто на экране устройства: какое приложение, кнопки или текст."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]
            }
        ],
        "temperature": 0.2,
        "max_tokens": 256
    }

    try:
        res = requests.post(VISION_URL, json=payload, timeout=40).json()
        desc = res["choices"][0]["message"]["content"].strip()
        return desc
    except Exception as e:
        return f"Ошибка Vision Core (:8081): {e}"

def tool_open_url(target):
    target = target.strip()
    if not target.startswith("http://") and not target.startswith("https://"):
        target = f"https://{target}"
    cmd = f"termux-open-url '{target}' || am start -a android.intent.action.VIEW -d '{target}'"
    subprocess.run(cmd, shell=True, stderr=subprocess.DEVNULL)
    return f"Открыта ссылка: {target}"

def tool_notify(text):
    subprocess.run(["termux-notification", "--title", "VoltCode", "--content", str(text)], stderr=subprocess.DEVNULL)
    return f"Уведомление: {text}"

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
    "see_screen": tool_see_screen,
    "open_url": tool_open_url,
    "notify": tool_notify,
    "vibrate": tool_vibrate,
    "bash": tool_bash
}

SYSTEM_PROMPT = """Ты — автономный исполнительный агент VoltCode для мобильного Android.
Если пользователь просит:
1. Запустить приложение (заметки, камера, ютуб, телеграм, файлы и т.д.) — вызови open_app.
2. Посмотреть экран / прочитать что на дисплее / понять что происходит — вызови see_screen.
3. Открыть сайт — вызови open_url.
4. Выполнить команду терминала — вызови bash.

Строго формат ответа:
{"action": "имя_действия", "arg": "параметр"}

Примеры:
- "открой заметки" -> {"action": "open_app", "arg": "заметки"}
- "что на экране?" -> {"action": "see_screen", "arg": "Что сейчас открыто?"}
- "посмотри экран" -> {"action": "see_screen", "arg": "Опиши экран"}

Если это обычная беседа — отвечай текстом без JSON."""

def print_banner():
    os.system("clear")
    print(f"""{IND}  /\\_/\\  {CYN}{B}VoltCode Agent{R}
{IND} ( o.o ) {DIM}Snapdragon 7 Gen 1 (Gold){R}
{IND}  > ^ <  {GRN}● Ready{R} {DIM}| :8080 Fast + :8081 Vision{R}
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

            print(f"{DIM}● Обработка...{R}", end="\r")
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
                r = requests.post(FAST_URL, json=payload, timeout=40).json()
            except Exception:
                print(f"\r{RED}✗ Fast Core не запущен на 8080.{R}")
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
                    print(f"{IND}👁 Результат:{R}\n{result}")
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
