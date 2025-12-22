-- ============================================================
-- SQL ПРИМЕРЫ ДЛЯ ТЕСТИРОВАНИЯ СЛОЖНЫХ ПОДЗАПРОСОВ
-- ============================================================

-- ВНИМАНИЕ: Выполнять только в базе данных 'perfume_db' с пользователем 'postgres'

-- ============================================================
-- ПОДЗАПРОС #1: ТОП БРЕНДЫ С АНАЛИТИКОЙ
-- ============================================================

-- Полный SQL запрос, используемый в функции get_top_brands_analytics():
SELECT 
    brand_data.brand,
    brand_data.product_count,
    brand_data.avg_price,
    brand_data.min_price,
    brand_data.max_price,
    COALESCE(order_stats.total_orders, 0) as total_orders,
    CASE 
        WHEN brand_data.product_count > 0 
        THEN ROUND(CAST(COALESCE(order_stats.total_orders, 0) AS NUMERIC) / brand_data.product_count, 2)
        ELSE 0
    END as avg_orders_per_product
FROM (
    -- ПОДЗАПРОС 1А: Агрегация данных о товарах по брендам
    SELECT 
        brand,
        COUNT(*) as product_count,
        ROUND(AVG(price)::NUMERIC, 2) as avg_price,
        MIN(price) as min_price,
        MAX(price) as max_price
    FROM parfumes
    WHERE brand IS NOT NULL
    GROUP BY brand
) as brand_data
LEFT JOIN (
    -- ПОДЗАПРОС 1Б: Подсчет заказов по брендам (сложный анализ JSONB)
    SELECT 
        p.brand,
        COUNT(DISTINCT o.id) as total_orders
    FROM orders o
    JOIN (
        SELECT DISTINCT ON (jsonb_object_keys(items))
            id,
            jsonb_each_text(items) as item_data
        FROM orders
    ) o_items ON o.id = o_items.id
    LEFT JOIN parfumes p ON p.id = CAST(o_items.item_data AS INTEGER)
    WHERE p.brand IS NOT NULL
    GROUP BY p.brand
) as order_stats ON brand_data.brand = order_stats.brand
ORDER BY total_orders DESC, brand_data.product_count DESC
LIMIT 10;

-- ============================================================
-- ПРОСТАЯ ВЕРСИЯ ПОДЗАПРОСА #1 (для тестирования):
-- ============================================================

-- Только статистика по товарам (без заказов):
SELECT 
    brand,
    COUNT(*) as product_count,
    ROUND(AVG(price)::NUMERIC, 2) as avg_price,
    MIN(price) as min_price,
    MAX(price) as max_price
FROM parfumes
WHERE brand IS NOT NULL
GROUP BY brand
ORDER BY product_count DESC
LIMIT 10;

-- ============================================================
-- АНАЛИЗ JSONB В ПОДЗАПРОСЕ #1:
-- ============================================================

-- Проверка, как работает расширение JSONB элементов:
SELECT 
    id,
    items,
    jsonb_each_text(items) as item_pair
FROM orders
WHERE items IS NOT NULL AND items != '{}'::jsonb
LIMIT 5;

-- Подсчет уникальных товаров в заказах:
SELECT 
    COUNT(DISTINCT CAST(item_data AS INTEGER)) as unique_products
FROM (
    SELECT jsonb_each_text(items) as item_data
    FROM orders
    WHERE items IS NOT NULL
) subq;

-- ============================================================
-- ПОДЗАПРОС #2: ПЕРСОНАЛИЗИРОВАННЫЕ РЕКОМЕНДАЦИИ
-- ============================================================

-- Полный SQL запрос для пользователя с ID = 1:
WITH user_cart_analysis AS (
    -- CTE 1: Анализ предпочитаемых брендов в корзине
    SELECT 
        p.brand,
        AVG(p.price) as avg_price_in_cart,
        MIN(p.price) as min_price_in_cart,
        MAX(p.price) as max_price_in_cart,
        COUNT(*) as items_in_cart
    FROM cart_items c
    JOIN parfumes p ON c.parfume_id = p.id
    WHERE c.user_id = 1
    GROUP BY p.brand
),
user_cart_items AS (
    -- CTE 2: Список товаров уже в корзине (для исключения)
    SELECT DISTINCT c.parfume_id
    FROM cart_items c
    WHERE c.user_id = 1
),
price_range_analysis AS (
    -- CTE 3: Анализ ценовых сегментов доступных товаров
    SELECT 
        CASE 
            WHEN price < 50 THEN 'budget'
            WHEN price < 150 THEN 'mid-range'
            ELSE 'premium'
        END as price_segment,
        COUNT(*) as segment_count,
        AVG(price) as segment_avg_price
    FROM parfumes
    WHERE id NOT IN (SELECT parfume_id FROM user_cart_items)
    GROUP BY price_segment
)
SELECT 
    p.id,
    p.name,
    p.brand,
    p.price,
    p.image_url,
    p.description,
    p.volume_ml,
    CASE 
        WHEN p.brand IN (SELECT brand FROM user_cart_analysis) THEN 'preferred_brand'
        ELSE 'new_brand'
    END as recommendation_reason,
    CASE 
        WHEN p.price < 50 THEN 'budget'
        WHEN p.price < 150 THEN 'mid-range'
        ELSE 'premium'
    END as price_segment,
    ROUND(ABS(p.price - (SELECT avg_price_in_cart FROM user_cart_analysis LIMIT 1))::NUMERIC, 2) as price_distance
FROM parfumes p
WHERE p.id NOT IN (SELECT parfume_id FROM user_cart_items)
AND (
    p.brand IN (SELECT brand FROM user_cart_analysis)
    OR ABS(p.price - (SELECT AVG(avg_price_in_cart) FROM user_cart_analysis)) < 100
)
ORDER BY 
    CASE WHEN p.brand IN (SELECT brand FROM user_cart_analysis) THEN 0 ELSE 1 END,
    price_distance ASC,
    p.id DESC
LIMIT 12;

-- ============================================================
-- РАЗБОР ПОДЗАПРОСА #2 НА ЧАСТИ:
-- ============================================================

-- Шаг 1: Посмотреть корзину пользователя (ID = 1):
SELECT 
    c.id as cart_id,
    c.parfume_id,
    p.name,
    p.brand,
    p.price
FROM cart_items c
LEFT JOIN parfumes p ON c.parfume_id = p.id
WHERE c.user_id = 1;

-- Шаг 2: Анализ брендов в корзине:
SELECT 
    p.brand,
    AVG(p.price) as avg_price,
    COUNT(*) as items_count
FROM cart_items c
JOIN parfumes p ON c.parfume_id = p.id
WHERE c.user_id = 1
GROUP BY p.brand;

-- Шаг 3: Товары, НЕ в корзине пользователя:
SELECT id, name, brand, price
FROM parfumes
WHERE id NOT IN (
    SELECT parfume_id FROM cart_items WHERE user_id = 1
)
LIMIT 20;

-- Шаг 4: Товары с похожей ценой (в диапазоне):
SELECT id, name, brand, price
FROM parfumes
WHERE price BETWEEN 100 AND 200  -- Примерный диапазон
AND id NOT IN (
    SELECT parfume_id FROM cart_items WHERE user_id = 1
)
ORDER BY price ASC;

-- Шаг 5: Расстояние по цене от среднего товара в корзине:
SELECT 
    p.id,
    p.name,
    p.price,
    (SELECT AVG(price) FROM parfumes WHERE id IN (
        SELECT parfume_id FROM cart_items WHERE user_id = 1
    )) as avg_cart_price,
    ABS(p.price - (SELECT AVG(price) FROM parfumes WHERE id IN (
        SELECT parfume_id FROM cart_items WHERE user_id = 1
    ))) as price_distance
FROM parfumes p
WHERE id NOT IN (
    SELECT parfume_id FROM cart_items WHERE user_id = 1
)
ORDER BY price_distance ASC
LIMIT 20;

-- ============================================================
-- ТЕСТИРОВАНИЕ: СОЗДАНИЕ ТЕСТОВЫХ ДАННЫХ
-- ============================================================

-- Если нужно создать тестовые данные для проверки (осторожно!):

-- Добавить тестового пользователя:
-- INSERT INTO users (username, email, password, role) 
-- VALUES ('test_user', 'test@example.com', 'hashed_password', 'client');

-- Добавить товары в тестовую корзину:
-- INSERT INTO cart_items (user_id, parfume_id, quantity) 
-- VALUES (1, 1, 2), (1, 3, 1), (1, 5, 1);

-- Добавить тестовый заказ:
-- INSERT INTO orders (id, items, total_price, status, timestamp, customer_phone, customer_email, customer_city)
-- VALUES ('test-order-1', '{"1": 2, "3": 1}'::jsonb, 250.00, 'delivered', 1700000000, '+79991234567', 'test@test.com', 'Moscow');

-- ============================================================
-- СОВЕТЫ ПО ОПТИМИЗАЦИИ:
-- ============================================================

-- 1. Добавить индексы для быстрого поиска:
-- CREATE INDEX IF NOT EXISTS idx_parfumes_brand ON parfumes(brand);
-- CREATE INDEX IF NOT EXISTS idx_parfumes_price ON parfumes(price);
-- CREATE INDEX IF NOT EXISTS idx_cart_items_user_id ON cart_items(user_id);
-- CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

-- 2. Проверить план выполнения:
-- EXPLAIN ANALYZE SELECT ... (скопировать весь запрос);

-- 3. Профилирование:
-- SET log_min_duration_statement = 100;  -- логировать запросы > 100мс

-- ============================================================
