from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.models import get_conn

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

@router.get("/date", response_class=HTMLResponse)
def by_date(request: Request, year: int | None = Query(None), month: int | None = Query(None)):
    with get_conn() as conn:
        if year and month:
            rows = conn.execute(
                "SELECT * FROM expeditions WHERE strftime('%Y', date_start) = ? AND strftime('%m', date_start) = ? ORDER BY date_start DESC",
                (str(year), f"{month:02d}")
            ).fetchall()
        elif year:
            rows = conn.execute(
                "SELECT * FROM expeditions WHERE strftime('%Y', date_start) = ? ORDER BY date_start DESC",
                (str(year),)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM expeditions ORDER BY date_start DESC"
            ).fetchall()
    return templates.TemplateResponse("date.html", {"request": request, "expeditions": rows, "year": year, "month": month})
