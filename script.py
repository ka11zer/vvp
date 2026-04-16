import asyncio
import re
import time
import requests
from playwright.async_api import async_playwright

API_MIRRORS = [
    "https://api.ppv.to/api/streams",
    "https://api.ppv.cx/api/streams",
]


# ── Fix stream URL ───────────────────────────────

def fix_url(url: str) -> str:
    return re.sub(r"index\.m3u8$", "tracks-v1a1/mono.ts.m3u8", url, flags=re.I)


# ── Fetch API with retry + fallback ─────────────

def get_streams():
    for attempt in range(3):
        for url in API_MIRRORS:
            try:
                print(f"[API] Trying: {url} (attempt {attempt+1})")

                r = requests.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Accept": "application/json"
                    },
                    timeout=10
                )

                if r.status_code != 200:
                    print(f"[API] Failed {url}: {r.status_code}")
                    continue

                data = r.json()

                streams = []

                for category in data.get("streams", []):
                    for s in category.get("streams", []):
                        if not s.get("iframe"):
                            continue

                        streams.append({
                            "name": s["name"],
                            "iframe": s["iframe"],
                            "logo": s.get("poster", "")
                        })

                print(f"[API] Loaded {len(streams)} streams from {url}")
                return streams

            except Exception as e:
                print(f"[API] Error with {url}: {e}")
                time.sleep(2)

    print("[API] All mirrors failed")
    return []


# ── Extract m3u8 via Playwright ─────────────────

async def extract_stream(browser, stream):
    context = await browser.new_context(
        user_agent="Mozilla/5.0",
        extra_http_headers={
            "Referer": stream["iframe"],
            "Origin": "https://pooembed.eu"
        }
    )

    page = await context.new_page()

    try:
        await page.goto(stream["iframe"], timeout=30000)

        # trigger player
        try:
            await page.mouse.click(640, 360)
        except:
            pass

        try:
            btn = page.locator("button").first
            await btn.click(timeout=3000)
        except:
            pass

        # wait for player
        try:
            await page.wait_for_function(
                "() => window.clapprPlayer || window.player",
                timeout=10000
            )
        except:
            pass

        await page.wait_for_timeout(3000)

        m3u8 = None

        for expr in [
            "() => window.clapprPlayer?.options?.source",
            "() => window.player?.options?.source",
            "() => document.querySelector('video')?.src",
        ]:
            try:
                val = await page.evaluate(expr)
                if val and ".m3u8" in val:
                    m3u8 = val
                    break
            except:
                pass

        if m3u8:
            fixed = fix_url(m3u8)
            print(f"[OK] {stream['name']}")
            return {
                "name": stream["name"],
                "url": fixed,
                "logo": stream["logo"],
                "referer": stream["iframe"]
            }

        print(f"[FAIL] {stream['name']}")
        return None

    except Exception as e:
        print(f"[ERR] {stream['name']} -> {e}")
        return None

    finally:
        await page.close()
        await context.close()


# ── Build M3U ───────────────────────────────────

def build_m3u(results):
    m3u = "#EXTM3U\n"

    for r in results:
        if not r:
            continue

        m3u += (
            f'#EXTINF:-1 tvg-logo="{r["logo"]}" group-title="PPV",{r["name"]}\n'
        )

        m3u += f'#EXTVLCOPT:http-referrer={r["referer"]}\n'
        m3u += f'#EXTVLCOPT:http-origin={r["referer"]}\n'
        m3u += f'#EXTVLCOPT:http-user-agent=Mozilla/5.0\n'

        m3u += f"{r['url']}\n"

    with open("ppv.m3u", "w", encoding="utf-8") as f:
        f.write(m3u)

    print("\nSaved ppv.m3u")


# ── MAIN ────────────────────────────────────────

async def main():
    streams = get_streams()

    if not streams:
        print("No streams found. Exiting.")
        return

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
