"""
Тест для демонстрации ПРОБЛЕМЫ race condition.

Этот тест должен ПРОХОДИТЬ, подтверждая, что при использовании
pay_order_unsafe() возникает двойная оплата.
"""

import asyncio
import pytest
import uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.application.payment_service import PaymentService
from app.tests.test_concurrent_payment_unsafe import DATABASE_URL

# TODO: Настроить подключение к тестовой БД
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/marketplace"


@pytest.fixture
async def db_session():
    """
    Создать сессию БД для тестов.
    
    TODO: Реализовать фикстуру:
    1. Создать engine
    2. Создать session maker
    3. Открыть сессию
    4. Yield сессию
    5. Закрыть сессию после теста
    """
    # TODO: Реализовать создание сессии
    engine = create_async_engine(DATABASE_URL, echo=True)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with AsyncSessionLocal() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def test_order(db_session):
    """
    Создать тестовый заказ со статусом 'created'.
    
    TODO: Реализовать фикстуру:
    1. Создать тестового пользователя
    2. Создать тестовый заказ со статусом 'created'
    3. Записать начальный статус в историю
    4. Вернуть order_id
    5. После теста - очистить данные
    """
    # TODO: Реализовать создание тестового заказа
    user_id = uuid.uuid4()
    order_id = uuid.uuid4()
 
    await db_session.execute(
        text(
            "INSERT INTO users (id, email, name, created_at) "
            "VALUES (:uid, 'unsafe@test.com', 'Unsafe User', NOW()) "
            "ON CONFLICT (email) DO NOTHING"),
        {"uid": str(user_id)},)

 
    res = await db_session.execute(
        text("SELECT id FROM users WHERE email = 'unsafe@test.com'"))
    user_id_db = res.scalar()
 
    await db_session.execute(
        text(
            "INSERT INTO orders (id, user_id, status, total_amount, created_at) "
            "VALUES (:oid, :uid, 'created', 100.00, NOW()) "
            "ON CONFLICT (id) DO NOTHING"),
        {"oid": str(order_id), "uid": str(user_id_db)},)
 
    await db_session.execute(
        text(
            "INSERT INTO order_status_history (id, order_id, status, changed_at) "
            "VALUES (uuid_generate_v4(), :oid, 'created', NOW())"),
        {"oid": str(order_id)},)

    await db_session.commit()
    return order_id



@pytest.mark.asyncio
async def test_concurrent_payment_unsafe_demonstrates_race_condition(db_session, test_order):
    """
    Тест демонстрирует проблему race condition при использовании pay_order_unsafe().
    
    ОЖИДАЕМЫЙ РЕЗУЛЬТАТ: Тест ПРОХОДИТ, подтверждая, что заказ был оплачен дважды.
    Это показывает, что метод pay_order_unsafe() НЕ защищен от конкурентных запросов.
    
    TODO: Реализовать тест следующим образом:
    
    1. Создать два экземпляра PaymentService с РАЗНЫМИ сессиями
       (это имитирует два независимых HTTP-запроса)
       
    2. Запустить два параллельных вызова pay_order_unsafe():
       
       async def payment_attempt_1():
           service1 = PaymentService(session1)
           return await service1.pay_order_unsafe(order_id)
           
       async def payment_attempt_2():
           service2 = PaymentService(session2)
           return await service2.pay_order_unsafe(order_id)
           
       results = await asyncio.gather(
           payment_attempt_1(),
           payment_attempt_2(),
           return_exceptions=True
       )
       
    3. Проверить историю оплат:
       
       service = PaymentService(session)
       history = await service.get_payment_history(order_id)
       
       # ОЖИДАЕМ ДВЕ ЗАПИСИ 'paid' - это и есть проблема!
       assert len(history) == 2, "Ожидалось 2 записи об оплате (RACE CONDITION!)"
       
    4. Вывести информацию о проблеме:
       
       print(f"⚠️ RACE CONDITION DETECTED!")
       print(f"Order {order_id} was paid TWICE:")
       for record in history:
           print(f"  - {record['changed_at']}: status = {record['status']}")
    """
    # TODO: Реализовать тест, демонстрирующий race condition
 
    order_id = test_order

    engine = create_async_engine(DATABASE_URL, echo=True)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def payment_attempt():
        async with AsyncSessionLocal() as session:
            service = PaymentService(session)
            try:
                await service.pay_order_unsafe(order_id)
                await session.commit()
                return "ok"
            except Exception as e:
                await session.rollback()
                return e
 
    results = await asyncio.gather(
        payment_attempt(),
        payment_attempt(),
        return_exceptions=True,)
 
    async with AsyncSessionLocal() as session:
        service = PaymentService(session)
        history = await service.get_payment_history(order_id)

    print("\n⚠️  RACE CONDITION DETECTED!")
    print(f"заказ {order_id} был оплачен {len(history)} время:")
    for record in history:
        print(f"  - {record['changed_at']}: status = {record['status']}")
 
    assert len(history) >= 2, "ожидалось как минимум 2 записи об оплате RACE CONDITION!"

    await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_payment_unsafe_both_succeed():
    """
    Дополнительный тест: проверить, что ОБЕ транзакции успешно завершились.
    
    TODO: Реализовать проверку, что:
    1. Обе попытки оплаты вернули успешный результат
    2. Ни одна не выбросила исключение
    3. Обе записали в историю
    
    Это подтверждает, что проблема не в ошибках, а в race condition.
    """
    # TODO: Реализовать проверку успешности обеих транзакций
    pytest.skip("дальше")


if __name__ == "__main__":
    """
    Запуск теста:
    
    cd backend
    export PYTHONPATH=$(pwd)
    pytest app/tests/test_concurrent_payment_unsafe.py -v -s
    
    ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:
    ✅ test_concurrent_payment_unsafe_demonstrates_race_condition PASSED
    
    Вывод должен показывать:
    ⚠️ RACE CONDITION DETECTED!
    Order XXX was paid TWICE:
      - 2024-XX-XX: status = paid
      - 2024-XX-XX: status = paid
    """
    pytest.main([__file__, "-v", "-s"])
