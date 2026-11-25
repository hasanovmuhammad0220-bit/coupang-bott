# Coupang chegirmalar boti

Har kuni soat **07:45 (Koreya vaqti)** Coupang Goldbox'dagi chegirmasi eng katta 20 ta mahsulotni Telegram guruhingizga tashlaydi.

## 0. Tayyorgarlik
1. **Apify**: apify.com → Sign up (bepul) → Settings → API & Integrations → **API token** ni nusxalang.
2. **Bot**: Telegramda @BotFather → `/newbot` → nom va `..._bot` bilan tugaydigan username bering → tokenni nusxalang.
3. **Botni guruhga qo'shing**: guruh → nomiga bosing → **A'zo qo'shish** → botni qidirib qo'shing.

## 1. Fayllarni GitHub'ga yuklash
1. github.com → yuqori o'ngdagi **+** → **New repository**.
2. Nom bering (masalan `coupang-bot`), **Private** ni tanlang → **Create repository**.
3. **uploading an existing file** havolasini bosing.
4. ZIP ichidagi **hamma fayl va papkalarni** (`bot`, `.github`, `tests`, `README.md`) sudrab tashlang → **Commit changes**.
   - `.github` papkasi ko'rinmasa: **Add file → Create new file** → nomiga `.github/workflows/daily.yml` yozing va fayl mazmunini joylang. `chat-id.yml` uchun ham shunday.

## 2. Maxfiy kalitlarni qo'yish
Repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Nomi | Qiymati |
|---|---|
| `APIFY_TOKEN` | Apify → Settings → API & Integrations dagi token |
| `TELEGRAM_BOT_TOKEN` | @BotFather bergan token |
| `TELEGRAM_CHAT_ID` | 3-qadamda topiladi |

## 3. Guruh ID sini topish
1. Bot guruh a'zosi ekanini tekshiring, keyin guruhga yozing: `/start@BOTINGIZ_NOMI`
2. Repo → **Actions** → **Guruh ID sini topish** → **Run workflow**.
3. Tugagach, ichiga kirib **Chat ID** qadamini oching — **minus bilan boshlanadigan** raqamni nusxalang (masalan `-100…` yoki `-4…`).
4. Uni `TELEGRAM_CHAT_ID` secret'iga qo'ying.

## 4. Sinab ko'rish
Repo → **Actions** → **Kunlik chegirmalar** → **Run workflow**. Bir necha daqiqada guruhga postlar tushadi.
Shundan keyin bot har kuni o'zi ishlaydi.

## Bilish kerak
- Apify bepul tarifi: oyiga $5. Bot kuniga ~40 qator oladi (~$0.13), oyiga ~$4.
- GitHub jadvali bir necha daqiqaga kechikishi mumkin.
- Har bir qo'lda **Run workflow** ham ~$0.13 sarflaydi — oyiga bir necha marta sinash mumkin.
- Agar loglarda "superguruhga aylangan" xatosi chiqsa: o'sha yerda ko'rsatilgan yangi ID ni `TELEGRAM_CHAT_ID` ga qo'ying.
- Repo **public** bo'lsa va 60 kun o'zgarmasa, GitHub jadvalni to'xtatishi mumkin — Actions'da **Enable** ni bosing.
- Coupang Partners API kaliti olinganda faqat `fetch_goldbox` funksiyasini almashtirish kifoya.
