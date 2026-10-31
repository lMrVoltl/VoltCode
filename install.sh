#!/bin/bash
set -e

echo "=== Установка VoltCode AI Studio ==="

# 1. Системные пакеты
pkg update -y
pkg install -y git cmake clang python curl psmisc termux-api

pip install requests

# 2. Сборка llama.cpp
if [ ! -f "$HOME/llama.cpp/build/bin/llama-server" ]; then
  echo "[1/4] Сборка оптимизированного llama-server..."
  cd ~
  rm -rf llama.cpp
  git clone --depth 1 https://github.com/ggerganov/llama.cpp
  cd llama.cpp
  cmake -B build
  cmake --build build --config Release -j$(nproc)
fi

# 3. Скачивание моделей (если еще нет)
mkdir -p ~/llama.cpp/models
cd ~/llama.cpp/models

echo "[2/4] Проверка весов моделей..."
if ! ls *1.5b*.gguf 1>/dev/null 2>&1; then
  echo "Скачивание Fast Core (Qwen 1.5B)..."
  curl -L -o qwen2.5-1.5b-instruct-q5_k_m.gguf \
    "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q5_k_m.gguf"
fi

if ! ls *VL-2B*.gguf 1>/dev/null 2>&1; then
  echo "Скачивание Vision Core (Qwen2-VL 2B)..."
  curl -L -o Qwen2-VL-2B-Instruct-Q4_K_M.gguf \
    "https://huggingface.co/bartowski/Qwen2-VL-2B-Instruct-GGUF/resolve/main/Qwen2-VL-2B-Instruct-Q4_K_M.gguf"
fi

if ! ls *mmproj*.gguf 1>/dev/null 2>&1; then
  echo "Скачивание проектора mmproj..."
  curl -L -o mmproj-Qwen2-VL-2B-Instruct-f16.gguf \
    "https://huggingface.co/bartowski/Qwen2-VL-2B-Instruct-GGUF/resolve/main/mmproj-Qwen2-VL-2B-Instruct-f16.gguf"
fi

# 4. Копирование интерфейса и скриптов
mkdir -p ~/voltcode/static
cd ~/voltcode-repo 2>/dev/null || cd /data/data/com.termux/files/home/voltcode-repo
cp volt_cli.py ~/volt_cli.py
cp server.py ~/voltcode/server.py
cp static/index.html ~/voltcode/static/index.html

# 5. Регистрация команды voltcode в Termux
cat << 'LAUNCH' > $PREFIX/bin/voltcode
#!/bin/bash
python ~/volt_cli.py
LAUNCH
chmod +x $PREFIX/bin/voltcode

# 6. Создание стабильного launch.sh
cat << 'LAUNCH_SCRIPT' > ~/launch.sh
#!/bin/bash
pkill -9 -f llama-server 2>/dev/null || true
pkill -9 -f "server.py" 2>/dev/null || true
sleep 1

# Автоопределение моделей
FAST_MODEL=$(ls ~/llama.cpp/models/*1.5b*.gguf 2>/dev/null | head -n 1)
VISION_MODEL=$(ls ~/llama.cpp/models/*VL-2B*.gguf 2>/dev/null | grep -v mmproj | head -n 1)
MMPROJ_MODEL=$(ls ~/llama.cpp/models/*mmproj*.gguf 2>/dev/null | head -n 1)

# Автоопределение доступных потоков
CORES=$(nproc)
THREADS=$(( CORES > 4 ? 4 : CORES ))

echo "[1/3] Запуск Fast Core..."
~/llama.cpp/build/bin/llama-server \
  -m "$FAST_MODEL" \
  -t $THREADS \
  -c 2048 \
  --temp 0.3 \
  --host 127.0.0.1 \
  --port 8080 > ~/fast_server.log 2>&1 &

echo "[2/3] Запуск Vision Core..."
~/llama.cpp/build/bin/llama-server \
  -m "$VISION_MODEL" \
  --mmproj "$MMPROJ_MODEL" \
  -t $THREADS \
  -c 3072 \
  -b 128 \
  -ub 128 \
  --temp 0.2 \
  --host 127.0.0.1 \
  --port 8081 > ~/vision_server.log 2>&1 &

echo "[3/3] Запуск веб-диспетчера VoltCode..."
python ~/voltcode/server.py > /dev/null 2>&1 &

sleep 3
termux-open-url http://127.0.0.1:3000
echo "=== VoltCode Studio запущен! ==="
LAUNCH_SCRIPT
chmod +x ~/launch.sh

echo ""
echo "=== Установка успешно завершена! ==="
echo "Для запуска используй: ~/launch.sh"
echo "Консольный агент: voltcode"
~/launch.sh
