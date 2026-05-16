"""
從 Google Drive 同步出隊資料到本機。

Drive 結構：
  所有出隊資料夾/
    {出隊名稱}/
      *.xlsx
      地圖資料夾/
        *.pdf, *.jpg, *.png, *.gpx, *.kml
      紀錄資料夾/
        *.txt

環境變數（存放於 GitHub Actions secrets）：
  GDRIVE_CREDENTIALS_JSON  - Service Account JSON 內容
  GDRIVE_ROOT_FOLDER_ID    - 「所有出隊資料夾」的 Drive folder ID
"""

import os
import io
import json
import sys
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

RAW_DIR  = Path(__file__).parent.parent / "data" / "raw"
GPX_DIR  = Path(__file__).parent.parent / "app" / "static" / "gpx"
MAPS_DIR = Path(__file__).parent.parent / "app" / "static" / "maps"

MAP_SUBFOLDER_NAMES = {"地圖資料夾", "地圖", "map", "maps"}
REC_SUBFOLDER_NAMES = {"紀錄資料夾", "紀錄", "record", "records"}
PDF_EXTS            = {".pdf"}
GPX_EXTS            = {".gpx", ".kml"}
RECORD_EXTS         = {".txt", ".md"}
EXCEL_EXTS          = {".xlsx", ".xls"}


def build_service():
    cred_json = os.environ.get("GDRIVE_CREDENTIALS_JSON")
    if not cred_json:
        raise RuntimeError("GDRIVE_CREDENTIALS_JSON not set")
    info = json.loads(cred_json)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def list_folder(service, folder_id: str) -> list[dict]:
    results = []
    page_token = None
    while True:
        resp = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, mimeType)",
            pageToken=page_token,
        ).execute()
        results.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return results


def download_file(service, file_id: str, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return
    request = service.files().get_media(fileId=file_id)
    with io.FileIO(dest, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    print(f"  downloaded: {dest}")


def sync_expedition(service, exp_folder_id: str, exp_name: str):
    exp_raw = RAW_DIR / exp_name
    exp_raw.mkdir(parents=True, exist_ok=True)

    items = list_folder(service, exp_folder_id)
    for item in items:
        name     = item["name"]
        fid      = item["id"]
        is_dir   = item["mimeType"] == "application/vnd.google-apps.folder"
        ext      = Path(name).suffix.lower()
        name_low = name.lower()

        if is_dir:
            if name_low in {n.lower() for n in MAP_SUBFOLDER_NAMES}:
                sync_map_folder(service, fid, exp_name)
            elif name_low in {n.lower() for n in REC_SUBFOLDER_NAMES}:
                sync_record_folder(service, fid, exp_name)
        elif ext in EXCEL_EXTS:
            download_file(service, fid, exp_raw / name)


def sync_map_folder(service, folder_id: str, exp_name: str):
    items = list_folder(service, folder_id)
    for item in items:
        name = item["name"]
        fid  = item["id"]
        ext  = Path(name).suffix.lower()
        if ext in GPX_EXTS:
            download_file(service, fid, GPX_DIR / f"{exp_name}.gpx")
        elif ext in PDF_EXTS:
            download_file(service, fid, MAPS_DIR / f"{exp_name}.pdf")


def sync_record_folder(service, folder_id: str, exp_name: str):
    rec_dir = RAW_DIR / exp_name / "records"
    rec_dir.mkdir(parents=True, exist_ok=True)
    items = list_folder(service, folder_id)
    for item in items:
        name = item["name"]
        fid  = item["id"]
        ext  = Path(name).suffix.lower()
        if ext in RECORD_EXTS:
            download_file(service, fid, rec_dir / name)


def main():
    root_id = os.environ.get("GDRIVE_ROOT_FOLDER_ID")
    if not root_id:
        print("GDRIVE_ROOT_FOLDER_ID not set", file=sys.stderr)
        sys.exit(1)

    service = build_service()
    expeditions = list_folder(service, root_id)

    for exp in expeditions:
        if exp["mimeType"] != "application/vnd.google-apps.folder":
            continue
        print(f"syncing: {exp['name']}")
        sync_expedition(service, exp["id"], exp["name"])

    print("sync complete")


if __name__ == "__main__":
    main()
