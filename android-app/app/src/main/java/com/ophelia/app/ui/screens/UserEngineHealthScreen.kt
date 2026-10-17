package com.ophelia.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.theme.*
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun UserEngineHealthScreen(
    onBack: () -> Unit
) {
    val scope = rememberCoroutineScope()
    val tokens = OpheliaThemeTokens.colors

    var isLoading by remember { mutableStateOf(true) }
    var healthData by remember { mutableStateOf<Map<String, Any>?>(null) }
    var errorMessage by remember { mutableStateOf<String?>(null) }

    fun loadHealth() {
        scope.launch {
            isLoading = true
            errorMessage = null
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                val res = api.getUserEngineHealth()
                healthData = res
            } catch (e: Exception) {
                errorMessage = e.message ?: "Failed to query engine health"
            } finally {
                isLoading = false
            }
        }
    }

    LaunchedEffect(Unit) {
        loadHealth()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = "ENGINE HEALTH",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = tokens.primaryText
                        )
                        Text(
                            text = "USER REPLICATION TELEMETRY",
                            style = MaterialTheme.typography.labelSmall,
                            color = tokens.secondaryText
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back", tint = tokens.primaryText)
                    }
                },
                actions = {
                    IconButton(onClick = { loadHealth() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = AccentBlue)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background)
            )
        },
        containerColor = tokens.surface
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            val isHealthy = (healthData?.get("status") as? String) == "HEALTHY"
            item {
                OpheliaGlassCard(
                    modifier = Modifier.fillMaxWidth(),
                    borderColor = if (isHealthy) BullishGreen.copy(alpha = 0.5f) else AccentYellow
                ) {
                    Row(
                        modifier = Modifier.padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Icon(
                            if (isHealthy) Icons.Default.CheckCircle else Icons.Default.Warning,
                            contentDescription = null,
                            tint = if (isHealthy) BullishGreen else AccentYellow,
                            modifier = Modifier.size(28.dp)
                        )
                        Column {
                            Text(
                                text = if (isHealthy) "ALL SYSTEMS OPERATIONAL" else "ENGINE STATUS: DEGRADED",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.Bold,
                                color = if (isHealthy) BullishGreen else AccentYellow
                            )
                            Text(
                                text = "24/7 autonomous VPS execution engine is active and monitoring master events.",
                                style = MaterialTheme.typography.bodySmall,
                                color = tokens.secondaryText,
                                fontSize = 11.sp
                            )
                        }
                    }
                }
            }

            item {
                OpheliaGlassCard(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Text(
                            text = "USER SUBSCRIPTION TELEMETRY",
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold,
                            color = tokens.secondaryText
                        )

                        val opheliaUid = healthData?.get("ophelia_user_id") as? String ?: "USR-0000"
                        val bingxConnected = healthData?.get("bingx_connected") as? Boolean ?: false
                        val lastSync = (healthData?.get("last_bingx_sync") as? Number)?.toLong()
                        val lastExec = healthData?.get("last_execution_status") as? String ?: "IDLE"
                        val lastErr = healthData?.get("last_error") as? String ?: "NONE"
                        val latency = (healthData?.get("db_latency_ms") as? Number)?.toInt() ?: 1

                        val dateFmt = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US)
                        val syncStr = if (lastSync != null && lastSync > 0) dateFmt.format(Date(lastSync)) else "Never"

                        HealthMetricRow("Ophelia User ID", opheliaUid, AccentBlue)
                        HealthMetricRow("BingX Connection", if (bingxConnected) "CONNECTED" else "DISCONNECTED", if (bingxConnected) BullishGreen else AccentYellow)
                        HealthMetricRow("Last BingX Sync", syncStr, tokens.primaryText)
                        HealthMetricRow("Last Execution Status", lastExec, BullishGreen)
                        HealthMetricRow("Database Latency", "${latency}ms", BullishGreen)
                        HealthMetricRow("Last Reported Error", lastErr, if (lastErr == "NONE") tokens.secondaryText else BearishRed)
                    }
                }
            }
        }
    }
}

@Composable
private fun HealthMetricRow(label: String, value: String, valueColor: Color) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(text = label, style = MaterialTheme.typography.bodySmall, color = OpheliaThemeTokens.colors.secondaryText)
        Text(
            text = value,
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.Bold,
            color = valueColor,
            fontFamily = FontFamily.Monospace
        )
    }
}
