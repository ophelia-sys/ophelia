import ast
import sys
import os

BANNED_TERMS = {
    "TradingEngine", "broker", "DecisionEngine", "RiskManager", 
    "place_order", "close_position", "cancel_order", "BinanceClient", "BingXClient"
}

def audit_file(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        
    tree = ast.parse(content, filename=filepath)
    
    violations = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if node.id in BANNED_TERMS:
                violations.append(f"Line {node.lineno}: Found banned reference '{node.id}'")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in BANNED_TERMS:
                    violations.append(f"Line {node.lineno}: Found banned import '{alias.name}'")
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in BANNED_TERMS:
                    violations.append(f"Line {node.lineno}: Found banned import '{alias.name}'")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in BANNED_TERMS:
                    violations.append(f"Line {node.lineno}: Found banned call '{node.func.id}'")
                    
    return violations

if __name__ == "__main__":
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    cvd_dir = os.path.join(base_dir, "institutional", "cvd")
    
    all_violations = []
    
    for root, dirs, files in os.walk(cvd_dir):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                v = audit_file(path)
                if v:
                    all_violations.append((path, v))
                    
    if all_violations:
        print("SECURITY AUDIT FAILED")
        for path, v in all_violations:
            print(f"File: {path}")
            for msg in v:
                print(f"  - {msg}")
        sys.exit(1)
    else:
        print("SECURITY AUDIT PASSED: No execution references found in CVD engine.")
        sys.exit(0)
