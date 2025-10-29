# OGC AGORA / Portal Downloader

This Python script automates downloading files from the OGC AGORA portal, including **portal.ogc.org**, handling authentication, cookies, and parallel downloads.

---

## Features

- **Authentication with Playwright** (manual login if necessary)
- **Persistent cookies** stored in `cookies_ogc.json`
- **Portal session initialization** via hardcoded uploader URL
- **Download files in parallel** (`--workers`)
- **File size check** to skip already downloaded files
- **Retries for failed downloads**
- **Organizes downloads by group folder**
- **Per-file progress bars** using `tqdm`

---

## Installation

1. Clone or download this repository.
2. Create a Python virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   venv\Scripts\activate     # Windows


## Install required Python packages:

pip install -r requirements.txt


## Install Playwright browser binaries:

playwright install
