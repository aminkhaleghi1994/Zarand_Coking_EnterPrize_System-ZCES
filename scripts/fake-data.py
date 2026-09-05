"""Fill the dev database with realistic fake data through the live API.

Everything goes through the real endpoints so audit entries, stock movements,
low-stock alert episodes and asset history build exactly as in production.

Usage (backend venv, backend running):
    python ../scripts/fake-data.py            # from backend/
    python scripts/fake-data.py               # from repo root

Reads backend/.env for INITIAL_ADMIN_EMAIL/PASSWORD. Safe to re-run: every
record carries a unique run tag, so repeated runs simply add more data.
"""

from __future__ import annotations

import os
import random
import sys
import uuid
from pathlib import Path

import httpx
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
BASE_URL = os.environ.get("ZCES_BACKEND_URL", "http://127.0.0.1:8000/api/v1")
FAKE_PASSWORD = "Fake@12345"

random.seed(20260901)


def env_value(key: str) -> str | None:
    env_path = BACKEND_DIR / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(key) and "=" in line:
            return line.split("=", 1)[1].strip().strip('"')
    return None


def api(
    client: httpx.Client,
    method: str,
    path: str,
    token: str | None = None,
    json: dict | list | None = None,
    expect: tuple[int, ...] = (200, 201),
) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = client.request(method, f"{BASE_URL}/{path}", json=json, headers=headers, timeout=30)
    if response.status_code not in expect:
        raise RuntimeError(
            f"{method} /{path} -> {response.status_code}: {response.text[:300]}"
        )
    return response.json() if response.content else {}


FIRST_NAMES = [
    ("Ali", "علی"), ("Mohammad", "محمد"), ("Reza", "رضا"), ("Hossein", "حسین"),
    ("Mehdi", "مهدی"), ("Amir", "امیر"), ("Saeed", "سعید"), ("Fatemeh", "فاطمه"),
]
LAST_NAMES = [
    ("Ahmadi", "احمدی"), ("Mohammadi", "محمدی"), ("Rezaei", "رضایی"), ("Hosseini", "حسینی"),
    ("Karimi", "کریمی"), ("Mousavi", "موسوی"), ("Jafari", "جعفری"), ("Naderi", "نادری"),
]

ITEMS = [
    ("Ball bearing 6204", "بلبرینگ ۶۲۰۴", "ad"),
    ("Work gloves leather", "دستکش کار چرمی", "pair"),
    ("Welding electrode E6013", "الکترود جوشکاری E6013", "kg"),
    ("Industrial valve 2-inch", "شیر صنعتی دو اینچ", "ad"),
    ("Hydraulic oil ISO 46", "روغن هیدرولیک ISO 46", "liter"),
    ("Air filter cartridge", "فیلتر هوای کارتریجی", "ad"),
    ("Conveyor belt PVC", "تسمه نقاله PVC", "meter"),
    ("Safety shoes size 42", "کفش ایمنی سایز ۴۲", "pair"),
    ("Safety helmet", "کلاه ایمنی", "ad"),
    ("Protective goggles", "عینک محافظ", "ad"),
    ("Lithium industrial grease", "گریس لیتیومی صنعتی", "kg"),
    ("Hydraulic hose 1/2-inch", "شیلنگ هیدرولیک نیم اینچ", "meter"),
    ("Carbon brush set", "پره ذغال موتور", "set"),
    ("V-belt B section", "تسمه پروانه تیپ B", "ad"),
    ("Cutting disc 4.5-inch", "صفحه برش چهار و نیم", "ad"),
]

ASSETS = [
    ("Dell Latitude 5540", "لپ‌تاپ دل لتیتیود ۵۵۴۰"),
    ("Bosch angle grinder", "فرز انگشتی بوش"),
    ("Fluke 87V multimeter", "مولتی‌متر فلوک 87V"),
    ("Digital platform scale", "ترازوی دیجیتال پرتابل"),
    ("Hydraulic floor jack 3t", "جک هیدرولیک سه تنی"),
    ("Welding helmet auto-dark", "کلاه جوشکاری اتوماتیک"),
    ("Bosch cordless drill", "دریل شارژی بوش"),
    ("Thermal camera FLIR", "دوربین حرارتی فیر"),
]

REQUEST_PURPOSES = [
    ("Monthly PPE replenishment for furnace crew", "شارژ ماهانه تجهیزات حفاظت فردی کوره"),
    ("Emergency maintenance spare parts", "قطعات یدکی تعمیرات اضطراری"),
    ("Quarterly lubrication materials", "مواد روانکاری سه‌ماهه"),
    ("Electrical panel repair kit", "کیت تعمیر تابلو برق"),
    ("Conveyor maintenance supplies", "ملزومات نگهداری نوار نقاله"),
    ("Safety stock restock", "تجدید موجودی ایمنی"),
]


def role_permission_codes(engine) -> dict[str, list[str]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "select r.name, p.code from roles r "
                "join role_permissions rp on rp.role_id = r.id "
                "join permissions p on p.id = rp.permission_id"
            )
        ).all()
    codes: dict[str, list[str]] = {}
    for name, code in rows:
        codes.setdefault(name, []).append(code)
    return codes


def split_code(code: str) -> tuple[str, str, str]:
    module, resource, operation = code.split(":", 2)
    return module, resource, operation


def main() -> int:
    admin_email = env_value("INITIAL_ADMIN_EMAIL")
    admin_password = env_value("INITIAL_ADMIN_PASSWORD")
    database_url = env_value("DATABASE_URL")
    if not (admin_email and admin_password and database_url):
        print("missing INITIAL_ADMIN_* or DATABASE_URL in backend/.env")
        return 1

    tag = uuid.uuid4().hex[:6]
    engine = create_engine(database_url)
    role_codes = role_permission_codes(engine)
    engine.dispose()

    with httpx.Client() as client:
        token = api(client, "POST", "auth/login", json={
            "email": admin_email, "password": admin_password,
        })["access_token"]

        roles = {
            role["name"]: role["id"]
            for role in api(client, "GET", "roles?page_size=100", token)["items"]
        }
        workplaces = api(client, "GET", "org/workplaces?page_size=50", token)["items"]
        print(f"run tag {tag}: {len(workplaces)} workplaces, roles {sorted(roles)}")

        # --- employees + users (+ roles & scopes for keeper/approver) ---
        employees: list[dict] = []
        keeper_codes = role_codes.get("WarehouseKeeper", [])
        approver_codes = role_codes.get("WarehouseApprover", [])
        for wp_index, wp in enumerate(workplaces):
            for slot in range(4):
                index = wp_index * 4 + slot
                first_en, first_fa = FIRST_NAMES[index % len(FIRST_NAMES)]
                last_en, last_fa = LAST_NAMES[(index * 3 + 1) % len(LAST_NAMES)]
                username = f"fake{tag}u{index:02d}"
                created = api(client, "POST", "employees", token, json={
                    "national_id": f"8{uuid.uuid4().int % 10**9:09d}",
                    "personnel_code": f"FK-{tag}-{index:03d}",
                    "first_name": first_en, "last_name": last_en,
                    "first_name_fa": first_fa, "last_name_fa": last_fa,
                    "phone": f"0913{random.randint(1000000, 9999999)}",
                    "workplace_id": wp["id"],
                    "user": {
                        "email": f"{username}@zarandsteel.ir",
                        "username": username,
                        "password": FAKE_PASSWORD,
                    },
                })
                user_id = created["user"]["id"]
                if slot == 0:  # workplace keeper
                    api(client, "POST", f"users/{user_id}/roles", token, json={
                        "role_id": roles["WarehouseKeeper"],
                    })
                    for code in keeper_codes:
                        module, resource, operation = split_code(code)
                        api(client, "POST", f"users/{user_id}/scopes", token, json={
                            "level": "workplace", "module": module,
                            "resource": resource, "operation": operation,
                            "workplace_id": wp["id"],
                        })
                elif slot == 1 and wp_index == 0:  # one complex-level approver
                    api(client, "POST", f"users/{user_id}/roles", token, json={
                        "role_id": roles["WarehouseApprover"],
                    })
                    for code in approver_codes:
                        module, resource, operation = split_code(code)
                        api(client, "POST", f"users/{user_id}/scopes", token, json={
                            "level": "complex", "module": module,
                            "resource": resource, "operation": operation,
                            "complex_id": wp["complex_id"],
                        })
                employees.append({**created, "workplace": wp, "slot": slot})
        print(f"employees: {len(employees)}")

        # --- catalog (names are globally unique among active items: reuse) ---
        items: list[dict] = []
        for i, (name_en, name_fa, unit) in enumerate(ITEMS):
            query = str(httpx.QueryParams({"search": name_en}))
            existing = api(client, "GET", f"warehouse/items?{query}&page_size=1", token)
            if existing["total"] > 0:
                items.append(existing["items"][0])
                continue
            items.append(api(client, "POST", "warehouse/items", token, json={
                "name": name_en, "name_fa": name_fa,
                "code": f"ITM-{tag}{i:02d}", "unit": unit, "min_quantity": "10",
            }))
        reused = len(items) - sum(1 for it in items if it.get("code", "").startswith(f"ITM-{tag}"))
        print(f"items: {len(items)} ({reused} reused from earlier runs)")

        # --- warehouses, shelves, stock (one below-threshold case each) ---
        placements: dict[str, list[dict]] = {}
        for wp_index, wp in enumerate(workplaces):
            warehouse = api(client, "POST", "warehouse/warehouses", token, json={
                "workplace_id": wp["id"],
                "code": f"WH-{tag}-{wp['code']}",
                "name": f"Main warehouse {wp['code']}",
                "name_fa": f"انبار اصلی {wp['code']}",
            })
            shelf_ids = [
                api(client, "POST", f"warehouse/warehouses/{warehouse['id']}/shelves", token, json={
                    "code": f"S-{n:02d}",
                })["id"]
                for n in (1, 2)
            ]
            for offset in range(3):
                item = items[(wp_index * 3 + offset) % len(items)]
                placement = api(client, "POST", "warehouse/placements/receive", token, json={
                    "item_id": item["id"], "shelf_id": shelf_ids[offset % 2],
                    "quantity": "120", "reason": "fake opening stock",
                })
                placements.setdefault(item["id"], []).append(placement)
                if offset == 0:  # issue down below the minimum -> alert episode
                    api(client, "POST", "warehouse/placements/issue", token, json={
                        "placement_id": placement["id"], "quantity": "115",
                        "reason": "fake consumption",
                    })
        print(f"warehouses: {len(workplaces)} (2 shelves each, 3 stocked items each)")

        # --- item requests across the lifecycle ---
        # Created by a plain employee so the request anchors to their
        # workplace (admin has no employee record and would anchor NULL).
        requester_token = api(client, "POST", "auth/login", json={
            "email": f"fake{tag}u02@zarandsteel.ir", "password": FAKE_PASSWORD,
        })["access_token"]
        pending = approved = 0
        for i, (purpose_en, purpose_fa) in enumerate(REQUEST_PURPOSES):
            lines = [
                {"item_id": items[i % len(items)]["id"],
                 "quantity": str(random.randint(2, 9)), "note": None},
                {"item_id": items[(i + 4) % len(items)]["id"],
                 "quantity": str(random.randint(2, 9)), "note": "fake line note"},
            ]
            purpose = purpose_en if i % 2 == 0 else purpose_fa
            request = api(client, "POST", "warehouse/requests", requester_token, json={
                "purpose_description": f"{purpose} [{tag}]",
                "lines": lines,
            })
            if i in (0, 1):
                pending += 1  # leave pending
            elif i == 2:
                api(client, "POST", f"warehouse/requests/{request['id']}/approve", token, json={
                    "version": request["version"], "note": "fake approval",
                })
                approved += 1
            elif i == 3:
                api(client, "POST", f"warehouse/requests/{request['id']}/reject", token, json={
                    "version": request["version"], "note": "fake rejection: budget cycle",
                })
            elif i in (4, 5):
                approved_request = api(
                    client, "POST", f"warehouse/requests/{request['id']}/approve", token,
                    json={"version": request["version"], "note": "fake approval"},
                )
                fulfill_lines = []
                for line in approved_request["lines"]:
                    current = api(
                        client, "GET",
                        f"warehouse/placements?item_id={line['item']['id']}&include_empty=true",
                        token,
                    )["items"]
                    options = [
                        p for p in current
                        if float(p["quantity"]) >= float(line["quantity"])
                    ]
                    if not options:
                        break
                    fulfill_lines.append({
                        "line_id": line["id"], "placement_id": options[0]["id"],
                    })
                if len(fulfill_lines) == len(approved_request["lines"]):
                    api(client, "POST", f"warehouse/requests/{request['id']}/fulfill", token, json={
                        "version": approved_request["version"], "lines": fulfill_lines,
                    })
        print(f"requests: {len(REQUEST_PURPOSES)} (2 pending, 1 approved, 1 rejected, 2 fulfilled)")

        # --- assets across the lifecycle ---
        # Created by the run's first workplace keeper so assets anchor to
        # that workplace; assignment targets stay inside the keeper's scope.
        keeper_token = api(client, "POST", "auth/login", json={
            "email": f"fake{tag}u00@zarandsteel.ir", "password": FAKE_PASSWORD,
        })["access_token"]
        holders = [
            e for e in employees
            if e["slot"] >= 2 and e["workplace"] == workplaces[0]
        ]
        for i, (name_en, name_fa) in enumerate(ASSETS):
            asset = api(client, "POST", "warehouse/assets", keeper_token, json={
                "name": name_en, "name_fa": name_fa,
                "serial": f"FA-{tag}-{i:02d}",
                "description": "fake asset for demo data",
            })
            if i in (0, 1):  # assigned to employees
                api(client, "POST", f"warehouse/assets/{asset['id']}/assign", keeper_token, json={
                    "version": asset["version"], "target_type": "employee",
                    "employee_id": holders[i % len(holders)]["id"], "note": "fake assignment",
                })
            elif i == 2:  # assigned to a location
                api(client, "POST", f"warehouse/assets/{asset['id']}/assign", keeper_token, json={
                    "version": asset["version"], "target_type": "location",
                    "location": "Maintenance workshop, rack B2", "note": None,
                })
            elif i == 3:  # returned after assignment
                assigned = api(client, "POST", f"warehouse/assets/{asset['id']}/assign", keeper_token, json={
                    "version": asset["version"], "target_type": "employee",
                    "employee_id": holders[1 % len(holders)]["id"], "note": None,
                })
                api(client, "POST", f"warehouse/assets/{asset['id']}/return", keeper_token, json={
                    "version": assigned["version"], "note": "fake return",
                })
            elif i == 4:  # retired
                api(client, "POST", f"warehouse/assets/{asset['id']}/retire", keeper_token, json={
                    "version": asset["version"],
                })
        print(f"assets: {len(ASSETS)} (2 employee-held, 1 location, 1 returned, 1 retired, 3 available)")

        # --- summary from the API itself ---
        for label, path in (
            ("employees", "employees?page_size=1"),
            ("items", "warehouse/items?page_size=1"),
            ("placements", "warehouse/placements?page_size=1&include_empty=true"),
            ("requests", "warehouse/requests?page_size=1"),
            ("assets", "warehouse/assets?status=all&page_size=1"),
            ("alerts", "warehouse/alerts?active=true&page_size=1"),
        ):
            body = api(client, "GET", path, token)
            print(f"total {label}: {body['total']}")

    print(f"\nfake users sign in with the password: {FAKE_PASSWORD}")
    print("keeper logins: fake{tag}u00..u03 @zarandsteel.ir (per workplace, slot 0)".replace("{tag}", tag))
    return 0


if __name__ == "__main__":
    sys.exit(main())
