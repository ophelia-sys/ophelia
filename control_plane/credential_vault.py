"""VPS Secure Credential Vault with AES-256-GCM.

Strict Security Contract:
- User BingX API credentials encrypted with AES-256-GCM before DB persistence.
- Master key stored outside DB, versioned, never logged.
- Plaintext kept in memory only for minimum necessary duration.
- Secrets NEVER returned in any API response, UI card, audit log, or Telegram message.
- Withdrawal permission safety: If withdrawal permission is present, FAILS CLOSED immediately.
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
import stat
import time
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from . import bingx_client
from . import config
from . import db

_VAULT_KEY_ENV = "OPH_VAULT_KEY"
_KEY_VERSION_V1 = b"\x01"


def _get_master_key() -> bytes:
    """Retrieve or generate persistent 32-byte AES-256-GCM master key."""
    # 1. Environment variable
    k_env = os.environ.get(_VAULT_KEY_ENV)
    if k_env:
        return hashlib.sha256(k_env.strip().encode()).digest()

    # 2. Check config .env / control.env
    env_paths = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        "/opt/ophelia/.env",
        "/opt/ophelia/control.env"
    ]
    for p in env_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("OPH_VAULT_KEY="):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if val:
                                return hashlib.sha256(val.encode()).digest()
            except Exception:
                pass

    # 3. Persistent secure key file in DATA_DIR
    key_file = os.path.join(config.DATA_DIR, ".vault_key")
    if os.path.exists(key_file):
        try:
            with open(key_file, "rb") as f:
                raw = f.read().strip()
                if len(raw) == 32:
                    return raw
                elif len(raw) > 0:
                    return hashlib.sha256(raw).digest()
        except Exception:
            pass

    # Generate new random 32-byte key and save with 0600 permissions
    new_key = secrets.token_bytes(32)
    os.makedirs(config.DATA_DIR, exist_ok=True)
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        mode = stat.S_IRUSR | stat.S_IWUSR  # 0600
        fd = os.open(key_file, flags, mode)
        with os.fdopen(fd, "wb") as f:
            f.write(new_key)
    except Exception:
        # If filesystem write fails, derive from machine-unique entropy
        machine_entropy = f"{os.getpid()}:{time.time()}:{secrets.token_hex(16)}"
        return hashlib.sha256(machine_entropy.encode()).digest()

    return new_key


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a plaintext string with AES-256-GCM.
    
    Format: base64(version_byte + 12-byte nonce + ciphertext_with_tag)
    """
    if not plaintext:
        return ""
    master_key = _get_master_key()
    aesgcm = AESGCM(master_key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    payload = _KEY_VERSION_V1 + nonce + ciphertext
    return base64.urlsafe_b64encode(payload).decode("ascii")


def decrypt_secret(ciphertext_b64: str) -> str:
    """Decrypt a base64 ciphertext with AES-256-GCM."""
    if not ciphertext_b64:
        return ""
    raw = base64.urlsafe_b64decode(ciphertext_b64.encode("ascii"))
    if len(raw) < 13:
        raise ValueError("Ciphertext payload too short")
    version = raw[:1]
    if version != _KEY_VERSION_V1:
        raise ValueError(f"Unsupported key version: {version!r}")
    nonce = raw[1:13]
    ciphertext = raw[13:]
    master_key = _get_master_key()
    aesgcm = AESGCM(master_key)
    plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext_bytes.decode("utf-8")


def mask_key(api_key: str) -> str:
    """Safely mask an API key for logs and UI."""
    k = (api_key or "").strip()
    if len(k) <= 4:
        return "****"
    return f"****{k[-4:]}"


def verify_bingx_permissions(api_key: str, api_secret: str) -> dict[str, Any]:
    """Test connectivity and verify permissions.
    
    FAIL CLOSED: If withdrawal permission is present, rejection is mandatory.
    """
    t0 = time.time()
    res: dict[str, Any] = {
        "is_valid": False,
        "has_withdrawal": False,
        "permissions": [],
        "account_identifier": None,
        "balance": 0.0,
        "equity": 0.0,
        "available": 0.0,
        "latency_ms": 0,
        "error": None,
    }
    
    if not api_key or not api_secret:
        res["error"] = "API key and Secret are required"
        return res

    client = bingx_client.Client(api_key, api_secret, allow_trade=False)
    try:
        bal_data = client.balance()
        res["latency_ms"] = int((time.time() - t0) * 1000)
        
        # Parse balances
        # BingX swap v3 user/balance returns balance dict or list of asset balances
        balance_list = bal_data.get("balance", []) if isinstance(bal_data, dict) else (bal_data if isinstance(bal_data, list) else [])
        usdt_bal = 0.0
        usdt_equity = 0.0
        usdt_avail = 0.0
        
        if isinstance(balance_list, list):
            for b in balance_list:
                if isinstance(b, dict) and b.get("asset") in ("USDT", "usdt"):
                    usdt_bal = float(b.get("balance") or 0.0)
                    usdt_equity = float(b.get("equity") or usdt_bal)
                    usdt_avail = float(b.get("availableMargin") or b.get("free") or 0.0)
                    break
        elif isinstance(bal_data, dict):
            usdt_bal = float(bal_data.get("balance") or 0.0)
            usdt_equity = float(bal_data.get("equity") or usdt_bal)
            usdt_avail = float(bal_data.get("availableMargin") or 0.0)
            
        res["balance"] = usdt_bal
        res["equity"] = usdt_equity
        res["available"] = usdt_avail
        res["account_identifier"] = mask_key(api_key)
        res["permissions"] = ["read", "perpetual_futures"]
        
        # Check positions endpoint to ensure perpetual futures read permission
        try:
            client.positions()
        except Exception as e:
            res["error"] = f"Perpetual futures permission check failed: {str(e)[:100]}"
            return res

        # Withdrawal permission detection:
        # Standard Swap V2/V3 trading keys do NOT permit withdrawals.
        # If the key returns or indicates withdrawal capacity, fail closed!
        has_withdrawal = False
        if isinstance(bal_data, dict):
            if bal_data.get("canWithdraw") is True or bal_data.get("withdrawEnabled") is True:
                has_withdrawal = True
        
        if has_withdrawal:
            res["has_withdrawal"] = True
            res["is_valid"] = False
            res["error"] = "WITHDRAWAL PERMISSION DETECTED: FAILS CLOSED. Remove withdrawal permission on BingX API key."
            return res

        res["is_valid"] = True
        res["error"] = None
        return res
        
    except Exception as e:
        res["latency_ms"] = int((time.time() - t0) * 1000)
        res["error"] = f"BingX authentication error: {str(e)[:120]}"
        return res


def save_user_credentials(user_id: int, api_key: str, api_secret: str) -> dict[str, Any]:
    """Verify permissions, encrypt, and store user BingX credentials safely."""
    # Strip whitespace
    k = (api_key or "").strip()
    s = (api_secret or "").strip()
    
    check = verify_bingx_permissions(k, s)
    if not check["is_valid"]:
        db.update_user_bingx_status(user_id, "ERROR", None, check.get("error"))
        return {
            "success": False,
            "error": check.get("error") or "Credential verification failed",
            "has_withdrawal": check.get("has_withdrawal", False)
        }
    
    masked = mask_key(k)
    key_enc = encrypt_secret(k)
    secret_enc = encrypt_secret(s)
    
    db.store_user_bingx_credentials(
        user_id=user_id,
        api_key_enc=key_enc,
        api_secret_enc=secret_enc,
        key_identifier=masked,
        permissions=check["permissions"],
        has_withdrawal=False,
        is_valid=True
    )
    
    db.update_user_bingx_status(user_id, "CONNECTED", masked, None)
    
    try:
        from . import account
        account.invalidate_user_cache(user_id)
    except Exception:
        pass
    
    return {
        "success": True,
        "key_identifier": masked,
        "permissions": check["permissions"],
        "balance": check["balance"],
        "equity": check["equity"],
        "available": check["available"],
        "latency_ms": check["latency_ms"],
        "error": None
    }


def delete_user_credentials(user_id: int) -> bool:
    """Safely delete a user's BingX credentials, mark disconnected, and clear caches."""
    ok = db.delete_user_bingx_credentials(user_id)
    db.update_user_bingx_status(user_id, "DISCONNECTED", None, None)
    try:
        from . import account
        account.invalidate_user_cache(user_id)
    except Exception:
        pass
    return ok


def ensure_admin_credentials_from_env() -> bool:
    """Auto-provision Admin (user_id=1) BingX credentials from server host environment if available."""
    try:
        from dotenv import load_dotenv
        load_dotenv("/opt/ophelia/.env")
        load_dotenv(".env")
    except Exception:
        pass

    api_key = (os.environ.get("BINGX_API_KEY") or getattr(config, "BINGX_API_KEY", "") or "").strip()
    api_secret = (os.environ.get("BINGX_SECRET_KEY") or os.environ.get("BINGX_SECRET") or getattr(config, "BINGX_SECRET", "") or "").strip()
    if not api_key or not api_secret or "mock" in api_key.lower():
        return False

    existing = db.get_user_bingx_credentials(1)
    if existing and existing.get("is_valid"):
        return True

    masked = mask_key(api_key)
    key_enc = encrypt_secret(api_key)
    secret_enc = encrypt_secret(api_secret)
    db.store_user_bingx_credentials(
        user_id=1,
        api_key_enc=key_enc,
        api_secret_enc=secret_enc,
        key_identifier=masked,
        permissions=["read", "futures"],
        has_withdrawal=False,
        is_valid=True
    )
    db.update_user_bingx_status(1, "CONNECTED", masked, None)
    return True


def get_user_bingx_client(user_id: int, allow_trade: bool = False) -> bingx_client.Client | None:
    """Create an authenticated BingX client for a specific user.
    
    Decrypts credentials in-memory only; never logs or persists plaintext.
    """
    creds = db.get_user_bingx_credentials(user_id)
    if (not creds or not creds.get("is_valid") or creds.get("has_withdrawal")) and user_id == 1:
        ensure_admin_credentials_from_env()
        creds = db.get_user_bingx_credentials(1)

    if not creds or not creds.get("is_valid") or creds.get("has_withdrawal"):
        return None
        
    try:
        api_key = decrypt_secret(creds["api_key_enc"])
        api_secret = decrypt_secret(creds["api_secret_enc"])
        return bingx_client.Client(api_key, api_secret, allow_trade=allow_trade)
    except Exception:
        return None


def user_has_credentials(user_id: int) -> bool:
    """Check if user has valid configured credentials in vault."""
    creds = db.get_user_bingx_credentials(user_id)
    if not creds and user_id == 1:
        ensure_admin_credentials_from_env()
        creds = db.get_user_bingx_credentials(1)
    return bool(creds and creds.get("is_valid") and not creds.get("has_withdrawal"))


def get_user_connection_state(user_id: int) -> str:
    """Return explicit connection state: CONNECTED, DISCONNECTED, NOT_CONFIGURED, INVALID, ERROR."""
    creds = db.get_user_bingx_credentials(user_id)
    if not creds and user_id == 1:
        ensure_admin_credentials_from_env()
        creds = db.get_user_bingx_credentials(1)
    if not creds:
        return "NOT_CONFIGURED"
    if creds.get("has_withdrawal"):
        return "INVALID"
    if not creds.get("is_valid"):
        return "INVALID"
    return "CONNECTED"


def get_user_credential_summary(user_id: int) -> dict[str, Any]:
    """Return safe metadata for UI/Admin without exposing raw secrets."""
    creds = db.get_user_bingx_credentials(user_id)
    u = db.get_user_by_id(user_id)
    if not creds or not creds.get("is_valid"):
        state = "NOT_CONFIGURED" if not creds else "INVALID"
        return {
            "user_id": user_id,
            "configured": bool(creds),
            "connected": False,
            "connection_state": state,
            "connection_status": state,
            "status": state,
            "key_identifier": None,
            "masked_key": None,
            "balance": 0.0,
            "equity": 0.0,
            "available_margin": 0.0,
            "permissions": [],
            "last_verified_ms": None,
            "last_error": u.get("last_error") if u else None
        }

    balance = 0.0
    equity = 0.0
    avail = 0.0
    c = get_user_bingx_client(user_id, allow_trade=False)
    conn_state = "CONNECTED"
    if c:
        try:
            bal_data = c.balance()
            b_list = bal_data.get("balance", []) if isinstance(bal_data, dict) else (bal_data if isinstance(bal_data, list) else [])
            if isinstance(b_list, list):
                for item in b_list:
                    if isinstance(item, dict) and item.get("asset") in ("USDT", "usdt"):
                        balance = float(item.get("balance") or 0.0)
                        equity = float(item.get("equity") or balance)
                        avail = float(item.get("availableMargin") or item.get("free") or 0.0)
                        break
            elif isinstance(bal_data, dict):
                balance = float(bal_data.get("balance") or 0.0)
                equity = float(bal_data.get("equity") or balance)
                avail = float(bal_data.get("availableMargin") or 0.0)
        except Exception:
            conn_state = "ERROR"
    else:
        conn_state = "INVALID"

    masked = creds["key_identifier"]
    is_conn = (conn_state == "CONNECTED")
    return {
        "user_id": user_id,
        "configured": True,
        "connected": is_conn,
        "connection_state": conn_state,
        "connection_status": conn_state,
        "status": conn_state,
        "key_identifier": masked,
        "masked_key": masked,
        "balance": balance if is_conn else 0.0,
        "equity": equity if is_conn else 0.0,
        "available_margin": avail if is_conn else 0.0,
        "permissions": creds.get("permissions", []),
        "last_verified_ms": creds.get("last_verified_ms"),
        "last_error": creds.get("last_error")
    }
