import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright

API_URL = "https://api.ppv.to/api/streams"

API_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://ppv.to/",
    "Origin": "https://ppv.to"
}

OUTPUT_FILE = "ppv.m3u"
MAX_WORKERS = 4  # keep low for GitHub


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
# EXTRACT USING PLAYWRIGHT
# ---------------------------
def extract_with_browser(embed_url):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            stream_url = None

            def handle_request(request):
                nonlocal stream_url
                url = request.url
                if ".m3u8" in url:
                    stream_url = url

            page.on("request", handle_request)

            page.goto(embed_url, timeout=15000)
            page.wait_for_timeout(5000)

            browser.close()

            return stream_url

    except:
        return None


# ---------------------------
# VALIDATE STREAM
# ---------------------------
def validate_stream(url):
    try:
        r = requests.get(url, timeout=5)
        return r.status_code == 200
    except:
        return False


# ---------------------------
# PROCESS EVENT
# ---------------------------
def process_event(ev):
    url = extract_with_browser(ev["embed"])

    if not url:
        return None

    if not validate_stream(url):
        return None

    return {
        "name": ev["name"],
        "group": ev["category"],
        "url": url
    }


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

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_event, ev): ev for ev in events}

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
