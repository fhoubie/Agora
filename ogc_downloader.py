#!/usr/bin/env python3
"""
ogc_downloader.py

Robust downloader for OGC AGORA / portal.ogc.org.

Behavior:
- Try to use saved cookies first.
- If fetching the JSON returns 403 or invalid JSON, open Playwright for manual login:
    * Visit agora
    * Visit hardcoded uploader page (to initialize portal session)
    * Visit the portal JSON URL (to ensure portal cookies exist)
- Save cookies for both domains and the browser User-Agent
- Retry fetching JSON and proceed to parallel downloads
"""

import json
import os
import time
import argparse
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import requests
from playwright.sync_api import sync_playwright

# -----------------------------
# Configuration
# -----------------------------
COOKIE_FILE = "cookies_ogc.json"
BASE_DOWNLOAD_DIR = "downloads"
MAX_RETRIES = 3
HARDCODED_UPLOADER_URL = "https://agora.ogc.org/202510-uploader"  # per your instruction (hardcoded)
PORTAL_ROOT = "https://portal.ogc.org"


# -----------------------------
# Utilities: save/load cookies + UA
# -----------------------------
def save_cookies_and_ua(cookies, user_agent):
    """
    Save Playwright cookies and user-agent to disk.
    cookies: list of cookie dicts as returned by Playwright page.context.cookies()
    user_agent: string
    """
    payload = {"cookies": cookies, "user_agent": user_agent}
    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"💾 Cookies and UA saved to {COOKIE_FILE}")


def load_cookies_and_ua():
    """
    Load cookies and user-agent from disk. Returns (cookies_list, user_agent) or (None, None).
    """
    if not os.path.exists(COOKIE_FILE):
        return None, None
    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload.get("cookies", []), payload.get("user_agent")
    except Exception as e:
        print(f"⚠️ Failed to load cookies file: {e}")
        return None, None


def inject_cookies_into_session(session: requests.Session, cookies):
    """
    Inject Playwright cookies into requests.Session.
    We attempt to set cookie domain as given; requests will send them accordingly.
    """
    for c in cookies:
        # Only keep cookies that have a name/value and domain
        name = c.get("name")
        value = c.get("value")
        domain = c.get("domain")
        path = c.get("path", "/")
        if not (name and value and domain):
            continue
        # requests' cookies API: session.cookies.set(name, value, domain=domain, path=path)
        try:
            session.cookies.set(name, value, domain=domain, path=path)
        except Exception:
            # fallback: set without domain
            session.cookies.set(name, value, path=path)


# -----------------------------
# Authentication & cookie refresh logic
# -----------------------------
def try_use_saved_cookies_and_fetch_json(month_code, session, json_url):
    """
    Attempt to use saved cookies (already injected into session) and fetch JSON.
    Returns (data_dict) on success or raises exception on failure.
    """
    print(f"📥 Attempting to fetch JSON from {json_url} using stored cookies...")
    resp = session.get(json_url, allow_redirects=True)
    # 403 or other non-200 likely means cookies invalid / session not initialized
    if resp.status_code == 403:
        raise Exception("403")
    if resp.status_code != 200:
        raise Exception(f"HTTP {resp.status_code}")
    try:
        data = resp.json()
    except Exception:
        raise Exception("InvalidJSON")
    return data


def perform_playwright_login_and_save(month_code, agora_url, portal_json_url, headless=False, wait_time=40):
    """
    Launch Playwright for manual login, visit the uploader hardcoded URL and the portal JSON URL
    so that cookies for both agora and portal domains are created. Save cookies + UA.
    Returns the cookies list and user-agent string.
    """
    print("🌐 Launching Playwright for manual login and cookie sync...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        # 1) go to agora and allow user to log in manually
        page.goto(agora_url)
        print(f"➡️ Please log in manually to {agora_url} (you have {wait_time} seconds)...")
        # Wait for the user to finish login. We do a simple time.wait here; alternative is to wait for URL change or selector.
        time.sleep(wait_time)

        # 2) visit the hardcoded uploader URL to initialize the portal session (per your request)
        try:
            print(f"🌐 Visiting hardcoded uploader URL: {HARDCODED_UPLOADER_URL}")
            page.goto(HARDCODED_UPLOADER_URL)
            time.sleep(3)
        except Exception as e:
            print(f"⚠️ Visiting uploader page raised: {e}")

        # 3) visit the portal JSON URL (so portal cookies are created/updated)
        try:
            print(f"🌐 Visiting portal JSON URL to ensure portal cookies: {portal_json_url}")
            page.goto(portal_json_url)
            # small pause to let any JS or redirects happen
            time.sleep(3)
        except Exception as e:
            print(f"⚠️ Visiting portal JSON URL raised: {e}")

        # collect cookies and user-agent
        cookies = context.cookies()
        user_agent = page.evaluate("() => navigator.userAgent")
        browser.close()

    # Save cookies + UA
    save_cookies_and_ua(cookies, user_agent)
    return cookies, user_agent


# -----------------------------
# Fetch file list (with auto-refresh if needed)
# -----------------------------
def fetch_file_list_with_auto_refresh(session, month_code, agora_url, headless, wait_time):
    """
    Try saved cookies first. If they fail, open Playwright for manual login and retry.
    Returns the parsed JSON data.
    """
    json_url = f"{PORTAL_ROOT}/upload/{month_code}/list_files.php"

    # try to load cookies+ua from disk and inject them into session
    cookies, ua = load_cookies_and_ua()
    if cookies:
        inject_cookies_into_session(session, cookies)
    # set user-agent header if available (helps some backends)
    if ua:
        session.headers.update({"User-Agent": ua})

    # Try to fetch JSON using stored cookies
    try:
        data = try_use_saved_cookies_and_fetch_json(month_code, session, json_url)
        print("✅ Successfully fetched JSON using stored cookies.")
        return data
    except Exception as e:
        print(f"⚠️ Stored cookies did not work ({e}). Will open browser to re-authenticate...")

    # Run Playwright to re-authenticate and save cookies
    cookies, ua = perform_playwright_login_and_save(month_code, agora_url, json_url, headless=headless, wait_time=wait_time)

    # Inject refreshed cookies and UA into session
    inject_cookies_into_session(session, cookies)
    if ua:
        session.headers.update({"User-Agent": ua})

    # Retry fetching JSON
    try:
        data = try_use_saved_cookies_and_fetch_json(month_code, session, json_url)
        print("✅ Successfully fetched JSON after manual login.")
        return data
    except Exception as e:
        raise Exception(f"Failed to fetch JSON even after login: {e}")


# -----------------------------
# Downloading utilities
# -----------------------------
def clean_group_name(group_name):
    safe_group = "".join(c if c.isalnum() or c in (" ", "_", "-", ".") else "_" for c in group_name)
    return safe_group.strip().replace(" ", "_") or "Others"


def download_single_file(session, file_entry, month_code):
    """
    Download a single file. Returns a short status string.
    This function is safe to run in parallel threads.
    """
    meta = file_entry.get("meta", {})
    original_name = meta.get("original_name")
    group_name = meta.get("group", "Others")
    server_size = file_entry.get("size", None)

    if not original_name:
        return "⚠️ File without original_name skipped."

    safe_group = clean_group_name(group_name)
    group_dir = os.path.join(BASE_DOWNLOAD_DIR, safe_group)
    os.makedirs(group_dir, exist_ok=True)
    dest_path = os.path.join(group_dir, original_name)

    # skip if present and size matches
    # Skip if present and size matches; otherwise redownload
    if os.path.exists(dest_path) and server_size is not None:
        local_size = os.path.getsize(dest_path)
        if local_size >= server_size:
            return f"⏭️ Skipped {original_name} (local size {local_size} >= server-reported size {server_size})"
        else:
            print(f"⚠️ Local file {original_name} smaller than server-reported size ({local_size} < {server_size}), re-downloading...")

    download_url = f"{PORTAL_ROOT}/upload/{month_code}/getfile.php?id=" + quote(original_name)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(download_url, stream=True, timeout=60)
            if resp.status_code == 200:
                # per-file progress bar (Content-Length may be missing)
                total = int(resp.headers.get("Content-Length", 0))
                # open file and stream write with progress
                with open(dest_path, "wb") as f, tqdm(
                    total=total, unit="B", unit_scale=True, leave=False,
                    desc=original_name[:40]
                ) as pbar:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
                # after successful download, optionally verify size
                if server_size is not None:
                    local_size = os.path.getsize(dest_path)
                    if local_size != server_size:
                        return f"⚠️ Downloaded {original_name} but size mismatch (local {local_size} vs server {server_size})"
                return f"✅ {original_name} -> {safe_group}"
            else:
                msg = f"❌ HTTP {resp.status_code}"
        except Exception as e:
            msg = f"❌ Exception: {e}"

        if attempt < MAX_RETRIES:
            time.sleep(2)
            # small backoff
        else:
            return f"⚠️ Failed {original_name} after {MAX_RETRIES} attempts: {msg}"


def download_files_in_parallel(session, data, month_code, max_workers=5):
    """
    Download files in parallel, with a global progress bar and per-file bars (per-file bars are set leave=False).
    """
    files = data.get("files", [])
    if not files:
        print("ℹ️ No files to download.")
        return

    print(f"📦 Starting downloads: {len(files)} files with {max_workers} workers...\n")
    os.makedirs(BASE_DOWNLOAD_DIR, exist_ok=True)

    results = []
    downloaded_files = []
    skipped_files = []
    failed_files = []
    total_bytes = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(download_single_file, session, f, month_code): f for f in files}
        # overall progress using as_completed
        for future in tqdm(as_completed(futures), total=len(futures), desc="Overall files"):
            try:
                res = future.result()
            except Exception as e:
                res = f"⚠️ Worker exception: {e}"
            results.append(res)

            # classify results
            if res.startswith("✅"):
                downloaded_files.append(res)
                # try to extract file size for total
                import re
                m = re.search(r"\((\d+)\s*bytes?\)", res)
                if m:
                    total_bytes += int(m.group(1))
            elif res.startswith("⏭️"):
                skipped_files.append(res)
            elif res.startswith(("⚠️", "❌")):
                failed_files.append(res)

        # print detailed summary
    print("\n=== 🧾 Download Summary ===")
    print(f"✅ Downloaded: {len(downloaded_files)} files")
    print(f"⏭️ Skipped:    {len(skipped_files)} files")
    print(f"⚠️ Failed:     {len(failed_files)} files")
    print(f"📦 Total size downloaded: {total_bytes / 1_000_000:.2f} MB")

    if failed_files:
        print("\n⚠️ Failed files:")
        for f in failed_files:
            print(" -", f)

    if downloaded_files:
        print("\n✅ Downloaded files:")
        for f in downloaded_files:
            print(" -", f)

    print("\n✅ All downloads complete.\n")




# -----------------------------
# CLI and main flow
# -----------------------------
def main():
    parser = argparse.ArgumentParser(description="OGC AGORA / portal.ogc.org downloader (auto refresh cookies if needed)")
    parser.add_argument("--month", required=True, help="Month code (e.g., 202510)")
    parser.add_argument("--headless", action="store_true", help="Run Playwright in headless mode (no visible browser). Omit to show browser for manual login.")
    parser.add_argument("--wait", type=int, default=40, help="Seconds to wait for manual login when Playwright opens (default: 40)")
    parser.add_argument("--workers", type=int, default=5, help="Number of parallel downloads (default: 5)")
    args = parser.parse_args()

    month_code = args.month
    agora_url = "https://agora.ogc.org"
    json_url = f"{PORTAL_ROOT}/upload/{month_code}/list_files.php"

    # prepare requests session
    session = requests.Session()
    # sensible default headers
    session.headers.update({
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })

    # Fetch file list with auto refresh/relogin if needed
    try:
        data = fetch_file_list_with_auto_refresh(session, month_code, agora_url, headless=args.headless, wait_time=args.wait)
    except Exception as e:
        print(f"❌ Failed to get file list: {e}")
        return

    # Download files in parallel
    download_files_in_parallel(session, data, month_code, max_workers=args.workers)


if __name__ == "__main__":
    main()
