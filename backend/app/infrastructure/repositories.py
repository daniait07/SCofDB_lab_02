"""Реализация репозиториев с использованием SQLAlchemy."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.user import User
from app.domain.order import Order, OrderItem, OrderStatus, OrderStatusChange


class UserRepository:
    """Репозиторий для User."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # TODO: Реализовать save(user: User) -> None
    # Используйте INSERT ... ON CONFLICT DO UPDATE
    async def save(self, user: User) -> None:
        result = await self.session.execute(
            text(
                "UPDATE users "
                "SET email = :email, name = :name, created_at = :created_at "
                "WHERE id = :id"),
            {"id": str(user.id), "email": user.email, "name": user.name or "", "created_at": user.created_at},)
        if result.rowcount == 0:
            await self.session.execute(
                text(
                    "INSERT INTO users (id, email, name, created_at) "
                    "VALUES (:id, :email, :name, :created_at)"),
                {"id": str(user.id), "email": user.email, "name": user.name or "", "created_at": user.created_at},)

    # TODO: Реализовать find_by_id(user_id: UUID) -> Optional[User]
    async def find_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        result = await self.session.execute(
            text(
                "SELECT id, email, name, created_at "
                "FROM users "
                "WHERE id = :id"),
            {"id": str(user_id)},)
        row = result.fetchone()
        if not row:
            return None
        return User(id=uuid.UUID(str(row[0])), email=row[1], name=row[2], created_at=row[3])

    # TODO: Реализовать find_by_email(email: str) -> Optional[User]
    async def find_by_email(self, email: str) -> Optional[User]:
        result = await self.session.execute(
            text(
                "SELECT id, email, name, created_at "
                "FROM users "
                "WHERE email = :email"),
            {"email": email},)
        row = result.fetchone()
        if not row:
            return None
        return User(id=uuid.UUID(str(row[0])), email=row[1], name=row[2], created_at=row[3])

    # TODO: Реализовать find_all() -> List[User]
    async def find_all(self) -> List[User]:
        result = await self.session.execute(
            text(
                "SELECT id, email, name, created_at "
                "FROM users "
                "ORDER BY created_at ASC"),)
        users: List[User] = []
        for row in result.fetchall():
            users.append(User(id=uuid.UUID(str(row[0])), email=row[1], name=row[2], created_at=row[3]))
        return users


class OrderRepository:
    """Репозиторий для Order."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # TODO: Реализовать save(order: Order) -> None
    # Сохранить заказ, товары и историю статусов
    async def save(self, order: Order) -> None:
        await self.session.execute(
            text(
                "INSERT INTO orders (id, user_id, status, total_amount, created_at) "
                "VALUES (:id, :user_id, :status, :total_amount, :created_at) "
                "ON CONFLICT(id) DO UPDATE SET "
                "user_id = EXCLUDED.user_id, "
                "status = EXCLUDED.status, "
                "total_amount = EXCLUDED.total_amount, "
                "created_at = EXCLUDED.created_at"),
            {
                "id": str(order.id),
                "user_id": str(order.user_id),
                "status": order.status.value,
                "total_amount": float(order.total_amount),
                "created_at": order.created_at,
            },)

        await self.session.execute(
            text("DELETE FROM order_items WHERE order_id = :oid"),
            {"oid": str(order.id)},)
        await self.session.execute(
            text("DELETE FROM order_status_history WHERE order_id = :oid"),
            {"oid": str(order.id)},)

        for item in order.items:
            await self.session.execute(
                text(
                    "INSERT INTO order_items "
                    "(id, order_id, product_name, price, quantity, subtotal) "
                    "VALUES (:id, :order_id, :product_name, :price, :quantity, :subtotal)"),
                {
                    "id": str(item.id),
                    "order_id": str(order.id),
                    "product_name": item.product_name,
                    "price": float(item.price),
                    "quantity": item.quantity,
                    "subtotal": float(item.subtotal),
                },)

        for h in order.status_history:
            await self.session.execute(
                text(
                    "INSERT INTO order_status_history "
                    "(id, order_id, status, changed_at) "
                    "VALUES (:id, :order_id, :status, :changed_at)"),
                {
                    "id": str(h.id),
                    "order_id": str(order.id),
                    "status": h.status.value,
                    "changed_at": h.changed_at,
                },)

    # TODO: Реализовать find_by_id(order_id: UUID) -> Optional[Order]
    # Загрузить заказ со всеми товарами и историей
    # Используйте object.__new__(Order) чтобы избежать __post_init__
    async def _load_order_core(self, row) -> Order:
        order = object.__new__(Order)
        order.id = row[0] if isinstance(row[0], uuid.UUID) else uuid.UUID(str(row[0]))
        order.user_id = row[1] if isinstance(row[1], uuid.UUID) else uuid.UUID(str(row[1]))
        order.status = OrderStatus(row[2])
        order.total_amount = Decimal(str(row[3]))
        order.created_at = row[4]
        order.items = []
        order.status_history = []
        return order
    
    async def find_by_id(self, order_id: uuid.UUID) -> Optional[Order]:
        result = await self.session.execute(
            text(
                "SELECT id, user_id, status, total_amount, created_at "
                "FROM orders "
                "WHERE id = :id"),
            {"id": str(order_id)},)
        row = result.fetchone()
        if not row:
            return None
        order = await self._load_order_core(row)

        items_res = await self.session.execute(
            text(
                "SELECT id, product_name, price, quantity "
                "FROM order_items "
                "WHERE order_id = :oid"),
            {"oid": str(order_id)},)
        for r in items_res.fetchall():
            item = OrderItem(
                id=uuid.UUID(str(r[0])),
                product_name=r[1],
                price=Decimal(str(r[2])),
                quantity=int(r[3]),)
            item.order_id = order.id
            order.items.append(item)

        hist_res = await self.session.execute(
            text(
                "SELECT id, status, changed_at "
                "FROM order_status_history "
                "WHERE order_id = :oid "
                "ORDER BY changed_at ASC"),
            {"oid": str(order_id)},)
        for r in hist_res.fetchall():
            h = OrderStatusChange(
                id=uuid.UUID(str(r[0])),
                order_id=order.id,
                status=OrderStatus(r[1]),
                changed_at=r[2],)
            order.status_history.append(h)

        return order

    # TODO: Реализовать find_by_user(user_id: UUID) -> List[Order]
    async def find_by_user(self, user_id: uuid.UUID) -> List[Order]:
        result = await self.session.execute(
            text(
                "SELECT id, user_id, status, total_amount, created_at "
                "FROM orders "
                "WHERE user_id = :uid "
                "ORDER BY created_at ASC"),
            {"uid": str(user_id)},)
        orders: List[Order] = []
        for row in result.fetchall():
            orders.append(await self._load_order_core(row))
        return orders

    # TODO: Реализовать find_all() -> List[Order]
    async def find_all(self) -> List[Order]:
        result = await self.session.execute(
            text(
                "SELECT id, user_id, status, total_amount, created_at "
                "FROM orders "
                "ORDER BY created_at ASC"),)
        orders: List[Order] = []
        for row in result.fetchall():
            orders.append(await self._load_order_core(row))
        return orders
