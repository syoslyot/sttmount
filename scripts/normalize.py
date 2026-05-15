"""
讀取出隊 Excel（all in one 直企格式），寫入 SQLite。
資料來源：直企P1（出隊資訊）、直企P2（隊員名單、留守資料）。
用法：
  python3 scripts/normalize.py data/raw/xxx.xlsx
  python3 scripts/normalize.py data/raw/          # 處理目錄下所有 xlsx
"""
import re
import sys
import sqlite3
from pathlib import Path

import openpyxl

DB_PATH = Path(__file__).parent.parent / "db" / "sttmount.db"

COUNTY_NORMALIZE = {
    "臺北市": "台北", "台北市": "台北",
    "新北市": "新北",
    "基隆市": "基隆",
    "宜蘭縣": "宜蘭",
    "桃園市": "桃園",
    "新竹市": "新竹", "新竹縣": "新竹",
    "苗栗縣": "苗栗",
    "臺中市": "台中", "台中市": "台中",
    "花蓮縣": "花蓮",
    "彰化縣": "彰化",
    "南投縣": "南投",
    "雲林縣": "雲林",
    "嘉義市": "嘉義", "嘉義縣": "嘉義",
    "臺南市": "台南", "台南市": "台南",
    "高雄市": "高雄",
    "屏東縣": "屏東",
    "臺東縣": "台東", "台東縣": "台東",
}

# P2 欄 A 的角色縮寫對應
ROLE_MAP = {"領": "領隊", "嚮": "嚮導", "隊": "隊員", "新": "新生"}


def roc_to_iso(text: str) -> str | None:
    """'民國 115 年 4 月 30 日 ...' → '2026-04-30'"""
    m = re.search(r"(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日", str(text))
    if not m:
        return None
    y = int(m.group(1)) + 1911
    mo, d = int(m.group(2)), int(m.group(3))
    return f"{y:04d}-{mo:02d}-{d:02d}"


def extract_county_region(location: str):
    """'入山：臺東縣達仁鄉' → ('台東', '達仁')"""
    county = None
    for official, display in COUNTY_NORMALIZE.items():
        if official in location:
            county = display
            break
    region = None
    m2 = re.search(r"[縣市](.{1,6}?)[鄉鎮市區]", location)
    if m2:
        region = m2.group(1)
    return county, region


def parse_p1(ws):
    """從 直企P1(列印) 萃取出隊資訊。"""
    name = str(ws["D2"].value or "").strip() or None
    date_start = roc_to_iso(ws["C3"].value or "")
    date_end = roc_to_iso(ws["C4"].value or "")
    entry_loc = str(ws["F3"].value or "")
    county, region = extract_county_region(entry_loc)
    return name, date_start, date_end, county, region


def parse_p2(ws):
    """從 直企P2(列印) 萃取留守資料（→ description）和隊員名單。"""
    # 留守資料：M/N 欄 rows 3–11
    desc_parts = []
    for r in range(3, 12):
        label = str(ws.cell(r, 13).value or "").strip()   # col M
        value = str(ws.cell(r, 14).value or "").strip()   # col N
        if label and value:
            desc_parts.append(f"{label}：{value}")
    garmin = str(ws["D10"].value or "").strip()
    if garmin.startswith("http"):
        desc_parts.append(f"Garmin 追蹤：{garmin}")
    notes = str(ws["D11"].value or "").strip()
    if notes:
        desc_parts.append(f"注意事項：{notes}")
    description = "\n".join(desc_parts) or None

    # 人員名單：rows 16+，col A = 角色縮寫（攜帶），col D = 姓名
    members: list[tuple[str, str | None]] = []
    current_role: str | None = None
    for r in range(16, ws.max_row + 1):
        role_abbr = str(ws.cell(r, 1).value or "").strip()   # col A
        name_raw = str(ws.cell(r, 4).value or "").strip()    # col D
        if role_abbr in ROLE_MAP:
            current_role = ROLE_MAP[role_abbr]
        name = name_raw.split("\n")[0].strip()
        if name and current_role is not None:
            members.append((name, current_role))

    return description, members


def normalize(xlsx_path: Path):
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)

    if "直企P1(列印)" not in wb.sheetnames:
        print(f"  ⚠ 找不到「直企P1(列印)」sheet，跳過 {xlsx_path.name}")
        return

    ws_p1 = wb["直企P1(列印)"]
    name, date_start, date_end, county, region = parse_p1(ws_p1)

    if not name:
        print(f"  ⚠ 無法取得出隊名稱，跳過 {xlsx_path.name}")
        return
    if not date_start:
        print(f"  ⚠ 無法解析 date_start，跳過 {xlsx_path.name}")
        return

    description, members = None, []
    if "直企P2(列印)" in wb.sheetnames:
        description, members = parse_p2(wb["直企P2(列印)"])
    else:
        print(f"  ⚠ 找不到「直企P2(列印)」sheet，隊員與留守資料略過")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    existing = conn.execute(
        "SELECT id FROM expeditions WHERE name=? AND date_start=?",
        (name, date_start)
    ).fetchone()

    if existing:
        print(f"  → 已存在（id={existing[0]}）：{name}，跳過")
        conn.close()
        return

    cur = conn.execute(
        "INSERT INTO expeditions(name, date_start, date_end, county, region, description) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (name, date_start, date_end, county, region, description),
    )
    conn.commit()
    exp_id = cur.lastrowid

    for mname, mrole in members:
        conn.execute(
            "INSERT INTO members(expedition_id, name, role) VALUES (?, ?, ?)",
            (exp_id, mname, mrole),
        )
    conn.commit()

    print(f"  ✓ 已插入：{name}（id={exp_id}）")
    print(f"    日期：{date_start} ～ {date_end or '—'}")
    print(f"    地點：{county or '—'} · {region or '—'}")
    print(f"    隊員：{len(members)} 人")
    conn.close()


def main():
    if len(sys.argv) < 2:
        print("用法：python3 scripts/normalize.py <檔案.xlsx 或目錄>")
        sys.exit(1)

    target = Path(sys.argv[1])
    files = sorted(target.glob("*.xlsx")) if target.is_dir() else [target]

    for f in files:
        print(f"\n處理：{f.name}")
        try:
            normalize(f)
        except Exception as e:
            print(f"  ✗ 錯誤：{e}")


if __name__ == "__main__":
    main()
