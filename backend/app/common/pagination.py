from typing import TypeVar

from pydantic import BaseModel

ItemT = TypeVar("ItemT")


class Page[ItemT](BaseModel):
    items: list[ItemT]
    page: int
    page_size: int
    total: int
