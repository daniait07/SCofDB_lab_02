"""Доменная сущность пользователя."""

from dataclasses import dataclass, field
import re
import uuid
from datetime import datetime

from .exceptions import InvalidEmailError


# TODO: Реализовать класс User
# - Использовать @dataclass
# - Поля: email, name, id, created_at
# - Реализовать валидацию email в __post_init__
# - Regex: r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

@dataclass
class User:
    email: str
    name: str = ""
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not self.email or self.email.strip() == "":
            raise InvalidEmailError(self.email)
 
        if "@" not in self.email:
            raise InvalidEmailError(self.email)

        local, _, domain = self.email.partition("@")
        if not local or not domain:
            raise InvalidEmailError(self.email)
 
        if not EMAIL_REGEX.match(self.email):
            raise InvalidEmailError(self.email)
