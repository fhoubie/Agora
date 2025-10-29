# OGC AGORA / Portal Downloader

This Python script automates downloading files from the OGC AGORA portal, including **portal.ogc.org**, handling authentication, cookies, and parallel downloads.

---

## Features

- **Authentication with Playwright** (manual login if necessary)
- **Persistent cookies** stored in `cookies_ogc.json`
- **Portal session initialization** via hardcoded uploader URL
- **Download files in parallel** (`--workers`)
- **File size check** to skip already downloaded files
- **Retries for failed downloads`
- **Organizes downloads by group folder**
- **Per-file progress bars** using `tqdm`

---

## Installation

1. **Clone or download this repository**
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Create a Python virtual environment (recommended)**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   venv\Scripts\activate     # Windows
   ```

3. **Install required Python packages**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright browser binaries**
   ```bash
   playwright install
   ```

> **Note:** Make sure Python ≥ 3.8 is installed.

---

## Usage

Run the script using:

```bash
python ogc_downloader.py --month <month_code> [--headless] [--workers N] [--wait S]
```

### Arguments

- `--month` (required): Month code to download, e.g., `202510`.
- `--headless` (optional flag): Run browser in headless mode (no GUI). Omit to show browser window for manual login.
- `--workers` (optional): Number of parallel downloads (default: 5).
- `--wait` (optional): Seconds to wait for manual login (default: 40).

### Examples

Run in **headful mode** (browser visible) for manual login:

```bash
python ogc_downloader.py --month 202510 --workers 10 --wait 30
```

Run in **headless mode** (browser invisible):

```bash
python ogc_downloader.py --month 202510 --headless --workers 10
```

---

## Directory Structure

- `downloads/` — files are saved here, organized by **group** (spaces replaced by underscores).  
- `cookies_ogc.json` — saved cookies for session persistence.

---

## Notes

- The script visits a **hardcoded uploader URL** (`202510-uploader`) to initialize the portal session. Update this URL if a different month is required.
- Already downloaded files with **matching size** are skipped automatically.
- Per-file **progress bars** show real-time download progress.
- Manual login is required on first run or if cookies have expired.
- Headless mode is useful for automated runs after cookies are saved, but **cannot be used for first-time login**.

---

## Troubleshooting

- **403 error fetching JSON** → Make sure to log in manually in headful mode if cookies are missing or expired.
- **Playwright browser does not open** → Do **not** use `--headless` if you need manual login.
- **Resume downloads** → The script skips files with matching size but does not currently resume partially downloaded files.

---

## License

This script is provided as-is for OGC portal automation. Use responsibly.
