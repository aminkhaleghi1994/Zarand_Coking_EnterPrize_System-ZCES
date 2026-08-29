<div dir="rtl" align="right">

# بازنگری Skillها و ابزارهای ZCES

**تاریخ:** ۲۰۲۶-۰۸-۲۹ · **زبان:** فارسی (نسخه انگلیسی: `docs/reviews/en/`)

## ۱. ممیزی زنجیره ابزار (این ماشین)

| ابزار | نسخه | وضعیت |
|---|---|---|
| git | 2.45.1 (ویندوز) | سالم |
| Node.js | 24.11.0 | سالم |
| npm | 11.5.1 | سالم |
| Python | 3.12.0 | سالم (هدف بک‌اند) |
| uv | 0.11.23 | سالم (نصب‌کننده spec-kit) |
| PostgreSQL | 18 (سرویس `postgresql-x64-18`) | در حال اجرا روی 5432 |
| Redis | — | **موجود نیست** → از طریق WSL2 تأمین می‌شود (§۵) |
| specify CLI | 1.0.1 | نصب‌شده با `uv tool install specify-cli` |

## ۲. Skillهای نصب‌شده

### سطح پروژه (`.opencode/skills/`)

| Skill | منبع | هدف |
|---|---|---|
| ui-ux-pro-max (به‌همراه design، design-system، ui-styling، brand، banner-design، slides) | nextlevelbuilder/ui-ux-pro-max-skill (درخواست کارفرما) | تولید Design System، هوشمندی سبک UI، ۱۹۲ قاعده صنعتی |
| frontend-design | anthropics/skills (درخواست کارفرما) | راهنمای طراحی بصری متمایز و هدفمند |
| react-best-practices | vercel-labs/agent-skills | بهترین شیوه‌های React/Next.js |
| web-design-guidelines | vercel-labs/agent-skills | راهنمای کیفیت طراحی وب |
| shadcn | رسمی shadcn/ui | کار با Registry کامپوننت‌ها، CLI و سفارشی‌سازی |
| tdd | mattpocock/skills | انضباط توسعه تست‌محور |
| code-review | mattpocock/skills | بازبینی ساختاریافته کد |
| domain-modeling | mattpocock/skills | طراحی دامنه‌محور و ADR |

### سطح سراسری (`~/.agents/skills/`)

| Skill | منبع | هدف |
|---|---|---|
| find-skills | vercel-labs/skills (از skills.sh، درخواست کارفرما) | کشف و نصب Skill در همه پروژه‌ها |

نکته: CLIیِ `npx skillsadd` در حال حاضر به رجیستری متفاوتی (skills.ws) اشاره می‌کند و لیست آن پاسخ نداد؛ بنابراین Skillها مستقیماً از منابع رسمی گیت‌هابشان نصب شدند — محتوا یکسان است و اصالت با فهرست skills.sh تطبیق داده شد.

## ۳. راه‌اندازی Spec Kit

- `specify init --here --force --non-interactive --integration opencode`
- دستورها در `.opencode/commands/speckit.*.md` در دسترس‌اند:
  specify، clarify، plan، analyze، tasks، implement، converge، checklist،
  constitution و taskstoissues.
- قانون اساسی پروژه در `.specify/memory/constitution.md` تصویب شد (نسخه 1.0.0) —
  ۸ اصل + محدودیت‌های معماری + دروازه‌های گردش کار + حکمرانی.
- گردش کار هر فاز (الزام‌آور): specify → clarify → plan → analyze → tasks →
  implement → converge؛ تکرار implement/converge تا رسیدن به Converged؛
  دروازه فاز (اجرای برنامه، تست‌های سبز، Smoke تست دستی) پیش از فاز بعدی.

## ۴. راه‌اندازی فونت Kalameh (انجام‌شده در فاز ۰)

- محل نهایی: `frontend/src/fonts/kalameh/`:
  - `standard/` — ۸ فایل (woff2 + woff × Thin/Regular/Bold/Black) برای `en`
  - `fa-num/` — ۸ فایل (woff2 + woff × ۴ وزن) برای `fa` (ارقام فارسی)
  - `FontLicense.txt` — لایسنس FontIran؛ **باید همیشه کنار فونت‌ها بماند**.
    ⚠ جای کد ۶ رقمی لایسنس FontIran خالی است — در صورت داشتن کد، آن را وارد کنید.
- پوشه مبدأ `kalameh(Eco) @RealPentesting` پس از تأیید کپی (۱۷ فایل) حذف شد.
  فایل‌های EOT حذف کردند (مخصوص IE و برای Next.js غیرضروری).
- نگاشت طراحی (قطعی — به `frontend/AGENTS.md` مراجعه کنید): Kalameh جایگزین
  Forma DJR Micro؛ نگاشت وزن‌ها 400→Regular، 500/600→Bold 700، 900→Black؛
  بدون وزن‌های ساختگی (Faux Bold).

## ۵. Redis روی ویندوز — تصمیم: WSL2

Redis برای کش، Broker سیلی و توزیع SSE لازم است. تصمیم: اجرای Redis داخل WSL2 (نزدیک‌ترین حالت به VM اوبونتوی Production).

راه‌اندازی (در فاز ۱ انجام می‌شود):

```powershell
wsl --install -d Ubuntu            # اگر هنوز دیسترو ندارید
wsl sudo apt-get update && sudo apt-get install -y redis-server
wsl sudo service redis-server start
wsl redis-cli ping                 # انتظار: PONG
```

`REDIS_HOST`/`REDIS_URL` در `.env` به میزبان WSL2 اشاره می‌کنند (تنها از طریق Env — هرگز Hardcode نمی‌شود).

## ۶. CI (تصمیم: پایه، از فاز ۱)

GitHub Actions روی هر Push/PR:

- وظیفه بک‌اند: ruff (Lint)، mypy (تایپ‌ها)، pytest (واحد + یکپارچگی)
- وظیفه فرانت‌اند: eslint، tsc --noEmit، next build

Deploy روی VM تا فاز ۱۱ (تهیه Runbook) به‌صورت دستی باقی می‌ماند.

</div>
