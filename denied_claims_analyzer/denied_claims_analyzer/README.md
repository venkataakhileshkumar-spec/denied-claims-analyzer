# Denied Claims Analyzer

Analyzes a claims file to show why claims are denied, which providers and
procedures are most affected, how much money is at stake, and what to do next.

## Structure
- `denied_claims_analyzer.py` - main script (Python 3.9+, no dependencies)
- `data/claims.csv` - sample input data
- `output/denied_claims_action_list.csv`, `output/summary.txt` - sample output

## Run
    python denied_claims_analyzer.py

The script reads `claims.csv` from the current folder and generates sample data
if it is missing. To use the bundled sample, copy `data/claims.csv` next to the
script.

## Input format (claims.csv)
claim_id, member_id, provider_id, provider_name, service_date (YYYY-MM-DD),
cpt_code, billed_amount, status (Paid/Denied), denial_code (only when Denied)

Known denial codes: CO-4, CO-16, CO-18, CO-27, CO-29, CO-50, CO-109, CO-197.
Add more in the DENIAL_CODES table at the top of the script.

## What you get
- Denial rate, denied $ and preventable $
- Breakdown by reason, category, provider, CPT code and month
- A prioritized action list (High/Medium/Low by amount) with a recommended fix per claim

Note: denial code mappings are simplified for demonstration.
