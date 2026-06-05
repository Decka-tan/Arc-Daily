# Panduan Arc Daily Bot — Bahasa Awam

Bot ini ngerjain tugas harian [community.arc.io](https://community.arc.io) otomatis:
**5 artikel + 4 video + absen = 27 poin/hari**. Sekali jalan ±20 menit.

> ⚠️ **BACA INI DULU — penting:**
> 1. "Kunci login" (cookie) Arc **cuma hidup 2 jam**. Jadi ambil cookie **PERSIS sebelum** jalanin bot. Telat = login gagal.
> 2. Bot sengaja jalan lama (±20 menit). Itu normal, biar dianggap baca beneran.
> 3. Cek poin **2-3 menit setelah** bot selesai (nyatetnya agak telat).

---

# BAGIAN 1 — Jalan di Laptop (Windows)

Paling gampang buat nyoba. Laptop harus nyala selama bot jalan.

### 1. Install Python
- Buka https://www.python.org/downloads/
- Klik **Download Python**
- Buka file-nya → **CENTANG "Add Python to PATH"** → Install Now

### 2. Download bot
- Buka https://github.com/Decka-tan/Arc-Daily
- Tombol hijau **Code** → **Download ZIP** → extract (misal ke Desktop)

### 3. Buka Terminal di folder bot
- Masuk folder hasil extract (`Arc-Daily-main`)
- Klik kanan area kosong → **Open in Terminal**

### 4. Pasang perlengkapan (sekali aja)
Ketik satu per satu, Enter tiap baris:
```
pip install -r requirements.txt
python -m playwright install chromium
```

### 5. Ambil cookie (kunci login)
- Buka https://community.arc.io di Chrome, **pastikan udah login**
- Pasang extension **Cookie-Editor** dari Chrome Web Store
- Klik ikon Cookie-Editor → **Export** → **Export as JSON** (otomatis ke-copy)
- Buka **Notepad** → Paste → Save As → nama file: `cookies.json` → simpan di folder bot
  (pas Save As, ganti "Save as type" jadi **All Files** biar ga jadi .txt)

### 6. Jalanin
```
python arc_daily.py --no-headless
```
Jendela Chrome kebuka, jalan sendiri. **Jangan ditutup.** Tunggu sampai muncul **✅ SELESAI!**

### 7. Cek poin
Tunggu 2-3 menit → buka https://community.arc.io/home/contributors/my-contributions

---

# BAGIAN 2 — Jalan di VPS (otomatis tiap hari)

Buat yang udah bisa Bagian 1 dan mau bener-bener AFK. VPS = Linux, perintahnya **`python3`** (bukan `python`).

### 1. Pasang perlengkapan (sekali aja)
```
sudo apt-get update && sudo apt-get install -y python3 python3-pip git xvfb
git clone https://github.com/Decka-tan/Arc-Daily
cd Arc-Daily
pip3 install -r requirements.txt
python3 -m playwright install chromium
python3 -m playwright install-deps chromium
```

### 2. Taruh cookie
Bikin file `cookies.json` di folder `Arc-Daily` (isi dari Cookie-Editor, sama kayak Bagian 1 langkah 5).

### 3. Jalanin
```
xvfb-run --auto-servernum python3 arc_daily.py
```
> `xvfb-run` itu WAJIB di VPS. Tanpa itu browser dianggap "ga keliatan" dan poin GA keitung.

### 4. Auto tiap hari (jam 8 pagi WIB)
```
crontab -e
```
Tambah baris ini (sesuaikan path folder):
```
0 1 * * * cd ~/Arc-Daily && xvfb-run --auto-servernum python3 arc_daily.py >> arc.log 2>&1
```
> Masalah: cookie mati tiap 2 jam, jadi cron harian butuh cookie yang masih valid. Solusi auto-refresh belum jadi — sementara ini paling pas dijalanin manual pas cookie fresh.

---

# BAGIAN 3 — (Opsional) Lapor ke Discord

Biar tiap selesai dikabarin hasilnya.

### Bikin webhook:
1. Discord → pilih channel → ⚙️ **Edit Channel**
2. **Integrations** → **Webhooks** → **New Webhook** → **Copy Webhook URL**

### Pakainya:
```
python arc_daily.py --no-headless --webhook "TEMPEL_URL_DISINI"
```
(VPS: ganti `python` → `python3`, tambah `xvfb-run --auto-servernum` di depan)

---

# Cara Update cookies.json (tiap kali mau jalanin)

Karena cookie mati tiap 2 jam, tiap mau jalanin bot kamu ambil cookie baru. Langkah ambilnya sama: buka community.arc.io (udah login) → Cookie-Editor → **Export as JSON**. Bedanya cara nyimpennya:

### Di Laptop (Windows) — gampang
- Buka file `cookies.json` lama pakai **Notepad**
- **Ctrl+A** (blok semua) → **Delete** → **Paste** (Ctrl+V) cookie baru → **Save** (Ctrl+S)
- Selesai.

### Di VPS (Linux) — pakai 1 perintah
Ga usah nano/editor. Ketik ini (ganti folder kalau beda), terus **paste** cookie, lalu di baris baru ketik `EOF` + Enter:

```
cat > ~/Arc-Daily/cookies.json << 'EOF'
```
(setelah Enter, paste isi cookie dari Cookie-Editor)
(lalu ketik di baris baru:)
```
EOF
```

Contoh lengkap tampilannya:
```
ubuntu@vps:~$ cat > ~/Arc-Daily/cookies.json << 'EOF'
> [ ...paste cookie panjang di sini... ]
> EOF
ubuntu@vps:~$
```
Tanda `>` muncul sendiri, itu normal. Setelah ketik `EOF` + Enter, cookie kesimpen.

Cek udah masuk apa belum:
```
head -c 200 ~/Arc-Daily/cookies.json
```
Kalau muncul `[{"domain":".community.arc.io"...` berarti udah bener.

---

# Kalau Error

| Tulisan | Solusi |
|---|---|
| `login gagal` / `cookie expired` | Cookie basi (lewat 2 jam). Ambil ulang (langkah 5). |
| `python: not found` (di VPS) | Pakai `python3`, bukan `python` |
| `playwright: ... not found` | Ulangi langkah pasang perlengkapan |
| `cookies.json ... No such file` | File belum dibuat / salah folder / kesimpan jadi .txt |

Stuck? Screenshot error-nya, kirim ke yang ngajakin.

---

> 📌 **Status jujur:** versi script ini baru dirombak pakai metode yang terbukti dapet 25 poin (lewat Hermes). Tapi script standalone-nya **belum 100% dites end-to-end**. Tes resmi pertama: besok pas limit harian reset. Kalau ada error pas dijalanin, wajar — laporin biar dibenerin.
