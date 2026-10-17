# OPHELIA AG VPS AUDIT

**Date:** 2026-08-26
**Target VPS:** `15.235.193.47` (Ubuntu 26.04 LTS)

## 1. System Services and Environment
- **Ophelia Control Plane:** `ophelia-control.service` is `active (running)`.
- **Ophelia Shadow Engine:** `ophelia-shadow.service` is `active (running)`.
- **Ollama:** `ollama.service` is `active (running)`.
  - Installed models: `qwen3:4b` (2.5 GB) and `qwen3:1.7b` (1.4 GB).
- **Deployment Location:** `/opt/ophelia` (Not a git repository, deployed via archive upload).

## 2. Local vs. VPS Comparison (control_plane)

The local repository is currently **NEWER** than the VPS repository. Several files in the local `control_plane` directory have been modified and expanded since the last VPS deployment.

| File | Local Size (Bytes) | VPS Size (Bytes) | Status |
|---|---|---|---|
| `__init__.py` | 0 | 0 | MATCH |
| `__main__.py` | 2,042 | 2,042 | MATCH |
| `account.py` | 7,622 | 7,622 | MATCH |
| `analytics.py` | 23,137 | 19,426 | **DIFFER (Local is newer/larger)** |
| `bingx_client.py` | 7,329 | 7,329 | MATCH |
| `config.py` | 2,408 | 1,888 | **DIFFER (Local is newer/larger)** |
| `core.py` | 36,430 | 31,766 | **DIFFER (Local is newer/larger)** |
| `db.py` | 15,806 | 15,806 | MATCH |
| `ingest.py` | 3,508 | 3,508 | MATCH |
| `llm.py` | 12,812 | 12,812 | MATCH |
| `news.py` | 3,907 | 3,907 | MATCH |
| `nlg.py` | 26,804 | 26,804 | MATCH |
| `sessions.py` | 1,397 | 1,397 | MATCH |
| `telegram_bot.py` | 78,008 | 78,008 | MATCH |

## 3. What Must Be Deployed

Based on the audit, the following steps must be taken during the deployment phase (Chunk I):
1. **Backup:** A new backup archive of `/opt/ophelia` must be created on the VPS before any modifications.
2. **Synchronization:** The modified local files (`analytics.py`, `config.py`, `core.py`, and any further modifications made during the implementation phase) must be deployed to `/opt/ophelia/control_plane/`.
3. **Service Restart:** The `ophelia-control.service` must be restarted to pick up the changes.
4. **Credential Verification:** Ensure that the temporary SSH password is not persisted anywhere in the local logs, reports, or source code.
