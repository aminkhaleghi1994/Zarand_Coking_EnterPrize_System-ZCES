<div dir="rtl" align="right">

# بازنگری لایه‌های مهندسی نرم‌افزار ZCES

**تاریخ:** ۲۰۲۶-۰۸-۲۹ · **زبان:** فارسی (نسخه انگلیسی: `docs/reviews/en/`)
**پرسش بازنگری‌شده:** آیا همه ۱۳ لایه مهندسی نرم‌افزار باید برای این پروژه پیاده‌سازی شوند؟

**پاسخ کوتاه: خیر.** این سامانه یک سیستم سازمانی Intranet با مقیاس یک VM داخلی است. شش لایه به‌صورت کامل، شش لایه به‌صورت سبک و متناسب با نیاز واقعی پیاده می‌شوند و دو لایه به‌طور صریح از نسخه اول خارج هستند. پیاده‌سازی کامل هر ۱۳ لایه بدون سود، هزینه و ریسک اضافه می‌کند — خود سند نیازمندی‌ها نیز Docker، ابر و Scale-Out را به آینده موکول کرده است.

## جدول نتیجه‌گیری

| # | لایه | نتیجه | دامنه در ZCES | فاز |
|---|---|---|---|---|
| 01 | Front-End Foundation | **کامل** | Next.js + TS strict + Tailwind + shadcn/ui + TanStack Query + RHF/Zod + next-intl (en/fa) + RTL + فونت Kalameh + کاملاً Responsive + انیمیشن‌های نرم | P1+ |
| 02 | Apps & Back-End | **کامل** | Modular Monolith فست‌اپی (۶ ماژول)، Celery Workerها، استریم SSE | P1–9 |
| 03 | DB & Storage | **کامل** | PostgreSQL (UUID، حذف نرم، ایندکس Unique جزئی، Constraintها) + Alembic + Redis. بدون Object Storage در v1 | P1+ |
| 04 | Authentications & Permissions | **کامل** | JWT + چرخش Refresh در کوکی HttpOnly، الگوی BFF، RBAC + Scope Resolver، CSRF، Masking | P2–3 |
| 05 | Hosting & Deployment | **محدود** | توسعه Local ویندوز + یک VM اوبونتو (systemd، Nginx، HTTPS با Certbot). بدون هاست ابری | P11 |
| 06 | Cloud & Computing | **خارج از نسخه اول** | VM داخلی. Config مبتنی بر Environment قابلیت انتقال آینده را حفظ می‌کند؛ فعلاً چیز دیگری لازم نیست | — |
| 07 | CI/CD & Version Control | **محدود** | Git + مدل Branching + Conventional Commits + SemVer از روز اول؛ GitHub Actions برای Lint/Test در هر Push؛ Deploy روی VM اسکریپت‌شده اما با اجرای دستی | P1+ (CI)، P11 (Deploy) |
| 08 | Rate Limiting | **سبک** | محدودیت مبتنی بر Redis فقط روی End-pointهای Auth و عملیات حساس. بدون لایه API Gateway | P10 |
| 09 | Security & Row Level Security | **هسته‌ای — در سطح برنامه** | Scope Filter اجباری روی همه Queryها همان RLS نسخه اول است (در لایه Repository + تست‌ها اعمال می‌شود). به‌علاوه CSRF/XSS/SQLi، Masking و انضباط Secretها. RLS بومی PostgreSQL = دفاع لایه‌ای اختیاری در آینده | P2، P10 |
| 10 | Caching & CDN | **سبک** | کش Redis برای مجوزها و جستجوی زنده کاتالوگ. بدون CDN — برنامه Intranet است و لبه عمومی ندارد | P10 |
| 11 | Load Balancing & Scaling | **خارج از نسخه اول** | یک VM، Nginx در جلو، چند Uvicorn Worker. Stateless بودن (JWT + Redis) امکان Scale-Out افقی آینده را حفظ می‌کند | — |
| 12 | Error Tracking & Logs | **کامل (با ابزار سبک)** | لاگ JSON ساختاریافته، همبستگی trace_id بین فرانت‌اند↔بک‌اند↔Workerها، Sentry اختیاری از طریق Env، `/metrics` پرومتئوس | P1 (trace)، P10 (metrics) |
| 13 | Availability & Recovery | **سبک اما ضروری** | بکاپ/بازیابی pg_dump + مانور عملی، Health Check، سیاست Restart سیستم‌دی، Runbook. بدون HA چندگرهی | P11 |

## استدلال موارد خارج‌شده

- **لایه 06 (ابر):** سند نیازمندی‌ها توسعه Local ویندوز و Deploy روی VM را الزامی کرده و صراحتاً «Docker زودهنگام» را نهاده است. ابر هیچ ارزشی به یک سیستم Intranet اضافه نمی‌کند و با راهکار کاهش ریسک §36.5 در تضاد است.
- **لایه 11 (توزیع بار/مقیاس‌پذیری):** جامعه کاربر، کارکنان یک شرکت هستند (حداکثر چند هزار نفر، به احتمال زیاد صدها نفر). یک VM با Nginx و چند Uvicorn Worker هدف P95 < 200ms را راحت پوشش می‌دهد. معماری Stateless می‌ماند تا بعدها بدون بازنویسی، این لایه اضافه شود.
- **RLS بومی PostgreSQL:** فیلتر Scope در سطح برنامه صرف‌نظر از هر چیز دیگری توسط سند نیازمندی‌ها الزامی است (Permission و Scope روی هر Query)، پس RLS دیتابیس مکانیزمی را تکرار می‌کند که به هر حال باید بسازیم و تست کنیم. اگر مدل تهدید تغییر کند، به‌عنوان دفاع لایه‌ای بازبینی خواهد شد.

## جای هر لایه در نقشه راه

به `01-implementation-roadmap.md` §۳ مراجعه کنید. پوشش لایه‌ها در محتوای فازها تنیده شده است (ستون سمت چپ جدول بالا) — هیچ لایه‌ای بدون فازِ مالک باقی نمی‌ماند و هیچ فازی زیرساختی را وارد نمی‌کند که سند نیازمندی‌ها توجیهش نکرده باشد.

</div>
