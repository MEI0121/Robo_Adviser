"""
verify_outputs.py
=================
Quick spot-check of all JSON artefacts produced by data_pipeline.py.
"""
import sys
import json
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASE = Path(__file__).parent.parent / "data" / "processed"

def check(label, condition, detail=""):
    status = "[PASS]" if condition else "[FAIL]"
    msg = f"  {status}  {label}"
    if detail:
        msg += f"  ({detail})"
    print(msg)
    return condition

all_ok = True

# ── mu_vector.json ─────────────────────────────────────────────────────────
print("\n=== mu_vector.json ===")
with open(BASE / "mu_vector.json") as f:
    mu = json.load(f)
all_ok &= check("10 fund codes", len(mu["fund_codes"]) == 10)
all_ok &= check("10 mu values",  len(mu["mu_vector"])   == 10)
all_ok &= check("all finite",    all(isinstance(v, float) for v in mu["mu_vector"]))
print(f"  mu values: {[round(v, 4) for v in mu['mu_vector']]}")

# ── cov_matrix.json ────────────────────────────────────────────────────────
print("\n=== cov_matrix.json ===")
with open(BASE / "cov_matrix.json") as f:
    cov_data = json.load(f)
cov = cov_data["cov_matrix"]
all_ok &= check("10 rows",       len(cov) == 10)
all_ok &= check("10 cols each",  all(len(row) == 10 for row in cov))
is_sym = all(abs(cov[i][j] - cov[j][i]) < 1e-10 for i in range(10) for j in range(10))
all_ok &= check("symmetric",     is_sym)
diag_pos = all(cov[i][i] > 0 for i in range(10))
all_ok &= check("positive diagonal", diag_pos)

# ── gmvp_weights.json ──────────────────────────────────────────────────────
print("\n=== gmvp_weights.json ===")
with open(BASE / "gmvp_weights.json") as f:
    gmvp = json.load(f)
w = gmvp["weights"]
all_ok &= check("10 weights",         len(w) == 10)
all_ok &= check("sum(w) = 1.0",       abs(sum(w) - 1.0) < 1e-6,  f"sum={sum(w):.10f}")
all_ok &= check("all w_i >= 0",       all(wi >= -1e-8 for wi in w), f"min={min(w):.6f}")
all_ok &= check("E(r_p) finite",      isinstance(gmvp["expected_annual_return"], float))
all_ok &= check("sigma_p finite",     isinstance(gmvp["annual_volatility"],     float))
all_ok &= check("Sharpe finite",      isinstance(gmvp["sharpe_ratio"],          float))
print(f"  E(r_p)  = {gmvp['expected_annual_return']*100:.4f}%")
print(f"  sigma_p = {gmvp['annual_volatility']*100:.4f}%")
print(f"  Sharpe  = {gmvp['sharpe_ratio']:.4f}")

# ── frontier_points.json ───────────────────────────────────────────────────
print("\n=== frontier_points.json ===")
with open(BASE / "frontier_points.json") as f:
    fp = json.load(f)
all_ok &= check("exactly 50 points", len(fp) == 50)
all_ok &= check("each point has 10 weights", all(len(p["weights"]) == 10 for p in fp))
all_ok &= check("all weights sum to 1",
                all(abs(sum(p["weights"]) - 1.0) < 1e-5 for p in fp))
vols = [p["volatility"] for p in fp]
mono = all(vols[i] <= vols[i+1] + 1e-8 for i in range(len(vols) - 1))
all_ok &= check("volatilities monotone non-decreasing", mono)
print(f"  vol range: {vols[0]*100:.4f}% -> {vols[-1]*100:.4f}%")
print(f"  ret range: {fp[0]['target_return']*100:.4f}% -> {fp[-1]['target_return']*100:.4f}%")

# ── Summary ────────────────────────────────────────────────────────────────
print("\n" + "=" * 55)
if all_ok:
    print("  ALL JSON ARTEFACT CHECKS PASSED")
else:
    print("  SOME CHECKS FAILED")
print("=" * 55)
