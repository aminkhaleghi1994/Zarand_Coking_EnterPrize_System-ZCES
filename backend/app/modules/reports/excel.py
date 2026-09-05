"""Excel workbook builder for report exports (research R4, T014).

openpyxl write-only mode; one sheet per report; bilingual headers chosen
by locale (`fa` gets an RTL sheet view and Jalali dates, `en` Gregorian
ISO). Rows are the SAME scope+masking-filtered projections the JSON
endpoints return — masked values are written as masked strings, never raw.
"""

import io
from datetime import UTC, datetime
from typing import Any

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from app.common.jalali import gregorian_to_jalali

_HEADERS: dict[str, tuple[tuple[str, str], ...]] = {
    "inventory": (
        ("item", "کالا"),
        ("code", "کد"),
        ("unit", "واحد"),
        ("warehouse", "انبار"),
        ("shelf", "قفسه"),
        ("quantity", "موجودی"),
        ("threshold", "حد مجاز"),
        ("below_min", "کمتر از حد"),
    ),
    "requests": (
        ("id", "شناسه"),
        ("status", "وضعیت"),
        ("requested_by", "درخواست‌کننده"),
        ("purpose", "شرح هدف"),
        ("lines", "تعداد ردیف"),
        ("created_at", "تاریخ ثبت"),
        ("decided_at", "تاریخ تصمیم"),
        ("fulfilled_at", "تاریخ تأمین"),
    ),
    "loans": (
        ("workplace", "محل کار"),
        ("year", "سال"),
        ("requests_total", "کل درخواست‌ها"),
        ("requests_pending", "در انتظار"),
        ("requests_active", "فعال"),
        ("requests_settled", "تسویه‌شده"),
        ("requests_cancelled", "لغوشده"),
        ("active_loan_commitment", "تعهد فعال وام"),
        ("active_guarantee_commitment", "تعهد فعال ضمانت"),
        ("policy_max_loan", "سقف وام"),
        ("policy_max_guarantee", "سقف ضمانت"),
    ),
    "audit": (
        ("id", "شناسه"),
        ("actor", "کاربر انجام‌دهنده"),
        ("action", "عملیات"),
        ("entity_type", "نوع موجودیت"),
        ("entity_id", "شناسه موجودیت"),
        ("before", "قبل از تغییر"),
        ("after", "بعد از تغییر"),
        ("trace_id", "شناسه رهگیری"),
        ("created_at", "تاریخ"),
    ),
}


def _format_timestamp(value: datetime | None, locale: str) -> str:
    if value is None:
        return ""
    moment = value if value.tzinfo else value.replace(tzinfo=UTC)
    if locale == "fa":
        jy, jm, jd = gregorian_to_jalali(moment.date())
        return f"{jy:04d}/{jm:02d}/{jd:02d} {moment:%H:%M}"
    return f"{moment:%Y-%m-%d %H:%M}"


def _bool(value: bool, locale: str) -> str:
    return ("بله" if locale == "fa" else "yes") if value else (
        "خیر" if locale == "fa" else "no"
    )


def _sheet_rows(report: str, rows: list[Any], locale: str) -> list[list[Any]]:
    if report == "inventory":
        return [
            [
                row.item_name_fa if locale == "fa" else row.item_name,
                row.item_code or "",
                row.unit,
                row.warehouse_name,
                row.shelf_code,
                row.quantity,
                row.threshold,
                _bool(row.below_min, locale),
            ]
            for row in rows
        ]
    if report == "requests":
        return [
            [
                str(row.id),
                row.status,
                row.requested_by_email or "",
                row.purpose_description,
                row.line_count,
                _format_timestamp(row.created_at, locale),
                _format_timestamp(row.decided_at, locale),
                _format_timestamp(row.fulfilled_at, locale),
            ]
            for row in rows
        ]
    if report == "loans":
        return [
            [
                row.workplace_name_fa if locale == "fa" else row.workplace_name,
                row.year,
                row.requests_total,
                row.requests_pending,
                row.requests_active,
                row.requests_settled,
                row.requests_cancelled,
                row.active_loan_commitment,
                row.active_guarantee_commitment,
                row.policy_max_loan if row.policy_max_loan is not None else "",
                row.policy_max_guarantee if row.policy_max_guarantee is not None else "",
            ]
            for row in rows
        ]
    if report == "audit":
        return [
            [
                row.id,
                row.actor_user_id or "",
                row.action,
                row.entity_type,
                row.entity_id or "",
                _snapshot_text(row.before_snapshot),
                _snapshot_text(row.after_snapshot),
                row.trace_id or "",
                _format_timestamp(row.created_at, locale),
            ]
            for row in rows
        ]
    raise ValueError(f"Unknown report: {report}")


def _snapshot_text(snapshot: dict[str, object] | None) -> str:
    if not snapshot:
        return ""
    parts = [f"{key}={value}" for key, value in snapshot.items()]
    return "; ".join(parts)


def build_report_workbook(
    report: str, rows: list[Any], locale: str
) -> io.BytesIO:
    """Build the report workbook in memory and return the buffer.

    ``rows`` are the report DTOs (already scope- and masking-filtered);
    an empty list yields a headers-only workbook.
    """
    if report not in _HEADERS:
        raise ValueError(f"Unknown report: {report}")

    workbook = Workbook(write_only=True)
    sheet: Worksheet = workbook.create_sheet(title=report)

    # In write-only mode the sheet view must be configured BEFORE the first
    # append (later mutations do not persist).
    if locale == "fa":
        sheet.sheet_view.rightToLeft = True

    header_row = [
        (persian if locale == "fa" else english)
        for english, persian in _HEADERS[report]
    ]
    sheet.append(header_row)

    for row in _sheet_rows(report, rows, locale):
        sheet.append(row)

    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


REPORT_FILENAMES: dict[str, tuple[str, str]] = {
    "inventory": ("inventory-report", "گزارش-موجودی"),
    "requests": ("requests-report", "گزارش-درخواست‌ها"),
    "loans": ("loans-report", "گزارش-وام"),
    "audit": ("audit-report", "گزارش-ممیزی"),
}


def export_filename(report: str, locale: str) -> str:
    base = REPORT_FILENAMES[report][0 if locale != "fa" else 1]
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d")
    return f"{base}-{stamp}.xlsx"
