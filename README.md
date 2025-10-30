# 🧭 OGC AGORA / PORTAL File Downloader

This Python script automates the download of files from the **OGC AGORA portal** (which runs on the Circle.so platform) and the **OGC Portal (portal.ogc.org)**.

It authenticates once through AGORA (via a manual login in a browser window) and then uses the stored cookies for future runs to fetch files automatically.

---

## 🚀 Features

✅ Automatic login through **Playwright** (manual the first time, then cookies are reused)  
✅ Automatically fetches JSON file listings from `portal.ogc.org`  
✅ Parallel downloads with progress bar (`tqdm`)  
✅ Files are grouped into folders by their `"group"` field  
✅ Intelligent skip logic:  
   - Skips files that already exist and are **at least the same size** as the server version  
   - Automatically re-downloads files that are smaller  
✅ Robust retry mechanism for network issues  
✅ **Final summary** at the end with counts and total MB downloaded  

---

## 📦 Requirements

Create a Python virtual environment (optional but recommended):

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

> 🧩 Main dependencies:
> - `requests`
> - `playwright`
> - `tqdm`
> - `argparse`
> - `concurrent.futures`

Before first use, initialize Playwright browsers:
```bash
playwright install
```

---

## ⚙️ Usage

```bash
python ogc_downloader.py --month 202510 --workers 10 --wait 20 [--headless]
```

### Arguments
| Argument | Description |
|-----------|--------------|
| `--month` | Month folder on the OGC Portal (e.g., `202510` for October 2025) |
| `--workers` | Number of parallel download threads (default: 5) |
| `--wait` | Seconds to wait for manual login during Playwright run (default: 20) |
| `--headless` | If present, runs the browser in headless mode (no visible window) |

---

## 🧱 Behavior and Logic

1. **Cookie Reuse**
   - On the first run, Playwright opens a browser for you to log in manually to AGORA.
   - After login, cookies for both `agora.ogc.org` and `portal.ogc.org` are saved in `cookies_ogc.json`.
   - Subsequent runs reuse these cookies until they expire.

2. **Session Initialization**
   - The script always calls `https://agora.ogc.org/202610-uploader` (temporary workaround for a known typo in the portal URL) before accessing the file list.

3. **Download Logic**
   - Files are grouped into subfolders under `downloads/` based on the `"group"` metadata.
   - If a file already exists locally:
     - ✅ **Skipped** if local size ≥ server-reported size  
     - ⚠️ **Re-downloaded** if local size < server-reported size  
   - Files are downloaded via `https://portal.ogc.org/upload/<month>/getfile.php?id=<original_name>`.

4. **Retries**
   - Each download is retried up to 3 times in case of transient errors (HTTP, network, timeout).

---

## 🧾 End-of-Run Summary

At the end of execution, the script prints a detailed summary:

```
=== 🧾 Download Summary ===
✅ Downloaded:  15 files
⏭️ Skipped:     42 files
⚠️ Failed:       2 files
📦 Total size downloaded: 128.35 MB

⚠️ Failed files:
 - UCPI_October_Presentation_FINAL.pptx
```

---

## 🧹 Troubleshooting

### ❌ "Failed to fetch JSON (403)"
Cookies are expired — simply delete `cookies_ogc.json` and rerun the script.  
It will reopen the browser and ask you to log in again.

### ❌ "Playwright not found"
Make sure you ran:
```bash
playwright install
```

### 🔁 Infinite "size mismatch"
The server’s reported `size` in JSON may be slightly off; the script now considers files valid if local size ≥ server size.

---

## 🪄 Example

```bash
python ogc_downloader.py --month 202510 --workers 8 --wait 30
```

Output:
```
📦 Starting downloads: 73 files with 8 workers...

Overall files: 100%|█████████████████████████████████| 73/73 [00:58<00:00,  1.25file/s]
✅ Downloaded 2025_October_glTF.pptx (832032 bytes)
⏭️ Skipped 2025_October_Chair_Slides_UDT_CityGML.pptx (already present)
...

=== 🧾 Download Summary ===
✅ Downloaded: 12 files
⏭️ Skipped:    61 files
⚠️ Failed:     0 files
📦 Total size downloaded: 47.38 MB
```

---

## 📁 File Structure

```
.
├── ogc_downloader.py
├── requirements.txt
├── README.md
├── cookies_ogc.json        # created automatically after first login
└── downloads/
    ├── Closing_Plenary_-_no_motions/
    ├── 3D_Geospatial_SWG/
    ├── UDT_CityGML/
    └── ...
```

---

## 🧰 Notes

- If AGORA changes its authentication flow, the Playwright automation might need an update.  
- If a future event uses a different month code (e.g., `202603`), simply change the `--month` argument.  
- The script avoids re-downloading existing files unless necessary, so you can rerun it safely multiple times.

---

© Open Geospatial Consortium (OGC) community use only — automation tool for members with valid credentials.
