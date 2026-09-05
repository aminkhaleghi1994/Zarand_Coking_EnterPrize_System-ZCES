"""Settings endpoints (contracts/reports-settings-endpoints.md, US4).

Global resource: `require_operation` gates the permission + scope
assignment; the fixed key set is validated by the schemas/service.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common.pagination import Page
from app.common.scope import ScopeContext
from app.core.database import get_db
from app.modules.settings import service
from app.modules.settings.schemas import SettingOut, SettingUpdateIn
from app.modules.user.dependencies import require_permission
from app.modules.user.schemas import PageParams

router = APIRouter(tags=["settings"])

require_setting_read = require_permission("settings:setting:read")
require_setting_update = require_permission("settings:setting:update")


@router.get("/settings", response_model=Page[SettingOut])
def get_settings(
    params: PageParams = Depends(),
    context: ScopeContext = Depends(require_setting_read),
    session: Session = Depends(get_db),
) -> Page[SettingOut]:
    rows = service.list_settings(session)
    start = (params.page - 1) * params.page_size
    page_rows = rows[start : start + params.page_size]
    return Page(
        items=[SettingOut.model_validate(row) for row in page_rows],
        page=params.page,
        page_size=params.page_size,
        total=len(rows),
    )


@router.patch("/settings/{key}", response_model=SettingOut)
def patch_setting(
    key: str,
    payload: SettingUpdateIn,
    context: ScopeContext = Depends(require_setting_update),
    session: Session = Depends(get_db),
) -> SettingOut:
    setting = service.update_setting(
        session, context, key, payload.value, payload.version
    )
    return SettingOut.model_validate(setting)
