"""
Arc Community Daily Task Bot
Otomatis: baca 5 artikel + tonton 1 video + check-in = ~35 poin
Jalankan: python arc_daily.py --cookies cookies.json
"""

import asyncio
import json
import os
import sys
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_URL = "https://community.arc.io"


def send_discord(webhook_url: str, success_articles: list, watched_video, points: int,
                 error: str = None):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if error:
        color = 0xFF4444
        title = "❌ Arc Daily Task — GAGAL"
        description = f"```{error}```"
        fields = []
    else:
        color = 0x00C853 if points >= 30 else 0xFFAA00
        title = "✅ Arc Daily Task — Selesai"
        article_list = "\n".join(
            f"{i}. {a['title'][:60]}" for i, a in enumerate(success_articles, 1)
        ) or "—"
        description = ""
        fields = [
            {"name": "📖 Artikel dibaca", "value": f"```{article_list}```", "inline": False},
            {"name": "🎬 Video", "value": watched_video['title'][:70] if watched_video else "—", "inline": True},
            {"name": "💰 Estimasi poin", "value": str(points), "inline": True},
            {"name": "🔗 Cek poin", "value": "[my-contributions](https://community.arc.network/home/contributors/my-contributions)", "inline": True},
        ]

    payload = json.dumps({
        "embeds": [{
            "title": title,
            "description": description,
            "color": color,
            "fields": fields,
            "footer": {"text": now},
        }]
    }).encode()

    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"📨 Laporan terkirim ke Discord. (status: {resp.status})")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"⚠️  Gagal kirim ke Discord: HTTP {e.code} - {body}")
    except urllib.error.URLError as e:
        print(f"⚠️  Gagal kirim ke Discord: {e}")


async def scroll_load(page, max_rounds=30, stable_target=2):
    await page.wait_for_timeout(3000)
    last_h = 0
    stable = 0
    for _ in range(max_rounds):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1500)
        btn = await page.evaluate("""
            () => {
                const b = [...document.querySelectorAll('button')]
                    .find(b => /^load more$/i.test(b.textContent.trim()));
                if (b) { b.scrollIntoView(); b.click(); return true; }
                return false;
            }
        """)
        if btn:
            await page.wait_for_timeout(2000)
            stable = 0
            continue
        h = await page.evaluate("() => document.body.scrollHeight")
        if h == last_h:
            stable += 1
            if stable >= stable_target:
                break
        else:
            stable = 0
            last_h = h


async def check_logged_in(page):
    await page.goto(f"{BASE_URL}/home", wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(3000)
    logged_in = await page.evaluate("""
        () => !![...document.querySelectorAll('header img, nav img')]
            .find(i => /\\/avatar\\//i.test(i.src || ''))
    """)
    return logged_in


async def get_history(page):
    print("📋 Ambil riwayat dari my-contributions...")
    await page.goto(f"{BASE_URL}/home/contributors/my-contributions",
                    wait_until="domcontentloaded", timeout=30000)
    await scroll_load(page, max_rounds=40, stable_target=2)
    result = await page.evaluate("""
        () => {
            const main = document.querySelector('main');
            if (!main) return { readTitles: [], videoTitles: [] };
            const text = main.innerText;
            const readTitles = [], videoTitles = [];
            const lines = text.split('\\n');
            for (let i = 0; i < lines.length; i++) {
                if (lines[i].includes('Read Content') || lines[i].includes('Watch a Video')) {
                    for (let j = i + 1; j < Math.min(i + 5, lines.length); j++) {
                        if (lines[j].includes(' · ')) {
                            const title = lines[j].split(' · ')[1];
                            if (title && title.trim()) {
                                if (lines[i].includes('Read Content')) readTitles.push(title.trim());
                                else videoTitles.push(title.trim());
                            }
                            break;
                        }
                    }
                }
            }
            return { readTitles, videoTitles };
        }
    """)
    print(f"   Sudah baca: {len(result['readTitles'])} artikel, sudah tonton: {len(result['videoTitles'])} video")
    return set(result['readTitles']), set(result['videoTitles'])


async def get_candidates(page):
    print("🔍 Scan konten dari homepage...")
    await page.goto(f"{BASE_URL}/home", wait_until="domcontentloaded", timeout=30000)
    await scroll_load(page, max_rounds=30, stable_target=2)
    items = await page.evaluate("""
        () => {
            const links = [...document.querySelectorAll('a[href]')];
            const items = [], seen = new Set();
            for (const a of links) {
                const href = a.getAttribute('href') || '';
                const m = href.match(/\\/home\\/(blogs|resources|externals|videos)\\/([^/?#]+)/);
                if (!m) continue;
                const slug = `${m[1]}/${m[2]}`;
                if (seen.has(slug)) continue;
                seen.add(slug);
                let card = a, found = null;
                for (let d = 0; d < 8 && card; d++, card = card.parentElement) {
                    const lines = (card.innerText || '').split('\\n').map(s => s.trim()).filter(Boolean);
                    if (lines.length < 2) continue;
                    const type = lines.find(l => ['Video','Blog','Resource','External Content'].includes(l));
                    const title = lines.find(l => l.length >= 5 &&
                        !['Video','Blog','Resource','External Content','Replay','Read more','Watch'].includes(l) &&
                        !/^\\d+:\\d+$/.test(l));
                    if (type && title) { found = { type, title: title.slice(0, 120), slug }; break; }
                }
                if (found) items.push(found);
            }
            return items;
        }
    """)
    print(f"   Total kandidat ditemukan: {len(items)}")
    return items


def filter_candidates(items, read_titles, video_titles):
    articles = []
    videos = []
    for item in items:
        if item['title'] in read_titles or item['title'] in video_titles:
            continue
        if item['type'] == 'External Content':
            continue  # tidak trigger Read Content scoring
        if item['type'] == 'Video':
            videos.append(item)
        else:  # Blog / Resource
            articles.append(item)
    # Blog dulu, baru Resource
    articles.sort(key=lambda x: 0 if x['type'] == 'Blog' else 1)
    return articles, videos


async def read_articles(page, articles, max_count=5):
    print(f"\n📖 Mulai baca artikel (target: {max_count})...")
    success = []
    fail_streak = 0
    for article in articles:
        if len(success) >= max_count:
            break
        if fail_streak >= 3:
            print("   3x gagal berturut-turut, hentikan fase baca.")
            break
        url = f"{BASE_URL}/home/{article['slug']}"
        print(f"   → {article['type']}: {article['title'][:60]}...")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        except PWTimeout:
            print("     ✗ Timeout navigasi, skip.")
            fail_streak += 1
            continue

        title = await page.evaluate("""
            async () => {
                await new Promise(r => setTimeout(r, 3000));
                const h = document.body.scrollHeight;
                for (let i = 1; i <= 10; i++) {
                    window.scrollTo({ top: (h * i) / 11, behavior: 'smooth' });
                    await new Promise(r => setTimeout(r, 3000));
                }
                await new Promise(r => setTimeout(r, 3000));
                return document.title;
            }
        """)
        if title and not any(kw in title.lower() for kw in ['404', 'error', 'not found']):
            success.append(article)
            fail_streak = 0
            print(f"     ✓ Berhasil ({len(success)}/{max_count})")
        else:
            fail_streak += 1
            print(f"     ✗ Gagal (title: {title})")

    return success


async def watch_video(page, videos, max_try=3):
    print(f"\n🎬 Mulai tonton video...")
    for video in videos[:max_try]:
        url = f"{BASE_URL}/home/{video['slug']}"
        print(f"   → {video['title'][:60]}...")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        except PWTimeout:
            print("     ✗ Timeout, coba video berikutnya.")
            continue

        await page.wait_for_timeout(3000)

        # Cari tombol Play Video / Play video
        play_btn = await page.evaluate("""
            () => {
                const btns = [...document.querySelectorAll('button, [role="button"]')];
                const btn = btns.find(b => /^Play [Vv]ideo/.test((b.getAttribute('aria-label') || b.textContent || '').trim()));
                if (btn) { btn.click(); return 'clicked-button'; }
                // fallback: iframe
                const f = document.querySelector('iframe[src*="wistia"], iframe[src*="player"], iframe[allow*="autoplay"]');
                if (f) { f.click(); return 'clicked-iframe'; }
                return 'not-found';
            }
        """)
        print(f"     Play result: {play_btn}")

        if play_btn == 'not-found':
            print("     ✗ Tombol play tidak ditemukan, coba video berikutnya.")
            continue

        # Tunggu 40 detik (video dianggap ditonton)
        print("     ⏳ Menunggu 40 detik...")
        await page.evaluate("() => new Promise(r => setTimeout(r, 40000))")
        print(f"     ✓ Video ditonton: {video['title'][:60]}")
        return video

    print("   ✗ Tidak ada video yang berhasil ditonton.")
    return None


def load_cookies(path: str) -> list:
    with open(path) as f:
        data = json.load(f)
    # Support format array langsung atau {cookies: [...]}
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and 'cookies' in data:
        return data['cookies']
    raise ValueError("Format cookie tidak dikenali. Gunakan array JSON atau {\"cookies\": [...]}")


def normalize_cookies(cookies: list) -> list:
    result = []
    for cookie in cookies:
        c = dict(cookie)
        if 'sameSite' in c:
            ss = c['sameSite']
            c['sameSite'] = 'None' if ss in ('no_restriction', 'unspecified', 'None', None) else \
                            'Lax' if ss == 'lax' else 'Strict'
        # Cookie-Editor pakai expirationDate, Playwright butuh expires
        if 'expirationDate' in c:
            c['expires'] = c.pop('expirationDate')
        for key in ['id', 'storeId', 'session', 'hostOnly', 'firstPartyDomain', 'partitionKey']:
            c.pop(key, None)
        result.append(c)
    return result


async def linkedin_login(page, email: str, password: str) -> bool:
    print("🔑 Login via LinkedIn...")
    try:
        await page.goto(f"{BASE_URL}/home", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        # Klik tombol login LinkedIn di Arc
        login_btn = await page.evaluate("""
            () => {
                const btns = [...document.querySelectorAll('a, button')];
                const btn = btns.find(b => /linkedin/i.test(b.textContent + b.getAttribute('href') + ''));
                if (btn) { btn.click(); return true; }
                return false;
            }
        """)
        if not login_btn:
            # Coba cari tombol sign in dulu
            await page.evaluate("""
                () => {
                    const btn = [...document.querySelectorAll('a, button')]
                        .find(b => /sign in|log in|login/i.test(b.textContent));
                    if (btn) btn.click();
                }
            """)
            await page.wait_for_timeout(2000)
            await page.evaluate("""
                () => {
                    const btn = [...document.querySelectorAll('a, button')]
                        .find(b => /linkedin/i.test(b.textContent + b.getAttribute('href') + ''));
                    if (btn) btn.click();
                }
            """)

        await page.wait_for_timeout(3000)

        # Sekarang di halaman LinkedIn login
        current_url = page.url
        if 'linkedin.com' not in current_url:
            print("   ⚠️  Tidak redirect ke LinkedIn, coba langsung ke LinkedIn login")
            await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=20000)

        await page.wait_for_timeout(2000)

        # Isi email
        await page.fill('#username', email)
        await page.wait_for_timeout(500)
        await page.fill('#password', password)
        await page.wait_for_timeout(500)
        await page.click('[type="submit"]')

        # Tunggu redirect balik ke Arc (max 30 detik)
        print("   ⏳ Menunggu redirect setelah login...")
        for _ in range(30):
            await page.wait_for_timeout(1000)
            if 'community.arc.network' in page.url:
                break
            if 'checkpoint' in page.url or 'verify' in page.url or 'challenge' in page.url:
                print("   ⚠️  LinkedIn minta verifikasi tambahan (2FA/CAPTCHA)")
                print("   ❌ Auto-login gagal, perlu manual")
                return False

        await page.wait_for_timeout(3000)
        logged_in = await check_logged_in(page)
        if logged_in:
            print("   ✅ LinkedIn login berhasil!")
            # Simpan cookie baru
            cookies = await page.context.cookies()
            cookies_path = os.environ.get("COOKIES_PATH", "cookies.json")
            with open(cookies_path, 'w') as f:
                json.dump(cookies, f, indent=2)
            print(f"   💾 Cookie baru disimpan ke {cookies_path}")
            return True
        return False
    except Exception as e:
        print(f"   ❌ Login error: {e}")
        return False


async def main(cookies_path: str, headless: bool, webhook_url: str = None):
    li_email = os.environ.get("LINKEDIN_EMAIL")
    li_password = os.environ.get("LINKEDIN_PASSWORD")

    if webhook_url:
        print(f"📡 Webhook aktif: {webhook_url[:50]}...")
    else:
        print("⚠️  Tidak ada webhook URL — laporan tidak akan dikirim ke Discord!")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )

            if Path(cookies_path).exists():
                print("🍪 Inject cookies...")
                raw = load_cookies(cookies_path)
                await context.add_cookies(normalize_cookies(raw))

            page = await context.new_page()

            print("🔐 Cek status login...")
            logged_in = await check_logged_in(page)

            if not logged_in:
                if li_email and li_password:
                    print("🔄 Cookie expired, coba auto-login LinkedIn...")
                    logged_in = await linkedin_login(page, li_email, li_password)
                if not logged_in:
                    msg = "Login gagal. Set LINKEDIN_EMAIL & LINKEDIN_PASSWORD di .env, atau perbarui cookies.json."
                    print(f"❌ {msg}")
                    if webhook_url:
                        send_discord(webhook_url, [], None, 0, error=msg)
                    await browser.close()
                    sys.exit(1)

            print("✅ Login berhasil!")

            read_titles, video_titles = await get_history(page)
            candidates = await get_candidates(page)
            articles, videos = filter_candidates(candidates, read_titles, video_titles)

            print(f"\n📊 Kandidat tersedia: {len(articles)} artikel, {len(videos)} video")

            success_articles = await read_articles(page, articles)
            watched_video = await watch_video(page, videos)

            points = len(success_articles) * 5 + (5 if watched_video else 0) + 5
            remaining_articles = len(articles) - len(success_articles)
            remaining_videos = len(videos) - (1 if watched_video else 0)

            print("\n" + "="*50)
            print("✅ SELESAI!")
            print(f"📖 Berhasil baca {len(success_articles)} artikel:")
            for i, a in enumerate(success_articles, 1):
                print(f"   {i}. {a['title'][:70]}")
            print(f"🎬 Video: {watched_video['title'][:70] if watched_video else '—'}")
            print(f"💰 Estimasi poin: {points}")
            print(f"📦 Sisa stok: {remaining_articles} artikel / {remaining_videos} video")
            print(f"⏰ Waktu: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
            print("   Cek my-contributions dalam ~5 menit")
            print("="*50)

            if webhook_url:
                send_discord(webhook_url, success_articles, watched_video, points)

            await browser.close()

    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        print(f"\n❌ FATAL ERROR:\n{err_msg}")
        if webhook_url:
            send_discord(webhook_url, [], None, 0, error=err_msg[-1500:])
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Arc Community Daily Task Bot")
    parser.add_argument("--cookies", default="cookies.json",
                        help="Path ke file cookies JSON (default: cookies.json)")
    parser.add_argument("--no-headless", action="store_true",
                        help="Tampilkan browser window (untuk debug)")
    parser.add_argument("--webhook", default=os.environ.get("DISCORD_WEBHOOK"),
                        help="Discord webhook URL (atau set env DISCORD_WEBHOOK)")
    args = parser.parse_args()

    asyncio.run(main(args.cookies, headless=not args.no_headless, webhook_url=args.webhook))
