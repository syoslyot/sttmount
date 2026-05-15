# sttmount — 山社出隊紀錄網站

## 專案目的
NCKU 山社的出隊紀錄展示網站。無會員系統，純資料展示。
幹部照舊把資料上傳至 Google Drive，系統每日自動同步並更新網站。

---

## 技術棧

| 層級 | 選擇 |
|---|---|
| Backend | Python 3.12 + FastAPI + Jinja2（SSR） |
| Database | SQLite（`db/sttmount.db`） |
| Frontend | HTML + Tailwind CSS（CDN）+ Vanilla JS |
| 地圖 | Leaflet.js + leaflet-omnivore（GPX/KML）|
| 地圖底圖 | OpenTopoMap（等高線）/ OSM / NLSC 正射影像 + 等高線 overlay |
| 部署 | Docker Compose + Nginx，跑在 Windows 筆電（學校固定 IP，內網） |
| 自動更新 | Watchtower（監聽 GHCR，自動 pull 新 image） |
| CI/CD | GitHub Actions：每日同步 Drive → build image → push GHCR |

---

## 資料來源（Google Drive）

```
所有出隊資料夾/
  {出隊名稱}/
    *.xlsx                 ← 出隊資料（正規化後存入 SQLite）
    地圖資料夾/
      *.gpx, *.kml         → app/static/gpx/{出隊名}/
      *.pdf, *.jpg, *.png  → app/static/maps/{出隊名}/
    紀錄資料夾/
      *.txt                → 讀入 DB records 資料表
```

環境變數（GitHub Actions Secrets）：
- `GDRIVE_CREDENTIALS_JSON` — Service Account JSON
- `GDRIVE_ROOT_FOLDER_ID` — 「所有出隊資料夾」的 Drive folder ID

---

## 專案結構

```
sttmount/
├── app/
│   ├── main.py            # FastAPI 入口
│   ├── models.py          # SQLite schema + get_conn()
│   ├── routes/
│   │   ├── region.py      # / 和 /region/{county}/{region}
│   │   ├── date.py        # /date
│   │   ├── search.py      # /search
│   │   └── expedition.py  # /expedition/{id}
│   ├── static/
│   │   ├── gpx/           # GPX/KML 檔案（依出隊名分子資料夾）
│   │   └── maps/          # PDF/圖片（依出隊名分子資料夾）
│   └── templates/
│       ├── base.html
│       ├── index.html         # 台灣縣市地圖（目前為格狀，之後改 SVG）
│       ├── region.html        # 縣市內子地區列表
│       ├── expedition_list.html
│       ├── expedition.html    # 出隊詳細頁（地圖、PDF、紀錄、隊員）
│       ├── date.html
│       └── search.html
├── scripts/
│   ├── sync_drive.py      # Google Drive → 本機（已實作）
│   └── normalize.py       # Excel → SQLite（待 Excel 範例後實作）
├── db/
│   └── sttmount.db        # SQLite（gitignore）
├── data/raw/              # Drive 下載的暫存 Excel（gitignore）
├── .github/workflows/
│   ├── sync.yml           # 每日定時同步（待實作）
│   └── deploy.yml         # push main 時 build & push image（待實作）
├── Dockerfile
├── docker-compose.yml     # app + nginx + watchtower
├── nginx.conf
└── requirements.txt
```

---

## DB Schema

```sql
expeditions  (id, name, date_start, date_end, county, region, description)
members      (id, expedition_id, name, role)
gpx_files    (id, expedition_id, filename, file_path)
map_files    (id, expedition_id, filename, file_path, file_type)
records      (id, expedition_id, filename, content)
```

---

## 功能現況

| 功能 | 狀態 |
|---|---|
| 地區查詢（縣市 → 子地區 → 出隊列表） | ✅ 完成（縣市頁目前為格狀，之後改台灣 SVG 地圖） |
| 日期查詢 | ✅ 完成 |
| 文字搜尋 | ✅ 完成 |
| 出隊詳細頁 | ✅ 完成 |
| Leaflet 地圖（底圖切換 + 等高線） | ✅ 完成 |
| GPX / KML 顯示 | ✅ 完成（omnivore，含 popup） |
| PDF / 圖片嵌入 + 下載 | ✅ 完成 |
| 成員紀錄（txt）顯示 | ✅ 完成 |
| Google Drive 同步腳本 | ✅ 完成（sync_drive.py） |
| Excel 正規化腳本 | ⏳ 待 Excel 範例 |
| GitHub Actions CI/CD | ⏳ 待實作 |
| 台灣 SVG 地圖（首頁） | ⏳ 待實作 |
| Server 部署文件 | ⏳ 待實作 |

---

## 本機開發

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 -c "from app.models import init_db; init_db()"
uvicorn app.main:app --reload
# 開啟 http://localhost:8000
```

---

## 待確認

- Excel 檔案結構（欄位、分頁名稱）→ normalize.py 依此設計
- 另一個地圖格式（目前支援 GPX + KML，其他之後補）
