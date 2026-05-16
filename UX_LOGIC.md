# sttmount — 完整 UX / 商業邏輯文件

---

## 一、資料進入流程（Data Ingestion）

### 1-1. Google Drive 同步（`sync_drive.py`）

幹部在 Drive 上維護以下結構，腳本每日透過 Service Account 讀取：

```
所有出隊資料夾/
  {出隊名稱}/              ← 每次出隊一個資料夾，名稱即為出隊名
    *.xlsx                 ← 出隊計畫書（直企格式）
    地圖資料夾/             ← 名稱可為「地圖資料夾」「地圖」「map」「maps」
      *.gpx 或 *.kml       ← GPX 軌跡
      *.pdf                ← 地圖 PDF
    紀錄資料夾/             ← 名稱可為「紀錄資料夾」「紀錄」「record」「records」
      *.txt 或 *.md        ← 隊員紀錄文章（可多份）
```

**下載目的地：**

| 類型 | 下載至 |
|---|---|
| xlsx | `data/raw/xlsx/{出隊名}.xlsx` |
| GPX / KML | `app/static/gpx/{出隊名}.gpx` |
| PDF | `app/static/maps/{出隊名}.pdf` |
| txt / md | `data/raw/txt/{出隊名}/{filename}` |

**冪等保護：** 若目標檔案已存在，`download_file()` 直接跳過，不重複下載。

---

### 1-2. 正規化入庫（`normalize.py`）

預設掃描 `data/raw/xlsx/` 下所有 xlsx，也可傳指定檔案路徑。

#### 處理步驟（依序）

```
讀取 xlsx
  ↓
解析 直企P1(列印) sheet
  → 出隊名稱、出發日、回程日、入山地點（縣市＋鄉鎮）、出山地點（縣市＋鄉鎮）
  ↓
解析 直企P2(列印) sheet
  → 留守資料（M/N 欄）、Garmin 追蹤連結、注意事項 → 合為 description
  → 人員名單（角色、系級、姓名、資歷）
  ↓
查詢 DB：是否已存在同名＋同日期的出隊？
  ├─ 已存在 → 補掃靜態檔案（scan_static_files）後結束
  └─ 不存在 → INSERT expeditions + members + expedition_counties
              ↓
              取得 exp_id
              ↓
              rename xlsx：{出隊名}.xlsx → {id}.xlsx
              ↓
              scan_static_files（見下）
              ↓
              生成截圖預覽（capture_sheet_range + build_a4_preview）
              ↓
              UPDATE expeditions SET preview_image
```

#### scan_static_files 行為

| 資源 | 來源（下載時名稱） | 目的地（改名後） | DB 寫入 |
|---|---|---|---|
| GPX | `app/static/gpx/{出隊名}.gpx` | `app/static/gpx/{id}.gpx` | `gpx_files` |
| PDF | `app/static/maps/{出隊名}.pdf` | `app/static/maps/{id}.pdf` | `map_files` |
| txt 資料夾 | `data/raw/txt/{出隊名}/` | `data/raw/txt/{id}/` | `records`（逐檔 INSERT） |

所有靜態資源在 DB 中以 `{id}.ext` 形式儲存，與出隊的原始中文名稱完全解耦。

#### 重複執行（idempotency）

- xlsx 已改名：`xlsx_path != xlsx_final` 為 false，略過 rename
- GPX/PDF 已改名：找不到 `{出隊名}.gpx`，略過 rename；`INSERT OR IGNORE` 保護不重複寫 DB
- txt 資料夾已改名（名稱為數字 id）：`txt_src != txt_dest` 為 false，略過 rename
- records：每筆用 `(expedition_id, filename)` 查 DB，已存在則跳過

---

### 1-3. 截圖生成邏輯

1. **擷取 P1 範圍**（`A2:G27`）→ LibreOffice 轉 PDF → PyMuPDF 轉 PNG（2× 解析度）
2. **擷取 P2 範圍**（`B2:O11`）→ 同上
3. **`trim_whitespace()`**：裁切空白邊框，保留 15px padding
4. **`build_a4_preview()`**：
   - 目標寬 1240px（A4 比例）
   - 兩張圖垂直排列，中間 16px gap
   - 若總高超過 1754px（A4 高），等比縮小至符合
   - 輸出：`app/static/previews/{id}.png`

---

## 二、網頁 UX 流程

### 2-1. 首頁（`/`）

**版面：** 左右分割，各佔 50% 視窗高度，獨立捲動

#### 左半：篩選區（三種模式）

| 模式 | Tab | 行為 |
|---|---|---|
| 地區 | 地圖圖示 | 顯示台灣縣市格狀地圖，點選縣市 |
| 日期 | 日曆圖示 | 快速預設（1個月／半年／1年／3年）＋自訂日期區間 |
| 關鍵字 | 搜尋圖示 | 即時搜尋（300ms debounce），清空自動恢復預設列表 |

Tab 切換時主動態清除縣市格的選取狀態（切到非地區模式時）。

#### 右半：結果列表

- 初始載入：`/fragment/recent`，以結束日期排序（最近的在上方）
- 每頁 20 筆，捲動到底部 200px 前自動載入下一頁（Infinite Scroll）
- 各篩選模式觸發的 Fragment API：

| 觸發 | 呼叫端點 |
|---|---|
| 點選縣市 | `GET /fragment/county/{name}` |
| 日期變更 | `GET /fragment/date?date_from=&date_to=` |
| 關鍵字輸入 | `GET /fragment/search?q=` |
| 關鍵字清空 | `GET /fragment/recent` |
| 切換模式（不觸發新查詢） | 維持目前右半結果 |

所有端點共用 `?offset=N` 參數支援分頁（LIMIT 21，多一筆用來判斷是否有下一頁）。

#### 日期模式細節

- 頁面載入時，日期輸入框預設為今天
- 快速預設按鈕設定 `date-from`／`date-to` 後自動呼叫 `loadDate()`
- `date-from` 或 `date-to` 任一空白：不觸發查詢

---

### 2-2. 出隊詳細頁（`/expedition/{id}`）

**版面：** 左右分割，左地圖右資訊，各自獨立捲動

#### 左半：互動地圖

- 預設底圖：NLSC 通用電子地圖
- 可切換底圖：OpenTopoMap（等高線地形）、OpenStreetMap、NLSC 正射影像
- 可疊加 overlay：NLSC 等高線
- 初始中心點：依出隊 `county` 欄對應縣市座標；無縣市資料則顯示台灣全島（`[23.6, 121.0]`，zoom 8）
- 若有 GPX：顯示高度剖面圖（底部固定 140px）；支援懸停游標對應地圖位置
- 若有 KML：改用 omnivore 載入，自動 fitBounds

#### 右半：出隊資訊

顯示順序（由上至下）：

1. **截圖預覽**（P1 + P2 合併圖，`previews/{id}.png`）— 若存在才顯示
2. **人員名單**（`<details>`，預設**收合**）— 若有隊員才顯示
   - 欄位：姓名、角色（領隊／嚮導／隊員／新生）、系級、資歷
3. **紀錄文章**（每份 txt 各一個 `<details>`，預設**展開**）— 若有才顯示
   - 以 `<pre>` 保留原始格式

#### Navbar 附加元素（右上角下載按鈕）

- 有 GPX：顯示下載按鈕（`{出隊名}.gpx`）
- 有 PDF：顯示下載按鈕（`{出隊名}.pdf`）
- 兩者皆無：不顯示任何下載元素

---

## 三、DB Schema 與資料規則

### 縣市正規化規則

所有縣市一律存 17 個顯示簡稱（「台北」「南投」等），
normalize.py 負責將 Excel 中的官方名稱（「臺北市」「台北市」「南投縣」）統一轉換。

```
expeditions      id, name, date_start, date_end, county, region, region_exit,
                 description, preview_image, created_at
members          id, expedition_id, name, role, department, experience
gpx_files        id, expedition_id, file_path          （如 "210.gpx"）
map_files        id, expedition_id, file_path          （如 "210.pdf"）
records          id, expedition_id, filename, content
expedition_counties  expedition_id, county             （入山＋出山各一筆，UNIQUE）
```

所有子表皆設 `ON DELETE CASCADE`，刪除出隊資料時自動清除關聯紀錄。

---

## 四、自動化 CI/CD 流程（`.github/workflows/ci.yml`）

```
每日定時觸發（或手動）
  ↓
sync_drive.py   ← 從 Google Drive 下載新資料
  ↓
normalize.py    ← 解析 xlsx → 寫入 DB → 改名靜態檔 → 生成截圖
  ↓
Build Docker image（含更新後的 DB 和靜態檔案）
  ↓
Push to GHCR
  ↓
Watchtower（部署伺服器）自動偵測新 image → 重啟容器
```
