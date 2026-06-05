# Arc Daily Task Bot

Bot otomatis untuk daily task [Arc Community](https://community.arc.io) — baca 5 artikel + tonton 4 video + daily-active = **27 poin/hari**.

> Skor harian maksimal (aturan resmi Arc):
> - **Read Content**: 2 poin × 5/hari = 10
> - **Watch a Video**: 4 poin × 4/hari = 16
> - **Daily Active**: 1 poin
> - **Total = 27 poin/hari**

## Kenapa bot biasa GAGAL (dan bot ini jalan)

Arc/Gradual ngitung engagement lewat **6 layer**. Kalau satu aja miss, read/watch **ga keitung**:

| Layer | Yang dicek | Fix di bot ini |
|---|---|---|
| 1. Auth | `token-v2` JWT valid | inject cookie |
| 2. Cloudflare | `_cfuvid` + `__cf_bm` | cookie jar lengkap |
| 3. GDPR | banner OneTrust harus hilang | `ENGAGEMENT_JS` remove banner |
| 4. **Visibility** | `document.visibilityState=visible` | **override (ini paling sering ke-miss!)** |
| 5. Engagement | dwell ≥ 2 menit + scroll asli | 180s + `mouse.wheel` (isTrusted) |
| 6. Video | Wistia iframe play | autoplay param + klik tengah iframe, fresh context/video |

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
playwright install-deps chromium   # Linux/VPS only
```

### 2. Siapkan `cookies.json`

Login ke `community.arc.io` di Chrome, pakai extension **Cookie-Editor** → **Export as JSON** → simpan jadi `cookies.json` di folder ini.

> ⚠️ Cookie `token-v2` Arc itu JWT yang **expired tiap 2 jam**. Buat cron harian, idealnya pakai profil Chrome persisten yang login sekali (auto-refresh). Untuk run manual, export cookie segar tepat sebelum jalan.

### 3. (Opsional) `.env` buat webhook Discord

```env
DISCORD_WEBHOOK=https://discord.com/api/webhooks/xxx/yyy
CHROME_PROFILE=/home/ubuntu/arc-chrome-profile
```

## Cara Pakai

```bash
# VPS headless (pakai xvfb biar browser headed = lolos deteksi)
xvfb-run --auto-servernum python arc_daily.py

# Debug dengan window
python arc_daily.py --no-headless

# Dengan laporan Discord
python arc_daily.py --webhook "https://discord.com/api/webhooks/xxx/yyy"
```

> Webhook Discord dari VPS sering kena Cloudflare error 1010 — bot ini udah kirim **User-Agent browser** biar lolos. Ga perlu proxy.

Durasi sekali jalan ≈ **20-25 menit** (5 artikel × 180s + 4 video × 90s + 150s final wait). Wajar — dwell time itu yang bikin keitung.

## Auto-run Tiap Hari (cron)

```bash
crontab -e
```

```
0 1 * * * cd /home/ubuntu/Arc-Daily && xvfb-run --auto-servernum python arc_daily.py >> arc.log 2>&1
```

## Catatan Penting

- **Cek poin ≥2 menit setelah selesai** — tracker Gradual kadang delayed 2-3 menit (bot udah nunggu 150s di akhir).
- Tiap video pakai **context baru** biar tracker ga nganggep "udah pernah liat".
- Headless polos **ga akan keitung** (visibility=hidden). Selalu pakai `xvfb-run` di VPS.
