# PHASE 7 VPS SHADOW VALIDATION CHECKLIST

Before the official 24-hour Shadow window begins, all criteria below must pass on the VPS.

## 1. System Check
- [ ] VPS runtime verified (Python, LightGBM version matching local)
- [ ] Required model artifacts transferred via `deploy_vps_shadow.sh`
- [ ] SHA-256 hashes of models match local hashes exactly
- [ ] SHA-256 hash of threshold JSON matches local exactly
- [ ] Features generate without error

## 2. Broker Isolation Check
- [ ] Tests run successfully proving `ShadowBroker` blocks order placements.
- [ ] `OPHELIA_MODE=SHADOW` is correctly enforced via systemd environment.
- [ ] HTTP layer correctly rejects `POST`/`DELETE` attempts to order endpoints.

## 3. Operational Integrity Test
- [ ] Start `ophelia-shadow.service`.
- [ ] Observe first valid completed 5m inference without errors.
- [ ] Observe systemd auto-restart functionality via forced termination (`sudo kill -9`).
- [ ] Confirm automatic market data reconnection after restart.
- [ ] Confirm CVD state builds without fatal drops.
- [ ] Confirm no duplicated decision timestamps in the `[SHADOW_JSON]` logs upon restart.

## 4. Monitoring Check
- [ ] Verify `vps_health_monitor.py` correctly parses json logs and returns heartbeat.
- [ ] Verify disk usage is safe (logs are rotated by `journalctl`).

## 5. Telegram Monitor Check
- [ ] Verify `ophelia-telegram-monitor.service` is running.
- [ ] Verify Telegram API token is loaded from environment variables and NOT hardcoded.
- [ ] Send `/stats` from authorized account and receive live Shadow status.
- [ ] Send `/status` from authorized account and receive valid response.
- [ ] Send `/health` from authorized account and receive valid response.
- [ ] Verify unauthorized user ID is rejected by the bot.

### Sign-off
Only when all items are checked is the platform authorized to record the `SHADOW_START_UTC` in `PHASE7_VPS_SHADOW_DEPLOYMENT.md` and transition to **SHADOW_ACTIVE**.
