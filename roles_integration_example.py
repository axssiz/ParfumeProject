"""
Пример интеграции системы ролей в основное приложение image.py
"""

# =====================================================
# Добавить эти импорты в начало image.py
# =====================================================

from roles_manager import RoleManager, init_roles_in_app


# =====================================================
# ВАРИАНТ 1: Инициализация при подключении к БД
# =====================================================

# В разделе "Подключение к БД (Исправлено)" добавить:

def initialize_roles():
    """Инициализирует систему ролей при первом подключении"""
    try:
        manager = RoleManager(cur)
        
        # Проверяем, существует ли таблица ролей
        cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'roles'
        )
        """)
        
        if not cur.fetchone()[0]:
            # Таблица не существует - создаём всё
            print("\n📋 Создаю систему ролей...")
            manager.init_all()
        else:
            print("✓ Система ролей уже инициализирована")
            
            # Показываем статистику
            print("\n=== Статистика ===")
            for stat in manager.get_role_statistics():
                print(f"  {stat['name']}: {stat['user_count']} пользователей")
    
    except Exception as e:
        print(f"⚠ Внимание при инициализации ролей: {e}")


# Вызвать после создания таблиц:
# initialize_roles()


# =====================================================
# ВАРИАНТ 2: Функция для проверки разрешений
# =====================================================

def check_user_permission(user_id: int, permission: str) -> bool:
    """Проверяет наличие разрешения у пользователя"""
    if cur is None:
        return False
    
    try:
        manager = RoleManager(cur)
        return manager.has_permission(user_id, permission)
    except Exception as e:
        print(f"Ошибка проверки разрешения: {e}")
        return False


# =====================================================
# ВАРИАНТ 3: Улучшенный require_role с разрешениями
# =====================================================

def require_permission(request: Request, permission: str):
    """Требует наличие конкретного разрешения"""
    user = request.session.get("user")
    if not user or not user.get("id"):
        raise HTTPException(403, "Не авторизованы")
    
    if check_user_permission(user.get("id"), permission):
        return True
    
    raise HTTPException(403, "Недостаточно прав для этого действия")


def require_any_permission(request: Request, permissions: List[str]):
    """Требует наличие любого из списка разрешений"""
    user = request.session.get("user")
    if not user or not user.get("id"):
        raise HTTPException(403, "Не авторизованы")
    
    for perm in permissions:
        if check_user_permission(user.get("id"), perm):
            return True
    
    raise HTTPException(403, "Недостаточно прав для этого действия")


# =====================================================
# ВАРИАНТ 4: API endpoints для управления ролями
# =====================================================

@app.get("/api/roles")
async def api_list_roles(request: Request):
    """Получить все роли и их разрешения"""
    require_permission(request, "manage_roles")
    
    manager = RoleManager(cur)
    roles = manager.get_all_roles()
    
    return JSONResponse({
        "success": True,
        "roles": roles
    })


@app.get("/api/roles/{role_name}/permissions")
async def api_role_permissions(request: Request, role_name: str):
    """Получить разрешения конкретной роли"""
    require_permission(request, "manage_roles")
    
    manager = RoleManager(cur)
    permissions = manager.get_role_permissions(role_name)
    
    return JSONResponse({
        "success": True,
        "role": role_name,
        "permissions": permissions
    })


@app.get("/api/users/role/{role_name}")
async def api_users_by_role(request: Request, role_name: str):
    """Получить пользователей с конкретной ролью"""
    require_permission(request, "view_users")
    
    manager = RoleManager(cur)
    users = manager.get_users_by_role(role_name)
    
    return JSONResponse({
        "success": True,
        "role": role_name,
        "users": users,
        "count": len(users)
    })


@app.post("/api/user/{user_id}/role")
async def api_change_user_role(request: Request, user_id: int):
    """Изменить роль пользователя"""
    require_permission(request, "edit_users")
    
    payload = await request.json()
    new_role = payload.get("role")
    
    if not new_role or new_role not in ["admin", "worker", "client", "guest"]:
        return JSONResponse({"success": False, "error": "Неправильная роль"}, status_code=400)
    
    manager = RoleManager(cur)
    success = manager.change_user_role(user_id, new_role)
    
    return JSONResponse({"success": success})


@app.get("/api/user/me/permissions")
async def api_my_permissions(request: Request):
    """Получить свои разрешения"""
    user = request.session.get("user")
    if not user or not user.get("id"):
        return JSONResponse({"permissions": []})
    
    manager = RoleManager(cur)
    permissions = manager.get_user_permissions(user.get("id"))
    
    return JSONResponse({
        "success": True,
        "permissions": permissions,
        "role": user.get("role")
    })


@app.get("/api/roles/stats")
async def api_roles_stats(request: Request):
    """Получить статистику по ролям"""
    require_permission(request, "manage_roles")
    
    manager = RoleManager(cur)
    stats = manager.get_role_statistics()
    
    return JSONResponse({
        "success": True,
        "statistics": stats
    })


# =====================================================
# ВАРИАНТ 5: Примеры использования в обработчиках
# =====================================================

@app.post("/worker/add_perfume")
def worker_add(request: Request, name: str=Form(...), brand: str=Form(...), price: int=Form(...),
               volume_ml: int=Form(...), description: str=Form(""), image_url: str=Form(""), gender: str=Form("")):
    """Добавить товар (требует разрешение edit_products)"""
    require_permission(request, "edit_products")
    
    try:
        cur.execute("""
            INSERT INTO parfumes (name, brand, description, price, volume_ml, image_url, gender)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (name, brand, description, price, volume_ml, image_url, gender))
        
        return RedirectResponse(url="/worker", status_code=status.HTTP_303_SEE_OTHER)
        
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)})


@app.post("/worker/delete_perfume/{pid}")
def worker_del(request: Request, pid: int):
    """Удалить товар (требует разрешение delete_products)"""
    require_permission(request, "delete_products")
    
    cur.execute("DELETE FROM parfumes WHERE id=%s", (pid,))
    return RedirectResponse("/worker", 303)


@app.get("/analytics")
def analytics_page(request: Request):
    """Страница аналитики (требует разрешение view_analytics)"""
    require_permission(request, "view_analytics")
    
    return templates.TemplateResponse("analytics.html", {"request": request, "user": request.session.get("user")})


@app.post("/admin/delete_user")
def admin_delete_user(request: Request, user_id: int = Form(...)):
    """Удалить пользователя (требует разрешение delete_users)"""
    require_permission(request, "delete_users")
    
    me = request.session["user"]["id"]
    if str(user_id) == str(me):
        return HTMLResponse("Cannot delete self", 400)
    
    cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
    return RedirectResponse("/admin", 303)


# =====================================================
# ВАРИАНТ 6: Инициализация в main
# =====================================================

if __name__ == "__main__":
    # Инициализировать роли при запуске
    if cur:
        initialize_roles()
    
    uvicorn.run(app, host="127.0.0.1", port=8000)
