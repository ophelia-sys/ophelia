package com.ophelia.app.models

import com.google.gson.annotations.SerializedName

// --- Auth ---
data class LoginResponse(
    val token: String,
    @SerializedName("user_id") val userId: Long
)

// --- Accounts ---
data class Account(
    val id: Long,
    val exchange: String,
    val name: String,
    val mode: String
)

data class AccountListResponse(val accounts: List<Account>)

data class GenericSuccessResponse(
    val success: Boolean,
    val note: String? = null,
    val balance: Double? = null
)

// --- Market ---
data class WatchlistResponse(val symbols: List<String>)

data class MarketSnapshotResponse(
    val price: Double,
    @SerializedName("price_change_pct") val priceChangePct: Double? = null,
    val volume: Double,
    @SerializedName("volume_24h") val volume24h: Double? = null,
    @SerializedName("volume_24h_base") val volume24hBase: Double? = null,
    @SerializedName("current_candle_volume") val currentCandleVolume: Double? = null,
    @SerializedName("current_candle_base_volume") val currentCandleBaseVolume: Double? = null,
    @SerializedName("current_candle_label") val currentCandleLabel: String? = null,
    @SerializedName("timeframe_volume") val timeframeVolume: Double? = null,
    @SerializedName("timeframe_base_volume") val timeframeBaseVolume: Double? = null,
    @SerializedName("rolling_volume_1h") val rollingVolume1h: Double? = null,
    @SerializedName("rolling_base_volume_1h") val rollingBaseVolume1h: Double? = null,
    @SerializedName("session_volume") val sessionVolume: Double? = null,
    @SerializedName("session_base_volume") val sessionBaseVolume: Double? = null,
    @SerializedName("base_asset") val baseAsset: String? = null,
    @SerializedName("volume_unit") val volumeUnit: String? = null,
    @SerializedName("rvol") val rvol: Double? = null,
    val inflow: Double,
    val outflow: Double,
    @SerializedName("net_flow") val netFlow: Double,
    val vwap: Double,
    @SerializedName("vwap_separation_pct") val vwapSeparationPct: Double,
    @SerializedName("vwap_regime") val vwapRegime: VwapRegime,
    val supertrend: Double,
    @SerializedName("supertrend_direction") val supertrendDirection: String,
    val ema9: Double,
    val ema20: Double,
    @SerializedName("ema_spread") val emaSpread: Double,
    @SerializedName("order_book_skew") val orderBookSkew: Double,
    @SerializedName("market_regime") val marketRegime: String? = null,
    @SerializedName("volatility_regime") val volatilityRegime: String? = null,
    @SerializedName("gamma_regime") val gammaRegime: String? = null,
    @SerializedName("daily_preference") val dailyPreference: String? = null,
    @SerializedName("daily_bias_summary") val dailyBiasSummary: String? = null,
    @SerializedName("allows_counter_trend") val allowsCounterTrend: Boolean? = null,
    @SerializedName("cvd") val cvd: Double? = null,
    @SerializedName("cvi") val cvi: Double? = null,
    @SerializedName("bvin") val bvin: Double? = null,
    @SerializedName("vcrix") val vcrix: Double? = null,
    @SerializedName("htf_4h_structure") val htf4hStructure: String? = null,
    @SerializedName("htf_1d_structure") val htf1dStructure: String? = null,
    @SerializedName("direction") val direction: String? = null,
    @SerializedName("trade_priority") val tradePriority: String? = null,
    @SerializedName("is_priority") val isPriority: Boolean? = null,
    @SerializedName("positioning_regime") val positioningRegime: String? = null,
    @SerializedName("news_macro_context") val newsMacroContext: String? = null,
    @SerializedName("ml_intelligence_bias") val mlIntelligenceBias: String? = null,
    @SerializedName("final_daily_market_bias") val finalDailyMarketBias: String? = null
)

// --- Detailed Engine Health & Subsystems ---
data class SubsystemHealthDto(
    val id: String = "",
    val name: String = "",
    val status: String = "ONLINE",
    @SerializedName("latency_ms") val latencyMs: Double = 0.0,
    val detail: String = "",
    val category: String = "SYSTEM"
)

data class BingxConnectionSubDto(
    val status: String = "CONNECTED",
    val source: String = "VPS",
    @SerializedName("latency_ms") val latencyMs: Double = 0.0,
    val enabled: Boolean = true
)

data class DetailedEngineHealthResponse(
    val status: String = "ONLINE",
    val mode: String = "SHADOW",
    @SerializedName("timestamp_ms") val timestampMs: Long = 0L,
    @SerializedName("uptime_seconds") val uptimeSeconds: Long = 0L,
    val subsystems: List<SubsystemHealthDto> = emptyList(),
    @SerializedName("active_automations") val activeAutomations: Int = 0,
    @SerializedName("open_positions") val openPositions: Int = 0,
    @SerializedName("max_open_trades") val maxOpenTrades: Int = 4,
    @SerializedName("available_slots") val availableSlots: Int = 4,
    @SerializedName("bingx_connection") val bingxConnection: BingxConnectionSubDto? = null
)

// --- Live Terminal Event Stream ---
data class TerminalLineDto(
    val timestamp: String = "",
    @SerializedName("ts_ms") val tsMs: Long = 0L,
    val component: String = "SYSTEM",
    val level: String = "INFO",
    val message: String = ""
)

data class TerminalStreamResponse(
    val lines: List<TerminalLineDto> = emptyList()
)

// --- Persistent VPS Audit Logs ---
data class SystemAuditLogDto(
    val id: Long = 0L,
    @SerializedName("timestamp_iso") val timestampIso: String = "",
    @SerializedName("ts_ms") val tsMs: Long = 0L,
    val component: String = "SYSTEM",
    val action: String = "",
    val detail: Any? = null,
    @SerializedName("user_id") val userId: Long = 1L
)

data class SystemAuditLogsResponse(
    val logs: List<SystemAuditLogDto> = emptyList(),
    val limit: Int = 50,
    val offset: Int = 0
)

// --- BingX Connection & Account Control ---
data class BingxPermissionsDto(
    val read: Boolean = true,
    val futures: Boolean = true,
    val withdrawal: Boolean = false
)

data class BingxConnectionStatusResponse(
    val status: String = "CONNECTED",
    val source: String = "VPS",
    @SerializedName("last_check_ms") val lastCheckMs: Long = 0L,
    @SerializedName("latency_ms") val latencyMs: Double = 0.0,
    val error: String? = null,
    val message: String? = null,
    @SerializedName("account_name") val accountName: String = "Ophelia-Agent",
    val permissions: BingxPermissionsDto = BingxPermissionsDto()
)

data class VwapRegime(
    val eligible: String,
    val state: String
)

// --- Automations ---
data class SymbolScopeDto(
    val mode: String = "SINGLE",
    val symbols: List<String> = emptyList()
)

data class AutomationConfig(
    val id: Long? = null,
    val name: String? = null,
    val strategy: String,
    @SerializedName("symbol_scope") val symbolScope: Any? = null,
    val symbol: String? = null,
    val symbols: List<String>? = null,
    val timeframe: String? = null,
    val direction: String? = null,
    @SerializedName("direction_pref") val directionPref: String? = null,
    @SerializedName("direction_preference") val directionPreference: String? = null,
    @SerializedName("margin_pct") val marginPct: Double? = null,
    @SerializedName("margin_usage_pct") val marginUsagePct: Double? = null,
    @SerializedName("fixed_margin") val fixedMargin: Double? = null,
    @SerializedName("margin_usdt") val marginUsdt: Double? = null,
    val leverage: Int = 15,
    val mode: String? = null,
    val status: String? = "ACTIVE",
    val lifecycle: String = "CONTINUOUS",
    @SerializedName("vwap_gate_enabled") val vwapGateEnabled: Boolean? = true,
    @SerializedName("strategy_risk") val strategyRisk: StrategyRiskMap? = null,
    @SerializedName("strategy_timeframes") val strategyTimeframes: Map<String, Int>? = null,
    @SerializedName("last_evaluated_ms") val lastEvaluatedMs: Long? = null,
    @SerializedName("last_eval_reason") val lastEvalReason: String? = null,
    @SerializedName("last_signal_ms") val lastSignalMs: Long? = null,
    @SerializedName("last_signal_direction") val lastSignalDirection: String? = null,
    @SerializedName("last_execution_status") val lastExecutionStatus: String? = null,
    @SerializedName("candidate_state") val candidateState: String? = null,
    @SerializedName("waiting_reason") val waitingReason: String? = null,
    @SerializedName("slot_info") val slotInfo: Map<String, Any?>? = null,
    @SerializedName("position_status") val positionStatus: String? = null,
    @SerializedName("position_id") val positionId: Any? = null,
    val note: String? = null
)

data class StrategyRiskMap(
    @SerializedName("VWAP_SUPERTREND") val vwapSupertrend: StrategyRiskConfig? = null,
    @SerializedName("EMA_CROSSOVER") val emaCrossover: StrategyRiskConfig? = null
)

data class StrategyRiskConfig(
    val timeframe: Int,
    @SerializedName("hard_stop_pct") val hardStopPct: Double,
    @SerializedName("structural_stop_pct") val structuralStopPct: Double? = null,
    @SerializedName("reverse_exit") val reverseExit: Boolean? = null,
    val targets: List<TargetConfig>,
    @SerializedName("trailing_stop") val trailingStop: TrailingStopConfig? = null,
    @SerializedName("break_even_after_partial") val breakEvenAfterPartial: Boolean
)

data class TargetConfig(
    @SerializedName("distance_pct") val distancePct: Double,
    @SerializedName("qty_pct") val qtyPct: Double
)

data class TrailingStopConfig(
    val enabled: Boolean,
    @SerializedName("activation_pct") val activationPct: Double? = 0.5,
    @SerializedName("trail_pct") val trailPct: Double
)

data class AutomationResponse(
    @SerializedName("automation_id") val automationId: Long? = null,
    val success: Boolean = true,
    val mode: String? = null,
    val strategy: String? = null,
    val status: String? = null,
    val note: String? = null,
    val proposal: Any? = null
)

data class AutomationsListResponse(
    val automations: List<AutomationConfig>
)

// --- Notifications ---
data class NotificationItem(
    val id: Long,
    val category: String, // TRADES, AUTOMATIONS, RISK, SYSTEM, REPORT
    val severity: String, // INFO, SUCCESS, WARNING, CRITICAL
    val title: String,
    val message: String,
    @SerializedName("dedup_key") val dedupKey: String? = null,
    @SerializedName("read_state") val readState: Int = 0,
    @SerializedName("data_json") val dataJson: String? = null,
    @SerializedName("created_ms") val createdMs: Long
)

data class NotificationsResponse(
    val notifications: List<NotificationItem> = emptyList(),
    @SerializedName("unread_count") val unreadCount: Int = 0
)

data class UnreadCountResponse(
    @SerializedName("unread_count") val unreadCount: Int = 0
)

data class NotificationSettingsDto(
    val enabled: Boolean = true,
    @SerializedName("trades_enabled") val tradesEnabled: Boolean = true,
    @SerializedName("tp_sl_enabled") val tpSlEnabled: Boolean = true,
    @SerializedName("risk_enabled") val riskEnabled: Boolean = true,
    @SerializedName("automations_enabled") val automationsEnabled: Boolean = true,
    @SerializedName("system_enabled") val systemEnabled: Boolean = true,
    @SerializedName("equity_4h_enabled") val equity4hEnabled: Boolean = true
)

// --- Positions ---
data class Position(
    val id: String,
    val symbol: String,
    val side: String,
    val strategy: String? = null,
    val timeframe: String? = null,
    val entry: Double,
    @SerializedName("current_price") val currentPrice: Double,
    @SerializedName("movement_pct") val movementPct: Double? = 0.0,
    @SerializedName("unrealized_pnl") val unrealizedPnl: Double,
    @SerializedName("unrealized_pnl_pct") val unrealizedPnlPct: Double? = 0.0,
    val leverage: Double,
    val margin: Double,
    val liquidation: Double? = 0.0,
    @SerializedName("liquidation_price") val liquidationPrice: Double? = null,
    @SerializedName("active_stop") val activeStop: Double? = null,
    @SerializedName("stop_type") val stopType: String? = null,
    @SerializedName("remaining_qty") val remainingQty: Double? = null,
    val qty: Double? = null,
    val status: String,
    val source: String? = "OPHELIA_MANAGED",
    @SerializedName("management_status") val managementStatus: String? = null,
    @SerializedName("automation_id") val automationId: Long? = null,
    @SerializedName("trailing_pct") val trailingPct: Double? = null
)

data class PositionsResponse(
    val positions: List<Position> = emptyList()
)

// --- Ask ---
data class AskResponse(
    val type: String,
    val response: String,
    val proposal: AskProposal? = null
)

data class AskProposal(
    val symbol: String,
    val direction: String,
    val leverage: Int,
    val strategy: String
)

// --- WebSocket Events ---
data class WsMessage(
    val type: String,
    val payload: com.google.gson.JsonElement
)

sealed class WebSocketEvent {
    data class PriceUpdate(val symbol: String, val price: Double) : WebSocketEvent()
    data class IndicatorUpdate(val symbol: String, val vwap: Double, val supertrend: Double, val ema9: Double, val ema20: Double) : WebSocketEvent()
    data class PositionUpdate(val position: Position) : WebSocketEvent()
    data class AutomationUpdate(val automation: AutomationConfig) : WebSocketEvent()
    data class SignalCandidate(val symbol: String, val strategy: String, val direction: String, val confidence: Double) : WebSocketEvent()
    data class AccountUpdate(val account: Account) : WebSocketEvent()
    data class PnlUpdate(val accountId: Long, val realizedPnl: Double, val unrealizedPnl: Double) : WebSocketEvent()
    data class HealthUpdate(val component: String, val status: String) : WebSocketEvent()
    data class NewsUpdate(val symbol: String, val headline: String, val sentiment: Double) : WebSocketEvent()
    object Connected : WebSocketEvent()
    object Disconnected : WebSocketEvent()
    data class Error(val message: String) : WebSocketEvent()
    data class DashboardUpdate(val dashboard: DashboardResponse) : WebSocketEvent()
    data class NotificationEvent(val notification: NotificationItem) : WebSocketEvent()
}

// --- Account Capacity ---
data class AccountCapacity(
    @SerializedName("account_available") val accountAvailable: Double = 0.0,
    @SerializedName("exchange_used") val exchangeUsed: Double = 0.0,
    @SerializedName("ophelia_used") val opheliaUsed: Double = 0.0,
    @SerializedName("automation_reserved") val automationReserved: Double = 0.0,
    @SerializedName("allocatable_remaining") val allocatableRemaining: Double = 0.0,
    @SerializedName("configured_max_open_trades") val configuredMaxOpenTrades: Int = 4,
    @SerializedName("system_safety_max_open_trades") val systemSafetyMaxOpenTrades: Int = 50,
    @SerializedName("open_positions_count") val openPositionsCount: Int = 0,
    @SerializedName("available_execution_slots") val availableExecutionSlots: Int = 4,
    @SerializedName("active_automations_count") val activeAutomationsCount: Int = 0,
    @SerializedName("cap_state") val capState: String = "NORMAL",
    @SerializedName("cap_message") val capMessage: String = "OK"
) {
    val maxOpenTrades: Int get() = configuredMaxOpenTrades
}


// --- Dashboard ---
data class DataHealthDto(
    @SerializedName("oldest_1m_utc") val oldest1mUtc: String? = null,
    @SerializedName("newest_1m_utc") val newest1mUtc: String? = null,
    val rows: Int? = null,
    @SerializedName("data_age_min") val dataAgeMin: Double? = null,
    @SerializedName("last_cleanup_min_ago") val lastCleanupMinAgo: Double? = null,
    @SerializedName("cleanup_ok") val cleanupOk: Boolean? = null
)

data class SessionsDto(
    @SerializedName("sessions_active_utc") val sessionsActiveUtc: List<String> = emptyList(),
    @SerializedName("blackout_new_entries") val blackoutNewEntries: Boolean = false,
    @SerializedName("next_daily_reset_ist") val nextDailyResetIst: String? = null
)

data class DashboardHealth(
    val status: String = "ONLINE",
    val mode: String = "SHADOW",
    @SerializedName("trading_mode") val tradingMode: String? = null,
    @SerializedName("control_plane") val controlPlane: String? = null,
    @SerializedName("core_engine") val coreEngine: String? = null,
    @SerializedName("market_data") val marketData: String? = null,
    val bingx: String? = null,
    val uptime: String? = null,
    @SerializedName("uptime_seconds") val uptimeSeconds: Long? = null,
    val data: String? = null,
    @SerializedName("active_automations") val activeAutomations: Int? = null,
    @SerializedName("open_positions") val openPositions: Int? = null,
    @SerializedName("last_heartbeat_ms") val lastHeartbeatMs: Long? = null,
    val core: String? = null,
    @SerializedName("cpu_pct") val cpuPct: Double? = null,
    @SerializedName("ram_used_pct") val ramUsedPct: Double? = null,
    @SerializedName("ram_available_gb") val ramAvailableGb: Double? = null,
    @SerializedName("disk_used_pct") val diskUsedPct: Double? = null,
    @SerializedName("data_health") val dataHealth: DataHealthDto? = null,
    val sessions: SessionsDto? = null
)

// --- Canonical Provenance ---
enum class DataProvenance(val rawValue: String, val displayLabel: String) {
    @SerializedName("LIVE_BINGX")
    LIVE_BINGX("LIVE_BINGX", "LIVE BINGX"),

    @SerializedName("SHADOW_PAPER")
    SHADOW_PAPER("SHADOW_PAPER", "SHADOW / PAPER"),

    @SerializedName("SIMULATION")
    SIMULATION("SIMULATION", "SIMULATION"),

    @SerializedName("NO_DATA")
    NO_DATA("NO_DATA", "NO DATA");

    companion object {
        fun fromString(value: String?): DataProvenance {
            return when (value?.uppercase()?.trim()) {
                "LIVE_BINGX", "LIVE" -> LIVE_BINGX
                "SHADOW_PAPER", "SHADOW", "PAPER" -> SHADOW_PAPER
                "SIMULATION", "SIM" -> SIMULATION
                "NO_DATA" -> NO_DATA
                else -> if (value.isNullOrBlank()) NO_DATA else SHADOW_PAPER
            }
        }
    }
}

data class DashboardPositionSummary(
    val id: String? = null,
    val symbol: String,
    val direction: String,
    val source: String? = "OPHELIA_MANAGED",
    @SerializedName("management_status") val managementStatus: String? = null,
    val strategy: String? = null,
    val timeframe: String? = null,
    val entry: Double,
    @SerializedName("current_price") val currentPrice: Double,
    val qty: Double? = null,
    val margin: Double,
    val leverage: Double,
    @SerializedName("unrealized_pnl") val unrealizedPnl: Double,
    @SerializedName("unrealized_pnl_pct") val unrealizedPnlPct: Double,
    @SerializedName("liquidation_price") val liquidationPrice: Double? = null,
    val stops: List<Any> = emptyList(),
    val targets: List<Any> = emptyList(),
    @SerializedName("trailing_pct") val trailingPct: Double? = null,
    val status: String? = "ACTIVE",
    val provenance: String? = null
)

data class DashboardAccount(
    @SerializedName("total_equity") val totalEquity: Double,
    @SerializedName("wallet_balance") val walletBalance: Double,
    @SerializedName("available_margin") val availableMargin: Double,
    @SerializedName("ophelia_used") val opheliaUsed: Double,
    @SerializedName("unrealized_pnl") val unrealizedPnl: Double,
    val provenance: String? = null
)

data class DashboardPerformance(
    @SerializedName("today_pct") val todayPct: Double,
    @SerializedName("yesterday_pct") val yesterdayPct: Double,
    @SerializedName("week_pct") val weekPct: Double,
    @SerializedName("month_pct") val monthPct: Double,
    val provenance: String? = null
)

data class DashboardTodayStats(
    val trades: Int = 0,
    val wins: Int = 0,
    val losses: Int = 0,
    @SerializedName("win_rate") val winRate: Double = 0.0,
    @SerializedName("realized_pnl") val realizedPnl: Double = 0.0,
    val fees: Double = 0.0,
    val provenance: String? = null,
    val mode: String? = null,
    val namespace: String? = null
)

data class DashboardRisk(
    @SerializedName("positions_count") val positionsCount: Int,
    @SerializedName("positions_max") val positionsMax: Int,
    @SerializedName("margin_pct") val marginPct: Double,
    val available: Double,
    val status: String
)

data class DashboardTrade(
    val id: String,
    val symbol: String,
    val direction: String,
    val entry: Double,
    @SerializedName("exit_price") val exitPrice: Double,
    val qty: Double,
    @SerializedName("realized_pnl") val realizedPnl: Double,
    val leverage: Double,
    val margin: Double,
    @SerializedName("closed_ms") val closedMs: Long,
    @SerializedName("pnl_pct") val pnlPct: Double,
    val provenance: String? = null
)

data class DashboardSystem(
    val status: String
)

data class DashboardResponse(
    val health: DashboardHealth,
    val position: DashboardPositionSummary? = null,
    val positions: List<DashboardPositionSummary> = emptyList(),
    val account: DashboardAccount,
    val capacity: AccountCapacity? = null,
    val performance: DashboardPerformance,
    val today: DashboardTodayStats? = null,
    val risk: DashboardRisk,
    @SerializedName("last_trades") val lastTrades: List<DashboardTrade> = emptyList(),
    val system: DashboardSystem? = null,
    val provenance: String? = null
)

// --- Contracts ---
data class ContractsResponse(
    val symbols: List<String>
)

// --- Candles ---
data class CandleItem(
    val ts: Long,
    val open: Double,
    val high: Double,
    val low: Double,
    val close: Double,
    val volume: Double,
    @SerializedName("time_utc") val timeUtc: String? = null
)

data class CandlesResponse(
    val symbol: String,
    val timeframe: String,
    val count: Int,
    val candles: List<CandleItem>
)

// --- Trade History ---
data class TradeHistoryItem(
    val id: String,
    @SerializedName("user_id") val userId: Long,
    val symbol: String,
    val direction: String,
    val entry: Double,
    @SerializedName("exit_price") val exitPrice: Double? = 0.0,
    val qty: Double,
    @SerializedName("realized_pnl") val realizedPnl: Double? = 0.0,
    val leverage: Double,
    val margin: Double? = 0.0,
    val status: String,
    val mode: String,
    @SerializedName("opened_ms") val openedMs: Long,
    @SerializedName("closed_ms") val closedMs: Long? = 0L,
    @SerializedName("reason_close") val reasonClose: String? = "",
    @SerializedName("pnl_pct") val pnlPct: Double = 0.0,
    val fees: Double? = 0.0,
    val funding: Double? = 0.0,
    @SerializedName("duration_sec") val durationSec: Long? = 0L,
    val sl: Double? = null,
    val tp: Double? = null,
    val trailing: Double? = null
)

data class TradeHistoryResponse(
    val page: Int,
    val limit: Int,
    val total: Int,
    val pages: Int,
    val trades: List<TradeHistoryItem>
)

// --- Analytics ---
data class EquityCurvePoint(
    val ts: Long,
    val equity: Double,
    val balance: Double,
    val upnl: Double
)

data class AnalyticsResponse(
    @SerializedName("range_days") val rangeDays: Int,
    @SerializedName("total_trades") val totalTrades: Int,
    val wins: Int,
    val losses: Int,
    @SerializedName("win_rate") val winRate: Double,
    @SerializedName("net_pnl") val netPnl: Double,
    @SerializedName("profit_factor") val profitFactor: Double,
    @SerializedName("avg_win") val avgWin: Double,
    @SerializedName("avg_loss") val avgLoss: Double,
    @SerializedName("equity_curve") val equityCurve: List<EquityCurvePoint>
)

// --- Audit Logs ---
data class AuditLogItem(
    val id: Long,
    @SerializedName("user_id") val userId: Long,
    @SerializedName("ts_ms") val tsMs: Long,
    val actor: String,
    val action: String,
    val detail: Map<String, Any>? = null
)

data class AuditLogsResponse(
    val logs: List<AuditLogItem>
)

// --- News ---
data class NewsItem(
    val id: String = "",
    val headline: String = "",
    val impact: String = "MEDIUM",
    val sentiment: String = "NEUTRAL",
    val source: String = "",
    @SerializedName("timestamp_ms") val timestampMs: Long = 0L,
    val symbols: List<String> = emptyList(),
    val title: String? = null,
    val url: String? = null,
    val summary: String? = null
)

data class NewsResponse(
    val news: List<NewsItem>
)

// --- Live Preflight ---
data class PreflightCheckItem(
    val category: String? = null,
    val item: String,
    val passed: Boolean,
    val detail: String
)

data class PreflightResponse(
    @SerializedName("ready_for_live") val readyForLive: Boolean,
    @SerializedName("live_ready") val liveReady: Boolean? = null,
    val checklist: List<PreflightCheckItem>,
    @SerializedName("blocking_reasons") val blockingReasons: List<String> = emptyList(),
    @SerializedName("current_mode") val currentMode: String? = null,
    @SerializedName("execution_gate") val executionGate: String? = null,
    @SerializedName("account_equity") val accountEquity: Double? = null,
    @SerializedName("available_margin") val availableMargin: Double? = null,
    @SerializedName("open_positions_count") val openPositionsCount: Int? = null,
    @SerializedName("positions_max") val positionsMax: Int? = null,
    val warning: String = ""
)

// --- Mode Management ---
data class SetModeRequest(
    val mode: String,
    val target: String = "ACCOUNT",
    @SerializedName("target_id") val targetId: Long? = null
)

data class ModeResponse(
    val success: Boolean,
    val mode: String? = null,
    @SerializedName("execution_gate") val executionGate: String? = null,
    val target: String? = null
)

data class ModeStatusResponse(
    val mode: String = "SHADOW",
    @SerializedName("execution_gate") val executionGate: String = "UNARMED",
    @SerializedName("live_enabled") val liveEnabled: Boolean = false
)

// --- Simulation ---
data class SimulateSignalItem(
    @SerializedName("signal_id") val signalId: Long? = null,
    val symbol: String,
    @SerializedName("timestamp_ms") val timestampMs: Long,
    @SerializedName("iso_utc") val isoUtc: String? = null,
    @SerializedName("time_ist") val timeIst: String? = null,
    @SerializedName("candle_window_ist") val candleWindowIst: String? = null,
    val strategy: String,
    val timeframe: String,
    val price: Double,
    val direction: String,
    @SerializedName("trigger") val trigger: String? = null,
    @SerializedName("vwap_regime") val vwapRegime: String? = null,
    @SerializedName("st_line") val stLine: Double? = null,
    val vwap: Double? = null,
    val status: String,
    @SerializedName("status_detail") val statusDetail: String? = null
)

data class PartialExitItem(
    val stage: String,
    @SerializedName("ts_ms") val tsMs: Long? = null,
    @SerializedName("time_ist") val timeIst: String? = null,
    @SerializedName("candle_window_ist") val candleWindowIst: String? = null,
    val price: Double,
    @SerializedName("qty_pct") val qtyPct: Double,
    @SerializedName("pnl_pct") val pnlPct: Double,
    @SerializedName("realized_pnl_usdt") val realizedPnlUsdt: Double = 0.0
)

data class StrategyFunnelDto(
    @SerializedName("breakout_candidates") val breakoutCandidates: Int = 0,
    @SerializedName("retest_candidates") val retestCandidates: Int = 0,
    @SerializedName("rejection_confirmations") val rejectionConfirmations: Int = 0,
    @SerializedName("final_entries") val finalEntries: Int = 0,
    val reason: String? = null
)

data class StrategySimResultDto(
    val status: String? = null,
    val strategy: String,
    val timeframe: String? = null,
    @SerializedName("fixed_sl_preset") val fixedSlPreset: String? = null,
    @SerializedName("signals_count") val signalsCount: Int = 0,
    @SerializedName("eligible_signals_count") val eligibleSignalsCount: Int? = null,
    @SerializedName("simulated_trades_count") val simulatedTradesCount: Int = 0,
    @SerializedName("win_rate_pct") val winRatePct: Double? = null,
    @SerializedName("net_pnl_pct") val netPnlPct: Double? = null,
    @SerializedName("profit_factor") val profitFactor: Double? = null,
    @SerializedName("net_r") val netR: Double? = null,
    val signals: List<SimulateSignalItem> = emptyList(),
    val trades: List<SimulateTradeItem> = emptyList(),
    val funnel: StrategyFunnelDto? = null
) {
    val tradesCount: Int get() = simulatedTradesCount
}

data class SimulateTradeItem(
    @SerializedName("trade_id") val tradeId: Long? = null,
    val symbol: String = "",
    val direction: String = "LONG",
    val strategy: String? = null,
    val timeframe: String? = null,
    @SerializedName("signal_ts_ms") val signalTsMs: Long? = null,
    @SerializedName("entry_ts_ms") val entryTsMs: Long? = null,
    @SerializedName("entry_time") val entryTime: String? = null,
    @SerializedName("entry_time_ist") val entryTimeIst: String = "",
    @SerializedName("entry_candle_window_ist") val entryCandleWindowIst: String? = null,
    @SerializedName("entry_price") val entryPrice: Double = 0.0,
    @SerializedName("exit_ts_ms") val exitTsMs: Long? = null,
    @SerializedName("exit_time") val exitTime: String? = null,
    @SerializedName("exit_time_ist") val exitTimeIst: String = "",
    @SerializedName("exit_candle_window_ist") val exitCandleWindowIst: String? = null,
    @SerializedName("exit_price") val exitPrice: Double = 0.0,
    @SerializedName("exit_reason") val exitReason: String = "EXIT",
    @SerializedName("partial_exits") val partialExits: List<PartialExitItem> = emptyList(),
    @SerializedName("trailing_activated") val trailingActivated: Boolean = false,
    @SerializedName("peak_price_after_tp") val peakPriceAfterTp: Double? = null,
    @SerializedName("breakeven_activated") val breakevenActivated: Boolean = false,
    @SerializedName("symbol_move_pct") val symbolMovePct: Double? = null,
    @SerializedName("gross_pnl_pct") val grossPnlPct: Double? = null,
    @SerializedName("realized_pnl_pct") val realizedPnlPct: Double = 0.0,
    @SerializedName("realized_pnl_usdt") val realizedPnlUsdt: Double? = null,
    @SerializedName("fee_pct") val feePct: Double? = null,
    @SerializedName("slippage_pct") val slippagePct: Double? = null,
    @SerializedName("funding_pct") val fundingPct: Double? = null,
    @SerializedName("margin_usdt") val marginUsdt: Double? = null,
    val leverage: Double? = null,
    @SerializedName("fees_usdt") val feesUsdt: Double? = null,
    @SerializedName("duration_min") val durationMin: Int? = null,
    val status: String? = null
)

data class SimulateResponse(
    val status: String? = null,
    @SerializedName("date_range_ist") val dateRangeIst: String? = null,
    @SerializedName("lookback_hours") val lookbackHours: Int? = null,
    val strategy: String,
    val strategies: List<String>? = null,
    @SerializedName("symbols_checked") val symbolsChecked: List<String>,
    val timeframe: String? = null,
    val timeframes: List<String>? = null,
    @SerializedName("fixed_sl_preset") val fixedSlPreset: String? = null,
    @SerializedName("trailing_stop_enabled") val trailingStopEnabled: Boolean? = null,
    @SerializedName("vwap_gate") val vwapGate: String? = null,
    @SerializedName("signals_count") val signalsCount: Int,
    @SerializedName("eligible_signals_count") val eligibleSignalsCount: Int? = null,
    @SerializedName("blocked_signals_count") val blockedSignalsCount: Int? = null,
    @SerializedName("filtered_signals_count") val filteredSignalsCount: Int? = null,
    @SerializedName("simulated_trades_count") val simulatedTradesCount: Int? = null,
    @SerializedName("open_at_end_count") val openAtEndCount: Int? = null,
    val signals: List<SimulateSignalItem>,
    val trades: List<SimulateTradeItem>? = null,
    val funnel: StrategyFunnelDto? = null,
    @SerializedName("results_by_strategy") val resultsByStrategy: Map<String, StrategySimResultDto>? = null,
    @SerializedName("win_rate_pct") val winRatePct: Double? = null,
    @SerializedName("net_pnl_pct") val netPnlPct: Double? = null,
    @SerializedName("profit_factor") val profitFactor: Double? = null,
    @SerializedName("max_drawdown_pct") val maxDrawdownPct: Double? = null,
    @SerializedName("net_r") val netR: Double? = null
)

// --- ML & TradingAgents Multi-Agent Advisory ---
data class MlStateDto(
    val symbol: String,
    @SerializedName("timestamp_ms") val timestampMs: Long,
    val framework: String? = null,
    @SerializedName("framework_version") val frameworkVersion: String? = null,
    @SerializedName("framework_commit") val frameworkCommit: String? = null,
    val provider: String? = null,
    val model: String? = null,
    @SerializedName("model_name") val modelName: String,
    @SerializedName("advisory_notice") val advisoryNotice: String,
    @SerializedName("is_advisory") val isAdvisory: Boolean,
    @SerializedName("execution_authority") val executionAuthority: Boolean,
    val regime: String,
    val sentiment: String,
    @SerializedName("directional_bias") val directionalBias: String,
    val confidence: Double,
    val thesis: String? = null,
    @SerializedName("bull_case") val bullCase: String? = null,
    @SerializedName("bear_case") val bearCase: String? = null,
    @SerializedName("technical_summary") val technicalSummary: String? = null,
    @SerializedName("macro_summary") val macroSummary: String? = null,
    @SerializedName("news_summary") val newsSummary: String? = null,
    @SerializedName("missing_conditions") val missingConditions: List<String> = emptyList(),
    @SerializedName("retest_state") val retestState: String? = null,
    @SerializedName("risk_warnings") val riskWarnings: List<String> = emptyList(),
    val features: Map<String, String> = emptyMap(),
    val diagnostics: Map<String, Any> = emptyMap(),
    @SerializedName("symbols_evaluated") val symbolsEvaluated: List<String> = emptyList(),
    @SerializedName("timeframe_states") val timeframeStates: Map<String, String>? = emptyMap(),
    @SerializedName("daily_bias") val dailyBias: DailyStructuralBiasDto? = null
)

data class DailyStructuralBiasDto(
    val symbol: String = "",
    @SerializedName("timestamp_ms") val timestampMs: Long = 0L,
    @SerializedName("daily_preference") val dailyPreference: String = "NEUTRAL",
    @SerializedName("bias_state") val biasState: String = "NO EDGE",
    @SerializedName("confidence_pct") val confidencePct: Double = 50.0,
    @SerializedName("multi_factor_score") val multiFactorScore: Double = 0.0,
    @SerializedName("structural_thesis") val structuralThesis: String = "",
    @SerializedName("supporting_factors") val supportingFactors: List<String> = emptyList(),
    @SerializedName("contradicting_factors") val contradictingFactors: List<String> = emptyList(),
    @SerializedName("key_levels") val keyLevels: Map<String, Any> = emptyMap(),
    @SerializedName("liquidity_map") val liquidityMap: Map<String, Any> = emptyMap(),
    @SerializedName("order_flow_condition") val orderFlowCondition: String = "",
    @SerializedName("news_macro_bias") val newsMacroBias: String = "",
    val invalidation: String = "",
    @SerializedName("what_flips_bias") val whatFlipsBias: String = "",
    val disclaimer: String = "",
    @SerializedName("allows_counter_trend") val allowsCounterTrend: Boolean = true
)

// --- WORLD Macro Context ---
data class SessionContextDto(
    @SerializedName("active_session") val activeSession: String = "NEW YORK",
    @SerializedName("session_progress_pct") val sessionProgressPct: Double = 50.0,
    @SerializedName("next_session") val nextSession: String = "ASIA",
    @SerializedName("utc_time") val utcTime: String = "12:00 UTC"
)

data class MarketEnvironmentDto(
    @SerializedName("risk_sentiment") val riskSentiment: String = "NEUTRAL",
    @SerializedName("daily_bias") val dailyBias: String? = "NEUTRAL",
    @SerializedName("btc_dominance_pct") val btcDominancePct: Double = 52.0,
    @SerializedName("eth_dominance_pct") val ethDominancePct: Double = 16.0,
    @SerializedName("total_24h_volume_usd") val total24hVolumeUsd: String = "$48.2B",
    @SerializedName("aggregate_volatility") val aggregateVolatility: String = "MODERATE",
    @SerializedName("feed_status") val feedStatus: String? = null
)

data class MacroEventDto(
    val title: String = "",
    val event: String? = null,
    @SerializedName("time_utc") val timeUtc: String? = null,
    val impact: String = "MEDIUM",
    val currency: String = "USD",
    val source: String? = null,
    val forecast: String? = null,
    val previous: String? = null,
    val prior: String? = null
)

data class WorldContextDto(
    @SerializedName("timestamp_ms") val timestampMs: Long = 0L,
    val status: String = "REFERENCE",
    @SerializedName("feed_status") val feedStatus: String? = null,
    val notice: String = "",
    @SerializedName("session_context") val sessionContext: SessionContextDto = SessionContextDto(),
    @SerializedName("market_environment") val marketEnvironment: MarketEnvironmentDto = MarketEnvironmentDto(),
    @SerializedName("bullish_reasons") val bullishReasons: List<String> = emptyList(),
    @SerializedName("bearish_reasons") val bearishReasons: List<String> = emptyList(),
    @SerializedName("invalidators") val invalidators: List<String> = emptyList(),
    @SerializedName("yahoo_instruments") val yahooInstruments: Map<String, YahooInstrumentDto> = emptyMap(),
    @SerializedName("macro_events") val macroEvents: List<MacroEventDto> = emptyList(),
    @SerializedName("world_events") val worldEvents: List<WorldEventDto> = emptyList(),
    @SerializedName("news_feed") val newsFeed: List<NewsItem> = emptyList(),
    @SerializedName("market_wide_summary") val marketWideSummary: Map<String, Any> = emptyMap()
)

data class YahooInstrumentDto(
    val symbol: String? = null,
    val price: Double? = null,
    @SerializedName("change_pct") val changePct: Double? = null,
    val status: String? = null,
    @SerializedName("data_status") val dataStatus: String? = null,
    val source: String? = null,
    @SerializedName("updated_ts") val updatedTs: Long? = null
)

data class WorldEventDto(
    val id: String = "",
    val title: String = "",
    val category: String = "MACRO",
    val importance: String = "NORMAL",
    val lat: Double = 0.0,
    val lng: Double = 0.0,
    val region: String = "GLOBAL",
    @SerializedName("timestamp_ms") val timestampMs: Long = 0L,
    val summary: String = "",
    @SerializedName("affected_assets") val affectedAssets: List<String> = emptyList(),
    @SerializedName("ophelia_relevance") val opheliaRelevance: String = "",
    @SerializedName("data_status") val dataStatus: String = "REFERENCE",
    val status: String? = "REFERENCE",
    val source: String? = null,
    val freshness: String? = null
)

data class WorldMapResponse(
    val events: List<WorldEventDto> = emptyList(),
    val calendar: List<Map<String, Any>> = emptyList(),
    @SerializedName("yahoo_macro") val yahooMacro: Map<String, Any> = emptyMap(),
    @SerializedName("timestamp_ms") val timestampMs: Long = 0L
)

data class SymbolIntelligenceDto(
    val symbol: String,
    val status: String = "READY",
    @SerializedName("last_analysis_ms") val lastAnalysisMs: Long = 0L,
    @SerializedName("latency_ms") val latencyMs: Long = 0L,
    val thesis: String = "",
    @SerializedName("directional_bias") val directionalBias: String = "NEUTRAL",
    @SerializedName("confidence_pct") val confidencePct: Double = 50.0,
    @SerializedName("retest_state") val retestState: String = "IDLE",
    val opportunities: List<String> = emptyList(),
    val risks: List<String> = emptyList(),
    @SerializedName("active_setups_count") val activeSetupsCount: Int = 0,
    val model: String = "qwen3:4b",
    @SerializedName("data_cutoff_ms") val dataCutoffMs: Long = 0L
)

data class MlIntelligenceResponse(
    val status: String = "ONLINE",
    val model: String = "qwen3:4b",
    val symbols: List<SymbolIntelligenceDto> = emptyList(),
    @SerializedName("recent_analyses") val recentAnalyses: List<Map<String, Any>> = emptyList(),
    val scheduler: Map<String, Any> = emptyMap()
)

data class CandidateConditionDto(
    val name: String = "",
    val status: String = "PENDING",
    val required: Boolean = true,
    val detail: String = "",
    @SerializedName("timestamp_ms") val timestampMs: Long = 0L
)

data class SetupCandidateDto(
    @SerializedName("setup_id") val setupId: String,
    @SerializedName("candidate_id") val candidateId: String? = null,
    val symbol: String,
    @SerializedName("display_symbol") val displaySymbol: String? = null,
    @SerializedName("venue_symbol") val venueSymbol: String? = null,
    val direction: String,
    val timeframe: Int,
    val strategy: String,
    @SerializedName("current_state") val currentState: String,
    val reason: String = "",
    @SerializedName("waiting_for") val waitingFor: String? = null,
    @SerializedName("next_required_event") val nextRequiredEvent: String? = null,
    @SerializedName("distance_pct") val distancePct: Double? = null,
    @SerializedName("distance_atr") val distanceAtr: Double? = null,
    val priority: String? = null,
    @SerializedName("priority_reasons") val priorityReasons: List<String> = emptyList(),
    val conditions: List<CandidateConditionDto> = emptyList(),
    @SerializedName("actionability_score") val actionabilityScore: Double? = null,
    @SerializedName("structural_invalidation") val structuralInvalidation: String? = null,
    @SerializedName("expected_horizon") val expectedHorizon: String? = null,
    @SerializedName("data_freshness") val dataFreshness: Map<String, Any>? = null,
    val zone: Map<String, Any>? = null,
    val vwap: Double = 0.0,
    @SerializedName("breakout_price") val breakoutPrice: Double? = null,
    @SerializedName("entry_price") val entryPrice: Double? = null,
    @SerializedName("retest_state") val retestState: String? = null,
    @SerializedName("cvd_confirmed") val cvdConfirmed: Boolean = false,
    @SerializedName("rvol_confirmed") val rvolConfirmed: Boolean = false,
    @SerializedName("fvg_confirmed") val fvgConfirmed: Boolean = false,
    @SerializedName("entry_conditions") val entryConditions: Map<String, Any> = emptyMap(),
    @SerializedName("confirmation_conditions") val confirmationConditions: Map<String, Any> = emptyMap(),
    val invalidation: Map<String, Any> = emptyMap(),
    @SerializedName("suggested_sl") val suggestedSl: Double = 0.0,
    @SerializedName("suggested_tp1") val suggestedTp1: Double = 0.0,
    @SerializedName("suggested_tp2") val suggestedTp2: Double = 0.0,
    @SerializedName("suggested_tp3") val suggestedTp3: Double? = null,
    @SerializedName("risk_distance") val riskDistance: Double? = null,
    @SerializedName("reward_distance_tp1") val rewardDistanceTp1: Double? = null,
    @SerializedName("reward_distance_tp2") val rewardDistanceTp2: Double? = null,
    @SerializedName("reward_distance_tp3") val rewardDistanceTp3: Double? = null,
    @SerializedName("reward_risk_ratio") val rewardRiskRatio: Double? = null,
    @SerializedName("reward_risk_tp1") val rewardRiskTp1: Double? = null,
    @SerializedName("reward_risk_tp2") val rewardRiskTp2: Double? = null,
    @SerializedName("reward_risk_tp3") val rewardRiskTp3: Double? = null,
    @SerializedName("sl_distance_pct") val slDistancePct: Double? = null,
    @SerializedName("tp1_distance_pct") val tp1DistancePct: Double? = null,
    @SerializedName("tp2_distance_pct") val tp2DistancePct: Double? = null,
    @SerializedName("tp3_distance_pct") val tp3DistancePct: Double? = null,
    @SerializedName("tp1_qty_pct") val tp1QtyPct: Double? = 30.0,
    @SerializedName("tp2_qty_pct") val tp2QtyPct: Double? = 40.0,
    @SerializedName("tp3_qty_pct") val tp3QtyPct: Double? = 30.0,
    @SerializedName("margin_recommendation") val marginRecommendation: Double? = 25.0,
    @SerializedName("leverage_recommendation") val leverageRecommendation: Double? = 15.0,
    @SerializedName("risk_reward") val riskReward: Double = 1.5,
    @SerializedName("confidence_pct") val confidencePct: Double = 65.0,
    @SerializedName("ai_confidence") val aiConfidence: Double? = null,
    @SerializedName("probability_event") val probabilityEvent: Double? = null,
    @SerializedName("probability_success") val probabilitySuccess: Double? = null,
    @SerializedName("estimated_event_probability") val estimatedEventProbability: Double? = null,
    @SerializedName("model_estimated_trigger_likelihood") val modelEstimatedTriggerLikelihood: String? = null,
    @SerializedName("empirical_success_probability") val empiricalSuccessProbability: Double? = null,
    @SerializedName("calibration_status") val calibrationStatus: String? = "NOT CALIBRATED",
    val thesis: String = "",
    @SerializedName("bull_case") val bullCase: String? = null,
    @SerializedName("bear_case") val bearCase: String? = null,
    val reasons: Map<String, Any>? = emptyMap(),
    @SerializedName("missing_conditions") val missingConditions: List<String>? = emptyList(),
    @SerializedName("snapshot_hash") val snapshotHash: String? = null,
    @SerializedName("target_provenance") val targetProvenance: Map<String, Any>? = null,
    @SerializedName("is_geometry_valid") val isGeometryValid: Boolean = true,
    @SerializedName("geometry_validation_error") val geometryValidationError: String? = null,
    @SerializedName("is_priority") val isPriority: Boolean? = null,
    @SerializedName("priority_reason") val priorityReason: String? = null,
    @SerializedName("priority_status") val priorityStatus: String? = null,
    @SerializedName("generated_ms") val generatedMs: Long = 0L,
    @SerializedName("expires_ms") val expiresMs: Long = 0L,
    val status: String = "ACTIVE"
)

data class SetupCandidatesResponse(
    val setups: List<SetupCandidateDto> = emptyList(),
    val count: Int = 0,
    val symbol: String? = null,
    val timeframe: Int? = null,
    @SerializedName("generated_at") val generatedAt: Long = 0L
)

data class CreateAutomationFromSetupResponse(
    val success: Boolean,
    @SerializedName("automation_id") val automationId: Long,
    @SerializedName("setup_id") val setupId: String,
    val symbol: String,
    val direction: String,
    val strategy: String,
    val origin: String? = null,
    @SerializedName("origin_label") val originLabel: String? = null,
    @SerializedName("vwap_gate_enabled") val vwapGateEnabled: Boolean = false
)

data class SystemControlResponse(
    @SerializedName("current_mode") val currentMode: String = "SHADOW",
    @SerializedName("live_execution") val liveExecution: String = "OFF",
    @SerializedName("live_preflight") val livePreflight: String = "BLOCKED",
    @SerializedName("execution_block") val executionBlock: String = "ACTIVE",
    @SerializedName("max_open_trades") val maxOpenTrades: Int = 4,
    @SerializedName("configured_max_open_trades") val configuredMaxOpenTrades: Int = 4,
    @SerializedName("system_safety_max_open_trades") val systemSafetyMaxOpenTrades: Int = 50,
    @SerializedName("available_execution_slots") val availableExecutionSlots: Int = 4,
    @SerializedName("active_automations_count") val activeAutomationsCount: Int = 0,
    @SerializedName("cap_state") val capState: String = "NORMAL",
    @SerializedName("cap_message") val capMessage: String = "OK",
    @SerializedName("bingx_auth") val bingxAuth: String = "NOT CONNECTED",
    @SerializedName("market_data") val marketData: String = "CONNECTED",
    @SerializedName("risk_engine") val riskEngine: String = "OK",
    @SerializedName("reconciliation") val reconciliation: String = "OK",
    @SerializedName("ollama") val ollama: String = "ONLINE",
    @SerializedName("tradingagents") val tradingagents: String = "ONLINE",
    val checklist: List<PreflightCheckItem> = emptyList(),
    @SerializedName("blocking_reasons") val blockingReasons: List<String> = emptyList(),
    @SerializedName("account_equity") val accountEquity: Double = 0.0,
    @SerializedName("available_margin") val availableMargin: Double = 0.0,
    @SerializedName("open_positions_count") val openPositionsCount: Int = 0
)


data class WorldNewsItemDto(
    val title: String,
    val source: String,
    val url: String? = null,
    @SerializedName("country_region") val countryRegion: String? = null,
    @SerializedName("published_time_utc") val publishedTimeUtc: String? = null,
    @SerializedName("updated_time_utc") val updatedTimeUtc: String? = null,
    @SerializedName("published_ts") val publishedTs: Long = 0L,
    val category: String,
    val status: String,
    @SerializedName("feed_status") val feedStatus: String? = "LIVE",
    val summary: String = "",
    @SerializedName("affected_assets") val affectedAssets: List<String> = emptyList(),
    val relevance: String? = null,
    @SerializedName("market_reaction") val marketReaction: Any? = null,
    @SerializedName("short_summary") val shortSummary: String? = null,
    @SerializedName("what_changed") val whatChanged: String? = null,
    @SerializedName("why_it_matters") val whyItMatters: String? = null,
    @SerializedName("market_transmission") val marketTransmission: String? = null,
    @SerializedName("btc_impact") val btcImpact: String? = null,
    @SerializedName("gold_impact") val goldImpact: String? = null,
    @SerializedName("bullish_case") val bullishCase: String? = null,
    @SerializedName("bearish_case") val bearishCase: String? = null,
    @SerializedName("current_market_confirmation") val currentMarketConfirmation: String? = null,
    @SerializedName("trade_relevance") val tradeRelevance: String? = null
)

data class EconomicEventDto(
    @SerializedName("event_id") val eventId: String? = null,
    @SerializedName("event_name") val eventName: String? = null,
    val id: String? = null,
    val title: String,
    val event: String? = null,
    val impact: String,
    val importance: String? = null,
    val currency: String,
    val country: String? = null,
    @SerializedName("scheduled_ts") val scheduledTs: Long = 0L,
    @SerializedName("scheduled_time") val scheduledTime: String? = null,
    @SerializedName("time_utc") val timeUtc: String? = null,
    val source: String? = null,
    val actual: String? = null,
    val forecast: String? = null,
    val previous: String? = null,
    val surprise: String? = null,
    val category: String,
    val status: String,
    @SerializedName("affected_assets") val affectedAssets: List<String> = emptyList(),
    val relevance: String? = null
)

data class NewsTradeCandidateDto(
    @SerializedName("candidate_id") val candidateId: String,
    val symbol: String,
    @SerializedName("display_symbol") val displaySymbol: String? = null,
    @SerializedName("venue_symbol") val venueSymbol: String? = null,
    val direction: String,
    val timeframe: Int = 15,
    val source: String = "NEWS EVENT",
    @SerializedName("event_id") val eventId: String? = null,
    @SerializedName("event_name") val eventName: String,
    @SerializedName("event_impact") val eventImpact: String,
    val surprise: String,
    @SerializedName("eligibility_status") val eligibilityStatus: String,
    @SerializedName("eligibility_label") val eligibilityLabel: String? = null,
    @SerializedName("relevance_explanation") val relevanceExplanation: String,
    val thesis: String,
    @SerializedName("entry_price") val entryPrice: Double,
    @SerializedName("suggested_sl") val suggestedSl: Double,
    @SerializedName("suggested_tp1") val suggestedTp1: Double,
    @SerializedName("suggested_tp2") val suggestedTp2: Double? = null,
    @SerializedName("suggested_tp3") val suggestedTp3: Double? = null,
    @SerializedName("risk_distance") val riskDistance: Double? = null,
    @SerializedName("reward_distance_tp1") val rewardDistanceTp1: Double? = null,
    @SerializedName("reward_distance_tp2") val rewardDistanceTp2: Double? = null,
    @SerializedName("reward_distance_tp3") val rewardDistanceTp3: Double? = null,
    @SerializedName("reward_risk_ratio") val rewardRiskRatio: Double = 1.5,
    @SerializedName("sl_distance_pct") val slDistancePct: Double = 0.0,
    @SerializedName("tp1_distance_pct") val tp1DistancePct: Double = 0.0,
    @SerializedName("tp2_distance_pct") val tp2DistancePct: Double? = null,
    @SerializedName("tp3_distance_pct") val tp3DistancePct: Double? = null,
    @SerializedName("recommended_tp1_pct") val recommendedTp1Pct: Double = 30.0,
    @SerializedName("recommended_tp2_pct") val recommendedTp2Pct: Double = 40.0,
    @SerializedName("recommended_tp3_pct") val recommendedTp3Pct: Double = 30.0,
    @SerializedName("recommended_margin") val recommendedMargin: Double = 25.0,
    @SerializedName("recommended_leverage") val recommendedLeverage: Double = 10.0,
    @SerializedName("recommended_quantity") val recommendedQuantity: Double = 0.0,
    @SerializedName("ai_confidence") val aiConfidence: Double = 70.0,
    @SerializedName("calibration_status") val calibrationStatus: String = "NOT CALIBRATED",
    @SerializedName("trigger_time_window") val triggerTimeWindow: String? = null,
    @SerializedName("price_confirmation") val priceConfirmation: String? = null,
    @SerializedName("generated_ms") val generatedMs: Long = 0L,
    val status: String = "TRADE_ELIGIBLE"
)

// --- 48-Hour Historical Backtest Models ---
data class BacktestTradeDto(
    @SerializedName("trade_id") val tradeId: String = "",
    val symbol: String = "",
    val timeframe: String = "5m",
    val direction: String = "LONG",
    @SerializedName("setup_id") val setupId: String = "",
    @SerializedName("detection_ts") val detectionTs: Long = 0L,
    @SerializedName("entry_ts") val entryTs: Long = 0L,
    @SerializedName("entry_price") val entryPrice: Double = 0.0,
    @SerializedName("initial_sl") val initialSl: Double = 0.0,
    @SerializedName("exit_ts") val exitTs: Long = 0L,
    @SerializedName("exit_price") val exitPrice: Double = 0.0,
    @SerializedName("exit_reason") val exitReason: String = "",
    @SerializedName("tp1_price") val tp1Price: Double = 0.0,
    @SerializedName("tp2_price") val tp2Price: Double = 0.0,
    @SerializedName("tp3_price") val tp3Price: Double = 0.0,
    @SerializedName("tp1_hit") val tp1Hit: Boolean = false,
    @SerializedName("tp2_hit") val tp2Hit: Boolean = false,
    @SerializedName("tp3_hit") val tp3Hit: Boolean = false,
    val notional: Double = 0.0,
    val margin: Double = 0.0,
    @SerializedName("gross_pnl") val grossPnl: Double = 0.0,
    val fees: Double = 0.0,
    val slippage: Double = 0.0,
    @SerializedName("total_costs") val totalCosts: Double = 0.0,
    @SerializedName("net_pnl") val netPnl: Double = 0.0,
    @SerializedName("r_multiple") val rMultiple: Double = 0.0,
    @SerializedName("mfe_pct") val mfePct: Double = 0.0,
    @SerializedName("mae_pct") val maePct: Double = 0.0,
    val result: String = "BE",
    val provenance: String = "DETERMINISTIC",
    @SerializedName("conditions_satisfied") val conditionsSatisfied: List<String> = emptyList()
)

data class BacktestMetricsDto(
    @SerializedName("total_setups") val totalSetups: Int = 0,
    @SerializedName("eligible_setups") val eligibleSetups: Int = 0,
    @SerializedName("executed_trades") val executedTrades: Int = 0,
    val wins: Int = 0,
    val losses: Int = 0,
    val breakevens: Int = 0,
    @SerializedName("win_rate_pct") val winRatePct: Double = 0.0,
    @SerializedName("profit_factor") val profitFactor: Double = 0.0,
    @SerializedName("net_return_pct") val netReturnPct: Double = 0.0,
    @SerializedName("net_r") val netR: Double = 0.0,
    @SerializedName("expectancy_r") val expectancyR: Double = 0.0,
    @SerializedName("avg_win_r") val avgWinR: Double = 0.0,
    @SerializedName("avg_loss_r") val avgLossR: Double = 0.0,
    @SerializedName("median_r") val medianR: Double = 0.0,
    @SerializedName("gross_pnl_usdt") val grossPnlUsdt: Double = 0.0,
    @SerializedName("total_fees_usdt") val totalFeesUsdt: Double = 0.0,
    @SerializedName("cost_pct_of_gross") val costPctOfGross: Double = 0.0,
    @SerializedName("cost_per_trade_usdt") val costPerTradeUsdt: Double = 0.0,
    @SerializedName("net_return_usdt") val netReturnUsdt: Double = 0.0,
    @SerializedName("net_roi_pct") val netRoiPct: Double = 0.0,
    @SerializedName("max_drawdown_usdt") val maxDrawdownUsdt: Double = 0.0,
    @SerializedName("max_drawdown_pct") val maxDrawdownPct: Double = 0.0,
    @SerializedName("ending_equity_usdt") val endingEquityUsdt: Double = 0.0
)

data class BacktestScopeDto(
    val symbols: List<String> = emptyList(),
    @SerializedName("total_watchlist_count") val totalWatchlistCount: Int = 5,
    val timeframes: List<String> = emptyList(),
    @SerializedName("window_hours") val windowHours: Int = 48,
    @SerializedName("start_time_utc") val startTimeUtc: String = "",
    @SerializedName("end_time_utc") val endTimeUtc: String = "",
    @SerializedName("initial_capital_usdt") val initialCapitalUsdt: Double = 1000.0,
    @SerializedName("risk_pct_per_trade") val riskPctPerTrade: Double = 0.01,
    @SerializedName("margin_per_trade_usdt") val marginPerTradeUsdt: Double? = null,
    val leverage: Double = 10.0,
    @SerializedName("max_open_trades") val maxOpenTrades: Int = 4,
    @SerializedName("max_open_trades_source") val maxOpenTradesSource: String = "PRODUCTION_AUTHORITATIVE",
    @SerializedName("fee_rate_bps") val feeRateBps: Int = 5,
    @SerializedName("slippage_rate_bps") val slippageRateBps: Int = 2
)

data class BacktestBreakdownItemDto(
    val status: String = "CONFIRMED DATA",
    val trades: Int = 0,
    val wins: Int = 0,
    @SerializedName("win_rate") val winRate: Double = 0.0,
    @SerializedName("net_r") val netR: Double = 0.0,
    @SerializedName("net_pnl") val netPnl: Double = 0.0
)

data class BacktestResponseDto(
    val status: String = "COMPLETED",
    val label: String = "BACKTEST / HISTORICAL SIMULATION (DETERMINISTIC)",
    @SerializedName("provenance_mode") val provenanceMode: String = "DETERMINISTIC",
    @SerializedName("is_deterministic") val isDeterministic: Boolean = true,
    @SerializedName("is_ml_assisted") val isMlAssisted: Boolean = false,
    val scope: BacktestScopeDto = BacktestScopeDto(),
    val metrics: BacktestMetricsDto = BacktestMetricsDto(),
    @SerializedName("performance_by_symbol") val performanceBySymbol: Map<String, BacktestBreakdownItemDto> = emptyMap(),
    @SerializedName("performance_by_timeframe") val performanceByTimeframe: Map<String, BacktestBreakdownItemDto> = emptyMap(),
    @SerializedName("performance_by_direction") val performanceByDirection: Map<String, BacktestBreakdownItemDto> = emptyMap(),
    val trades: List<BacktestTradeDto> = emptyList(),
    @SerializedName("timestamp_ms") val timestampMs: Long = 0L
)

// --- Primary ML Setup Historical Replay Models ---
data class ReplayGeometryDto(
    @SerializedName("entry_pct") val entryPct: Double = 0.0,
    @SerializedName("sl_pct") val slPct: Double = 0.0,
    @SerializedName("tp1_pct") val tp1Pct: Double = 0.0,
    @SerializedName("tp1_r") val tp1R: Double = 0.0,
    @SerializedName("tp2_pct") val tp2Pct: Double = 0.0,
    @SerializedName("tp2_r") val tp2R: Double = 0.0,
    @SerializedName("tp3_pct") val tp3Pct: Double = 0.0,
    @SerializedName("tp3_r") val tp3R: Double = 0.0
)

data class ReplayFrozenSetupDto(
    @SerializedName("setup_id") val setupId: String = "",
    val symbol: String = "",
    val direction: String = "LONG",
    val timeframe: Int = 5,
    @SerializedName("timeframe_label") val timeframeLabel: String = "5m",
    val entry: Double = 0.0,
    val sl: Double = 0.0,
    val tp1: Double = 0.0,
    val tp2: Double = 0.0,
    val tp3: Double = 0.0,
    @SerializedName("ai_confidence") val aiConfidence: Double = 70.0,
    val thesis: String = "",
    @SerializedName("snapshot_hash") val snapshotHash: String? = null,
    @SerializedName("is_geometry_valid") val isGeometryValid: Boolean = true,
    @SerializedName("geometry_validation_error") val geometryValidationError: String? = null,
    val geometry: ReplayGeometryDto = ReplayGeometryDto()
)

data class ReplayDataAvailabilityDto(
    val status: String = "48H CONFIRMED DATA AVAILABLE",
    @SerializedName("is_full_48h") val isFull48h: Boolean = true,
    @SerializedName("available_span_hours") val availableSpanHours: Double = 48.0,
    @SerializedName("data_source") val dataSource: String = "BINGX (PRIMARY)",
    @SerializedName("cvd_status") val cvdStatus: String = "CONFIRMED CVD TAKER FLOW"
)

data class ReplayDeterministicEvidenceDto(
    val breakout: Boolean = true,
    val retest: Boolean = true,
    val cvd: String = "ALIGNED",
    val rvol: Double = 1.0,
    val structure: String = "BOS CONFIRMED",
    val vwap: String = "ACCEPTED",
    val fvg: String = "SUPPORTIVE"
)

data class ReplayQualityLayersDto(
    @SerializedName("technical_quality") val technicalQuality: String = "VALID",
    @SerializedName("tradingagents_decision") val tradingAgentsDecision: String = "LONG",
    @SerializedName("qwen_decision") val qwenDecision: String = "LONG",
    @SerializedName("ai_confidence_pct") val aiConfidencePct: Double = 75.0,
    @SerializedName("confidence_agreement_pct") val confidenceAgreementPct: Double = 100.0,
    @SerializedName("direction_agreement") val directionAgreement: Boolean = true,
    @SerializedName("deterministic_validation") val deterministicValidation: Boolean = true,
    @SerializedName("deterministic_validation_status") val deterministicValidationStatus: String = "VALIDATED",
    @SerializedName("ml_status") val mlStatus: String = "SIMULATED_REPLAY"
)

data class HistoricalMatchDto(
    @SerializedName("match_number") val matchNumber: Int = 1,
    val timestamp: Long = 0L,
    @SerializedName("timestamp_utc") val timestampUtc: String = "",
    val symbol: String = "",
    val timeframe: String = "5m",
    val direction: String = "LONG",
    @SerializedName("match_score_pct") val matchScorePct: Double = 0.0,
    @SerializedName("why_matched") val whyMatched: String = "",
    @SerializedName("which_matched") val whichMatched: List<String> = emptyList(),
    @SerializedName("which_differed") val whichDiffered: List<String> = emptyList(),
    @SerializedName("deterministic_evidence") val deterministicEvidence: ReplayDeterministicEvidenceDto = ReplayDeterministicEvidenceDto(),
    @SerializedName("quality_layers") val qualityLayers: ReplayQualityLayersDto = ReplayQualityLayersDto(),
    val geometry: ReplayGeometryDto = ReplayGeometryDto(),
    val outcome: String = "TP1",
    @SerializedName("result_pct") val resultPct: Double = 0.0,
    @SerializedName("result_r") val resultR: Double = 0.0,
    @SerializedName("mae_pct") val maePct: Double = 0.0,
    @SerializedName("mfe_pct") val mfePct: Double = 0.0
)

data class ReplayBreakdownItemDto(
    val matches: Int = 0,
    @SerializedName("tp1_rate") val tp1Rate: Double = 0.0,
    @SerializedName("expectancy_r") val expectancyR: Double = 0.0,
    @SerializedName("net_return_pct") val netReturnPct: Double = 0.0
)

data class ReplaySummaryDto(
    @SerializedName("primary_display_currency") val primaryDisplayCurrency: String = "PERCENT_AND_R",
    @SerializedName("historical_matches_count") val historicalMatchesCount: Int = 0,
    @SerializedName("technical_valid_matches_count") val technicalValidMatchesCount: Int = 0,
    @SerializedName("tradingagents_agreement_pct") val tradingAgentsAgreementPct: Double = 0.0,
    @SerializedName("qwen_agreement_pct") val qwenAgreementPct: Double = 0.0,
    @SerializedName("deterministic_validation_pct") val deterministicValidationPct: Double = 0.0,
    @SerializedName("tp1_hit_rate_pct") val tp1HitRatePct: Double = 0.0,
    @SerializedName("tp2_hit_rate_pct") val tp2HitRatePct: Double = 0.0,
    @SerializedName("tp3_hit_rate_pct") val tp3HitRatePct: Double = 0.0,
    @SerializedName("sl_first_rate_pct") val slFirstRatePct: Double = 0.0,
    @SerializedName("breakeven_rate_pct") val breakevenRatePct: Double = 0.0,
    @SerializedName("expectancy_r") val expectancyR: Double = 0.0,
    @SerializedName("median_r") val medianR: Double = 0.0,
    @SerializedName("avg_win_r") val avgWinR: Double = 0.0,
    @SerializedName("avg_loss_r") val avgLossR: Double = 0.0,
    @SerializedName("profit_factor") val profitFactor: Double = 0.0,
    @SerializedName("max_drawdown_pct") val maxDrawdownPct: Double = 0.0,
    @SerializedName("net_return_pct") val netReturnPct: Double = 0.0
)

data class MLHistoricalReplayDto(
    val status: String = "COMPLETED",
    @SerializedName("replay_mode") val replayMode: String = "ML_SETUP_HISTORICAL_REPLAY",
    @SerializedName("replay_system") val replaySystem: String = "ML_SETUP_HISTORICAL_REPLAY",
    val label: String = "ML SETUP HISTORICAL REPLAY (Ophelia ML Intelligence)",
    val disclaimer: String = "HISTORICAL ANALOGUE — NOT GUARANTEE OF FUTURE PERFORMANCE",
    @SerializedName("frozen_setup") val frozenSetup: ReplayFrozenSetupDto = ReplayFrozenSetupDto(),
    @SerializedName("data_availability") val dataAvailability: ReplayDataAvailabilityDto = ReplayDataAvailabilityDto(),
    val summary: ReplaySummaryDto = ReplaySummaryDto(),
    val breakdowns: Map<String, Map<String, ReplayBreakdownItemDto>> = emptyMap(),
    @SerializedName("breakdown_by_timeframe") val breakdownByTimeframe: Map<String, ReplayBreakdownItemDto> = emptyMap(),
    @SerializedName("breakdown_by_direction") val breakdownByDirection: Map<String, ReplayBreakdownItemDto> = emptyMap(),
    @SerializedName("historical_matches") val historicalMatches: List<HistoricalMatchDto> = emptyList(),
    @SerializedName("timestamp_ms") val timestampMs: Long = 0L
)

data class AppVersionResponse(
    @SerializedName("version_name") val versionName: String = "2.7.0",
    @SerializedName("version_code") val versionCode: Int = 27,
    @SerializedName("min_version_code") val minVersionCode: Int = 1,
    @SerializedName("force_update") val forceUpdate: Boolean = false,
    @SerializedName("release_notes") val releaseNotes: String? = null,
    @SerializedName("download_url") val downloadUrl: String = "/api/system/app-download",
    @SerializedName("apk_available") val apkAvailable: Boolean = false,
    @SerializedName("apk_size_bytes") val apkSizeBytes: Long = 0L,
    val sha256: String? = null,
    val channel: String = "admin",
    @SerializedName("timestamp_ms") val timestampMs: Long = 0L
)

// ============================================================
// TWO-APP & GOD EYE DATA TRANSFER OBJECTS
// ============================================================

data class GodEyeSummaryDto(
    @SerializedName("connected_users") val connectedUsers: Int = 0,
    @SerializedName("active_copy") val activeCopy: Int = 0,
    val paused: Int = 0,
    @SerializedName("bingx_disconnected") val bingxDisconnected: Int = 0,
    val suspended: Int = 0,
    @SerializedName("execution_errors") val executionErrors: Int = 0
)

data class GodEyeUserDto(
    val id: Long,
    @SerializedName("user_uid") val userUid: String? = null,
    val role: String = "USER",
    val name: String? = null,
    val email: String? = null,
    val status: String = "ACTIVE",
    @SerializedName("app_version") val appVersion: String? = null,
    @SerializedName("bingx_connection") val bingxConnection: String = "DISCONNECTED",
    @SerializedName("copy_enabled") val copyEnabled: Boolean = true,
    @SerializedName("admin_copy_allowed") val adminCopyAllowed: Boolean = true,
    val suspended: Boolean = false,
    val balance: Double? = null,
    val equity: Double? = null,
    @SerializedName("available_margin") val availableMargin: Double? = null,
    @SerializedName("open_positions") val openPositions: List<UserPositionDto> = emptyList(),
    @SerializedName("open_positions_count") val openPositionsCount: Int = 0,
    @SerializedName("last_heartbeat") val lastHeartbeat: Long? = null,
    @SerializedName("last_bingx_sync") val lastBingxSync: Long? = null,
    @SerializedName("last_execution_status") val lastExecutionStatus: String? = null,
    @SerializedName("last_error") val lastError: String? = null
)


data class GodEyeOverviewResponse(
    val summary: GodEyeSummaryDto = GodEyeSummaryDto(),
    val users: List<GodEyeUserDto> = emptyList()
)

data class UserAppMetadataResponse(
    @SerializedName("version_name") val versionName: String = "1.0.0",
    @SerializedName("version_code") val versionCode: Int = 1,
    @SerializedName("release_notes") val releaseNotes: String? = null,
    @SerializedName("download_url") val downloadUrl: String = "https://15.235.193.47/download/user",
    @SerializedName("apk_available") val apkAvailable: Boolean = true,
    @SerializedName("apk_size_bytes") val apkSizeBytes: Long = 0L,
    val sha256: String? = null,
    @SerializedName("direct_link") val directLink: String = "https://15.235.193.47/download/user"
)

data class GoogleAuthResponse(
    val token: String,
    @SerializedName("user_id") val userId: Long,
    @SerializedName("user_uid") val userUid: String? = null,
    val role: String = "USER",
    val email: String? = null,
    @SerializedName("display_name") val displayName: String? = null,
    val status: String = "ACTIVE",
    @SerializedName("copy_enabled") val copyEnabled: Boolean = true,
    @SerializedName("bingx_connected") val bingxConnected: Boolean = false
)

data class UserPositionDto(
    val id: Long = 0L,
    val symbol: String = "",
    val direction: String = "LONG",
    val quantity: Double = 0.0,
    @SerializedName("entry_price") val entryPrice: Double = 0.0,
    val leverage: Double = 10.0,
    val margin: Double = 0.0,
    @SerializedName("sl_price") val slPrice: Double? = null,
    @SerializedName("tp1_price") val tp1Price: Double? = null,
    @SerializedName("tp2_price") val tp2Price: Double? = null,
    @SerializedName("tp3_price") val tp3Price: Double? = null,
    val trailing: Boolean = false,
    val breakeven: Boolean = false,
    val status: String = "OPEN",
    @SerializedName("unrealized_pnl") val unrealizedPnl: Double = 0.0,
    @SerializedName("realized_pnl") val realizedPnl: Double = 0.0,
    @SerializedName("lifecycle_state") val lifecycleState: String = "FILLED",
    @SerializedName("remaining_quantity") val remainingQuantity: Double? = null,
    @SerializedName("actual_entry_price") val actualEntryPrice: Double? = null,
    @SerializedName("breakeven_stop") val breakevenStop: Double? = null,
    @SerializedName("current_trailing_stop") val currentTrailingStop: Double? = null,
    @SerializedName("last_management_event") val lastManagementEvent: String? = null,
    @SerializedName("reconciliation_status") val reconciliationStatus: String? = null
)

data class UserPositionLifecycleResponse(
    val positions: List<Map<String, Any?>> = emptyList()
)

data class CopyExecutionDto(
    @SerializedName("copy_execution_id") val copyExecutionId: String = "",
    @SerializedName("master_trade_id") val masterTradeId: String = "",
    val status: String = "PLANNED",
    @SerializedName("blocked_reason") val blockedReason: String? = null,
    @SerializedName("allocated_margin") val allocatedMargin: Double? = null,
    @SerializedName("calculated_quantity") val calculatedQuantity: Double? = null,
    @SerializedName("executed_quantity") val executedQuantity: Double? = null,
    @SerializedName("executed_price") val executedPrice: Double? = null,
    @SerializedName("execution_latency_ms") val executionLatencyMs: Long? = null,
    @SerializedName("created_ms") val createdMs: Long = 0L
)

data class UserDashboardResponse(
    @SerializedName("user_id") val userId: Long,
    @SerializedName("user_uid") val userUid: String? = null,
    @SerializedName("display_name") val displayName: String? = null,
    val email: String? = null,
    @SerializedName("bingx_status") val bingxStatus: String = "DISCONNECTED",
    @SerializedName("bingx_identifier") val bingxIdentifier: String? = null,
    @SerializedName("copy_enabled") val copyEnabled: Boolean = true,
    @SerializedName("copy_engine_status") val copyEngineStatus: String = "ACTIVE",
    val balance: Double = 0.0,
    val equity: Double = 0.0,
    @SerializedName("available_margin") val availableMargin: Double = 0.0,
    val positions: List<UserPositionDto> = emptyList(),
    @SerializedName("recent_trades") val recentTrades: List<CopyExecutionDto> = emptyList(),
    @SerializedName("last_heartbeat") val lastHeartbeat: Long? = null
)

// ==========================================
// OPHELIA AUTONOMOUS TRADE SLOTS (GLOBAL & DYNAMIC)
// ==========================================

data class AutonomousTradeSlotDto(
    val id: Int,
    val name: String,
    val enabled: Boolean,
    @SerializedName("allocated_margin_usdt") val allocatedMarginUsdt: Double,
    @SerializedName("max_leverage") val maxLeverage: Double,
    val status: String, // AVAILABLE, RESERVED, OCCUPIED
    @SerializedName("asset_scope") val assetScope: String = "ALL",
    @SerializedName("allowed_asset_classes") val allowedAssetClasses: String = "CRYPTO,COMMODITIES,US_MARKET",
    @SerializedName("allowed_symbols") val allowedSymbols: String = "",
    @SerializedName("strategy_scope") val strategyScope: String = "ALL_STRATEGIES",
    @SerializedName("current_trade_id") val currentTradeId: String? = null,
    @SerializedName("current_position_id") val currentPositionId: String? = null,
    @SerializedName("created_at") val createdAt: Long = 0L,
    @SerializedName("updated_at") val updatedAt: Long = 0L,
    @SerializedName("last_used_at") val lastUsedAt: Long? = null,
    @SerializedName("max_loss_usdt") val maxLossUsdt: Double = 0.0,
    @SerializedName("max_loss_pct") val maxLossPct: Double = 10.0,
    @SerializedName("trailing_enabled") val trailingEnabled: Boolean = true,
    @SerializedName("trailing_pct") val trailingPct: Double = 1.5,
    @SerializedName("tp1_enabled") val tp1Enabled: Boolean = true,
    @SerializedName("tp1_pct") val tp1Pct: Double = 50.0,
    @SerializedName("breakeven_enabled") val breakevenEnabled: Boolean = true,
    @SerializedName("breakeven_mode") val breakevenMode: String = "AFTER_TP1",
    @SerializedName("slot_mode") val slotMode: String = "BOTH",
    @SerializedName("account_id") val accountId: Int? = 1,
    val scope: String? = "ALL",
    val mode: String? = "BOTH",
    @SerializedName("maximum_loss_percent") val maximumLossPercent: Double? = 10.0,
    @SerializedName("trailing_configuration") val trailingConfiguration: String? = null,
    @SerializedName("tp1_percent") val tp1Percent: Double? = 50.0,
    @SerializedName("move_sl_to_cost") val moveSlToCost: Boolean? = true,
    @SerializedName("reserved_at") val reservedAt: Long? = null,
    @SerializedName("released_at") val releasedAt: Long? = null,
    @SerializedName("reservation_id") val reservationId: String? = null,
    @SerializedName("last_error") val lastError: String? = null,
    @SerializedName("last_error_reason") val lastErrorReason: String? = null
)

data class UserSlotTemplateDto(
    val id: Long? = null,
    @SerializedName("user_id") val userId: Int = 1,
    @SerializedName("account_id") val accountId: Int = 1,
    val scope: String = "CRYPTO",
    @SerializedName("strategy_scope") val strategyScope: String = "ALL",
    val margin: Double = 50.0,
    val leverage: Double = 5.0,
    @SerializedName("max_loss_pct") val maxLossPct: Double = 2.0,
    @SerializedName("tp1_pct") val tp1Pct: Double = 50.0,
    val breakeven: Boolean = true,
    val trailing: Boolean = true,
    @SerializedName("trailing_pct") val trailingPct: Double = 1.5,
    @SerializedName("max_slots") val maxSlots: Int = 5,
    @SerializedName("max_autonomous_capital") val maxAutonomousCapital: Double = 500.0
)

data class UserSlotTemplateResponse(
    val template: UserSlotTemplateDto? = null,
    val templates: List<UserSlotTemplateDto> = emptyList(),
    @SerializedName("has_template") val hasTemplate: Boolean = false
)

data class ExecutionIntentDto(
    @SerializedName("execution_intent_id") val executionIntentId: String,
    @SerializedName("candidate_id") val candidateId: String? = null,
    @SerializedName("automation_id") val automationId: Long? = null,
    @SerializedName("slot_id") val slotId: Int? = null,
    @SerializedName("user_id") val userId: Int,
    @SerializedName("account_id") val accountId: Int = 1,
    val instrument: String,
    val direction: String,
    @SerializedName("requested_margin") val requestedMargin: Double,
    val leverage: Double,
    val status: String,
    @SerializedName("created_at") val createdAt: Long,
    @SerializedName("error_reason") val errorReason: String? = null,
    @SerializedName("position_id") val positionId: String? = null
)

data class AutomationPipelineItemDto(
    @SerializedName("automation_id") val automationId: Long,
    @SerializedName("user_id") val userId: Int,
    @SerializedName("account_id") val accountId: Int,
    val status: String?,
    val strategy: String?,
    val symbol: String?,
    @SerializedName("last_evaluated_ms") val lastEvaluatedMs: Long? = null,
    @SerializedName("last_eval_reason") val lastEvalReason: String? = null,
    val candidate: Map<String, Any?>? = null,
    val slot: Map<String, Any?>? = null,
    @SerializedName("execution_intent") val executionIntent: Map<String, Any?>? = null,
    val position: Map<String, Any?>? = null,
    val tp1: Map<String, Any?>? = null,
    val breakeven: Map<String, Any?>? = null,
    val trailing: Map<String, Any?>? = null,
    val exit: Map<String, Any?>? = null,
    val reconciliation: Map<String, Any?>? = null,
    @SerializedName("waiting_reason") val waitingReason: String? = null,
    @SerializedName("last_error") val lastError: String? = null
)

data class AutomationPipelineDiagnosticsResponse(
    val pipeline: List<AutomationPipelineItemDto> = emptyList()
)

data class RecoverStaleReservationsResponse(
    val success: Boolean = true,
    @SerializedName("recovered_count") val recoveredCount: Int = 0
)

data class AutonomousSlotsSummaryResponse(
    @SerializedName("global_enabled") val globalEnabled: Boolean,
    @SerializedName("total_slots") val totalSlots: Int,
    @SerializedName("user_configured_slots") val userConfiguredSlots: Int? = null,
    @SerializedName("system_max_slots") val systemMaxSlots: Int? = null,
    @SerializedName("enabled_slots") val enabledSlots: Int,
    @SerializedName("available_slots") val availableSlots: Int,
    @SerializedName("occupied_slots") val occupiedSlots: Int,
    @SerializedName("reserved_slots") val reservedSlots: Int,
    @SerializedName("total_authorized_margin_usdt") val totalAuthorizedMarginUsdt: Double,
    @SerializedName("authorized_capital_usdt") val authorizedCapitalUsdt: Double? = null,
    @SerializedName("reserved_margin_usdt") val reservedMarginUsdt: Double,
    @SerializedName("allocated_capital_usdt") val allocatedCapitalUsdt: Double? = null,
    @SerializedName("available_authorized_margin_usdt") val availableAuthorizedMarginUsdt: Double,
    val slots: List<AutonomousTradeSlotDto> = emptyList(),
    @SerializedName("is_admin") val isAdmin: Boolean = false
)

data class AddTradeSlotRequest(
    val name: String,
    @SerializedName("allocated_margin_usdt") val allocatedMarginUsdt: Double,
    @SerializedName("max_leverage") val maxLeverage: Int = 5,
    @SerializedName("asset_scope") val assetScope: String = "ALL",
    @SerializedName("strategy_scope") val strategyScope: String = "ALL",
    @SerializedName("allowed_symbols") val allowedSymbols: List<String>? = null,
    val enabled: Boolean = true,
    @SerializedName("max_loss_usdt") val maxLossUsdt: Double? = null,
    @SerializedName("max_loss_pct") val maxLossPct: Double? = 10.0,
    @SerializedName("trailing_enabled") val trailingEnabled: Boolean? = true,
    @SerializedName("trailing_pct") val trailingPct: Double? = 1.5,
    @SerializedName("tp1_enabled") val tp1Enabled: Boolean? = true,
    @SerializedName("tp1_pct") val tp1Pct: Double? = 50.0,
    @SerializedName("breakeven_enabled") val breakevenEnabled: Boolean? = true,
    @SerializedName("breakeven_mode") val breakevenMode: String? = "AFTER_TP1",
    @SerializedName("slot_mode") val slotMode: String? = "BOTH"
)

data class UpdateTradeSlotRequest(
    val name: String? = null,
    @SerializedName("allocated_margin_usdt") val allocatedMarginUsdt: Double? = null,
    @SerializedName("max_leverage") val maxLeverage: Int? = null,
    @SerializedName("asset_scope") val assetScope: String? = null,
    @SerializedName("strategy_scope") val strategyScope: String? = null,
    @SerializedName("allowed_symbols") val allowedSymbols: List<String>? = null,
    val enabled: Boolean? = null,
    @SerializedName("max_loss_usdt") val maxLossUsdt: Double? = null,
    @SerializedName("max_loss_pct") val maxLossPct: Double? = null,
    @SerializedName("trailing_enabled") val trailingEnabled: Boolean? = null,
    @SerializedName("trailing_pct") val trailingPct: Double? = null,
    @SerializedName("tp1_enabled") val tp1Enabled: Boolean? = null,
    @SerializedName("tp1_pct") val tp1Pct: Double? = null,
    @SerializedName("breakeven_enabled") val breakevenEnabled: Boolean? = null,
    @SerializedName("breakeven_mode") val breakevenMode: String? = null,
    @SerializedName("slot_mode") val slotMode: String? = null
)

data class CopiedPositionDto(
    @SerializedName("position_id") val positionId: Any? = null,
    @SerializedName("master_trade_id") val masterTradeId: String = "",
    val symbol: String = "",
    val side: String = "",
    @SerializedName("master_entry") val masterEntry: Double = 0.0,
    @SerializedName("follower_entry") val followerEntry: Double = 0.0,
    @SerializedName("slippage_pct") val slippagePct: Double = 0.0,
    @SerializedName("current_price") val currentPrice: Double = 0.0,
    @SerializedName("unrealized_pnl") val unrealizedPnl: Double = 0.0,
    val status: String = "SYNCED",
    @SerializedName("slot_id") val slotId: Int? = null
)

data class ReplicationStatusResponse(
    @SerializedName("master_status") val masterStatus: String = "ONLINE",
    @SerializedName("master_trades_count") val masterTradesCount: Int = 0,
    @SerializedName("authorized_followers_count") val authorizedFollowersCount: Int = 0,
    @SerializedName("copy_enabled") val copyEnabled: Boolean = false,
    @SerializedName("admin_copy_allowed") val adminCopyAllowed: Boolean = true,
    @SerializedName("active_copied_trades") val activeCopiedTrades: List<CopiedPositionDto> = emptyList(),
    @SerializedName("total_executions") val totalExecutions: Int = 0
)

data class ToggleAutonomousMasterRequest(
    val enabled: Boolean
)

// ==========================================
// US MARKET & TOP 100 UNIVERSE MODELS
// ==========================================

data class UsSessionDetails(
    @SerializedName("current_time_et") val currentTimeEt: String? = null,
    @SerializedName("current_day") val currentDay: String? = null,
    @SerializedName("is_weekday") val isWeekday: Boolean = true,
    @SerializedName("is_market_holiday") val isMarketHoliday: Boolean = false,
    @SerializedName("holiday_name") val holidayName: String? = null,
    @SerializedName("dst_active") val dstActive: Boolean = true,
    @SerializedName("next_session_open_et") val nextSessionOpenEt: String? = null,
    @SerializedName("bingx_status") val bingxStatus: String = "OPEN_CONTINUOUS_TRADFI"
)

data class UsSessionState(
    val underlying: String, // REGULAR_HOURS, PRE_MARKET, AFTER_HOURS, OVERNIGHT, CLOSED_WEEKEND, CLOSED_HOLIDAY
    val bingx: String,
    val details: UsSessionDetails? = null
)

data class BenchmarkItem(
    val price: Double = 0.0,
    @SerializedName("change_pct") val changePct: Double = 0.0
)

data class UsTopMoverItem(
    val symbol: String,
    @SerializedName("change_pct") val changePct: Double,
    val price: Double,
    val bias: String
)

data class UsMarketOverviewResponse(
    val session: UsSessionState,
    @SerializedName("market_regime") val marketRegime: String,
    val benchmarks: Map<String, BenchmarkItem> = emptyMap(),
    val sectors: List<UsSectorItem> = emptyList(),
    @SerializedName("top_gainers") val topGainers: List<UsTopMoverItem> = emptyList(),
    @SerializedName("top_losers") val topLosers: List<UsTopMoverItem> = emptyList(),
    @SerializedName("breaking_news") val breakingNews: List<UsNewsItem> = emptyList(),
    @SerializedName("priority_opportunities") val priorityOpportunities: List<UsOvernightCandidate> = emptyList(),
    @SerializedName("data_health") val dataHealth: Map<String, Any> = emptyMap(),
    @SerializedName("timestamp_ms") val timestampMs: Long = 0L
)

data class UsStockUniverseItem(
    val rank: Int = 0,
    val symbol: String = "",
    val name: String? = "",
    @SerializedName("company_name") val companyName: String? = "",
    val sector: String = "",
    val subsector: String? = "",
    val industry: String? = "",
    val price: Double = 0.0,
    @SerializedName("change_pct") val changePct: Double = 0.0,
    val direction: String = "UP",
    val bias: String = "NEUTRAL",
    val confidence: Double = 70.0,
    val rvol: Double = 1.0,
    @SerializedName("bingx_tradfi_symbol") val bingxTradfiSymbol: String? = "",
    @SerializedName("bingx_symbol") val bingxSymbol: String? = "",
    @SerializedName("bingx_support_status") val bingxSupportStatus: String? = "UNSUPPORTED",
    @SerializedName("bingx_available") val bingxAvailable: Boolean = false,
    val enabled: Boolean = true
) {
    val displayName: String get() = (name?.takeIf { it.isNotBlank() } ?: companyName ?: symbol)
    val displayBingxSymbol: String get() = (bingxTradfiSymbol?.takeIf { it.isNotBlank() } ?: bingxSymbol ?: "TRADFI: N/A")
    val isBingxSupported: Boolean get() = (bingxAvailable || bingxSupportStatus == "VERIFIED")
}

data class UsTop100Response(
    val count: Int,
    val stocks: List<UsStockUniverseItem> = emptyList()
)

data class UsSectorItem(
    val sector: String = "",
    val proxy: String? = "N/A",
    val performance: Double = 0.0,
    @SerializedName("advancing_stocks") val advancingStocks: Int = 0,
    @SerializedName("declining_stocks") val decliningStocks: Int = 0,
    val breadth: String? = "NEUTRAL",
    val regime: String? = "NEUTRAL",
    val momentum: String? = "FLAT"
) {
    val displayProxy: String get() = proxy?.takeIf { it.isNotBlank() && it != "null" } ?: "N/A"
    val displayBreadth: String get() = breadth?.takeIf { it.isNotBlank() && it != "null" } ?: "NEUTRAL"
}

data class UsSectorsResponse(
    val sectors: List<UsSectorItem> = emptyList()
)

data class UsNewsItem(
    val headline: String? = "",
    val url: String? = "",
    val timestamp: String? = "",
    val source: String? = "",
    val sentiment: String? = "NEUTRAL",
    @SerializedName("impact_score") val impactScore: Double? = 0.0,
    @SerializedName("relevant_symbols") val relevantSymbols: List<String>? = emptyList(),
    @SerializedName("relevant_sectors") val relevantSectors: List<String>? = emptyList()
) {
    val displayHeadline: String get() = headline ?: ""
    val displaySource: String get() = source ?: "News Wire"
    val displaySentiment: String get() = sentiment ?: "NEUTRAL"
    val safeSymbols: List<String> get() = relevantSymbols ?: emptyList()
}

data class UsNewsResponse(
    val news: List<UsNewsItem> = emptyList()
)

data class UsStructuralTarget(
    @SerializedName("target_price") val targetPrice: Double,
    @SerializedName("target_type") val targetType: String,
    @SerializedName("reward_r") val rewardR: Double
)

data class UsOvernightCandidate(
    @SerializedName("candidate_id") val candidateId: String,
    @SerializedName("asset_class") val assetClass: String = "US_MARKET",
    val strategy: String = "US_OVERNIGHT",
    val symbol: String,
    @SerializedName("bingx_symbol") val bingxSymbol: String,
    val direction: String, // LONG, SHORT
    @SerializedName("entry_price") val entryPrice: Double,
    @SerializedName("sl_price") val slPrice: Double,
    val targets: List<UsStructuralTarget> = emptyList(),
    @SerializedName("rr_ratio") val rrRatio: Double = 1.4,
    val confidence: Double = 80.0,
    val bias: String,
    @SerializedName("session_state") val sessionState: String,
    val thesis: String,
    @SerializedName("waiting_for") val waitingFor: String = "",
    @SerializedName("risk_status") val riskStatus: String = "APPROVED",
    @SerializedName("timestamp_ms") val timestampMs: Long = 0L
)

data class UsOvernightResponse(
    val candidates: List<UsOvernightCandidate> = emptyList()
)

data class UsOpportunitiesResponse(
    val opportunities: List<UsOvernightCandidate> = emptyList()
)

data class UsStockDossier(
    val symbol: String,
    val name: String,
    val rank: Int = 999,
    val price: Double = 0.0,
    @SerializedName("change_pct") val changePct: Double = 0.0,
    val direction: String = "UP",
    val bias: String = "NEUTRAL",
    val confidence: Double = 0.0,
    val sector: String = "General",
    val industry: String = "General",
    val exchange: String = "NASDAQ",
    @SerializedName("market_regime") val marketRegime: String = "NEUTRAL",
    @SerializedName("volume_state") val volumeState: String = "NORMAL",
    val rvol: Double = 1.0,
    @SerializedName("order_flow") val orderFlow: String = "NOT_AVAILABLE",
    val vwap: Double = 0.0,
    @SerializedName("vwap_state") val vwapState: String = "NEAR",
    val volatility: Double = 0.0,
    val liquidity: String = "ACCEPTABLE",
    @SerializedName("news_state") val newsState: String = "NEUTRAL",
    @SerializedName("news_direction") val newsDirection: String = "NEUTRAL",
    @SerializedName("news_impact") val newsImpact: String = "LOW",
    @SerializedName("options_state") val optionsState: String = "NOT_AVAILABLE",
    @SerializedName("gex_state") val gexState: String = "NOT_AVAILABLE",
    @SerializedName("bingx_state") val bingxState: String = "NOT_AVAILABLE",
    @SerializedName("bingx_symbol") val bingxSymbol: String = "",
    @SerializedName("overnight_bias") val overnightBias: String = "NEUTRAL",
    @SerializedName("candidate_state") val candidateState: String = "IDLE",
    @SerializedName("waiting_for") val waitingFor: String = "SETUP_MATURATION",
    @SerializedName("trade_direction") val tradeDirection: String = "NO_TRADE",
    @SerializedName("entry_reference_price") val entryReferencePrice: Double = 0.0,
    @SerializedName("sl_price") val slPrice: Double? = null,
    val targets: List<UsStructuralTarget> = emptyList(),
    @SerializedName("rr_ratio") val rrRatio: Double = 1.4,
    @SerializedName("data_freshness") val dataFreshness: String = "REAL_TIME",
    @SerializedName("updated_at") val updatedAt: Long = 0L
)

data class UsManualTradeRequest(
    val symbol: String,
    val direction: String,
    val leverage: Int = 5,
    @SerializedName("margin_usdt") val marginUsdt: Double? = null,
    @SerializedName("slot_id") val slotId: Int? = null,
    val reason: String? = "Admin Manual US Trade"
)

data class UsTradeResponse(
    val success: Boolean,
    @SerializedName("position_id") val positionId: String,
    val symbol: String,
    @SerializedName("bingx_symbol") val bingxSymbol: String,
    val direction: String,
    val price: Double,
    @SerializedName("margin_usdt") val marginUsdt: Double,
    val leverage: Int,
    val quantity: Double,
    val mode: String,
    val status: String
)

data class UserCopySettingsRequest(
    @SerializedName("copy_enabled") val copyEnabled: Boolean
)

// --- Market Movers & Universal Search & Manual Order ---
data class UsMoverItem(
    val symbol: String = "",
    val name: String = "",
    val price: Double = 0.0,
    @SerializedName("change_pct") val changePct: Double = 0.0,
    val direction: String = "UP",
    val sector: String = "General",
    @SerializedName("impact_score") val impactScore: Double = 0.0,
    val rvol: Double = 1.0,
    val bias: String = "NEUTRAL",
    val confidence: Double = 0.0,
    @SerializedName("bingx_available") val bingxAvailable: Boolean = false,
    @SerializedName("bingx_symbol") val bingxSymbol: String? = ""
)

data class UsMoversResponse(
    val movers: List<UsMoverItem> = emptyList()
)

data class MarketSearchItem(
    val symbol: String = "",
    val name: String = "",
    @SerializedName("asset_class") val assetClass: String = "CRYPTO",
    val price: Double = 0.0,
    @SerializedName("change_pct") val changePct: Double = 0.0,
    @SerializedName("bingx_symbol") val bingxSymbol: String = "",
    @SerializedName("venue_product") val venueProduct: String? = null,
    val executable: Boolean = true
)

data class MarketSearchResponse(
    val query: String = "",
    val results: List<MarketSearchItem> = emptyList()
)

data class ManualOrderRequest(
    val symbol: String,
    val side: String,
    @SerializedName("order_type") val orderType: String = "MARKET",
    @SerializedName("entry_price") val entryPrice: Double? = null,
    val margin: Double,
    val leverage: Int = 5,
    val sl: Double? = null,
    val tp1: Double? = null,
    val tp2: Double? = null,
    val tp3: Double? = null,
    @SerializedName("trailing_pct") val trailingPct: Double? = null,
    @SerializedName("move_sl_to_cost") val moveSlToCost: Boolean = true,
    @SerializedName("slot_id") val slotId: Int? = null,
    @SerializedName("asset_class") val assetClass: String? = null,
    val reason: String? = "Manual AUTO Terminal Order"
)

data class ManualOrderResponse(
    val ok: Boolean = true,
    val success: Boolean = true,
    @SerializedName("internal_order_id") val internalOrderId: String? = null,
    @SerializedName("order_id") val orderId: String? = null,
    @SerializedName("position_id") val positionId: String? = null,
    val venue: String? = "BINGX",
    @SerializedName("venue_product") val venueProduct: String? = null,
    @SerializedName("venue_symbol") val venueSymbol: String? = null,
    @SerializedName("venue_order_id") val venueOrderId: String? = null,
    @SerializedName("client_order_id") val clientOrderId: String? = null,
    @SerializedName("display_symbol") val displaySymbol: String? = null,
    val symbol: String = "",
    @SerializedName("bingx_symbol") val bingxSymbol: String = "",
    @SerializedName("asset_class") val assetClass: String? = null,
    val side: String = "",
    val price: Double = 0.0,
    val margin: Double = 0.0,
    val leverage: Int = 1,
    val quantity: Double = 0.0,
    val mode: String = "SHADOW",
    val status: String = "ACKNOWLEDGED",
    @SerializedName("reconciliation_status") val reconciliationStatus: String? = null,
    val message: String? = null
)

// --- TimesFM 3.0 Subsystem Models ---
data class TimesFmDiagnosticsResponse(
    @SerializedName("model_loaded") val modelLoaded: Boolean = false,
    @SerializedName("lifecycle_state") val lifecycleState: String = "UNINITIALIZED",
    val version: String = "3.0",
    @SerializedName("package_version") val packageVersion: String = "3.0.2",
    val checkpoint: String = "google/timesfm-3.0-pytorch",
    val device: String = "cpu",
    @SerializedName("forecast_count") val forecastCount: Int = 0,
    @SerializedName("last_inference_ms") val lastInferenceMs: Double = 0.0,
    @SerializedName("last_inference_ts") val lastInferenceTs: Long = 0L,
    @SerializedName("last_success_timestamp") val lastSuccessTimestamp: Long = 0L,
    @SerializedName("last_error") val lastError: String? = null,
    @SerializedName("queue_depth") val queueDepth: Int = 0,
    @SerializedName("p50_latency_ms") val p50LatencyMs: Double? = null,
    @SerializedName("p95_latency_ms") val p95LatencyMs: Double? = null,
    val mode: String = "SHADOW_ONLY",
    @SerializedName("trading_authority") val tradingAuthority: Boolean = false,
    @SerializedName("provider_pid") val providerPid: Int? = null,
    @SerializedName("api_pid") val apiPid: Int? = null,
    @SerializedName("evaluation_count") val evaluationCount: Int = 0,
    @SerializedName("evaluation_status") val evaluationStatus: String = "INSUFFICIENT_SAMPLE",
    @SerializedName("system_ram_total_mb") val systemRamTotalMb: Double? = null,
    @SerializedName("system_ram_available_mb") val systemRamAvailableMb: Double? = null,
    @SerializedName("system_ram_used_pct") val systemRamUsedPct: Double? = null,
    @SerializedName("system_swap_used_mb") val systemSwapUsedMb: Double? = null,
    @SerializedName("system_cpu_pct") val systemCpuPct: Double? = null
)

data class TimesFmForecastResponse(
    @SerializedName("forecast_id") val forecastId: String = "",
    val instrument: String = "",
    val timeframe: String = "15m",
    @SerializedName("forecast_timestamp") val forecastTimestamp: Long = 0L,
    @SerializedName("data_timestamp") val dataTimestamp: Long = 0L,
    @SerializedName("model_name") val modelName: String = "timesfm",
    @SerializedName("model_version") val modelVersion: String = "3.0",
    val checkpoint: String = "google/timesfm-3.0-pytorch",
    @SerializedName("context_length") val contextLength: Int = 0,
    val horizon: Int = 10,
    @SerializedName("forecast_values") val forecastValues: List<Double> = emptyList(),
    val quantiles: Map<String, List<Double>> = emptyMap(),
    @SerializedName("forecast_generation_ms") val forecastGenerationMs: Double = 0.0,
    @SerializedName("latency_ms") val latencyMs: Double = 0.0,
    val status: String = "SUCCESS",
    @SerializedName("data_freshness") val dataFreshness: String = "FRESH",
    val error: String? = null,
    val mode: String = "SHADOW",
    @SerializedName("forecast_return_pct") val forecastReturnPct: Double = 0.0,
    @SerializedName("quantile_spread_pct") val quantileSpreadPct: Double = 0.0,
    val direction: String = "NEUTRAL"
)

// --- Phase 6A: Microstructure Research Models ---
data class TradeFlowObservationModel(
    val instrument: String = "",
    val venue: String = "BINGX",
    @SerializedName("event_timestamp") val eventTimestamp: Long = 0L,
    @SerializedName("sample_count") val sampleCount: Int = 0,
    @SerializedName("quality_state") val qualityState: String = "VALID",
    @SerializedName("freshness_state") val freshnessState: String = "FRESH",
    @SerializedName("signed_flow") val signedFlow: Double = 0.0,
    @SerializedName("expected_flow") val expectedFlow: Double = 0.0,
    @SerializedName("flow_innovation") val flowInnovation: Double = 0.0,
    @SerializedName("flow_zscore") val flowZscore: Double = 0.0,
    @SerializedName("flow_direction") val flowDirection: Int = 0,
    @SerializedName("flow_persistence") val flowPersistence: Double = 0.0,
    @SerializedName("aggressor_source") val aggressorSource: String = "NOT_AVAILABLE",
    val mode: String = "RESEARCH"
)

data class TradeDurationObservationModel(
    val instrument: String = "",
    val venue: String = "BINGX",
    @SerializedName("event_timestamp") val eventTimestamp: Long = 0L,
    @SerializedName("sample_count") val sampleCount: Int = 0,
    @SerializedName("quality_state") val qualityState: String = "VALID",
    @SerializedName("freshness_state") val freshnessState: String = "FRESH",
    @SerializedName("duration_ms") val durationMs: Double = 0.0,
    @SerializedName("expected_duration_ms") val expectedDurationMs: Double = 0.0,
    @SerializedName("duration_pressure") val durationPressure: Double = 0.0,
    @SerializedName("arrival_intensity") val arrivalIntensity: Double = 0.0,
    @SerializedName("duration_zscore") val durationZscore: Double = 0.0,
    val persistence: Double = 0.0,
    val mode: String = "RESEARCH"
)

data class MicrostructureSummaryResponse(
    val instrument: String = "",
    @SerializedName("venue_symbol") val venueSymbol: String = "",
    @SerializedName("methodology_version") val methodologyVersion: String = "1.0.0",
    val mode: String = "RESEARCH",
    @SerializedName("trade_flow") val tradeFlow: TradeFlowObservationModel? = null,
    @SerializedName("trade_duration") val tradeDuration: TradeDurationObservationModel? = null,
    @SerializedName("order_book") val orderBook: OrderBookObservationModel? = null,
    @SerializedName("liquidity_stress") val liquidityStress: LiquidityStressObservationModel? = null,
    @SerializedName("price_impact") val priceImpact: PriceImpactObservationModel? = null,
    @SerializedName("toxicity") val toxicity: ToxicityObservationModel? = null,
    @SerializedName("hasbrouck") val hasbrouck: HasbrouckVarObservationModel? = null,
    @SerializedName("vecm") val vecm: VecmObservationModel? = null,
    @SerializedName("timestamp_ms") val timestampMs: Long = 0L
)

// --- Phase 6B: Order Book & Liquidity Stress Models ---
data class OrderBookObservationModel(
    val instrument: String = "",
    val venue: String = "BINGX",
    @SerializedName("event_timestamp") val eventTimestamp: Long = 0L,
    @SerializedName("sample_count") val sampleCount: Int = 0,
    @SerializedName("quality_state") val qualityState: String = "VALID",
    @SerializedName("freshness_state") val freshnessState: String = "FRESH",
    @SerializedName("depth_requested") val depthRequested: Int = 10,
    @SerializedName("depth_available") val depthAvailable: Int = 10,
    @SerializedName("depth_used") val depthUsed: Int = 10,
    @SerializedName("obi_top") val obiTop: Double? = null,
    @SerializedName("obi_depth_N") val obiDepthN: Double? = null,
    @SerializedName("bid_depth") val bidDepth: Double = 0.0,
    @SerializedName("ask_depth") val askDepth: Double = 0.0,
    @SerializedName("imbalance_direction") val imbalanceDirection: Int = 0,
    @SerializedName("imbalance_persistence") val imbalancePersistence: Double? = null,
    @SerializedName("obi_level_1") val obiLevel1: Double? = null,
    @SerializedName("obi_level_5") val obiLevel5: Double? = null,
    @SerializedName("obi_level_10") val obiLevel10: Double? = null,
    @SerializedName("cancellation_flow") val cancellationFlow: String = "NOT_AVAILABLE",
    @SerializedName("hidden_liquidity") val hiddenLiquidity: String = "NOT_AVAILABLE",
    @SerializedName("book_snapshot_age_ms") val bookSnapshotAgeMs: Long = 0L,
    @SerializedName("sequence_state") val sequenceState: String = "VALID",
    val mode: String = "RESEARCH"
)

data class LiquidityStressObservationModel(
    val instrument: String = "",
    val venue: String = "BINGX",
    @SerializedName("event_timestamp") val eventTimestamp: Long = 0L,
    @SerializedName("sample_count") val sampleCount: Int = 0,
    @SerializedName("quality_state") val qualityState: String = "VALID",
    @SerializedName("freshness_state") val freshnessState: String = "FRESH",
    val spread: Double? = null,
    @SerializedName("mid_price") val midPrice: Double? = null,
    @SerializedName("relative_spread") val relativeSpread: Double? = null,
    @SerializedName("expected_spread") val expectedSpread: Double? = null,
    @SerializedName("spread_zscore") val spreadZscore: Double? = null,
    @SerializedName("spread_percentile") val spreadPercentile: Double? = null,
    @SerializedName("spread_stress") val spreadStress: Double? = null,
    @SerializedName("depth_stress") val depthStress: Double? = null,
    @SerializedName("book_thinning") val bookThinning: Boolean? = null,
    @SerializedName("liquidity_stress") val liquidityStress: Double? = null,
    @SerializedName("liquidity_recovery_state") val liquidityRecoveryState: String = "NOT_AVAILABLE",
    val mode: String = "RESEARCH"
)

// --- Phase 6C: Price Impact & Toxicity Models ---
data class PriceImpactObservationModel(
    val instrument: String = "",
    val venue: String = "BINGX",
    @SerializedName("event_timestamp") val eventTimestamp: Long = 0L,
    @SerializedName("sample_count") val sampleCount: Int = 0,
    @SerializedName("quality_state") val qualityState: String = "VALID",
    @SerializedName("freshness_state") val freshnessState: String = "FRESH",
    @SerializedName("impact_coefficient") val impactCoefficient: Double? = null,
    @SerializedName("impact_direction") val impactDirection: Int = 0,
    @SerializedName("impact_stability") val impactStability: Double? = null,
    @SerializedName("impact_asymmetry") val impactAsymmetry: Double? = null,
    @SerializedName("buy_impact") val buyImpact: Double? = null,
    @SerializedName("sell_impact") val sellImpact: Double? = null,
    @SerializedName("flow_response") val flowResponse: Double? = null,
    @SerializedName("horizon_steps") val horizonSteps: Int = 1,
    @SerializedName("methodology_version") val methodologyVersion: String = "KYLE_INSPIRED_EMPIRICAL_IMPACT",
    val mode: String = "RESEARCH"
)

data class ToxicityObservationModel(
    val instrument: String = "",
    val venue: String = "BINGX",
    @SerializedName("event_timestamp") val eventTimestamp: Long = 0L,
    @SerializedName("sample_count") val sampleCount: Int = 0,
    @SerializedName("quality_state") val qualityState: String = "VALID",
    @SerializedName("freshness_state") val freshnessState: String = "FRESH",
    @SerializedName("flow_intensity") val flowIntensity: Double? = null,
    @SerializedName("adverse_price_response") val adversePriceResponse: Double? = null,
    @SerializedName("spread_stress_context") val spreadStressContext: Double? = null,
    @SerializedName("depth_stress_context") val depthStressContext: Double? = null,
    @SerializedName("trade_arrival_stress") val tradeArrivalStress: Double? = null,
    @SerializedName("toxicity_metric") val toxicityMetric: Double? = null,
    @SerializedName("toxicity_state") val toxicityState: String = "NOT_AVAILABLE",
    @SerializedName("methodology_version") val methodologyVersion: String = "VPIN_INSPIRED_RESEARCH",
    val mode: String = "RESEARCH"
)

// --- Phase 6D: Hasbrouck-Style VAR & VECM Models ---
data class HasbrouckVarObservationModel(
    val instrument: String = "",
    val venue: String = "BINGX",
    @SerializedName("event_timestamp") val eventTimestamp: Long = 0L,
    @SerializedName("sample_count") val sampleCount: Int = 0,
    @SerializedName("quality_state") val qualityState: String = "VALID",
    @SerializedName("freshness_state") val freshnessState: String = "FRESH",
    @SerializedName("run_id") val runId: String? = null,
    val status: String = "NOT_AVAILABLE",
    @SerializedName("selected_lag") val selectedLag: Int? = null,
    @SerializedName("lag_selection_method") val lagSelectionMethod: String = "BIC",
    @SerializedName("candidate_lags") val candidateLags: List<Int> = emptyList(),
    @SerializedName("window_start") val windowStart: Long? = null,
    @SerializedName("window_end") val windowEnd: Long? = null,
    @SerializedName("sampling_method") val samplingMethod: String = "EVENT_TIME",
    @SerializedName("is_stable") val isStable: Boolean? = null,
    @SerializedName("max_eigenvalue_modulus") val maxEigenvalueModulus: Double? = null,
    @SerializedName("cumulative_impact") val cumulativeImpact: Double? = null,
    @SerializedName("variance_share_flow") val varianceShareFlow: Double? = null,
    @SerializedName("methodology_version") val methodologyVersion: String = "HASBROUCK_STYLE_RESEARCH",
    val mode: String = "RESEARCH"
)

data class VecmObservationModel(
    val instrument: String = "",
    val venue: String = "BINGX",
    @SerializedName("event_timestamp") val eventTimestamp: Long = 0L,
    @SerializedName("sample_count") val sampleCount: Int = 0,
    @SerializedName("quality_state") val qualityState: String = "VALID",
    @SerializedName("freshness_state") val freshnessState: String = "FRESH",
    @SerializedName("run_id") val runId: String? = null,
    val status: String = "NOT_AVAILABLE",
    @SerializedName("series_1") val series1: String = "BTC-USDT-SPOT",
    @SerializedName("series_2") val series2: String = "BTC-USDT-PERP",
    @SerializedName("alignment_method") val alignmentMethod: String = "NEAREST_PRIOR",
    @SerializedName("window_start") val windowStart: Long? = null,
    @SerializedName("window_end") val windowEnd: Long? = null,
    @SerializedName("selected_lag") val selectedLag: Int? = null,
    @SerializedName("cointegration_rank") val cointegrationRank: Int? = null,
    @SerializedName("trace_stat") val traceStat: Double? = null,
    @SerializedName("max_eigen_stat") val maxEigenStat: Double? = null,
    @SerializedName("beta_coeff") val betaCoeff: Double? = null,
    @SerializedName("alpha_1") val alpha1: Double? = null,
    @SerializedName("alpha_2") val alpha2: Double? = null,
    @SerializedName("gg_share_1") val ggShare1: Double? = null,
    @SerializedName("gg_share_2") val ggShare2: Double? = null,
    @SerializedName("is_stable") val isStable: Boolean? = null,
    @SerializedName("methodology_version") val methodologyVersion: String = "VECM_STYLE_RESEARCH",
    val mode: String = "RESEARCH"
)

// --- Phase 10: Multi-Venue Market Intelligence & TimesFM Compatibility ---
data class CrossVenueBasisObservationModel(
    val symbol: String = "",
    @SerializedName("canonical_instrument_id") val canonicalInstrumentId: String = "",
    @SerializedName("binance_price") val binancePrice: Double = 0.0,
    @SerializedName("bingx_price") val bingxPrice: Double = 0.0,
    @SerializedName("basis_abs") val basisAbs: Double = 0.0,
    @SerializedName("basis_pct") val basisPct: Double = 0.0,
    @SerializedName("basis_zscore") val basisZscore: Double? = null,
    @SerializedName("basis_velocity") val basisVelocity: Double = 0.0,
    @SerializedName("timestamp_delta_ms") val timestampDeltaMs: Long = 0L,
    @SerializedName("binance_data_age_ms") val binanceDataAgeMs: Long = 0L,
    @SerializedName("bingx_data_age_ms") val bingxDataAgeMs: Long = 0L,
    @SerializedName("execution_spread") val executionSpread: Double = 0.0,
    @SerializedName("estimated_slippage_pct") val estimatedSlippagePct: Double = 0.0,
    val state: String = "NOT_AVAILABLE",
    val version: String = "CROSS_VENUE_BASIS_V1"
)

data class TimesFMCompatibilityObservationModel(
    @SerializedName("candidate_id") val candidateId: String = "",
    val symbol: String = "",
    val direction: String = "LONG",
    @SerializedName("entry_price") val entryPrice: Double = 0.0,
    @SerializedName("sl_price") val slPrice: Double = 0.0,
    @SerializedName("tp1_price") val tp1Price: Double = 0.0,
    @SerializedName("forecast_direction") val forecastDirection: String = "NEUTRAL",
    @SerializedName("forecast_dispersion") val forecastDispersion: String = "MODERATE",
    @SerializedName("trade_compatibility") val tradeCompatibility: String = "NOT_AVAILABLE",
    val q10: Double = 0.0,
    val q50: Double = 0.0,
    val q90: Double = 0.0,
    @SerializedName("dispersion_pct") val dispersionPct: Double = 0.0,
    val status: String = "SHADOW_ONLY",
    @SerializedName("calibration_status") val calibrationStatus: String = "NOT CALIBRATED"
)





