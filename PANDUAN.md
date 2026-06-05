# Panduan Garap Arc Daily (Bahasa Awam, Anti-Ribet)

Buat kamu yang **ga ngerti coding sama sekali**. Ikutin pelan-pelan, ga ada yang susah kok.

Bot ini bakal otomatis: **baca 5 artikel + nonton 4 video + absen harian = 27 poin/hari** di [community.arc.io](https://community.arc.io). Kamu tinggal jalanin, dia kerja sendiri ~20 menit.

---

## 🅰️ CARA GAMPANG: Jalan di Laptop Sendiri (ga butuh VPS)

Cocok buat nyobain dulu. Laptop harus nyala selama bot jalan (~20 menit).

### Langkah 1 — Install Python (sekali aja)

1. Buka [python.org/downloads](https://www.python.org/downloads/)
2. Klik tombol kuning **Download Python**
3. Buka file-nya, **CENTANG "Add Python to PATH"** (penting!), lalu Install

### Langkah 2 — Download bot-nya

1. Buka [github.com/Decka-tan/Arc-Daily](https://github.com/Decka-tan/Arc-Daily)
2. Klik tombol hijau **Code** → **Download ZIP**
3. Extract ZIP-nya ke folder mana aja (misal Desktop)

### Langkah 3 — Buka "Terminal" di folder itu

- **Windows**: buka folder hasil extract → klik kanan area kosong → **Open in Terminal** (atau ketik `cmd` di address bar folder lalu Enter)
- **Mac**: buka aplikasi **Terminal**, ketik `cd ` (pakai spasi) lalu seret folder-nya ke Terminal, Enter

### Langkah 4 — Pasang perlengkapan (copy-paste satu-satu, Enter tiap baris)

```
pip install -r requirements.txt
```
```
playwright install chromium
```

Tunggu sampai selesai (sekali ini doang).

### Langkah 5 — Ambil "kunci login" (cookies)

Ini biar bot bisa masuk pakai akun kamu:

1. Buka [community.arc.io](https://community.arc.io) di Chrome, **pastikan kamu udah login**
2. Pasang extension **Cookie-Editor** dari Chrome Web Store
3. Klik ikon Cookie-Editor → klik **Export** (ikon di kanan bawah) → **Export as JSON**
4. Buat file baru namanya **`cookies.json`** di folder bot, **paste** isinya, simpan

> Gampangnya: buka Notepad → paste → Save As → ketik `cookies.json` (pakai tanda kutip) di folder bot.

### Langkah 6 — JALANKAN

```
python arc_daily.py --no-headless
```

Bakal kebuka jendela Chrome dan jalan sendiri. **Jangan ditutup**, biarin ~20 menit sampai muncul tulisan **✅ SELESAI!**

### Langkah 7 — Cek hasil

Tunggu 2-3 menit, buka [halaman poin kamu](https://community.arc.io/home/contributors/my-contributions). Harusnya nambah artikel & video baru. 🎉

---

## 🅱️ CARA OTOMATIS: Pakai VPS (jalan tiap hari sendiri)

Kalau udah jago Cara A dan mau **bener-bener AFK** (ga usah nyalain laptop), baru pindah ke VPS. VPS = komputer sewaan yang nyala 24 jam.

Langkahnya mirip, bedanya di Linux pakai **`python3`** (bukan `python`):

```
# pasang perlengkapan (sekali aja):
pip3 install -r requirements.txt
python3 -m playwright install chromium
python3 -m playwright install-deps chromium
sudo apt-get install -y xvfb

# jalanin (pakai xvfb biar lolos deteksi bot):
xvfb-run --auto-servernum python3 arc_daily.py
```

> Kalau `python3` juga ga ada: `sudo apt-get install -y python3 python3-pip`

Lalu set biar jalan otomatis tiap jam 8 pagi:
```
crontab -e
```
Tambahin baris ini (ganti path sesuai folder kamu):
```
0 1 * * * cd ~/Arc-Daily && xvfb-run --auto-servernum python3 arc_daily.py >> arc.log 2>&1
```

---

## ⚠️ Yang WAJIB Diingat

1. **Kunci login (cookies) cuma tahan ~2 jam.** Jadi ambil cookie-nya **tepat sebelum** jalanin bot. Kalau bot bilang "login gagal", berarti cookie udah basi — ulangi Langkah 5.

2. **Cek poin 2-3 menit SETELAH bot selesai**, jangan buru-buru. Sistem Arc nyatet poinnya agak telat.

3. **1 akun = 1 cookies.json.** Kalau mau garap rame-rame, tiap orang export cookie dari akun masing-masing.

4. Bot jalan ~20 menit. Itu normal — sengaja lama biar dianggap "beneran baca", bukan bot.

---

## 😵 Kalau Error

| Tulisan error | Artinya | Solusi |
|---|---|---|
| `login gagal` / `cookie expired` | Cookie udah basi | Ambil cookie baru (Langkah 5) |
| `python: command not found` | Di Windows: ulangi Langkah 1, centang "Add to PATH". Di Linux/VPS: pakai `python3` (bukan `python`) | |
| `playwright not found` | Belum install | Jalanin Langkah 4 lagi |

Stuck? Screenshot tulisannya, tanya ke yang ngajakin kamu. 👍
