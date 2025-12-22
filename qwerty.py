# qwerty.py
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from typing import List, Optional
import psycopg2
from psycopg2.extensions import connection as Connection, cursor as Cursor 
from itertools import combinations as iter_combinations
import uvicorn

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="f9b8e2c1d4a5b6c7e8f9a0b1c2d3e4f5")

templates = Jinja2Templates(directory=".")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------- DB CONNECTION & SETUP ----------
DB_CONFIG = {
    "host": "localhost",
    "database": "perfume_db",
    "user": "postgres",
    "password": "",
    "port": "5432",
}

conn: Optional[Connection] = None
cur: Optional[Cursor] = None

try:
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()
    print("DB connected successfully")
except Exception as e:
    print("DB connection error:", e)

def initialize_db(cursor):
    """Создает таблицы, удаляет старые данные и заполняет их тестовыми данными."""
    if not cursor:
        return
        
    print("Initializing DB...")
    
    # 1. Создание таблицы ingredients
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ingredients(
            code TEXT PRIMARY KEY,
            name TEXT
        )
    """)
    
    # 2. Создание таблицы parfumes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parfumes(
            id SERIAL PRIMARY KEY,
            name TEXT,
            brand TEXT,
            description TEXT,
            price NUMERIC,
            volume_ml INTEGER,
            image_url TEXT,
            gender TEXT
        )
    """)
    
    # 3. Создание таблицы combinations (со ссылками на ingredients)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS combinations(
            id SERIAL PRIMARY KEY,
            ingredient1_code TEXT REFERENCES ingredients(code),
            ingredient2_code TEXT REFERENCES ingredients(code),
            parfume_id INTEGER REFERENCES parfumes(id)
        )
    """)
    
    # 4. ОЧИСТКА: Удаление данных и сброс последовательности ID
    # combinations должна быть очищена первой, так как она зависит от обеих таблиц.
    cursor.execute("TRUNCATE TABLE combinations RESTART IDENTITY;") 
    
    # Очистка основных таблиц с CASCADE для надежности, если на них есть другие ссылки
    cursor.execute("TRUNCATE TABLE parfumes RESTART IDENTITY CASCADE;") 
    cursor.execute("TRUNCATE TABLE ingredients RESTART IDENTITY CASCADE;") # <-- ИСПРАВЛЕНО
    
    print("Old data truncated. Sequences restarted.")
    
    # 5. ЗАПОЛНЕНИЕ: Добавление ингредиентов
    cursor.execute("""
        INSERT INTO ingredients (code, name)
        VALUES 
            ('A', 'Лимон'),
            ('B', 'Мята'),
            ('C', 'Роза'),
            ('D', 'Сандал')
    """)
    print("Ingredients data inserted.")
    
    # 6. Добавление тестовых парфюмов
    cursor.execute("""
        INSERT INTO parfumes (name, brand, price, image_url)
        VALUES 
            ('Aqua Fresca', 'Ocean', 25000, 'https://via.placeholder.com/150/0000FF/FFFFFF?text=Aqua'),
            ('Flower Night', 'Garden', 32000, 'https://via.placeholder.com/150/FF00FF/FFFFFF?text=Flower'),
            ('Woody Spice', 'Forest', 45000, 'https://via.placeholder.com/150/8B4513/FFFFFF?text=Wood'),
            ('Lemon Mint Twist', 'Zest', 18000, 'https://via.placeholder.com/150/FFFF00/000000?text=L+M')
        RETURNING id
    """)
    parfume_ids = [row[0] for row in cursor.fetchall()]
    
    aqua_fresca_id = parfume_ids[0]     
    flower_night_id = parfume_ids[1]    
    woody_spice_id = parfume_ids[2]     
    lemon_mint_id = parfume_ids[3]      

    # 7. Добавление тестовых комбинаций
    cursor.execute("""
        INSERT INTO combinations (ingredient1_code, ingredient2_code, parfume_id)
        VALUES 
            ('A', 'B', %s), 
            ('C', 'D', %s), 
            ('A', 'D', %s), 
            ('B', 'C', %s)  
        """, (lemon_mint_id, flower_night_id, woody_spice_id, aqua_fresca_id))

    print("Test data inserted.")

if cur:
    initialize_db(cur)

# ---------- ROUTES ----------

@app.get("/", response_class=HTMLResponse)
def home_page(request: Request):
    ingredients = [
        {"code": "A", "name": "Лимон"},
        {"code": "B", "name": "Мята"},
        {"code": "C", "name": "Роза"},
        {"code": "D", "name": "Сандал"}
    ]
    return templates.TemplateResponse("index3.html", {"request": request, "ingredients": ingredients})

@app.get("/check_combination")
def check_combination(ingredients: List[str] = Query(...)):
    if not cur or len(ingredients) < 2:
        return {"found": False}
    
    ingredient_pairs = list(iter_combinations(ingredients, 2))
    
    if not ingredient_pairs:
        return {"found": False}

    conditions = []
    params = []
    for pair in ingredient_pairs:
        conditions.append(
            """
            (c.ingredient1_code = %s AND c.ingredient2_code = %s) 
            OR 
            (c.ingredient1_code = %s AND c.ingredient2_code = %s)
            """
        )
        params.extend([pair[0], pair[1], pair[1], pair[0]]) 

    where_clause = " OR ".join(conditions)

    try:
        query = f"""
            SELECT p.id, p.name, p.brand, p.price, p.image_url
            FROM combinations c
            JOIN parfumes p ON c.parfume_id = p.id
            WHERE {where_clause}
            LIMIT 1
        """
        
        cur.execute(query, tuple(params))
        row = cur.fetchone()

        if row:
            parfume = {"id": row[0], "name": row[1], "brand": row[2], "price": float(row[3]), "image_url": row[4]}
            return {"found": True, "parfum": parfume}
            
        return {"found": False}
        
    except Exception as e:
        print("Combination error:", e)
        return {"found": False}

@app.get("/big/{parfum_id}")
def view_parfum(parfum_id: int):
    # Заглушка
    return JSONResponse({"message": f"Просмотр парфюма с ID: {parfum_id}"})


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
