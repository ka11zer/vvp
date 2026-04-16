import asyncio
import requests
from playwright.async_api import async_playwright

API_URL = "https://api.ppv.to/api/streams"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


# ── Step 1: Fetch API ─────────────────────────────

def get_streams():
    r = requests.get(API_URL, headers=HEADERS)
    data = r.json()

    streams = []

    for category in data.get("streams", []):
        for s in category.get("streams", []):
            streams.append({
                "name": s["name"],
                "iframe": s["iframe"]
            })

    print(f"Found {len(streams)} streams")
    return streams


# ── Step 2: Extract m3u8 using Playwright ────────

async def extract_stream(browser, stream):
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        extra_http_headers={
            "Referer": stream["iframe"],
            "Origin": "https://pooembed.eu"
        }
    )

    page = await context.new_page()

    try:
        await page.goto(stream["iframe"], timeout=30000)

        # try clicking player (some streams need interaction)
        try:
            await page.mouse.click(640, 360)
        except:
            pass

        try:
            btn = page.locator("button").first
            await btn.click(timeout=3000)
        except:
            pass

        # wait for player object
        try:
            await page.wait_for_function(
                "() => window.clapprPlayer || window.player",
                timeout=10000
            )
        except:
            pass

        # small delay to allow stream to initialize
        await page.wait_for_timeout(3000)

        m3u8 = None

        # multiple extraction methods
        for expr in [
            "() => window.clapprPlayer?.options?.source",
            "() => window.player?.options?.source",
            "() => document.querySelector('video')?.src",
            "() => document.querySelector('source')?.src"
        ]:
            try:
                val = await page.evaluate(expr)
                if val and ".m3u8" in val:
                    m3u8 = val
                    break
            except:
                pass

        if m3u8:
            print(f"[OK] {stream['name']}")
            return {
                "name": stream["name"],
                "url": m3u8
            }
        else:
            print(f"[FAIL] {stream['name']}")
            return None

    except Exception as e:
        print(f"[ERR] {stream['name']} -> {e}")
        return None

    finally:
        await page.close()
        await context.close()


# ── Step 3: Build M3U ────────────────────────────

def build_m3u(results):
    m3u = "#EXTM3U\n"

    for r in results:
        if not r:
            continue

        m3u += f"#EXTINF:-1,{r['name']}\n"
        m3u += f"{r['url']}\n"

    with open("playlist.m3u", "w") as f:
        f.write(m3u)

    print("\nSaved playlist.m3u")


# ── MAIN ─────────────────────────────────────────

async def main():
    streams = get_streams()

    sem = asyncio.Semaphore(3)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--autoplay-policy=no-user-gesture-required"
            ]
        )

        async def limited(s):
            async with sem:
                return await extract_stream(browser, s)

        tasks = [limited(s) for s in streams]
        results = await asyncio.gather(*tasks)

        await browser.close()

    build_m3u(results)


if __name__ == "__main__":
    asyncio.run(main())
