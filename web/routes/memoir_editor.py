"""Routes for the Memoir Editor (placeholder).

Stage 4+ work — UI is a stub. The route exists so the nav link works and so
the Upgrade Manager / nav structure is stable for future rounds.
"""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web import config
from web.services import userdata_service

router = APIRouter()
templates = Jinja2Templates(directory=str(config.ROOT / "web" / "templates"))


def _redirect(target: str, *, message: str | None = None, error: str | None = None) -> RedirectResponse:
    params: dict[str, str] = {}
    if message:
        params["message"] = message
    if error:
        params["error"] = error
    qs = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(url=f"{target}{qs}", status_code=303)


@router.get("/memoirs", response_class=HTMLResponse)
def memoir_editor_index(request: Request):
    try:
        users = userdata_service.list_users()
    except FileNotFoundError as e:
        return _redirect("/", error=str(e))
    if len(users) == 1:
        return RedirectResponse(url=f"/users/{users[0].user_id}/memoirs", status_code=303)
    return templates.TemplateResponse(
        request,
        "memoir_editor.html",
        {
            "active": "memoirs",
            "user_id": None,
        },
    )


@router.get("/users/{user_id}/memoirs", response_class=HTMLResponse)
def memoir_editor_view(request: Request, user_id: int):
    try:
        users = userdata_service.list_users()
    except FileNotFoundError as e:
        return _redirect("/", error=str(e))
    user_match = next((u for u in users if u.user_id == user_id), None)
    if user_match is None:
        return _redirect("/users", error=f"User {user_id} not found.")
    return templates.TemplateResponse(
        request,
        "memoir_editor.html",
        {
            "active": "memoirs",
            "user_id": user_id,
            "user_name": user_match.name,
        },
    )
