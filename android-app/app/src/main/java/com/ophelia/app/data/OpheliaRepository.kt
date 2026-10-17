package com.ophelia.app.data

import com.ophelia.app.auth.TokenManager
import com.ophelia.app.models.*
import com.ophelia.app.network.OpheliaApiService
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.network.WebSocketClient
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

class OpheliaRepository(
    private val tokenManager: TokenManager,
    private val webSocketClient: WebSocketClient? = null
) {
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    private val api: OpheliaApiService?
        get() = RetrofitClient.apiService

    // --- Cached Reactive StateFlows ---
    private val _dashboardState = MutableStateFlow<DashboardResponse?>(null)
    val dashboardState: StateFlow<DashboardResponse?> = _dashboardState.asStateFlow()

    private val _watchlistState = MutableStateFlow<List<String>>(listOf("BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT"))
    val watchlistState: StateFlow<List<String>> = _watchlistState.asStateFlow()

    private val _automationsState = MutableStateFlow<List<AutomationConfig>>(emptyList())
    val automationsState: StateFlow<List<AutomationConfig>> = _automationsState.asStateFlow()

    private val _positionsState = MutableStateFlow<List<Position>>(emptyList())
    val positionsState: StateFlow<List<Position>> = _positionsState.asStateFlow()

    private val _newsState = MutableStateFlow<List<NewsItem>>(emptyList())
    val newsState: StateFlow<List<NewsItem>> = _newsState.asStateFlow()

    private val _connectionStatus = MutableStateFlow("CONNECTED")
    val connectionStatus: StateFlow<String> = _connectionStatus.asStateFlow()

    init {
        // Wire WebSocket deltas if webSocketClient is provided
        webSocketClient?.let { ws ->
            scope.launch {
                ws.events.collect { event ->
                    when (event) {
                        is WebSocketEvent.DashboardUpdate -> {
                            _dashboardState.value = event.dashboard
                            _connectionStatus.value = "CONNECTED"
                        }
                        is WebSocketEvent.PositionUpdate -> {
                            val current = _positionsState.value.toMutableList()
                            val idx = current.indexOfFirst { it.id == event.position.id }
                            if (idx >= 0) {
                                current[idx] = event.position
                            } else {
                                current.add(0, event.position)
                            }
                            _positionsState.value = current
                        }
                        is WebSocketEvent.AutomationUpdate -> {
                            val current = _automationsState.value.toMutableList()
                            val idx = current.indexOfFirst { it.id == event.automation.id }
                            if (idx >= 0) {
                                current[idx] = event.automation
                            } else {
                                current.add(0, event.automation)
                            }
                            _automationsState.value = current
                        }
                        is WebSocketEvent.Connected -> {
                            _connectionStatus.value = "CONNECTED"
                        }
                        is WebSocketEvent.Disconnected -> {
                            _connectionStatus.value = "DISCONNECTED"
                        }
                        else -> {}
                    }
                }
            }
        }
    }

    // --- REST operations ---
    suspend fun fetchDashboard(): Result<DashboardResponse> = withContext(Dispatchers.IO) {
        try {
            val res = api?.getDashboard() ?: throw Exception("API service not initialized")
            _dashboardState.value = res
            Result.success(res)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun fetchWatchlist(): Result<List<String>> = withContext(Dispatchers.IO) {
        try {
            val res = api?.getWatchlist() ?: throw Exception("API service not initialized")
            _watchlistState.value = res.symbols
            Result.success(res.symbols)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun addWatchlistSymbol(symbol: String): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            api?.addWatchlist(mapOf("symbol" to symbol)) ?: throw Exception("API not ready")
            fetchWatchlist()
            Result.success(true)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun removeWatchlistSymbol(symbol: String): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            api?.removeWatchlist(symbol) ?: throw Exception("API not ready")
            fetchWatchlist()
            Result.success(true)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun fetchContracts(): Result<List<String>> = withContext(Dispatchers.IO) {
        try {
            val res = api?.getContracts() ?: throw Exception("API service not initialized")
            Result.success(res.symbols)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun fetchCandles(symbol: String, tf: String = "5m", limit: Int = 100): Result<CandlesResponse> = withContext(Dispatchers.IO) {
        try {
            val res = api?.getCandles(symbol, tf, limit) ?: throw Exception("API service not initialized")
            Result.success(res)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun fetchMarketSnapshot(symbol: String, tf: String = "5"): Result<MarketSnapshotResponse> = withContext(Dispatchers.IO) {
        try {
            val res = api?.getMarketSnapshot(symbol, tf) ?: throw Exception("API service not initialized")
            Result.success(res)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun fetchAutomations(status: String? = null): Result<List<AutomationConfig>> = withContext(Dispatchers.IO) {
        try {
            val res = api?.getAutomations(status) ?: throw Exception("API service not initialized")
            _automationsState.value = res.automations
            Result.success(res.automations)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun updateAutomationStatus(id: Long, status: String): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            api?.updateAutomation(id, mapOf("status" to status)) ?: throw Exception("API not ready")
            fetchAutomations()
            Result.success(true)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun deleteAutomation(id: Long): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            api?.deleteAutomation(id) ?: throw Exception("API not ready")
            fetchAutomations()
            Result.success(true)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun createAutomation(config: AutomationConfig): Result<AutomationResponse> = withContext(Dispatchers.IO) {
        try {
            val res = api?.createAutomation(config) ?: throw Exception("API not ready")
            fetchAutomations()
            Result.success(res)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun simulateAutomation(spec: Map<String, Any>): Result<SimulateResponse> = withContext(Dispatchers.IO) {
        try {
            val res = api?.simulateAutomation(spec) ?: throw Exception("API not ready")
            Result.success(res)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun fetchPositions(mode: String? = null): Result<List<Position>> = withContext(Dispatchers.IO) {
        try {
            val res = api?.getPositions(mode) ?: throw Exception("API not ready")
            _positionsState.value = res.positions
            Result.success(res.positions)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun editPosition(id: String, req: Map<String, Any>): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            api?.editPosition(id, req) ?: throw Exception("API not ready")
            fetchPositions()
            Result.success(true)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun closePosition(id: String): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            api?.closePosition(id) ?: throw Exception("API not ready")
            fetchPositions()
            Result.success(true)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun fetchTradeHistory(page: Int = 1, limit: Int = 50, symbol: String? = null, status: String? = null, mode: String? = null): Result<TradeHistoryResponse> = withContext(Dispatchers.IO) {
        try {
            val res = api?.getTradeHistory(page, limit, symbol, status, mode) ?: throw Exception("API not ready")
            Result.success(res)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun fetchAnalytics(days: Int = 30): Result<AnalyticsResponse> = withContext(Dispatchers.IO) {
        try {
            val res = api?.getAnalytics(days) ?: throw Exception("API not ready")
            Result.success(res)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun fetchAuditLogs(limit: Int = 50): Result<List<AuditLogItem>> = withContext(Dispatchers.IO) {
        try {
            val res = api?.getAuditLogs(limit) ?: throw Exception("API not ready")
            Result.success(res.logs)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun fetchNews(): Result<List<NewsItem>> = withContext(Dispatchers.IO) {
        try {
            val res = api?.getNews() ?: throw Exception("API not ready")
            _newsState.value = res.news
            Result.success(res.news)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun fetchPreflight(): Result<PreflightResponse> = withContext(Dispatchers.IO) {
        try {
            val res = api?.getPreflight() ?: throw Exception("API not ready")
            Result.success(res)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun setMode(mode: String): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            val res = api?.setMode(SetModeRequest(mode = mode)) ?: throw Exception("API not ready")
            fetchDashboard()
            Result.success(res.success)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun clearAllNotifications(): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            val res = api?.clearAllNotifications() ?: throw Exception("API not ready")
            Result.success(res.success)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
