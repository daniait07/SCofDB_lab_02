-- ============================================
-- Схема базы данных маркетплейса
-- ============================================

-- Включаем расширение UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- TODO: Создать таблицу order_statuses
-- Столбцы: status (PK), description
CREATE TABLE IF NOT EXISTS order_statuses (status TEXT PRIMARY KEY, description TEXT NOT NULL);

-- TODO: Вставить значения статусов
-- created, paid, cancelled, shipped, completed
INSERT INTO order_statuses (status, description) VALUES
    ('created', 'Order created'),
    ('paid', 'Order paid'),
    ('cancelled', 'Order cancelled'),
    ('shipped', 'Order shipped'),
    ('completed', 'Order completed')
ON CONFLICT (status) DO NOTHING;

-- TODO: Создать таблицу users
-- Столбцы: id (UUID PK), email, name, created_at
-- Ограничения:
--   - email UNIQUE
--   - email NOT NULL и не пустой
--   - email валидный (regex через CHECK)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT users_email_not_empty CHECK (length(trim(email)) > 0),
    CONSTRAINT users_email_format CHECK (email ~ '^[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\-.]+$'));

-- TODO: Создать таблицу orders
-- Столбцы: id (UUID PK), user_id (FK), status (FK), total_amount, created_at
-- Ограничения:
--   - user_id -> users(id)
--   - status -> order_statuses(status)
--   - total_amount >= 0
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    status TEXT NOT NULL,
    total_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT orders_user_fk FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT orders_status_fk FOREIGN KEY (status) REFERENCES order_statuses(status),
    CONSTRAINT orders_total_amount_non_negative CHECK (total_amount >= 0));

-- TODO: Создать таблицу order_items
-- Столбцы: id (UUID PK), order_id (FK), product_name, price, quantity
-- Ограничения:
--   - order_id -> orders(id) CASCADE
--   - price >= 0
--   - quantity > 0
--   - product_name не пустой
CREATE TABLE IF NOT EXISTS order_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID NOT NULL,
    product_name TEXT NOT NULL,
    price NUMERIC(12,2) NOT NULL,
    quantity INTEGER NOT NULL,
    CONSTRAINT order_items_order_fk FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    CONSTRAINT order_items_price_non_negative CHECK (price >= 0),
    CONSTRAINT order_items_quantity_positive CHECK (quantity > 0),
    CONSTRAINT order_items_product_name_not_empty CHECK (length(trim(product_name)) > 0));

-- TODO: Создать таблицу order_status_history
-- Столбцы: id (UUID PK), order_id (FK), status (FK), changed_at
-- Ограничения:
--   - order_id -> orders(id) CASCADE
--   - status -> order_statuses(status)
CREATE TABLE IF NOT EXISTS order_status_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID NOT NULL,
    status TEXT NOT NULL,
    changed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT order_status_history_order_fk FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    CONSTRAINT order_status_history_status_fk FOREIGN KEY (status) REFERENCES order_statuses(status));

-- ============================================
-- КРИТИЧЕСКИЙ ИНВАРИАНТ: Нельзя оплатить заказ дважды
-- ============================================
-- TODO: Создать функцию триггера check_order_not_already_paid()
-- При изменении статуса на 'paid' проверить что его нет в истории
-- Если есть - RAISE EXCEPTION
CREATE OR REPLACE FUNCTION check_order_not_already_paid()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'paid' THEN
        IF EXISTS (SELECT 1 FROM order_status_history h WHERE h.order_id = NEW.id AND h.status = 'paid') THEN
            RAISE EXCEPTION 'заказ уже оплачен', NEW.id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- TODO: Создать триггер trigger_check_order_not_already_paid
-- BEFORE UPDATE ON orders FOR EACH ROW
DROP TRIGGER IF EXISTS trigger_check_order_not_already_paid ON orders;
CREATE TRIGGER trigger_check_order_not_already_paid
BEFORE UPDATE OF status ON orders
FOR EACH ROW EXECUTE FUNCTION check_order_not_already_paid();

-- ============================================
-- БОНУС (опционально)
-- ============================================
-- TODO: Триггер автоматического пересчета total_amount
CREATE OR REPLACE FUNCTION recalc_order_total()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE orders o
    SET total_amount = COALESCE((SELECT SUM(oi.price * oi.quantity) FROM order_items oi WHERE oi.order_id = o.id), 0)
    WHERE o.id = COALESCE(NEW.order_id, OLD.order_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_recalc_order_total_insert ON order_items;
DROP TRIGGER IF EXISTS trigger_recalc_order_total_update ON order_items;
DROP TRIGGER IF EXISTS trigger_recalc_order_total_delete ON order_items;

CREATE TRIGGER trigger_recalc_order_total_insert
AFTER INSERT ON order_items
FOR EACH ROW EXECUTE FUNCTION recalc_order_total();

CREATE TRIGGER trigger_recalc_order_total_update
AFTER UPDATE ON order_items
FOR EACH ROW EXECUTE FUNCTION recalc_order_total();

CREATE TRIGGER trigger_recalc_order_total_delete
AFTER DELETE ON order_items
FOR EACH ROW EXECUTE FUNCTION recalc_order_total();

-- TODO: Триггер автоматической записи в историю при изменении статуса
CREATE OR REPLACE FUNCTION add_status_history_on_update()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        INSERT INTO order_status_history (id, order_id, status, changed_at)
        VALUES (uuid_generate_v4(), NEW.id, NEW.status, NOW());
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_add_status_history_on_update ON orders;
CREATE TRIGGER trigger_add_status_history_on_update
AFTER UPDATE OF status ON orders
FOR EACH ROW EXECUTE FUNCTION add_status_history_on_update();

-- TODO: Триггер записи начального статуса при создании заказа
CREATE OR REPLACE FUNCTION add_initial_status_history()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO order_status_history (id, order_id, status, changed_at)
    VALUES (uuid_generate_v4(), NEW.id, NEW.status, NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_add_initial_status_history ON orders;
CREATE TRIGGER trigger_add_initial_status_history
AFTER INSERT ON orders
FOR EACH ROW EXECUTE FUNCTION add_initial_status_history();
