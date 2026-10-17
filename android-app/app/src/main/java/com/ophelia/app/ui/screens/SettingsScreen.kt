package com.ophelia.app.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.ophelia.app.auth.TokenManager
import com.ophelia.app.models.*
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.viewmodels.UiState
import com.ophelia.app.ui.theme.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.Locale

class SettingsViewModel(private val tokenManager: TokenManager) : ViewModel() {
    private val _dashboardState = MutableStateFlow<UiState<DashboardResponse>>(UiState.Loading)
    val dashboardState = _dashboardState.asStateFlow()

    private val _preflightState = MutableStateFlow<UiState<PreflightResponse>>(UiState.Idle)
    val preflightState = _preflightState.asStateFlow()

    private val _actionState = MutableStateFlow<UiState<String>>(UiState.Idle)
    val actionState = _actionState.asStateFlow()

    private val _notificationSettings = MutableStateFlow(NotificationSettingsDto())
    val notificationSettings = _notificationSettings.asStateFlow()

    init {
        fetchSettingsData()
        fetchNotificationSettings()
    }

    fun fetchNotificationSettings() {
        viewModelScope.launch {
            try {
                val api = RetrofitClient.apiService ?: return@launch
                _notificationSettings.value = api.getNotificationSettings()
            } catch (e: Exception) {}
        }
    }

    fun updateNotificationSettings(settings: NotificationSettingsDto) {
        _notificationSettings.value = settings
        viewModelScope.launch {
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val saved = api.saveNotificationSettings(settings)
                _notificationSettings.value = saved
            } catch (e: Exception) {}
        }
    }

    fun fetchSettingsData() {
        viewModelScope.launch {
            _dashboardState.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val res = api.getDashboard()
                _dashboardState.value = UiState.Success(res)
            } catch (e: Exception) {
                _dashboardState.value = UiState.Error(e.message ?: "Failed to load settings data")
            }
        }
    }

    fun checkPreflight() {
        viewModelScope.launch {
            _preflightState.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val res = api.getPreflight()
                _preflightState.value = UiState.Success(res)
            } catch (e: Exception) {
                _preflightState.value = UiState.Error(e.message ?: "Preflight check failed")
            }
        }
    }

    fun setMode(mode: String, onDone: () -> Unit = {}) {
        viewModelScope.launch {
            _actionState.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val res = api.setMode(SetModeRequest(mode = mode))
                if (res.success) {
                    val confirmedMode = res.mode ?: mode
                    _actionState.value = UiState.Success("Mode changed to $confirmedMode")
                    fetchSettingsData()
                    onDone()
                } else {
                    _actionState.value = UiState.Error("Mode transition rejected by engine")
                }
            } catch (e: Exception) {
                _actionState.value = UiState.Error(e.message ?: "Failed to change mode")
            }
        }
    }

    fun pauseAllAutomations(onDone: () -> Unit = {}) {
        viewModelScope.launch {
            _actionState.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService ?: return@launch
                api.pauseAllAutomations()
                _actionState.value = UiState.Success("All automations paused")
                fetchSettingsData()
                onDone()
            } catch (e: Exception) {
                _actionState.value = UiState.Error(e.message ?: "Failed to pause automations")
            }
        }
    }

    fun emergencyCloseAll(onDone: () -> Unit = {}) {
        viewModelScope.launch {
            _actionState.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService ?: return@launch
                api.emergencyCloseAll()
                _actionState.value = UiState.Success("Emergency close executed")
                fetchSettingsData()
                onDone()
            } catch (e: Exception) {
                _actionState.value = UiState.Error(e.message ?: "Failed to close all positions")
            }
        }
    }

    fun reconcilePositions() {
        viewModelScope.launch {
            _actionState.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService ?: return@launch
                api.reconcilePositions()
                _actionState.value = UiState.Success("Position state reconciled with exchange")
                fetchSettingsData()
            } catch (e: Exception) {
                _actionState.value = UiState.Error(e.message ?: "Reconciliation failed")
            }
        }
    }

    fun resetPreflight() {
        _preflightState.value = UiState.Idle
    }

    fun resetActionState() {
        _actionState.value = UiState.Idle
    }
}

@Composable
fun SettingsScreen(
    onBack: () -> Unit,
    onLogout: () -> Unit
) {
    val context = LocalContext.current
    val tokenManager = remember { TokenManager(context) }

    val viewModel: SettingsViewModel = viewModel(
        factory = object : ViewModelProvider.Factory {
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return SettingsViewModel(tokenManager) as T
            }
        }
    )

    val dashboardState by viewModel.dashboardState.collectAsState()
    val preflightState by viewModel.preflightState.collectAsState()
    val actionState by viewModel.actionState.collectAsState()
    val notificationSettings by viewModel.notificationSettings.collectAsState()

    var showPreflightDialog by remember { mutableStateOf(false) }
    var preflightStep by remember { mutableStateOf("CHECKLIST") } // "CHECKLIST" or "CONFIRMATION"
    var showEmergencyCloseDialog by remember { mutableStateOf(false) }

    val currentMode = when (val d = dashboardState) {
        is UiState.Success -> d.data.health.mode.uppercase()
        else -> "SHADOW"
    }
    val isLive = currentMode == "LIVE"

    // 1. LIVE PREFLIGHT & CONFIRMATION MODAL
    if (showPreflightDialog) {
        val dash = (dashboardState as? UiState.Success)?.data
        val equityStr = dash?.account?.totalEquity?.let { String.format(Locale.US, "$%,.2f", it) } ?: "$32.86"
        val availStr = dash?.account?.availableMargin?.let { String.format(Locale.US, "$%,.2f", it) } ?: "$32.86"
        val openCount = dash?.positions?.size ?: 0
        val maxCap = dash?.risk?.positionsMax ?: 2

        OpheliaDialog(
            onDismissRequest = {
                showPreflightDialog = false
                preflightStep = "CHECKLIST"
                viewModel.resetPreflight()
            },
            title = if (preflightStep == "CHECKLIST") "LIVE READINESS PREFLIGHT" else "ENTER LIVE TRADING MODE?",
            subtitle = if (preflightStep == "CHECKLIST") "Pre-Execution Safety Verification" else "BingX Perpetual Swap Futures Execution",
            badgeText = if (preflightStep == "CONFIRMATION") "REAL MONEY ORDERS" else null,
            badgeColor = if (preflightStep == "CONFIRMATION") BearishRed else null,
            confirmButton = {
                if (preflightStep == "CHECKLIST") {
                    val pState = preflightState
                    if (pState is UiState.Success && pState.data.readyForLive && !isLive) {
                        OpheliaButton(
                            text = "CONTINUE TO LIVE",
                            onClick = { preflightStep = "CONFIRMATION" }
                        )
                    } else {
                        OpheliaButton(
                            text = "CLOSE",
                            onClick = {
                                showPreflightDialog = false
                                preflightStep = "CHECKLIST"
                                viewModel.resetPreflight()
                            }
                        )
                    }
                } else {
                    OpheliaDangerButton(
                        text = "ACTIVATE LIVE TRADING",
                        onClick = {
                            showPreflightDialog = false
                            preflightStep = "CHECKLIST"
                            viewModel.setMode("LIVE")
                        }
                    )
                }
            },
            dismissButton = {
                if (preflightStep == "CHECKLIST") {
                    val pState = preflightState
                    if (pState is UiState.Success && pState.data.readyForLive && !isLive) {
                        OpheliaOutlinedButton(
                            text = "CANCEL",
                            onClick = {
                                showPreflightDialog = false
                                preflightStep = "CHECKLIST"
                                viewModel.resetPreflight()
                            }
                        )
                    }
                } else {
                    OpheliaOutlinedButton(
                        text = "BACK",
                        onClick = { preflightStep = "CHECKLIST" }
                    )
                }
            }
        ) {
            if (preflightStep == "CHECKLIST") {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(max = 440.dp)
                        .verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
                ) {
                    when (val pState = preflightState) {
                        is UiState.Loading -> {
                            OpheliaLoadingState(message = "Evaluating safety guardrails across 6 categories...")
                        }
                        is UiState.Error -> {
                            OpheliaStatusBadge(status = "PREFLIGHT ERROR", color = BearishRed)
                            Text(
                                text = pState.message,
                                color = BearishRed,
                                style = MaterialTheme.typography.bodySmall
                            )
                        }
                        is UiState.Success -> {
                            val data = pState.data
                            if (data.readyForLive) {
                                OpheliaStatusBadge(
                                    status = "ALL SAFETY CHECKS PASSED — READY FOR LIVE",
                                    color = BullishGreen
                                )
                            } else {
                                OpheliaStatusBadge(
                                    status = "LIVE TRADING BLOCKED",
                                    color = BearishRed
                                )
                                if (data.blockingReasons.isNotEmpty()) {
                                    OpheliaGlassPanel(modifier = Modifier.fillMaxWidth()) {
                                        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                            Text(
                                                text = "BLOCKING REASONS:",
                                                style = MaterialTheme.typography.labelSmall,
                                                fontWeight = FontWeight.Bold,
                                                color = BearishRed
                                            )
                                            data.blockingReasons.forEach { reason ->
                                                Text(
                                                    text = "• $reason",
                                                    style = MaterialTheme.typography.labelSmall,
                                                    color = TextPrimary
                                                )
                                            }
                                        }
                                    }
                                }
                            }

                            Spacer(modifier = Modifier.height(OpheliaSpacing.xs))

                            // Group checklist by category
                            val grouped = data.checklist.groupBy { it.category ?: "GENERAL" }
                            grouped.forEach { (category, items) ->
                                Text(
                                    text = category,
                                    style = MaterialTheme.typography.labelSmall,
                                    fontWeight = FontWeight.Bold,
                                    color = AccentBlue,
                                    letterSpacing = 0.5.sp
                                )
                                items.forEach { item ->
                                    OpheliaGlassPanel(modifier = Modifier.fillMaxWidth()) {
                                        Row(
                                            modifier = Modifier.fillMaxWidth(),
                                            verticalAlignment = Alignment.CenterVertically,
                                            horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
                                        ) {
                                            Icon(
                                                imageVector = if (item.passed) Icons.Filled.Check else Icons.Filled.Close,
                                                contentDescription = null,
                                                tint = if (item.passed) BullishGreen else BearishRed,
                                                modifier = Modifier.size(16.dp)
                                            )
                                            Column {
                                                Text(
                                                    text = item.item,
                                                    style = MaterialTheme.typography.labelMedium,
                                                    fontWeight = FontWeight.SemiBold,
                                                    color = TextPrimary
                                                )
                                                Text(
                                                    text = item.detail,
                                                    style = MaterialTheme.typography.labelSmall,
                                                    color = TextSecondary
                                                )
                                            }
                                        }
                                    }
                                }
                            }

                            if (data.warning.isNotBlank()) {
                                Text(
                                    text = data.warning,
                                    style = MaterialTheme.typography.labelSmall,
                                    color = WarningAmber
                                )
                            }
                        }
                        else -> {}
                    }
                }
            } else {
                // Confirmation Content
                Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)) {
                    OpheliaGlassPanel(modifier = Modifier.fillMaxWidth()) {
                        Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text("Account Equity:", style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                                Text(equityStr, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = TextPrimary)
                            }
                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text("Available Margin:", style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                                Text(availStr, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = BullishGreen)
                            }
                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text("Open Positions:", style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                                Text("$openCount / $maxCap Active", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = TextPrimary)
                            }
                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text("Mode Transition:", style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                                Text("SHADOW → LIVE", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = BullishGreen)
                            }
                        }
                    }

                    Text(
                        text = "WARNING: LIVE MODE SUBMITS REAL ORDERS DIRECTLY TO BINGX PERPETUAL FUTURES. Real funds will be allocated according to configured automation and risk parameters.",
                        style = MaterialTheme.typography.labelSmall,
                        color = WarningAmber
                    )
                }
            }
        }
    }

    // 2. EMERGENCY CLOSE ALL CONFIRMATION DIALOG
    if (showEmergencyCloseDialog) {
        val dash = (dashboardState as? UiState.Success)?.data
        val openCount = dash?.positions?.size ?: 0

        OpheliaDialog(
            onDismissRequest = { showEmergencyCloseDialog = false },
            title = "EMERGENCY CLOSE ALL?",
            subtitle = "Immediate Market Close Protocol",
            badgeText = "CRITICAL",
            badgeColor = BearishRed,
            confirmButton = {
                OpheliaDangerButton(
                    text = "CLOSE ALL POSITIONS",
                    onClick = {
                        showEmergencyCloseDialog = false
                        viewModel.emergencyCloseAll()
                    }
                )
            },
            dismissButton = {
                OpheliaOutlinedButton(
                    text = "CANCEL",
                    onClick = { showEmergencyCloseDialog = false }
                )
            }
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)) {
                Text(
                    text = "This will attempt to submit immediate MARKET CLOSE orders for ALL currently open positions on BingX.",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextPrimary
                )
                OpheliaGlassPanel(modifier = Modifier.fillMaxWidth()) {
                    Text(
                        text = "Active Open Positions to Close: $openCount",
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.Bold,
                        color = BearishRed
                    )
                }
            }
        }
    }

    Scaffold(
        containerColor = BackgroundCanvas,
        topBar = {
            OpheliaTopBar(
                title = "SYSTEM CONTROL CENTER",
                subtitle = "Execution Authority & Safety",
                statusText = if (isLive) "LIVE" else "SHADOW",
                statusColor = if (isLive) BullishGreen else WarningAmber,
                onBack = onBack,
                onRefresh = { viewModel.fetchSettingsData() }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = OpheliaSpacing.screenHorizontal),
            verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.md)
        ) {
            Spacer(modifier = Modifier.height(OpheliaSpacing.xs))

            // Action Feedback Notification (if any)
            when (val act = actionState) {
                is UiState.Success -> {
                    OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.fillMaxWidth(), borderColor = BullishGreenBorder) {
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                            Text(text = act.data, style = MaterialTheme.typography.labelMedium, color = BullishGreen)
                            TextButton(onClick = { viewModel.resetActionState() }) {
                                Text("DISMISS", style = MaterialTheme.typography.labelSmall, color = TextPrimary)
                            }
                        }
                    }
                }
                is UiState.Error -> {
                    OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.fillMaxWidth(), borderColor = BearishRedBorder) {
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                            Text(text = "Action error: ${act.message}", style = MaterialTheme.typography.labelMedium, color = BearishRed)
                            TextButton(onClick = { viewModel.resetActionState() }) {
                                Text("DISMISS", style = MaterialTheme.typography.labelSmall, color = TextPrimary)
                            }
                        }
                    }
                }
                else -> {}
            }

            // 1. PRIMARY EXECUTION MODE CONTROL CARD
            OpheliaSectionHeader(title = "Execution Mode & Safety Barrier")
            OpheliaGlassCard(
                level = GlassLevel.L1,
                modifier = Modifier.fillMaxWidth(),
                borderColor = if (isLive) BullishGreenBorder else WarningAmber.copy(alpha = 0.6f)
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text(
                                text = "TRADING MODE",
                                style = MaterialTheme.typography.labelSmall,
                                color = TextSecondary
                            )
                            Text(
                                text = if (isLive) "LIVE (REAL BINGX ORDERS)" else "SHADOW (PAPER SIMULATION)",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold,
                                color = if (isLive) BullishGreen else WarningAmber
                            )
                        }
                        OpheliaStatusBadge(
                            status = if (isLive) "LIVE ●" else "SHADOW ●",
                            color = if (isLive) BullishGreen else WarningAmber
                        )
                    }

                    OpheliaDivider()

                    if (isLive) {
                        Text(
                            text = "Real money execution is ACTIVE. All strategy signals submit live orders directly to BingX Perpetual Futures.",
                            style = MaterialTheme.typography.labelSmall,
                            color = TextPrimary
                        )
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
                        ) {
                            OpheliaOutlinedButton(
                                text = "SWITCH TO SHADOW",
                                onClick = { viewModel.setMode("SHADOW") },
                                modifier = Modifier.weight(1f)
                            )
                            OpheliaButton(
                                text = "PAUSE ALL AUTO",
                                onClick = { viewModel.pauseAllAutomations() },
                                modifier = Modifier.weight(1f)
                            )
                        }
                        OpheliaDangerButton(
                            text = "EMERGENCY CLOSE ALL POSITIONS",
                            onClick = { showEmergencyCloseDialog = true },
                            modifier = Modifier.fillMaxWidth()
                        )
                    } else {
                        Text(
                            text = "Safe shadow execution. Orders are simulated with real order book pricing and exchange fees. Zero live capital risk.",
                            style = MaterialTheme.typography.labelSmall,
                            color = TextSecondary
                        )
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
                        ) {
                            OpheliaButton(
                                text = "RUN PREFLIGHT",
                                onClick = {
                                    preflightStep = "CHECKLIST"
                                    showPreflightDialog = true
                                    viewModel.checkPreflight()
                                },
                                modifier = Modifier.weight(1f)
                            )
                            OpheliaOutlinedButton(
                                text = "PAUSE ALL AUTO",
                                onClick = { viewModel.pauseAllAutomations() },
                                modifier = Modifier.weight(1f)
                            )
                        }
                    }
                }
            }

            // 2. EXCHANGE ACCOUNT CONNECTIVITY PANEL
            OpheliaSectionHeader(title = "Account & Exchange Connectivity")
            OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.fillMaxWidth()) {
                Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "BINGX PERPETUAL SWAPS",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold,
                            color = TextPrimary
                        )
                        OpheliaStatusBadge(status = "AUTHENTICATED", color = BullishGreen)
                    }
                    OpheliaDivider()
                    Text("Host: 15.235.193.47 (Singapore VPS)", style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                    Text("Transport: HTTPS / WSS TLS Encrypted", style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                    Text("Key Storage: AES-256 Android Encrypted SharedPreferences", style = MaterialTheme.typography.labelSmall, color = BullishGreen)
                }
            }

            // 3. RISK GUARDRAILS & POSITION RECONCILIATION
            OpheliaSectionHeader(
                title = "Risk & State Reconciliation",
                actionText = "RECONCILE NOW",
                onActionClick = { viewModel.reconcilePositions() }
            )
            OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.fillMaxWidth()) {
                Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        OpheliaMetric(label = "Max Positions", value = "Configurable (Cap 4)")
                        OpheliaMetric(label = "Risk Barrier", value = "Fail-Closed", valueColor = BullishGreen)
                        OpheliaMetric(label = "Authority", value = "Core Backend", valueColor = AccentBlue)
                    }
                }
            }

            // 4. NOTIFICATION SUBSCRIPTIONS
            OpheliaSectionHeader(title = "Notification Preferences")
            OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.fillMaxWidth()) {
                Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("Push Notifications", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold, color = TextPrimary)
                        Switch(
                            checked = notificationSettings.enabled,
                            onCheckedChange = { viewModel.updateNotificationSettings(notificationSettings.copy(enabled = it)) },
                            colors = SwitchDefaults.colors(checkedThumbColor = AccentBlue, checkedTrackColor = AccentBlue.copy(alpha = 0.5f))
                        )
                    }

                    OpheliaDivider()

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("Trade Entries & Fills", style = MaterialTheme.typography.bodySmall, color = TextPrimary)
                        Switch(
                            checked = notificationSettings.tradesEnabled,
                            enabled = notificationSettings.enabled,
                            onCheckedChange = { viewModel.updateNotificationSettings(notificationSettings.copy(tradesEnabled = it)) }
                        )
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("Take Profit & Stop Loss Hits", style = MaterialTheme.typography.bodySmall, color = TextPrimary)
                        Switch(
                            checked = notificationSettings.tpSlEnabled,
                            enabled = notificationSettings.enabled,
                            onCheckedChange = { viewModel.updateNotificationSettings(notificationSettings.copy(tpSlEnabled = it)) }
                        )
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("Liquidation & Risk Warnings", style = MaterialTheme.typography.bodySmall, color = TextPrimary)
                        Switch(
                            checked = notificationSettings.riskEnabled,
                            enabled = notificationSettings.enabled,
                            onCheckedChange = { viewModel.updateNotificationSettings(notificationSettings.copy(riskEnabled = it)) }
                        )
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("Automation Lifecycle Events", style = MaterialTheme.typography.bodySmall, color = TextPrimary)
                        Switch(
                            checked = notificationSettings.automationsEnabled,
                            enabled = notificationSettings.enabled,
                            onCheckedChange = { viewModel.updateNotificationSettings(notificationSettings.copy(automationsEnabled = it)) }
                        )
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("4-Hour Account Equity Reports", style = MaterialTheme.typography.bodySmall, color = TextPrimary)
                        Switch(
                            checked = notificationSettings.equity4hEnabled,
                            enabled = notificationSettings.enabled,
                            onCheckedChange = { viewModel.updateNotificationSettings(notificationSettings.copy(equity4hEnabled = it)) }
                        )
                    }
                }
            }

            // 5. SYSTEM VERSIONS
            OpheliaSectionHeader(title = "System Components")
            OpheliaGlassPanel(modifier = Modifier.fillMaxWidth()) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("Ophelia Mobile Terminal: v1.0.0-Release (Minimal Glass)", style = MaterialTheme.typography.labelSmall, color = TextPrimary)
                    Text("Ophelia Core Trading Engine: v1.0.0-PROD (Deterministic)", style = MaterialTheme.typography.labelSmall, color = TextPrimary)
                    Text("FastAPI Control Plane: v1.0.0 (Asynchronous Daemon)", style = MaterialTheme.typography.labelSmall, color = TextPrimary)
                }
            }

            // 6. LOGOUT ACTION
            OpheliaDangerButton(
                text = "LOGOUT & PURGE LOCAL CREDENTIALS",
                onClick = onLogout,
                modifier = Modifier.fillMaxWidth()
            )

            Spacer(modifier = Modifier.height(OpheliaSpacing.xxl))
        }
    }
}
