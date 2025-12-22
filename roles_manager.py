"""
Модуль управления ролями и разрешениями для приложения парфюмерии
Содержит функции для работы с ролями, разрешениями и контролем доступа
"""

import psycopg2
from psycopg2 import extras
from typing import List, Dict, Optional


class RoleManager:
    """Класс для управления ролями и разрешениями"""
    
    def __init__(self, cur):
        """Инициализация с курсором БД"""
        self.cur = cur
    
    def create_roles_structure(self):
        """Создаёт все необходимые таблицы для управления ролями"""
        try:
            # Таблица ролей
            self.cur.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # Таблица разрешений
            self.cur.execute("""
            CREATE TABLE IF NOT EXISTS permissions (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # Таблица связи ролей и разрешений
            self.cur.execute("""
            CREATE TABLE IF NOT EXISTS role_permissions (
                id SERIAL PRIMARY KEY,
                role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
                permission_id INTEGER REFERENCES permissions(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(role_id, permission_id)
            )
            """)
            
            print("✓ Таблицы ролей успешно созданы")
            return True
        except Exception as e:
            print(f"✗ Ошибка создания таблиц ролей: {e}")
            return False
    
    def seed_default_roles(self):
        """Вставляет стандартные роли"""
        default_roles = [
            ('admin', 'Администратор - полный доступ к системе'),
            ('worker', 'Сотрудник - управление товарами и заказами'),
            ('client', 'Клиент - обычный пользователь'),
            ('guest', 'Гость - ограниченный доступ')
        ]
        
        try:
            for role_name, description in default_roles:
                self.cur.execute(
                    "INSERT INTO roles (name, description) VALUES (%s, %s) ON CONFLICT (name) DO NOTHING",
                    (role_name, description)
                )
            print("✓ Стандартные роли созданы")
            return True
        except Exception as e:
            print(f"✗ Ошибка создания ролей: {e}")
            return False
    
    def seed_default_permissions(self):
        """Вставляет стандартные разрешения"""
        default_permissions = [
            ('view_products', 'Просмотр товаров'),
            ('edit_products', 'Редактирование товаров'),
            ('delete_products', 'Удаление товаров'),
            ('view_orders', 'Просмотр заказов'),
            ('edit_orders', 'Редактирование заказов'),
            ('view_users', 'Просмотр пользователей'),
            ('edit_users', 'Редактирование пользователей'),
            ('delete_users', 'Удаление пользователей'),
            ('view_analytics', 'Просмотр аналитики'),
            ('manage_roles', 'Управление ролями')
        ]
        
        try:
            for perm_name, description in default_permissions:
                self.cur.execute(
                    "INSERT INTO permissions (name, description) VALUES (%s, %s) ON CONFLICT (name) DO NOTHING",
                    (perm_name, description)
                )
            print("✓ Стандартные разрешения созданы")
            return True
        except Exception as e:
            print(f"✗ Ошибка создания разрешений: {e}")
            return False
    
    def assign_permissions_to_roles(self):
        """Привязывает разрешения к ролям"""
        role_perms = {
            'admin': None,  # None = все разрешения
            'worker': ['view_products', 'edit_products', 'view_orders', 'edit_orders', 'view_analytics'],
            'client': ['view_products', 'view_orders'],
            'guest': ['view_products']
        }
        
        try:
            for role_name, permissions in role_perms.items():
                self.cur.execute("SELECT id FROM roles WHERE name = %s", (role_name,))
                role_row = self.cur.fetchone()
                if not role_row:
                    continue
                
                role_id = role_row[0]
                
                if permissions is None:
                    # Для admin - все разрешения
                    self.cur.execute(
                        "SELECT id FROM permissions"
                    )
                    perm_ids = [p[0] for p in self.cur.fetchall()]
                else:
                    # Для других ролей - выбранные разрешения
                    placeholders = ','.join(['%s'] * len(permissions))
                    self.cur.execute(
                        f"SELECT id FROM permissions WHERE name IN ({placeholders})",
                        tuple(permissions)
                    )
                    perm_ids = [p[0] for p in self.cur.fetchall()]
                
                # Вставить связи
                for perm_id in perm_ids:
                    self.cur.execute(
                        "INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (role_id, perm_id)
                    )
            
            print("✓ Разрешения привязаны к ролям")
            return True
        except Exception as e:
            print(f"✗ Ошибка привязки разрешений: {e}")
            return False
    
    def get_all_roles(self) -> List[Dict]:
        """Получает все роли с количеством разрешений"""
        try:
            self.cur.execute("""
            SELECT 
                r.id,
                r.name,
                r.description,
                COUNT(p.id) as permission_count,
                STRING_AGG(p.name, ', ') as permissions
            FROM roles r
            LEFT JOIN role_permissions rp ON r.id = rp.role_id
            LEFT JOIN permissions p ON rp.permission_id = p.id
            GROUP BY r.id, r.name, r.description
            ORDER BY r.id
            """)
            
            columns = [desc[0] for desc in self.cur.description]
            return [dict(zip(columns, row)) for row in self.cur.fetchall()]
        except Exception as e:
            print(f"✗ Ошибка получения ролей: {e}")
            return []
    
    def get_role_permissions(self, role_name: str) -> List[str]:
        """Получает разрешения конкретной роли"""
        try:
            self.cur.execute("""
            SELECT p.name
            FROM permissions p
            INNER JOIN role_permissions rp ON p.id = rp.permission_id
            INNER JOIN roles r ON rp.role_id = r.id
            WHERE r.name = %s
            ORDER BY p.name
            """, (role_name,))
            
            return [row[0] for row in self.cur.fetchall()]
        except Exception as e:
            print(f"✗ Ошибка получения разрешений: {e}")
            return []
    
    def get_users_by_role(self, role_name: str) -> List[Dict]:
        """Получает всех пользователей с определённой ролью"""
        try:
            self.cur.execute("""
            SELECT id, username, email, role
            FROM users
            WHERE role = %s
            ORDER BY username
            """, (role_name,))
            
            columns = [desc[0] for desc in self.cur.description]
            return [dict(zip(columns, row)) for row in self.cur.fetchall()]
        except Exception as e:
            print(f"✗ Ошибка получения пользователей: {e}")
            return []
    
    def change_user_role(self, user_id: int, new_role: str) -> bool:
        """Изменяет роль пользователя"""
        try:
            self.cur.execute("UPDATE users SET role = %s WHERE id = %s", (new_role, user_id))
            if self.cur.rowcount > 0:
                print(f"✓ Роль пользователя {user_id} изменена на {new_role}")
                return True
            print(f"✗ Пользователь {user_id} не найден")
            return False
        except Exception as e:
            print(f"✗ Ошибка изменения роли: {e}")
            return False
    
    def get_user_permissions(self, user_id: int) -> List[str]:
        """Получает все разрешения пользователя через его роль"""
        try:
            self.cur.execute("""
            SELECT DISTINCT p.name
            FROM users u
            INNER JOIN roles r ON u.role = r.name
            LEFT JOIN role_permissions rp ON r.id = rp.role_id
            LEFT JOIN permissions p ON rp.permission_id = p.id
            WHERE u.id = %s
            ORDER BY p.name
            """, (user_id,))
            
            return [row[0] for row in self.cur.fetchall()]
        except Exception as e:
            print(f"✗ Ошибка получения разрешений пользователя: {e}")
            return []
    
    def has_permission(self, user_id: int, permission: str) -> bool:
        """Проверяет наличие разрешения у пользователя"""
        permissions = self.get_user_permissions(user_id)
        return permission in permissions
    
    def get_role_statistics(self) -> List[Dict]:
        """Получает статистику по ролям"""
        try:
            self.cur.execute("""
            SELECT 
                r.name,
                COUNT(u.id) as user_count
            FROM roles r
            LEFT JOIN users u ON u.role = r.name
            GROUP BY r.id, r.name
            ORDER BY user_count DESC
            """)
            
            columns = [desc[0] for desc in self.cur.description]
            return [dict(zip(columns, row)) for row in self.cur.fetchall()]
        except Exception as e:
            print(f"✗ Ошибка получения статистики: {e}")
            return []
    
    def add_permission(self, permission_name: str, description: str = "") -> bool:
        """Добавляет новое разрешение"""
        try:
            self.cur.execute(
                "INSERT INTO permissions (name, description) VALUES (%s, %s)",
                (permission_name, description)
            )
            print(f"✓ Разрешение '{permission_name}' добавлено")
            return True
        except Exception as e:
            if 'duplicate' in str(e).lower():
                print(f"⚠ Разрешение '{permission_name}' уже существует")
            else:
                print(f"✗ Ошибка добавления разрешения: {e}")
            return False
    
    def add_permission_to_role(self, role_name: str, permission_name: str) -> bool:
        """Добавляет разрешение к роли"""
        try:
            self.cur.execute("""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id 
            FROM roles r, permissions p
            WHERE r.name = %s AND p.name = %s
            """, (role_name, permission_name))
            
            if self.cur.rowcount > 0:
                print(f"✓ Разрешение '{permission_name}' добавлено роли '{role_name}'")
                return True
            return False
        except Exception as e:
            print(f"✗ Ошибка добавления разрешения к роли: {e}")
            return False
    
    def init_all(self):
        """Полная инициализация всей системы ролей"""
        print("\n=== Инициализация системы ролей ===")
        
        steps = [
            self.create_roles_structure,
            self.seed_default_roles,
            self.seed_default_permissions,
            self.assign_permissions_to_roles
        ]
        
        for step in steps:
            if not step():
                print(f"\n✗ Инициализация отменена на шаге: {step.__name__}")
                return False
        
        print("\n✓ Система ролей полностью инициализирована!\n")
        return True


# Пример использования в FastAPI приложении
def init_roles_in_app(cur):
    """Инициализирует роли при запуске приложения"""
    manager = RoleManager(cur)
    manager.init_all()
    
    # Показать статистику
    print("=== Статистика ===")
    for stat in manager.get_role_statistics():
        print(f"{stat['name']}: {stat['user_count']} пользователей")
    
    print("\n=== Роли и разрешения ===")
    for role in manager.get_all_roles():
        print(f"\n{role['name'].upper()}: {role['permission_count']} разрешений")
        if role['permissions']:
            print(f"  Разрешения: {role['permissions']}")
