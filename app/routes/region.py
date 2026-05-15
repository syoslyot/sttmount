from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.models import get_conn

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

COUNTIES = [
    "臺北市", "新北市", "基隆市", "宜蘭縣",
    "桃園市", "新竹市", "新竹縣", "苗栗縣",
    "臺中市", "彰化縣", "南投縣", "雲林縣",
    "嘉義市", "嘉義縣", "臺南市", "高雄市",
    "屏東縣", "臺東縣", "花蓮縣", "澎湖縣",
    "金門縣", "連江縣",
]

@router.get("/region", response_class=HTMLResponse)
def region_index(request: Request):
    return templates.TemplateResponse("region_list.html", {
        "request": request,
        "counties": COUNTIES,
    })

@router.get("/region/{county}", response_class=HTMLResponse)
def county(request: Request, county: str):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT region FROM expeditions WHERE county = ? ORDER BY region",
            (county,)
        ).fetchall()
    return templates.TemplateResponse("region.html", {
        "request": request,
        "county": county,
        "regions": rows,
    })

@router.get("/region/{county}/{region}", response_class=HTMLResponse)
def region_detail(request: Request, county: str, region: str):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM expeditions WHERE county = ? AND region = ? ORDER BY date_start DESC",
            (county, region)
        ).fetchall()
    return templates.TemplateResponse("expedition_list.html", {
        "request": request,
        "county": county,
        "region": region,
        "expeditions": rows,
    })
