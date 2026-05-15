from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.models import get_conn

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/region/{county}", response_class=HTMLResponse)
def county(request: Request, county: str):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT region FROM expeditions WHERE county = ? ORDER BY region",
            (county,)
        ).fetchall()
    return templates.TemplateResponse("region.html", {"request": request, "county": county, "regions": rows})

@router.get("/region/{county}/{region}", response_class=HTMLResponse)
def region_detail(request: Request, county: str, region: str):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM expeditions WHERE county = ? AND region = ? ORDER BY date_start DESC",
            (county, region)
        ).fetchall()
    return templates.TemplateResponse("expedition_list.html", {"request": request, "expeditions": rows})
