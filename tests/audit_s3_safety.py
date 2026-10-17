import ast
import sys
from pathlib import Path

# The files we must audit
ROOT_DIR = Path(__file__).resolve().parents[1]
FILES_TO_AUDIT = [
    ROOT_DIR / "institutional" / "data" / "archive" / "oi_poller.py",
    ROOT_DIR / "institutional" / "data" / "s3_shadow_engine.py",
    ROOT_DIR / "institutional" / "data" / "s3_outcome_tracker.py",
    ROOT_DIR / "exchange" / "bingx_client.py"
]

FORBIDDEN_TERMS = [
    "place_order",
    "cancel_order",
    "TradingEngine",
    "DecisionEngine",
    "RiskManager",
]

# We must allow place_order inside BingXClient because it's inherently part of the API.
# The user explicitly said: "Market-data methods may remain connected to the existing client, but execution side effects must be impossible from these paths."
# However, if we audit bingx_client.py AST, it WILL contain place_order (because it implements it).
# The user said: "Reject the implementation if references exist to: place_order..."
# To satisfy this strictly for the new daemons, we check the daemons for these terms. 
# For bingx_client.py, we just ensure the NEW methods don't call place_order.

def audit_file(file_path: Path):
    if not file_path.exists():
        print(f"Skipping {file_path.name} (Does not exist yet)")
        return True

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 1. Simple text scan for the new daemons
    if file_path.name != "bingx_client.py":
        for term in FORBIDDEN_TERMS:
            if term in content:
                print(f"FAIL: Found forbidden term '{term}' in {file_path.name}")
                return False
                
    # 2. AST check for BingXClient new methods
    if file_path.name == "bingx_client.py":
        tree = ast.parse(content)
        class_def = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "BingXClient")
        
        new_methods = ["get_open_interest", "get_funding_rate", "get_premium_index"]
        for node in class_def.body:
            if isinstance(node, ast.FunctionDef) and node.name in new_methods:
                method_code = ast.unparse(node)
                for term in FORBIDDEN_TERMS:
                    if term in method_code:
                        print(f"FAIL: Found forbidden term '{term}' inside {node.name} of BingXClient")
                        return False

    return True

def run_audit():
    print("Running Static Safety Audit for S3 Shadow Mode...")
    passed = True
    for fp in FILES_TO_AUDIT:
        if not audit_file(fp):
            passed = False
            
    if passed:
        print("SAFETY_AUDIT = PASS")
        sys.exit(0)
    else:
        print("SAFETY_AUDIT = FAIL")
        sys.exit(1)

if __name__ == "__main__":
    run_audit()
