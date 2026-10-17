package com.ophelia.app.network

import android.util.Log
import com.google.gson.Gson
import com.ophelia.app.auth.TokenManager
import com.ophelia.app.models.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import okhttp3.*
import okio.ByteString

class WebSocketClient(private val tokenManager: TokenManager) {
    private val client = OkHttpClient()
    private var webSocket: WebSocket? = null
    // Use wss:// for production, ws:// for local dev
    private val WS_URL = "wss://15.235.193.47/ws/market"
    private val gson = Gson()
    
    private val _events = MutableSharedFlow<WebSocketEvent>(replay = 1)
    val events: SharedFlow<WebSocketEvent> = _events
    
    private var isConnected = false
    private var reconnectJob: Job? = null
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var reconnectDelay = 1000L

    fun connect() {
        if (isConnected) return
        
        val token = tokenManager.getToken()
        // Pass token in URL for initial handshake auth as defined in contract
        val url = if (token != null) "$WS_URL?token=$token" else WS_URL
        
        val request = Request.Builder()
            .url(url)
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d("WebSocket", "Connected")
                isConnected = true
                reconnectDelay = 1000L // Reset delay
                scope.launch { _events.emit(WebSocketEvent.Connected) }
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                scope.launch {
                    try {
                        val msg = gson.fromJson(text, WsMessage::class.java)
                        val event = parsePayload(msg)
                        if (event != null) {
                            _events.emit(event)
                        }
                    } catch (e: Exception) {
                        Log.e("WebSocket", "Failed to parse message", e)
                    }
                }
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(1000, null)
                handleDisconnect()
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e("WebSocket", "Error: " + t.message)
                handleDisconnect()
            }
        })
    }
    
    private fun parsePayload(msg: WsMessage): WebSocketEvent? {
        return try {
            when (msg.type) {
                "PRICE_UPDATE" -> gson.fromJson(msg.payload, WebSocketEvent.PriceUpdate::class.java)
                "INDICATOR_UPDATE" -> gson.fromJson(msg.payload, WebSocketEvent.IndicatorUpdate::class.java)
                "POSITION_UPDATE" -> WebSocketEvent.PositionUpdate(gson.fromJson(msg.payload, Position::class.java))
                "AUTOMATION_UPDATE" -> WebSocketEvent.AutomationUpdate(gson.fromJson(msg.payload, AutomationConfig::class.java))
                "SIGNAL_CANDIDATE" -> gson.fromJson(msg.payload, WebSocketEvent.SignalCandidate::class.java)
                "ACCOUNT_UPDATE" -> WebSocketEvent.AccountUpdate(gson.fromJson(msg.payload, Account::class.java))
                "PNL_UPDATE" -> gson.fromJson(msg.payload, WebSocketEvent.PnlUpdate::class.java)
                "HEALTH_UPDATE" -> gson.fromJson(msg.payload, WebSocketEvent.HealthUpdate::class.java)
                "NEWS_UPDATE" -> gson.fromJson(msg.payload, WebSocketEvent.NewsUpdate::class.java)
                "DASHBOARD_UPDATE" -> WebSocketEvent.DashboardUpdate(gson.fromJson(msg.payload, DashboardResponse::class.java))
                "NOTIFICATION" -> WebSocketEvent.NotificationEvent(gson.fromJson(msg.payload, NotificationItem::class.java))
                else -> null
            }
        } catch (e: Exception) {
            Log.e("WebSocket", "Error parsing payload for ${msg.type}", e)
            null
        }
    }

    private fun handleDisconnect() {
        if (!isConnected) return
        isConnected = false
        webSocket = null
        scope.launch { _events.emit(WebSocketEvent.Disconnected) }
        scheduleReconnect()
    }

    private fun scheduleReconnect() {
        reconnectJob?.cancel()
        reconnectJob = scope.launch {
            delay(reconnectDelay)
            reconnectDelay = (reconnectDelay * 2).coerceAtMost(30000L) // Exponential backoff up to 30s
            connect()
        }
    }

    fun disconnect() {
        reconnectJob?.cancel()
        webSocket?.close(1000, "User disconnected")
        webSocket = null
        isConnected = false
        scope.launch { _events.emit(WebSocketEvent.Disconnected) }
    }
}
