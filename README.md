# Arc Daily Task Bot

Bot otomatis untuk daily task [Arc Community](https://community.arc.network) — baca 5 artikel + tonton 1 video + check-in = **35 poin/hari**.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
playwright install-deps chromium  # Linux/VPS only
```

### 2. Buat file `.env`

```bash
cp .env.example .env
nano .env
```

Isi dengan kredensial kamu:

```env
LINKEDIN_EMAIL=your@email.com
LINKEDIN_PASSWORD=yourpassword
DISCORD_WEBHOOK=https://discord.com/api/webhooks/xxx/yyy
COOKIES_PATH=cookies.json
```

> `.env` tidak akan ter-commit ke GitHub (sudah ada di `.gitignore`).

### 3. Siapkan cookies (pertama kali)

Login manual dulu untuk generate `cookies.json`:
1. Buka `community.arc.network` di Chrome, login via LinkedIn
2. Install extension [Cookie-Editor](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm)
3. Klik icon Cookie-Editor → **Export as JSON**
4. Simpan sebagai `cookies.json` di folder ini

Setelah cookies ada, bot akan **auto-refresh login via LinkedIn** kalau cookies expired — tidak perlu manual lagi.

## Cara Pakai

```bash
# Jalankan biasa (headless, cocok untuk VPS)
python arc_daily.py

# Dengan laporan ke Discord
python arc_daily.py --webhook "https://discord.com/api/webhooks/xxx/yyy"

# Tampilkan browser (untuk debug)
python arc_daily.py --no-headless
```

Semua config bisa juga lewat `.env` — tidak perlu passing argumen setiap kali.

## Auto-run Tiap Hari (VPS/Linux)

```bash
crontab -e
```

Tambahkan (jalan jam 08:00 WIB = 01:00 UTC):

```
0 1 * * * cd /home/ubuntu/ArcSign-Skill && /home/ubuntu/arcenv/bin/python arc_daily.py >> arc.log 2>&1
```

## Laporan Discord

Bot kirim embed ke Discord setiap selesai jalan:

- Daftar artikel yang dibaca
- Video yang ditonton  
- Estimasi poin (maks 35)
- Link ke my-contributions
- Alert merah kalau gagal login

## Flow Auto-Login LinkedIn

1. Bot inject `cookies.json`
2. Cek apakah sudah login
3. Kalau belum → auto login via LinkedIn dengan kredensial di `.env`
4. Simpan cookie baru ke `cookies.json`
5. Lanjut jalankan task

> Kalau LinkedIn minta 2FA/CAPTCHA, auto-login gagal dan bot kirim alert ke Discord.
