# 🎯 MidasBuy Coupon Bot — План реализации

## Описание проекта

Автоматизированный Telegram-бот, который:
1. Принимает купон-коды от пользователей через Telegram
2. Автоматически активирует купоны на сайте [midasbuy.com](https://www.midasbuy.com/shop/pagedoo/ct1744785094_QMGQJMGD/mobile/index.html)
3. Возвращает пользователю статус активации (успех / ошибка / уже использован)

---

## 🏗️ Архитектура системы

```
┌─────────────────┐        ┌─────────────────┐        ┌──────────────────────┐
│   Пользователь  │──────▶│  Telegram Bot   │──────▶│   Coupon Activator   │
│   (Telegram)    │◀──────│  (python-telegram│◀──────│  (Playwright/Selenium│
└─────────────────┘        │   -bot)         │        │   + HTTP клиент)     │
                           └────────┬────────┘        └──────────────────────┘
                                    │
                           ┌────────▼────────┐
                           │    База данных  │
                           │  (SQLite / PG)  │
                           └─────────────────┘
```

---

## 🧰 Технологический стек

| Компонент         | Технология               | Назначение                              |
|-------------------|--------------------------|-----------------------------------------|
| Язык              | Python 3.11+             | Основной язык разработки                |
| Telegram Bot      | `python-telegram-bot`    | Обработка сообщений пользователей       |
| Браузерная авто.  | `playwright` (async)     | Активация купонов на сайте              |
| HTTP клиент       | `httpx` / `aiohttp`      | Прямые API-запросы (если возможно)      |
| База данных       | SQLite (dev) / PostgreSQL (prod) | Хранение купонов и статусов    |
| ORM               | `SQLAlchemy` + `alembic` | Работа с БД                             |
| Планировщик       | `APScheduler`            | Повторные попытки активации             |
| Логирование       | `loguru`                 | Структурированные логи                  |
| Конфигурация      | `pydantic-settings`      | Управление переменными окружения        |
| Деплой            | Docker + Docker Compose  | Контейнеризация                         |

---

## 📦 Модули проекта

### 1. `bot/` — Telegram Bot
- Обработка команд: `/start`, `/help`, `/status`
- Приём купон-кодов от пользователей
- Валидация формата купона (regex)
- Отправка статуса активации
- Защита от спама (rate limiting)

### 2. `activator/` — Модуль активации купонов
- Запуск headless-браузера (Playwright)
- Навигация на страницу midasbuy.com
- Ввод купон-кода в форму
- Парсинг результата активации
- Обработка ошибок (CAPTCHA, timeout, invalid coupon)

### 3. `database/` — Работа с БД
- Модели: `User`, `Coupon`, `ActivationLog`
- CRUD операции
- История активаций
- Статистика

### 4. `core/` — Бизнес-логика
- Очередь задач на активацию
- Управление сессиями браузера
- Логика повторных попыток (retry)

### 5. `config/` — Конфигурация
- `.env` переменные
- Настройки браузера
- Настройки Telegram

---

## 🗄️ Схема базы данных

```sql
-- Пользователи
CREATE TABLE users (
    id          BIGINT PRIMARY KEY,   -- Telegram user_id
    username    TEXT,
    created_at  TIMESTAMP DEFAULT NOW(),
    is_banned   BOOLEAN DEFAULT FALSE
);

-- Купоны
CREATE TABLE coupons (
    id          SERIAL PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    user_id     BIGINT REFERENCES users(id),
    status      TEXT DEFAULT 'pending',  -- pending | success | failed | duplicate
    submitted_at TIMESTAMP DEFAULT NOW(),
    activated_at TIMESTAMP,
    error_msg   TEXT
);

-- Логи активаций
CREATE TABLE activation_logs (
    id          SERIAL PRIMARY KEY,
    coupon_id   INTEGER REFERENCES coupons(id),
    attempt     INTEGER DEFAULT 1,
    result      TEXT,
    screenshot  TEXT,  -- путь к скриншоту (при ошибке)
    created_at  TIMESTAMP DEFAULT NOW()
);
```

---

## 📁 Структура проекта

```
midasbuyAPI/
├── bot/
│   ├── __init__.py
│   ├── handlers/
│   │   ├── start.py          # /start команда
│   │   ├── coupon.py         # Обработка купонов
│   │   └── status.py         # Статус купона
│   ├── middlewares/
│   │   └── rate_limit.py     # Защита от спама
│   └── keyboards.py          # Inline/Reply клавиатуры
├── activator/
│   ├── __init__.py
│   ├── browser.py            # Управление Playwright
│   ├── midasbuy.py           # Логика активации на сайте
│   └── exceptions.py         # Кастомные исключения
├── database/
│   ├── __init__.py
│   ├── models.py             # SQLAlchemy модели
│   ├── crud.py               # CRUD операции
│   └── migrations/           # Alembic миграции
├── core/
│   ├── __init__.py
│   ├── queue.py              # Очередь задач
│   └── scheduler.py          # Планировщик повторных попыток
├── config/
│   ├── __init__.py
│   └── settings.py           # pydantic-settings конфиг
├── tests/
│   ├── test_bot.py
│   ├── test_activator.py
│   └── test_database.py
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── alembic.ini
└── main.py                   # Точка входа
```

---

## 🚀 Этапы разработки

### Этап 1 — Исследование (1-2 дня) ✅ ЗАВЕРШЁН
- [x] Изучить структуру страницы midasbuy.com (DevTools)
- [x] Определить: есть ли прямой API или нужна браузерная автоматизация
- [x] Изучить форму ввода купона: селекторы, CAPTCHA, авторизация
- [x] Проверить наличие защиты от ботов (Cloudflare, reCAPTCHA)

### Этап 2 — Настройка окружения (1 день) ✅ ЗАВЕРШЁН
- [x] Инициализация проекта, `.gitignore`, `requirements.txt`
- [x] Настройка Docker Compose (бот + БД)
- [x] Настройка `.env` и конфигурации (`config/settings.py` — pydantic-settings)
- [x] Инициализация базы данных + модели (`database/models.py`, `session.py`, `crud.py`)

### Этап 3 — Telegram Bot (2-3 дня) ✅ ЗАВЕРШЁН
- [ ] Создание бота в @BotFather, получение токена ← **нужен реальный токен**
- [x] Базовые хэндлеры: `/start`, `/help` (`bot/handlers/start.py`)
- [x] Хэндлер приёма купон-кода с валидацией (`bot/handlers/coupon.py`)
- [x] Rate limiting (макс. 5 купонов в час + in-memory 20 msg/min) (`bot/middlewares/rate_limit.py`)
- [x] Уведомления о статусе активации (`bot/handlers/status.py`)

### Этап 4 — Модуль активации (3-5 дней) ✅ ЗАВЕРШЁН
- [x] Настройка Playwright (headless Chromium) (`activator/browser.py`)
- [x] Автоматизация: логин + HTTP API + Playwright fallback (`activator/midasbuy.py`)
- [x] Парсинг ответа (успех / ошибка) с классификацией по тексту
- [x] Скриншот при ошибке для отладки
- [x] Обработка edge-cases: timeout, invalid, duplicate, expired, flagged, rate_limited

### Этап 5 — Очередь и повторные попытки (1-2 дня) ✅ ЗАВЕРШЁН
- [x] Очередь активаций (asyncio Queue) (`core/queue.py`)
- [x] Логика повторных попыток (max 3 попытки с задержкой)
- [x] Уведомление пользователя о финальном статусе (через asyncio.Future)

### Этап 6 — Тестирование (2-3 дня)
- [ ] Unit-тесты для модулей
- [ ] Интеграционные тесты
- [ ] Тест с реальными купонами (sandbox или тестовые)
- [ ] Нагрузочное тестирование (несколько купонов одновременно)

### Этап 7 — Деплой (1-2 дня)
- [x] Настройка Docker + Docker Compose (`Dockerfile`, `docker-compose.yml`)
- [ ] Деплой на VPS (Ubuntu)
- [ ] Настройка systemd или supervisor
- [ ] Мониторинг логов

---

## ⚠️ Риски и сложности

| Риск | Вероятность | Митигация |
|------|------------|-----------|
| CAPTCHA на сайте | Высокая | Anti-CAPTCHA сервис (2captcha, CapSolver) |
| Блокировка IP | Средняя | Прокси-сервер, ротация IP |
| Изменение HTML структуры | Средняя | Мониторинг + алерты при сбоях |
| Авторизация на сайте | Высокая | Хранение сессии Playwright |
| Rate limiting сайта | Средняя | Задержки между запросами |

---

## 🔑 Переменные окружения (`.env.example`)

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here
ADMIN_CHAT_ID=your_admin_chat_id

# Database
DATABASE_URL=sqlite:///./data/coupons.db
# DATABASE_URL=postgresql://user:pass@localhost:5432/midasbuy

# MidasBuy
MIDASBUY_URL=https://www.midasbuy.com/shop/pagedoo/ct1744785094_QMGQJMGD/mobile/index.html
MIDASBUY_SESSION_FILE=./data/session.json

# Activator
MAX_RETRIES=3
RETRY_DELAY_SECONDS=5
HEADLESS=true

# Anti-CAPTCHA (если нужно)
ANTICAPTCHA_API_KEY=your_key_here
```

---

## 📋 Следующие шаги

1. **Подтвердить план** — согласовать стек и архитектуру
2. **Исследовать сайт** — изучить страницу через DevTools, найти API эндпоинты
3. **Создать Telegram бота** — зарегистрировать через @BotFather
4. **Начать с Этапа 2** — настройка окружения и структуры проекта
