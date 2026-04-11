import requests
import re
import base64
import urllib.parse
from playwright.sync_api import sync_playwright

API_URL = "https://api.ppv.to/api/streams"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://ppv.to/",
    "Origin": "https://ppv.to"
}

OUTPUT_FILE = "ppv.m3u"


# ---------------------------
# API
# ---------------------------
def get_events():
    r = requests.get(API_URL, headers=HEADERS, timeout=10)
    data = r.json()

    events = []

    for cat in data.get("streams", []):
        for s in cat.get("streams", []):
            if s.get("iframe"):
                events.append({
                    "name": s.get("name"),
                    "embed": s.get("iframe"),
                    "group": cat.get("category")
                })

    return events


# ---------------------------
# LIGHTWEIGHT EXTRACTOR
# ---------------------------
def extract_fast(url):
    try:
        r = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://pooembed.eu/"
        }, timeout=10)

        html = r.text

        # direct m3u8
        m = re.findall(r'https?://[^"\']+\.m3u8[^"\']*', html)
        if m:
            return m[0]

        # base64
        b64 = re.findall(r'atob\("([^"]+)"\)', html)
        for b in b64:
            try:
                decoded = base64.b64decode(b).decode()
                if ".m3u8" in decoded:
                    m = re.search(r'https?://[^"\']+\.m3u8[^"\']*', decoded)
                    if m:
                        return m.group(0)
            except:
                pass

    except:
        pass

    return None


# ---------------------------
# PLAYWRIGHT FALLBACK
# ---------------------------
def extract_browser(page, url):
    stream = None

    def handler(response):
        nonlocal stream
        if ".m3u8" in response.url:
            stream = response.url

    page.on("response", handler)

    try:
        page.goto(url, timeout=20000)

        try:
            page.click("body")
        except:
            pass

        page.wait_for_timeout(8000)

        return stream

    except:
        return None


# ---------------------------
# MAIN
# ---------------------------
def main():
    events = get_events()
    print(f"Found {len(events)} events")

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )

        context = browser.new_context()
        page = context.new_page()

        for i, ev in enumerate(events, 1):
            print(f"[{i}] {ev['name']}")

            # 🔥 try fast first
            stream = extract_fast(ev["embed"])

            # fallback to browser
            if not stream:
                stream = extract_browser(page, ev["embed"])

            if not stream:
                print("   ✗ failed")
                continue

            results.append({
                "name": ev["name"],
                "group": ev["group"],
                "url": stream
            })

            print("   ✓ success")

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

    print(f"\nDONE: {len(results)} working")


if __name__ == "__main__":
    main()
