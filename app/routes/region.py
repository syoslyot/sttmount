from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.models import get_conn

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

# (display, db_counties, col, row)
COUNTY_GRID = [
    ("基隆", ["基隆市"],                3, 1),
    ("台北", ["臺北市", "台北市"],      4, 1),
    ("新北", ["新北市"],                2, 2),
    ("宜蘭", ["宜蘭縣"],                5, 2),
    ("桃園", ["桃園市"],                1, 3),
    ("新竹", ["新竹市", "新竹縣"],      2, 3),
    ("苗栗", ["苗栗縣"],                1, 4),
    ("台中", ["臺中市", "台中市"],      2, 4),
    ("花蓮", ["花蓮縣"],                5, 4),
    ("彰化", ["彰化縣"],                2, 5),
    ("南投", ["南投縣"],                3, 5),
    ("雲林", ["雲林縣"],                2, 6),
    ("嘉義", ["嘉義市", "嘉義縣"],      2, 7),
    ("台南", ["臺南市", "台南市"],      2, 8),
    ("台東", ["台東縣"],                5, 8),
    ("高雄", ["高雄市"],                1, 9),
    ("屏東", ["屏東縣"],                1, 10),
]

COUNTY_MAP = {c[0]: c[1] for c in COUNTY_GRID}


def _query_expeditions(counties: list[str], limit: int = 5) -> list:
    placeholders = ",".join("?" * len(counties))
    with get_conn() as conn:
        return conn.execute(
            f"SELECT * FROM expeditions WHERE county IN ({placeholders}) ORDER BY date_start DESC LIMIT {limit}",
            counties
        ).fetchall()


@router.get("/", response_class=HTMLResponse)
def home(request: Request, mode: str = "map"):
    with get_conn() as conn:
        recent = conn.execute(
            "SELECT * FROM expeditions ORDER BY date_start DESC LIMIT 5"
        ).fetchall()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "county_grid": COUNTY_GRID,
        "initial_mode": mode,
        "recent": recent,
    })


# ── Fragment endpoints ─────────────────────────────────────────────────────

@router.get("/fragment/recent", response_class=HTMLResponse)
def fragment_recent(request: Request):
    with get_conn() as conn:
        items = conn.execute(
            "SELECT * FROM expeditions ORDER BY date_start DESC LIMIT 5"
        ).fetchall()
    return templates.TemplateResponse("_results.html", {"request": request, "items": items, "title": "最近出隊"})


@router.get("/fragment/county/{name}", response_class=HTMLResponse)
def fragment_county(request: Request, name: str):
    counties = COUNTY_MAP.get(name, [name])
    items = _query_expeditions(counties)
    return templates.TemplateResponse("_results.html", {
        "request": request, "items": items, "title": name,
    })


@router.get("/fragment/date", response_class=HTMLResponse)
def fragment_date(request: Request, year: int | None = Query(None), month: int | None = Query(None)):
    with get_conn() as conn:
        if year and month:
            items = conn.execute(
                "SELECT * FROM expeditions WHERE strftime('%Y', date_start)=? AND strftime('%m', date_start)=? ORDER BY date_start DESC LIMIT 5",
                (str(year), f"{month:02d}")
            ).fetchall()
        elif year:
            items = conn.execute(
                "SELECT * FROM expeditions WHERE strftime('%Y', date_start)=? ORDER BY date_start DESC LIMIT 5",
                (str(year),)
            ).fetchall()
        else:
            items = []
    title = f"{year}年{'%d月' % month if month else ''}" if year else ""
    return templates.TemplateResponse("_results.html", {"request": request, "items": items, "title": title})


@router.get("/fragment/search", response_class=HTMLResponse)
def fragment_search(request: Request, q: str = Query("")):
    items = []
    if q:
        pattern = f"%{q}%"
        with get_conn() as conn:
            items = conn.execute(
                "SELECT * FROM expeditions WHERE name LIKE ? OR region LIKE ? OR county LIKE ? OR description LIKE ? ORDER BY date_start DESC LIMIT 5",
                (pattern, pattern, pattern, pattern)
            ).fetchall()
    return templates.TemplateResponse("_results.html", {"request": request, "items": items, "title": f"「{q}」" if q else ""})


# ── Detail pages ───────────────────────────────────────────────────────────

@router.get("/region/{county}", response_class=HTMLResponse)
def county_detail(request: Request, county: str):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT region FROM expeditions WHERE county = ? ORDER BY region",
            (county,)
        ).fetchall()
    return templates.TemplateResponse("region.html", {
        "request": request, "county": county, "regions": rows,
    })


@router.get("/region/{county}/{region}", response_class=HTMLResponse)
def region_detail(request: Request, county: str, region: str):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM expeditions WHERE county = ? AND region = ? ORDER BY date_start DESC",
            (county, region)
        ).fetchall()
    return templates.TemplateResponse("expedition_list.html", {
        "request": request, "county": county, "region": region, "expeditions": rows,
    })
