from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.models import get_conn

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    with get_conn() as conn:
        recent = conn.execute(
            "SELECT * FROM expeditions ORDER BY date_start DESC LIMIT 5"
        ).fetchall()
    return templates.TemplateResponse("index.html", {"request": request, "recent": recent})
