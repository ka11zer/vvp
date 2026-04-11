import requests
import re
import time

API_URL = "https://api.ppv.to/api/streams"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://ppv.to/",
    "Origin": "https://ppv.to"
}

OUTPUT_FILE = "ppv.m3u"


# ---------------------------
# GET EVENTS
# ---------------------------
def get_events():
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=10)

        if r.status_code != 200:
            print("Bad status:", r.status_code)
            print(r.text[:200])
            return []

        data = r.json()

        streams = data.get("streams", [])
        events = []

        for category in streams:
            cat_name = category.get("category_name", "PPV")

            for item in category.get("streams", []):
                name = item.get("name")
                iframe = item.get("iframe")

                if iframe:
                    events.append({
                        "name": name,
                        "embed": iframe,
                        "category": cat_name
                    })

        print(f"Found {len(events)} events")
        return events

    except Exception as e:
        print("API error:", e)
        return []


# ---------------------------
# EXTRACT M3U8
# ---------------------------
def extract_m3u8(embed_url):
    try:
        r = requests.get(embed_url, headers=HEADERS, timeout=10)
        html = r.text

        matches = re.findall(r'https?://[^"\']+\.m3u8[^"\']*', html)

        if matches:
            for m in matches:
                if "index.m3u8" in m:
                    return m
            return matches[0]

    except Exception:
        pass

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

    for i, ev in enumerate(events, 1):
        print(f"[{i}/{len(events)}] {ev['name']}")

        m3u8 = extract_m3u8(ev["embed"])

        if m3u8:
            results.append({
                "name": ev["name"],
                "url": m3u8,
                "group": ev["category"]
            })
            print("   ✓ stream found")
        else:
            print("   ✗ failed")

        time.sleep(0.5)

    # ---------------------------
    # WRITE M3U
    # ---------------------------
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")

        for r in results:
            f.write(f'#EXTINF:-1 group-title="{r["group"]}",{r["name"]}\n')

            # IMPORTANT headers
            f.write("#EXTVLCOPT:http-referrer=https://pooembed.eu/\n")
            f.write("#EXTVLCOPT:http-origin=https://pooembed.eu\n")

            f.write(r["url"] + "\n")

    print(f"\nDONE: {len(results)} streams saved")


if __name__ == "__main__":
    main()
