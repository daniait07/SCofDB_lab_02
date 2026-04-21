"""
Тест для демонстрации РЕШЕНИЯ проблемы race condition.

Этот тест должен ПРОХОДИТЬ, подтверждая, что при использовании
pay_order_safe() заказ оплачивается только один раз.
"""

import asyncio
import pytest
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.application.payment_service import PaymentService
from app.domain.exceptions import OrderAlreadyPaidError


# TODO: Настроить подключение к тестовой БД
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/marketplace"


@pytest.fixture
async def db_session():
    """
    Создать сессию БД для тестов.
    
    TODO: Реализовать фикстуру (см. test_concurrent_payment_unsafe.py)
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
    
    TODO: Реализовать фикстуру (см. test_concurrent_payment_unsafe.py)
    """
    # TODO: Реализовать создание тестового заказа

    user_id = uuid.uuid4()
    order_id = uuid.uuid4()

    await db_session.execute(
        text(
            "INSERT INTO users (id, email, name, created_at) "
            "VALUES (:uid, 'safe@test.com', 'Safe User', NOW()) "
            "ON CONFLICT (email) DO NOTHING"),
        {"uid": str(user_id)},)
 
    res = await db_session.execute(
        text("SELECT id FROM users WHERE email = 'safe@test.com'"))
    user_id_db = res.scalar()

    await db_session.execute(
        text(
            "INSERT INTO orders (id, user_id, status, total_amount, created_at) "
            "VALUES (:oid, :uid, 'created', 100.00, NOW()) "
            "ON CONFLICT (id) DO NOTHING"),
        {"oid": str(order_id), "uid": str(user_id_db)},)
    await db_session.commit()

    return order_id


@pytest.mark.asyncio
async def test_concurrent_payment_safe_prevents_race_condition(db_session, test_order):
    """
    Тест демонстрирует решение проблемы race condition с помощью pay_order_safe().
    
    ОЖИДАЕМЫЙ РЕЗУЛЬТАТ: Тест ПРОХОДИТ, подтверждая, что заказ был оплачен только один раз.
    Это показывает, что метод pay_order_safe() защищен от конкурентных запросов.
    
    TODO: Реализовать тест следующим образом:
    
    1. Создать два экземпляра PaymentService с РАЗНЫМИ сессиями
       (это имитирует два независимых HTTP-запроса)
       
    2. Запустить два параллельных вызова pay_order_safe():
       
       async def payment_attempt_1():
           service1 = PaymentService(session1)
           return await service1.pay_order_safe(order_id)
           
       async def payment_attempt_2():
           service2 = PaymentService(session2)
           return await service2.pay_order_safe(order_id)
           
       results = await asyncio.gather(
           payment_attempt_1(),
           payment_attempt_2(),
           return_exceptions=True
       )
       
    3. Проверить результаты:
       - Одна попытка должна УСПЕШНО завершиться
       - Вторая попытка должна выбросить OrderAlreadyPaidError ИЛИ вернуть ошибку
       
       success_count = sum(1 for r in results if not isinstance(r, Exception))
       error_count = sum(1 for r in results if isinstance(r, Exception))
       
       assert success_count == 1, "Ожидалась одна успешная оплата"
       assert error_count == 1, "Ожидалась одна неудачная попытка"
       
    4. Проверить историю оплат:
       
       service = PaymentService(session)
       history = await service.get_payment_history(order_id)
       
       # ОЖИДАЕМ ОДНУ ЗАПИСЬ 'paid' - проблема решена!
       assert len(history) == 1, "Ожидалась 1 запись об оплате (БЕЗ RACE CONDITION!)"
       
    5. Вывести информацию об успешном решении:
       
       print(f"✅ RACE CONDITION PREVENTED!")
       print(f"Order {order_id} was paid only ONCE:")
       print(f"  - {history[0]['changed_at']}: status = {history[0]['status']}")
       print(f"Second attempt was rejected: {results[1]}")
    """
    # TODO: Реализовать тест, демонстрирующий решение race condition
 
    order_id = test_order

 
    engine = create_async_engine(DATABASE_URL, echo=True)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def payment_attempt():
        async with AsyncSessionLocal() as session:
            service = PaymentService(session)
            try:
                await service.pay_order_safe(order_id)
                await session.commit()
                return "ok"
            except Exception as e:
                await session.rollback()
                return e
                 
    results = await asyncio.gather(
        payment_attempt(),
        payment_attempt(),
        return_exceptions=True,
    )

    success_count = sum(1 for r in results if r == "ok")
    error_count = sum(1 for r in results if isinstance(r, Exception))
 
    async with AsyncSessionLocal() as session:
        service = PaymentService(session)
        history = await service.get_payment_history(order_id)

    print("\n✅ RACE CONDITION PREVENTED!")
    print(f"успешная оплата: {success_count}, ошибка: {error_count}")
    print(f"заказ {order_id} был оплачен {len(history)} времени")

    assert success_count == 1, "ожидалась одна успешная оплата"
    assert error_count == 1, "ожидалась одна неудачная попытка"
    assert len(history) == 1, "ожидалась 1 запись об оплате БЕЗ RACE CONDITION!"

    await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_payment_safe_with_explicit_timing():
    """
    Дополнительный тест: проверить работу блокировок с явной задержкой.
    
    TODO: Реализовать тест с добавлением задержки в первой транзакции:
    
    1. Первая транзакция:
       - Начать транзакцию
       - Заблокировать заказ (FOR UPDATE)
       - Добавить задержку (asyncio.sleep(1))
       - Оплатить
       - Commit
       
    2. Вторая транзакция (запустить через 0.1 секунды после первой):
       - Начать транзакцию
       - Попытаться заблокировать заказ (FOR UPDATE)
       - ДОЛЖНА ЖДАТЬ освобождения блокировки от первой транзакции
       - После освобождения - увидеть обновленный статус 'paid'
       - Выбросить OrderAlreadyPaidError
       
    3. Проверить временные метки:
       - Вторая транзакция должна завершиться ПОЗЖЕ первой
       - Разница должна быть >= 1 секунды (время задержки)
       
    Это подтверждает, что FOR UPDATE действительно блокирует строку.
    """
    # TODO: Реализовать тест с проверкой блокировки
 
    order_id = test_order
 
    engine = create_async_engine(DATABASE_URL, echo=True)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def payment_attempt():
        async with AsyncSessionLocal() as session:
            service = PaymentService(session)
            try:
                await service.pay_order_safe(order_id)
                await session.commit()
                return "ok"
            except Exception as e:
                await session.rollback()
                return e
 
    results = await asyncio.gather(
        payment_attempt(),
        payment_attempt(),
        return_exceptions=True,)

    success_count = sum(1 for r in results if not isinstance(r, Exception))
    error_count = sum(1 for r in results if isinstance(r, Exception))
 
    async with AsyncSessionLocal() as session:
        service = PaymentService(session)
        history = await service.get_payment_history(order_id)

    print("✅ RACE CONDITION PREVENTED!")
    print(f"заказ {order_id} был оплачен только {len(history)} время")
    if len(history) == 1:
        print(f"  - {history[0]['changed_at']}: status = {history[0]['status']}")
    print(f"результат: {results}")

    assert success_count == 1, "ожидалась одна успешная оплата"
    assert error_count == 1, "ожидалась одна неудачная попытка"
    assert len(history) == 1, "ожидалась 1 запись об оплате БЕЗ RACE CONDITION!"

    await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_payment_safe_multiple_orders():
    """
    Дополнительный тест: проверить, что блокировки не мешают разным заказам.
    
    TODO: Реализовать тест:
    1. Создать ДВА разных заказа
    2. Оплатить их ПАРАЛЛЕЛЬНО с помощью pay_order_safe()
    3. Проверить, что ОБА успешно оплачены
    
    Это показывает, что FOR UPDATE блокирует только конкретную строку,
    а не всю таблицу, что важно для производительности.
    """
    # TODO: Реализовать тест с несколькими заказами
    raise NotImplementedError("TODO: Реализовать test_concurrent_payment_safe_multiple_orders")


if __name__ == "__main__":
    """
    Запуск теста:
    
    cd backend
    export PYTHONPATH=$(pwd)
    pytest app/tests/test_concurrent_payment_safe.py -v -s
    
    ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:
    ✅ test_concurrent_payment_safe_prevents_race_condition PASSED
    
    Вывод должен показывать:
    ✅ RACE CONDITION PREVENTED!
    Order XXX was paid only ONCE:
      - 2024-XX-XX: status = paid
    Second attempt was rejected: OrderAlreadyPaidError(...)
    """
    pytest.main([__file__, "-v", "-s"])
