package com.ophelia.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
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
import com.ophelia.app.models.DashboardResponse
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.viewmodels.UiState
import com.ophelia.app.ui.theme.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class RiskViewModel(private val tokenManager: TokenManager) : ViewModel() {
    private val _dashboardState = MutableStateFlow<UiState<DashboardResponse>>(UiState.Loading)
    val dashboardState = _dashboardState.asStateFlow()

    init {
        fetchRisk()
    }

    fun fetchRisk() {
        viewModelScope.launch {
            _dashboardState.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val res = api.getDashboard()
                _dashboardState.value = UiState.Success(res)
            } catch (e: Exception) {
                _dashboardState.value = UiState.Error(e.message ?: "Failed to load risk telemetry")
            }
        }
    }

    fun pauseAllAutomations(onDone: () -> Unit = {}) {
        viewModelScope.launch {
            try {
                RetrofitClient.apiService?.pauseAllAutomations()
                fetchRisk()
                onDone()
            } catch (e: Exception) { }
        }
    }

    fun emergencyCloseAll(onDone: () -> Unit = {}) {
        viewModelScope.launch {
            try {
                RetrofitClient.apiService?.emergencyCloseAll()
                fetchRisk()
                onDone()
            } catch (e: Exception) { }
        }
    }
}

@Composable
fun RiskScreen(
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val tokenManager = remember { TokenManager(context) }

    val viewModel: RiskViewModel = viewModel(
        factory = object : ViewModelProvider.Factory {
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return RiskViewModel(tokenManager) as T
            }
        }
    )

    val dashboardState by viewModel.dashboardState.collectAsState()
    var showPauseAllConfirm by remember { mutableStateOf(false) }
    var showEmergencyCloseConfirm by remember { mutableStateOf(false) }

    if (showPauseAllConfirm) {
        OpheliaDialog(
            onDismissRequest = { showPauseAllConfirm = false },
            title = "PAUSE ALL AUTOMATIONS",
            subtitle = "Suspend signal evaluation",
            badgeText = "CAUTION",
            badgeColor = WarningAmber,
            confirmButton = {
                OpheliaButton(
                    text = "YES, PAUSE ALL",
                    onClick = {
                        showPauseAllConfirm = false
                        viewModel.pauseAllAutomations()
                    }
                )
            },
            dismissButton = {
                OpheliaOutlinedButton(
                    text = "CANCEL",
                    onClick = { showPauseAllConfirm = false }
                )
            }
        ) {
            Text(
                text = "Are you sure you want to pause all active strategy automations? No new trade signals will be evaluated.",
                style = MaterialTheme.typography.bodyMedium,
                color = TextPrimary
            )
        }
    }

    if (showEmergencyCloseConfirm) {
        OpheliaDialog(
            onDismissRequest = { showEmergencyCloseConfirm = false },
            title = "EMERGENCY MARKET FLATTEN",
            subtitle = "Immediate liquidation of all positions",
            badgeText = "CRITICAL",
            badgeColor = BearishRed,
            confirmButton = {
                OpheliaDangerButton(
                    text = "EXECUTE FLATTEN ALL",
                    onClick = {
                        showEmergencyCloseConfirm = false
                        viewModel.emergencyCloseAll()
                    }
                )
            },
            dismissButton = {
                OpheliaOutlinedButton(
                    text = "CANCEL",
                    onClick = { showEmergencyCloseConfirm = false }
                )
            }
        ) {
            Text(
                text = "DANGER: Are you sure you want to market close ALL active positions immediately?",
                style = MaterialTheme.typography.bodyMedium,
                color = TextPrimary
            )
            Spacer(modifier = Modifier.height(OpheliaSpacing.sm))
            Text(
                text = "This sends immediate market exit orders to BingX for all open positions.",
                style = MaterialTheme.typography.bodySmall,
                color = BearishRed
            )
        }
    }

    Scaffold(
        containerColor = BackgroundCanvas,
        topBar = {
            OpheliaTopBar(
                title = "RISK CONTROL CENTER",
                subtitle = "Capital Preservation & Exposure Guards",
                onBack = onBack,
                onRefresh = { viewModel.fetchRisk() }
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

            when (val state = dashboardState) {
                is UiState.Loading -> {
                    OpheliaLoadingState(message = "Evaluating risk telemetry...")
                }
                is UiState.Error -> {
                    OpheliaErrorState(
                        message = state.message,
                        onRetry = { viewModel.fetchRisk() }
                    )
                }
                is UiState.Success -> {
                    val risk = state.data.risk
                    val account = state.data.account
                    val statusColor = if (risk.status == "NORMAL") BullishGreen else WarningAmber

                    // 1. Risk Status Banner Card
                    OpheliaGlassCard(
                        level = GlassLevel.L1,
                        modifier = Modifier.fillMaxWidth(),
                        borderColor = statusColor
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column {
                                Text(
                                    text = "SYSTEM RISK REGIME",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = TextSecondary
                                )
                                Text(
                                    text = risk.status,
                                    style = MaterialTheme.typography.displayMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = statusColor
                                )
                            }
                            OpheliaStatusBadge(
                                status = if (risk.status == "NORMAL") "GUARD ACTIVE" else "CAUTION",
                                color = statusColor
                            )
                        }
                    }

                    // 2. Margin Utilization Gauge Card
                    OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.fillMaxWidth()) {
                        Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                            Text(
                                text = "MARGIN UTILIZATION",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.Bold,
                                color = TextPrimary
                            )
                            LinearProgressIndicator(
                                progress = (risk.marginPct / 100.0).toFloat().coerceIn(0f, 1f),
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(6.dp),
                                color = if (risk.marginPct > 80) BearishRed else BullishGreen,
                                trackColor = GlassSurfaceL1
                            )
                            Spacer(modifier = Modifier.height(2.dp))
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text("Utilized: ${risk.marginPct}%", style = TabularNumberStyle, color = TextPrimary)
                                Text("Available: $${risk.available} USDT", style = TabularNumberStyle, color = BullishGreen)
                            }
                        }
                    }

                    // 3. Position Sizing & Exposure
                    OpheliaSectionHeader(title = "Position Caps & Exposure")
                    OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.fillMaxWidth()) {
                        Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                OpheliaMetric(
                                    label = "Open Positions",
                                    value = "${risk.positionsCount} / ${risk.positionsMax}",
                                    valueColor = if (risk.positionsCount >= risk.positionsMax) WarningAmber else BullishGreen,
                                    subValue = "Strict Limit: ${risk.positionsMax}"
                                )
                                OpheliaMetric(
                                    label = "Ophelia Used",
                                    value = "$${account.opheliaUsed} USDT",
                                    valueColor = TextPrimary
                                )
                                OpheliaMetric(
                                    label = "Total Live Equity",
                                    value = "$${account.totalEquity} USDT",
                                    valueColor = AccentBlue
                                )
                            }
                        }
                    }

                    // 4. Automation Margin Capacity
                    val cap = state.data.capacity
                    if (cap != null) {
                        OpheliaSectionHeader(title = "Automation Allocatable Buffer")
                        OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.fillMaxWidth()) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                OpheliaMetric(label = "Exchange Avail", value = "$${cap.accountAvailable}")
                                OpheliaMetric(label = "Reserved", value = "$${cap.automationReserved}", valueColor = WarningAmber)
                                OpheliaMetric(label = "Allocatable", value = "$${cap.allocatableRemaining}", valueColor = BullishGreen)
                            }
                        }
                    }

                    // 5. Emergency Controls
                    OpheliaSectionHeader(title = "Emergency Circuit Controls")
                    OpheliaGlassCard(
                        level = GlassLevel.L1,
                        modifier = Modifier.fillMaxWidth(),
                        borderColor = BearishRedBorder
                    ) {
                        Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)) {
                            Text(
                                text = "RAPID INTERVENTION PROTOCOLS",
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.Bold,
                                color = BearishRed
                            )
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
                            ) {
                                OpheliaOutlinedButton(
                                    text = "PAUSE ALL AUTO",
                                    onClick = { showPauseAllConfirm = true },
                                    modifier = Modifier.weight(1f),
                                    textColor = WarningAmber
                                )
                                OpheliaDangerButton(
                                    text = "FLATTEN ALL POSITIONS",
                                    onClick = { showEmergencyCloseConfirm = true },
                                    modifier = Modifier.weight(1f)
                                )
                            }
                        }
                    }

                    // 6. Automated Circuit Breakers
                    OpheliaSectionHeader(title = "Active Safety Guardrails")
                    OpheliaGlassPanel(modifier = Modifier.fillMaxWidth()) {
                        Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                            Text("✓ Max Concurrent Trades Limit: ${risk.positionsMax} Positions (Enforced)", style = MaterialTheme.typography.labelSmall, color = TextPrimary)
                            Text("✓ Hard Margin Allocation Limit: 45%", style = MaterialTheme.typography.labelSmall, color = TextPrimary)
                            Text("✓ Entry Blackout Hours: 02:30 - 05:30 IST (Strict Enforcement)", style = MaterialTheme.typography.labelSmall, color = TextPrimary)
                            Text("✓ Fail-Closed Shadow Execution Barrier Active", style = MaterialTheme.typography.labelSmall, color = BullishGreen)
                        }
                    }
                }
                else -> {}
            }

            Spacer(modifier = Modifier.height(OpheliaSpacing.xxl))
        }
    }
}
