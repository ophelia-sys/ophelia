package com.ophelia.app.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
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
import androidx.lifecycle.viewmodel.compose.viewModel
import com.ophelia.app.auth.TokenManager
import com.ophelia.app.models.DashboardPositionSummary
import com.ophelia.app.models.DataProvenance
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.viewmodels.HomeDashboardViewModel
import com.ophelia.app.ui.viewmodels.UiState
import com.ophelia.app.ui.theme.*

@Composable
fun HomeDashboardScreen(
    onLogout: () -> Unit,
    onNavigateToHistory: () -> Unit = {},
    onNavigateToRisk: () -> Unit = {},
    onNavigateToNews: () -> Unit = {},
    onNavigateToActivity: () -> Unit = {},
    onNavigateToSymbol: (String) -> Unit = {}
) {
    val context = LocalContext.current
    val tokenManager = remember { TokenManager(context) }
    
    val viewModel: HomeDashboardViewModel = viewModel(
        factory = object : ViewModelProvider.Factory {
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return HomeDashboardViewModel(tokenManager) as T
            }
        }
    )

    val connectionState by viewModel.connectionState.collectAsState()
    val dashboardState by viewModel.dashboardState.collectAsState()
    var editingPosition by remember { mutableStateOf<DashboardPositionSummary?>(null) }

    if (editingPosition != null) {
        PositionEditDialog(
            position = editingPosition!!,
            onDismiss = { editingPosition = null },
            onSave = { sl, tp, trailing ->
                val req = mutableMapOf<String, Any>()
                if (sl != null) req["stop_loss"] = sl
                if (tp != null) req["take_profit"] = tp
                if (trailing) req["trailing_stop"] = true
                viewModel.editPosition(editingPosition!!.id ?: "", req)
                editingPosition = null
            },
            onPartialClose = { qtyPct ->
                viewModel.partialClosePosition(editingPosition!!.id ?: "", qtyPct)
                editingPosition = null
            },
            onClosePosition = {
                viewModel.closePosition(editingPosition!!.id ?: "")
                editingPosition = null
            }
        )
    }

    Scaffold(
        containerColor = BackgroundCanvas,
        topBar = {
            val statusColor = when (connectionState) {
                "ONLINE" -> BullishGreen
                "DEGRADED" -> WarningAmber
                "CONNECTING" -> TextMuted
                else -> BearishRed
            }
            OpheliaTopBar(
                title = "OPHELIA",
                subtitle = "BingX Perpetual Swap Futures",
                statusText = connectionState,
                statusColor = statusColor,
                onRefresh = { viewModel.fetchDashboard() },
                actions = {
                    IconButton(onClick = onNavigateToActivity) {
                        Icon(
                            imageVector = Icons.Filled.Notifications,
                            contentDescription = "Activity Center",
                            tint = TextSecondary,
                            modifier = Modifier.size(22.dp)
                        )
                    }
                }
            )
        }
    ) { padding ->
        when (dashboardState) {
            is UiState.Loading -> {
                OpheliaLoadingState(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding),
                    message = "Connecting to live terminal..."
                )
            }
            is UiState.Error -> {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding)
                        .padding(horizontal = OpheliaSpacing.screenHorizontal),
                    contentAlignment = Alignment.Center
                ) {
                    OpheliaErrorState(
                        message = (dashboardState as UiState.Error).message,
                        onRetry = { viewModel.fetchDashboard() }
                    )
                }
            }
            is UiState.Success -> {
                val data = (dashboardState as UiState.Success).data
                val openPositions = if (data.positions.isNotEmpty()) data.positions else (if (data.position != null) listOf(data.position) else emptyList())

                LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding)
                        .padding(horizontal = OpheliaSpacing.screenHorizontal),
                    verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.md)
                ) {
                    item { Spacer(modifier = Modifier.height(OpheliaSpacing.xs)) }

                    // 0. SYSTEM HEALTH & MODE BANNER (SHADOW TRADING & SESSIONS)
                    item {
                        OpheliaGlassCard(
                            level = GlassLevel.L1,
                            modifier = Modifier.fillMaxWidth(),
                            borderColor = if (data.health.mode.equals("LIVE", ignoreCase = true)) WarningAmber else AccentBlue
                        ) {
                            Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    OpheliaStatusBadge(
                                        status = "TRADING MODE: ${data.health.mode.uppercase()}",
                                        color = if (data.health.mode.equals("LIVE", ignoreCase = true)) WarningAmber else AccentBlue,
                                        showDot = true
                                    )
                                    OpheliaStatusBadge(
                                        status = "ENGINE: ${data.health.core ?: data.health.coreEngine ?: "RUNNING"}",
                                        color = BullishGreen,
                                        showDot = false
                                    )
                                }
                                OpheliaDivider()
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    OpheliaMetric(
                                        label = "Market Data",
                                        value = data.health.marketData ?: "CONNECTED",
                                        valueColor = BullishGreen
                                    )
                                    OpheliaMetric(
                                        label = "BingX Auth",
                                        value = data.health.bingx ?: "AUTHENTICATED",
                                        valueColor = BullishGreen
                                    )
                                    OpheliaMetric(
                                        label = "Active Autos",
                                        value = "${data.health.activeAutomations ?: 0}",
                                        valueColor = TextPrimary
                                    )
                                    OpheliaMetric(
                                        label = "OCCUPIED SLOTS",
                                        value = "${openPositions.size} / ${data.risk.positionsMax} MAX",
                                        valueColor = if (openPositions.size >= data.risk.positionsMax) WarningAmber else BullishGreen
                                    )
                                }

                                val sessionList = data.health.sessions?.sessionsActiveUtc?.ifEmpty { listOf("ACTIVE") } ?: listOf("ACTIVE")
                                val isBlackout = data.health.sessions?.blackoutNewEntries == true
                                val resetTime = data.health.sessions?.nextDailyResetIst ?: "05:30 IST"
                                val dataAge = data.health.dataHealth?.dataAgeMin?.let { String.format(java.util.Locale.US, "%.1fm", it) } ?: "<1m"
                                val rowCount = data.health.dataHealth?.rows ?: 5760

                                OpheliaDivider()
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(
                                        text = "SESSION: ${sessionList.joinToString(", ")}",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = TextSecondary
                                    )
                                    if (isBlackout) {
                                        OpheliaStatusBadge(status = "BLACKOUT: ACTIVE", color = BearishRed, showDot = true)
                                    } else {
                                        OpheliaStatusBadge(status = "ENTRIES: OPEN", color = BullishGreen, showDot = false)
                                    }
                                    Text(
                                        text = "RESET: $resetTime",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = TextMuted
                                    )
                                    Text(
                                        text = "DATA: $dataAge",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = TextMuted
                                    )
                                }
                            }
                        }
                    }

                    // 1. PRIMARY ACCOUNT OVERVIEW PANEL
                    item {
                        OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.fillMaxWidth()) {
                            Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.Top
                                ) {
                                    Column {
                                        Row(
                                            verticalAlignment = Alignment.CenterVertically,
                                            horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)
                                        ) {
                                            Text(
                                                text = "TOTAL EQUITY (USDT)",
                                                style = MaterialTheme.typography.labelSmall,
                                                color = TextSecondary,
                                                letterSpacing = 0.6.sp
                                            )
                                            val eqProv = DataProvenance.fromString(data.account.provenance ?: data.provenance)
                                            OpheliaStatusBadge(
                                                status = eqProv.displayLabel,
                                                color = if (eqProv == DataProvenance.LIVE_BINGX) BullishGreen else AccentBlue,
                                                showDot = true
                                            )
                                        }
                                        Text(
                                            text = "$${data.account.totalEquity}",
                                            style = MaterialTheme.typography.displayLarge,
                                            fontWeight = FontWeight.Bold,
                                            color = TextPrimary
                                        )
                                    }
                                    val upnlColor = if (data.account.unrealizedPnl >= 0) BullishGreen else BearishRed
                                    Column(horizontalAlignment = Alignment.End) {
                                        Text(
                                            text = "UNREALIZED PNL",
                                            style = MaterialTheme.typography.labelSmall,
                                            color = TextSecondary
                                        )
                                        Text(
                                            text = "${if (data.account.unrealizedPnl >= 0) "+" else ""}$${data.account.unrealizedPnl}",
                                            style = TabularNumberLargeStyle,
                                            color = upnlColor
                                        )
                                    }
                                }

                                OpheliaDivider()

                                // Margin & Balance Sub-Grid
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    OpheliaMetric(
                                        label = "Available",
                                        value = "$${data.account.availableMargin}",
                                        valueColor = BullishGreen
                                    )
                                    OpheliaMetric(
                                        label = "Ophelia Used",
                                        value = "$${data.account.opheliaUsed}",
                                        valueColor = TextPrimary
                                    )
                                    if (data.capacity != null) {
                                        OpheliaMetric(
                                            label = "Allocatable",
                                            value = "$${data.capacity.allocatableRemaining}",
                                            valueColor = AccentBlue
                                        )
                                    } else {
                                        OpheliaMetric(
                                            label = "Wallet",
                                            value = "$${data.account.walletBalance}",
                                            valueColor = TextSecondary
                                        )
                                    }
                                }
                            }
                        }
                    }

                    // 2. OPEN POSITIONS SECTION (Max Concurrent Trades Enforced)
                    item {
                        OpheliaSectionHeader(
                            title = "Active Positions",
                            badgeText = "${openPositions.size}/${data.risk.positionsMax} SLOTS",
                            actionText = "RECONCILE",
                            onActionClick = { viewModel.reconcilePositions() }
                        )
                    }

                    if (openPositions.isNotEmpty()) {
                        items(openPositions) { pos ->
                            PositionCard(
                                position = pos,
                                onManage = { editingPosition = pos },
                                onSymbolClick = { onNavigateToSymbol(pos.symbol) }
                            )
                        }
                    } else {
                        item {
                            OpheliaGlassPanel(modifier = Modifier.fillMaxWidth()) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(
                                        text = "NO OPEN POSITIONS",
                                        style = MaterialTheme.typography.labelMedium,
                                        fontWeight = FontWeight.SemiBold,
                                        color = TextSecondary
                                    )
                                    Row(
                                        verticalAlignment = Alignment.CenterVertically,
                                        horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)
                                    ) {
                                        val posProv = DataProvenance.fromString(data.positions.firstOrNull()?.provenance ?: DataProvenance.SHADOW_PAPER.rawValue)
                                        OpheliaStatusBadge(
                                            status = posProv.displayLabel,
                                            color = if (posProv == DataProvenance.LIVE_BINGX) BullishGreen else AccentBlue,
                                            showDot = false
                                        )
                                        OpheliaStatusBadge(
                                            status = "0/${data.risk.positionsMax} SLOTS",
                                            color = TextSecondary,
                                            showDot = false
                                        )
                                    }
                                }
                            }
                        }
                    }

                    // 3. PERFORMANCE BREAKDOWN
                    item {
                        OpheliaSectionHeader(title = "Performance")
                        OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.fillMaxWidth()) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                PerformanceMetric(label = "Today", pct = data.performance.todayPct)
                                PerformanceMetric(label = "Yesterday", pct = data.performance.yesterdayPct)
                                PerformanceMetric(label = "Week", pct = data.performance.weekPct)
                                PerformanceMetric(label = "Month", pct = data.performance.monthPct)
                            }
                        }
                    }

                    // 4. TODAY'S STATISTICS & RISK SUMMARY
                    item {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
                        ) {
                            // Today's Stats Card
                            val today = data.today
                            val realized = today?.realizedPnl ?: 0.0
                            OpheliaGlassCard(
                                level = GlassLevel.L1,
                                modifier = Modifier.weight(1f)
                            ) {
                                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Text(
                                            text = "TODAY'S STATS",
                                            style = MaterialTheme.typography.labelSmall,
                                            color = TextSecondary
                                        )
                                        val activeNamespace = today?.namespace ?: today?.mode ?: "LIVE"
                                        val isLive = activeNamespace.equals("LIVE", ignoreCase = true)
                                        OpheliaStatusBadge(
                                            status = activeNamespace.uppercase(),
                                            color = if (isLive) BullishGreen else AccentBlue,
                                            showDot = false
                                        )
                                    }
                                    Text(
                                        text = "${if (realized >= 0) "+" else ""}$$realized",
                                        style = TabularNumberLargeStyle,
                                        color = if (realized >= 0) BullishGreen else BearishRed
                                    )
                                    Text(
                                        text = "Win: ${today?.winRate ?: 0.0}% (${today?.wins ?: 0}W / ${today?.losses ?: 0}L)",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = TextPrimary
                                    )
                                    Text(
                                        text = "Fees: $${today?.fees ?: 0.0}",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = TextMuted
                                    )
                                }
                            }

                            // Risk Status Card
                            OpheliaGlassCard(
                                level = GlassLevel.L1,
                                modifier = Modifier
                                    .weight(1f)
                                    .clickable { onNavigateToRisk() }
                            ) {
                                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Text(
                                            text = "RISK CENTER",
                                            style = MaterialTheme.typography.labelSmall,
                                            color = TextSecondary
                                        )
                                        OpheliaStatusBadge(status = data.risk.status)
                                    }
                                    Text(
                                        text = "Margin: ${data.risk.marginPct}%",
                                        style = TabularNumberLargeStyle,
                                        color = if (data.risk.marginPct > 80) BearishRed else if (data.risk.marginPct > 50) WarningAmber else BullishGreen
                                    )
                                    Text(
                                        text = "Avail: $${data.risk.available}",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = TextPrimary
                                    )
                                    Text(
                                        text = "Slots: ${data.risk.positionsCount}/${data.risk.positionsMax} Active",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = TextMuted
                                    )
                                }
                            }
                        }
                    }

                    // 5. RECENT EXECUTED TRADES
                    item {
                        OpheliaSectionHeader(
                            title = "Recent Trades",
                            actionText = "VIEW ALL",
                            onActionClick = onNavigateToHistory
                        )
                    }

                    if (data.lastTrades.isEmpty()) {
                        item {
                            OpheliaGlassPanel(modifier = Modifier.fillMaxWidth()) {
                                Text(
                                    text = "No recent trades recorded.",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = TextSecondary
                                )
                            }
                        }
                    } else {
                        items(data.lastTrades) { trade ->
                            val isProfit = trade.realizedPnl >= 0
                            OpheliaGlassCard(level = GlassLevel.L2, modifier = Modifier.fillMaxWidth()) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Row(
                                        verticalAlignment = Alignment.CenterVertically,
                                        horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
                                    ) {
                                        OpheliaStatusBadge(
                                            status = trade.direction,
                                            color = if (trade.direction == "LONG") BullishGreen else BearishRed
                                        )
                                        val trProv = DataProvenance.fromString(trade.provenance)
                                        OpheliaStatusBadge(
                                            status = trProv.displayLabel,
                                            color = if (trProv == DataProvenance.LIVE_BINGX) BullishGreen else AccentBlue,
                                            showDot = false
                                        )
                                        Column {
                                            Text(
                                                text = trade.symbol,
                                                style = MaterialTheme.typography.bodyMedium,
                                                fontWeight = FontWeight.Bold,
                                                color = TextPrimary
                                            )
                                            Text(
                                                text = "In: $${trade.entry} | Out: $${trade.exitPrice}",
                                                style = MaterialTheme.typography.labelSmall,
                                                color = TextSecondary
                                            )
                                        }
                                    }
                                    Column(horizontalAlignment = Alignment.End) {
                                        Text(
                                            text = "${if (isProfit) "+" else ""}$${trade.realizedPnl}",
                                            style = TabularNumberStyle,
                                            color = if (isProfit) BullishGreen else BearishRed
                                        )
                                        Text(
                                            text = "${if (isProfit) "+" else ""}${trade.pnlPct}%",
                                            style = MaterialTheme.typography.labelSmall,
                                            color = if (isProfit) BullishGreen else BearishRed
                                        )
                                    }
                                }
                            }
                        }
                    }

                    item { Spacer(modifier = Modifier.height(OpheliaSpacing.lg)) }
                }
            }
            else -> {}
        }
    }
}

@Composable
private fun PositionCard(
    position: DashboardPositionSummary,
    onManage: () -> Unit,
    onSymbolClick: () -> Unit
) {
    val isProfit = position.unrealizedPnl >= 0
    val pnlColor = if (isProfit) BullishGreen else BearishRed
    val isManual = position.source == "BINGX MANUAL" || position.managementStatus == "EXTERNAL POSITION"
    val isDesynced = position.managementStatus == "DESYNCED" ||
            position.status?.contains("RECONCIL", ignoreCase = true) == true ||
            position.managementStatus?.contains("RECONCIL", ignoreCase = true) == true

    OpheliaGlassCard(
        level = GlassLevel.L1,
        modifier = Modifier.fillMaxWidth(),
        borderColor = if (isDesynced) BearishRed else (if (isProfit) BullishGreenBorder else BearishRedBorder)
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
            // Header: Symbol, Direction, Source Tag, Manage Button
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
                        text = position.symbol,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = TextPrimary,
                        modifier = Modifier.clickable(onClick = onSymbolClick)
                    )
                    OpheliaStatusBadge(
                        status = position.direction,
                        color = if (position.direction == "LONG") BullishGreen else BearishRed
                    )
                    val pProv = DataProvenance.fromString(position.provenance)
                    OpheliaStatusBadge(
                        status = pProv.displayLabel,
                        color = if (pProv == DataProvenance.LIVE_BINGX) BullishGreen else AccentBlue,
                        showDot = false
                    )
                    if (isManual) {
                        OpheliaStatusBadge(status = "MANUAL", color = WarningAmber, showDot = false)
                    }
                }
                OpheliaOutlinedButton(
                    text = "MANAGE",
                    onClick = onManage
                )
            }

            // Reconciliation Alert Banner
            if (isDesynced) {
                OpheliaGlassPanel(
                    modifier = Modifier.fillMaxWidth(),
                    borderColor = BearishRed
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(horizontal = 4.dp, vertical = 2.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "[LOCAL ONLY - RECONCILIATION_REQUIRED]",
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold,
                            color = BearishRed
                        )
                        Text(
                            text = "DESYNCED",
                            style = MaterialTheme.typography.labelSmall,
                            color = BearishRed
                        )
                    }
                }
            }

            OpheliaDivider()

            // Metrics: Entry, Mark, Margin, PnL
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                OpheliaMetric(label = "Entry", value = "$${position.entry}")
                OpheliaMetric(label = "Mark", value = "$${position.currentPrice}")
                OpheliaMetric(label = "Margin", value = "$${position.margin} (${position.leverage.toInt()}x)")
                OpheliaMetric(
                    label = "Unrealized PnL",
                    value = "$${position.unrealizedPnl}",
                    valueColor = pnlColor,
                    subValue = "${if (isProfit) "+" else ""}${position.unrealizedPnlPct}%",
                    subValueColor = pnlColor
                )
            }

            // Protection State (Stops, Targets, Size)
            val sizeStr = position.qty?.let { String.format(java.util.Locale.US, "%.4f", it) }
            val stopsStr = if (position.stops.isNotEmpty()) {
                position.stops.joinToString(", ") { item ->
                    when (item) {
                        is Number -> "$${item.toDouble()}"
                        is Map<*, *> -> "$${item["value"] ?: item["price"] ?: item}"
                        else -> "$$item"
                    }
                }
            } else null
            val targetsStr = if (position.targets.isNotEmpty()) {
                position.targets.joinToString(", ") { item ->
                    when (item) {
                        is Number -> "$${item.toDouble()}"
                        is Map<*, *> -> "$${item["value"] ?: item["price"] ?: item}"
                        else -> "$$item"
                    }
                }
            } else null
            val trailStr = position.trailingPct?.let { "${it}%" }

            if (sizeStr != null || stopsStr != null || targetsStr != null || trailStr != null) {
                OpheliaDivider()
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    if (sizeStr != null) {
                        Text(
                            text = "SIZE: $sizeStr",
                            style = MaterialTheme.typography.labelSmall,
                            color = TextSecondary
                        )
                    }
                    val protList = mutableListOf<String>()
                    if (stopsStr != null) protList.add("SL: $stopsStr")
                    if (targetsStr != null) protList.add("TP: $targetsStr")
                    if (trailStr != null) protList.add("Trail: $trailStr")
                    Text(
                        text = if (protList.isNotEmpty()) protList.joinToString(" | ") else "PROTECTION: NONE",
                        style = MaterialTheme.typography.labelSmall,
                        color = AccentTeal
                    )
                }
            }
        }
    }
}

@Composable
private fun PerformanceMetric(label: String, pct: Double) {
    val isPositive = pct >= 0
    val color = if (isPositive) BullishGreen else BearishRed
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            text = label.uppercase(),
            style = MaterialTheme.typography.labelSmall,
            color = TextSecondary
        )
        Spacer(modifier = Modifier.height(2.dp))
        Text(
            text = "${if (isPositive) "+" else ""}${pct}%",
            style = TabularNumberStyle,
            color = color
        )
    }
}
