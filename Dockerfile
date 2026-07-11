FROM python:3.11-slim

WORKDIR /app

# Системные зависимости для Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libx11-xcb1 \
    libxcb1 \
    && rm -rf /var/lib/apt/lists/*

# Python зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Установка Playwright Chromium
RUN playwright install chromium

# Копируем код
COPY . .

# Создаём папки для данных
RUN mkdir -p data logs

CMD ["python", "main.py"]
