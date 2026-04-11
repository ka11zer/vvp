import re
import requests
import base64
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

API_URL = "https://api.ppv.to/api/streams"

API_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://ppv.to/",
    "Origin": "https://ppv.to"
}

EMBED_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://pooembed.eu/",
    "Origin": "https://pooembed.eu"
}

OUTPUT_FILE = "ppv.m3u"
MAX_WORKERS = 6


# ---------------------------
# BASE64
# ---------------------------
def decode_b64(s):
    try:
        s = s.replace('-', '+').replace('_', '/')
        while len(s) % 4:
            s += '='
        return base64.b64decode(s).decode()
    except:
        return ""


# ---------------------------
# UNPACK JS (doms9-style)
# ---------------------------
def unpack_js(packed):
    try:
        payload, symtab, radix, count = re.search(
            r"}\('(.*)',(\d+),(\d+),'(.*)'\.split\('\|'\)",
            packed, re.DOTALL
        ).groups()

        radix = int(radix)
        symtab = symtab.split('|')

        def lookup(match):
            word = match.group(0)
            try:
                return symtab[int(word, radix)]
            except:
                return word

        return re.sub(r'\b\w+\b', lookup, payload)

    except:
        return packed


# ---------------------------
# VALIDATE STREAM
# ---------------------------
def validate_stream(url):
    try:
        r = requests.get(url, headers=EMBED_HEADERS, timeout=5)
        return r.status_code == 200
    except:
        return False


# ---------------------------
# HEAVY EXTRACTOR
# ---------------------------
def extract_m3u8(embed_url):
    try:
        r = requests.get(embed_url, headers=EMBED_HEADERS, timeout=10)
        html = r.text

        # 1. direct
        m = re.findall(r'https?://[^"\']+\.m3u8[^"\']*', html)
        if m:
            return m[0]

        # 2. packed JS
        packed_list = re.findall(r'eval\(function\(p,a,c,k,e,d\).*?\)\)', html, re.DOTALL)
        for packed in packed_list:
            unpacked = unpack_js(packed)
            m = re.findall(r'https?://[^"\']+\.m3u8[^"\']*', unpacked)
            if m:
                return m[0]

        # 3. base64
        b64_list = re.findall(r'atob\("([^"]+)"\)', html)
        for b64 in b64_list:
            decoded = decode_b64(b64)
            if ".m3u8" in decoded:
                m = re.search(r'https?://[^"\']+\.m3u8[^"\']*', decoded)
                if m:
                    return m.group(0)

        # 4. jwplayer
        jw = re.search(r'file\s*:\s*"([^"]+\.m3u8[^"]*)"', html)
        if jw:
            return jw.group(1)

    except:
        pass

    return None


# ---------------------------
# GET EVENTS FROM API
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
# PROCESS EVENT
# ---------------------------
def process_event(ev):
    for _ in range(2):  # retry
        url = extract_m3u8(ev["embed"])

        if not url:
            continue

        if validate_stream(url):
            return {
                "name": ev["name"],
                "group": ev["category"],
                "url": url
            }

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
