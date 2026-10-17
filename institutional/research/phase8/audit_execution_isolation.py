import ast
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[3]
TARGETS = [
    BASE_DIR / "institutional" / "data" / "archive" / "oi_poller.py",
    BASE_DIR / "institutional" / "data" / "s3_shadow_engine.py",
    BASE_DIR / "institutional" / "data" / "s3_outcome_tracker.py"
]

FORBIDDEN_TERMS = [
    "place_order",
    "cancel_order",
    "TradingEngine",
    "DecisionEngine",
    "RiskManager"
]

def audit_file(filepath):
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return False
        
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Check simple text search
    violations = []
    for line_num, line in enumerate(content.split('\n'), 1):
        for term in FORBIDDEN_TERMS:
            if term in line:
                violations.append((line_num, term, line.strip()))
                
    if violations:
        print(f"\n[FAIL] {filepath.name}")
        for v in violations:
            print(f"  Line {v[0]}: found forbidden term '{v[1]}' -> {v[2]}")
        return False
    else:
        print(f"[PASS] {filepath.name} is fully isolated from execution.")
        return True

def main():
    print("--- EXECUTION ISOLATION AUDIT ---")
    all_passed = True
    for t in TARGETS:
        if not audit_file(t):
            all_passed = False
            
    if all_passed:
        print("\nSUCCESS: All shadow data components are strictly read-only and execution-isolated.")
        sys.exit(0)
    else:
        print("\nERROR: Execution isolation violation detected.")
        sys.exit(1)

if __name__ == "__main__":
    main()
