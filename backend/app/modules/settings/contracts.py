"""Public contract of the settings module for other modules (constitution VI).

Cross-module consumers import ONLY from this file. Contract reads fall
back to a default when the row is missing, so consumers never hard-fail
on a seed gap.
"""

from typing import Any

from sqlalchemy.orm import Session

__all__ = [
    "get_setting",
    "get_setting_bool",
]


def get_setting(session: Session, key: str, default: Any = None) -> Any:
    from app.modules.settings import service

    return service.get_setting(session, key, default)


def get_setting_bool(session: Session, key: str, default: bool = False) -> bool:
    from app.modules.settings import service

    return service.get_setting_bool(session, key, default)
