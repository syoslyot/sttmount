from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.models import get_conn

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

@router.get("/search", response_class=HTMLResponse)
def search(request: Request, q: str = Query("")):
    rows = []
    if q:
        pattern = f"%{q}%"
        with get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM expeditions
                   WHERE name LIKE ? OR region LIKE ? OR county LIKE ? OR description LIKE ?
                   ORDER BY date_start DESC""",
                (pattern, pattern, pattern, pattern)
            ).fetchall()
    return templates.TemplateResponse("search.html", {"request": request, "expeditions": rows, "q": q})
