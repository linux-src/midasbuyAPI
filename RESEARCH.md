# 🔍 RESEARCH.md — Исследование midasbuy.com

**Дата исследования:** 2026-07-08  
**Тестовый аккаунт:** alihanveliev2@gmail.com  
**Целевая страница:** `#/pages/p-wgbu/` (Coupon Redeem)

---

## 📐 Архитектура сайта

| Параметр | Значение |
|----------|---------|
| Фреймворк | **React** (react.production.min.js загружается с cdn.midasbuy.com) |
| Сборщик | **Vite** (ES modules + Legacy fallback через SystemJS) |
| UI движок | **Pagedoo** — собственная SaaS-платформа Tencent для page builder |
| CDN ресурсов | `pagedoo.midasbuy.com`, `cdn.midasbuy.com` |
| Основной SDK | `x-midas` — фреймворк Tencent |
| Авторизация SDK | `loginSdk2.6.0.js` + `xmidas.encrypt` (RSA) |
| Аналитика | Aegis SDK (Tencent), NEL, Google Analytics |
| AntiBot | `tdrc.js` (Tencent Device Risk Control), `pay.harvestsharp.com/cgi-bin/fp-behv` |

---

## 🗺️ Карта страниц (page_id → маршрут)

| page_id | Название | URL hash |
|---------|----------|----------|
| `page000` | Роутер | `#/` |
| **`p-wgbu`** | **Coupon Redeem** | **`#/pages/p-wgbu/`** ← наша цель |
| `p-cdrw` | My Coupon | `#/pages/p-cdrw/` |
| `p-f3on` | Coupon History | `#/pages/p-f3on/` |
| `p-8buw` | Coupon iframe popup | `#/pages/p-8buw/` |
| `transaction` | Order Center | `#/pages/transaction/` |

---

## 🧩 React-компоненты страницы купонов

Страница `p-wgbu` (Coupon Redeem) использует компонент **`MRedeemCoupon`**:

```
gems-materials-midasbuy_saas_materials@1780999150
  └── MRedeemCoupon          ← ввод кода купона
  └── McouponManage          ← управление купонами (p-cdrw)
  └── MCouponIframePop       ← iframe-попап купона (p-8buw)
  └── MRedeem                ← логика redemption (CDK/Voucher коды)
  └── MredeemPrize           ← призы от redemption
```

CDN компонентов:
```
https://pagedoo.midasbuy.com/cdn/materials/dist/gems-materials-midasbuy_saas_materials@1780999150/
  manifest.json
  main.d40243d499e9d2e0.js
  component-MRedeemCoupon.main.d40243d499e9d2e0.js
  component-McouponManage.main.d40243d499e9d2e0.js
  ...
```

---

## 🔌 API — Полная карта эндпоинтов

### ✅ Подтверждённые рабочие эндпоинты

#### 1. Получение категорий приложений (без авторизации)
```http
POST https://www.midasbuy.com/frontend/api/midasbuy/v1/app/get_app_category_list
Content-Type: application/json

{
  "browserParams": "from=self.midasbuy_saas&adtag=couponManage",
  "region": "ru",
  "shop_code": "midasbuy",
  "language": "ru",
  "email": ""
}
→ 200 OK: {"category_list": [...]}
```

#### 2. Авторизация (логин по email)
```http
POST https://www.midasbuy.com/midas/usc/v1/123123/emaillogin
Content-Type: application/json

{
  "encrypt_msg": "<RSA-зашифрованный пароль через xmidas.encrypt>"
}
→ 200 OK: (сессионные куки)
```
> ⚠️ `encrypt_msg` — пароль + email, зашифрованные RSA публичным ключом через JavaScript SDK `xmidas.encrypt`. Без браузера воспроизвести сложно!

#### 3. Активация купона (ТРЕБУЕТ авторизации)
```http
POST https://www.midasbuy.com/frontend/api/midasbuy/v1/coupon/redeem
Content-Type: application/json
(требуется авторизованная сессия — cookie select_cookie=1)

{
  "couponCode": "XXXXX"
}
→ 401: {"name":"INVALID_AUTHORIZATION"} — без авторизации
→ ??? — с авторизацией (нужно протестировать)
```

#### 4. Запрос VIP-информации (после логина)
```http
POST https://www.midasbuy.com/frontend/api/midasbuy/vip/v1/queryVip
Content-Type: application/json

{
  "browserParams": "from=self.midasbuy_saas&adtag=couponManage",
  "offer_id": "1450027575",
  "shop_code": "midasbuy",
  "country": "ru",
  "user_id": "Uc5olonf3fdubjb2ionb0",
  "openid": "",
  "role_id": "",
  "server_id": "1"
}
→ 200 OK
```

### 🔴 Старый API (редирект, использовать не нужно)
```
GET/POST https://www.midasbuy.com/cgi-bin/oversea_web/coupon/v1/redeem
  → 302 redirect → /midasbuy/cgi-bin/oversea_web/coupon/v1/redeem
  → 404 json: {"message":"server error"}  (устаревший путь)
```

### 📡 Базовый URL API
```
https://www.midasbuy.com/frontend/api/midasbuy/v1/
```

---

## 🔐 Система авторизации — детальный разбор

### Поток авторизации (подтверждён через Playwright + network capture)

```
[Браузер] → открывает страницу Coupon Redeem
     ↓
[iframe] balance-verify загружается:
  https://www.midasbuy.com/balance-verify?
    country=ru
    &removeIframeBeforeLoad=true
    &from=self.midasbuy_saas.midasbuy_saas
    &lang=ru
    &appid=1450027575
    &shopcode=midasbuy
    &adtag=couponManage
     ↓
[iframe загружает loginSdk2.6.0.js + xmidas SDK]
     ↓
[Страница логина]:
  https://www.midasbuy.com/apps/login/home/ru?appid=1450027575&lang=ru#login
     ↓
[Пользователь вводит email + пароль]
     ↓
[xmidas.encrypt(email + password) → RSA encrypt_msg]
     ↓
POST /midas/usc/v1/123123/emaillogin
  Body: {"encrypt_msg": "<зашифрованные данные>"}
     ↓
[Успех] cookie select_cookie: 0 → 1
        user_id = "Uc5olonf3fdubjb2ionb0"
```

### Ключевые куки сессии

| Cookie | Значение при незалогиненном | После логина |
|--------|---------------------------|--------------|
| `select_cookie` | `0` | **`1`** ← ключевой индикатор! |
| `cookie_control` | `0\|0\|0` | `1\|1\|1` |
| `shopcode` | `midasbuy` | `midasbuy` |
| `UUID` | уникальный ID | тот же |
| `midasbuyDeviceId` | уникальный | тот же |

### Дополнительные куки после логина (Google/аналитика)
```
_ga, _gid, _ga_NQX2JD8STG, _gcl_au, _gat_UA-21773189-2
```

### AppID проекта
```
offerId / appid: 1450027575
merchant_id: 1450027575
mp_app_id: 202212191737170171064960
```

---

## 🛡️ Защита от ботов

| Механизм | Статус | Детали |
|----------|--------|--------|
| CAPTCHA | ❌ Не обнаружена | На уровне API |
| Cloudflare | ❌ Нет | Nginx + собственный CDN |
| **Tencent TDRC** | ✅ Активна | `tdrc.js` — Device Risk Control |
| **harvestsharp FP** | ✅ Активна | `pay.harvestsharp.com/cgi-bin/fp-behv` — fingerprinting |
| **RSA-шифрование пароля** | ✅ Активна | xmidas.encrypt перед логином |
| Rate Limiting | ✅ Активна | `x-ratelimit-limit: 30` |
| DeviceID | ✅ Активна | cookie `midasbuyDeviceId` — 1 год |

---

## ⚙️ Rate Limiting

```http
x-ratelimit-limit: 30
x-ratelimit-remaining: 29
```
- Лимит: **30 запросов** (вероятно, в минуту)
- Заголовки присутствуют на всех API-вызовах

---

## 📝 Сообщения об ошибках купонов (из JS компонентов)

```js
// Из компонента MRedeemCoupon:
text257: 'This redemption code has expired. Please check and try again.'
text258: 'The redemption code is invalid. Please check and try again.'
text260: 'This redemption code has already been used.'
text261: 'The redemption request timed out. Please try again'
text262: 'The request has been flagged for additional review. Please try again later.'
text263: 'Verification failed. Please try again later or contact support.'
text264: 'A system error occurred during verification. Please try again later.'
text265: 'A system error occurred while querying the redemption code. Please try again later.'
text267: 'CDK Code is not currently supported'
text268: 'The Code you entered seems to be a Redeem code. Please switch to redeem it.'
text270: 'Redeem Code is not currently supported'
text281: 'We have detected that your account has been banned. please return to the game to confirm'
text283: 'This redemption code can only be redeemed for game accounts in the {0}...'
text294: 'Code format error, please try again.'
text372: 'The coupon has expired'
text373: 'The coupon has already been redeemed'
text374: 'The coupon is invalid. Please try again later'
text375: 'Please enter redeem code'
text376: 'Invalid redeem code format'
text378: 'Invalid redeem code'
text381: 'Failed to redeem coupon'
```

---

## 🤖 Финальное решение по автоматизации

### Выбранный подход: **Playwright (сессия) + httpx (API)**

```
[Playwright]
  1. Запуск headless Chromium
  2. Открытие Coupon Redeem страницы
  3. Автоматический логин через login popup (loginSdk обрабатывает RSA сам)
  4. Ожидание cookie select_cookie=1
  5. Сохранение storage_state (куки + localStorage)

[httpx / requests]
  6. Загрузка сохранённой сессии
  7. POST /frontend/api/midasbuy/v1/coupon/redeem + куки
  8. Парсинг результата
  9. Возврат статуса боту

[Playwright (fallback)]
  - Если HTTP API не работает → полная браузерная активация
  - Скриншот при ошибке
```

### Преимущества подхода
- ✅ Playwright автоматически обрабатывает RSA-шифрование через JS
- ✅ Сессия сохраняется — один логин → много активаций
- ✅ httpx быстрее браузера для самой активации
- ✅ Playwright как fallback при проблемах с API

---

## 📌 Ключевые URL

```
# Целевая страница
https://www.midasbuy.com/shop/pagedoo/ct1744785094_QMGQJMGD/mobile/index.html
  ?from=self.midasbuy_saas&adtag=couponManage#/pages/p-wgbu/

# Страница авторизации
https://www.midasbuy.com/apps/login/home/ru?appid=1450027575&lang=ru#login

# balance-verify iframe
https://www.midasbuy.com/balance-verify
  ?country=ru&removeIframeBeforeLoad=true&from=self.midasbuy_saas.midasbuy_saas
  &lang=ru&appid=1450027575&shopcode=midasbuy&adtag=couponManage

# API base
https://www.midasbuy.com/frontend/api/midasbuy/v1/

# Основные API endpoints
POST /frontend/api/midasbuy/v1/coupon/redeem          ← активация купона
POST /midas/usc/v1/123123/emaillogin                   ← логин
POST /frontend/api/midasbuy/v1/app/get_app_category_list
POST /frontend/api/midasbuy/vip/v1/queryVip

# CDN компонентов
https://pagedoo.midasbuy.com/cdn/materials/dist/gems-materials-midasbuy_saas_materials@1780999150/
```

---

## 🧪 Результаты тестирования API

| Endpoint | Method | Без auth | С auth | Примечание |
|----------|--------|----------|--------|------------|
| `/frontend/api/midasbuy/v1/coupon/redeem` | POST | 401 TRPC | ❓ | Нужен TRPC-токен из сессии |
| `/midas/usc/v1/123123/emaillogin` | POST | 200 | — | RSA encrypt_msg обязателен |
| `/frontend/api/midasbuy/v1/app/get_app_category_list` | POST | 200 | 200 | Открытый |
| `/cgi-bin/oversea_web/coupon/v1/redeem` | POST | 302→404 | — | Устаревший путь |
