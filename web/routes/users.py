"""Routes for the read-only user viewer (Stage 0b)."""

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


@router.get("/users", response_class=HTMLResponse)
def list_users_view(request: Request, message: str | None = None, error: str | None = None):
    try:
        users = userdata_service.list_users()
    except FileNotFoundError as e:
        return _redirect("/", error=str(e))
    return templates.TemplateResponse(
        request,
        "users.html",
        {
            "active": "users",
            "message": message,
            "error": error,
            "users": users,
        },
    )


@router.get("/users/{user_id}", response_class=HTMLResponse)
def user_detail_view(
    request: Request,
    user_id: int,
    message: str | None = None,
    error: str | None = None,
):
    try:
        detail = userdata_service.get_user_detail(user_id)
    except FileNotFoundError as e:
        return _redirect("/", error=str(e))
    if detail is None:
        return _redirect("/users", error=f"User {user_id} not found.")
    return templates.TemplateResponse(
        request,
        "user_detail.html",
        {
            "active": "users",
            "message": message,
            "error": error,
            "u": detail,
        },
    )
