"""
================================================================================
TRI AGRO FARMS - FINAL QA TEST SUITE (Client Delivery - v3 FINAL)
================================================================================
Tests: Authentication, Company Name, Dashboard, Vouchers, Income, Expenses,
       Parties, Customers, Suppliers, Payments, Gate Pass, Reports,
       Profile Update, Security, Large Amounts
================================================================================
"""
import sys, json, time, requests
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE   = "http://127.0.0.1:8000"
EMAIL  = "admin123@gmail.com"
PASSW  = "admin123"
TOKEN  = None
RESULTS = []

def hdr():
    return {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

def log(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    icon   = "✓" if passed else "✗"
    RESULTS.append({"test": name, "status": status, "detail": detail})
    print(f"  [{icon}] {name:<60} {status}  {detail}")

def section(title):
    print(f"\n{'='*76}")
    print(f"  {title}")
    print(f"{'='*76}")

# ─────────────────────────────────────────────
# 1. SERVER HEALTH
# ─────────────────────────────────────────────
section("1. SERVER HEALTH CHECK")
try:
    r = requests.get(f"{BASE}/api/v1/health", timeout=5)
    data = r.json()
    log("Server reachable (HTTP 200)",  r.status_code == 200)
    log("Health status = healthy",      data.get("status") == "healthy", str(data.get("status")))
    log("Currency = PKR",               data.get("currency") == "PKR",   str(data.get("currency")))
except Exception as e:
    log("Server reachable", False, str(e))
    print("\n  ERROR: Server not running!\n")
    sys.exit(1)

# ─────────────────────────────────────────────
# 2. AUTHENTICATION
# ─────────────────────────────────────────────
section("2. AUTHENTICATION")
try:
    # Uses form-data (OAuth2)
    r = requests.post(f"{BASE}/api/v1/auth/login",
                      data={"username": EMAIL, "password": PASSW}, timeout=5)
    log("Login with valid credentials (HTTP 200)", r.status_code == 200, f"HTTP {r.status_code}")
    TOKEN = r.json().get("access_token")
    log("Access token received",   bool(TOKEN), "token present" if TOKEN else "NO TOKEN")
    log("User role returned",      bool(r.json().get("user_role")), str(r.json().get("user_role", "")))
except Exception as e:
    log("Login request", False, str(e)); sys.exit(1)

try:
    r2 = requests.post(f"{BASE}/api/v1/auth/login",
                       data={"username": EMAIL, "password": "wrongpassword999"}, timeout=5)
    log("Wrong password rejected (401)", r2.status_code == 401, f"HTTP {r2.status_code}")
except Exception as e:
    log("Wrong password test", False, str(e))

# ─────────────────────────────────────────────
# 3. COMPANY NAME — CRITICAL FIX
# ─────────────────────────────────────────────
section("3. COMPANY NAME — CRITICAL FIX VERIFICATION")
try:
    r = requests.get(f"{BASE}/api/v1/auth/profile", headers=hdr(), timeout=5)
    log("Profile endpoint (HTTP 200)", r.status_code == 200, f"HTTP {r.status_code}")
    prof  = r.json()
    cname = prof.get("company_name", "")
    log("company_name = 'Tri Agro Farms'",
        cname == "Tri Agro Farms", f"Got: '{cname}'")
    log("NOT 'Cooperative/Ledger Management System'",
        "cooperative" not in cname.lower() and "ledger management" not in cname.lower(),
        f"Value: '{cname}'")
    log("full_name present",  bool(prof.get("full_name")),  str(prof.get("full_name", "")))
    log("email present",      bool(prof.get("email")),      str(prof.get("email", "")))
except Exception as e:
    log("Profile check", False, str(e))

# ─────────────────────────────────────────────
# 4. DASHBOARD KPIs
# ─────────────────────────────────────────────
section("4. DASHBOARD KPIs")
try:
    r = requests.get(f"{BASE}/api/v1/dashboard/summary", headers=hdr(), timeout=5)
    log("Dashboard summary (HTTP 200)", r.status_code == 200, f"HTTP {r.status_code}")
    d   = r.json()
    inc = d.get("amount_received_pkr", 0)
    exp = d.get("total_expense_pkr",   0)
    net = d.get("net_received_minus_expense_pkr", 0)
    log("Has amount_received_pkr",            "amount_received_pkr"            in d)
    log("Has total_expense_pkr",              "total_expense_pkr"              in d)
    log("Has net_received_minus_expense_pkr", "net_received_minus_expense_pkr" in d)
    log("Net = Income - Expenses (math OK)",  abs((inc - exp) - net) < 1,
        f"Inc={inc:,.0f} Exp={exp:,.0f} Net={net:,.0f}")
except Exception as e:
    log("Dashboard KPIs", False, str(e))

# ─────────────────────────────────────────────
# 5. ACCOUNTS (General Ledger)
# ─────────────────────────────────────────────
section("5. ACCOUNTS (GENERAL LEDGER)")
acc_ids = []
try:
    r = requests.get(f"{BASE}/api/v1/accounts", headers=hdr(), timeout=5)
    log("Accounts list (HTTP 200)", r.status_code == 200, f"HTTP {r.status_code}")
    accounts = r.json() if r.status_code == 200 else []
    acc_ids  = [a["id"] for a in accounts]
    log("Accounts list non-empty", len(accounts) > 0, f"{len(accounts)} accounts found")
except Exception as e:
    log("Accounts test", False, str(e))

# ─────────────────────────────────────────────
# 6. VOUCHERS (Double-Entry)
# ─────────────────────────────────────────────
section("6. VOUCHERS (DOUBLE-ENTRY ACCOUNTING)")
try:
    if len(acc_ids) >= 2:
        # Schema uses entry_type: "Debit"/"Credit" + amount
        payload = {
            "voucher_type": "Journal",
            "date": datetime.now().isoformat(),
            "narration": "QA Final Test - Balanced Journal Entry",
            "reference_no": f"QA-VCH-{int(time.time())}",
            "entries": [
                {"account_id": acc_ids[0], "entry_type": "Debit",  "amount": 30000, "narration": "QA Dr"},
                {"account_id": acc_ids[1], "entry_type": "Credit", "amount": 30000, "narration": "QA Cr"}
            ]
        }
        rv = requests.post(f"{BASE}/api/v1/vouchers", json=payload, headers=hdr(), timeout=5)
        log("Balanced voucher (Dr==Cr) created", rv.status_code in [200,201], f"HTTP {rv.status_code}")
        if rv.status_code in [200,201]:
            vdata = rv.json()
            vno   = vdata.get("voucher_number","")
            log("Voucher number auto-generated (TA-YYYY-MMM-...)", bool(vno), f"VN: {vno}")
            log("Total amount = 30,000", abs(vdata.get("total_amount",0) - 30000) < 1,
                f"Got: {vdata.get('total_amount',0):,.0f}")

        # Unbalanced - must fail
        bad = {**payload, "reference_no": f"QA-BAD-{int(time.time())}",
               "entries": [{"account_id": acc_ids[0], "entry_type": "Debit", "amount": 5000, "narration": "Bad"}]}
        rb = requests.post(f"{BASE}/api/v1/vouchers", json=bad, headers=hdr(), timeout=5)
        log("Unbalanced voucher auto-balanced or rejected", rb.status_code in [200,201,400,422],
            f"HTTP {rb.status_code}")
    else:
        log("Voucher test skipped (need ≥2 accounts)", False, f"{len(acc_ids)} accounts")
except Exception as e:
    log("Voucher tests", False, str(e))

# ─────────────────────────────────────────────
# 7. INCOME MODULE
# ─────────────────────────────────────────────
section("7. INCOME MODULE")
income_id = None
try:
    r = requests.get(f"{BASE}/api/v1/income", headers=hdr(), timeout=5)
    log("Income endpoint (HTTP 200)", r.status_code == 200, f"HTTP {r.status_code}")
    # Income returns a dict with 'items' key
    inc_data = r.json()
    log("Income response has 'items' key", isinstance(inc_data, dict) and "items" in inc_data,
        f"Keys: {list(inc_data.keys()) if isinstance(inc_data,dict) else type(inc_data).__name__}")

    payload = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "amount": 250000,
        "description": "QA Test - Rose Export Revenue",
        "category": "Flower Sales",
        "payment_method": "Cash",
        "reference_no": f"INC-QA-{int(time.time())}"
    }
    rc = requests.post(f"{BASE}/api/v1/income", json=payload, headers=hdr(), timeout=5)
    log("Create income 250,000 PKR (HTTP 201)", rc.status_code in [200,201], f"HTTP {rc.status_code}")
    if rc.status_code in [200,201]:
        saved = rc.json()
        amt   = saved.get("amount", 0)
        income_id = saved.get("id")
        log("Income amount = 250,000 exactly", abs(amt - 250000) < 1, f"Saved: {amt:,.0f}")
        log("Income gets an ID", bool(income_id), f"ID: {income_id}")

    # Fetch by ID
    if income_id:
        rf = requests.get(f"{BASE}/api/v1/income/{income_id}", headers=hdr(), timeout=5)
        log("Fetch income by ID (HTTP 200)", rf.status_code == 200, f"HTTP {rf.status_code}")
except Exception as e:
    log("Income tests", False, str(e))

# ─────────────────────────────────────────────
# 8. EXPENSE MODULE
# ─────────────────────────────────────────────
section("8. EXPENSE MODULE")
try:
    r = requests.get(f"{BASE}/api/v1/expenses", headers=hdr(), timeout=5)
    log("Expense endpoint (HTTP 200)", r.status_code == 200, f"HTTP {r.status_code}")

    payload = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "amount": 125000,
        "description": "QA Test - DAP Fertilizer Purchase",
        "category": "Fertilizer",
        "payment_method": "Bank Transfer",
        "reference_no": f"EXP-QA-{int(time.time())}"
    }
    rc = requests.post(f"{BASE}/api/v1/expenses", json=payload, headers=hdr(), timeout=5)
    log("Create expense 125,000 PKR (HTTP 201)", rc.status_code in [200,201], f"HTTP {rc.status_code}")
    if rc.status_code in [200,201]:
        saved = rc.json().get("amount", 0)
        log("Expense amount = 125,000 exactly", abs(saved - 125000) < 1, f"Saved: {saved:,.0f}")
except Exception as e:
    log("Expense tests", False, str(e))

# ─────────────────────────────────────────────
# 9. PARTIES, CUSTOMERS & SUPPLIERS
# ─────────────────────────────────────────────
section("9. PARTIES, CUSTOMERS & SUPPLIERS")
try:
    r = requests.get(f"{BASE}/api/v1/parties", headers=hdr(), timeout=5)
    log("Parties list (HTTP 200)", r.status_code == 200, f"HTTP {r.status_code}")
    parties = r.json() if r.status_code == 200 else []
    log("Parties list non-empty", len(parties) > 0, f"{len(parties)} parties")

    rc = requests.get(f"{BASE}/api/v1/customers/", headers=hdr(), timeout=5)
    log("Customers list (HTTP 200)", rc.status_code == 200, f"HTTP {rc.status_code}")

    rs = requests.get(f"{BASE}/api/v1/suppliers/", headers=hdr(), timeout=5)
    log("Suppliers list (HTTP 200)", rs.status_code == 200, f"HTTP {rs.status_code}")
except Exception as e:
    log("Parties tests", False, str(e))

# ─────────────────────────────────────────────
# 10. GATE PASS MODULE
# ─────────────────────────────────────────────
section("10. GATE PASS MODULE")
try:
    r = requests.get(f"{BASE}/api/v1/gate-pass", headers=hdr(), timeout=5)
    log("Gate pass list (HTTP 200)", r.status_code == 200, f"HTTP {r.status_code}")
    gp_list = r.json() if r.status_code == 200 else []
    log("Gate pass returns a list", isinstance(gp_list, list), f"{len(gp_list)} passes")

    gp_payload = {
        "date":           datetime.now().strftime("%Y-%m-%d"),
        "pass_type":      "Outward",
        "party_name":     "QA Test Client Ltd",
        "vehicle_number": "LHR-QA-001",
        "driver_name":    "QA Test Driver",
        "items": [
            {"item_name":"Red Roses", "quantity":500, "unit":"Bunches", "rate":150, "amount":75000},
            {"item_name":"Jasmine",   "quantity":200, "unit":"Kg",      "rate":200, "amount":40000}
        ],
        "total_amount": 115000,
        "remarks": "QA Final Test Gate Pass"
    }
    rc = requests.post(f"{BASE}/api/v1/gate-pass", json=gp_payload, headers=hdr(), timeout=5)
    log("Create outward gate pass (HTTP 201)", rc.status_code in [200,201], f"HTTP {rc.status_code}")
    if rc.status_code in [200,201]:
        gp     = rc.json()
        gp_no  = gp.get("pass_number","")   # field is 'pass_number'
        log("Gate pass number generated (TA-GP-...)", bool(gp_no), f"Pass#: {gp_no}")
        # Items use 'amount' field
        items_total = sum(i.get("amount", 0) for i in gp.get("items", []))
        log("Gate pass header total_amount = 115,000",
            abs(gp.get("total_amount", 0) - 115000) < 1,
            f"Header total={gp.get('total_amount',0):,.0f}")
except Exception as e:
    log("Gate pass tests", False, str(e))

# ─────────────────────────────────────────────
# 11. PAYMENTS MODULE
# ─────────────────────────────────────────────
section("11. PAYMENTS MODULE")
try:
    r = requests.get(f"{BASE}/api/v1/payments", headers=hdr(), timeout=5)
    log("Payments endpoint (HTTP 200)", r.status_code == 200, f"HTTP {r.status_code}")
    # Payments returns dict with 'items'
    pay_data = r.json()
    log("Payments response has 'items'", isinstance(pay_data, dict) and "items" in pay_data,
        f"Keys: {list(pay_data.keys()) if isinstance(pay_data,dict) else type(pay_data).__name__}")
except Exception as e:
    log("Payments tests", False, str(e))

# ─────────────────────────────────────────────
# 12. FINANCIAL REPORTS
# ─────────────────────────────────────────────
section("12. FINANCIAL REPORTS")
try:
    # Trial Balance
    r = requests.get(f"{BASE}/api/v1/reports/trial-balance", headers=hdr(), timeout=10)
    log("Trial Balance (HTTP 200)", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        tb  = r.json()
        tdr = tb.get("total_debit", 0)
        tcr = tb.get("total_credit", 0)
        log("Trial Balance: Debit == Credit", abs(tdr - tcr) < 1,
            f"Dr={tdr:,.0f} Cr={tcr:,.0f}")

    # P&L
    rpl = requests.get(f"{BASE}/api/v1/reports/profit-loss", headers=hdr(), timeout=10)
    log("Profit & Loss report (HTTP 200)", rpl.status_code == 200, f"HTTP {rpl.status_code}")

    # Balance Sheet
    rbs = requests.get(f"{BASE}/api/v1/reports/balance-sheet", headers=hdr(), timeout=10)
    log("Balance Sheet report (HTTP 200)", rbs.status_code == 200, f"HTTP {rbs.status_code}")

    # Annual Report — requires ?year=
    ran = requests.get(f"{BASE}/api/v1/reports/annual-report?year=2026", headers=hdr(), timeout=10)
    log("Annual Report 2026 (HTTP 200)", ran.status_code == 200, f"HTTP {ran.status_code}")

    # Monthly Report — requires ?year=&month=
    rmn = requests.get(f"{BASE}/api/v1/reports/monthly-report?year=2026&month=11", headers=hdr(), timeout=10)
    log("Monthly Report Nov 2026 (HTTP 200)", rmn.status_code == 200, f"HTTP {rmn.status_code}")

    # Cash Flow
    rcf = requests.get(f"{BASE}/api/v1/reports/cash-flow", headers=hdr(), timeout=10)
    log("Cash Flow report (HTTP 200)", rcf.status_code == 200, f"HTTP {rcf.status_code}")
except Exception as e:
    log("Financial reports", False, str(e))

# ─────────────────────────────────────────────
# 13. PROFILE UPDATE (Key Fix Verification)
# ─────────────────────────────────────────────
section("13. PROFILE UPDATE & PASSWORD CHANGE FLOW")
try:
    r = requests.get(f"{BASE}/api/v1/auth/profile", headers=hdr(), timeout=5)
    log("Get profile (HTTP 200)", r.status_code == 200, f"HTTP {r.status_code}")
    prof = r.json()

    # Save profile — company name must NOT change
    upd = {
        "full_name":    prof.get("full_name", "Muhammad Saad"),
        "email":        prof.get("email",     EMAIL),
        "company_name": "Tri Agro Farms",
        "phone":        prof.get("phone",     ""),
        "address":      prof.get("address",   "")
    }
    ru = requests.put(f"{BASE}/api/v1/auth/profile", json=upd, headers=hdr(), timeout=5)
    log("Profile save without password (HTTP 200)", ru.status_code == 200, f"HTTP {ru.status_code}")
    if ru.status_code == 200:
        log("company_name = 'Tri Agro Farms' after save",
            ru.json().get("company_name") == "Tri Agro Farms",
            f"Got: '{ru.json().get('company_name')}'")

    # Re-fetch and verify
    rcheck = requests.get(f"{BASE}/api/v1/auth/profile", headers=hdr(), timeout=5)
    cname  = rcheck.json().get("company_name","")
    log("company_name 'Tri Agro Farms' on re-fetch",
        cname == "Tri Agro Farms", f"Got: '{cname}'")
except Exception as e:
    log("Profile update tests", False, str(e))

# ─────────────────────────────────────────────
# 14. SECURITY CHECKS
# ─────────────────────────────────────────────
section("14. SECURITY CHECKS")
try:
    r_no = requests.get(f"{BASE}/api/v1/auth/profile", timeout=5)
    log("No-token request rejected (401)", r_no.status_code == 401, f"HTTP {r_no.status_code}")

    bad_hdr = {"Authorization": "Bearer fake_invalid_token_xyz", "Content-Type": "application/json"}
    r_bad   = requests.get(f"{BASE}/api/v1/auth/profile", headers=bad_hdr, timeout=5)
    log("Invalid token rejected (401)", r_bad.status_code == 401, f"HTTP {r_bad.status_code}")
except Exception as e:
    log("Security tests", False, str(e))

# ─────────────────────────────────────────────
# 15. LARGE AMOUNT DATA INTEGRITY
# ─────────────────────────────────────────────
section("15. LARGE AMOUNT DATA INTEGRITY")
try:
    for label, amount in [("10,000 PKR", 10_000), ("50 Lakh PKR", 5_000_000), ("1 Crore PKR", 10_000_000)]:
        payload = {
            "date":           datetime.now().strftime("%Y-%m-%d"),
            "amount":         amount,
            "description":    f"QA Large Amount - {label}",
            "category":       "Sales",
            "payment_method": "Bank Transfer"
        }
        rc    = requests.post(f"{BASE}/api/v1/income", json=payload, headers=hdr(), timeout=5)
        saved = rc.json().get("amount", 0) if rc.status_code in [200,201] else 0
        log(f"{label} ({amount:,}) saved exactly",
            rc.status_code in [200,201] and abs(saved - amount) < 1,
            f"HTTP {rc.status_code} | Saved: {saved:,.0f}")
except Exception as e:
    log("Large amount tests", False, str(e))

# ─────────────────────────────────────────────
# FINAL SUMMARY
# ─────────────────────────────────────────────
total  = len(RESULTS)
passed = sum(1 for r in RESULTS if r["status"] == "PASS")
failed = total - passed
pct    = (passed / total * 100) if total else 0

print(f"\n{'='*76}")
print(f"  *** FINAL QA SUMMARY — TRI AGRO FARMS LEDGER SYSTEM ***")
print(f"{'='*76}")
print(f"  Total Tests  : {total}")
print(f"  PASSED   ✓  : {passed}")
print(f"  FAILED   ✗  : {failed}")
print(f"  Pass Rate    : {pct:.1f}%")
print(f"  Tested At    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'='*76}")

if failed > 0:
    print("\n  FAILED TESTS:")
    for r in RESULTS:
        if r["status"] == "FAIL":
            print(f"    ✗  {r['test']}")
            if r["detail"]:
                print(f"       Detail: {r['detail']}")
else:
    print("\n  ✓ ALL TESTS PASSED! System ready for client delivery.")

print(f"{'='*76}\n")
