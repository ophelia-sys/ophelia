package com.ophelia.app.ui.screens

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun UserSystemControlScreen(
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val tokens = OpheliaThemeTokens.colors

    var isLoading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var systemControlData by remember { mutableStateOf<Map<String, Any>?>(null) }
    var isTogglingCopy by remember { mutableStateOf(false) }

    fun loadStatus() {
        scope.launch {
            isLoading = true
            errorMessage = null
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                val res = api.getUserSystemControl()
                systemControlData = res
            } catch (e: Exception) {
                errorMessage = e.message ?: "Failed to load system control status"
            } finally {
                isLoading = false
            }
        }
    }

    fun toggleCopyTrading(currentVal: Boolean) {
        scope.launch {
            isTogglingCopy = true
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                val newVal = !currentVal
                api.updateUserCopySettings(mapOf("copy_enabled" to newVal))
                Toast.makeText(
                    context,
                    if (newVal) "Master Copy Trading: ENABLED" else "Master Copy Trading: PAUSED",
                    Toast.LENGTH_SHORT
                ).show()
                loadStatus()
            } catch (e: Exception) {
                Toast.makeText(context, "Failed: ${e.message}", Toast.LENGTH_LONG).show()
            } finally {
                isTogglingCopy = false
            }
        }
    }

    LaunchedEffect(Unit) {
        loadStatus()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = "SYSTEM CONTROL",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = tokens.primaryText
                        )
                        Text(
                            text = "OPERATIONAL STATUS & PERMISSIONS",
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
            item {
                // Header Policy Banner
                OpheliaGlassCard(modifier = Modifier.fillMaxWidth()) {
                    Row(
                        modifier = Modifier.padding(14.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Icon(Icons.Default.Lock, contentDescription = null, tint = AccentBlue)
                        Column {
                            Text(
                                text = "READ-ONLY OPERATIONAL ACCESS",
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.Bold,
                                color = AccentBlue
                            )
                            Text(
                                text = "Admin maintains authoritative control over strategies, leverage, risk, and order sizing. Users can toggle personal copy trading and capital budgeting.",
                                style = MaterialTheme.typography.bodySmall,
                                color = tokens.secondaryText,
                                fontSize = 11.sp
                            )
                        }
                    }
                }
            }

            // User-controllable: Master Copy Trading Toggle
            item {
                val copyEnabled = systemControlData?.get("copy_trading_enabled") as? Boolean ?: false
                val adminAllowed = systemControlData?.get("admin_copy_allowed") as? Boolean ?: true
                val isSuspended = systemControlData?.get("suspended") as? Boolean ?: false

                OpheliaGlassCard(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Text(
                            text = "MASTER COPY TRADING",
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold,
                            color = tokens.primaryText
                        )

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = if (copyEnabled) "Copy Trading ACTIVE" else "Copy Trading PAUSED",
                                    style = MaterialTheme.typography.bodyMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = if (copyEnabled) BullishGreen else AccentYellow
                                )
                                Text(
                                    text = "When OFF, no new trades are copied to your account. Existing positions remain protected by VPS.",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = tokens.secondaryText,
                                    fontSize = 11.sp
                                )
                            }

                            Switch(
                                checked = copyEnabled,
                                onCheckedChange = { toggleCopyTrading(copyEnabled) },
                                enabled = !isTogglingCopy && adminAllowed && !isSuspended,
                                colors = SwitchDefaults.colors(
                                    checkedThumbColor = BullishGreen,
                                    checkedTrackColor = BullishGreen.copy(alpha = 0.3f)
                                )
                            )
                        }

                        if (!adminAllowed) {
                            Text(
                                text = "Admin has temporarily restricted fleet copy permission for this account.",
                                color = BearishRed,
                                fontSize = 11.sp
                            )
                        }
                        if (isSuspended) {
                            Text(
                                text = "Account suspended by Admin.",
                                color = BearishRed,
                                fontSize = 11.sp
                            )
                        }
                    }
                }
            }

            // System Status / Telemetry (Read-Only)
            item {
                OpheliaGlassCard(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Text(
                            text = "SYSTEM TELEMETRY (AUTHORITATIVE)",
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold,
                            color = tokens.secondaryText
                        )

                        val mode = systemControlData?.get("trading_mode") as? String ?: "SHADOW"
                        val gate = systemControlData?.get("execution_gate") as? String ?: "UNARMED"
                        val status = systemControlData?.get("system_status") as? String ?: "OPERATIONAL"
                        val bingxStatus = systemControlData?.get("bingx_connection_status") as? String ?: "DISCONNECTED"

                        TelemetryRow(label = "Trading Mode", value = mode, valueColor = if (mode == "LIVE") BearishRed else AccentBlue)
                        TelemetryRow(label = "Execution Gate", value = gate, valueColor = if (gate == "ARMED") BearishRed else tokens.secondaryText)
                        TelemetryRow(label = "VPS Health", value = status, valueColor = BullishGreen)
                        TelemetryRow(label = "BingX Connection", value = bingxStatus, valueColor = if (bingxStatus == "CONNECTED") BullishGreen else AccentYellow)
                        TelemetryRow(label = "User Permissions", value = "READ_ONLY", valueColor = tokens.secondaryText)
                    }
                }
            }
        }
    }
}

@Composable
private fun TelemetryRow(label: String, value: String, valueColor: Color) {
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
