package com.ophelia.app.ui.screens

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.KeyboardType
import com.ophelia.app.models.PreflightCheckItem
import com.ophelia.app.models.SetModeRequest
import com.ophelia.app.models.SystemControlResponse
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SystemControlCenterScreen(
    onBack: () -> Unit,
    onNavigateToAccountApiKeys: (() -> Unit)? = null
) {
    val context = LocalContext.current
    val uriHandler = androidx.compose.ui.platform.LocalUriHandler.current
    val scope = rememberCoroutineScope()

    var status by remember { mutableStateOf<SystemControlResponse?>(null) }
    var isLoading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }

    var isCheckingPreflight by remember { mutableStateOf(false) }
    var isSwitchingMode by remember { mutableStateOf(false) }
    var preflightBlockers by remember { mutableStateOf<List<String>>(emptyList()) }
    var showPreflightBlockerDialog by remember { mutableStateOf(false) }
    var showLiveConfirmDialog by remember { mutableStateOf(false) }
    var showDisableLiveConfirmDialog by remember { mutableStateOf(false) }

    var capInput by remember { mutableStateOf("2") }
    var isUpdatingCap by remember { mutableStateOf(false) }
    var capErrorMessage by remember { mutableStateOf<String?>(null) }

    fun refreshStatus() {
        scope.launch {
            isLoading = true
            errorMessage = null
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                val res = api.getSystemControl()
                status = res
                val configured = res.configuredMaxOpenTrades ?: res.maxOpenTrades
                capInput = configured.toString()
            } catch (e: Exception) {
                errorMessage = e.message ?: "Failed to connect to control plane"
            } finally {
                isLoading = false
            }
        }
    }

    LaunchedEffect(Unit) {
        refreshStatus()
    }

    val colors = OpheliaThemeTokens.colors

    if (showPreflightBlockerDialog) {
        OpheliaDialog(
            onDismissRequest = { showPreflightBlockerDialog = false },
            title = "LIVE READINESS BLOCKED",
            subtitle = "Preflight requirements must pass before arming LIVE mode",
            badgeText = "BLOCKED",
            badgeColor = WarningAmber,
            confirmButton = {
                OpheliaButton(
                    text = "DISMISS",
                    onClick = { showPreflightBlockerDialog = false }
                )
            }
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    text = "The following preflight requirements are currently blocking LIVE execution:",
                    style = MaterialTheme.typography.bodySmall,
                    color = colors.secondaryText
                )
                preflightBlockers.forEach { reason ->
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                        verticalAlignment = Alignment.Top
                    ) {
                        Text("•", color = BearishRed, fontWeight = FontWeight.Bold)
                        Text(
                            text = reason,
                            style = MaterialTheme.typography.bodySmall,
                            color = colors.primaryText,
                            fontSize = 11.sp
                        )
                    }
                }
            }
        }
    }

    if (showLiveConfirmDialog) {
        OpheliaDialog(
            onDismissRequest = { if (!isSwitchingMode) showLiveConfirmDialog = false },
            title = "ARM LIVE EXECUTION GATE",
            subtitle = "BingX Perpetual Swap Futures Real Execution",
            badgeText = "ARMED PROTOCOL",
            badgeColor = BearishRed,
            confirmButton = {
                OpheliaDangerButton(
                    text = if (isSwitchingMode) "ARMING..." else "CONFIRM & ARM LIVE",
                    enabled = !isSwitchingMode,
                    onClick = {
                        scope.launch {
                            isSwitchingMode = true
                            try {
                                val api = RetrofitClient.apiService ?: throw Exception("API unavailable")
                                val res = api.setMode(SetModeRequest(mode = "LIVE"))
                                Toast.makeText(context, "System transitioned to LIVE mode. Execution gate ARMED.", Toast.LENGTH_SHORT).show()
                                showLiveConfirmDialog = false
                                refreshStatus()
                            } catch (e: Exception) {
                                Toast.makeText(context, "Failed to switch to LIVE: ${e.message}", Toast.LENGTH_LONG).show()
                            } finally {
                                isSwitchingMode = false
                            }
                        }
                    }
                )
            },
            dismissButton = {
                OpheliaOutlinedButton(
                    text = "CANCEL",
                    enabled = !isSwitchingMode,
                    onClick = { showLiveConfirmDialog = false }
                )
            }
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    text = "AUTHORITATIVE LIVE TRANSITION",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Bold,
                    color = BearishRed
                )
                Text(
                    text = "Switching mode to LIVE will ARM the backend execution gate. Valid breakout & retest signals will place real orders on BingX Perpetual Futures. This transition will be permanently recorded in the system audit log.",
                    style = MaterialTheme.typography.bodySmall,
                    color = colors.secondaryText
                )
            }
        }
    }

    if (showDisableLiveConfirmDialog) {
        OpheliaDialog(
            onDismissRequest = { if (!isSwitchingMode) showDisableLiveConfirmDialog = false },
            title = "RETURN TO SHADOW MODE?",
            subtitle = "Block real exchange order execution",
            badgeText = "SAFETY RETURN",
            badgeColor = AccentBlue,
            confirmButton = {
                OpheliaButton(
                    text = if (isSwitchingMode) "DISARMING..." else "DISARM & RETURN TO SHADOW",
                    enabled = !isSwitchingMode,
                    onClick = {
                        scope.launch {
                            isSwitchingMode = true
                            try {
                                val api = RetrofitClient.apiService ?: throw Exception("API unavailable")
                                val res = api.setMode(SetModeRequest(mode = "SHADOW"))
                                Toast.makeText(context, "System transitioned to SHADOW mode. Execution gate UNARMED.", Toast.LENGTH_SHORT).show()
                                showDisableLiveConfirmDialog = false
                                refreshStatus()
                            } catch (e: Exception) {
                                Toast.makeText(context, "Failed to switch to SHADOW: ${e.message}", Toast.LENGTH_LONG).show()
                            } finally {
                                isSwitchingMode = false
                            }
                        }
                    }
                )
            },
            dismissButton = {
                OpheliaOutlinedButton(
                    text = "CANCEL",
                    enabled = !isSwitchingMode,
                    onClick = { showDisableLiveConfirmDialog = false }
                )
            }
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    text = "This will return the system to SHADOW mode. The execution gate will be immediately UNARMED and all new live orders blocked. The transition will be recorded in the audit log.",
                    style = MaterialTheme.typography.bodySmall,
                    color = colors.secondaryText
                )
            }
        }
    }

    Scaffold(
        containerColor = BackgroundCanvas,
        topBar = {
            OpheliaTopBar(
                title = "SYSTEM CONTROL",
                subtitle = "Authoritative Execution, Safety Gates & BingX Connection",
                onBack = onBack,
                onRefresh = { refreshStatus() }
            )
        }
    ) { padding ->
        if (isLoading) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
            }
        } else if (errorMessage != null) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(16.dp),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("Error: $errorMessage", color = BearishRed, fontWeight = FontWeight.Bold)
                    OpheliaButton(text = "RETRY", onClick = { refreshStatus() })
                }
            }
        } else {
            val s = status ?: SystemControlResponse()

            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                // 1. PRIMARY SYSTEM STATE BANNER
                item {
                    OpheliaGlassCard(
                        borderColor = AccentBlue.copy(alpha = 0.5f)
                    ) {
                        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Icon(Icons.Filled.Lock, contentDescription = null, tint = AccentBlue, modifier = Modifier.size(20.dp))
                                    Text(
                                        text = "CORE SYSTEM STATUS",
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.Bold,
                                        color = colors.primaryText
                                    )
                                }
                                OpheliaStatusBadge(
                                    status = "MODE: ${s.currentMode}",
                                    color = if (s.currentMode == "LIVE") WarningAmber else AccentBlue,
                                    showDot = true
                                )
                            }

                            OpheliaDivider()

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                OpheliaMetric(label = "Trading Mode", value = s.currentMode, valueColor = AccentBlue)
                                OpheliaMetric(label = "Live Execution", value = s.liveExecution, valueColor = BearishRed)
                                OpheliaMetric(label = "Execution Block", value = s.executionBlock, valueColor = WarningAmber)
                                OpheliaMetric(label = "Configured Cap", value = "${s.configuredMaxOpenTrades ?: s.maxOpenTrades}", valueColor = BullishGreen)
                            }
                        }
                    }
                }

                // 1.5 BINGX CONNECTION & API CREDENTIAL SOURCE (Requirement 18-24)
                // 1.5 BINGX CONNECTION QUICK ACCESS CARD
                item {
                    OpheliaGlassCard(
                        borderColor = AccentBlue.copy(alpha = 0.4f),
                        onClick = onNavigateToAccountApiKeys
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(10.dp),
                                modifier = Modifier.weight(1f)
                            ) {
                                Icon(Icons.Filled.Settings, contentDescription = null, tint = AccentBlue, modifier = Modifier.size(22.dp))
                                Column {
                                    Text(
                                        text = "BINGX ACCOUNT & CREDENTIALS",
                                        style = MaterialTheme.typography.titleSmall,
                                        fontWeight = FontWeight.Bold,
                                        color = colors.primaryText
                                    )
                                    Text(
                                        text = "Manage exchange API keys, connection latency & credentials",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = colors.mutedText,
                                        fontSize = 11.sp
                                    )
                                }
                            }
                            if (onNavigateToAccountApiKeys != null) {
                                OpheliaOutlinedButton(
                                    text = "MANAGE",
                                    onClick = onNavigateToAccountApiKeys
                                )
                            }
                        }
                    }
                }

                // 2. CONCURRENT TRADE CAPACITY SETTING (PERSISTENT USER-CONFIGURABLE)
                item {
                    val configuredCap = s.configuredMaxOpenTrades ?: s.maxOpenTrades
                    val safetyCeiling = s.systemSafetyMaxOpenTrades ?: 50
                    val openCount = s.openPositionsCount
                    val availSlots = s.availableExecutionSlots ?: maxOf(0, configuredCap - openCount)
                    val isCapBelowExposure = s.capState == "BELOW_EXPOSURE" || configuredCap < openCount

                    OpheliaGlassCard(
                        borderColor = if (isCapBelowExposure) BearishRed.copy(alpha = 0.6f) else AccentBlue.copy(alpha = 0.4f)
                    ) {
                        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text(
                                        text = "CONCURRENT TRADE CAPACITY",
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.Bold,
                                        color = colors.primaryText
                                    )
                                    Text(
                                        text = "User-configurable persistent trade ceiling (Safety ceiling: $safetyCeiling)",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = colors.mutedText,
                                        fontSize = 11.sp
                                    )
                                }
                                OpheliaStatusBadge(
                                    status = if (isCapBelowExposure) "CAP BELOW EXPOSURE" else "$availSlots SLOTS AVAIL",
                                    color = if (isCapBelowExposure) BearishRed else (if (availSlots > 0) BullishGreen else WarningAmber),
                                    showDot = true
                                )
                            }

                            OpheliaDivider()

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                OpheliaMetric(
                                    label = "Configured Cap",
                                    value = "$configuredCap",
                                    valueColor = BullishGreen,
                                    subValue = "Persistent"
                                )
                                OpheliaMetric(
                                    label = "Open Exposure",
                                    value = "$openCount",
                                    valueColor = if (openCount > 0) WarningAmber else colors.primaryText,
                                    subValue = "Active trades"
                                )
                                OpheliaMetric(
                                    label = "Available Slots",
                                    value = "$availSlots",
                                    valueColor = if (availSlots > 0) BullishGreen else BearishRed,
                                    subValue = if (isCapBelowExposure) "Blocked" else "Entries allowed"
                                )
                                OpheliaMetric(
                                    label = "Safety Ceiling",
                                    value = "$safetyCeiling",
                                    valueColor = colors.mutedText,
                                    subValue = "Platform constraint"
                                )
                            }

                            if (isCapBelowExposure) {
                                Box(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clip(RoundedCornerShape(8.dp))
                                        .background(BearishRed.copy(alpha = 0.15f))
                                        .border(1.dp, BearishRed.copy(alpha = 0.5f), RoundedCornerShape(8.dp))
                                        .padding(10.dp)
                                ) {
                                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                            Icon(Icons.Filled.Warning, contentDescription = null, tint = BearishRed, modifier = Modifier.size(16.dp))
                                            Text(
                                                text = "CAP BELOW CURRENT EXPOSURE",
                                                style = MaterialTheme.typography.labelSmall,
                                                fontWeight = FontWeight.Bold,
                                                color = BearishRed
                                            )
                                        }
                                        Text(
                                            text = "Configured trade cap ($configuredCap) is below current open exposure ($openCount). Existing positions are preserved (never force-closed). All new entries are strictly blocked and available slots = 0 until exposure drops below cap.",
                                            style = MaterialTheme.typography.bodySmall,
                                            color = colors.secondaryText,
                                            fontSize = 11.sp,
                                            lineHeight = 15.sp
                                        )
                                    }
                                }
                            }

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(10.dp)
                            ) {
                                OutlinedTextField(
                                    value = capInput,
                                    onValueChange = { newVal ->
                                        if (newVal.all { it.isDigit() } && newVal.length <= 3) {
                                            capInput = newVal
                                            capErrorMessage = null
                                        }
                                    },
                                    modifier = Modifier.weight(1f),
                                    label = { Text("Max Trades (1-$safetyCeiling)", fontSize = 11.sp) },
                                    singleLine = true,
                                    keyboardOptions = KeyboardOptions(
                                        keyboardType = KeyboardType.Number
                                    ),
                                    colors = OutlinedTextFieldDefaults.colors(
                                        focusedBorderColor = AccentBlue,
                                        unfocusedBorderColor = colors.border,
                                        focusedTextColor = colors.primaryText,
                                        unfocusedTextColor = colors.primaryText,
                                        focusedLabelColor = AccentBlue,
                                        unfocusedLabelColor = colors.mutedText
                                    )
                                )

                                OpheliaButton(
                                    text = if (isUpdatingCap) "SAVING..." else "APPLY CAP",
                                    enabled = !isUpdatingCap && capInput.isNotBlank(),
                                    onClick = {
                                        val parsed = capInput.toIntOrNull()
                                        if (parsed == null || parsed < 1) {
                                            capErrorMessage = "Cap must be at least 1"
                                            Toast.makeText(context, "Cap must be at least 1", Toast.LENGTH_SHORT).show()
                                            return@OpheliaButton
                                        }
                                        if (parsed > safetyCeiling) {
                                            capErrorMessage = "Exceeds platform safety ceiling ($safetyCeiling)"
                                            Toast.makeText(context, "Exceeds safety limit of $safetyCeiling", Toast.LENGTH_SHORT).show()
                                            return@OpheliaButton
                                        }

                                        scope.launch {
                                            isUpdatingCap = true
                                            try {
                                                val api = RetrofitClient.apiService ?: throw Exception("API unavailable")
                                                val updated = api.setTradeCap(mapOf("max_open_trades" to parsed))
                                                Toast.makeText(context, "Trade cap updated to ${updated.configuredMaxOpenTrades}", Toast.LENGTH_SHORT).show()
                                                refreshStatus()
                                            } catch (e: Exception) {
                                                Toast.makeText(context, "Failed to update cap: ${e.message}", Toast.LENGTH_LONG).show()
                                            } finally {
                                                isUpdatingCap = false
                                            }
                                        }
                                    }
                                )
                            }

                            if (capErrorMessage != null) {
                                Text(
                                    text = capErrorMessage ?: "",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = BearishRed,
                                    fontSize = 11.sp
                                )
                            }
                        }
                    }
                }

                // 3. LIVE TOGGLE CONTROL (AUTHORITATIVE)
                item {
                    val isLiveMode = s.currentMode == "LIVE" || s.liveExecution == "ON"
                    OpheliaGlassCard(
                        borderColor = if (isLiveMode) BearishRed.copy(alpha = 0.8f) else colors.border
                    ) {
                        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text(
                                        text = "LIVE EXECUTION TOGGLE",
                                        style = MaterialTheme.typography.titleSmall,
                                        fontWeight = FontWeight.Bold,
                                        color = if (isLiveMode) BearishRed else colors.primaryText
                                    )
                                    Text(
                                        text = if (isLiveMode) "Execution gate ARMED (Real BingX Orders)" else "Execution gate UNARMED (Shadow / Paper Mode)",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = colors.mutedText,
                                        fontSize = 11.sp
                                    )
                                }
                                Switch(
                                    checked = isLiveMode,
                                    enabled = !isCheckingPreflight && !isSwitchingMode,
                                    onCheckedChange = { checked ->
                                        if (checked) {
                                            scope.launch {
                                                isCheckingPreflight = true
                                                try {
                                                    val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                                                    val readiness = api.getLiveReadiness()
                                                    val blockers = readiness.blockingReasons.filter { !it.contains("Trading mode is SHADOW") }
                                                    if (blockers.isNotEmpty() || readiness.liveReady == false) {
                                                        preflightBlockers = blockers.ifEmpty { listOf("Live readiness preflight checks failed.") }
                                                        showPreflightBlockerDialog = true
                                                    } else {
                                                        showLiveConfirmDialog = true
                                                    }
                                                } catch (e: Exception) {
                                                    Toast.makeText(context, "Preflight check failed: ${e.message}", Toast.LENGTH_LONG).show()
                                                } finally {
                                                    isCheckingPreflight = false
                                                }
                                            }
                                        } else {
                                            showDisableLiveConfirmDialog = true
                                        }
                                    },
                                    colors = SwitchDefaults.colors(
                                        checkedThumbColor = Color.White,
                                        checkedTrackColor = BearishRed,
                                        uncheckedThumbColor = colors.mutedText,
                                        uncheckedTrackColor = colors.surfaceElevated
                                    )
                                )
                            }

                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clip(RoundedCornerShape(8.dp))
                                    .background(if (isLiveMode) BearishRed.copy(alpha = 0.15f) else AccentBlue.copy(alpha = 0.12f))
                                    .border(1.dp, if (isLiveMode) BearishRed.copy(alpha = 0.45f) else AccentBlue.copy(alpha = 0.35f), RoundedCornerShape(8.dp))
                                    .padding(10.dp)
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Icon(
                                        if (isLiveMode) Icons.Filled.Warning else Icons.Filled.Lock,
                                        contentDescription = null,
                                        tint = if (isLiveMode) BearishRed else AccentBlue,
                                        modifier = Modifier.size(16.dp)
                                    )
                                    Text(
                                        text = if (isLiveMode) "EXECUTION GATE: ARMED • Real BingX Perpetual orders permitted." else "EXECUTION GATE: UNARMED • System running in SHADOW mode (zero live orders).",
                                        style = MaterialTheme.typography.bodySmall,
                                        fontSize = 11.sp,
                                        fontWeight = FontWeight.SemiBold,
                                        color = if (isLiveMode) BearishRed else AccentBlue
                                    )
                                }
                            }
                        }
                    }
                }

                // 3. SUBSYSTEM HEALTH MATRIX
                item {
                    OpheliaSectionHeader(title = "SUBSYSTEM HEALTH & INTEGRATIONS")
                }

                item {
                    OpheliaGlassCard {
                        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            val items = listOf(
                                Pair("BingX API Authentication", s.bingxAuth),
                                Pair("Market Data Feed (Websocket & REST)", s.marketData),
                                Pair("Deterministic Risk Engine", s.riskEngine),
                                Pair("Portfolio Reconciliation", s.reconciliation),
                                Pair("Ollama Reasoning Daemon", s.ollama),
                                Pair("Ophelia ML Intelligence Engine", s.tradingagents)
                            )

                            items.forEach { (name, state) ->
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(text = name, style = MaterialTheme.typography.bodyMedium, color = colors.primaryText)
                                    val isOk = state in listOf("OK", "CONNECTED", "ONLINE", "AUTHENTICATED")
                                    val badgeColor = if (isOk) BullishGreen else BearishRed
                                    OpheliaStatusBadge(status = state, color = badgeColor, showDot = isOk)
                                }
                                OpheliaDivider()
                            }
                        }
                    }
                }

                // 4. 12-POINT PREFLIGHT VERIFICATION CHECKLIST
                item {
                    OpheliaSectionHeader(title = "12-POINT PREFLIGHT CHECKLIST")
                }

                if (s.checklist.isNotEmpty()) {
                    items(s.checklist) { item ->
                        OpheliaGlassCard {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = item.item,
                                        style = MaterialTheme.typography.bodyMedium,
                                        fontWeight = FontWeight.SemiBold,
                                        color = colors.primaryText
                                    )
                                    if (item.detail.isNotBlank()) {
                                        Text(
                                            text = item.detail,
                                            style = MaterialTheme.typography.bodySmall,
                                            color = colors.mutedText,
                                            fontSize = 11.sp
                                        )
                                    }
                                }
                                val statusText = if (item.passed) "PASS" else "BLOCKED"
                                OpheliaStatusBadge(
                                    status = statusText,
                                    color = if (item.passed) BullishGreen else BearishRed,
                                    showDot = item.passed
                                )
                            }
                        }
                    }
                } else {
                    item {
                        OpheliaGlassCard {
                            Text("All 12 preflight verification safety checks evaluated.", style = MaterialTheme.typography.bodySmall, color = colors.secondaryText)
                        }
                    }
                }

                item {
                    Spacer(modifier = Modifier.height(16.dp))
                }
            }
        }
    }
}
