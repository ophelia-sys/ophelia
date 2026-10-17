package com.ophelia.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.draw.clip
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
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
import com.ophelia.app.models.Position
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.viewmodels.MarketViewModel
import com.ophelia.app.ui.viewmodels.UiState
import com.ophelia.app.ui.theme.*

@Composable
fun DashboardScreen(
    onLogout: () -> Unit,
    onNavigateToSymbol: (String) -> Unit
) {
    val context = LocalContext.current
    val tokenManager = remember { TokenManager(context) }
    
    val viewModel: MarketViewModel = viewModel(
        factory = object : ViewModelProvider.Factory {
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return MarketViewModel(tokenManager) as T
            }
        }
    )

    val connectionState by viewModel.connectionState.collectAsState()
    val positionsState by viewModel.positionsState.collectAsState()
    val watchlistState by viewModel.watchlistState.collectAsState()
    val snapshots by viewModel.snapshots.collectAsState()
    val contractsState by viewModel.contractsState.collectAsState()

    var showAddDialog by remember { mutableStateOf(false) }
    var newSymbolText by remember { mutableStateOf("") }
    var cryptoExpanded by remember { mutableStateOf(true) }
    var usMarketExpanded by remember { mutableStateOf(true) }
    var goldExpanded by remember { mutableStateOf(true) }

    if (showAddDialog) {
        OpheliaDialog(
            onDismissRequest = { showAddDialog = false },
            title = "ADD SYMBOL TO WATCHLIST",
            subtitle = "BingX Perpetual Swap Futures",
            confirmButton = {
                OpheliaButton(
                    text = "ADD TO WATCHLIST",
                    onClick = {
                        if (newSymbolText.isNotBlank()) {
                            viewModel.addWatchlist(newSymbolText.trim().uppercase())
                            newSymbolText = ""
                            showAddDialog = false
                        }
                    }
                )
            },
            dismissButton = {
                OpheliaOutlinedButton(
                    text = "CANCEL",
                    onClick = { showAddDialog = false }
                )
            }
        ) {
            OutlinedTextField(
                value = newSymbolText,
                onValueChange = { newSymbolText = it },
                label = { Text("Symbol (e.g. BTC-USDT, SOL-USDT)") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = AccentBlue,
                    unfocusedBorderColor = GlassBorderSubtle,
                    focusedTextColor = TextPrimary,
                    unfocusedTextColor = TextPrimary,
                    focusedContainerColor = GlassSurfaceL1,
                    unfocusedContainerColor = GlassSurfaceL1
                )
            )
        }
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
                title = "MARKET RADAR",
                subtitle = "Perpetual Swaps & Regimes",
                statusText = connectionState,
                statusColor = statusColor,
                onRefresh = { viewModel.fetchDashboardData() },
                actions = {
                    IconButton(onClick = { showAddDialog = true }) {
                        Icon(
                            imageVector = Icons.Filled.Add,
                            contentDescription = "Add Symbol",
                            tint = AccentBlue
                        )
                    }
                }
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = OpheliaSpacing.screenHorizontal),
            verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.md)
        ) {
            item { Spacer(modifier = Modifier.height(OpheliaSpacing.xs)) }

            // 1. ACTIVE OPEN POSITIONS (If any)
            when (val posState = positionsState) {
                is UiState.Success -> {
                    val positions = posState.data
                    if (positions.isNotEmpty()) {
                        item {
                            OpheliaSectionHeader(
                                title = "Open Positions",
                                badgeText = "${positions.size} ACTIVE"
                            )
                        }
                        items(positions) { pos ->
                            val isProfit = pos.unrealizedPnl >= 0
                            OpheliaGlassCard(
                                level = GlassLevel.L1,
                                modifier = Modifier.fillMaxWidth(),
                                borderColor = if (isProfit) BullishGreenBorder else BearishRedBorder,
                                onClick = { onNavigateToSymbol(pos.symbol) }
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
                                                text = pos.symbol,
                                                style = MaterialTheme.typography.titleMedium,
                                                fontWeight = FontWeight.Bold,
                                                color = TextPrimary
                                            )
                                            OpheliaStatusBadge(
                                                status = pos.side,
                                                color = if (pos.side == "LONG") BullishGreen else BearishRed
                                            )
                                        }
                                        Text(
                                            text = "${if (isProfit) "+" else ""}$${pos.unrealizedPnl}",
                                            style = TabularNumberStyle,
                                            color = if (isProfit) BullishGreen else BearishRed
                                        )
                                    }
                                    OpheliaDivider()
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween
                                    ) {
                                        OpheliaMetric(label = "Entry", value = "$${pos.entry}")
                                        OpheliaMetric(label = "Mark", value = "$${pos.currentPrice}")
                                        OpheliaMetric(label = "Margin", value = "$${pos.margin} (${pos.leverage.toInt()}x)")
                                        OpheliaMetric(
                                            label = "Stop",
                                            value = if (pos.activeStop != null && pos.activeStop > 0) "$${pos.activeStop}" else "N/A",
                                            subValue = pos.stopType
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
                is UiState.Loading -> {
                    item { OpheliaLoadingState(message = "Checking position state...") }
                }
                else -> {}
            }

            // 2. MARKET DOMAINS (Collapsible: CRYPTO, US MARKET, COMMODITIES / GOLD)
            item {
                OpheliaSectionHeader(
                    title = "Market Radar Universe",
                    actionText = "+ ADD SYMBOL",
                    onActionClick = { showAddDialog = true }
                )
            }

            when (val wlState = watchlistState) {
                is UiState.Loading -> {
                    item { OpheliaLoadingState(message = "Loading market instruments...") }
                }
                is UiState.Error -> {
                    item {
                        OpheliaErrorState(
                            message = wlState.message,
                            onRetry = { viewModel.fetchWatchlist() }
                        )
                    }
                }
                is UiState.Success -> {
                    val allSymbols = wlState.data
                    if (allSymbols.isEmpty()) {
                        item {
                            OpheliaGlassPanel(modifier = Modifier.fillMaxWidth()) {
                                Text(
                                    text = "Watchlist is empty. Tap + ADD SYMBOL to track markets.",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = TextSecondary
                                )
                            }
                        }
                    } else {
                        // Classify into 3 distinct domains
                        val goldSymbols = allSymbols.filter { sym ->
                            sym.contains("GOLD", ignoreCase = true) || sym.contains("XAU", ignoreCase = true) || sym.contains("NCCO", ignoreCase = true)
                        }
                        val usSymbols = allSymbols.filter { sym ->
                            sym.startsWith("US.") || sym in listOf("SPY", "QQQ", "IWM", "AAPL", "NVDA", "MSFT", "TSLA", "AMZN", "META", "GOOGL") ||
                            (!sym.contains("-USDT") && !sym.contains("USDT") && !sym.contains("GOLD") && !sym.contains("XAU"))
                        }
                        val cryptoSymbols = allSymbols.filter { sym ->
                            !goldSymbols.contains(sym) && !usSymbols.contains(sym)
                        }

                        // Domain 1: CRYPTO
                        item {
                            CollapsibleMarketDomainHeader(
                                title = "CRYPTO",
                                count = cryptoSymbols.size,
                                isExpanded = cryptoExpanded,
                                onToggle = { cryptoExpanded = !cryptoExpanded }
                            )
                        }
                        if (cryptoExpanded) {
                            if (cryptoSymbols.isEmpty()) {
                                item {
                                    Text(
                                        text = "No crypto instruments in watchlist",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = TextMuted,
                                        modifier = Modifier.padding(start = 12.dp, bottom = 6.dp)
                                    )
                                }
                            } else {
                                items(cryptoSymbols) { sym ->
                                    val snap = snapshots[sym]
                                    WatchlistRow(
                                        symbol = sym,
                                        snapshot = snap,
                                        onClick = { onNavigateToSymbol(sym) },
                                        onRemove = { viewModel.removeWatchlist(sym) }
                                    )
                                }
                            }
                        }

                        // Domain 2: US MARKET
                        item {
                            CollapsibleMarketDomainHeader(
                                title = "US MARKET",
                                count = usSymbols.size,
                                isExpanded = usMarketExpanded,
                                onToggle = { usMarketExpanded = !usMarketExpanded }
                            )
                        }
                        if (usMarketExpanded) {
                            if (usSymbols.isEmpty()) {
                                item {
                                    Text(
                                        text = "No US equity instruments in watchlist",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = TextMuted,
                                        modifier = Modifier.padding(start = 12.dp, bottom = 6.dp)
                                    )
                                }
                            } else {
                                items(usSymbols) { sym ->
                                    val snap = snapshots[sym]
                                    WatchlistRow(
                                        symbol = sym,
                                        snapshot = snap,
                                        onClick = { onNavigateToSymbol(sym) },
                                        onRemove = { viewModel.removeWatchlist(sym) }
                                    )
                                }
                            }
                        }

                        // Domain 3: COMMODITIES / GOLD
                        item {
                            CollapsibleMarketDomainHeader(
                                title = "COMMODITIES / GOLD",
                                count = goldSymbols.size,
                                isExpanded = goldExpanded,
                                onToggle = { goldExpanded = !goldExpanded }
                            )
                        }
                        if (goldExpanded) {
                            if (goldSymbols.isEmpty()) {
                                item {
                                    Text(
                                        text = "No commodity instruments in watchlist",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = TextMuted,
                                        modifier = Modifier.padding(start = 12.dp, bottom = 6.dp)
                                    )
                                }
                            } else {
                                items(goldSymbols) { sym ->
                                    val snap = snapshots[sym]
                                    WatchlistRow(
                                        symbol = sym,
                                        snapshot = snap,
                                        onClick = { onNavigateToSymbol(sym) },
                                        onRemove = { viewModel.removeWatchlist(sym) }
                                    )
                                }
                            }
                        }
                    }
                }
                else -> {}
            }

            item { Spacer(modifier = Modifier.height(OpheliaSpacing.lg)) }
        }
    }
}

@Composable
private fun WatchlistRow(
    symbol: String,
    snapshot: com.ophelia.app.models.MarketSnapshotResponse?,
    onClick: () -> Unit,
    onRemove: () -> Unit
) {
    OpheliaGlassCard(
        level = GlassLevel.L1,
        modifier = Modifier.fillMaxWidth(),
        onClick = onClick
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Left: Symbol, Regime / Status Pill
            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(
                    text = symbol,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = TextPrimary
                )
                if (snapshot != null) {
                    val dir = snapshot.direction ?: snapshot.dailyPreference ?: snapshot.supertrendDirection
                    val reg = snapshot.marketRegime ?: "CHOP / MEAN REVERSION"
                    val prio = snapshot.tradePriority ?: if (snapshot.isPriority == true) "HIGH PRIORITY" else "NORMAL PRIORITY"

                    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Row(horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                            OpheliaStatusBadge(
                                status = dir,
                                color = if (dir == "BULLISH" || dir == "LONG") BullishGreen else if (dir == "BEARISH" || dir == "SHORT") BearishRed else WarningAmber,
                                showDot = false
                            )
                            OpheliaStatusBadge(
                                status = reg,
                                color = AccentPurple,
                                showDot = false
                            )
                        }
                        Text(
                            text = prio,
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.SemiBold,
                            color = if (prio.contains("HIGH")) BullishGreen else TextSecondary
                        )
                    }
                } else {
                    Text(
                        text = "Scanning market structure...",
                        style = MaterialTheme.typography.labelSmall,
                        color = TextMuted
                    )
                }
            }

            // Right: Mark Price, 24H Change %, and Navigation Button
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
            ) {
                if (snapshot != null) {
                    Column(horizontalAlignment = Alignment.End) {
                        val formattedPrice = when {
                            snapshot.price >= 1000.0 -> String.format(java.util.Locale.US, "$%,.2f", snapshot.price)
                            snapshot.price >= 1.0 -> String.format(java.util.Locale.US, "$%.2f", snapshot.price)
                            else -> String.format(java.util.Locale.US, "$%.4f", snapshot.price)
                        }
                        Text(
                            text = formattedPrice,
                            style = TabularNumberLargeStyle,
                            color = TextPrimary
                        )
                        val changePct = snapshot.priceChangePct
                        if (changePct != null) {
                            val isPos = changePct >= 0
                            Text(
                                text = "${if (isPos) "+" else ""}${String.format(java.util.Locale.US, "%.2f", changePct)}% 24H",
                                style = MaterialTheme.typography.labelSmall,
                                color = if (isPos) BullishGreen else BearishRed
                            )
                        } else {
                            Text(
                                text = "PERPETUAL",
                                style = MaterialTheme.typography.labelSmall,
                                color = TextMuted
                            )
                        }
                    }
                }
                OpheliaOutlinedButton(
                    text = "VIEW",
                    onClick = onClick
                )
            }
        }
    }
}

@Composable
fun CollapsibleMarketDomainHeader(
    title: String,
    count: Int,
    isExpanded: Boolean,
    onToggle: () -> Unit
) {
    Surface(
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f),
        shape = RoundedCornerShape(8.dp),
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onToggle() }
            .padding(vertical = 4.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text(
                    text = if (isExpanded) "▼ $title" else "▶ $title",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = AccentBlue,
                    fontSize = 12.sp,
                    letterSpacing = 0.5.sp
                )
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(4.dp))
                        .background(AccentBlue.copy(alpha = 0.15f))
                        .padding(horizontal = 6.dp, vertical = 2.dp)
                ) {
                    Text(
                        text = "$count",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = AccentBlue,
                        fontSize = 10.sp
                    )
                }
            }
            Text(
                text = if (isExpanded) "HIDE" else "SHOW",
                style = MaterialTheme.typography.labelSmall,
                color = TextSecondary,
                fontSize = 10.sp
            )
        }
    }
}

