import requests
import urllib.parse
from playwright.sync_api import sync_playwright

API_URL = "https://api.ppv.to/api/streams"

API_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://ppv.to/",
    "Origin": "https://ppv.to"
}

# 🔥 IMPORTANT: REMOVE if using GitHub
PROXY = ""  # or your proxy if running locally

OUTPUT_FILE = "ppv.m3u"


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
# STEALTH
# ---------------------------
def stealth(page):
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)


# ---------------------------
# EXTRACT
# ---------------------------
def extract(page, url):
    stream_url = None

    def handle_response(response):
        nonlocal stream_url
        if ".m3u8" in response.url:
            stream_url = response.url

    page.on("response", handle_response)

    try:
        page.goto(url, timeout=20000)

        try:
            page.click("body")
        except:
            pass

        page.wait_for_timeout(8000)

        return stream_url

    except:
        return None


# ---------------------------
# MAIN
# ---------------------------
def main():
    events = get_events()

    if not events:
        return

    results = []
    failed = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )

        context = browser.new_context()

        page = context.new_page()
        stealth(page)

        for i, ev in enumerate(events, 1):
            url = extract(page, ev["embed"])

            if not url:
                failed += 1
                print(f"[{i}] ✗ {ev['name']}")
                continue

            # proxy wrap (optional)
            if PROXY:
                url = PROXY + urllib.parse.quote(url, safe='')

            results.append({
                "name": ev["name"],
                "group": ev["category"],
                "url": url
            })

            print(f"[{i}] ✓ {ev['name']}")

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
