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
import androidx.lifecycle.viewmodel.compose.viewModel
import com.ophelia.app.auth.TokenManager
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.viewmodels.MarketViewModel
import com.ophelia.app.ui.viewmodels.UiState
import com.ophelia.app.ui.theme.*

@Composable
fun SymbolDetailScreen(
    symbol: String,
    onBack: () -> Unit
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

    var selectedTimeframe by remember { mutableIntStateOf(5) }
    val detailState by viewModel.detailSnapshotState.collectAsState()
    val candlesState by viewModel.candlesState.collectAsState()

    LaunchedEffect(symbol, selectedTimeframe) {
        viewModel.getSymbolSnapshot(symbol, selectedTimeframe)
    }

    Scaffold(
        containerColor = BackgroundCanvas,
        topBar = {
            OpheliaTopBar(
                title = symbol,
                subtitle = "${selectedTimeframe}m Perpetual Telemetry",
                onBack = onBack,
                onRefresh = { viewModel.getSymbolSnapshot(symbol, selectedTimeframe) }
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
            itemSpacer()

            // 1. Timeframe Selection Pills
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
            ) {
                listOf(1, 3, 5, 15).forEach { tf ->
                    OpheliaChip(
                        text = "${tf}m",
                        isSelected = selectedTimeframe == tf,
                        onClick = { selectedTimeframe = tf },
                        modifier = Modifier.weight(1f)
                    )
                }
            }

            // 2. Mark Price & 24h Volume Card
            when (val state = detailState) {
                is UiState.Success -> {
                    val snapshot = state.data
                    OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.fillMaxWidth()) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column {
                                Text(
                                    text = "MARK PRICE (USDT)",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = TextSecondary
                                )
                                Text(
                                    text = "$${snapshot.price}",
                                    style = MaterialTheme.typography.displayMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = TextPrimary
                                )
                            }
                            Column(horizontalAlignment = Alignment.End) {
                                Text(
                                    text = "24H VOLUME",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = TextSecondary
                                )
                                val vol24 = snapshot.volume24h ?: snapshot.volume
                                val formattedVol = when {
                                    vol24 >= 1_000_000_000.0 -> String.format(java.util.Locale.US, "%.2fB USDT", vol24 / 1_000_000_000.0)
                                    vol24 >= 1_000_000.0 -> String.format(java.util.Locale.US, "%.2fM USDT", vol24 / 1_000_000.0)
                                    vol24 >= 1_000.0 -> String.format(java.util.Locale.US, "%,.0f USDT", vol24)
                                    else -> String.format(java.util.Locale.US, "%.2f USDT", vol24)
                                }
                                Text(
                                    text = formattedVol,
                                    style = TabularNumberLargeStyle,
                                    color = TextPrimary
                                )
                            }
                        }
                    }
                }
                else -> {}
            }

            // 3. Candlestick Chart Area
            OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.fillMaxWidth()) {
                Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "$symbol · ${selectedTimeframe}m KLINE CHART",
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold,
                            color = TextSecondary
                        )
                        OpheliaStatusBadge(status = "CANDLES", color = AccentBlue, showDot = false)
                    }

                    OpheliaDivider()

                    when (val cState = candlesState) {
                        is UiState.Loading -> {
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(200.dp),
                                contentAlignment = Alignment.Center
                            ) {
                                OpheliaLoadingState(message = "Streaming klines...")
                            }
                        }
                        is UiState.Error -> {
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(200.dp),
                                contentAlignment = Alignment.Center
                            ) {
                                OpheliaErrorState(
                                    message = "Failed to load candles: ${cState.message}",
                                    onRetry = { viewModel.getSymbolSnapshot(symbol, selectedTimeframe) }
                                )
                            }
                        }
                        is UiState.Success -> {
                            CandleChart(
                                candles = cState.data,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(220.dp)
                            )
                        }
                        else -> {}
                    }
                }
            }

            // 4. Indicator State Telemetry (Unified Terminal Panel)
            when (val state = detailState) {
                is UiState.Loading -> {
                    OpheliaLoadingState(message = "Calculating technical indicators...")
                }
                is UiState.Error -> {
                    OpheliaErrorState(
                        message = state.message,
                        onRetry = { viewModel.getSymbolSnapshot(symbol, selectedTimeframe) }
                    )
                }
                is UiState.Success -> {
                    val snapshot = state.data
                    val vwapColor = when (snapshot.vwapRegime.state) {
                        "CLEAR_ABOVE" -> BullishGreen
                        "CLEAR_BELOW" -> BearishRed
                        else -> WarningAmber
                    }

                    OpheliaSectionHeader(title = "Regime & Indicators")

                    OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.fillMaxWidth()) {
                        Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)) {
                            // Hierarchical Market Regime & Gamma
                            if (snapshot.marketRegime != null || snapshot.gammaRegime != null) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Column(modifier = Modifier.weight(1f).padding(end = OpheliaSpacing.xs)) {
                                        Text(
                                            text = "HIERARCHICAL REGIME",
                                            style = MaterialTheme.typography.labelSmall,
                                            color = TextSecondary
                                        )
                                        Text(
                                            text = "${snapshot.marketRegime ?: "TREND / CHOP"} · ${snapshot.volatilityRegime ?: "NORMAL"}",
                                            style = TabularNumberStyle,
                                            color = TextPrimary
                                        )
                                        Text(
                                            text = "Gamma: ${snapshot.gammaRegime ?: "N/A"} · Bias: ${snapshot.dailyPreference ?: "NEUTRAL"}",
                                            style = MaterialTheme.typography.labelSmall,
                                            color = TextMuted
                                        )
                                    }
                                    OpheliaStatusBadge(
                                        status = snapshot.dailyPreference ?: "NEUTRAL",
                                        color = when (snapshot.dailyPreference) {
                                            "BULLISH", "STRONG BULLISH" -> BullishGreen
                                            "BEARISH", "STRONG BEARISH" -> BearishRed
                                            else -> AccentPurple
                                        },
                                        showDot = false
                                    )
                                }
                                OpheliaDivider()
                            }

                            // VWAP Directional Gate
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text(
                                        text = "VWAP ANCHOR",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = TextSecondary
                                    )
                                    Text(
                                        text = "$${String.format(java.util.Locale.US, "%.2f", snapshot.vwap)}",
                                        style = TabularNumberStyle,
                                        color = TextPrimary
                                    )
                                    Text(
                                        text = "Separation: ${String.format(java.util.Locale.US, "%.3f", snapshot.vwapSeparationPct)}%",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = TextMuted
                                    )
                                }
                                OpheliaStatusBadge(
                                    status = snapshot.vwapRegime.state,
                                    color = vwapColor
                                )
                            }

                            OpheliaDivider()

                            // OI / Volume Positioning Regime
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(modifier = Modifier.weight(1f).padding(end = OpheliaSpacing.xs)) {
                                    Text(
                                        text = "OI / VOLUME POSITIONING REGIME",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = TextSecondary
                                    )
                                    Text(
                                        text = snapshot.positioningRegime ?: "COMPRESSION_RANGE_POSITIONING",
                                        style = TabularNumberStyle,
                                        color = TextPrimary
                                    )
                                    Text(
                                        text = snapshot.tradePriority ?: "NORMAL PRIORITY",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = if ((snapshot.tradePriority ?: "").contains("HIGH")) BullishGreen else TextMuted
                                    )
                                }
                                OpheliaStatusBadge(
                                    status = if ((snapshot.tradePriority ?: "").contains("HIGH")) "HIGH PRIO" else "STANDARD",
                                    color = if ((snapshot.tradePriority ?: "").contains("HIGH")) BullishGreen else AccentPurple,
                                    showDot = false
                                )
                            }
                        }
                    }

                    // 5. Volume Telemetry Separation
                    OpheliaSectionHeader(title = "Volume Telemetry")
                    OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.fillMaxWidth()) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = snapshot.currentCandleLabel ?: "CURRENT ${selectedTimeframe}m CANDLE",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = TextSecondary
                                )
                                val curVol = snapshot.currentCandleVolume ?: snapshot.volume
                                val formattedCur = when {
                                    curVol >= 1_000_000_000.0 -> String.format(java.util.Locale.US, "$%.2fB", curVol / 1_000_000_000.0)
                                    curVol >= 1_000_000.0 -> String.format(java.util.Locale.US, "$%.2fM", curVol / 1_000_000.0)
                                    curVol >= 1_000.0 -> String.format(java.util.Locale.US, "$%,.0f", curVol)
                                    else -> String.format(java.util.Locale.US, "$%.2f", curVol)
                                }
                                Text(
                                    text = formattedCur,
                                    style = TabularNumberStyle,
                                    color = TextPrimary
                                )
                                if (snapshot.currentCandleBaseVolume != null && snapshot.currentCandleBaseVolume > 0) {
                                    Text(
                                        text = "${String.format(java.util.Locale.US, "%.2f", snapshot.currentCandleBaseVolume)} ${snapshot.baseAsset ?: ""}",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = TextMuted
                                    )
                                }
                            }
                            Column(modifier = Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally) {
                                Text("1H ROLLING", style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                                val r1h = snapshot.rollingVolume1h ?: 0.0
                                val formatted1h = when {
                                    r1h >= 1_000_000_000.0 -> String.format(java.util.Locale.US, "$%.2fB", r1h / 1_000_000_000.0)
                                    r1h >= 1_000_000.0 -> String.format(java.util.Locale.US, "$%.2fM", r1h / 1_000_000.0)
                                    r1h >= 1_000.0 -> String.format(java.util.Locale.US, "$%,.0f", r1h)
                                    else -> String.format(java.util.Locale.US, "$%.2f", r1h)
                                }
                                Text(
                                    text = formatted1h,
                                    style = TabularNumberStyle,
                                    color = TextPrimary
                                )
                                if (snapshot.rollingBaseVolume1h != null && snapshot.rollingBaseVolume1h > 0) {
                                    Text(
                                        text = "${String.format(java.util.Locale.US, "%.1f", snapshot.rollingBaseVolume1h)} ${snapshot.baseAsset ?: ""}",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = TextMuted
                                    )
                                }
                            }
                            Column(modifier = Modifier.weight(0.8f), horizontalAlignment = Alignment.End) {
                                Text("RVOL (20-BAR)", style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                                val rvolVal = snapshot.rvol ?: 1.0
                                Text(
                                    text = "${String.format(java.util.Locale.US, "%.2f", rvolVal)}x",
                                    style = TabularNumberStyle,
                                    color = if (rvolVal >= 1.5) BullishGreen else (if (rvolVal < 0.8) WarningAmber else TextPrimary)
                                )
                                Text(
                                    text = if (rvolVal >= 1.2) "EXPANDING" else "COMPRESSED",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = if (rvolVal >= 1.2) BullishGreen else TextMuted
                                )
                            }
                        }
                    }

                    // 6. Order Flow & Microstructure Depth (PRESERVED: Net Taker Flow, Order Book Skew, CVD)
                    OpheliaSectionHeader(title = "Order Flow Telemetry")
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
                    ) {
                        OpheliaGlassCard(
                            level = GlassLevel.L1,
                            modifier = Modifier.weight(1f)
                        ) {
                            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                val baseAsset = symbol.split("-", "_").firstOrNull() ?: "Units"
                                Text("NET TAKER FLOW", style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                                Text(
                                    text = "${if (snapshot.netFlow >= 0) "+" else ""}${snapshot.netFlow} $baseAsset",
                                    style = TabularNumberLargeStyle,
                                    color = if (snapshot.netFlow >= 0) BullishGreen else BearishRed
                                )
                                Text(
                                    text = "In: ${snapshot.inflow.toInt()} | Out: ${snapshot.outflow.toInt()} $baseAsset",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = TextMuted
                                )
                            }
                        }

                        OpheliaGlassCard(
                            level = GlassLevel.L1,
                            modifier = Modifier.weight(1f)
                        ) {
                            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                Text("ORDER BOOK SKEW", style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                                Text(
                                    text = "${snapshot.orderBookSkew}%",
                                    style = TabularNumberLargeStyle,
                                    color = if (snapshot.orderBookSkew >= 0) BullishGreen else BearishRed
                                )
                                Text(
                                    text = "Depth imbalance",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = TextMuted
                                )
                            }
                        }

                        OpheliaGlassCard(
                            level = GlassLevel.L1,
                            modifier = Modifier.weight(1f)
                        ) {
                            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                Text("CVD AGGRESSION", style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                                val cvdVal = snapshot.cvd ?: 0.0
                                Text(
                                    text = "${if (cvdVal >= 0) "+" else ""}${String.format(java.util.Locale.US, "%.1f", cvdVal)}",
                                    style = TabularNumberLargeStyle,
                                    color = if (cvdVal >= 0) BullishGreen else BearishRed
                                )
                                Text(
                                    text = "Cumulative delta",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = TextMuted
                                )
                            }
                        }
                    }

                    // 7. Higher-Timeframe Structure & Macro
                    OpheliaSectionHeader(title = "Higher-Timeframe & Macro Context")
                    OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.fillMaxWidth()) {
                        Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text("4H STRUCTURE", style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                                    Text(
                                        text = snapshot.htf4hStructure ?: "NEUTRAL",
                                        style = TabularNumberStyle,
                                        color = if ((snapshot.htf4hStructure ?: "").contains("BULL")) BullishGreen else BearishRed
                                    )
                                }
                                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                    Text("1D STRUCTURE", style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                                    Text(
                                        text = snapshot.htf1dStructure ?: "NEUTRAL",
                                        style = TabularNumberStyle,
                                        color = if ((snapshot.htf1dStructure ?: "").contains("BULL")) BullishGreen else BearishRed
                                    )
                                }
                                Column(horizontalAlignment = Alignment.End) {
                                    Text("GAMMA REGIME", style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                                    Text(
                                        text = if ((snapshot.gammaRegime ?: "").contains("NOT AVAILABLE")) "N/A (ALT/GOLD)" else "CONFIRMED",
                                        style = TabularNumberStyle,
                                        color = AccentPurple
                                    )
                                }
                            }
                            OpheliaDivider()
                            Text(
                                text = "NEWS/MACRO: ${snapshot.newsMacroContext ?: "MACRO LIQUIDITY STABLE"}",
                                style = MaterialTheme.typography.labelSmall,
                                color = TextMuted
                            )
                        }
                    }

                    // 8. Volatility Indices (CVI, BVIN, VCRIX)
                    OpheliaSectionHeader(title = "Crypto Volatility Benchmarks")
                    OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.fillMaxWidth()) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column {
                                Text("CVI BENCHMARK", style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                                Text(
                                    text = "${String.format(java.util.Locale.US, "%.1f", snapshot.cvi ?: 50.0)}%",
                                    style = TabularNumberStyle,
                                    color = TextPrimary
                                )
                                Text("Realized vol basket", style = MaterialTheme.typography.labelSmall, color = TextMuted)
                            }
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Text("BVIN / BVOL", style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                                Text(
                                    text = "${String.format(java.util.Locale.US, "%.1f", snapshot.bvin ?: 50.0)}%",
                                    style = TabularNumberStyle,
                                    color = TextPrimary
                                )
                                Text("BTC 30d vol", style = MaterialTheme.typography.labelSmall, color = TextMuted)
                            }
                            Column(horizontalAlignment = Alignment.End) {
                                Text("VCRIX INDEX", style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                                Text(
                                    text = "${String.format(java.util.Locale.US, "%.1f", snapshot.vcrix ?: 50.0)}%",
                                    style = TabularNumberStyle,
                                    color = TextPrimary
                                )
                                Text("Market composite", style = MaterialTheme.typography.labelSmall, color = TextMuted)
                            }
                        }
                    }

                    // 9. Intelligence Bias & Final Market Bias
                    OpheliaSectionHeader(title = "Final Market Bias & Intelligence")
                    OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.fillMaxWidth()) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(modifier = Modifier.weight(1f).padding(end = OpheliaSpacing.xs)) {
                                Text("FINAL DAILY MARKET BIAS", style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                                Text(
                                    text = snapshot.finalDailyMarketBias ?: snapshot.dailyPreference ?: "NEUTRAL",
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = when (snapshot.finalDailyMarketBias ?: snapshot.dailyPreference) {
                                        "LONG", "BULLISH", "STRONG BULLISH" -> BullishGreen
                                        "SHORT", "BEARISH", "STRONG BEARISH" -> BearishRed
                                        else -> AccentPurple
                                    }
                                )
                                Text(
                                    text = "ML Intelligence: ${snapshot.mlIntelligenceBias ?: "ALIGNED"} · Counter-trend: ${if (snapshot.allowsCounterTrend != false) "PERMITTED" else "BLOCKED"}",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = TextMuted
                                )
                            }
                            OpheliaStatusBadge(
                                status = snapshot.finalDailyMarketBias ?: snapshot.dailyPreference ?: "NEUTRAL",
                                color = when (snapshot.finalDailyMarketBias ?: snapshot.dailyPreference) {
                                    "LONG", "BULLISH", "STRONG BULLISH" -> BullishGreen
                                    "SHORT", "BEARISH", "STRONG BEARISH" -> BearishRed
                                    else -> AccentPurple
                                },
                                showDot = true
                            )
                        }
                    }
                }
                else -> {}
            }

            itemSpacer()
        }
    }
}

@Composable
private fun itemSpacer() {
    Spacer(modifier = Modifier.height(OpheliaSpacing.xs))
}
