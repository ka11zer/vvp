import requests
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright

API_URL = "https://api.ppv.to/api/streams"

API_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://ppv.to/",
    "Origin": "https://ppv.to"
}

# 🔥 YOUR PROXY (change if needed)
PROXY = "http://192.168.1.101:8090/stream?url="

OUTPUT_FILE = "ppv.m3u"
MAX_WORKERS = 5


# ---------------------------
# GET EVENTS
# ---------------------------
def get_events():
    try:
        r = requests.get(API_URL, headers=API_HEADERS, timeout=10)
        data = r.json()

        events = []

        for cat in data.get("streams", []):
            category = cat.get("category", "PPV")

            for s in cat.get("streams", []):
                iframe = s.get("iframe")
                name = s.get("name")

                if iframe:
                    events.append({
                        "name": name,
                        "embed": iframe,
                        "category": category
                    })

        print(f"Found {len(events)} events")
        return events

    except Exception as e:
        print("API error:", e)
        return []


# ---------------------------
# STEALTH PATCH
# ---------------------------
def stealth_page(page):
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)


# ---------------------------
# EXTRACT (FAST + STEALTH)
# ---------------------------
def process_event(context, ev):
    page = context.new_page()
    stealth_page(page)

    stream_url = None

    def handle_response(response):
        nonlocal stream_url
        if ".m3u8" in response.url:
            stream_url = response.url

    page.on("response", handle_response)

    try:
        page.goto(ev["embed"], timeout=20000)

        # simulate user interaction
        try:
            page.click("body")
        except:
            pass

        page.wait_for_timeout(8000)

        page.close()

        if not stream_url:
            return None

        # 🔥 proxy wrap
        encoded = urllib.parse.quote(stream_url, safe='')
        proxied = PROXY + encoded

        return {
            "name": ev["name"],
            "group": ev["category"],
            "url": proxied
        }

    except:
        page.close()
        return None


# ---------------------------
# MAIN
# ---------------------------
def main():
    events = get_events()

    if not events:
        print("No events found")
        return

    results = []
    failed = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled"
            ]
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            viewport={"width": 1280, "height": 720}
        )

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(process_event, context, ev): ev
                for ev in events
            }

            for i, future in enumerate(as_completed(futures), 1):
                ev = futures[future]

                try:
                    res = future.result()

                    if res:
                        results.append(res)
                        print(f"[{i}] ✓ {res['name']}")
                    else:
                        failed += 1
                        print(f"[{i}] ✗ {ev['name']}")

                except:
                    failed += 1

        browser.close()

    # ---------------------------
    # WRITE M3U
    # ---------------------------
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")

        for r in results:
            f.write(f'#EXTINF:-1 group-title="{r["group"]}",{r["name"]}\n')
            f.write("#EXTVLCOPT:http-referrer=https://pooembed.eu/\n")
            f.write("#EXTVLCOPT:http-origin=https://pooembed.eu\n")
            f.write(r["url"] + "\n")

    print("\n" + "="*40)
    print(f"DONE: {len(results)} working / {failed} failed / {len(events)} total")


if __name__ == "__main__":
    main()
