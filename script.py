import requests
import re
import time

API_URL = "https://ppv.cx/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://pooembed.eu/"
}

OUTPUT_FILE = "ppv.m3u"


# ---------------------------
# GET EVENTS FROM API
# ---------------------------
def get_events():
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=10)
        data = r.json()

        events = []

        for item in data:
            title = item.get("title") or item.get("name")
            embed = item.get("embed") or item.get("url")

            if embed:
                events.append({
                    "name": title,
                    "embed": embed
                })

        print(f"Found {len(events)} events")
        return events

    except Exception as e:
        print("API error:", e)
        return []


# ---------------------------
# EXTRACT M3U8 FROM EMBED
# ---------------------------
def extract_m3u8(embed_url):
    try:
        r = requests.get(embed_url, headers=HEADERS, timeout=10)
        html = r.text

        # Primary: direct m3u8
        match = re.findall(r'https?://[^"\']+\.m3u8[^"\']*', html)

        if match:
            # prefer index.m3u8
            for m in match:
                if "index.m3u8" in m:
                    return m
            return match[0]

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
                "url": m3u8
            })
            print("   ✓ Found stream")
        else:
            print("   ✗ No stream")

        time.sleep(0.5)  # small delay (important)

    # ---------------------------
    # WRITE M3U
    # ---------------------------
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")

        for r in results:
            f.write(f'#EXTINF:-1 group-title="PPV",{r["name"]}\n')

            # critical headers
            f.write("#EXTVLCOPT:http-referrer=https://pooembed.eu/\n")
            f.write("#EXTVLCOPT:http-origin=https://pooembed.eu\n")

            f.write(r["url"] + "\n")

    print(f"\nDONE: {len(results)} working streams saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
