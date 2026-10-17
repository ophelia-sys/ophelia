package com.ophelia.app.ui.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.ophelia.app.auth.TokenManager
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.network.WebSocketClient
import com.ophelia.app.models.WebSocketEvent
import com.ophelia.app.models.DashboardResponse
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

import com.ophelia.app.notifications.NotificationHelper

class HomeDashboardViewModel(private val tokenManager: TokenManager) : ViewModel() {
    private var webSocketClient: WebSocketClient? = null
    
    private val _connectionState = MutableStateFlow("CONNECTING")
    val connectionState = _connectionState.asStateFlow()

    private val _isWsConnected = MutableStateFlow(false)
    val isWsConnected = _isWsConnected.asStateFlow()

    private val _dashboardState = MutableStateFlow<UiState<DashboardResponse>>(UiState.Loading)
    val dashboardState = _dashboardState.asStateFlow()

    init {
        fetchDashboard()
        initializeWebSocket()
    }

    private fun initializeWebSocket() {
        webSocketClient = WebSocketClient(tokenManager)
        
        viewModelScope.launch {
            webSocketClient?.events?.collect { event ->
                when (event) {
                    is WebSocketEvent.Connected -> {
                        _isWsConnected.value = true
                        _connectionState.value = "ONLINE"
                    }
                    is WebSocketEvent.Disconnected -> {
                        _isWsConnected.value = false
                        if (_dashboardState.value is UiState.Success) {
                            _connectionState.value = "ONLINE"
                        } else {
                            _connectionState.value = "OFFLINE"
                        }
                    }
                    is WebSocketEvent.DashboardUpdate -> {
                        _dashboardState.value = UiState.Success(event.dashboard)
                        val status = event.dashboard.health.status
                        _connectionState.value = if (status.equals("OFFLINE", ignoreCase = true)) "OFFLINE" else if (status.equals("DEGRADED", ignoreCase = true)) "DEGRADED" else "ONLINE"
                    }
                    is WebSocketEvent.NotificationEvent -> {
                        NotificationHelper.postNotification(tokenManager.context, event.notification)
                    }
                    else -> {}
                }
            }
        }
        
        webSocketClient?.connect()
    }

    fun fetchDashboard() {
        viewModelScope.launch {
            try {
                val api = RetrofitClient.apiService ?: run {
                    _dashboardState.value = UiState.Error("API service not initialized")
                    _connectionState.value = "OFFLINE"
                    return@launch
                }
                val response = api.getDashboard()
                _dashboardState.value = UiState.Success(response)
                val status = response.health.status
                _connectionState.value = if (status.equals("OFFLINE", ignoreCase = true)) "OFFLINE" else if (status.equals("DEGRADED", ignoreCase = true)) "DEGRADED" else "ONLINE"
            } catch (e: Exception) {
                _dashboardState.value = UiState.Error(e.message ?: "Failed to load dashboard")
                _connectionState.value = "OFFLINE"
            }
        }
    }

    fun editPosition(id: String, req: Map<String, Any>) {
        viewModelScope.launch {
            try {
                RetrofitClient.apiService?.editPosition(id, req)
                fetchDashboard()
            } catch (e: Exception) { }
        }
    }

    fun partialClosePosition(id: String, qtyPct: Double) {
        viewModelScope.launch {
            try {
                RetrofitClient.apiService?.partialClosePosition(id, mapOf("qty_pct" to qtyPct))
                fetchDashboard()
            } catch (e: Exception) { }
        }
    }

    fun closePosition(id: String) {
        viewModelScope.launch {
            try {
                RetrofitClient.apiService?.closePosition(id)
                fetchDashboard()
            } catch (e: Exception) { }
        }
    }

    fun reconcilePositions() {
        viewModelScope.launch {
            try {
                RetrofitClient.apiService?.reconcilePositions()
                fetchDashboard()
            } catch (e: Exception) { }
        }
    }

    override fun onCleared() {
        super.onCleared()
        webSocketClient?.disconnect()
    }
}
