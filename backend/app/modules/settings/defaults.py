"""Fixed settings key set with typed defaults (research R2, data-model.md).

The key set is code-defined: the service layer rejects unknown keys, the
seed inserts these defaults idempotently, and contract readers fall back
to the default when a row is missing — a missing row never breaks a
consumer.
"""

from typing import Any

ALERTING_LOW_STOCK_ENABLED = "alerting.low_stock_enabled"
ALERTING_LOW_STOCK_NOTIFY_BROADCAST = "alerting.low_stock_notify_broadcast"
NOTIFICATIONS_DEFAULT_RECIPIENTS = "notifications.default_recipients"
REQUESTS_APPROVAL_REQUIRE_NOTE = "requests.approval_require_note"
DASHBOARD_SHOW_ALERTS_BREAKDOWN = "dashboard.show_alerts_breakdown"
DASHBOARD_SHOW_REQUESTS_BREAKDOWN = "dashboard.show_requests_breakdown"
FLAGS_LOAN_MODULE_ENABLED = "flags.loan_module_enabled"
FLAGS_ASSET_MODULE_ENABLED = "flags.asset_module_enabled"


class SettingDefault:
    __slots__ = (
        "key",
        "value",
        "value_type",
        "description",
        "description_fa",
    )

    def __init__(
        self,
        key: str,
        value: Any,
        value_type: str,
        description: str,
        description_fa: str,
    ) -> None:
        self.key = key
        self.value = value
        self.value_type = value_type
        self.description = description
        self.description_fa = description_fa


SETTING_DEFAULTS: tuple[SettingDefault, ...] = (
    SettingDefault(
        ALERTING_LOW_STOCK_ENABLED,
        True,
        "boolean",
        "Raise in-app notifications when stock drops below the item threshold",
        "ارسال اعلان داخل سامانه هنگام افت موجودی به زیر حد مجاز کالا",
    ),
    SettingDefault(
        ALERTING_LOW_STOCK_NOTIFY_BROADCAST,
        True,
        "boolean",
        "Low-stock notifications go to all scope-covered readers (false: recipients list only)",
        "اعلان کمبود موجودی برای همه دارندگان دسترسی (غیرفعال: فقط فهرست گیرندگان)",
    ),
    SettingDefault(
        NOTIFICATIONS_DEFAULT_RECIPIENTS,
        [],
        "json",
        "Fallback notification recipient user ids when broadcast is off",
        "گیرندگان پیش‌فرض اعلان‌ها در حالت غیر پخشی",
    ),
    SettingDefault(
        REQUESTS_APPROVAL_REQUIRE_NOTE,
        True,
        "boolean",
        "Approve/reject decisions on item requests require a note",
        "تأیید یا رد درخواست کالا نیازمند توضیح است",
    ),
    SettingDefault(
        DASHBOARD_SHOW_ALERTS_BREAKDOWN,
        True,
        "boolean",
        "Show the low-stock alerts breakdown card on the dashboard",
        "نمایش کارت تفکیک هشدارهای کمبود در داشبورد",
    ),
    SettingDefault(
        DASHBOARD_SHOW_REQUESTS_BREAKDOWN,
        True,
        "boolean",
        "Show the item-requests breakdown card on the dashboard",
        "نمایش کارت تفکیک درخواست‌های کالا در داشبورد",
    ),
    SettingDefault(
        FLAGS_LOAN_MODULE_ENABLED,
        True,
        "boolean",
        "Feature flag: loans & guarantees module visible",
        "فلگ ویژگی: نمایش ماژول وام و ضمانت",
    ),
    SettingDefault(
        FLAGS_ASSET_MODULE_ENABLED,
        True,
        "boolean",
        "Feature flag: asset tracking module visible",
        "فلگ ویژگی: نمایش ماژول ردیابی اموال",
    ),
)

SETTING_KEYS: frozenset[str] = frozenset(item.key for item in SETTING_DEFAULTS)

_DEFAULTS_BY_KEY: dict[str, SettingDefault] = {
    item.key: item for item in SETTING_DEFAULTS
}


def default_for(key: str) -> SettingDefault | None:
    return _DEFAULTS_BY_KEY.get(key)
