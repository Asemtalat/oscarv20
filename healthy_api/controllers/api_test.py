#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اختبار نظام صلاحيات API Rules
الاستخدام:
    python3 api_test.py
    python3 api_test.py --url http://localhost:8081 --pass "كلمة_المرور"
"""

import requests
import json
import sys
import argparse

# ─────────────────────────────────────────────
#  الإعدادات
# ─────────────────────────────────────────────
BASE_URL       = "http://mohamed-precision-3510:8081"
ADMIN_LOGIN    = "admin"
ADMIN_PASSWORD = "1"
TEST_LOGIN     = "Ahmed@gmail.com"
TEST_PASSWORD  = "1"
TEST_USER_ID   = 7
RULE_ID        = 3

# محتوى الـ rule:
# orders   → [read, create, update]  -- delete ممنوع
# products → [read, create, update]  -- delete ممنوع
# invoices → [read]                  -- create ممنوع
# merchants→ (لا توجد rule)          -- كل شيء ممنوع

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

pass_count = 0
fail_count = 0
admin_token = None


# ─────────────────────────────────────────────
#  دوال مساعدة
# ─────────────────────────────────────────────
def header(title):
    print(f"\n{BOLD}{BLUE}{'─'*58}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{BLUE}{'─'*58}{RESET}")


def get_token(login, password, label=""):
    try:
        resp = requests.post(
            f"{BASE_URL}/api/login",
            json={"login": login, "password": password},
            timeout=10,
        )
        data = resp.json()
    except Exception as e:
        print(f"{RED}خطأ في الاتصال: {e}{RESET}")
        return None

    if data.get("error"):
        print(f"{RED}فشل تسجيل الدخول ({label}): {data['error']}{RESET}")
        return None

    token = data["data"]["token"]
    roles = data["data"].get("roles", [])
    print(f"  {GREEN}✓ تسجيل دخول{RESET} [{label}]  roles: {roles or 'لا يوجد'}")
    return token


def api(method, endpoint, token, payload=None):
    headers = {"Authorization": token, "Content-Type": "application/json"}
    url = f"{BASE_URL}{endpoint}"
    fn  = getattr(requests, method.lower())
    kwargs = {"headers": headers, "timeout": 10}
    if payload is not None:
        kwargs["json"] = payload
    try:
        resp = fn(url, **kwargs)
        return resp.json()
    except Exception as e:
        return {"data": None, "error": str(e)}


def check(description, result, expect_ok=True, show_data=False):
    global pass_count, fail_count
    error  = result.get("error")
    is_ok  = error is None

    if expect_ok:
        passed       = is_ok
        expected_lbl = f"{GREEN}200 OK{RESET}"
        actual_lbl   = f"{GREEN}✓ OK{RESET}" if is_ok else f"{RED}✗ {error}{RESET}"
    else:
        passed       = (not is_ok) and ("Forbidden" in str(error) or "Unauthorized" in str(error))
        expected_lbl = f"{RED}403 Forbidden{RESET}"
        actual_lbl   = f"{GREEN}✓ Forbidden{RESET}" if passed else f"{RED}✗ {error if not is_ok else 'OK — لم يُمنع!'}{RESET}"

    icon = f"{GREEN}✅ PASS{RESET}" if passed else f"{RED}❌ FAIL{RESET}"
    (pass_count if passed else fail_count).__class__  # dummy
    if passed:
        pass_count += 1
    else:
        fail_count += 1

    print(f"\n  {icon}  {description}")
    print(f"       المتوقع: {expected_lbl}")
    print(f"       الفعلي : {actual_lbl}")

    if show_data and is_ok and result.get("data"):
        raw = json.dumps(result["data"], ensure_ascii=False)
        print(f"       البيانات: {raw[:100]}{'...' if len(raw)>100 else ''}")


def set_role(token, user_id, role):
    """تغيير role المستخدم"""
    r = api("PUT", f"/users/{user_id}/role", token, {"role": role})
    label = role if role else "بدون role"
    if r.get("error"):
        print(f"  {YELLOW}⚠ فشل تغيير الـ role: {r['error']}{RESET}")
    else:
        print(f"  {YELLOW}→ تم تغيير role إلى [{label}]{RESET}")


def set_rules(token, user_id, rule_ids):
    """إسناد أو إزالة rules من المستخدم"""
    r = api("PUT", f"/api/users/{user_id}/rules", token, {"rule_ids": rule_ids})
    if r.get("error"):
        print(f"  {YELLOW}⚠ فشل تغيير rules: {r['error']}{RESET}")
    else:
        label = str(rule_ids) if rule_ids else "لا يوجد"
        print(f"  {YELLOW}→ تم تعيين rules: {label}{RESET}")


# ─────────────────────────────────────────────
#  مجموعات التيست
# ─────────────────────────────────────────────
def test_invoices(token):
    header("الفواتير (invoices) — rule: [read] فقط")
    print(f"  المتوقع: قراءة ✅  |  إنشاء ❌\n")

    r = api("GET", "/api/invoices", token)
    check("GET  /api/invoices  → مسموح (invoices:read)", r, expect_ok=True, show_data=True)

    r = api("POST", "/api/invoices", token, {"partner_id": 1, "lines": []})
    check("POST /api/invoices  → ممنوع (invoices:create غير موجودة)", r, expect_ok=False)


def test_products(token):
    header("المنتجات (products) — rule: [read, create, update]")
    print(f"  المتوقع: قراءة ✅  إنشاء ✅  تعديل ✅  حذف ❌\n")

    r = api("GET", "/api/products", token)
    check("GET    /api/products     → مسموح (products:read)", r, expect_ok=True, show_data=True)

    r = api("POST", "/api/products", token, {"name": "تيست API Rules", "price": 99.0, "type": "consu"})
    check("POST   /api/products     → مسموح (products:create)", r, expect_ok=True)
    created_id = (r.get("data") or {}).get("id")

    if created_id:
        r = api("PUT", f"/api/products/{created_id}", token, {"price": 150.0})
        check(f"PUT    /api/products/{created_id} → مسموح (products:update)", r, expect_ok=True)

        r = api("DELETE", f"/api/products/{created_id}", token)
        check(f"DELETE /api/products/{created_id} → ممنوع (products:delete غير موجودة)", r, expect_ok=False)
    else:
        print(f"  {YELLOW}⚠ لم يُنشأ منتج - تخطي تيستات PUT/DELETE{RESET}")


def test_orders(token):
    header("الطلبات (orders) — rule: [read, create, update]")
    print(f"  المتوقع: قراءة ✅  |  حذف ❌\n")

    r = api("GET", "/api/orders", token)
    check("GET    /api/orders       → مسموح (orders:read)", r, expect_ok=True, show_data=True)

    # DELETE يتحقق من الصلاحية قبل البحث عن الـ order
    r = api("DELETE", "/api/orders/9999", token)
    check("DELETE /api/orders/9999  → ممنوع (orders:delete غير موجودة)", r, expect_ok=False)


def test_merchants(token):
    header("التجار (merchants) — لا توجد rule")
    print(f"  المتوقع: كل الطلبات ❌\n")

    r = api("GET", "/api/merchants", token)
    check("GET  /api/merchants  → ممنوع (لا توجد merchants rule)", r, expect_ok=False)

    r = api("POST", "/api/merchants", token, {"name": "تيست", "mobile": "0500000000"})
    check("POST /api/merchants  → ممنوع (لا توجد merchants rule)", r, expect_ok=False)


def test_no_rules(token_func):
    """تيست مستخدم بدون rules - يجب 403 في كل شيء"""
    header("مستخدم بدون أي rule — يجب 403 في كل شيء")

    set_rules(admin_token, TEST_USER_ID, [])
    token = token_func()
    if not token:
        print(f"  {RED}فشل تسجيل الدخول - المستخدم ليس عنده rules ولا roles{RESET}")
        print(f"  {YELLOW}هذا متوقع إذا لم يُصلح has_api_access() بعد{RESET}")
        set_rules(admin_token, TEST_USER_ID, [RULE_ID])
        return

    print()
    r = api("GET", "/api/invoices", token)
    check("GET  /api/invoices  → ممنوع (لا توجد rule)", r, expect_ok=False)

    r = api("GET", "/api/orders", token)
    check("GET  /api/orders   → ممنوع (لا توجد rule)", r, expect_ok=False)

    r = api("POST", "/api/products", token, {"name": "test"})
    check("POST /api/products → ممنوع (لا توجد rule)", r, expect_ok=False)

    set_rules(admin_token, TEST_USER_ID, [RULE_ID])
    print(f"\n  {YELLOW}↩ تم إعادة الـ rule {RULE_ID}{RESET}")


def print_summary():
    total = pass_count + fail_count
    header("ملخص النتائج")
    print(f"  المجموع : {total}")
    print(f"  {GREEN}✅ نجح   : {pass_count}{RESET}")
    print(f"  {RED}❌ فشل   : {fail_count}{RESET}\n")
    if fail_count == 0:
        print(f"  {GREEN}{BOLD}🎉 نظام الـ rules يعمل بشكل صحيح تماماً!{RESET}")
    else:
        print(f"  {RED}{BOLD}⚠️  يوجد {fail_count} تيست فشل — راجع النتائج أعلاه{RESET}")
    print()


# ─────────────────────────────────────────────
#  التشغيل الرئيسي
# ─────────────────────────────────────────────
def main():
    global BASE_URL, admin_token

    parser = argparse.ArgumentParser()
    parser.add_argument("--url",  default=BASE_URL,      help="Base URL")
    parser.add_argument("--user", default=TEST_LOGIN,    help="Test user login")
    parser.add_argument("--pass", default=TEST_PASSWORD, dest="pwd")
    args = parser.parse_args()
    BASE_URL = args.url.rstrip("/")

    print(f"\n{BOLD}{CYAN}{'═'*58}{RESET}")
    print(f"{BOLD}{CYAN}   اختبار نظام API Rules{RESET}")
    print(f"{BOLD}{CYAN}{'═'*58}{RESET}")
    print(f"  Server  : {BASE_URL}")
    print(f"  Rule ID : {RULE_ID}  →  orders:[r,c,u]  products:[r,c,u]  invoices:[r]")

    # ── 1. تسجيل الدخول ──────────────────────────
    header("تسجيل الدخول")
    admin_token = get_token(ADMIN_LOGIN, ADMIN_PASSWORD, "Admin")
    if not admin_token:
        sys.exit(1)

    # ── 2. إزالة role المستخدم ليعتمد على rules فقط ──
    header("إعداد بيئة التيست")
    print(f"  نزيل role من Ahmed حتى يعتمد على rules فقط")
    set_role(admin_token, TEST_USER_ID, "")
    set_rules(admin_token, TEST_USER_ID, [RULE_ID])

    # ── 3. تسجيل دخول Ahmed بعد إزالة الـ role ──────
    user_token = get_token(args.user, args.pwd, "Ahmed (بدون role)")
    if not user_token:
        print(f"\n  {RED}Ahmed لا يستطيع تسجيل الدخول!")
        print(f"  السبب: has_api_access() لا تعترف بالـ rules — الإصلاح مطلوب في res_users.py{RESET}")
        print(f"\n  {YELLOW}تأكد إنك عملت restart للـ server بعد التعديل ثم أعد التشغيل{RESET}\n")
        set_role(admin_token, TEST_USER_ID, "delegate")
        sys.exit(1)

    # ── 4. التيستات الأساسية ──────────────────────
    test_invoices(user_token)
    test_products(user_token)
    test_orders(user_token)
    test_merchants(user_token)

    # ── 5. تيست بدون rules ───────────────────────
    test_no_rules(lambda: get_token(args.user, args.pwd, "Ahmed (بدون rule)"))

    # ── 6. إعادة الـ role الأصلي ─────────────────
    header("استعادة البيئة")
    set_role(admin_token, TEST_USER_ID, "delegate")
    set_rules(admin_token, TEST_USER_ID, [RULE_ID])
    print(f"  {GREEN}✓ تمت استعادة role وrules لـ Ahmed{RESET}")

    print_summary()


if __name__ == "__main__":
    main()
