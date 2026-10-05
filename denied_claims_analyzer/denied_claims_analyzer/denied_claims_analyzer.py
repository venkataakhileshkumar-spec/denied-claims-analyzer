"""
Denied Claims Analyzer
----------------------
Analyzes a claims file to show why claims are denied, which providers and
procedures are affected, how much money is at stake, and what to do next.

Run:  python denied_claims_analyzer.py
Input (auto-generated with sample data if missing):
    claims.csv : claim_id, member_id, provider_id, provider_name, service_date,
                 cpt_code, billed_amount, status, denial_code
                 (status = Paid or Denied; denial_code only for denied claims)
Output:
    denied_claims_action_list.csv + report printed to console
"""

import csv
import random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

AS_OF = date.today()
MIN_PROVIDER_CLAIMS = 5  # ignore tiny providers in the ranking

# ---------------------------------------------------------------------------
# 1. Denial code reference (simplified CARC-style codes)
#    code: (description, category, recommended action, preventable?)
# ---------------------------------------------------------------------------
DENIAL_CODES = {
    "CO-4":   ("Modifier inconsistent with procedure", "Coding",         "Correct coding/modifier and resubmit", True),
    "CO-16":  ("Missing or invalid claim information", "Administrative", "Fix the missing data and resubmit",     True),
    "CO-18":  ("Duplicate claim",                      "Administrative", "Check original claim status; do not resubmit", True),
    "CO-27":  ("Coverage terminated",                  "Eligibility",    "Verify eligibility; bill patient or other payer", False),
    "CO-29":  ("Timely filing limit exceeded",         "Administrative", "Appeal with proof of timely filing",    True),
    "CO-50":  ("Not medically necessary",              "Clinical",       "Appeal with clinical documentation",    False),
    "CO-109": ("Not covered by this payer",            "Eligibility",    "Route claim to the correct payer",      False),
    "CO-197": ("Prior authorization missing",          "Authorization",  "Request retro-authorization or appeal", True),
}


def priority(amount: float) -> str:
    if amount >= 1000:
        return "High"
    if amount >= 300:
        return "Medium"
    return "Low"


# ---------------------------------------------------------------------------
# 2. Load data
# ---------------------------------------------------------------------------
def load_claims(path: str) -> list[dict]:
    claims = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            row["billed_amount"] = float(row["billed_amount"])
            row["service_date"] = date.fromisoformat(row["service_date"])
            row["status"] = row["status"].strip().title()
            claims.append(row)
    return claims


# ---------------------------------------------------------------------------
# 3. Analysis
# ---------------------------------------------------------------------------
def analyze(claims: list[dict]) -> dict:
    denied = [c for c in claims if c["status"] == "Denied"]
    total_billed = sum(c["billed_amount"] for c in claims)
    denied_amount = sum(c["billed_amount"] for c in denied)

    by_reason = defaultdict(lambda: {"count": 0, "amount": 0.0})
    by_category = defaultdict(lambda: {"count": 0, "amount": 0.0})
    by_provider = defaultdict(lambda: {"claims": 0, "denied": 0, "amount": 0.0})
    by_cpt = defaultdict(lambda: {"claims": 0, "denied": 0})
    by_month = defaultdict(lambda: {"claims": 0, "denied": 0})

    for c in claims:
        month = c["service_date"].strftime("%Y-%m")
        by_month[month]["claims"] += 1
        by_cpt[c["cpt_code"]]["claims"] += 1
        by_provider[c["provider_name"]]["claims"] += 1

        if c["status"] == "Denied":
            code = c["denial_code"]
            category = DENIAL_CODES.get(code, ("Unknown", "Other", "Review manually", False))[1]
            by_reason[code]["count"] += 1
            by_reason[code]["amount"] += c["billed_amount"]
            by_category[category]["count"] += 1
            by_category[category]["amount"] += c["billed_amount"]
            by_provider[c["provider_name"]]["denied"] += 1
            by_provider[c["provider_name"]]["amount"] += c["billed_amount"]
            by_cpt[c["cpt_code"]]["denied"] += 1
            by_month[month]["denied"] += 1

    preventable_amount = sum(
        c["billed_amount"] for c in denied if DENIAL_CODES.get(c["denial_code"], (0, 0, 0, False))[3]
    )

    return {
        "total": len(claims), "denied": denied,
        "total_billed": total_billed, "denied_amount": denied_amount,
        "preventable_amount": preventable_amount,
        "by_reason": by_reason, "by_category": by_category,
        "by_provider": by_provider, "by_cpt": by_cpt, "by_month": by_month,
    }


# ---------------------------------------------------------------------------
# 4. Reporting
# ---------------------------------------------------------------------------
def print_report(r: dict):
    n_denied = len(r["denied"])
    rate = n_denied / r["total"] * 100 if r["total"] else 0

    print(f"\nDenied Claims Report (as of {AS_OF})")
    print("=" * 66)
    print(f"Total claims        : {r['total']}")
    print(f"Denied claims       : {n_denied} ({rate:.1f}%)")
    print(f"Total billed        : ${r['total_billed']:,.2f}")
    print(f"Denied amount       : ${r['denied_amount']:,.2f}")
    pct = r["preventable_amount"] / r["denied_amount"] * 100 if r["denied_amount"] else 0
    print(f"Preventable denials : ${r['preventable_amount']:,.2f} ({pct:.0f}% of denied $)")

    print("\nDenials by reason")
    print(f"{'Code':<8}{'Description':<40}{'Count':>6}{'Amount':>13}")
    print("-" * 67)
    for code, v in sorted(r["by_reason"].items(), key=lambda x: -x[1]["amount"]):
        desc = DENIAL_CODES.get(code, ("Unknown",))[0]
        print(f"{code:<8}{desc:<40}{v['count']:>6}{v['amount']:>13,.2f}")

    print("\nDenials by category")
    for cat, v in sorted(r["by_category"].items(), key=lambda x: -x[1]["amount"]):
        print(f"  {cat:<16}{v['count']:>4} claims   ${v['amount']:>10,.2f}")

    print(f"\nTop providers by denial rate (min {MIN_PROVIDER_CLAIMS} claims)")
    providers = [(p, v) for p, v in r["by_provider"].items() if v["claims"] >= MIN_PROVIDER_CLAIMS]
    for p, v in sorted(providers, key=lambda x: -x[1]["denied"] / x[1]["claims"])[:5]:
        print(f"  {p:<28}{v['denied']:>3}/{v['claims']:<3} = {v['denied'] / v['claims'] * 100:>5.1f}%   ${v['amount']:>9,.2f}")

    print("\nTop procedure codes by denials")
    for cpt, v in sorted(r["by_cpt"].items(), key=lambda x: -x[1]["denied"])[:5]:
        print(f"  CPT {cpt:<8}{v['denied']:>3}/{v['claims']:<3} = {v['denied'] / v['claims'] * 100:>5.1f}%")

    print("\nMonthly denial trend")
    for month, v in sorted(r["by_month"].items()):
        bar = "#" * round(v["denied"] / v["claims"] * 50) if v["claims"] else ""
        print(f"  {month}  {v['denied']:>3}/{v['claims']:<4} {v['denied'] / v['claims'] * 100:>5.1f}%  {bar}")


def write_action_list(denied: list[dict], path: str):
    rows = []
    for c in denied:
        desc, cat, action, preventable = DENIAL_CODES.get(
            c["denial_code"], ("Unknown", "Other", "Review manually", False))
        rows.append({
            "claim_id": c["claim_id"], "provider": c["provider_name"],
            "service_date": c["service_date"], "cpt_code": c["cpt_code"],
            "billed_amount": c["billed_amount"], "denial_code": c["denial_code"],
            "reason": desc, "category": cat, "preventable": "Yes" if preventable else "No",
            "recommended_action": action, "priority": priority(c["billed_amount"]),
        })
    order = {"High": 0, "Medium": 1, "Low": 2}
    rows.sort(key=lambda x: (order[x["priority"]], -x["billed_amount"]))
    if rows:
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)


# ---------------------------------------------------------------------------
# 5. Sample data generator
# ---------------------------------------------------------------------------
def generate_sample_data(path: str, n: int = 500):
    random.seed(7)
    providers = [(f"P{i:03d}", name) for i, name in enumerate(
        ["City General Hospital", "Sunrise Clinic", "Metro Imaging Center",
         "Green Valley Ortho", "Lakeside Family Care", "Apex Cardiology"], start=1)]
    cpts = {"99213": 120, "99214": 180, "71046": 250, "73721": 900, "93000": 80, "27447": 12000, "80053": 60}
    codes = list(DENIAL_CODES)
    weights = [10, 25, 12, 8, 10, 15, 5, 15]  # aligned with DENIAL_CODES order

    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["claim_id", "member_id", "provider_id", "provider_name", "service_date",
                    "cpt_code", "billed_amount", "status", "denial_code"])
        for i in range(1, n + 1):
            pid, pname = random.choice(providers)
            cpt = random.choice(list(cpts))
            amount = round(cpts[cpt] * random.uniform(0.8, 1.3), 2)
            svc = AS_OF - timedelta(days=random.randint(1, 180))
            deny_chance = 0.30 if pid == "P003" else 0.12  # one weak provider
            denied = random.random() < deny_chance
            w.writerow([f"C{i:05d}", f"M{random.randint(1, 150):04d}", pid, pname, svc, cpt, amount,
                        "Denied" if denied else "Paid",
                        random.choices(codes, weights)[0] if denied else ""])


# ---------------------------------------------------------------------------
# 6. Main
# ---------------------------------------------------------------------------
def main():
    claims_path = "claims.csv"
    if not Path(claims_path).exists():
        print("claims.csv not found - generating sample data...")
        generate_sample_data(claims_path)

    claims = load_claims(claims_path)
    result = analyze(claims)
    print_report(result)
    write_action_list(result["denied"], "denied_claims_action_list.csv")
    print("\nPrioritized action list saved to denied_claims_action_list.csv")


if __name__ == "__main__":
    main()
