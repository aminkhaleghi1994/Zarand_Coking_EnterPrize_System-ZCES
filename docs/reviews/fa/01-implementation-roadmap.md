<div dir="rtl" align="right">

# بازنگری نقشه راه پیاده‌سازی سامانه ZCES

**تاریخ:** ۲۰۲۶-۰۸-۲۹ · **زبان:** فارسی (نسخه انگلیسی: `docs/reviews/en/`)
**ورودی‌ها:** `docs/requirements-prompt.txt` (سند کامل نیازمندی‌ها)، `frontend/DESIGN.md`، ممیزی محیط، تصمیمات کارفرما.

---

## ۱. چه چیزی می‌سازیم

یک سامانه جامع سازمانی دوزبانه (انگلیسی/فارسی) برای زرند کک و فولاد شامل: کارکنان، انبار و موجودی، درخواست کالا، ردیابی دارایی، وام و ضمانت، اعلان‌ها، گزارش‌ها، تنظیمات و ثبت کامل Audit — با معماری **Modular Monolith**:

- **بک‌اند:** FastAPI + SQLAlchemy 2.0 + Alembic + Pydantic v2 و Celery + Redis
- **فرانت‌اند:** Next.js (App Router) + TypeScript + Tailwind + shadcn/ui + TanStack Query در نقش BFF
- **داده:** PostgreSQL (کلید UUID، حذف نرم، ایندکس‌های Unique جزئی)
- **احراز هویت:** JWT + چرخش Refresh Token در کوکی HttpOnly؛ RBAC + Scope سلسله‌مراتبی (Global > Complex > Workplace)
- **استقرار:** توسعه Local روی ویندوز → یک VM اوبونتو (systemd + Nginx) → Docker در آینده

## ۲. رویکرد تحویل — ماژول به ماژول (پاسخ پرسش)

**پرسش:** آیا بهتر است هر ماژول/سرویس را پیاده کنیم، اجرا و تست کنیم و بعد سراغ ماژول بعدی برویم؟

**پاسخ: بله — با یک اصلاح.** الگوی بهینه:

1. **ابتدا پلتفرم افقی** (فاز ۱ و ۲): اسکلت، Config، پاکت خطای استاندارد، Auth، RBAC + Scope Resolver و Audit پایه. همه ماژول‌های کسب‌وکار به این‌ها وابسته‌اند؛ ساخت آن‌ها داخل یک ماژول کسب‌وکار باعث دوباره‌کاری می‌شود.
2. **سپس برش‌های عمودی** (فاز ۳ تا ۹): هر ماژول کسب‌وکار سرتاسری تحویل می‌شود — مدل‌ها → Migration → Repository (با Scope Filter) → Service → Router → تست‌ها → **صفحات فرانت‌اند** → اجرای برنامه → تست دستی Smoke → Converge → ماژول بعدی.

مقایسه رویکردها:

| رویکرد | نتیجه | دلیل |
|---|---|---|
| برش عمودی به ازای هر ماژول (انتخاب‌شده) | بهترین | بازخورد اجرایی مداوم؛ کشف زودهنگام خطاهای Scope Filter و یکپارچگی؛ برنامه همیشه قابل اجراست |
| یکجا (همه ماژول‌ها، یک مرحله تست) | بدترین | ریسک یکپارچگی انباشته می‌شود؛ تا پایان هیچ چیز قابل نمایش نیست |
| ابتدا کل بک‌اند، بعد کل فرانت‌اند | ضعیف | بازخورد دیرهنگام UI/RTL/i18n؛ یک فاز فرانت‌اند بزرگ و پرریسک |
| Microservice به ازای ماژول | رد | در تضاد با معماری مصوب Modular Monolith |

**دروازه فاز (هر فاز، بدون استثنا):** برنامه Boot می‌شود، همه تست‌ها سبز هستند و قابلیت جدید به‌صورت دستی Smoke-Test شده است. فقط پس از آن فاز بعدی با `/speckit.specify` آغاز می‌شود.

## ۳. برنامه فازها

هر فاز = یک چرخه کامل Spec Kit:
`/speckit.specify → /speckit.clarify → /speckit.plan → /speckit.analyze → /speckit.tasks → /speckit.implement → /speckit.converge` (تکرار implement/converge تا رسیدن به **Converged**).

| # | شناسه Spec | محتوا | دروازه |
|---|---|---|---|
| 0 | *(ابزارها — انجام شد)* | مخزن، Skills، فونت‌ها، spec-kit، قانون اساسی، AGENTS.md، همین بازنگری | آماده‌سازی کامل |
| 1 | `foundation-skeleton` | اسکلت بک‌اند (Config، لاگ + trace_id، پاکت خطا، healthz)؛ اسکلت فرانت‌اند (Next.js، shadcn، next-intl، فونت Kalameh، توکن‌های DESIGN.md، Layout اصلی، پوسته Login، ترنزیشن صفحات)؛ پایه Alembic + Mixinها؛ `.env.example` دو طرف؛ اسکریپت‌های اجرای توسعه؛ CI گیت‌هاب | هر دو برنامه اجرا شوند؛ healthz کد 200 |
| 2 | `auth-rbac-scope-platform` | Login/Logout/Refresh/Me؛ چرخش Refresh + تشخیص استفاده مجدد؛ کوکی + CSRF؛ مسیرهای BFF؛ مدل RBAC؛ Scope Resolver (Union، Deny ضمنی)؛ Audit پایه (Snapshot، Masking، trace_id) | ورود سرتاسری کار کند؛ تست‌های واحد Scope Resolver سبز |
| 3 | `org-user-module` | Company/Complex/Workplace + Seed؛ Employee↔User یک‌به‌یک در یک تراکنش؛ ایندکس‌های Unique جزئی (national_id، personnel_code)؛ UI تخصیص نقش/مجوز/Scope؛ صفحات کارکنان | CRUD کارمند تأیید شود؛ جلوگیری از تکراری؛ غیرفعال‌سازی به User سرایت کند |
| 4 | `warehouse-catalog-inventory` | ItemCatalog + جستجوی زنده Debounce شده (ایندکس‌دار، صفحه‌بندی‌شده)؛ Warehouse/Shelf؛ InventoryPlacement؛ StockMovement (اتمیک + FOR UPDATE)؛ هشدار کمبود | جریان موجودی تأیید شود؛ موجودی منفی ناممکن باشد |
| 5 | `item-requests-flow` | ItemRequest + خطوط؛ توضیح هدف؛ تأیید/رد/Fulfillment؛ کنترل موجودی هنگام Fulfillment؛ Audit کامل تغییر وضعیت | سناریوی کامل درخواست تا Fulfillment بگذرد |
| 6 | `asset-tracking` | AssetInstance؛ تخصیص/بازگشت؛ AssetHistory؛ رویدادهای AssetAssigned/AssetReturned | چرخه عمر دارایی تأیید شود |
| 7 | `loan-module` | LoanPolicy به ازای Workplace/سال؛ LoanRequest؛ آبشار اعتبارسنجی با ترتیب دقیق (تعداد کل عمر → تعداد سال → سقف وام فعال → سقف ضمانت فعال)؛ محاسبه سال جلالی | هر ۴ قانون اعتبارسنجی تست شود (شامل حالت Settled/Soft-Deleted) |
| 8 | `notifications-outbox-sse` | EventOutbox + Worker ارسال؛ اعلان In-app؛ استریم SSE؛ قانون Critical بودن | اعلان زنده در مرورگر دریافت شود |
| 9 | `settings-reports-dashboard` | تنظیمات + Feature Flag (با Audit)؛ داشبورد مدیریتی؛ گزارش‌های موجودی/درخواست/وام/حساس؛ خروجی Excel با Masking مبتنی بر سطح دسترسی | گزارش‌ها و خروجی در هر دو زبان تأیید شوند |
| 10 | `hardening-observability` | Rate Limiting (Auth + عملیات حساس)؛ Security Headerها؛ کش Redis برای مجوزها و جستجوی کاتالوگ؛ `/metrics` پرومتئوس؛ بازبینی لاگ ساختاریافته؛ pre-commit | چک‌لیست امنیت سبز شود |
| 11 | `vm-deployment-recovery` | سرویس‌های systemd، Nginx، HTTPS با Certbot، seed_prod، بکاپ/بازیابی pg_dump + مانور، Health Check، Runbook، **راهنمای اجرای تک‌فرمانی** | کارفرما خودش برنامه را Deploy و اجرا کند |
| بعداً | `dockerization` | طبق نیازمندی‌ها §33، پس از پایدار شدن Local/VM | — |

**دانه‌بندی وظایف:** عمداً ریز. کارفرما صراحتاً افزایش تعداد وظایف را به از دست رفتن جزئیات ترجیح داده — انتظار ۲۰ تا ۶۰ وظیفه در هر فاز را داشته باشید.

## ۴. تصمیمات قطعی‌شده (۲۰۲۶-۰۸-۲۹)

1. مخزن Monorepo در همین پوشه ZCES (ریشه همین Repo).
2. Redis از طریق **WSL2** روی همین ماشین ویندوزی.
3. واریانت **FaNum** فونت Kalameh برای زبان فارسی (ارقام فارسی بومی)؛ واریانت Standard برای انگلیسی.
4. **برش‌های عمودی درهم‌تنیده** — هر فاز شامل بک‌اند + UI + تست‌ها تحویل می‌شود.
5. Skills در **سطح پروژه** (`.opencode/skills/`) نصب شوند + `find-skills` سراسری (`~/.agents/skills/`).
6. **CI پایه GitHub Actions از فاز ۱** (ruff/mypy/pytest + eslint/tsc/next build).

## ۵. نتایج ممیزی محیط (فاز ۰)

- git نسخه 2.45.1، Node 24.11، npm 11.5.1، Python 3.12.0، uv 0.11.23 — همه سالم
- سرویس PostgreSQL 18 روی پورت 5432 در حال اجرا — سالم (نیازمندی 16+ است؛ 18 پوشش می‌دهد)
- Redis — **موجود نبود** (پورت 6379 بسته) → با تصمیم WSL2 حل شد
- پورت‌های 3000 و 8000 آزاد

## ۶. نگاشت معیارهای موفقیت

معیارهای §35 سند نیازمندی‌ها بین دروازه‌های فازها پخش شده‌اند: صحت RBAC/Scope (فاز ۲–۳)، تراکنشی بودن Employee+User و جلوگیری از تکرار (فاز ۳)، یکپارچگی موجودی و StockMovement (فاز ۴)، جریان درخواست (فاز ۵)، ردیابی دارایی (فاز ۶)، اعتبارسنجی وام (فاز ۷)، Audit صددرصدی + Masking (فاز ۲ و مستمر)، خطاهای استاندارد + trace_id (فاز ۱–۲)، قابلیت Deploy روی VM (فاز ۱۱). هر معیار تنها زمانی محقق است که دروازه فازِ مالک آن بگذرد.

</div>
