"""
讀取出隊 Excel（all in one 直企格式），寫入 SQLite。
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

TOWNSHIP_RE = re.compile(r"[市縣][^市縣]{1,6}?([鄉鎮市區])")


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
    m = TOWNSHIP_RE.search(location)
    if m:
        end = m.end()
        # 取鄉鎮名（含結尾字元，去掉結尾字）
        start = location.rfind(county[0] if county else "", 0, end)
        # 更簡單：直接擷取縣市後到鄉/鎮/市/區
        m2 = re.search(r"[縣市](.{1,6}?)[鄉鎮市區]", location)
        if m2:
            region = m2.group(1)
    return county, region


def scan_cell(ws, keyword: str):
    """在 worksheet 中找含 keyword 的儲存格，回傳其值和座標。"""
    for row in ws.iter_rows():
        for cell in row:
            if cell.value and keyword in str(cell.value):
                return cell
    return None


def parse_p1(ws):
    """從 直企P1(列印) 萃取出隊資訊。"""
    # 出隊名稱：D2
    name = str(ws["D2"].value or "").strip() or None

    # 日期：C3 / C4
    date_start = roc_to_iso(ws["C3"].value or "")
    date_end = roc_to_iso(ws["C4"].value or "")

    # 入山地點：F3
    entry_loc = str(ws["F3"].value or "")
    county, region = extract_county_region(entry_loc)

    return name, date_start, date_end, county, region


def parse_roles(ws) -> dict[str, str]:
    """從 直企P1 工作人員區塊建立 {姓名: 角色} 對照。"""
    roles: dict[str, str] = {}
    role_keywords = {"主持人", "留守", "領隊", "嚮導"}
    for row in ws.iter_rows(min_row=16, max_row=26):
        label_cell = row[1]  # column B
        name_cell = row[2]   # column C
        label = str(label_cell.value or "").strip()
        name = str(name_cell.value or "").strip()
        if label in role_keywords and name:
            roles[name] = label
    return roles


def parse_members(ws, roles: dict[str, str]) -> list[tuple[str, str | None]]:
    """從 人員資料表 回傳 [(姓名, 角色), ...]。"""
    headers = {str(cell.value).strip(): cell.column for cell in ws[4] if cell.value}
    name_col = headers.get("全名")
    if name_col is None:
        return []
    members = []
    for row in ws.iter_rows(min_row=5, values_only=False):
        name_cell = row[name_col - 1]
        name = str(name_cell.value or "").strip()
        if not name:
            continue
        role = roles.get(name)
        members.append((name, role))
    return members


def normalize(xlsx_path: Path):
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)

    # 確認必要 sheet 存在
    if "直企P1(列印)" not in wb.sheetnames:
        print(f"  ⚠ 找不到「直企P1(列印)」sheet，跳過 {xlsx_path.name}")
        return
    if "人員資料表" not in wb.sheetnames:
        print(f"  ⚠ 找不到「人員資料表」sheet，跳過 {xlsx_path.name}")
        return

    ws_p1 = wb["直企P1(列印)"]
    ws_members = wb["人員資料表"]

    name, date_start, date_end, county, region = parse_p1(ws_p1)
    roles = parse_roles(ws_p1)
    members = parse_members(ws_members, roles)

    if not name:
        print(f"  ⚠ 無法取得出隊名稱，跳過 {xlsx_path.name}")
        return
    if not date_start:
        print(f"  ⚠ 無法解析 date_start，跳過 {xlsx_path.name}")
        return

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
        "INSERT INTO expeditions(name, date_start, date_end, county, region) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, date_start, date_end, county, region),
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
