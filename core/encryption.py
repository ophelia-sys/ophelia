import os
import logging
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

def _resolve_encryption_key() -> str:
    """Resolve encryption key from environment or persistent keyfile.
    Never prints or logs the secret key.
    """
    key = os.environ.get("OPH_ENCRYPTION_KEY")
    if key and len(key.strip()) >= 32:
        return key.strip()

    # Search for persistent key file
    candidates = [
        os.path.join(os.environ.get("OPH_DATA_DIR", "/opt/ophelia/control_data"), ".encryption_key"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", ".encryption_key"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "control_data", ".encryption_key"),
    ]

    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    stored = f.read().strip()
                    if stored:
                        return stored
            except Exception as e:
                logger.warning(f"Could not read key file at {path}: {e}")

    # Generate and persist new persistent key (never ephemeral if writable)
    new_key = Fernet.generate_key().decode("utf-8")
    for path in candidates:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_key)
            try:
                os.chmod(path, 0o600)
            except Exception:
                pass
            logger.info(f"Persisted new encryption key to {path}")
            return new_key
        except Exception:
            continue

    logger.warning("Could not persist encryption key to disk; using in-memory key.")
    return new_key

_KEY = _resolve_encryption_key()

try:
    _fernet = Fernet(_KEY.encode("utf-8"))
except Exception as exc:
    logger.error(f"Invalid encryption key format; generating fallback key: {exc}")
    _fernet = Fernet(Fernet.generate_key())

def encrypt(data: str) -> str:
    """Encrypts plaintext to a Fernet token string."""
    if not data:
        return ""
    return _fernet.encrypt(data.encode("utf-8")).decode("utf-8")

def decrypt(token: str) -> str:
    """Decrypts a Fernet token string back to plaintext.
    Returns empty string on failure or for non-encrypted legacy placeholders.
    """
    if not token or token == "LEGACY":
        return ""
    try:
        return _fernet.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""
    except Exception as e:
        logger.debug(f"Decryption failed: {e}")
        return ""

