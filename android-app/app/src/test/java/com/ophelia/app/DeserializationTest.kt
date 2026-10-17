package com.ophelia.app

import com.google.gson.Gson
import com.ophelia.app.models.*
import org.junit.Assert.*
import org.junit.Test

class DeserializationTest {
    private val gson = Gson()

    @Test
    fun testPositionIdLargeIntegerDeserialization() {
        val json = """
            {
                "positions": [
                    {
                        "id": "2093647289470103554",
                        "symbol": "SOL-USDT",
                        "side": "LONG",
                        "entry": 140.5,
                        "current_price": 142.1,
                        "unrealized_pnl": 15.2,
                        "leverage": 15.0,
                        "margin": 100.0,
                        "status": "ACTIVE"
                    }
                ]
            }
        """.trimIndent()

        val response = gson.fromJson(json, PositionsResponse::class.java)
        assertNotNull(response)
        assertEquals(1, response.positions.size)
        assertEquals("2093647289470103554", response.positions[0].id)
    }

    @Test
    fun testDashboardWithNumericLargeIdAndNullToday() {
        val json = """
            {
                "health": {
                    "status": "Healthy",
                    "mode": "SHADOW",
                    "uptime": "Active",
                    "data": "Connected"
                },
                "position": {
                    "id": "2093647289470103554",
                    "symbol": "SOL-USDT",
                    "direction": "LONG",
                    "source": "BINGX MANUAL",
                    "management_status": "EXTERNAL POSITION",
                    "entry": 140.5,
                    "current_price": 142.1,
                    "margin": 100.0,
                    "leverage": 15.0,
                    "unrealized_pnl": 15.2,
                    "unrealized_pnl_pct": 1.14
                },
                "positions": [
                    {
                        "id": "2093647289470103554",
                        "symbol": "SOL-USDT",
                        "direction": "LONG",
                        "source": "BINGX MANUAL",
                        "management_status": "EXTERNAL POSITION",
                        "entry": 140.5,
                        "current_price": 142.1,
                        "margin": 100.0,
                        "leverage": 15.0,
                        "unrealized_pnl": 15.2,
                        "unrealized_pnl_pct": 1.14
                    }
                ],
                "account": {
                    "total_equity": 1000.0,
                    "wallet_balance": 1000.0,
                    "available_margin": 900.0,
                    "ophelia_used": 100.0,
                    "unrealized_pnl": 15.2
                },
                "performance": {
                    "today_pct": 0.0,
                    "yesterday_pct": 0.0,
                    "week_pct": 0.0,
                    "month_pct": 0.0
                },
                "today": null,
                "risk": {
                    "positions_count": 1,
                    "positions_max": 2,
                    "margin_pct": 10.0,
                    "available": 900.0,
                    "status": "NORMAL"
                },
                "last_trades": []
            }
        """.trimIndent()

        val dashboard = gson.fromJson(json, DashboardResponse::class.java)
        assertNotNull(dashboard)
        assertNotNull(dashboard.position)
        assertEquals("2093647289470103554", dashboard.position?.id)
        assertEquals(1, dashboard.positions.size)
        assertEquals("2093647289470103554", dashboard.positions[0].id)
        assertNull(dashboard.today)
    }

    @Test
    fun testTradeHistoryLargeIdDeserialization() {
        val json = """
            {
                "page": 1,
                "limit": 50,
                "total": 1,
                "pages": 1,
                "trades": [
                    {
                        "id": "2093647289470103554",
                        "user_id": 1,
                        "symbol": "BTC-USDT",
                        "direction": "LONG",
                        "entry": 65000.0,
                        "exit_price": 66000.0,
                        "qty": 0.01,
                        "realized_pnl": 10.0,
                        "leverage": 15.0,
                        "status": "CLOSED",
                        "mode": "SHADOW",
                        "opened_ms": 1740000000000,
                        "closed_ms": 1740003600000
                    }
                ]
            }
        """.trimIndent()

        val response = gson.fromJson(json, TradeHistoryResponse::class.java)
        assertNotNull(response)
        assertEquals(1, response.trades.size)
        assertEquals("2093647289470103554", response.trades[0].id)
    }

    @Test
    fun testSetModeRequestSerialization() {
        val shadowReq = SetModeRequest(mode = "SHADOW")
        val paperReq = SetModeRequest(mode = "PAPER")
        val liveReq = SetModeRequest(mode = "LIVE")

        val shadowJson = gson.toJson(shadowReq)
        val paperJson = gson.toJson(paperReq)
        val liveJson = gson.toJson(liveReq)

        assertTrue(shadowJson.contains("\"mode\":\"SHADOW\""))
        assertTrue(paperJson.contains("\"mode\":\"PAPER\""))
        assertTrue(liveJson.contains("\"mode\":\"LIVE\""))
        assertTrue(liveJson.contains("\"target\":\"ACCOUNT\""))

        val deserialized = gson.fromJson(liveJson, SetModeRequest::class.java)
        assertEquals("LIVE", deserialized.mode)
        assertEquals("ACCOUNT", deserialized.target)
    }

    @Test
    fun testModeResponseDeserialization() {
        val jsonSuccess = """{"success": true, "mode": "LIVE"}"""
        val response = gson.fromJson(jsonSuccess, ModeResponse::class.java)
        assertTrue(response.success)
        assertEquals("LIVE", response.mode)

        val jsonShadow = """{"success": true, "mode": "SHADOW"}"""
        val shadowRes = gson.fromJson(jsonShadow, ModeResponse::class.java)
        assertTrue(shadowRes.success)
        assertEquals("SHADOW", shadowRes.mode)
    }

    @Test
    fun testSetModeRetrofitSignatureNoWildcards() {
        val method = com.ophelia.app.network.OpheliaApiService::class.java.methods.firstOrNull { it.name == "setMode" }
        assertNotNull("setMode method must exist on OpheliaApiService", method)
        
        val bodyParamType = method!!.genericParameterTypes[0]
        val typeStr = bodyParamType.toString()
        
        assertEquals(SetModeRequest::class.java, method.parameterTypes[0])
        assertFalse(
            "Body parameter type must not contain wildcard '?': $typeStr",
            typeStr.contains("?")
        )
        assertFalse(
            "Body parameter type must not be raw or wildcard Map: $typeStr",
            typeStr.contains("Map")
        )
    }

    @Test
    fun testDashboardHealthWithSessionsAndDataHealth() {
        val json = """
            {
                "status": "ONLINE",
                "trading_mode": "SHADOW",
                "mode": "SHADOW",
                "core_engine": "RUNNING",
                "market_data": "CONNECTED",
                "bingx": "AUTHENTICATED",
                "last_heartbeat_ms": 1788429660000,
                "uptime_seconds": 2067863,
                "active_automations": 2,
                "open_positions": 0,
                "core": "OK",
                "cpu_pct": 1.2,
                "ram_used_pct": 54.8,
                "ram_available_gb": 3.67,
                "disk_used_pct": 14.2,
                "data_health": {
                    "oldest_1m_utc": "2026-09-02T10:02:00+00:00",
                    "newest_1m_utc": "2026-09-03T10:01:00+00:00",
                    "rows": 5760,
                    "data_age_min": 0.5,
                    "last_cleanup_min_ago": 0.4,
                    "cleanup_ok": true
                },
                "sessions": {
                    "sessions_active_utc": ["LONDON", "NEW_YORK"],
                    "blackout_new_entries": false,
                    "next_daily_reset_ist": "2026-09-04 05:30 IST"
                }
            }
        """.trimIndent()

        val health = gson.fromJson(json, DashboardHealth::class.java)
        assertNotNull(health)
        assertEquals("SHADOW", health.mode)
        assertEquals("SHADOW", health.tradingMode)
        assertEquals("CONNECTED", health.marketData)
        assertEquals("AUTHENTICATED", health.bingx)
        assertEquals(2, health.activeAutomations)
        assertEquals(0, health.openPositions)
        assertEquals(1788429660000L, health.lastHeartbeatMs)
        assertNotNull(health.dataHealth)
        assertEquals(5760, health.dataHealth?.rows)
        assertEquals(0.5, health.dataHealth?.dataAgeMin ?: 0.0, 0.001)
        assertTrue(health.dataHealth?.cleanupOk == true)
        assertNotNull(health.sessions)
        assertEquals(2, health.sessions?.sessionsActiveUtc?.size)
        assertEquals("LONDON", health.sessions?.sessionsActiveUtc?.get(0))
        assertFalse(health.sessions?.blackoutNewEntries == true)
        assertEquals("2026-09-04 05:30 IST", health.sessions?.nextDailyResetIst)
    }

    @Test
    fun testMaxOpenTradesInvariantRiskCap() {
        val json = """
            {
                "positions_count": 0,
                "positions_max": 1,
                "margin_pct": 0.0,
                "available": 1000.0,
                "status": "NORMAL"
            }
        """.trimIndent()

        val risk = gson.fromJson(json, DashboardRisk::class.java)
        assertNotNull(risk)
        assertEquals(1, risk.positionsMax)
        assertEquals(0, risk.positionsCount)
        assertEquals("NORMAL", risk.status)
    }

    @Test
    fun testPositionWithReconciliationAndProtectionDetails() {
        val json = """
            {
                "id": "101",
                "symbol": "BTC-USDT",
                "direction": "LONG",
                "source": "OPHELIA_MANAGED",
                "management_status": "DESYNCED",
                "strategy": "VWAP_SUPERTREND",
                "timeframe": "3m",
                "entry": 65000.0,
                "current_price": 64800.0,
                "qty": 0.05,
                "margin": 216.67,
                "leverage": 15.0,
                "unrealized_pnl": -10.0,
                "unrealized_pnl_pct": -4.61,
                "stops": [64500.0],
                "targets": [66000.0, 67000.0],
                "trailing_pct": 0.8,
                "status": "DESYNC_CLOSED"
            }
        """.trimIndent()

        val pos = gson.fromJson(json, DashboardPositionSummary::class.java)
        assertNotNull(pos)
        assertEquals("DESYNCED", pos.managementStatus)
        assertEquals(1, pos.stops.size)
        assertEquals(64500.0, (pos.stops[0] as Number).toDouble(), 0.01)
        assertEquals(2, pos.targets.size)
        assertEquals(0.8, pos.trailingPct ?: 0.0, 0.001)
        assertEquals(0.05, pos.qty ?: 0.0, 0.0001)

        val isDesynced = pos.managementStatus == "DESYNCED" || pos.status?.contains("RECONCIL") == true
        assertTrue(isDesynced)
    }

    @Test
    fun testMultiStrategyBothSerializationWithIndependentTimeframes() {
        val config = AutomationConfig(
            strategy = "BOTH",
            symbolScope = SymbolScopeDto("ALL_WATCHLIST", emptyList()),
            direction = "ANY",
            marginPct = 45.0,
            leverage = 15,
            mode = "SHADOW",
            strategyTimeframes = mapOf(
                "VWAP_SUPERTREND" to 3,
                "EMA_CROSSOVER" to 1
            ),
            strategyRisk = StrategyRiskMap(
                vwapSupertrend = StrategyRiskConfig(
                    timeframe = 3,
                    hardStopPct = 0.8,
                    structuralStopPct = 0.2,
                    targets = listOf(TargetConfig(1.5, 50.0)),
                    breakEvenAfterPartial = true,
                    trailingStop = TrailingStopConfig(true, 1.0, 0.2)
                ),
                emaCrossover = StrategyRiskConfig(
                    timeframe = 1,
                    hardStopPct = 0.5,
                    structuralStopPct = 0.2,
                    reverseExit = true,
                    targets = listOf(TargetConfig(1.0, 100.0)),
                    breakEvenAfterPartial = false,
                    trailingStop = null
                )
            )
        )

        val json = gson.toJson(config)
        assertTrue(json.contains("\"strategy\":\"BOTH\""))
        assertTrue(json.contains("\"strategy_timeframes\":{\"VWAP_SUPERTREND\":3,\"EMA_CROSSOVER\":1}"))
        assertTrue(json.contains("\"hard_stop_pct\":0.8"))
        assertTrue(json.contains("\"hard_stop_pct\":0.5"))
        assertTrue(json.contains("\"reverse_exit\":true"))

        val deserialized = gson.fromJson(json, AutomationConfig::class.java)
        assertNotNull(deserialized)
        assertEquals("BOTH", deserialized.strategy)
        assertEquals(3, deserialized.strategyTimeframes?.get("VWAP_SUPERTREND"))
        assertEquals(1, deserialized.strategyTimeframes?.get("EMA_CROSSOVER"))
        assertNotNull(deserialized.strategyRisk?.vwapSupertrend)
        assertNotNull(deserialized.strategyRisk?.emaCrossover)
        assertEquals(0.8, deserialized.strategyRisk?.vwapSupertrend?.hardStopPct ?: 0.0, 0.001)
        assertEquals(0.5, deserialized.strategyRisk?.emaCrossover?.hardStopPct ?: 0.0, 0.001)
    }
}
