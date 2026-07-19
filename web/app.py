"""Веб-панель управления ботом на FastAPI (localhost).

Простой логин по WEB_LOGIN/WEB_PASSWORD из .env, сессия в signed cookie.
Позволяет смотреть чаты, участников, баллы, товары и редактировать баллы.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import select

from config import config
from database.models import Chat, ChatMember, ShopItem, User
from database.session import get_session

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
serializer = URLSafeSerializer(config.web_secret, salt="web-session")

app = FastAPI(title="MeowMind Panel")

COOKIE_NAME = "mm_session"


# ─── Аутентификация ─────────────────────────────────────────

def _is_authed(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return False
    try:
        data = serializer.loads(token)
        return data.get("user") == config.web_login
    except BadSignature:
        return False


def _redirect_login() -> RedirectResponse:
    return RedirectResponse("/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login")
async def login_submit(
    request: Request, username: str = Form(...), password: str = Form(...)
):
    if username == config.web_login and password == config.web_password:
        token = serializer.dumps({"user": username})
        resp = RedirectResponse("/", status_code=302)
        resp.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax")
        return resp
    return templates.TemplateResponse(
        request, "login.html", {"error": "Неверный логин или пароль"}
    )


@app.get("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie(COOKIE_NAME)
    return resp


# ─── Список чатов ───────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not _is_authed(request):
        return _redirect_login()
    async with get_session() as session:
        chats = list(await session.scalars(select(Chat).order_by(Chat.title)))
    return templates.TemplateResponse(
        request, "index.html", {"chats": chats}
    )


# ─── Участники чата ─────────────────────────────────────────

@app.get("/chat/{chat_id}", response_class=HTMLResponse)
async def chat_view(request: Request, chat_id: int):
    if not _is_authed(request):
        return _redirect_login()
    async with get_session() as session:
        chat = await session.get(Chat, chat_id)
        rows = await session.execute(
            select(ChatMember, User)
            .join(User, User.id == ChatMember.user_id)
            .where(ChatMember.chat_id == chat_id)
            .order_by(ChatMember.points.desc())
        )
        members = [(m, u) for m, u in rows]
        items = list(
            await session.scalars(
                select(ShopItem).where(ShopItem.chat_id == chat_id)
            )
        )
    return templates.TemplateResponse(
        request,
        "chat.html",
        {"chat": chat, "members": members, "items": items},
    )


@app.post("/chat/{chat_id}/points")
async def update_points(
    request: Request,
    chat_id: int,
    user_id: int = Form(...),
    points: int = Form(...),
):
    if not _is_authed(request):
        return _redirect_login()
    async with get_session() as session:
        member = await session.scalar(
            select(ChatMember).where(
                ChatMember.chat_id == chat_id, ChatMember.user_id == user_id
            )
        )
        if member:
            member.points = points
            await session.commit()
    return RedirectResponse(f"/chat/{chat_id}", status_code=302)
