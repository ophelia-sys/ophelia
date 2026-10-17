package com.ophelia.app.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import com.ophelia.app.models.Position
import com.ophelia.app.models.TradeHistoryItem
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.viewmodels.UiState
import com.ophelia.app.ui.theme.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.*

class PositionHistoryViewModel(private val tokenManager: TokenManager) : ViewModel() {
    private val _selectedTab = MutableStateFlow(0) // 0: Positions & Orders, 1: Past History
    val selectedTab = _selectedTab.asStateFlow()

    private val _positionsState = MutableStateFlow<UiState<List<Position>>>(UiState.Loading)
    val positionsState = _positionsState.asStateFlow()

    private val _historyState = MutableStateFlow<UiState<List<TradeHistoryItem>>>(UiState.Loading)
    val historyState = _historyState.asStateFlow()

    private val _filterMode = MutableStateFlow<String?>(null)
    val filterMode = _filterMode.asStateFlow()

    init {
        refreshAll()
    }

    fun setSelectedTab(tab: Int) {
        _selectedTab.value = tab
    }

    fun setFilterMode(mode: String?) {
        _filterMode.value = mode
        fetchHistory()
    }

    fun refreshAll() {
        fetchPositions()
        fetchHistory()
    }

    fun fetchPositions() {
        viewModelScope.launch {
            _positionsState.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val res = api.getPositions()
                _positionsState.value = UiState.Success(res.positions)
            } catch (e: Exception) {
                _positionsState.value = UiState.Error(e.message ?: "Failed to load open positions")
            }
        }
    }

    fun fetchHistory() {
        viewModelScope.launch {
            _historyState.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val res = api.getTradeHistory(page = 1, limit = 50, mode = _filterMode.value)
                _historyState.value = UiState.Success(res.trades)
            } catch (e: Exception) {
                _historyState.value = UiState.Error(e.message ?: "Failed to load trade history")
            }
        }
    }

    fun reconcilePositions() {
        viewModelScope.launch {
            try {
                RetrofitClient.apiService?.reconcilePositions()
                fetchPositions()
            } catch (e: Exception) {
                // Keep current state
            }
        }
    }
}

@Composable
fun TradeHistoryScreen(
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val tokenManager = remember { TokenManager(context) }
    
    val viewModel: PositionHistoryViewModel = viewModel(
        factory = object : ViewModelProvider.Factory {
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return PositionHistoryViewModel(tokenManager) as T
            }
        }
    )

    val selectedTab by viewModel.selectedTab.collectAsState()
    val positionsState by viewModel.positionsState.collectAsState()
    val historyState by viewModel.historyState.collectAsState()
    val filterMode by viewModel.filterMode.collectAsState()

    Scaffold(
        containerColor = BackgroundCanvas,
        topBar = {
            OpheliaTopBar(
                title = "POSITION / HISTORY",
                subtitle = "Active Execution Ledger & Historical Fills",
                onBack = onBack,
                onRefresh = { viewModel.refreshAll() }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = OpheliaSpacing.screenHorizontal),
            verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.md)
        ) {
            Spacer(modifier = Modifier.height(OpheliaSpacing.xs))

            // Primary Navigation Tabs
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
            ) {
                OpheliaChip(
                    text = "POSITIONS & ORDERS",
                    isSelected = selectedTab == 0,
                    onClick = { viewModel.setSelectedTab(0) },
                    modifier = Modifier.weight(1f)
                )
                OpheliaChip(
                    text = "PAST TRADES & ORDERS",
                    isSelected = selectedTab == 1,
                    onClick = { viewModel.setSelectedTab(1) },
                    modifier = Modifier.weight(1f)
                )
            }

            if (selectedTab == 0) {
                // ==========================================
                // TAB 0: CURRENT POSITIONS & OPEN ORDERS
                // ==========================================
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "ACTIVE PERPETUAL POSITIONS",
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.Bold,
                        color = TextSecondary
                    )
                    OpheliaOutlinedButton(
                        text = "RECONCILE",
                        onClick = { viewModel.reconcilePositions() }
                    )
                }

                when (val state = positionsState) {
                    is UiState.Loading -> {
                        OpheliaLoadingState(message = "Querying live positions & working stops...")
                    }
                    is UiState.Error -> {
                        OpheliaErrorState(
                            message = state.message,
                            onRetry = { viewModel.fetchPositions() }
                        )
                    }
                    is UiState.Success -> {
                        val positions = state.data
                        if (positions.isEmpty()) {
                            OpheliaGlassCard(
                                level = GlassLevel.L1,
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Column(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(OpheliaSpacing.lg),
                                    horizontalAlignment = Alignment.CenterHorizontally,
                                    verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)
                                ) {
                                    Text(
                                        text = "NO ACTIVE POSITIONS OR OPEN ORDERS",
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.Bold,
                                        color = TextPrimary
                                    )
                                    Text(
                                        text = "Execution slots available. Automations are monitoring breakout & retest conditions.",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = TextSecondary
                                    )
                                }
                            }
                        } else {
                            LazyColumn(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)) {
                                items(positions) { pos ->
                                    val isProfit = pos.unrealizedPnl >= 0
                                    val pnlColor = if (isProfit) BullishGreen else BearishRed
                                    val isDesynced = pos.managementStatus == "DESYNCED"

                                    OpheliaGlassCard(
                                        level = GlassLevel.L1,
                                        modifier = Modifier.fillMaxWidth(),
                                        borderColor = if (isDesynced) BearishRed else (if (isProfit) BullishGreenBorder else BearishRedBorder)
                                    ) {
                                        Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                                            // Header
                                            Row(
                                                modifier = Modifier.fillMaxWidth(),
                                                horizontalArrangement = Arrangement.SpaceBetween,
                                                verticalAlignment = Alignment.CenterVertically
                                            ) {
                                                Row(
                                                    verticalAlignment = Alignment.CenterVertically,
                                                    horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)
                                                ) {
                                                    Text(
                                                        text = pos.symbol,
                                                        style = MaterialTheme.typography.titleMedium,
                                                        fontWeight = FontWeight.Bold,
                                                        color = TextPrimary
                                                    )
                                                    val posSide = pos.side ?: "LONG"
                                                    OpheliaStatusBadge(
                                                        status = posSide,
                                                        color = if (posSide.uppercase() == "LONG") BullishGreen else BearishRed
                                                    )
                                                    OpheliaStatusBadge(
                                                        status = pos.source ?: "SHADOW",
                                                        color = if (pos.source == "LIVE_BINGX") BullishGreen else AccentBlue,
                                                        showDot = false
                                                    )
                                                }
                                                Text(
                                                    text = "${if (isProfit) "+" else ""}$${pos.unrealizedPnl} (${pos.unrealizedPnlPct ?: 0.0}%)",
                                                    style = TabularNumberLargeStyle,
                                                    color = pnlColor
                                                )
                                            }

                                            OpheliaDivider()

                                            // Row 1: Entry, Current Mark, Margin & Leverage
                                            Row(
                                                modifier = Modifier.fillMaxWidth(),
                                                horizontalArrangement = Arrangement.SpaceBetween
                                            ) {
                                                OpheliaMetric(label = "Entry Price", value = "$${pos.entry}")
                                                OpheliaMetric(label = "Mark Price", value = "$${pos.currentPrice}")
                                                OpheliaMetric(label = "Margin", value = "$${pos.margin} (${pos.leverage.toInt()}x)")
                                                OpheliaMetric(
                                                    label = "Size",
                                                    value = "${pos.remainingQty ?: pos.qty ?: 0.0} contracts"
                                                )
                                            }

                                            // Row 2: Stops, Targets, Trailing
                                            Row(
                                                modifier = Modifier.fillMaxWidth(),
                                                horizontalArrangement = Arrangement.SpaceBetween
                                            ) {
                                                OpheliaMetric(
                                                    label = "Active SL",
                                                    value = pos.activeStop?.let { "$${it}" } ?: "0.7% STRUCTURAL",
                                                    valueColor = BearishRed
                                                )
                                                OpheliaMetric(
                                                    label = "Liquidation",
                                                    value = pos.liquidationPrice?.let { "$${it}" } ?: "SAFE / NONE",
                                                    valueColor = WarningAmber
                                                )
                                                val trailingVal = pos.trailingPct?.toString()?.let { "$it% (1m PEAK)" } ?: "CAUSAL 1M"
                                                OpheliaMetric(
                                                    label = "Trailing",
                                                    value = trailingVal,
                                                    valueColor = AccentBlue
                                                )
                                                OpheliaMetric(
                                                    label = "Engine",
                                                    value = pos.strategy ?: "OPHELIA_COMPOSITE"
                                                )
                                            }
                                        }
                                    }
                                }
                                item { Spacer(modifier = Modifier.height(OpheliaSpacing.xxl)) }
                            }
                        }
                    }
                    else -> {}
                }
            } else {
                // ==========================================
                // TAB 1: PAST TRADES & CLOSED ORDERS
                // ==========================================
                // Mode Filter Chips
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
                ) {
                    OpheliaChip(
                        text = "ALL TRADES",
                        isSelected = filterMode == null,
                        onClick = { viewModel.setFilterMode(null) },
                        modifier = Modifier.weight(1f)
                    )
                    OpheliaChip(
                        text = "SHADOW",
                        isSelected = filterMode == "SHADOW",
                        onClick = { viewModel.setFilterMode("SHADOW") },
                        modifier = Modifier.weight(1f)
                    )
                    OpheliaChip(
                        text = "LIVE",
                        isSelected = filterMode == "LIVE",
                        onClick = { viewModel.setFilterMode("LIVE") },
                        modifier = Modifier.weight(1f)
                    )
                }

                when (val state = historyState) {
                    is UiState.Loading -> {
                        OpheliaLoadingState(message = "Loading historical executions & fills...")
                    }
                    is UiState.Error -> {
                        OpheliaErrorState(
                            message = state.message,
                            onRetry = { viewModel.fetchHistory() }
                        )
                    }
                    is UiState.Success -> {
                        val trades = state.data
                        if (trades.isEmpty()) {
                            OpheliaGlassCard(
                                level = GlassLevel.L1,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = OpheliaSpacing.md)
                            ) {
                                Column(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(OpheliaSpacing.lg),
                                    horizontalAlignment = Alignment.CenterHorizontally,
                                    verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)
                                ) {
                                    val emptyTitle = when (filterMode) {
                                        "LIVE" -> "NO LIVE TRADES RECORDED"
                                        "SHADOW" -> "NO SHADOW TRADES RECORDED"
                                        else -> "NO TRADES RECORDED"
                                    }
                                    val emptySubtitle = when (filterMode) {
                                        "LIVE" -> "The system operates in SHADOW mode by default. Real money executions require explicit live arming."
                                        "SHADOW" -> "No shadow executions recorded for the selected filter."
                                        else -> "No historical executions or fills recorded."
                                    }
                                    Text(
                                        text = emptyTitle,
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.Bold,
                                        color = TextPrimary
                                    )
                                    Text(
                                        text = emptySubtitle,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = TextSecondary,
                                        textAlign = androidx.compose.ui.text.style.TextAlign.Center
                                    )
                                }
                            }
                        } else {
                            LazyColumn(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)) {
                                items(trades) { t ->
                                    val isWin = (t.realizedPnl ?: 0.0) >= 0
                                    val pnlColor = if (isWin) BullishGreen else BearishRed
                                    val dateStr = if (t.openedMs > 0) {
                                        SimpleDateFormat("MMM dd, HH:mm", Locale.getDefault()).format(Date(t.openedMs))
                                    } else ""
                                    val durationStr = if ((t.durationSec ?: 0L) > 0) {
                                        val m = (t.durationSec!! / 60)
                                        val s = (t.durationSec!! % 60)
                                        if (m >= 60) "${m / 60}h ${m % 60}m" else "${m}m ${s}s"
                                    } else "< 1m"

                                    OpheliaGlassCard(
                                        level = GlassLevel.L1,
                                        modifier = Modifier.fillMaxWidth(),
                                        borderColor = if (isWin) BullishGreenBorder else BearishRedBorder
                                    ) {
                                        Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                                            Row(
                                                modifier = Modifier.fillMaxWidth(),
                                                horizontalArrangement = Arrangement.SpaceBetween,
                                                verticalAlignment = Alignment.CenterVertically
                                            ) {
                                                Row(
                                                    verticalAlignment = Alignment.CenterVertically,
                                                    horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)
                                                ) {
                                                    Text(
                                                        text = t.symbol,
                                                        style = MaterialTheme.typography.titleMedium,
                                                        fontWeight = FontWeight.Bold,
                                                        color = TextPrimary
                                                    )
                                                    OpheliaStatusBadge(
                                                        status = t.direction,
                                                        color = if (t.direction == "LONG") BullishGreen else BearishRed
                                                    )
                                                    OpheliaStatusBadge(
                                                        status = t.mode,
                                                        color = if (t.mode == "LIVE") BullishGreen else WarningAmber,
                                                        showDot = false
                                                    )
                                                }
                                                Text(
                                                    text = "${if (isWin) "+" else ""}$${t.realizedPnl ?: 0.0} (${t.pnlPct}%)",
                                                    style = TabularNumberLargeStyle,
                                                    color = pnlColor
                                                )
                                            }

                                            OpheliaDivider()

                                            // Row 1: Entry, Exit, Leverage & Margin, Time
                                            Row(
                                                modifier = Modifier.fillMaxWidth(),
                                                horizontalArrangement = Arrangement.SpaceBetween
                                            ) {
                                                OpheliaMetric(label = "Entry", value = "$${t.entry}")
                                                OpheliaMetric(label = "Exit", value = "$${t.exitPrice ?: t.entry}")
                                                OpheliaMetric(label = "Margin", value = "$${t.margin ?: 0.0} (${t.leverage.toInt()}x)")
                                                OpheliaMetric(label = "Date", value = dateStr)
                                            }

                                            // Row 2: Duration, Fees, Funding, Exit Reason
                                            Row(
                                                modifier = Modifier.fillMaxWidth(),
                                                horizontalArrangement = Arrangement.SpaceBetween
                                            ) {
                                                OpheliaMetric(label = "Duration", value = durationStr)
                                                OpheliaMetric(label = "Fees", value = "$${t.fees ?: 0.0}")
                                                OpheliaMetric(label = "Funding", value = "$${t.funding ?: 0.0}")
                                                OpheliaMetric(
                                                    label = "Exit Reason",
                                                    value = t.reasonClose?.takeIf { it.isNotBlank() } ?: "TAKE_PROFIT / TRAILING",
                                                    valueColor = if (isWin) BullishGreen else BearishRed
                                                )
                                            }
                                        }
                                    }
                                }
                                item { Spacer(modifier = Modifier.height(OpheliaSpacing.xxl)) }
                            }
                        }
                    }
                    else -> {}
                }
            }
        }
    }
}
