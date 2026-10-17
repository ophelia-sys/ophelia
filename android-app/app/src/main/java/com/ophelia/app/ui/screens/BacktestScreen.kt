package com.ophelia.app.ui.screens

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
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
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.ophelia.app.models.*
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.theme.*
import com.ophelia.app.ui.viewmodels.UiState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.Locale

class BacktestViewModel : ViewModel() {
    var selectedSystem by mutableStateOf("ML_REPLAY") // "ML_REPLAY" (PRIMARY) or "DETERMINISTIC" (SECONDARY)

    private val _replayState = MutableStateFlow<UiState<MLHistoricalReplayDto>>(UiState.Loading)
    val replayState = _replayState.asStateFlow()

    private val _backtestState = MutableStateFlow<UiState<BacktestResponseDto>>(UiState.Loading)
    val backtestState = _backtestState.asStateFlow()

    private val _availableSetups = MutableStateFlow<List<SetupCandidateDto>>(emptyList())
    val availableSetups = _availableSetups.asStateFlow()

    var activeSetupId by mutableStateOf<String?>(null)
    var isRunningReplay by mutableStateOf(false)
    var isRunningDeterministic by mutableStateOf(false)

    fun initialize(initialSetupId: String?) {
        if (!initialSetupId.isNullOrBlank()) {
            activeSetupId = initialSetupId
            selectedSystem = "ML_REPLAY"
            fetchReplay(initialSetupId)
        } else {
            fetchAvailableSetupsAndReplayFirst()
        }
        fetchDeterministicBacktest()
    }

    fun fetchAvailableSetupsAndReplayFirst() {
        viewModelScope.launch {
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val setupsRes = api.getMlSetups()
                val list = setupsRes.setups
                _availableSetups.value = list
                val targetId = activeSetupId ?: list.firstOrNull()?.setupId
                if (!targetId.isNullOrBlank()) {
                    activeSetupId = targetId
                    fetchReplay(targetId)
                } else {
                    _replayState.value = UiState.Error("No active ML setups available in current market state.")
                }
            } catch (e: Exception) {
                _replayState.value = UiState.Error(e.message ?: "Failed to load ML setups")
            }
        }
    }

    fun fetchReplay(setupId: String) {
        viewModelScope.launch {
            _replayState.value = UiState.Loading
            isRunningReplay = true
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API not connected")
                val res = api.getMlSetupReplay(setupId)
                _replayState.value = UiState.Success(res)
            } catch (e: Exception) {
                _replayState.value = UiState.Error(e.message ?: "Failed to load ML Setup Replay")
            } finally {
                isRunningReplay = false
            }
        }
    }

    fun fetchDeterministicBacktest() {
        viewModelScope.launch {
            _backtestState.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API not connected")
                val res = api.get48hBacktest()
                _backtestState.value = UiState.Success(res)
            } catch (e: Exception) {
                _backtestState.value = UiState.Error(e.message ?: "Failed to load deterministic backtest")
            }
        }
    }

    fun runDeterministicBacktest(onComplete: (String) -> Unit) {
        viewModelScope.launch {
            isRunningDeterministic = true
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API not connected")
                val res = api.runBacktest()
                _backtestState.value = UiState.Success(res)
                onComplete("Deterministic simulation finished: ${res.metrics.executedTrades} trades simulated.")
            } catch (e: Exception) {
                onComplete("Simulation error: ${e.message}")
            } finally {
                isRunningDeterministic = false
            }
        }
    }
}

@Composable
fun BacktestScreen(
    initialSetupId: String? = null,
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val vm: BacktestViewModel = viewModel()

    LaunchedEffect(initialSetupId) {
        vm.initialize(initialSetupId)
    }

    val replayState by vm.replayState.collectAsState()
    val detBacktestState by vm.backtestState.collectAsState()
    val availableSetups by vm.availableSetups.collectAsState()
    val colors = OpheliaThemeTokens.colors

    Scaffold(
        containerColor = BackgroundCanvas,
        topBar = {
            OpheliaTopBar(
                title = if (vm.selectedSystem == "ML_REPLAY") "ML HISTORICAL REPLAY" else "DETERMINISTIC BACKTEST",
                subtitle = if (vm.selectedSystem == "ML_REPLAY") "Ophelia ML Intelligence Causal Replay" else "Research Deterministic Strategy Performance",
                onBack = onBack,
                onRefresh = {
                    if (vm.selectedSystem == "ML_REPLAY") {
                        vm.activeSetupId?.let { vm.fetchReplay(it) } ?: vm.fetchAvailableSetupsAndReplayFirst()
                    } else {
                        vm.fetchDeterministicBacktest()
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            // 1. Two Backtest Systems Toggle (Sections 1 & 15)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(12.dp))
                    .background(colors.surfaceElevated)
                    .border(1.dp, colors.border, RoundedCornerShape(12.dp))
                    .padding(4.dp),
                horizontalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                // Tab A: ML SETUP HISTORICAL REPLAY (PRIMARY)
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .clip(RoundedCornerShape(8.dp))
                        .background(if (vm.selectedSystem == "ML_REPLAY") AccentPurple else Color.Transparent)
                        .clickable { vm.selectedSystem = "ML_REPLAY" }
                        .padding(vertical = 8.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "ML HISTORICAL REPLAY",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = if (vm.selectedSystem == "ML_REPLAY") Color.White else colors.secondaryText,
                        fontSize = 11.sp
                    )
                }

                // Tab B: DETERMINISTIC STRATEGY BACKTEST (SECONDARY)
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .clip(RoundedCornerShape(8.dp))
                        .background(if (vm.selectedSystem == "DETERMINISTIC") AccentBlue else Color.Transparent)
                        .clickable { vm.selectedSystem = "DETERMINISTIC" }
                        .padding(vertical = 8.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "DETERMINISTIC BACKTEST",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = if (vm.selectedSystem == "DETERMINISTIC") Color.White else colors.secondaryText,
                        fontSize = 11.sp
                    )
                }
            }

            // 2. Body based on selected system
            if (vm.selectedSystem == "ML_REPLAY") {
                RenderMlReplayView(
                    vm = vm,
                    replayState = replayState,
                    availableSetups = availableSetups,
                    colors = colors
                )
            } else {
                RenderDeterministicBacktestView(
                    vm = vm,
                    detState = detBacktestState,
                    context = context,
                    colors = colors
                )
            }
        }
    }
}

@Composable
private fun RenderMlReplayView(
    vm: BacktestViewModel,
    replayState: UiState<MLHistoricalReplayDto>,
    availableSetups: List<SetupCandidateDto>,
    colors: OpheliaSemanticColors
) {
    // Setup Selector Row if multiple active setups exist
    if (availableSetups.isNotEmpty()) {
        LazyRow(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            items(availableSetups) { setup ->
                val isSelected = setup.setupId == vm.activeSetupId
                val isLong = setup.direction.uppercase() == "LONG"
                val dirColor = if (isLong) BullishGreen else BearishRed

                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .background(if (isSelected) AccentPurple.copy(alpha = 0.25f) else colors.surfaceElevated)
                        .border(
                            1.dp,
                            if (isSelected) AccentPurple else colors.border,
                            RoundedCornerShape(8.dp)
                        )
                        .clickable {
                            vm.activeSetupId = setup.setupId
                            vm.fetchReplay(setup.setupId)
                        }
                        .padding(horizontal = 10.dp, vertical = 6.dp)
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        Text(
                            text = setup.direction,
                            fontWeight = FontWeight.Bold,
                            color = dirColor,
                            fontSize = 10.sp
                        )
                        Text(
                            text = setup.symbol,
                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                            color = if (isSelected) AccentPurple else colors.primaryText,
                            fontSize = 11.sp
                        )
                        Text(
                            text = "${setup.timeframe}m",
                            fontSize = 10.sp,
                            color = colors.mutedText
                        )
                    }
                }
            }
        }
    }

    when (val state = replayState) {
        is UiState.Loading -> {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    CircularProgressIndicator(color = AccentPurple)
                    Text("Executing causal Ophelia ML Intelligence historical replay...", color = colors.mutedText, fontSize = 12.sp)
                }
            }
        }
        is UiState.Error -> {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text(text = state.message, color = BearishRed, fontWeight = FontWeight.Bold)
                    OpheliaButton(text = "RETRY REPLAY", onClick = {
                        vm.activeSetupId?.let { vm.fetchReplay(it) } ?: vm.fetchAvailableSetupsAndReplayFirst()
                    })
                }
            }
        }
        is UiState.Success -> {
            val replay = state.data
            val frozen = replay.frozenSetup
            val sum = replay.summary
            val dataAvail = replay.dataAvailability
            val isLong = frozen.direction.uppercase() == "LONG"
            val dirColor = if (isLong) BullishGreen else BearishRed

            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(bottom = 24.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                // A. Frozen Setup Snapshot Card (Section 2)
                item {
                    OpheliaGlassCard(
                        level = GlassLevel.L2,
                        borderColor = AccentPurple.copy(alpha = 0.55f)
                    ) {
                        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    Icon(Icons.Filled.Lock, contentDescription = null, tint = AccentPurple, modifier = Modifier.size(16.dp))
                                    Text(
                                        text = "FROZEN SETUP SNAPSHOT",
                                        style = MaterialTheme.typography.labelSmall,
                                        fontWeight = FontWeight.Black,
                                        color = AccentPurple,
                                        letterSpacing = 0.8.sp
                                    )
                                }
                                OpheliaStatusBadge(
                                    status = frozen.direction,
                                    color = dirColor,
                                    showDot = true
                                )
                            }

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text(
                                        text = "${frozen.symbol} • ${frozen.timeframeLabel}",
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.Bold,
                                        color = colors.primaryText
                                    )
                                    Text(
                                        text = "ID: ${frozen.setupId}",
                                        fontSize = 10.sp,
                                        color = colors.mutedText
                                    )
                                }
                                Text(
                                    text = "AI CONF: ${frozen.aiConfidence.toInt()}%",
                                    style = MaterialTheme.typography.labelSmall,
                                    fontWeight = FontWeight.Bold,
                                    color = AccentPurple
                                )
                            }

                            if (frozen.thesis.isNotBlank()) {
                                Text(
                                    text = frozen.thesis,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = colors.secondaryText,
                                    fontSize = 11.sp
                                )
                            }

                            // Geometry in % and R (NO USDT in primary display!)
                            OpheliaGlassPanel {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Column {
                                        Text("ENTRY", fontSize = 10.sp, color = colors.mutedText)
                                        Text("0.00%", fontWeight = FontWeight.Bold, fontSize = 12.sp, color = colors.primaryText)
                                    }
                                    Column {
                                        Text("SL", fontSize = 10.sp, color = colors.mutedText)
                                        Text("${String.format(Locale.US, "%.2f", frozen.geometry.slPct)}%", fontWeight = FontWeight.Bold, fontSize = 12.sp, color = BearishRed)
                                    }
                                    Column {
                                        Text("TP1", fontSize = 10.sp, color = colors.mutedText)
                                        Text("+${String.format(Locale.US, "%.2f", frozen.geometry.tp1Pct)}%", fontWeight = FontWeight.Bold, fontSize = 12.sp, color = BullishGreen)
                                        Text("${String.format(Locale.US, "%.1f", frozen.geometry.tp1R)}R", fontSize = 9.sp, color = colors.mutedText)
                                    }
                                    Column {
                                        Text("TP2", fontSize = 10.sp, color = colors.mutedText)
                                        Text("+${String.format(Locale.US, "%.2f", frozen.geometry.tp2Pct)}%", fontWeight = FontWeight.Bold, fontSize = 12.sp, color = BullishGreen)
                                        Text("${String.format(Locale.US, "%.1f", frozen.geometry.tp2R)}R", fontSize = 9.sp, color = colors.mutedText)
                                    }
                                    Column(horizontalAlignment = Alignment.End) {
                                        Text("TP3", fontSize = 10.sp, color = colors.mutedText)
                                        Text("+${String.format(Locale.US, "%.2f", frozen.geometry.tp3Pct)}%", fontWeight = FontWeight.Bold, fontSize = 12.sp, color = BullishGreen)
                                        Text("${String.format(Locale.US, "%.1f", frozen.geometry.tp3R)}R", fontSize = 9.sp, color = colors.mutedText)
                                    }
                                }
                            }
                        }
                    }
                }

                // B. Data Availability & Venue Accuracy Banner (Sections 6, 7, 8)
                item {
                    val isFull = dataAvail.isFull48h
                    val availColor = if (isFull) BullishGreen else WarningAmber
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(10.dp))
                            .background(availColor.copy(alpha = 0.10f))
                            .border(1.dp, availColor.copy(alpha = 0.40f), RoundedCornerShape(10.dp))
                            .padding(10.dp)
                    ) {
                        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = dataAvail.status,
                                    style = MaterialTheme.typography.labelSmall,
                                    fontWeight = FontWeight.Bold,
                                    color = availColor,
                                    fontSize = 11.sp
                                )
                                Text(
                                    text = dataAvail.dataSource,
                                    style = MaterialTheme.typography.labelSmall,
                                    color = colors.primaryText,
                                    fontWeight = FontWeight.SemiBold,
                                    fontSize = 10.sp
                                )
                            }
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(
                                    text = "Order Flow: ${dataAvail.cvdStatus}",
                                    fontSize = 10.sp,
                                    color = colors.secondaryText
                                )
                                Text(
                                    text = "${String.format(Locale.US, "%.1f", dataAvail.availableSpanHours)}H SPAN",
                                    fontSize = 10.sp,
                                    color = colors.mutedText,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }
                    }
                }

                // C. Aggregate % and R Statistics Card (Sections 12 & 14 — NO USDT)
                item {
                    OpheliaGlassCard(level = GlassLevel.L1) {
                        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "HISTORICAL ANALOGUE PERFORMANCE",
                                    style = MaterialTheme.typography.labelSmall,
                                    fontWeight = FontWeight.Bold,
                                    color = colors.primaryText,
                                    letterSpacing = 0.8.sp
                                )
                                Text(
                                    text = "${sum.historicalMatchesCount} MATCHES",
                                    style = MaterialTheme.typography.labelSmall,
                                    fontWeight = FontWeight.Black,
                                    color = AccentPurple
                                )
                            }

                            // Expectancy & Net Return Grid (Strictly % and R)
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                OpheliaMetric(
                                    label = "Net Return",
                                    value = "${if (sum.netReturnPct >= 0) "+" else ""}${String.format(Locale.US, "%.2f", sum.netReturnPct)}%",
                                    valueColor = if (sum.netReturnPct >= 0) BullishGreen else BearishRed,
                                    subValue = "All Matches"
                                )
                                OpheliaMetric(
                                    label = "Expectancy R",
                                    value = "${if (sum.expectancyR >= 0) "+" else ""}${String.format(Locale.US, "%.2f", sum.expectancyR)}R",
                                    valueColor = if (sum.expectancyR >= 0) BullishGreen else BearishRed,
                                    subValue = "Median: ${String.format(Locale.US, "%.2f", sum.medianR)}R"
                                )
                                OpheliaMetric(
                                    label = "Profit Factor",
                                    value = "${String.format(Locale.US, "%.2f", sum.profitFactor)}",
                                    valueColor = if (sum.profitFactor >= 1.0) BullishGreen else BearishRed,
                                    subValue = "Max DD: ${String.format(Locale.US, "%.1f", sum.maxDrawdownPct)}%"
                                )
                            }

                            OpheliaDivider()

                            // Hit Rates Row
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Column {
                                    Text("TP1 HIT", fontSize = 10.sp, color = colors.mutedText)
                                    Text("${String.format(Locale.US, "%.1f", sum.tp1HitRatePct)}%", fontWeight = FontWeight.Bold, fontSize = 12.sp, color = BullishGreen)
                                }
                                Column {
                                    Text("TP2 HIT", fontSize = 10.sp, color = colors.mutedText)
                                    Text("${String.format(Locale.US, "%.1f", sum.tp2HitRatePct)}%", fontWeight = FontWeight.Bold, fontSize = 12.sp, color = BullishGreen)
                                }
                                Column {
                                    Text("TP3 HIT", fontSize = 10.sp, color = colors.mutedText)
                                    Text("${String.format(Locale.US, "%.1f", sum.tp3HitRatePct)}%", fontWeight = FontWeight.Bold, fontSize = 12.sp, color = BullishGreen)
                                }
                                Column {
                                    Text("SL FIRST", fontSize = 10.sp, color = colors.mutedText)
                                    Text("${String.format(Locale.US, "%.1f", sum.slFirstRatePct)}%", fontWeight = FontWeight.Bold, fontSize = 12.sp, color = BearishRed)
                                }
                                Column(horizontalAlignment = Alignment.End) {
                                    Text("BREAKEVEN", fontSize = 10.sp, color = colors.mutedText)
                                    Text("${String.format(Locale.US, "%.1f", sum.breakevenRatePct)}%", fontWeight = FontWeight.Bold, fontSize = 12.sp, color = colors.secondaryText)
                                }
                            }

                            OpheliaDivider()

                            // 3-Layer Agreement Metrics (Section 10)
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Column {
                                    Text("TECH VALID", fontSize = 10.sp, color = colors.mutedText)
                                    Text("${sum.technicalValidMatchesCount}/${sum.historicalMatchesCount}", fontWeight = FontWeight.Bold, fontSize = 11.sp, color = colors.primaryText)
                                }
                                Column {
                                    Text("AGENTS AGREE", fontSize = 10.sp, color = colors.mutedText)
                                    Text("${String.format(Locale.US, "%.1f", sum.tradingAgentsAgreementPct)}%", fontWeight = FontWeight.Bold, fontSize = 11.sp, color = AccentPurple)
                                }
                                Column {
                                    Text("OPHELIA ML AGREE", fontSize = 10.sp, color = colors.mutedText)
                                    Text("${String.format(Locale.US, "%.1f", sum.qwenAgreementPct)}%", fontWeight = FontWeight.Bold, fontSize = 11.sp, color = AccentBlue)
                                }
                                Column(horizontalAlignment = Alignment.End) {
                                    Text("RISK VALID", fontSize = 10.sp, color = colors.mutedText)
                                    Text("${String.format(Locale.US, "%.1f", sum.deterministicValidationPct)}%", fontWeight = FontWeight.Bold, fontSize = 11.sp, color = BullishGreen)
                                }
                            }
                        }
                    }
                }

                // D. Mandatory Analogue Disclaimer Banner (Section 13)
                item {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(8.dp))
                            .background(colors.surfaceElevated)
                            .border(1.dp, colors.border, RoundedCornerShape(8.dp))
                            .padding(10.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = replay.disclaimer,
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold,
                            color = colors.mutedText,
                            fontSize = 10.sp,
                            letterSpacing = 0.5.sp
                        )
                    }
                }

                // E. Historical Analogue Matches (Sections 10 & 11)
                item {
                    OpheliaSectionHeader(title = "HISTORICAL CANDIDATE MATCHES (${replay.historicalMatches.size})")
                }

                items(replay.historicalMatches) { match ->
                    val isMatchLong = match.direction.uppercase() == "LONG"
                    val mDirColor = if (isMatchLong) BullishGreen else BearishRed
                    val outcomeColor = when (match.outcome) {
                        "TP1", "TP2", "TP3" -> BullishGreen
                        "SL FIRST" -> BearishRed
                        else -> colors.mutedText
                    }

                    OpheliaGlassCard(
                        level = GlassLevel.L2,
                        borderColor = if (match.outcome.startsWith("TP")) BullishGreen.copy(alpha = 0.4f) else colors.border
                    ) {
                        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            // Match Header
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    Text(
                                        text = "MATCH #${match.matchNumber}",
                                        style = MaterialTheme.typography.labelSmall,
                                        fontWeight = FontWeight.Black,
                                        color = AccentPurple
                                    )
                                    Text(
                                        text = "• ${match.symbol} (${match.timeframe})",
                                        style = MaterialTheme.typography.labelSmall,
                                        fontWeight = FontWeight.Bold,
                                        color = colors.primaryText
                                    )
                                    Text(
                                        text = match.direction,
                                        style = MaterialTheme.typography.labelSmall,
                                        fontWeight = FontWeight.Bold,
                                        color = mDirColor
                                    )
                                }
                                Text(
                                    text = "${match.matchScorePct.toInt()}% MATCH",
                                    style = MaterialTheme.typography.labelSmall,
                                    fontWeight = FontWeight.Bold,
                                    color = AccentBlue
                                )
                            }

                            // WHY MATCHED Panel (Section 4 & 9)
                            OpheliaGlassPanel(backgroundColor = colors.surface) {
                                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    Text(
                                        text = "WHY MATCHED",
                                        style = MaterialTheme.typography.labelSmall,
                                        fontWeight = FontWeight.Bold,
                                        color = colors.mutedText,
                                        fontSize = 9.sp
                                    )
                                    Text(
                                        text = match.whyMatched,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = colors.primaryText,
                                        fontSize = 11.sp
                                    )
                                }
                            }

                            // Deterministic Evidence Strip
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(4.dp)
                            ) {
                                val ev = match.deterministicEvidence
                                listOf(
                                    "BREAKOUT" to ev.breakout,
                                    "RETEST" to ev.retest,
                                    "CVD ${ev.cvd}" to (ev.cvd == "ALIGNED"),
                                    "RVOL ${String.format(Locale.US, "%.1f", ev.rvol)}" to (ev.rvol >= 1.0),
                                    "STRUCTURE" to true,
                                    "VWAP" to true
                                ).forEach { (label, ok) ->
                                    Box(
                                        modifier = Modifier
                                            .clip(RoundedCornerShape(4.dp))
                                            .background(if (ok) BullishGreen.copy(alpha = 0.12f) else colors.surfaceElevated)
                                            .border(0.5.dp, if (ok) BullishGreen.copy(alpha = 0.35f) else colors.border, RoundedCornerShape(4.dp))
                                            .padding(horizontal = 4.dp, vertical = 2.dp)
                                    ) {
                                        Text(text = label, fontSize = 8.sp, fontWeight = FontWeight.Bold, color = if (ok) BullishGreen else colors.mutedText)
                                    }
                                }
                            }

                            // Three Quality Layers (Section 10)
                            val ql = match.qualityLayers
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text("AGENT BIAS", fontSize = 9.sp, color = colors.mutedText)
                                    Text(ql.tradingAgentsDecision, fontWeight = FontWeight.Bold, fontSize = 11.sp, color = if (ql.tradingAgentsDecision == match.direction) BullishGreen else colors.secondaryText)
                                }
                                Column {
                                    Text("OPHELIA ML", fontSize = 9.sp, color = colors.mutedText)
                                    Text("${ql.qwenDecision} (${ql.aiConfidencePct.toInt()}%)", fontWeight = FontWeight.Bold, fontSize = 11.sp, color = if (ql.qwenDecision == match.direction) BullishGreen else colors.secondaryText)
                                }
                                Column {
                                    Text("RISK VALID", fontSize = 9.sp, color = colors.mutedText)
                                    Text(ql.deterministicValidationStatus, fontWeight = FontWeight.Bold, fontSize = 11.sp, color = if (ql.deterministicValidation) BullishGreen else BearishRed)
                                }
                                Column(horizontalAlignment = Alignment.End) {
                                    Text("AGREEMENT", fontSize = 9.sp, color = colors.mutedText)
                                    Text("${String.format(Locale.US, "%.0f", match.qualityLayers.confidenceAgreementPct)}%", fontWeight = FontWeight.Bold, fontSize = 11.sp, color = AccentBlue)
                                }
                            }

                            // Simulated Trade Geometry & Outcome (% and R ONLY — NO USDT)
                            OpheliaGlassPanel {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Column {
                                        Text("OUTCOME", fontSize = 9.sp, color = colors.mutedText)
                                        Text(match.outcome, fontWeight = FontWeight.Black, fontSize = 12.sp, color = outcomeColor)
                                    }
                                    Column {
                                        Text("RESULT %", fontSize = 9.sp, color = colors.mutedText)
                                        Text("${if (match.resultPct >= 0) "+" else ""}${String.format(Locale.US, "%.2f", match.resultPct)}%", fontWeight = FontWeight.Bold, fontSize = 12.sp, color = if (match.resultPct >= 0) BullishGreen else BearishRed)
                                    }
                                    Column {
                                        Text("RESULT R", fontSize = 9.sp, color = colors.mutedText)
                                        Text("${if (match.resultR >= 0) "+" else ""}${String.format(Locale.US, "%.2f", match.resultR)}R", fontWeight = FontWeight.Bold, fontSize = 12.sp, color = if (match.resultR >= 0) BullishGreen else BearishRed)
                                    }
                                    Column(horizontalAlignment = Alignment.End) {
                                        Text("MAE / MFE", fontSize = 9.sp, color = colors.mutedText)
                                        Text("${String.format(Locale.US, "%.1f", match.maePct)}% / ${String.format(Locale.US, "%.1f", match.mfePct)}%", fontSize = 10.sp, color = colors.secondaryText)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        else -> {}
    }
}

@Composable
private fun RenderDeterministicBacktestView(
    vm: BacktestViewModel,
    detState: UiState<BacktestResponseDto>,
    context: android.content.Context,
    colors: OpheliaSemanticColors
) {
    when (val s = detState) {
        is UiState.Loading -> {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
                    Text("Loading 48h deterministic backtest...", color = colors.mutedText, fontSize = 12.sp)
                }
            }
        }
        is UiState.Error -> {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("Error: ${s.message}", color = BearishRed, fontWeight = FontWeight.Bold)
                    OpheliaButton(text = "RETRY", onClick = { vm.fetchDeterministicBacktest() })
                }
            }
        }
        is UiState.Success -> {
            val report = s.data
            val metrics = report.metrics

            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                // Secondary Research System Notice
                item {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(10.dp))
                            .background(AccentBlue.copy(alpha = 0.10f))
                            .border(1.dp, AccentBlue.copy(alpha = 0.35f), RoundedCornerShape(10.dp))
                            .padding(12.dp)
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Icon(Icons.Filled.Info, contentDescription = null, tint = AccentBlue, modifier = Modifier.size(18.dp))
                            Text(
                                text = "DETERMINISTIC STRATEGY BACKTEST (SECONDARY RESEARCH): Tests pure Ophelia technical strategy state machine without TradingAgents or Ophelia ML Intelligence reasoning.",
                                style = MaterialTheme.typography.bodySmall,
                                fontSize = 11.sp,
                                color = colors.primaryText,
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }
                }

                // Simulation Controls & Scope
                item {
                    OpheliaGlassCard(level = GlassLevel.L1) {
                        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text("SIMULATION WINDOW", style = MaterialTheme.typography.labelSmall, color = colors.mutedText)
                                    Text("Last 48 Hours (Closed Bars)", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold, color = colors.primaryText)
                                }
                                OpheliaStatusBadge(
                                    status = report.label,
                                    color = AccentBlue,
                                    showDot = true
                                )
                            }

                            OpheliaDivider()

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Column {
                                    Text("CAPITAL", style = MaterialTheme.typography.labelSmall, color = colors.mutedText, fontSize = 10.sp)
                                    Text("${report.scope.initialCapitalUsdt.toInt()} USDT", fontWeight = FontWeight.Bold, fontSize = 12.sp, color = colors.primaryText)
                                }
                                Column {
                                    Text("RISK/TRADE", style = MaterialTheme.typography.labelSmall, color = colors.mutedText, fontSize = 10.sp)
                                    Text("${String.format(Locale.US, "%.1f", report.scope.riskPctPerTrade * 100.0)}%", fontWeight = FontWeight.Bold, fontSize = 12.sp, color = colors.primaryText)
                                }
                                Column {
                                    Text("LEVERAGE", style = MaterialTheme.typography.labelSmall, color = colors.mutedText, fontSize = 10.sp)
                                    Text("${report.scope.leverage.toInt()}x", fontWeight = FontWeight.Bold, fontSize = 12.sp, color = MaterialTheme.colorScheme.primary)
                                }
                                Column {
                                    Text("MAX POS", style = MaterialTheme.typography.labelSmall, color = colors.mutedText, fontSize = 10.sp)
                                    Text("${report.scope.maxOpenTrades} Global", fontWeight = FontWeight.Bold, fontSize = 12.sp, color = colors.primaryText)
                                }
                                Column(horizontalAlignment = Alignment.End) {
                                    Text("ASSETS", style = MaterialTheme.typography.labelSmall, color = colors.mutedText, fontSize = 10.sp)
                                    Text("5 Watchlist", fontWeight = FontWeight.Bold, fontSize = 12.sp, color = AccentTeal)
                                }
                            }

                            Button(
                                onClick = {
                                    vm.runDeterministicBacktest { msg ->
                                        Toast.makeText(context, msg, Toast.LENGTH_LONG).show()
                                    }
                                },
                                enabled = !vm.isRunningDeterministic,
                                modifier = Modifier.fillMaxWidth(),
                                shape = RoundedCornerShape(10.dp),
                                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                            ) {
                                if (vm.isRunningDeterministic) {
                                    CircularProgressIndicator(modifier = Modifier.size(16.dp), color = MaterialTheme.colorScheme.onPrimary, strokeWidth = 2.dp)
                                    Spacer(Modifier.width(8.dp))
                                    Text("RUNNING DETERMINISTIC SIMULATION...", fontWeight = FontWeight.Bold, fontSize = 12.sp)
                                } else {
                                    Icon(Icons.Filled.PlayArrow, contentDescription = null, modifier = Modifier.size(18.dp))
                                    Spacer(Modifier.width(6.dp))
                                    Text("RUN 48H DETERMINISTIC BACKTEST", fontWeight = FontWeight.Bold, fontSize = 12.sp)
                                }
                            }
                        }
                    }
                }

                // Deterministic Metrics
                item {
                    OpheliaGlassCard(level = GlassLevel.L1) {
                        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text("DETERMINISTIC PORTFOLIO RESULTS", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = colors.primaryText)
                                Text("${metrics.executedTrades} TRADES", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = AccentBlue)
                            }

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                OpheliaMetric(
                                    label = "Net Return %",
                                    value = "${if (metrics.netReturnPct >= 0) "+" else ""}${String.format(Locale.US, "%.2f", metrics.netReturnPct)}%",
                                    valueColor = if (metrics.netReturnPct >= 0) BullishGreen else BearishRed,
                                    subValue = "ROI: ${String.format(Locale.US, "%.1f", metrics.netRoiPct)}%"
                                )
                                OpheliaMetric(
                                    label = "Net Return R",
                                    value = "${if (metrics.netR >= 0) "+" else ""}${String.format(Locale.US, "%.2f", metrics.netR)}R",
                                    valueColor = if (metrics.netR >= 0) BullishGreen else BearishRed,
                                    subValue = "Expectancy: ${String.format(Locale.US, "%.2f", metrics.expectancyR)}R"
                                )
                                OpheliaMetric(
                                    label = "Win Rate",
                                    value = "${String.format(Locale.US, "%.1f", metrics.winRatePct)}%",
                                    valueColor = if (metrics.winRatePct >= 50.0) BullishGreen else WarningAmber,
                                    subValue = "PF: ${String.format(Locale.US, "%.2f", metrics.profitFactor)}"
                                )
                            }
                        }
                    }
                }
            }
        }
        else -> {}
    }
}
