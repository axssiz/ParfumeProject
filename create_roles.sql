-- =====================================================
-- --- СОЗДАНИЕ РОЛЕЙ PostgreSQL И УПРАВЛЕНИЕ ДОСТУПОМ ---
-- =====================================================

-- =====================================================
-- 1. СОЗДАНИЕ РОЛЕЙ НА УРОВНЕ БД (CREATE ROLE)
-- =====================================================

-- Администратор - полный доступ
CREATE ROLE admin_role LOGIN PASSWORD 'admin_password' SUPERUSER;

-- Сотрудник/Рабочий - управление товарами и заказами
CREATE ROLE worker_role LOGIN PASSWORD 'worker_password';

-- Клиент - обычный пользователь
CREATE ROLE client_role LOGIN PASSWORD 'client_password';

-- Гость - ограниченный доступ (только чтение)
CREATE ROLE guest_role LOGIN PASSWORD 'guest_password' NOLOGIN;

-- =====================================================
-- 2. ВЫДАЧА ПРАВ ДОСТУПА (GRANT)
-- =====================================================

-- ===== ПРАВА ДЛЯ АДМИНИСТРАТОРА =====
-- Администратор может всё
GRANT USAGE ON SCHEMA public TO admin_role;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO admin_role;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO admin_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO admin_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO admin_role;

-- ===== ПРАВА ДЛЯ РАБОЧЕГО (WORKER) =====
-- Может работать с таблицами: parfumes, orders, cart_items
GRANT USAGE ON SCHEMA public TO worker_role;

-- Чтение и изменение таблиц товаров
GRANT SELECT, INSERT, UPDATE, DELETE ON parfumes TO worker_role;
GRANT USAGE, SELECT ON SEQUENCE parfumes_id_seq TO worker_role;

-- Чтение и изменение заказов
GRANT SELECT, INSERT, UPDATE, DELETE ON orders TO worker_role;
GRANT USAGE, SELECT ON SEQUENCE orders_id_seq TO worker_role;
GRANT USAGE, SELECT ON SEQUENCE orders_order_num_seq TO worker_role;

-- Чтение корзины пользователя
GRANT SELECT, INSERT, UPDATE, DELETE ON cart_items TO worker_role;
GRANT USAGE, SELECT ON SEQUENCE cart_items_id_seq TO worker_role;

-- Чтение информации о пользователях (для обработки заказов)
GRANT SELECT ON users TO worker_role;

-- Логирование событий заказов
GRANT INSERT ON order_events TO worker_role;
GRANT USAGE, SELECT ON SEQUENCE order_events_id_seq TO worker_role;

-- Работа с ингредиентами и комбинациями
GRANT SELECT, INSERT, UPDATE, DELETE ON ingredients TO worker_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON combinations TO worker_role;
GRANT USAGE, SELECT ON SEQUENCE combinations_id_seq TO worker_role;

-- ===== ПРАВА ДЛЯ КЛИЕНТА (CLIENT) =====
-- Только чтение товаров
GRANT SELECT ON parfumes TO client_role;

-- Просмотр своих заказов
GRANT SELECT ON orders TO client_role;
GRANT INSERT, UPDATE ON orders TO client_role; -- может создавать и обновлять свои заказы
GRANT USAGE, SELECT ON SEQUENCE orders_id_seq TO client_role;
GRANT USAGE, SELECT ON SEQUENCE orders_order_num_seq TO client_role;

-- Управление своей корзиной
GRANT SELECT, INSERT, UPDATE, DELETE ON cart_items TO client_role;
GRANT USAGE, SELECT ON SEQUENCE cart_items_id_seq TO client_role;

-- Логирование событий своих заказов
GRANT INSERT ON order_events TO client_role;
GRANT USAGE, SELECT ON SEQUENCE order_events_id_seq TO client_role;

-- ===== ПРАВА ДЛЯ ГОСТЯ (GUEST) =====
-- Только просмотр товаров
GRANT SELECT ON parfumes TO guest_role;
GRANT SELECT ON ingredients TO guest_role;

-- =====================================================
-- 3. ОТЗЫВ ПРАВ (REVOKE)
-- =====================================================

-- Отозвать все права у роли
-- REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM worker_role;
-- REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM worker_role;

-- Отозвать конкретное право
-- REVOKE DELETE ON parfumes FROM worker_role;
-- REVOKE UPDATE ON orders FROM worker_role;

-- =====================================================
-- 4. ИЗМЕНЕНИЕ ПАРАМЕТРОВ РОЛЕЙ (ALTER ROLE)
-- =====================================================

-- Изменить пароль роли
ALTER ROLE admin_role WITH PASSWORD 'new_admin_password';
ALTER ROLE worker_role WITH PASSWORD 'new_worker_password';
ALTER ROLE client_role WITH PASSWORD 'new_client_password';

-- Разрешить вход для гостя
ALTER ROLE guest_role WITH LOGIN;

-- Запретить вход для гостя
ALTER ROLE guest_role WITH NOLOGIN;

-- Сделать администратором
ALTER ROLE worker_role WITH SUPERUSER;

-- Убрать права администратора
ALTER ROLE worker_role WITH NOSUPERUSER;

-- Установить лимит на количество соединений
ALTER ROLE client_role CONNECTION LIMIT 10;
ALTER ROLE guest_role CONNECTION LIMIT 5;
ALTER ROLE admin_role CONNECTION LIMIT -1; -- неограниченно

-- =====================================================
-- 5. ПРОСМОТР ИНФОРМАЦИИ О РОЛЯХ
-- =====================================================

-- Получить все роли в системе
SELECT * FROM pg_roles WHERE rolname LIKE '%_role';

-- Получить права доступа к таблицам
SELECT 
    grantee, 
    privilege_type, 
    table_name
FROM information_schema.role_table_grants
WHERE grantee IN ('admin_role', 'worker_role', 'client_role', 'guest_role')
ORDER BY table_name, grantee;

-- Получить права на последовательности (SEQUENCES)
SELECT 
    grantee,
    privilege_type,
    table_name
FROM information_schema.role_usage_grants
WHERE grantee IN ('admin_role', 'worker_role', 'client_role', 'guest_role')
ORDER BY table_name, grantee;

-- Информация о конкретной роли
SELECT 
    rolname,
    rolsuper,
    rolinherit,
    rolcreaterole,
    rolcreatedb,
    rolcanlogin,
    rolreplication,
    rolbypassrls,
    rolconnlimit,
    rolvaliduntil
FROM pg_roles
WHERE rolname = 'worker_role';

-- =====================================================
-- 6. РАБОТА С ЧЛЕНСТВОМ РОЛЕЙ
-- =====================================================

-- Создать группу ролей
CREATE ROLE moderator_group NOLOGIN;

-- Добавить роль в группу
GRANT moderator_group TO worker_role;

-- Удалить роль из группы
REVOKE moderator_group FROM worker_role;

-- Получить все члены группы
SELECT member, admin_option
FROM pg_auth_members
WHERE roleid = (SELECT oid FROM pg_roles WHERE rolname = 'moderator_group');

-- =====================================================
-- 7. УДАЛЕНИЕ РОЛЕЙ (DROP ROLE)
-- =====================================================

-- Удалить роль (если она не имеет объектов и соединений)
-- DROP ROLE IF EXISTS guest_role;

-- Удалить роль со всеми её объектами
-- DROP ROLE IF EXISTS old_role CASCADE;

-- =====================================================
-- 8. БЕЗОПАСНОСТЬ И АУДИТ
-- =====================================================

-- Просмотр текущего пользователя
SELECT current_user, session_user;

-- Просмотр текущей роли (для приложения)
SELECT current_role;

-- Просмотр всех активных соединений
SELECT 
    pid,
    usename,
    application_name,
    state,
    query_start,
    query
FROM pg_stat_activity
WHERE datname = current_database()
ORDER BY query_start DESC;

-- =====================================================
-- 9. ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ
-- =====================================================

-- Подключение как рабочий
-- psql -U worker_role -d perfume_db -h localhost

-- Смена пользователя в PostgreSQL
SET ROLE worker_role;

-- Вернуться к исходной роли
RESET ROLE;

-- Вывести текущего пользователя
SELECT current_user;

-- =====================================================
-- 10. СЦЕНАРИИ ПРЕДОСТАВЛЕНИЯ ДОСТУПА
-- =====================================================

-- Сценарий 1: Новый сотрудник (рабочий)
-- CREATE ROLE new_worker LOGIN PASSWORD 'secure_password';
-- GRANT SELECT, INSERT, UPDATE ON parfumes TO new_worker;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON orders TO new_worker;

-- Сценарий 2: Повышение клиента в администраторы
-- ALTER ROLE client_role SUPERUSER;

-- Сценарий 3: Ограничение доступа для проблемного пользователя
-- ALTER ROLE problematic_user WITH NOLOGIN;

-- Сценарий 4: Временный доступ (с истечением)
-- CREATE ROLE temp_user LOGIN PASSWORD 'temp_pass' VALID UNTIL '2025-12-31';

-- =====================================================
-- ВАЖНО: ПРИМЕНИТЬ ВСЕ ПРАВА ПО УМОЛЧАНИЮ ДЛЯ НОВЫХ ОБЪЕКТОВ
-- =====================================================

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO client_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO admin_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO worker_role;
