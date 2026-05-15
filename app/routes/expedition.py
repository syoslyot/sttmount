from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.models import get_conn

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

STATIC_MAPS = Path(__file__).parent.parent / "static" / "maps"

@router.get("/expedition/{expedition_id}", response_class=HTMLResponse)
def expedition_detail(request: Request, expedition_id: int):
    with get_conn() as conn:
        exp = conn.execute("SELECT * FROM expeditions WHERE id = ?", (expedition_id,)).fetchone()
        if not exp:
            raise HTTPException(status_code=404)
        members   = conn.execute("SELECT * FROM members   WHERE expedition_id = ?", (expedition_id,)).fetchall()
        gpx_files = conn.execute("SELECT * FROM gpx_files WHERE expedition_id = ?", (expedition_id,)).fetchall()
        map_files = conn.execute("SELECT * FROM map_files WHERE expedition_id = ?", (expedition_id,)).fetchall()
        records   = conn.execute("SELECT * FROM records   WHERE expedition_id = ?", (expedition_id,)).fetchall()

    exp_dir = STATIC_MAPS / str(expedition_id)
    return templates.TemplateResponse("expedition.html", {
        "request":    request,
        "exp":        exp,
        "members":    members,
        "gpx_files":  gpx_files,
        "map_files":  map_files,
        "records":    records,
        "p1_preview": (exp_dir / "p1_preview.png").exists(),
        "p2_preview": (exp_dir / "p2_preview.png").exists(),
    })
