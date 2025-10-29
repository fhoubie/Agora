import json
import os
import time
from urllib.parse import quote
from tqdm import tqdm
import requests
from playwright.sync_api import sync_playwright
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# -----------------------------
# Configuration
# -----------------------------
COOKIE_FILE = "cookies_ogc.json"
BASE_DOWNLOAD_DIR = "downloads"
MAX_RETRIES = 3
HARDCODED_UPLOADER_URL = "https://agora.ogc.org/202610-uploader"  # Initialize portal session, probably typo in URL, so hardcoded


# -----------------------------
# 1️⃣ Authentication with Playwright
# -----------------------------
def get_authenticated_session(agora_url="https://agora.ogc.org",
                              uploader_url=HARDCODED_UPLOADER_URL,
                              portal_url="https://portal.ogc.org",
                              wait_time=40,
                              headless=False):
    """
    Authenticate via Playwright, initialize portal session, and persist cookies.
    """
    session = requests.Session()

    if os.path.exists(COOKIE_FILE):
        print("🍪 Loading cookies from disk...")
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        for c in cookies:
            if "ogc.org" in c["domain"]:
                session.cookies.set(c["name"], c["value"], domain=c["domain"])
        test_resp = session.get(portal_url)
        if test_resp.status_code == 200 and "login" not in test_resp.text.lower():
            print("✅ Cookies valid, skipping login.")
            return session
        else:
            print("⚠️ Cookies expired, manual login required.")

    # Manual login via Playwright
    print("🌐 Launching Playwright for AGORA authentication...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        page.goto(agora_url)
        print(f"➡️ Please login manually at {agora_url}")
        print(f"⏳ Waiting {wait_time} seconds for login...")
        time.sleep(wait_time)

        # Initialize portal session
        print(f"🌐 Visiting uploader page {uploader_url} to initialize portal session...")
        page.goto(uploader_url)
        time.sleep(5)

        page.goto(portal_url)
        time.sleep(5)

        cookies = page.context.cookies()
        browser.close()

    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2)
    print(f"💾 Cookies saved to {COOKIE_FILE}")

    for c in cookies:
        if "ogc.org" in c["domain"]:
            session.cookies.set(c["name"], c["value"], domain=c["domain"])

    return session


# -----------------------------
# 2️⃣ Fetch JSON file list
# -----------------------------
def fetch_file_list(session, month_code):
    json_url = f"https://portal.ogc.org/upload/{month_code}/list_files.php"
    print(f"📥 Fetching JSON from {json_url}")
    resp = session.get(json_url)
    if resp.status_code != 200:
        raise Exception(f"❌ Failed to fetch JSON ({resp.status_code})")
    try:
        data = resp.json()
    except json.JSONDecodeError:
        raise Exception("❌ Response is not valid JSON — check authentication")
    print(f"✅ JSON retrieved: {len(data.get('files', []))} files found")
    return data


# -----------------------------
# 3️⃣ Download a single file with per-file progress bar
# -----------------------------
def download_file(session, file_entry, month_code):
    meta = file_entry.get("meta", {})
    original_name = meta.get("original_name")
    group_name = meta.get("group", "Others")
    server_size = file_entry.get("size", None)

    if not original_name:
        return f"⚠️ File without 'original_name' skipped."

    safe_group = "".join(c if c.isalnum() or c in (" ", "_", "-", ".") else "_" for c in group_name).strip().replace(" ", "_")
    group_dir = os.path.join(BASE_DOWNLOAD_DIR, safe_group)
    os.makedirs(group_dir, exist_ok=True)
    dest_path = os.path.join(group_dir, original_name)

    if os.path.exists(dest_path) and server_size is not None:
        local_size = os.path.getsize(dest_path)
        if local_size == server_size:
            return f"⏭️ Skipping {original_name}, already downloaded ({local_size} bytes)"

    download_url = f"https://portal.ogc.org/upload/{month_code}/getfile.php?id=" + quote(original_name)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(download_url, stream=True)
            if resp.status_code == 200:
                total = int(resp.headers.get("Content-Length", 0))
                with open(dest_path, "wb") as f, tqdm(
                    total=total, unit="B", unit_scale=True,
                    desc=original_name, leave=False
                ) as pbar:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
                return f"✅ {original_name} → {safe_group}"
            else:
                msg = f"❌ Error {resp.status_code} downloading {original_name}"
        except Exception as e:
            msg = f"❌ Exception on attempt {attempt}: {e}"

        if attempt < MAX_RETRIES:
            time.sleep(2)
        else:
            return f"⚠️ Failed to download {original_name} after {MAX_RETRIES} attempts"


# -----------------------------
# 4️⃣ Parallel download with per-file bars
# -----------------------------
def download_files_parallel(session, data, month_code, max_workers=5):
    os.makedirs(BASE_DOWNLOAD_DIR, exist_ok=True)
    files = data.get("files", [])
    print(f"📦 Starting parallel download of {len(files)} files with {max_workers} workers...\n")

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(download_file, session, f, month_code): f for f in files}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Files overall"):
            results.append(future.result())

    for r in results:
        print(r)


# -----------------------------
# 5️⃣ CLI
# -----------------------------
def main():
    parser = argparse.ArgumentParser(description="OGC AGORA/PORTAL downloader with per-file progress bars")
    parser.add_argument("--month", type=str, required=True, help="Month code to download (e.g., 202510)")
    parser.add_argument("--headless", action="store_true", help="Run Playwright in headless mode")
    parser.add_argument("--wait", type=int, default=40, help="Seconds to wait for manual login")
    parser.add_argument("--workers", type=int, default=5, help="Number of parallel downloads")
    args = parser.parse_args()

    session = get_authenticated_session(wait_time=args.wait, headless=args.headless)
    data = fetch_file_list(session, args.month)
    download_files_parallel(session, data, args.month, max_workers=args.workers)


if __name__ == "__main__":
    main()
