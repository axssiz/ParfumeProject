from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import psycopg2, bcrypt

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="supersecret")

templates = Jinja2Templates(directory="templates")

# Подключение к БД
conn = psycopg2.connect(
    dbname="perfume",
    user="postgres",
    password="1234",
    host="localhost",
    port="5432"
)
cur = conn.cursor()


# ---------------------- ДОМ -------------------------
@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": request.session.get("user")
    })


# ---------------------- РЕГИСТРАЦИЯ ----------------------
@app.get("/reg.html")
def reg_page(request: Request):
    return templates.TemplateResponse("reg.html", {"request": request})


@app.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):

    hash_pass = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    # по умолчанию роль client
    cur.execute(
        "INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)",
        (username, email, hash_pass, "client")
    )
    conn.commit()

    return RedirectResponse("/sign.html", status_code=303)


# ---------------------- ЛОГИН ----------------------
@app.get("/sign.html")
def login_page(request: Request):
    return templates.TemplateResponse("sign.html", {"request": request})


@app.post("/login")
def login_user(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):

    cur.execute("SELECT id, username, password, role FROM users WHERE email=%s", (email,))
    user = cur.fetchone()

    if not user:
        return RedirectResponse("/sign.html", status_code=303)

    user_id, username, hashed, role = user

    if not bcrypt.checkpw(password.encode(), hashed.encode()):
        return RedirectResponse("/sign.html", status_code=303)

    # сохраняем всё в сессию
    request.session["user"] = {
        "id": user_id,
        "name": username,
        "email": email,
        "role": role
    }

    return RedirectResponse("/", status_code=303)


# ---------------------- ВЫХОД ----------------------
@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


# ---------------------- ПРОФИЛЬ ---------------------
@app.get("/profile")
def profile(request: Request):
    user = request.session.get("user")

    if not user:
        return RedirectResponse("/sign.html", status_code=303)

    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": user
    })


# ---------------------- АДМИН: НАЗНАЧИТЬ РОЛЬ ----------------------
@app.post("/set_role")
def set_role(
    request: Request,
    user_id: int = Form(...),
    new_role: str = Form(...)
):

    current = request.session.get("user")
    if not current or current["role"] != "admin":
        return RedirectResponse("/", status_code=303)

    cur.execute("UPDATE users SET role=%s WHERE id=%s", (new_role, user_id))
    conn.commit()

    return RedirectResponse("/profile", status_code=303)
