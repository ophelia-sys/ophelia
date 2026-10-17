package com.ophelia.app.ui.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.ophelia.app.auth.TokenManager
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.network.WebSocketClient
import com.ophelia.app.models.*
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed class UiState<out T> {
    object Loading : UiState<Nothing>()
    data class Success<T>(val data: T) : UiState<T>()
    data class Error(val message: String) : UiState<Nothing>()
    object Offline : UiState<Nothing>()
    object Idle : UiState<Nothing>()
}

class MarketViewModel(private val tokenManager: TokenManager) : ViewModel() {
    private var webSocketClient: WebSocketClient? = null
    
    private val _connectionState = MutableStateFlow("CONNECTING")
    val connectionState = _connectionState.asStateFlow()

    private val _watchlistState = MutableStateFlow<UiState<List<String>>>(UiState.Loading)
    val watchlistState = _watchlistState.asStateFlow()
    
    private val _healthState = MutableStateFlow<UiState<Map<String, Any>>>(UiState.Loading)
    val healthState = _healthState.asStateFlow()

    private val _positionsState = MutableStateFlow<UiState<List<Position>>>(UiState.Loading)
    val positionsState = _positionsState.asStateFlow()

    private val _snapshots = MutableStateFlow<Map<String, MarketSnapshotResponse>>(emptyMap())
    val snapshots = _snapshots.asStateFlow()

    private val _detailSnapshotState = MutableStateFlow<UiState<MarketSnapshotResponse>>(UiState.Loading)
    val detailSnapshotState = _detailSnapshotState.asStateFlow()

    private val _candlesState = MutableStateFlow<UiState<List<CandleItem>>>(UiState.Loading)
    val candlesState = _candlesState.asStateFlow()

    private val _contractsState = MutableStateFlow<UiState<List<String>>>(UiState.Loading)
    val contractsState = _contractsState.asStateFlow()

    init {
        initializeWebSocket()
        fetchDashboardData()
        fetchContracts()
    }

    private fun initializeWebSocket() {
        webSocketClient = WebSocketClient(tokenManager)
        webSocketClient?.connect()
        
        viewModelScope.launch {
            webSocketClient?.events?.collect { event ->
                when (event) {
                    is WebSocketEvent.Connected -> {
                        _connectionState.value = "ONLINE"
                    }
                    is WebSocketEvent.Disconnected -> {
                        if (_healthState.value is UiState.Success) {
                            _connectionState.value = "ONLINE"
                        } else {
                            _connectionState.value = "OFFLINE"
                        }
                    }
                    is WebSocketEvent.PositionUpdate -> {
                        // Optimistically update positions
                        val current = (_positionsState.value as? UiState.Success)?.data?.toMutableList() ?: mutableListOf()
                        val idx = current.indexOfFirst { it.id == event.position.id }
                        if (idx >= 0) {
                            current[idx] = event.position
                        } else {
                            current.add(0, event.position)
                        }
                        _positionsState.value = UiState.Success(current)
                    }
                    is WebSocketEvent.HealthUpdate -> {
                        _healthState.value = UiState.Success(mapOf("status" to event.status, "component" to event.component))
                        _connectionState.value = if (event.status.equals("OFFLINE", ignoreCase = true)) "OFFLINE" else if (event.status.equals("DEGRADED", ignoreCase = true)) "DEGRADED" else "ONLINE"
                    }
                    else -> {}
                }
            }
        }
    }

    fun fetchContracts() {
        viewModelScope.launch {
            _contractsState.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val res = api.getContracts()
                _contractsState.value = UiState.Success(res.symbols)
            } catch (e: Exception) {
                _contractsState.value = UiState.Error(e.message ?: "Failed to load contracts")
            }
        }
    }

    fun fetchWatchlist() {
        viewModelScope.launch {
            _watchlistState.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val watchlistRes = api.getWatchlist()
                _watchlistState.value = UiState.Success(watchlistRes.symbols)
                
                // Fetch market snapshot for each symbol
                val currentSnapshots = _snapshots.value.toMutableMap()
                for (symbol in watchlistRes.symbols) {
                    try {
                        val snap = api.getMarketSnapshot(symbol)
                        currentSnapshots[symbol] = snap
                    } catch (e: Exception) { }
                }
                _snapshots.value = currentSnapshots
            } catch (e: Exception) {
                _watchlistState.value = UiState.Error(e.message ?: "Failed to load watchlist")
            }
        }
    }

    fun fetchPositions() {
        viewModelScope.launch {
            _positionsState.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService ?: run {
                    _positionsState.value = UiState.Error("API service not initialized")
                    return@launch
                }
                val positionsRes = api.getPositions()
                _positionsState.value = UiState.Success(positionsRes.positions)
            } catch (e: Exception) {
                _positionsState.value = UiState.Error(e.message ?: "Failed to load positions")
            }
        }
    }

    fun fetchHealth() {
        viewModelScope.launch {
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val health = api.getHealth()
                _healthState.value = UiState.Success(health)
                val status = health["status"] as? String ?: "ONLINE"
                _connectionState.value = if (status.equals("OFFLINE", ignoreCase = true)) "OFFLINE" else if (status.equals("DEGRADED", ignoreCase = true)) "DEGRADED" else "ONLINE"
            } catch (e: Exception) {
                _healthState.value = UiState.Error(e.message ?: "Offline")
                _connectionState.value = "OFFLINE"
            }
        }
    }

    fun fetchDashboardData() {
        fetchHealth()
        fetchPositions()
        fetchWatchlist()
    }

    fun getSymbolSnapshot(symbol: String, timeframe: Int) {
        viewModelScope.launch {
            _detailSnapshotState.value = UiState.Loading
            _candlesState.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService ?: return@launch
                
                // Fetch snapshot and candles in parallel
                val tfStr = "${timeframe}m"
                val snapJob = async { api.getMarketSnapshot(symbol, tf = tfStr) }
                val candleJob = async { api.getCandles(symbol, tf = tfStr, limit = 100) }

                val snap = snapJob.await()
                _detailSnapshotState.value = UiState.Success(snap)

                val candleRes = candleJob.await()
                _candlesState.value = UiState.Success(candleRes.candles)
                
                // Update global cache
                val current = _snapshots.value.toMutableMap()
                current[symbol] = snap
                _snapshots.value = current
            } catch (e: Exception) {
                _detailSnapshotState.value = UiState.Error(e.message ?: "Failed to load snapshot")
                _candlesState.value = UiState.Error(e.message ?: "Failed to load candles")
            }
        }
    }

    fun addWatchlist(symbol: String) {
        viewModelScope.launch {
            try {
                RetrofitClient.apiService?.addWatchlist(mapOf("symbol" to symbol))
                fetchWatchlist()
            } catch (e: Exception) { }
        }
    }

    fun removeWatchlist(symbol: String) {
        viewModelScope.launch {
            try {
                RetrofitClient.apiService?.removeWatchlist(symbol)
                fetchWatchlist()
            } catch (e: Exception) { }
        }
    }

    override fun onCleared() {
        super.onCleared()
        webSocketClient?.disconnect()
    }
}
