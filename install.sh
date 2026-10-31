#!/bin/bash
set -e

echo "=== Установка VoltCode AI Studio ==="

# 1. Пакеты
pkg update -y
pkg install -y git cmake clang python curl psmisc termux-api

pip install requests

# 2. Сборка llama.cpp (если еще не собрана)
if [ ! -f "$HOME/llama.cpp/build/bin/llama-server" ]; then
  echo "[1/4] Клонирование и сборка llama.cpp..."
  cd ~
  rm -rf llama.cpp
  git clone --depth 1 https://github.com/ggerganov/llama.cpp
  cd llama.cpp
  cmake -B build
  cmake --build build --config Release -j$(nproc)
fi

# 3. Скачивание моделей
mkdir -p ~/llama.cpp/models
cd ~/llama.cpp/models

echo "[2/4] Проверка весов моделей..."
if [ ! -f "qwen2.5-1.5b-instruct-q5_k_m.gguf" ]; then
  echo "Скачивание Fast Core (Qwen 1.5B)..."
  curl -L -o qwen2.5-1.5b-instruct-q5_k_m.gguf \
    "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q5_k_m.gguf"
fi

if [ ! -f "Qwen2-VL-2B-Instruct-Q4_K_M.gguf" ]; then
  echo "Скачивание Vision Core (Qwen2-VL 2B)..."
  curl -L -o Qwen2-VL-2B-Instruct-Q4_K_M.gguf \
    "https://huggingface.co/bartowski/Qwen2-VL-2B-Instruct-GGUF/resolve/main/Qwen2-VL-2B-Instruct-Q4_K_M.gguf"
fi

if [ ! -f "mmproj-Qwen2-VL-2B-Instruct-f16.gguf" ]; then
  echo "Скачивание проектора mmproj..."
  curl -L -o mmproj-Qwen2-VL-2B-Instruct-f16.gguf \
    "https://huggingface.co/bartowski/Qwen2-VL-2B-Instruct-GGUF/resolve/main/mmproj-Qwen2-VL-2B-Instruct-f16.gguf"
fi

# 4. Развертывание файлов VoltCode
mkdir -p ~/voltcode/static
cd ~/voltcode-repo
cp volt_cli.py ~/volt_cli.py
cp server.py ~/voltcode/server.py
cp static/index.html ~/voltcode/static/index.html

# 5. Регистрация команды voltcode в системе
cat << 'LAUNCH' > $PREFIX/bin/voltcode
#!/bin/bash
python ~/volt_cli.py
LAUNCH
chmod +x $PREFIX/bin/voltcode

# 6. Создание launch.sh с автоподстройкой ядер
CORES=$(nproc)
FAST_THREADS=$(( CORES > 4 ? 4 : CORES ))

cat << LAUNCH_SCRIPT > ~/launch.sh
#!/bin/bash
pkill -9 -f llama-server 2>/dev/null || true
pkill -9 -f "voltcode/server.py" 2>/dev/null || true
sleep 1

# Запуск Fast Core
~/llama.cpp/build/bin/llama-server \
  -m ~/llama.cpp/models/qwen2.5-1.5b-instruct-q5_k_m.gguf \
  -t $FAST_THREADS \
  -c 2048 \
  --chat-template chatml \
  --temp 0.3 \
  --host 127.0.0.1 \
  --port 8080 > /dev/null 2>&1 &

# Запуск Vision Core
~/llama.cpp/build/bin/llama-server \
  -m ~/llama.cpp/models/Qwen2-VL-2B-Instruct-Q4_K_M.gguf \
  --mmproj ~/llama.cpp/models/mmproj-Qwen2-VL-2B-Instruct-f16.gguf \
  -t $FAST_THREADS \
  -c 3072 \
  -b 128 \
  -ub 128 \
  --temp 0.2 \
  --host 127.0.0.1 \
  --port 8081 > /dev/null 2>&1 &

# Запуск веб-сервера
python ~/voltcode/server.py > /dev/null 2>&1 &

sleep 3
termux-open-url http://127.0.0.1:3000
LAUNCH_SCRIPT
chmod +x ~/launch.sh

echo ""
echo "=== Установка завершена! ==="
echo "Запуск: ~/launch.sh"
echo "Консольный агент: voltcode"
~/launch.sh
