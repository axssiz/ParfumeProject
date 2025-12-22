from fastapi import FastAPI, Request, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from typing import Optional, List
from collections import defaultdict
from itertools import combinations as iter_combinations
import uvicorn
import psycopg2
import bcrypt
import re
import httpx
import os
import json, time, uuid
import psycopg2.extras

from fastapi import status

# ======================
# --- Конфигурация ---
# ======================

# ВАЖНО: Замените своим ключом OpenRouter
OPENROUTER_KEY = "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" 
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openai/gpt-4o-mini"

DB_CONFIG = {
    "host": "localhost",
    "database": "perfume_db",
    "user": "postgres",
    "password": "Sula2206",
    "port": "5432",
}

# ==================================
# --- АРОМАТИЧЕСКАЯ КЛАССИФИКАЦИЯ НОТ (Расширена RU/EN) ---
# ==================================

# Словарь для классификации нот (корни слов) для умного поиска
NOTE_CLASSIFICATION = {
    # СЛАДКИЕ / ГУРМАНСКИЕ (RU/EN)
    "сладк": "Сладкий", "ванил": "Сладкий", "гурман": "Сладкий", "шоколад": "Сладкий", 
    "карамел": "Сладкий", "мед": "Сладкий", "пралин": "Сладкий", "кокос": "Сладкий",
    "бобы тонка": "Сладкий", "кориц": "Сладкий", "амбра": "Сладкий",
    "sweet": "Сладкий", "vanil": "Сладкий", "gourmand": "Сладкий", "chocola": "Сладкий", 
    "caramel": "Сладкий", "honey": "Сладкий", "praline": "Сладкий", "coconut": "Сладкий",
    "tonka": "Сладкий", "cinnamo": "Сладкий", "amber": "Сладкий",

    # ГОРЬКИЕ / ПРЯНЫЕ / КОФЕЙНЫЕ (RU/EN)
    "горьк": "Горький", "кофе": "Горький", "какао": "Горький", "перец": "Пряный", 
    "шафран": "Пряный", "кардам": "Пряный", "гвоздик": "Пряный", "мускат": "Пряный",
    "bitter": "Горький", "coffee": "Горький", "cacao": "Горький", "pepper": "Пряный", 
    "saffro": "Пряный", "cardamo": "Пряный", "clove": "Пряный", "nutmeg": "Пряный",
    
    # СВЕЖИЕ / ЦИТРУСОВЫЕ / ВОДНЫЕ (RU/EN)
    "свеж": "Свежий", "цитрус": "Свежий", "мандарин": "Свежий", "бергамот": "Свежий", 
    "лимон": "Свежий", "грейпфр": "Свежий", "морск": "Свежий", "водн": "Свежий",
    "fresh": "Свежий", "citrus": "Свежий", "mandari": "Свежий", "bergamot": "Свежий", 
    "lemon": "Свежий", "grapefr": "Свежий", "marine": "Свежий", "aquatic": "Свежий", 
    
    # ДРЕВЕСНЫЕ / ЗЕМЛИСТЫЕ (RU/EN)
    "древесн": "Древесный", "кедр": "Древесный", "сандал": "Древесный", "ветивер": "Древесный", 
    "пачули": "Древесный", "мох": "Древесный",
    "wood": "Древесный", "cedar": "Древесный", "sandal": "Древесный", "vetiver": "Древесный", 
    "patchouli": "Древесный", "moss": "Древесный",
    
    # КОЖАНЫЕ / МУСКУСНЫЕ (RU/EN)
    "кож": "Кожаный", "мускус": "Мускусный", "уд": "Древесный", "табак": "Кожаный",
    "leather": "Кожаный", "musk": "Мускусный", "oud": "Древесный", "tobacco": "Кожаный",
    
    # ЦВЕТОЧНЫЕ (RU/EN)
    "цветоч": "Цветочный", "роза": "Цветочный", "жасмин": "Цветочный", "фиалк": "Цветочный",
    "flower": "Цветочный", "rose": "Цветочный", "jasmin": "Цветочный", "violet": "Цветочный"
}

# ======================
# --- Инициализация FastAPI ---
# ======================

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="f9b8e2c1d4a5b6c7e8f9a0b1c2d3e4f5")
templates = Jinja2Templates(directory=".")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ==================================
# --- Подключение к БД (Исправлено) ---
# ==================================

conn = None
cur = None

try:
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()
    print("Подключение к БД успешно")

    # Создание таблиц (если нет)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        username VARCHAR(150) UNIQUE,
        email VARCHAR(255) UNIQUE,
        password VARCHAR(255) NOT NULL,
        role VARCHAR(20) DEFAULT 'client'
    )
    """)
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS parfumes(
        id SERIAL PRIMARY KEY,
        name TEXT,
        brand TEXT,
        description TEXT,
        price NUMERIC,
        volume_ml INTEGER,
        image_url TEXT,
        gender TEXT,
        features TEXT[] 
    )
    """)

    # orders table
    try:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS orders(
            id TEXT PRIMARY KEY,
            perfume JSONB,
            items JSONB,
            total_price NUMERIC,
            status VARCHAR(20),
            timestamp BIGINT,
            customer_phone TEXT,
            customer_email TEXT,
            customer_city TEXT
        )
        """)
        # ensure columns exist if table was created earlier
        cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_phone TEXT")
        cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_email TEXT")
        cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_city TEXT")
        cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_user_id INTEGER")
        cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_name TEXT")
        cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_comment TEXT")
        cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS items JSONB")
        cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS total_price NUMERIC")
        # ensure order_events table for logging status changes
        try:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS order_events(
                id SERIAL PRIMARY KEY,
                order_id TEXT,
                user_id INTEGER,
                event_type VARCHAR(50),
                event_meta JSONB,
                timestamp BIGINT
            )
            """)
        except Exception as e:
            print('Ошибка создания таблицы order_events:', e)
        # ensure order_num sequence/column for short numeric order ids
        try:
            cur.execute("CREATE SEQUENCE IF NOT EXISTS orders_order_num_seq START 1")
            cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS order_num BIGINT")
            cur.execute("ALTER SEQUENCE orders_order_num_seq OWNED BY orders.order_num")
            cur.execute("ALTER TABLE orders ALTER COLUMN order_num SET DEFAULT nextval('orders_order_num_seq')")
            # populate existing NULL order_num values
            cur.execute("UPDATE orders SET order_num = nextval('orders_order_num_seq') WHERE order_num IS NULL")
        except Exception as e:
            print('Ошибка настройки order_num sequence:', e)
    except Exception as e:
        print('Ошибка создания/обновления таблицы orders:', e)

    # cart_items table (корзина)
    try:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS cart_items(
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            parfume_id INTEGER,
            quantity INTEGER DEFAULT 1,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, parfume_id)
        )
        """)
    except Exception as e:
        print('Ошибка создания таблицы cart_items:', e)

    # ingredients table (for game / crafting)
    try:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS ingredients(
            code TEXT PRIMARY KEY,
            name TEXT,
            meta JSONB DEFAULT '{}'
        )
        """)
    except Exception as e:
        print('Ошибка создания таблицы ingredients:', e)

    # combinations table: maps unordered pair of ingredient codes to parfume id (nullable)
    try:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS combinations(
            id SERIAL PRIMARY KEY,
            ingredient1_code TEXT,
            ingredient2_code TEXT,
            parfume_id INTEGER REFERENCES parfumes(id),
            UNIQUE(ingredient1_code, ingredient2_code)
        )
        """)
    except Exception as e:
        print('Ошибка создания таблицы combinations:', e)

    # seed 7 ingredients (do not truncate existing data)
    

except Exception as e:
    print("Ошибка подключения к БД:", e)








# ======================
# --- Функции БД (Каталог) ---
# ======================

def fetch_parfumes(brands: Optional[List[str]], price_min: Optional[float],
                   
                   price_max: Optional[float], sort_by: str):
    if cur is None: return []
    sql_query = """
        SELECT id, name, brand, description, price, volume_ml, image_url, gender
        FROM parfumes
    """
    where_clauses = []
    params = []

    if brands:
        placeholders = ','.join(['%s'] * len(brands))
        where_clauses.append(f"brand IN ({placeholders})")
        params.extend(brands)
    if price_min is not None:
        where_clauses.append("price >= %s"); params.append(price_min)
    if price_max is not None:
        where_clauses.append("price <= %s"); params.append(price_max)
    if where_clauses: sql_query += " WHERE " + " AND ".join(where_clauses)

    order_map = {
        "price_asc": " ORDER BY price ASC",
        "price_desc": " ORDER BY price DESC",
        "name_asc": " ORDER BY name ASC"
    }
    sql_query += order_map.get(sort_by, " ORDER BY id ASC")

    try:
        cur.execute(sql_query, tuple(params))
        rows = cur.fetchall()
        return [
            {
                "id": r[0], "name": r[1], "brand": r[2], "description": r[3],
                "price": float(r[4]) if r[4] is not None else None,
                "volume_ml": r[5], "image_url": r[6], "gender": r[7],
            } for r in rows
        ]
    except Exception as e:
        print("Ошибка при fetch_parfumes:", e)
        return []

# ============================================
# --- ПОДЗАПРОСЫ БД (2 шт) ---
# ============================================

def get_brands_with_stats(limit: int = 10):
    """
    ПОДЗАПРОС 1: Получить топ брендов с количеством товаров и средней ценой
    Использует: GROUP BY и агрегирующие функции COUNT, AVG
    """
    if cur is None:
        return []
    
    try:
        sql = """
        SELECT 
            brand,
            COUNT(*) as product_count,
            ROUND(AVG(price)::NUMERIC, 2) as avg_price
        FROM parfumes
        WHERE brand IS NOT NULL
        GROUP BY brand
        ORDER BY COUNT(*) DESC
        LIMIT %s
        """
        cur.execute(sql, (limit,))
        rows = cur.fetchall()
        
        return [
            {
                "brand": r[0],
                "product_count": r[1],
                "avg_price": float(r[2]) if r[2] else 0
            }
            for r in rows
        ]
    except Exception as e:
        print("Ошибка при get_brands_with_stats:", e)
        return []

def get_user_cart_total(user_id: int):
    """
    ПОДЗАПРОС 2: Получить корзину пользователя с расчетом стоимости
    Использует: JOIN, GROUP BY, агрегирующую функцию SUM
    """
    if cur is None:
        return None
    
    try:
        sql = """
        SELECT 
            COUNT(*) as items_count,
            ROUND(SUM(p.price * c.quantity)::NUMERIC, 2) as total_price
        FROM cart_items c
        LEFT JOIN parfumes p ON c.parfume_id = p.id
        WHERE c.user_id = %s
        """
        cur.execute(sql, (user_id,))
        row = cur.fetchone()
        
        if row:
            return {
                "items_count": row[0] or 0,
                "total_price": float(row[1]) if row[1] else 0
            }
        return None
    except Exception as e:
        print("Ошибка при get_user_cart_total:", e)
        return None

# =================================================
# --- ЧАТ-БОТ (Логика парсинга и умного поиска) ---
# =================================================

def parse_user_preferences(text: str):
    """Парсит текст пользователя на ключевые слова, цену и определяет основную категорию аромата."""
    text = text.lower()
    
    # 1. Определяем категорию, которую ищет пользователь
    aroma_category = "Общий"
    detected_keywords = []
    
    # Используем ключи из словаря классификации как поисковые слова
    for root, category in NOTE_CLASSIFICATION.items():
        if root in text:
            # Добавляем корень (бергамот)
            detected_keywords.append(root)
            # Присваиваем категорию по первому совпадению
            if aroma_category == "Общий" and category != "Общий": 
                aroma_category = category
    
    # 2. Поиск ценового лимита
    price_limit = None
    # Удаляем не-цифры (кроме пробелов) и текстовые обозначения тенге, чтобы найти число
    cleaned_text = re.sub(r'[^\d\s]', '', text.replace("тг", " ").replace("тенге", " "))
    price_matches = re.findall(r'\b\d{3,7}\b', cleaned_text) # Ищем числа от 3 до 7 цифр
    if price_matches:
        try: price_limit = int(price_matches[-1]) # Берем последнее найденное число как лимит
        except: pass

    # 3. Добавляем общие поисковые слова (бренд, название), если категория не определена
    if aroma_category == "Общий":
        common_words = text.split()
        for word in common_words:
            if len(word) > 2 and word not in detected_keywords:
                 detected_keywords.append(word)

    return detected_keywords, price_limit, aroma_category

def search_perfumes_for_bot(keywords: List[str], price_limit: Optional[int], category: str):
    """
    Умный поиск для бота. 
    Ищет по ключевым словам ИЛИ по цене, если ключевых слов нет.
    """
    if cur is None: return []

    # Используем только те ключевые слова (корни), которые были найдены в ИСХОДНОМ запросе.
    search_roots = list(set(keywords))
    
    # Если нет ни ключевых слов, ни ценового лимита — нет критериев для поиска.
    if not search_roots and not price_limit:
        return [] 
    
    sql = "SELECT name, brand, price, gender, description FROM parfumes WHERE 1=1"
    params = []

    # 1. Добавление фильтра по ключевым словам (нотам/брендам)
    if search_roots:
        like_conditions = []
        for root in search_roots:
            # Ищем совпадения корня ноты в названии, бренде или описании
            like_conditions.append("(name ILIKE %s OR brand ILIKE %s OR description ILIKE %s)")
            root_param = f"%{root}%"
            params.extend([root_param, root_param, root_param])
            
        sql += " AND (" + " OR ".join(like_conditions) + ")"
    
    # 2. Добавление фильтра по цене
    if price_limit:
        sql += " AND price <= %s"
        params.append(price_limit)

    sql += " ORDER BY price ASC LIMIT 8"

    try:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        
        # *** Исправление для запросов ТОЛЬКО по цене (например, "до 10000тг") ***
        # Если поиск по корням + цене ничего не дал, но цена была указана, 
        # и при этом не было найдено корней (пользователь ввел только число),
        # то выполняем поиск только по цене, чтобы найти все дешевые товары.
        if not rows and price_limit and not search_roots:
             # Повторный поиск только по цене, без LIKE-условий
             sql_only_price = "SELECT name, brand, price, gender, description FROM parfumes WHERE price <= %s ORDER BY price ASC LIMIT 8"
             cur.execute(sql_only_price, (price_limit,))
             rows = cur.fetchall()
        
        return [
            {"name": r[0], "brand": r[1], "price": float(r[2]) if r[2] else 0, "gender": r[3], "description": r[4]}
            for r in rows
        ]
    except Exception as e:
        print(f"Ошибка поиска SQL бота: {e}")
        return []

def build_ai_context(perfumes):
    if not perfumes:
        return "В базе данных по запросу ничего не найдено. Посоветуй что-то общее."
    text = "Найденные товары в магазине:\n"
    for p in perfumes:
        desc = p['description'][:100] if p['description'] else "Нет описания"
        text += f"- {p['brand']} {p['name']} ({p['gender']}): {p['price']} тг. Инфо: {desc}...\n"
    return text

async def ask_ai(user_message: str, db_context: str):
    """Асинхронный запрос к OpenRouter."""
    system_prompt = (
        "Ты — консультант магазина парфюмерии. Твоя цель — помочь выбрать аромат из списка. "
        "1. Опирайся ТОЛЬКО на список 'Найденные товары'. "
        "2. Если товары есть, порекомендуй 2-3 варианта, укажи цену. "
        "3. Если список пуст, предложи поискать по другим критериям. "
        "4. Отвечай кратко и вежливо. Используй русский язык."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Запрос: {user_message}\n\n{db_context}"}
    ]

    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5049",
        "X-Title": "PerfumeBot"
    }
    
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "max_tokens": 600
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(OPENROUTER_URL, json=payload, headers=headers)
            if response.status_code != 200:
                print(f"Ошибка AI API: {response.status_code} - {response.text}")
                return "Извините, сервис временно недоступен или API-ключ недействителен."
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Exception AI: {e}")
        return "Ошибка соединения с помощником."

@app.post("/chatbot")
async def chatbot_api(message: str = Form(...)):
    if cur is None:
        return JSONResponse({"reply": "Извините, эксперт не может работать из-за проблем с базой данных."}, status_code=500)

    # Используем логику парсинга
    keywords, price_limit, category = parse_user_preferences(message)
    
    # Используем исправленную логику поиска
    perfumes = search_perfumes_for_bot(keywords, price_limit, category)
    
    context = build_ai_context(perfumes)
    reply = await ask_ai(message, context)
    return JSONResponse({"reply": reply})

# ======================
# --- Маршруты страниц ---
# ======================

@app.get("/analytics.html", response_class=HTMLResponse)
@app.get("/analytics", response_class=HTMLResponse)
def analytics_page(request: Request):
    """Страница аналитики по брендам с сложным подзапросом #1"""
    return templates.TemplateResponse("analytics.html", {"request": request, "user": request.session.get("user")})

@app.get("/recommendations.html", response_class=HTMLResponse)
@app.get("/recommendations", response_class=HTMLResponse)
def recommendations_page(request: Request):
    """Страница персональных рекомендаций со сложным подзапросом #2"""
    return templates.TemplateResponse("recommendations.html", {"request": request, "user": request.session.get("user")})

@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
def home_page(request: Request):
    user = request.session.get("user")
    if user and isinstance(user, dict) and cur:
        try:
            cur.execute("SELECT role FROM users WHERE id=%s", (user.get("id"),))
            r = cur.fetchone()
            if r:
                user['role'] = r[0]
                request.session["user"] = user
                request.session["role"] = r[0]
        except: pass
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/index2.html", response_class=HTMLResponse)
@app.get("/catalog", response_class=HTMLResponse)
def catalog(
    request: Request,
    brands: Optional[List[str]] = Query(None),
    price_min: Optional[float] = Query(None, alias="price_min"),
    price_max: Optional[float] = Query(None, alias="price_max"),
    sort_by: str = Query("id_asc"),
):
    parfumes_list = fetch_parfumes(brands, price_min, price_max, sort_by)
    
    brands_grouped = defaultdict(list)
    if cur:
        try:
            cur.execute("SELECT DISTINCT brand FROM parfumes WHERE brand IS NOT NULL ORDER BY brand")
            for r in cur.fetchall():
                b = r[0]
                if b: brands_grouped[b[0].upper()].append(b)
        except Exception as e:
            print("Ошибка брендов:", e)

    return templates.TemplateResponse("index2.html", {
        "request": request,
        "parfumes": parfumes_list,
        "brands_grouped": brands_grouped,
        "selected_brands": request.query_params.getlist("brands"),
        "current_sort": sort_by,
        "price_min": price_min,
        "price_max": price_max,
        "user": request.session.get("user")
    })

@app.get("/search")
def search_ajax(q: str = Query(...)):
    if cur is None:
        return JSONResponse({"products": [], "brands": []}, status_code=500)
    try:
        # поиск по названию товаров
        cur.execute("SELECT id, name, image_url, price FROM parfumes WHERE name ILIKE %s LIMIT 10", (f"%{q}%",))
        prod_rows = cur.fetchall()
        products = [{"id": r[0], "name": r[1], "image": r[2], "price": r[3]} for r in prod_rows]

        # поиск по брендам (уникальные значения)
        try:
            cur.execute("SELECT DISTINCT brand FROM parfumes WHERE brand ILIKE %s ORDER BY brand LIMIT 8", (f"%{q}%",))
            brand_rows = cur.fetchall()
            brands = [r[0] for r in brand_rows if r[0]]
        except Exception:
            brands = []

        return JSONResponse({"products": products, "brands": brands})
    except Exception as e:
        print('search_ajax error:', e)
        return JSONResponse({"products": [], "brands": []}, status_code=500)

@app.get("/products", response_class=HTMLResponse)
def get_products_partial(
    request: Request,
    brands: Optional[List[str]] = Query(None),
    price_min: Optional[float] = Query(None, alias="price_min"),
    price_max: Optional[float] = Query(None, alias="price_max"),
    sort_by: str = Query("id_asc"),
):
    parfumes_list = fetch_parfumes(brands, price_min, price_max, sort_by)
    return templates.TemplateResponse("products_partial.html", {"request": request, "parfumes": parfumes_list})


# ========================
# --- API для корзины ---
# ========================

@app.post("/api/cart/add")
async def add_to_cart(request: Request, parfume_id: int = Form(...), quantity: int = Form(1)):
    """Добавить товар в корзину (для авторизованных пользователей)"""
    user = request.session.get("user")
    if not user or not user.get("id"):
        return JSONResponse({"ok": False, "msg": "Не авторизованы"}, status_code=401)
    
    user_id = user.get("id")
    if cur is None:
        return JSONResponse({"ok": False, "msg": "БД недоступна"}, status_code=500)
    
    try:
        # Проверяем, существует ли товар в корзине
        cur.execute("SELECT id, quantity FROM cart_items WHERE user_id=%s AND parfume_id=%s", (user_id, parfume_id))
        existing = cur.fetchone()
        
        if existing:
            # Обновляем количество
            new_qty = existing[1] + quantity
            cur.execute("UPDATE cart_items SET quantity=%s WHERE id=%s", (new_qty, existing[0]))
        else:
            # Добавляем новый товар
            cur.execute("INSERT INTO cart_items (user_id, parfume_id, quantity) VALUES (%s, %s, %s)", 
                       (user_id, parfume_id, quantity))
        
        return JSONResponse({"ok": True, "msg": "Добавлено в корзину"})
    except Exception as e:
        print('add_to_cart error:', e)
        return JSONResponse({"ok": False, "msg": str(e)}, status_code=500)

@app.get("/api/cart")
async def get_cart(request: Request):
    """Получить все товары из корзины пользователя"""
    user = request.session.get("user")
    if not user or not user.get("id"):
        return JSONResponse({"items": []})
    
    user_id = user.get("id")
    if cur is None:
        return JSONResponse({"items": []}, status_code=500)
    
    try:
        cur.execute("""
            SELECT c.id, c.parfume_id, c.quantity, p.name, p.brand, p.price, p.image_url
            FROM cart_items c
            LEFT JOIN parfumes p ON c.parfume_id = p.id
            WHERE c.user_id=%s
            ORDER BY c.added_at DESC
        """, (user_id,))
        
        rows = cur.fetchall()
        items = [
            {
                "cart_id": r[0],
                "parfume_id": r[1],
                "quantity": r[2],
                "name": r[3],
                "brand": r[4],
                "price": float(r[5]) if r[5] else 0,
                "image_url": r[6]
            }
            for r in rows
        ]
        
        total = sum(item["price"] * item["quantity"] for item in items)
        return JSONResponse({"items": items, "total": total})
    except Exception as e:
        print('get_cart error:', e)
        return JSONResponse({"items": []}, status_code=500)

@app.post("/api/cart/remove")
async def remove_from_cart(request: Request, cart_id: int = Form(...)):
    """Удалить товар из корзины"""
    user = request.session.get("user")
    if not user or not user.get("id"):
        return JSONResponse({"ok": False}, status_code=401)
    
    user_id = user.get("id")
    if cur is None:
        return JSONResponse({"ok": False}, status_code=500)
    
    try:
        # Проверяем, что товар принадлежит пользователю
        cur.execute("SELECT id FROM cart_items WHERE id=%s AND user_id=%s", (cart_id, user_id))
        if not cur.fetchone():
            return JSONResponse({"ok": False, "msg": "Товар не найден"}, status_code=404)
        
        cur.execute("DELETE FROM cart_items WHERE id=%s", (cart_id,))
        return JSONResponse({"ok": True})
    except Exception as e:
        print('remove_from_cart error:', e)
        return JSONResponse({"ok": False}, status_code=500)

@app.post("/api/cart/update")
async def update_cart_qty(request: Request, cart_id: int = Form(...), quantity: int = Form(1)):
    """Обновить количество товара в корзине"""
    user = request.session.get("user")
    if not user or not user.get("id"):
        return JSONResponse({"ok": False}, status_code=401)
    
    user_id = user.get("id")
    if cur is None:
        return JSONResponse({"ok": False}, status_code=500)
    
    try:
        cur.execute("SELECT id FROM cart_items WHERE id=%s AND user_id=%s", (cart_id, user_id))
        if not cur.fetchone():
            return JSONResponse({"ok": False}, status_code=404)
        
        if quantity <= 0:
            cur.execute("DELETE FROM cart_items WHERE id=%s", (cart_id,))
        else:
            cur.execute("UPDATE cart_items SET quantity=%s WHERE id=%s", (quantity, cart_id))
        
        return JSONResponse({"ok": True})
    except Exception as e:
        print('update_cart_qty error:', e)
        return JSONResponse({"ok": False}, status_code=500)

@app.get("/cart", response_class=HTMLResponse)
def cart_page(request: Request):
    """Страница корзины"""
    user = request.session.get("user")
    return templates.TemplateResponse("cart.html", {"request": request, "user": user})


# ------------------ orders API (DB-backed, fallback to file) ------------------
def _orders_fallback_file():
    # simple fallback when DB not available
    f = 'orders.json'
    try:
        if not os.path.exists(f):
            return []
        with open(f, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return []

def _orders_fallback_save(orders):
    f = 'orders.json'
    with open(f, 'w', encoding='utf-8') as fh:
        json.dump(orders, fh, ensure_ascii=False, indent=2)

def _orders_fallback_nextnum():
    orders = _orders_fallback_file()
    if not orders:
        return 1
    try:
        nums = [int(o.get('order_num') or 0) for o in orders]
        return max(nums) + 1
    except Exception:
        return len(orders) + 1


def _events_fallback_file():
    f = 'events.json'
    try:
        if not os.path.exists(f):
            return []
        with open(f, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return []


def _events_fallback_save(events):
    f = 'events.json'
    with open(f, 'w', encoding='utf-8') as fh:
        json.dump(events, fh, ensure_ascii=False, indent=2)


def _generate_sms_code(length=6):
    import random
    start = 10**(length-1)
    return str(random.randint(start, 10**length - 1))


def send_sms_via_twilio(to_number: str, message: str):
    sid = os.environ.get('TWILIO_SID')
    token = os.environ.get('TWILIO_TOKEN')
    from_num = os.environ.get('TWILIO_FROM')
    if not (sid and token and from_num):
        print('Twilio not configured; SMS not sent. Would send to', to_number, 'message:', message)
        return False
    url = f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json'
    data = {'To': to_number, 'From': from_num, 'Body': message}
    try:
        resp = httpx.post(url, data=data, auth=(sid, token), timeout=10.0)
        if resp.status_code in (200, 201):
            return True
        print('Twilio send failed', resp.status_code, resp.text)
    except Exception as e:
        print('Twilio exception', e)
    return False

# SMS functionality removed — alias stubs to avoid import errors
def _generate_sms_code(*a, **k):
    raise RuntimeError('SMS flow disabled')

def send_sms_via_twilio(*a, **k):
    print('SMS disabled — not sending')
    return False


@app.post('/api/add_to_cart')
async def add_cart_item(request: Request):
    session_user = request.session.get("user")
    if not session_user:
        return JSONResponse(
        {"ok": False, "error": "login_required"},
        status_code=401
    )

    payload = await request.json()
    perfume = payload.get('perfume') or {}
    customer_name = payload.get('customer_name') or ''
    customer_phone = payload.get('customer_phone') or payload.get('phone') or ''
    customer_email = payload.get('customer_email') or payload.get('email') or ''
    customer_city = payload.get('customer_city') or payload.get('city') or ''
    customer_comment = payload.get('customer_comment') or ''
    order_id = str(uuid.uuid4())
    ts = int(time.time())
    # determine user id from session or by email
    session_user = request.session.get('user') if hasattr(request, 'session') else None
    user_id = session_user.get('id') if session_user else None
    # require login to create orders
    if not session_user:
        return JSONResponse({'ok': False, 'error': 'login_required'}, status_code=401)
    print(f'[add_cart_item] session_user={session_user}, user_id={user_id}, customer_email={customer_email}')
    if cur:
        try:
            print(f'[add_cart_item] Final user_id before insert: {user_id}')
            cur.execute(
                "INSERT INTO orders (id, perfume, status, timestamp, customer_name, customer_phone, customer_email, customer_city, customer_comment, customer_user_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING order_num",
                (order_id, psycopg2.extras.Json(perfume), 'awaiting_confirmation', ts, customer_name, customer_phone, customer_email, customer_city, customer_comment, user_id)
            )
            row = cur.fetchone()
            order_num = row[0] if row else None
            print(f'[add_cart_item] Order created: id={order_id}, order_num={order_num}, user_id={user_id}')
            try:
                cur.execute("INSERT INTO order_events (order_id, user_id, event_type, event_meta, timestamp) VALUES (%s,%s,%s,%s,%s)", (order_id, user_id, 'created', psycopg2.extras.Json({'customer_name': customer_name, 'customer_email': customer_email}), int(time.time())))
            except Exception as ee:
                print('event insert error on create', ee)
            return JSONResponse({'ok': True, 'order': {'id': order_id, 'order_num': order_num, 'perfume': perfume, 'status': 'awaiting_confirmation', 'timestamp': ts, 'customer_name': customer_name, 'customer_phone': customer_phone, 'customer_email': customer_email, 'customer_city': customer_city, 'customer_comment': customer_comment, 'customer_user_id': user_id}})
        except Exception as e:
            print(f'[add_cart_item] DB add order error: {e}')
            # fallback to file
    # fallback
    # require login even for fallback
    session_user_fb = request.session.get('user') if hasattr(request, 'session') else None
    if not session_user_fb:
        return JSONResponse({'ok': False, 'error': 'login_required'}, status_code=401)
    orders = _orders_fallback_file()
    order_num = _orders_fallback_nextnum()
    # fallback user_id from session (must exist)
    fallback_user_id = session_user_fb.get('id')
    order = {'id': order_id, 'order_num': order_num, 'perfume': perfume, 'status': 'awaiting_confirmation', 'timestamp': ts, 'customer_name': customer_name, 'customer_phone': customer_phone, 'customer_email': customer_email, 'customer_city': customer_city, 'customer_comment': customer_comment, 'customer_user_id': fallback_user_id}
    orders.insert(0, order)
    orders = orders[:200]
    _orders_fallback_save(orders)
    try:
        events = _events_fallback_file()
        events.insert(0, {'order_id': order_id, 'user_id': fallback_user_id, 'event_type': 'created', 'event_meta': {'customer_name': customer_name, 'customer_email': customer_email}, 'timestamp': int(time.time())})
        _events_fallback_save(events)
    except Exception as e:
        print('fallback event save error', e)
    return JSONResponse({'ok': True, 'order': order})


@app.post('/api/create_order')
async def create_order(request: Request):
    """Create an order from current user's cart items.
    Expects JSON body with optional customer_name, customer_phone, customer_email, customer_city, customer_comment.
    """
    session_user = request.session.get('user') if hasattr(request, 'session') else None
    if not session_user:
        return JSONResponse({'ok': False, 'error': 'login_required'}, status_code=401)
    user_id = session_user.get('id')
    payload = await request.json()
    customer_name = payload.get('customer_name') or session_user.get('username') or ''
    customer_phone = payload.get('customer_phone') or ''
    customer_email = payload.get('customer_email') or ''
    customer_city = payload.get('customer_city') or ''
    customer_comment = payload.get('customer_comment') or ''
    order_id = str(uuid.uuid4())
    ts = int(time.time())

    # fetch cart items
    try:
        if not cur:
            raise Exception('DB not available')
        cur.execute("""
            SELECT c.parfume_id, c.quantity, p.name, p.brand, p.price, p.image_url
            FROM cart_items c
            LEFT JOIN parfumes p ON c.parfume_id = p.id
            WHERE c.user_id=%s
        """, (user_id,))
        rows = cur.fetchall()
        if not rows:
            return JSONResponse({'ok': False, 'error': 'cart_empty'}, status_code=400)
        items = []
        total = 0
        for r in rows:
            pid, qty, name, brand, price, image = r
            price_f = float(price) if price is not None else 0.0
            items.append({'id': pid, 'name': name, 'brand': brand, 'price': price_f, 'image_url': image, 'quantity': qty})
            total += price_f * int(qty)

        # create order row
        cur.execute(
            "INSERT INTO orders (id, perfume, items, total_price, status, timestamp, customer_name, customer_phone, customer_email, customer_city, customer_comment, customer_user_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING order_num",
            (order_id, psycopg2.extras.Json(items[0] if items else None), psycopg2.extras.Json(items), total, 'pending', ts, customer_name, customer_phone, customer_email, customer_city, customer_comment, user_id)
        )
        row = cur.fetchone()
        order_num = row[0] if row else None
        # clear cart
        try:
            cur.execute("DELETE FROM cart_items WHERE user_id=%s", (user_id,))
        except Exception:
            pass
        try:
            cur.execute("INSERT INTO order_events (order_id, user_id, event_type, event_meta, timestamp) VALUES (%s,%s,%s,%s,%s)", (order_id, user_id, 'created', psycopg2.extras.Json({'customer_name': customer_name}), int(time.time())))
        except Exception as ee:
            print('event insert error on create', ee)
        return JSONResponse({'ok': True, 'order': {'id': order_id, 'order_num': order_num, 'items': items, 'total_price': total, 'status': 'pending', 'timestamp': ts, 'customer_name': customer_name, 'customer_phone': customer_phone, 'customer_email': customer_email, 'customer_city': customer_city, 'customer_comment': customer_comment, 'customer_user_id': user_id}})
    except Exception as e:
        print('[create_order] error:', e)
    # fallback to file fallback when DB not available
    orders = _orders_fallback_file()
    order_num = _orders_fallback_nextnum()
    # try to read cart items from DB fallback not possible — create a single placeholder item
    items = payload.get('items') or []
    total = payload.get('total_price') or sum((i.get('price',0) * i.get('quantity',1) for i in items))
    order = {'id': order_id, 'order_num': order_num, 'items': items, 'total_price': total, 'status': 'pending', 'timestamp': ts, 'customer_name': customer_name, 'customer_phone': customer_phone, 'customer_email': customer_email, 'customer_city': customer_city, 'customer_comment': customer_comment, 'customer_user_id': user_id}
    orders.insert(0, order)
    orders = orders[:200]
    _orders_fallback_save(orders)
    try:
        events = _events_fallback_file()
        events.insert(0, {'order_id': order_id, 'user_id': user_id, 'event_type': 'created', 'event_meta': {'customer_name': customer_name}, 'timestamp': int(time.time())})
        _events_fallback_save(events)
    except Exception as e:
        print('fallback event save error', e)
    return JSONResponse({'ok': True, 'order': order})


@app.get('/api/orders')
async def get_orders():
    if cur:
        try:
            cur.execute("SELECT id, order_num, perfume, items, total_price, status, timestamp, customer_name, customer_phone, customer_email, customer_city, customer_comment, customer_user_id FROM orders WHERE status NOT IN ('delivered', 'cancelled') ORDER BY timestamp DESC LIMIT 200")
            rows = cur.fetchall()
            out = []
            for r in rows:
                out.append({'id': r[0], 'order_num': r[1], 'perfume': r[2], 'items': r[3], 'total_price': float(r[4]) if r[4] is not None else 0, 'status': r[5], 'timestamp': r[6], 'customer_name': r[7], 'customer_phone': r[8], 'customer_email': r[9], 'customer_city': r[10], 'customer_comment': r[11], 'customer_user_id': r[12]})
            return JSONResponse({'orders': out})
        except Exception as e:
            print('DB get orders error:', e)
    # fallback
    orders = _orders_fallback_file()
    filtered = [o for o in orders if o.get('status') not in ('delivered', 'cancelled')]
    return JSONResponse({'orders': filtered})


@app.post('/api/orders/{order_id}/ack')
async def ack_order(order_id: str, request: Request):
    session_user = request.session.get('user') if hasattr(request, 'session') else None
    user_id = session_user.get('id') if session_user else None
    if cur:
        try:
            cur.execute("UPDATE orders SET status=%s WHERE id=%s", ('ack', order_id))
            if cur.rowcount > 0:
                try:
                    cur.execute("INSERT INTO order_events (order_id, user_id, event_type, event_meta, timestamp) VALUES (%s,%s,%s,%s,%s)", (order_id, user_id, 'ack', psycopg2.extras.Json({}), int(time.time())))
                except Exception as ee:
                    print('event insert error on ack', ee)
                return JSONResponse({'ok': True})
            return JSONResponse({'ok': False, 'error': 'not found'}, status_code=404)
        except Exception as e:
            print('DB ack error:', e)
    # fallback
    orders = _orders_fallback_file()
    changed = False
    for o in orders:
        if o.get('id') == order_id:
            o['status'] = 'ack'
            changed = True
            break
    if changed:
        _orders_fallback_save(orders)
        try:
            events = _events_fallback_file()
            events.insert(0, {'order_id': order_id, 'user_id': user_id, 'event_type': 'ack', 'event_meta': {}, 'timestamp': int(time.time())})
            _events_fallback_save(events)
        except Exception as e:
            print('fallback ack event save error', e)
        return JSONResponse({'ok': True})
    return JSONResponse({'ok': False, 'error': 'not found'}, status_code=404)


@app.post('/api/orders/{order_id}/status')
async def set_order_status(order_id: str, request: Request):
    payload = await request.json()
    status = payload.get('status')
    if not status:
        return JSONResponse({'ok': False, 'error': 'missing status'}, status_code=400)
    # normalize/validate status
    ALLOWED_STATUSES = {'pending','confirmed','in_progress','shipped','delivered','cancelled','ack','awaiting_confirmation','in_processing','sent','new'}
    if status not in ALLOWED_STATUSES:
        return JSONResponse({'ok': False, 'error': 'invalid status'}, status_code=400)
    # map legacy synonyms to canonical ones for clarity
    STATUS_MAP = {
        'awaiting_confirmation':'pending',
        'in_processing':'in_progress',
        'sent':'shipped',
        'new':'pending',
        'ack':'in_progress'
    }
    status = STATUS_MAP.get(status, status)
    session_user = request.session.get('user') if hasattr(request, 'session') else None
    session_user_id = session_user.get('id') if session_user else None
    if cur:
        try:
            # set status directly; SMS flow removed — worker may set awaiting_confirmation, client will confirm via profile button
            cur.execute("""
                UPDATE orders SET status=%s WHERE id=%s RETURNING id, order_num, perfume, status, timestamp, customer_phone, customer_email, customer_city, customer_user_id
            """, (status, order_id))
            row = cur.fetchone()
            if row:
                o = {'id': row[0], 'order_num': row[1], 'perfume': row[2], 'status': row[3], 'timestamp': row[4], 'customer_phone': row[5], 'customer_email': row[6], 'customer_city': row[7], 'customer_user_id': row[8]}
                try:
                    cur.execute("INSERT INTO order_events (order_id, user_id, event_type, event_meta, timestamp) VALUES (%s,%s,%s,%s,%s)", (order_id, session_user_id, status, psycopg2.extras.Json({}), int(time.time())))
                except Exception as ee:
                    print('event insert error on set_status', ee)
                return JSONResponse({'ok': True, 'order': o})
            return JSONResponse({'ok': False, 'error': 'not found'}, status_code=404)
        except Exception as e:
            print('DB set status error:', e)
    # fallback to file
    orders = _orders_fallback_file()
    changed = False
    out = None
    for o in orders:
        if o.get('id') == order_id:
            o['status'] = status
            changed = True
            out = o
            break
    if changed:
        _orders_fallback_save(orders)
        try:
            events = _events_fallback_file()
            events.insert(0, {'order_id': order_id, 'user_id': session_user_id, 'event_type': status, 'event_meta': {}, 'timestamp': int(time.time())})
            _events_fallback_save(events)
        except Exception as e:
            print('fallback status event save error', e)
        return JSONResponse({'ok': True, 'order': out})
    return JSONResponse({'ok': False, 'error': 'not found'}, status_code=404)


@app.post('/api/orders/{order_id}/confirm')
async def confirm_order(order_id: str, request: Request):
    # client confirmation endpoint — only order owner can confirm when status awaiting_confirmation
    session_user = request.session.get('user') if hasattr(request, 'session') else None
    if cur:
        try:
            # check ownership and current status
            cur.execute("SELECT customer_user_id, status FROM orders WHERE id=%s", (order_id,))
            row = cur.fetchone()
            if not row:
                return JSONResponse({'ok': False, 'error': 'not found'}, status_code=404)
            owner_id, status = row[0], row[1]
            # verify session user
            if not session_user or not session_user.get('id') or not owner_id or int(session_user.get('id')) != int(owner_id):
                return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
            if status != 'awaiting_confirmation':
                return JSONResponse({'ok': False, 'error': 'invalid status'}, status_code=400)
            # set confirmed and log event
            cur.execute("UPDATE orders SET status=%s WHERE id=%s RETURNING id, order_num, status", ('confirmed', order_id))
            r = cur.fetchone()
            if r:
                try:
                    cur.execute("INSERT INTO order_events (order_id, user_id, event_type, event_meta, timestamp) VALUES (%s, %s, %s, %s, %s)", (order_id, session_user.get('id'), 'confirmed', psycopg2.extras.Json({'by':'client'}), int(time.time())))
                except Exception as ee:
                    print('event insert error', ee)
                return JSONResponse({'ok': True, 'order': {'id': r[0], 'order_num': r[1], 'status': r[2]}})
            return JSONResponse({'ok': False, 'error': 'not found'}, status_code=404)
        except Exception as e:
            print('DB confirm error:', e)
    # fallback
    orders = _orders_fallback_file()
    session_id = session_user.get('id') if session_user else None
    events = _events_fallback_file()
    for o in orders:
        if o.get('id') == order_id:
            if o.get('customer_user_id') and session_id and int(o.get('customer_user_id')) == int(session_id):
                if o.get('status') != 'awaiting_confirmation':
                    return JSONResponse({'ok': False, 'error': 'invalid status'}, status_code=400)
                o['status'] = 'confirmed'
                events.insert(0, {'order_id': order_id, 'user_id': session_id, 'event_type': 'confirmed', 'event_meta': {}, 'timestamp': int(time.time())})
                _orders_fallback_save(orders)
                _events_fallback_save(events)
                return JSONResponse({'ok': True, 'order': o})
            return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    return JSONResponse({'ok': False, 'error': 'not found'}, status_code=404)


@app.get('/api/my_orders')
async def my_orders(request: Request):
    session_user = request.session.get('user') if hasattr(request, 'session') else None
    if not session_user:
        return JSONResponse({'active': [], 'finished': []})
    user_id = session_user.get('id')
    try:
        if cur:
            cur.execute("SELECT id, order_num, perfume, items, total_price, status, timestamp, customer_name, customer_phone, customer_email, customer_city, customer_comment FROM orders WHERE customer_user_id=%s ORDER BY timestamp DESC", (user_id,))
            rows = cur.fetchall()
            active = []
            finished = []
            # classify by status
            ACTIVE_STATUSES = set(['processing','in_processing','awaiting_confirmation','sent','shipped','new','confirmed'])
            FINISHED_STATUSES = set(['delivered','cancelled'])
            for r in rows:
                o = {'id': r[0], 'order_num': r[1], 'perfume': r[2], 'items': r[3], 'total_price': float(r[4]) if r[4] is not None else 0, 'status': r[5], 'timestamp': r[6], 'customer_name': r[7], 'customer_phone': r[8], 'customer_email': r[9], 'customer_city': r[10], 'customer_comment': r[11]}
                st = (o.get('status') or '').lower()
                if st in FINISHED_STATUSES:
                    finished.append(o)
                else:
                    # treat known active statuses as active, default to active
                    active.append(o)
            return JSONResponse({'active': active, 'finished': finished})
    except Exception as e:
        print('DB my_orders error:', e)
    # fallback: filter by customer_user_id or customer_email
    orders = _orders_fallback_file()
    active=[]; finished=[]
    for o in orders:
        if o.get('customer_user_id') and user_id and int(o.get('customer_user_id'))==int(user_id):
            if o.get('status') in ('delivered', 'cancelled'): finished.append(o)
            else: active.append(o)
    return JSONResponse({'active': active, 'finished': finished})

@app.get("/big/{parfum_id}", response_class=HTMLResponse)
def product_card(request: Request, parfum_id: int):
    if cur is None: return HTMLResponse("DB Error", 500)
    cur.execute("""
        SELECT id, name, brand, description, price, volume_ml, image_url, gender 
        FROM parfumes WHERE id=%s
    """, (parfum_id,))
    row = cur.fetchone()
    if not row: return HTMLResponse("Not Found", 404)
    
    p = {
        "id": row[0], "name": row[1], "brand": row[2], "description": row[3],
        "price": row[4], "volume_ml": row[5], "image": row[6], "gender": row[7]
    }
    return templates.TemplateResponse("big.html", {"request": request, "parfum": p})


@app.get('/lab', response_class=HTMLResponse)
@app.get('/index3.html', response_class=HTMLResponse)
def lab_page(request: Request):
    ingredients = []
    try:
        if cur:
            cur.execute("SELECT code, name FROM ingredients ORDER BY code")
            ingredients = [{'code': r[0], 'name': r[1]} for r in cur.fetchall()]
    except Exception as e:
        print('lab_page ingredients error:', e)

    return templates.TemplateResponse(
        'index3.html',
        {'request': request, 'ingredients': ingredients}
    )



@app.get('/game/ingredients')
def api_ingredients():
    if not cur:
        return JSONResponse({'ingredients': []})
    try:
        cur.execute("SELECT code, name, meta FROM ingredients ORDER BY code")
        rows = cur.fetchall()
        return JSONResponse({'ingredients': [{'code': r[0], 'name': r[1], 'meta': r[2] or {}} for r in rows]})
    except Exception as e:
        print('api_ingredients error:', e)
        return JSONResponse({'ingredients': []}, status_code=500)


@app.get('/game/check_combination')
def api_check_combination(ingredients: List[str] = Query(...)):
    """Check any pair among provided ingredient codes; return parfum if mapping exists.
    If mapping exists but no parfume linked — return locked: true.
    """
    if not cur or not ingredients or len(ingredients) < 2:
        return JSONResponse({'found': False})

    ingredient_pairs = list(iter_combinations(ingredients, 2))
    if not ingredient_pairs:
        return JSONResponse({'found': False})

    conditions = []
    params = []
    for pair in ingredient_pairs:
        a, b = pair[0], pair[1]
        # ensure both orderings checked
        conditions.append("(c.ingredient1_code=%s AND c.ingredient2_code=%s)")
        conditions.append("(c.ingredient1_code=%s AND c.ingredient2_code=%s)")
        params.extend([a, b, b, a])

    where_clause = ' OR '.join(conditions)
    try:
        query = f"SELECT c.parfume_id, p.id, p.name, p.brand, p.price, p.image_url FROM combinations c LEFT JOIN parfumes p ON c.parfume_id=p.id WHERE {where_clause} LIMIT 1"
        cur.execute(query, tuple(params))
        row = cur.fetchone()
        if row:
            parfume_id = row[0]
            if parfume_id is None:
                return JSONResponse({'found': False, 'locked': True})
            parfum = {'id': row[1], 'name': row[2], 'brand': row[3], 'price': float(row[4]) if row[4] is not None else 0, 'image_url': row[5]}
            return JSONResponse({'found': True, 'parfum': parfum})
        return JSONResponse({'found': False})
    except Exception as e:
        print('api_check_combination error:', e)
        return JSONResponse({'found': False}, status_code=500)


@app.get('/check_combination')
def api_check_combination_alias(ingredients: List[str] = Query(...)):
    return api_check_combination(ingredients)


@app.post('/admin/map_combination')
async def admin_map_combination(request: Request):
    """Admin/worker endpoint to link two ingredient codes to an existing parfume id.
    JSON body: {"ing1":"COF","ing2":"VAN","parfume_id":123}
    """
    require_role(request, ['worker', 'admin'])
    payload = {}
    try:
        payload = await request.json()
    except Exception:
        # try form data
        try:
            form = await request.form()
            payload = dict(form)
        except Exception:
            payload = {}
    ing1 = payload.get('ing1') or payload.get('ingredient1')
    ing2 = payload.get('ing2') or payload.get('ingredient2')
    parfume_id = payload.get('parfume_id')
    if not ing1 or not ing2:
        return JSONResponse({'ok': False, 'error': 'missing ingredients'}, status_code=400)
    # normalize order (lexicographic) to keep unique pair
    a, b = sorted([ing1, ing2])
    try:
        cur.execute("INSERT INTO combinations (ingredient1_code, ingredient2_code, parfume_id) VALUES (%s,%s,%s) ON CONFLICT (ingredient1_code, ingredient2_code) DO UPDATE SET parfume_id=EXCLUDED.parfume_id", (a, b, parfume_id))
        return JSONResponse({'ok': True})
    except Exception as e:
        print('admin_map_combination error:', e)
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)


@app.get('/game/combinations')
def api_list_combinations():
    if not cur:
        return JSONResponse({'combinations': []})
    try:
        cur.execute("SELECT ingredient1_code, ingredient2_code, parfume_id FROM combinations ORDER BY id DESC LIMIT 500")
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append({'ing1': r[0], 'ing2': r[1], 'parfume_id': r[2]})
        return JSONResponse({'combinations': out})
    except Exception as e:
        print('api_list_combinations error:', e)
        return JSONResponse({'combinations': []}, status_code=500)

# ============================================================
# --- API МАРШРУТЫ ДЛЯ ПОДЗАПРОСОВ БД ---
# ============================================================

@app.get("/api/brands/stats")
def api_brands_stats(limit: int = Query(10, ge=1, le=100)):
    """
    API эндпоинт: Получить ТОП брендов с количеством товаров и средней ценой
    ПОДЗАПРОС 1: GROUP BY с агрегирующими функциями COUNT и AVG
    """
    brands = get_brands_with_stats(limit)
    return JSONResponse({
        "success": True,
        "count": len(brands),
        "brands": brands
    })

@app.get("/api/cart/stats")
async def api_cart_stats(request: Request):
    """
    API эндпоинт: Получить статистику корзины пользователя
    ПОДЗАПРОС 2: JOIN с GROUP BY и агрегирующей функцией SUM
    """
    user = request.session.get("user")
    
    if not user or not user.get("id"):
        return JSONResponse({
            "success": False,
            "message": "Не авторизованы"
        }, status_code=401)
    
    stats = get_user_cart_total(user.get("id"))
    
    if stats is None:
        return JSONResponse({
            "success": True,
            "items_count": 0,
            "total_price": 0
        })
    
    return JSONResponse({
        "success": True,
        "items_count": stats["items_count"],
        "total_price": stats["total_price"]
    })


# ======================
# --- Авторизация ---
# ======================

@app.get("/reg.html", response_class=HTMLResponse)
def reg_page(request: Request):
    return templates.TemplateResponse("reg.html", {"request": request, "user": request.session.get("user")})

@app.post("/register")
def register(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    if cur is None: return HTMLResponse("No DB", 500)
    try:
        cur.execute("SELECT id FROM users WHERE username=%s OR email=%s", (username, email))
        if cur.fetchone(): return HTMLResponse("User already exists", 400)
        
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cur.execute(
            "INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, 'client') RETURNING id",
            (username, email, hashed)
        )
        uid = cur.fetchone()[0]
        request.session["user"] = {"id": uid, "username": username, "role": "client"}
        request.session["role"] = "client"
        return RedirectResponse("/index.html", status_code=303)
    except Exception as e:
        print(e)
        return HTMLResponse("Reg error", 500)

@app.get("/sign.html", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("sign.html", {"request": request, "user": request.session.get("user")})

@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    if cur is None: return HTMLResponse("No DB", 500)
    try:
        cur.execute("SELECT id, username, password, role FROM users WHERE email=%s", (email,))
        row = cur.fetchone()
        if row and bcrypt.checkpw(password.encode(), row[2].encode()):
            request.session["user"] = {"id": row[0], "username": row[1], "role": row[3]}
            request.session["role"] = row[3]
            return RedirectResponse("/index.html", status_code=303)
        return HTMLResponse("Invalid credentials", 400)
    except Exception as e:
        print(e)
        return HTMLResponse("Login error", 500)

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/index.html", 302)

@app.get("/profile", response_class=HTMLResponse)
def profile(request: Request):
    user = request.session.get("user")
    if not user: return RedirectResponse("/", 302)
    email = ""
    if cur:
        cur.execute("SELECT email, role FROM users WHERE id=%s", (user["id"],))
        r = cur.fetchone()
        if r: email = r[0]
    return templates.TemplateResponse("profile.html", {"request": request, "user": user, "email": email})

# ======================
# --- ADMIN / WORKER ---
# ======================

def require_role(request: Request, allowed: list):
    u = request.session.get("user")
    if not u or u.get("role") not in allowed:
        raise HTTPException(403, "Access denied")

@app.get("/admin", response_class=HTMLResponse)
def admin_dash(request: Request):
    # require_role(request, ["admin"]) 
    users = []
    if cur:
        cur.execute("SELECT id, username, email, role FROM users ORDER BY id")
        users = [{"id": r[0], "username": r[1], "email": r[2], "role": r[3]} for r in cur.fetchall()]
    return templates.TemplateResponse("admin.html", {"request": request, "users": users})

@app.post("/admin/change_role")
def admin_change_role(request: Request, user_id: int = Form(...), new_role: str = Form(...)):
    require_role(request, ["admin"])
    if new_role in ["admin", "worker", "client"]:
        cur.execute("UPDATE users SET role=%s WHERE id=%s", (new_role, user_id))
    return RedirectResponse("/admin", 303)

@app.get("/session_info")
async def session_info(request: Request):
    """Check current session info"""
    session_user = request.session.get('user') if hasattr(request, 'session') else None
    return JSONResponse({'session_user': session_user})

@app.get("/test_orders")
async def test_orders(request: Request):
    """Debug endpoint to see all orders and current user"""
    session_user = request.session.get('user') if hasattr(request, 'session') else None
    user_id = session_user.get('id') if session_user else None
    all_orders = []
    my_orders = []
    
    if cur:
        try:
            cur.execute("SELECT id, order_num, customer_name, customer_email, customer_user_id, status FROM orders ORDER BY timestamp DESC LIMIT 50")
            rows = cur.fetchall()
            all_orders = [{'id': r[0], 'order_num': r[1], 'customer_name': r[2], 'customer_email': r[3], 'customer_user_id': r[4], 'status': r[5]} for r in rows]
            
            if user_id:
                cur.execute("SELECT id, order_num, customer_name, status FROM orders WHERE customer_user_id=%s ORDER BY timestamp DESC", (user_id,))
                rows = cur.fetchall()
                my_orders = [{'id': r[0], 'order_num': r[1], 'customer_name': r[2], 'status': r[3]} for r in rows]
        except Exception as e:
            print(f'[test_orders] DB error: {e}')
    
    return JSONResponse({
        'current_user': session_user,
        'user_id': user_id,
        'all_orders': all_orders,
        'my_orders': my_orders
    })


@app.get('/events')
async def events_view(request: Request):
    """Return recent order_events from DB or fallback events.json for debugging"""
    if cur:
        try:
            cur.execute("SELECT id, order_id, user_id, event_type, event_meta, timestamp FROM order_events ORDER BY id DESC LIMIT 200")
            rows = cur.fetchall()
            ev = []
            for r in rows:
                ev.append({'id': r[0], 'order_id': r[1], 'user_id': r[2], 'event_type': r[3], 'event_meta': r[4], 'timestamp': r[5]})
            return JSONResponse({'events': ev})
        except Exception as e:
            print('DB events error', e)
    # fallback
    try:
        return JSONResponse({'events': _events_fallback_file()})
    except Exception as e:
        print('events fallback read error', e)
        return JSONResponse({'events': []})

@app.post("/admin/delete_user")
def admin_delete_user(request: Request, user_id: int = Form(...)):
    require_role(request, ["admin"])
    me = request.session["user"]["id"]
    if str(user_id) == str(me): return HTMLResponse("Cannot delete self", 400)
    cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
    return RedirectResponse("/admin", 303)

@app.get("/worker", response_class=HTMLResponse)
def worker_dash(request: Request):
    require_role(request, ["worker", "admin"])
    parf = []
    if cur:
        cur.execute("SELECT id, name, brand, price FROM parfumes ORDER BY id DESC LIMIT 50")
        parf = cur.fetchall()
    return templates.TemplateResponse("worker.html", {"request": request, "parfumes": parf})

@app.post("/worker/add_perfume")
def worker_add(request: Request, name: str=Form(...), brand: str=Form(...), price: int=Form(...),
               volume_ml: int=Form(...), description: str=Form(""), image_url: str=Form(""), gender: str=Form("")):
    require_role(request, ["worker", "admin"])
    try:
        cur.execute("""
            INSERT INTO parfumes (name, brand, description, price, volume_ml, image_url, gender)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (name, brand, description, price, volume_ml, image_url, gender))
        
        # Вместо JSONResponse делаем редирект обратно на страницу панели
        # Замените "/worker" на ваш фактический путь к панели
        return RedirectResponse(url="/worker", status_code=status.HTTP_303_SEE_OTHER)
        
    except Exception as e:
        # В случае ошибки можно вернуть JSON или перенаправить с сообщением об ошибке
        return JSONResponse({"status": "error", "message": str(e)})

@app.post("/worker/delete_perfume/{pid}")
def worker_del(request: Request, pid: int):
    require_role(request, ["worker", "admin"])
    cur.execute("DELETE FROM parfumes WHERE id=%s", (pid,))
    return RedirectResponse("/worker", 303)

@app.post("/worker/edit_perfume/{pid}")
def worker_edit(request: Request, pid: int, name: str=Form(...), brand: str=Form(...), price: float=Form(...)):
    require_role(request, ["worker", "admin"])
    cur.execute("UPDATE parfumes SET name=%s, brand=%s, price=%s WHERE id=%s", (name, brand, price, pid))
    return RedirectResponse("/worker", 303)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)