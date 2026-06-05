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

# ── Engagement layers (resep yang terbukti credit poin) ──────────────────
# Dijalankan di tiap halaman SETELAH load. Tanpa ini, Arc/Gradual tracker
# nganggep tab "hidden" / consent belum diterima → read & watch GA diitung.
ENGAGEMENT_JS = """
() => {
    // Layer 3 — buang banner OneTrust (GDPR) yang block pointer events & render
    const sdk = document.getElementById('onetrust-consent-sdk');
    if (sdk) sdk.remove();
    document.querySelectorAll('.onetrust-pc-dark-filter, #onetrust-banner-sdk')
        .forEach(e => e.remove());
    // Layer 4 — paksa tab dianggap visible & fokus
    try {
        Object.defineProperty(document, 'visibilityState', { get: () => 'visible', configurable: true });
        Object.defineProperty(document, 'hidden', { get: () => false, configurable: true });
        document.dispatchEvent(new Event('visibilitychange'));
        window.dispatchEvent(new Event('focus'));
    } catch (e) {}
}
"""

# Di-inject sebelum tiap halaman load (level context) — visibility default visible
VISIBILITY_INIT = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(document, 'visibilityState', { get: () => 'visible', configurable: true });
    Object.defineProperty(document, 'hidden', { get: () => false, configurable: true });
    window.chrome = { runtime: {} };
"""


def send_discord(webhook_url: str, success_articles: list, watched_video, points: int,
                 error: str = None):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if error:
        color = 0xFF4444
        title = "❌ Arc Daily Task — GAGAL"
        description = f"```{error}```"
        fields = []
    else:
        color = 0x00C853 if points >= 25 else 0xFFAA00
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
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        },
        method="POST"
    )
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"https": proxy, "http": proxy} if proxy else {})
    )
    try:
        with opener.open(req, timeout=10) as resp:
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
    # Retry beberapa kali: Chrome di VPS lambat, avatar/UI butuh waktu render
    for attempt in range(6):
        await page.wait_for_timeout(4000)
        signal = await page.evaluate("""
            () => {
                // Sinyal 1: ada avatar user di header/nav
                const hasAvatar = !![...document.querySelectorAll('header img, nav img')]
                    .find(i => /\\/avatar\\//i.test(i.src || ''));
                // Sinyal 2: TIDAK ada tombol Sign in / Log in (kalau logout pasti ada)
                const hasSignIn = !![...document.querySelectorAll('a, button')]
                    .find(b => /^(sign in|log in|login|connect)$/i.test((b.textContent||'').trim()));
                return { hasAvatar, hasSignIn };
            }
        """)
        if signal['hasAvatar']:
            return True
        # Kalau ga ada avatar TAPI juga ga ada tombol login, kemungkinan masih loading → retry
        if not signal['hasSignIn'] and attempt < 5:
            print(f"   ⏳ UI belum siap, retry {attempt+1}/6...")
            continue
        if signal['hasSignIn']:
            return False
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

    api_calls = []
    def on_request(request):
        if 'community.arc.io/api' in request.url:
            body = ""
            try:
                post_data = request.post_data
                if post_data:
                    body = f" | BODY: {post_data[:200]}"
            except Exception:
                pass
            auth = request.headers.get('authorization', 'MISSING')[:30]
            api_calls.append(f"  [REQ] {request.method} {request.url} | AUTH: {auth}{body}")
    def on_response(response):
        if 'community.arc.io/api' in response.url:
            api_calls.append(f"  [RES] {response.status} {response.url}")
    page.on("request", on_request)
    page.on("response", on_response)

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
        api_calls.clear()
        # Navigasi SPA: buka homepage lalu KLIK link artikel (kayak user beneran),
        # bukan goto langsung — biar event "read" client-side ke-trigger
        try:
            await page.goto(f"{BASE_URL}/home", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(2000)
            clicked = await page.evaluate(f"""
                async (slug) => {{
                    // scroll cari link sampai ketemu
                    for (let r = 0; r < 20; r++) {{
                        const a = [...document.querySelectorAll('a[href]')]
                            .find(a => (a.getAttribute('href') || '').includes(slug));
                        if (a) {{ a.scrollIntoView({{block:'center'}}); a.click(); return true; }}
                        window.scrollTo(0, document.body.scrollHeight);
                        await new Promise(r => setTimeout(r, 1200));
                    }}
                    return false;
                }}
            """, article['slug'])
            if not clicked:
                # fallback ke goto langsung kalau link ga ketemu
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            else:
                await page.wait_for_timeout(3000)
        except PWTimeout:
            print("     ✗ Timeout navigasi, skip.")
            fail_streak += 1
            continue

        await page.wait_for_timeout(3000)
        # Layer 3+4: buang OneTrust & paksa visible SETELAH halaman ke-load
        try:
            await page.evaluate(ENGAGEMENT_JS)
        except Exception:
            pass
        # Layer 5: dwell ~180 detik + scroll mouse wheel ASLI (isTrusted=true)
        try:
            await page.mouse.move(640, 360)
            # Scroll turun pelan (≈70 detik)
            for _ in range(20):
                await page.mouse.wheel(0, 350)
                await page.wait_for_timeout(3500)
            # Re-assert visibility (kadang ke-reset) + tetap aktif (≈110 detik)
            await page.evaluate(ENGAGEMENT_JS)
            for i in range(22):
                await page.mouse.wheel(0, -250 if i % 2 else 250)
                await page.wait_for_timeout(5000)
        except Exception as e:
            print(f"     (scroll wheel error: {e})")
        title = await page.title()
        if api_calls:
            print("     📡 API calls detected:")
            for c in api_calls:
                print(c)
        else:
            print("     ⚠️  Tidak ada API call terdeteksi")
        if title and not any(kw in title.lower() for kw in ['404', 'error', 'not found']):
            success.append(article)
            fail_streak = 0
            print(f"     ✓ Berhasil ({len(success)}/{max_count})")
        else:
            fail_streak += 1
            print(f"     ✗ Gagal (title: {title})")

    return success


async def watch_videos(context, cookies, videos, max_count=4):
    """Tonton hingga 4 video. Tiap video pakai context/tab fresh biar tracker
    Wistia ga nganggep 'udah pernah liat' (state pollution). Cap Arc = 4/24jam."""
    print(f"\n🎬 Mulai tonton video (target: {max_count})...")
    watched = []
    for video in videos:
        if len(watched) >= max_count:
            break
        url = f"{BASE_URL}/home/{video['slug']}"
        print(f"   → {video['title'][:60]}...")

        # Layer F: fresh context per video (cookies di-inject ulang)
        vctx = await context.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )
        await vctx.add_init_script(VISIBILITY_INIT)
        try:
            await vctx.add_cookies(normalize_cookies(cookies))
            vpage = await vctx.new_page()
            try:
                await vpage.goto(url, wait_until="domcontentloaded", timeout=20000)
            except PWTimeout:
                print("     ✗ Timeout, skip.")
                await vctx.close()
                continue

            await vpage.wait_for_timeout(3000)
            await vpage.evaluate(ENGAGEMENT_JS)  # OneTrust + visible

            # Layer 6: Wistia/iframe — set autoplay param lalu klik tengah iframe
            play = await vpage.evaluate("""
                () => {
                    // tombol Play eksplisit dulu
                    const btn = [...document.querySelectorAll('button, [role=\"button\"]')]
                        .find(b => /^Play [Vv]ideo/.test((b.getAttribute('aria-label')||b.textContent||'').trim()));
                    if (btn) { btn.click(); }
                    // iframe: tambah autoPlay param
                    const f = document.querySelector('iframe[src*=\"wistia\"], iframe[src*=\"player\"], iframe[allow*=\"autoplay\"]');
                    if (f) {
                        try {
                            const u = new URL(f.src);
                            u.searchParams.set('autoPlay', 'true');
                            u.searchParams.set('muted', 'true');
                            f.src = u.toString();
                        } catch(e) {}
                        return 'iframe';
                    }
                    return btn ? 'button' : 'none';
                }
            """)
            # Klik tengah iframe (trigger play event yang propagate ke tracker)
            try:
                box = await vpage.evaluate("""
                    () => {
                        const f = document.querySelector('iframe[src*=\"wistia\"], iframe[src*=\"player\"], iframe[allow*=\"autoplay\"]');
                        if (!f) return null;
                        const r = f.getBoundingClientRect();
                        return { x: r.x + r.width/2, y: r.y + r.height/2 };
                    }
                """)
                if box:
                    await vpage.mouse.click(box['x'], box['y'])
            except Exception:
                pass
            print(f"     Play: {play}")

            # Dwell 90 detik, re-assert visible di tengah
            print("     ⏳ Nonton 90 detik...")
            await vpage.wait_for_timeout(45000)
            await vpage.evaluate(ENGAGEMENT_JS)
            await vpage.wait_for_timeout(45000)
            watched.append(video)
            print(f"     ✓ Ditonton ({len(watched)}/{max_count})")
        finally:
            await vctx.close()

    if not watched:
        print("   ✗ Tidak ada video yang berhasil ditonton.")
    return watched


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

    profile_dir = os.environ.get("CHROME_PROFILE", "/home/ubuntu/arc-chrome-profile")

    try:
        async with async_playwright() as p:
            launch_kwargs = dict(
                user_data_dir=profile_dir,
                headless=headless,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            )
            # Pakai real Google Chrome kalau terinstall, fallback ke Chromium
            try:
                context = await p.chromium.launch_persistent_context(channel="chrome", **launch_kwargs)
                print("🌐 Pakai real Google Chrome")
            except Exception:
                context = await p.chromium.launch_persistent_context(**launch_kwargs)
                print("🌐 Pakai Chromium (Chrome tidak tersedia)")

            browser = context.browser
            await context.add_init_script(VISIBILITY_INIT)

            if Path(cookies_path).exists():
                print("🍪 Inject cookies...")
                raw = load_cookies(cookies_path)
                await context.add_cookies(normalize_cookies(raw))

            page = context.pages[0] if context.pages else await context.new_page()

            print("🔐 Cek status login...")
            logged_in = await check_logged_in(page)

            if not logged_in:
                msg = "Cookie Arc expired/invalid. Perbarui cookies.json (export ulang dari browser)."
                print(f"❌ {msg}")
                if webhook_url:
                    send_discord(webhook_url, [], None, 0, error=msg)
                await context.close()
                sys.exit(1)

            print("✅ Login berhasil!")

            raw_cookies = load_cookies(cookies_path) if Path(cookies_path).exists() else []

            read_titles, video_titles = await get_history(page)
            candidates = await get_candidates(page)
            articles, videos = filter_candidates(candidates, read_titles, video_titles)

            print(f"\n📊 Kandidat tersedia: {len(articles)} artikel, {len(videos)} video")

            # Read Content: max 5/24jam · Watch a Video: max 4/24jam
            success_articles = await read_articles(page, articles, max_count=5)
            watched_videos = await watch_videos(context, raw_cookies, videos, max_count=4)

            # Poin resmi Arc: Read=2 (max5), Watch=4 (max4), Daily Active=1
            points = len(success_articles) * 2 + len(watched_videos) * 4 + 1

            # Tracker Gradual kadang delayed 2-3 menit → tunggu sebelum lapor
            print("\n⏳ Tunggu 150 detik biar tracking ter-commit...")
            await page.wait_for_timeout(150000)

            print("\n" + "="*50)
            print("✅ SELESAI!")
            print(f"📖 Berhasil baca {len(success_articles)} artikel:")
            for i, a in enumerate(success_articles, 1):
                print(f"   {i}. {a['title'][:70]}")
            print(f"🎬 Berhasil tonton {len(watched_videos)} video:")
            for i, v in enumerate(watched_videos, 1):
                print(f"   {i}. {v['title'][:70]}")
            print(f"💰 Estimasi poin: {points} (read {len(success_articles)}×2 + video {len(watched_videos)}×4 + daily 1)")
            print(f"⏰ Waktu: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
            print("="*50)

            if webhook_url:
                first_video = watched_videos[0] if watched_videos else None
                send_discord(webhook_url, success_articles, first_video, points)

            await context.close()

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
