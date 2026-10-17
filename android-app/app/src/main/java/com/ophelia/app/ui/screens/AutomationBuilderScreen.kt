package com.ophelia.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.viewmodels.AutomationViewModel
import com.ophelia.app.ui.viewmodels.UiState
import com.ophelia.app.ui.theme.*

@Composable
fun AutomationBuilderScreen(
    viewModel: AutomationViewModel,
    onBack: () -> Unit
) {
    val strategy by viewModel.strategy.collectAsState()
    val selectedStrategies by viewModel.selectedStrategies.collectAsState()
    val selectedTimeframes by viewModel.selectedTimeframes.collectAsState()
    val symbolScope by viewModel.symbolScope.collectAsState()
    val direction by viewModel.direction.collectAsState()
    val vwapGateEnabled by viewModel.vwapGateEnabled.collectAsState()
    val lifecycle by viewModel.lifecycle.collectAsState()

    // Form State
    val marginPct by viewModel.marginPct.collectAsState()
    val isFixedMargin by viewModel.isFixedMargin.collectAsState()
    val leverage by viewModel.leverage.collectAsState()
    val accountCapacity by viewModel.accountCapacity.collectAsState()
    
    // ST/VWAP Risk State
    val stVwapTimeframe by viewModel.stVwapTimeframe.collectAsState()
    val stVwapHardStopPct by viewModel.stVwapHardStopPct.collectAsState()
    val stVwapStructuralVwapEnabled by viewModel.stVwapStructuralVwapEnabled.collectAsState()
    val stVwapStructuralVwapPct by viewModel.stVwapStructuralVwapPct.collectAsState()
    val stVwapStructuralStEnabled by viewModel.stVwapStructuralStEnabled.collectAsState()
    val stVwapStructuralStPct by viewModel.stVwapStructuralStPct.collectAsState()
    val stVwapBreakEven by viewModel.stVwapBreakEven.collectAsState()
    val stVwapTargets by viewModel.stVwapTargets.collectAsState()
    val stVwapTrailingEnabled by viewModel.stVwapTrailingEnabled.collectAsState()
    val stVwapTrailingTrailPct by viewModel.stVwapTrailingTrailPct.collectAsState()

    // EMA Risk State
    val emaTimeframe by viewModel.emaTimeframe.collectAsState()
    val emaHardStopPct by viewModel.emaHardStopPct.collectAsState()
    val emaStructuralEnabled by viewModel.emaStructuralEnabled.collectAsState()
    val emaStructuralPct by viewModel.emaStructuralPct.collectAsState()
    val emaReverseExit by viewModel.emaReverseExit.collectAsState()
    val emaBreakEven by viewModel.emaBreakEven.collectAsState()
    val emaTargets by viewModel.emaTargets.collectAsState()
    val emaTrailingEnabled by viewModel.emaTrailingEnabled.collectAsState()
    val emaTrailingTrailPct by viewModel.emaTrailingTrailPct.collectAsState()

    val saveState by viewModel.saveState.collectAsState()
    val currentMode by viewModel.currentMode.collectAsState()
    var showReviewDialog by remember { mutableStateOf(false) }
    var showSuccessDialog by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        viewModel.fetchCurrentMode()
    }

    LaunchedEffect(saveState) {
        if (saveState is UiState.Success) {
            showReviewDialog = false
            showSuccessDialog = true
        }
    }

    val simState by viewModel.simState.collectAsState()
    var showSimDialog by remember { mutableStateOf(false) }

    LaunchedEffect(simState) {
        if (simState is UiState.Success || simState is UiState.Error) {
            showSimDialog = true
        }
    }

    // 1. STANDARDIZED SIMULATION MODAL
    if (showSimDialog) {
        when (val s = simState) {
            is UiState.Success -> {
                SimulationResultDialog(
                    response = s.data,
                    onDismiss = {
                        showSimDialog = false
                        viewModel.resetSimState()
                    }
                )
            }
            is UiState.Error -> {
                OpheliaDialog(
                    onDismissRequest = {
                        showSimDialog = false
                        viewModel.resetSimState()
                    },
                    title = "SIMULATION FAILED",
                    subtitle = "Historical Lookback Engine",
                    badgeText = "ERROR",
                    badgeColor = BearishRed,
                    confirmButton = {
                        OpheliaButton(
                            text = "DISMISS",
                            onClick = {
                                showSimDialog = false
                                viewModel.resetSimState()
                            }
                        )
                    }
                ) {
                    Text(
                        text = "Simulation error: ${s.message}",
                        style = MaterialTheme.typography.bodyMedium,
                        color = BearishRed
                    )
                }
            }
            else -> {}
        }
    }

    // 2. SUCCESS MODAL
    if (showSuccessDialog) {
        val isLiveMode = currentMode == "LIVE"
        OpheliaDialog(
            onDismissRequest = {
                showSuccessDialog = false
                viewModel.resetSaveState()
                onBack()
            },
            title = "AUTOMATION DEPLOYED",
            subtitle = if (isLiveMode) "Live Algorithmic Order Flow Active" else "Shadow Paper Simulation Active",
            badgeText = if (isLiveMode) "● LIVE EXECUTION" else "● SHADOW ACTIVE",
            badgeColor = if (isLiveMode) BullishGreen else AccentBlue,
            confirmButton = {
                OpheliaButton(
                    text = "VIEW IN AUTOMATIONS",
                    onClick = {
                        showSuccessDialog = false
                        viewModel.resetSaveState()
                        onBack()
                    }
                )
            }
        ) {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
            ) {
                OpheliaGlassPanel(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.padding(OpheliaSpacing.sm),
                        verticalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        Text(
                            "STRATEGY: $strategy",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold,
                            color = TextPrimary
                        )
                        Text(
                            "MODE: ${if (isLiveMode) "LIVE (Real BingX Perpetual Futures)" else "SHADOW (Paper Trading Simulation)"}",
                            style = MaterialTheme.typography.bodySmall,
                            color = if (isLiveMode) BullishGreen else WarningAmber
                        )
                        Text(
                            "SCOPE: $symbolScope | DIRECTION: $direction",
                            style = MaterialTheme.typography.bodySmall,
                            color = TextSecondary
                        )
                        Text(
                            "MARGIN: ${if (isFixedMargin) "$marginPct USDT" else "$marginPct%"} (${leverage}x Leverage)",
                            style = MaterialTheme.typography.bodySmall,
                            color = TextSecondary
                        )
                    }
                }
                Text(
                    text = if (isLiveMode) 
                        "Your strategy is now actively scanning BingX perpetual swap books and will place live orders when entry rules confirm."
                        else "Your strategy is running in shadow mode. Signals will be simulated in real-time without risking real funds.",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary
                )
            }
        }
    }

    // 3. REVIEW & DEPLOY CONFIRMATION MODAL
    if (showReviewDialog) {
        val isLiveMode = currentMode == "LIVE"
        OpheliaDialog(
            onDismissRequest = { 
                if (saveState !is UiState.Loading) {
                    showReviewDialog = false
                    viewModel.resetSaveState()
                }
            },
            title = "CONFIRM AUTOMATION CONFIG",
            subtitle = "Ophelia Algorithmic Strategy Engine",
            badgeText = if (isLiveMode) "● LIVE — REAL BINGX EXECUTION" else "● SHADOW — PAPER SIMULATION",
            badgeColor = if (isLiveMode) BullishGreen else WarningAmber,
            confirmButton = {
                OpheliaButton(
                    text = if (isLiveMode) "CONFIRM & DEPLOY (LIVE)" else "CONFIRM & DEPLOY (SHADOW)",
                    onClick = { viewModel.saveAutomation() },
                    isLoading = saveState is UiState.Loading
                )
            },
            dismissButton = {
                OpheliaOutlinedButton(
                    text = "EDIT",
                    onClick = { 
                        showReviewDialog = false
                        viewModel.resetSaveState()
                    },
                    enabled = saveState !is UiState.Loading
                )
            }
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 440.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
            ) {
                // Inline error display on failure
                if (saveState is UiState.Error) {
                    OpheliaGlassPanel(
                        modifier = Modifier.fillMaxWidth(),
                        borderColor = BearishRed
                    ) {
                        Column(
                            modifier = Modifier.padding(OpheliaSpacing.sm),
                            verticalArrangement = Arrangement.spacedBy(4.dp)
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    Icons.Filled.Warning,
                                    contentDescription = "Error",
                                    tint = BearishRed,
                                    modifier = Modifier.size(16.dp)
                                )
                                Spacer(modifier = Modifier.width(6.dp))
                                Text(
                                    "DEPLOYMENT REJECTED",
                                    style = MaterialTheme.typography.labelSmall,
                                    fontWeight = FontWeight.Bold,
                                    color = BearishRed
                                )
                            }
                            Text(
                                text = (saveState as UiState.Error).message,
                                style = MaterialTheme.typography.bodySmall,
                                color = TextPrimary
                            )
                        }
                    }
                }

                OpheliaGlassPanel(modifier = Modifier.fillMaxWidth()) {
                    Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                        Text("STRATEGY: $strategy", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold, color = TextPrimary)
                        Text("MODE: ${if (isLiveMode) "LIVE (REAL BINGX SWAPS)" else "SHADOW (PAPER SIMULATION)"}", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = if (isLiveMode) BullishGreen else WarningAmber)
                        Text("SCOPE: $symbolScope | DIRECTION: $direction", style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                        Text("VWAP GATE: ${if (vwapGateEnabled) "ON (ENFORCED)" else "OFF (DISABLED)"}", style = MaterialTheme.typography.labelSmall, color = if (vwapGateEnabled) BullishGreen else WarningAmber)
                        Text("MARGIN: ${if (isFixedMargin) "$marginPct USDT" else "$marginPct%"} (${leverage}x Leverage)", style = MaterialTheme.typography.labelSmall, color = TextPrimary)
                        Text("LIFECYCLE: $lifecycle", style = MaterialTheme.typography.labelSmall, color = TextMuted)
                    }
                }

                if (strategy == "VWAP_SUPERTREND" || strategy == "BOTH") {
                    OpheliaSectionHeader(title = "ST/VWAP Execution Spec")
                    OpheliaGlassPanel(modifier = Modifier.fillMaxWidth()) {
                        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text("Timeframe: ${stVwapTimeframe}m | Hard Stop: $stVwapHardStopPct%", style = MaterialTheme.typography.labelSmall, color = TextPrimary)
                            if (stVwapStructuralVwapEnabled) Text("VWAP Structural Stop: $stVwapStructuralVwapPct%", style = MaterialTheme.typography.labelSmall, color = AccentTeal)
                            if (stVwapStructuralStEnabled) Text("ST Structural Stop: $stVwapStructuralStPct%", style = MaterialTheme.typography.labelSmall, color = AccentTeal)
                            stVwapTargets.forEachIndexed { i, tp ->
                                Text("TP${i+1}: ${tp.qtyPct}% qty @ ${tp.distancePct}%", style = MaterialTheme.typography.labelSmall, color = BullishGreen)
                            }
                            if (stVwapTrailingEnabled) Text("Trailing: $stVwapTrailingTrailPct%", style = MaterialTheme.typography.labelSmall, color = AccentPurple)
                            if (stVwapBreakEven) Text("Break-Even: ON", style = MaterialTheme.typography.labelSmall, color = WarningAmber)
                        }
                    }
                }

                if (strategy == "EMA_CROSSOVER" || strategy == "BOTH") {
                    OpheliaSectionHeader(title = "EMA Crossover Execution Spec")
                    OpheliaGlassPanel(modifier = Modifier.fillMaxWidth()) {
                        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text("Timeframe: ${emaTimeframe}m | Hard Stop: $emaHardStopPct%", style = MaterialTheme.typography.labelSmall, color = TextPrimary)
                            if (emaStructuralEnabled) Text("EMA20 Structural Stop: $emaStructuralPct%", style = MaterialTheme.typography.labelSmall, color = AccentTeal)
                            if (emaReverseExit) Text("Reverse EMA Exit: ON", style = MaterialTheme.typography.labelSmall, color = AccentTeal)
                            emaTargets.forEachIndexed { i, tp ->
                                Text("TP${i+1}: ${tp.qtyPct}% qty @ ${tp.distancePct}%", style = MaterialTheme.typography.labelSmall, color = BullishGreen)
                            }
                            if (emaTrailingEnabled) Text("Trailing: $emaTrailingTrailPct%", style = MaterialTheme.typography.labelSmall, color = AccentPurple)
                            if (emaBreakEven) Text("Break-Even: ON", style = MaterialTheme.typography.labelSmall, color = WarningAmber)
                        }
                    }
                }
            }
        }
    }

    Scaffold(
        containerColor = BackgroundCanvas,
        topBar = {
            OpheliaTopBar(
                title = "STRATEGY BUILDER",
                subtitle = "Algorithmic Rule Architect",
                onBack = onBack,
                actions = {
                    TextButton(
                        onClick = { viewModel.simulateStrategy() },
                        colors = ButtonDefaults.textButtonColors(contentColor = BullishGreen)
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(4.dp)
                        ) {
                            if (simState is UiState.Loading) {
                                CircularProgressIndicator(modifier = Modifier.size(14.dp), color = BullishGreen, strokeWidth = 2.dp)
                            } else {
                                Icon(Icons.Filled.PlayArrow, contentDescription = null, modifier = Modifier.size(16.dp))
                            }
                            Text(
                                text = "BACKTEST",
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                }
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

            // 1. MARGIN CAPACITY OVERVIEW PANEL
            if (accountCapacity != null) {
                OpheliaGlassCard(
                    level = GlassLevel.L1,
                    modifier = Modifier.fillMaxWidth(),
                    borderColor = AccentBlue.copy(alpha = 0.5f)
                ) {
                    Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "ACCOUNT MARGIN CAPACITY",
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.Bold,
                                color = AccentBlue
                            )
                            Text(
                                text = "Allocatable: $${accountCapacity?.allocatableRemaining ?: 0.0} USDT",
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.Bold,
                                color = BullishGreen
                            )
                        }
                        OpheliaDivider()
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            OpheliaMetric(label = "Exchange Avail", value = "$${accountCapacity?.accountAvailable ?: 0.0}")
                            OpheliaMetric(label = "Auto Reserved", value = "$${accountCapacity?.automationReserved ?: 0.0}", valueColor = WarningAmber)
                            OpheliaMetric(label = "Global Limit", value = "MAX: ${accountCapacity?.maxOpenTrades ?: 4} TRADES", valueColor = AccentBlue)
                        }
                    }
                }
            }

            // 2. STRATEGY ENGINE SELECTION (RESEARCHED CANDIDATES - MULTI-SELECT)
            OpheliaSectionHeader(title = "Strategy Engine (Researched Candidates)")
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
            ) {
                viewModel.strategies.forEach { s ->
                    val label = when (s) {
                        "OPHELIA_COMPOSITE" -> "OPHELIA COMPOSITE"
                        "D_WITHOUT_CVD" -> "D (WITHOUT CVD)"
                        else -> s.replace("_", " ")
                    }
                    val isSelected = selectedStrategies.contains(s)
                    OpheliaChip(
                        text = if (isSelected) "✓ $label" else label,
                        isSelected = isSelected,
                        onClick = { viewModel.toggleStrategy(s) },
                        modifier = Modifier.weight(1f)
                    )
                }
            }

            // 3. SYMBOL SCOPE & DIRECTION
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
            ) {
                // Scope Card
                OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.weight(1f)) {
                    Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                        Text("SCOPE", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold, color = TextPrimary)
                        viewModel.symbolScopes.forEach { scope ->
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier.padding(vertical = 2.dp)
                            ) {
                                RadioButton(
                                    selected = symbolScope == scope,
                                    onClick = { viewModel.symbolScope.value = scope },
                                    colors = RadioButtonDefaults.colors(selectedColor = AccentBlue)
                                )
                                Text(scope.replace("_", " "), style = MaterialTheme.typography.labelMedium, color = TextPrimary)
                            }
                        }
                    }
                }

                // Direction Card
                OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.weight(1f)) {
                    Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                        Text("DIRECTION", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold, color = TextPrimary)
                        viewModel.directions.forEach { dir ->
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier.padding(vertical = 2.dp)
                            ) {
                                RadioButton(
                                    selected = direction == dir,
                                    onClick = { viewModel.direction.value = dir },
                                    colors = RadioButtonDefaults.colors(selectedColor = AccentBlue)
                                )
                                Text(dir, style = MaterialTheme.typography.labelMedium, color = TextPrimary)
                            }
                        }
                    }
                }
            }

            // 5. SYMBOL SELECTOR (If Single or Multiple)
            if (symbolScope == "SINGLE" || symbolScope == "MULTIPLE") {
                val watchlist by viewModel.watchlist.collectAsState()
                val selected by viewModel.selectedSymbols.collectAsState()
                
                OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.fillMaxWidth()) {
                    Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                        Text("SELECT INSTRUMENTS", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold, color = TextPrimary)
                        Text(
                            text = if (symbolScope == "SINGLE") "Select exactly 1 symbol" else "Select 1 or more symbols",
                            style = MaterialTheme.typography.labelSmall,
                            color = TextMuted
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        LazyRow(horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                            items(watchlist.size) { index ->
                                val sym = watchlist[index]
                                OpheliaChip(
                                    text = sym,
                                    isSelected = selected.contains(sym),
                                    onClick = {
                                        if (symbolScope == "SINGLE") {
                                            viewModel.selectedSymbols.value = listOf(sym)
                                        } else {
                                            viewModel.toggleSymbol(sym)
                                        }
                                    }
                                )
                            }
                        }
                    }
                }
            }

            // 6. MARGIN & LEVERAGE
            OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.fillMaxWidth()) {
                Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)) {
                    Text("MARGIN & LEVERAGE ALLOCATION", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold, color = TextPrimary)
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
                    ) {
                        OutlinedTextField(
                            value = marginPct,
                            onValueChange = { viewModel.marginPct.value = it },
                            label = { Text(if (isFixedMargin) "Margin (USDT)" else "Margin (%)") },
                            modifier = Modifier.weight(1f),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = AccentBlue,
                                unfocusedBorderColor = GlassBorderSubtle,
                                focusedTextColor = TextPrimary,
                                unfocusedTextColor = TextPrimary
                            )
                        )
                        OutlinedTextField(
                            value = leverage,
                            onValueChange = { viewModel.leverage.value = it },
                            label = { Text("Leverage (x)") },
                            modifier = Modifier.weight(1f),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = AccentBlue,
                                unfocusedBorderColor = GlassBorderSubtle,
                                focusedTextColor = TextPrimary,
                                unfocusedTextColor = TextPrimary
                            )
                        )
                    }
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(
                                checked = isFixedMargin,
                                onCheckedChange = { viewModel.isFixedMargin.value = it },
                                colors = CheckboxDefaults.colors(checkedColor = AccentBlue)
                            )
                            Text("Use Fixed USDT Amount", style = MaterialTheme.typography.labelMedium, color = TextPrimary)
                        }
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(4.dp)
                        ) {
                            OpheliaChip(
                                text = "CONTINUOUS",
                                isSelected = lifecycle == "CONTINUOUS",
                                onClick = { viewModel.lifecycle.value = "CONTINUOUS" }
                            )
                            OpheliaChip(
                                text = "ONE-SHOT",
                                isSelected = lifecycle == "ONE_SHOT",
                                onClick = { viewModel.lifecycle.value = "ONE_SHOT" }
                            )
                        }
                    }
                }
            }

            // 7. STRATEGY TIMEFRAME & STOP PRESET
            // 6. EXECUTION TIMEFRAMES (MULTI-SELECT)
            OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.fillMaxWidth()) {
                Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)) {
                    Text("EXECUTION TIMEFRAME (MULTI-SELECT)", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold, color = TextPrimary)
                    Text(
                        text = "Primary Execution: 3m, 5m, 15m | Context / Microstructure: 1m, 30m, 1h, 4h",
                        style = MaterialTheme.typography.labelSmall,
                        color = BullishGreen
                    )
                    LazyRow(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)
                    ) {
                        items(viewModel.timeframes.size) { index ->
                            val tf = viewModel.timeframes[index]
                            val label = when {
                                tf >= 60 -> "${tf / 60}h"
                                else -> "${tf}m"
                            }
                            val isSel = selectedTimeframes.contains(tf)
                            OpheliaChip(
                                text = if (isSel) "✓ $label" else label,
                                isSelected = isSel,
                                onClick = { viewModel.toggleTimeframe(tf) }
                            )
                        }
                    }
                }
            }

            // 7. STOP LOSS PRESET (3m/5m -> 0.7%, 15m -> 1.0%, user changeable)
            OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.fillMaxWidth()) {
                Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)) {
                    Text("STOP LOSS PRESET", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold, color = TextPrimary)
                    Text(
                        text = "Defaults: 3m/5m -> 0.7% | 15m -> 1.0% (User Configurable)",
                        style = MaterialTheme.typography.labelSmall,
                        color = BullishGreen
                    )
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)
                    ) {
                        OpheliaChip(
                            text = "0.7% (3m/5m)",
                            isSelected = stVwapHardStopPct == "0.7",
                            onClick = { viewModel.hardStopPct.value = "0.7" },
                            modifier = Modifier.weight(1f)
                        )
                        OpheliaChip(
                            text = "1.0% (15m)",
                            isSelected = stVwapHardStopPct == "1.0",
                            onClick = { viewModel.hardStopPct.value = "1.0" },
                            modifier = Modifier.weight(1f)
                        )
                    }
                    OutlinedTextField(
                        value = stVwapHardStopPct,
                        onValueChange = { viewModel.stVwapHardStopPct.value = it },
                        label = { Text("Configured Stop Loss (%)") },
                        modifier = Modifier.fillMaxWidth(),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = AccentBlue,
                            unfocusedBorderColor = GlassBorderSubtle,
                            focusedTextColor = TextPrimary,
                            unfocusedTextColor = TextPrimary
                        )
                    )

                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = stVwapTrailingEnabled, onCheckedChange = { viewModel.stVwapTrailingEnabled.value = it }, colors = CheckboxDefaults.colors(checkedColor = AccentBlue))
                        Text("Causal 1m Trailing Stop", style = MaterialTheme.typography.labelMedium, modifier = Modifier.weight(1f))
                        OutlinedTextField(
                            value = stVwapTrailingTrailPct,
                            onValueChange = { viewModel.stVwapTrailingTrailPct.value = it },
                            label = { Text("Trail %") },
                            modifier = Modifier.width(90.dp),
                            enabled = stVwapTrailingEnabled
                        )
                    }

                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = stVwapBreakEven, onCheckedChange = { viewModel.stVwapBreakEven.value = it }, colors = CheckboxDefaults.colors(checkedColor = AccentBlue))
                        Text("Break-Even on TP1 Trigger", style = MaterialTheme.typography.labelMedium, color = TextPrimary)
                    }

                    OpheliaSectionHeader(title = "Take Profit Targets (TP1, TP2, TP3)")
                    stVwapTargets.forEachIndexed { index, target ->
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            OutlinedTextField(
                                value = target.distancePct.toString(),
                                onValueChange = { v -> viewModel.updateStVwapTarget(index, v.toDoubleOrNull() ?: 0.0, target.qtyPct) },
                                label = { Text("TP${index + 1} Gain %") },
                                modifier = Modifier.weight(1f)
                            )
                            OutlinedTextField(
                                value = target.qtyPct.toString(),
                                onValueChange = { v -> viewModel.updateStVwapTarget(index, target.distancePct, v.toDoubleOrNull() ?: 0.0) },
                                label = { Text("Qty %") },
                                modifier = Modifier.weight(1f)
                            )
                            IconButton(onClick = { viewModel.removeStVwapTarget(index) }) {
                                Icon(Icons.Filled.Close, contentDescription = "Remove", tint = BearishRed)
                            }
                        }
                    }
                    OpheliaOutlinedButton(
                        text = "+ ADD TAKE PROFIT TARGET",
                        onClick = { viewModel.addStVwapTarget() },
                        modifier = Modifier.fillMaxWidth()
                    )
                }
            }

            // Bottom Deploy Button
            OpheliaButton(
                text = "REVIEW & DEPLOY AUTOMATION",
                onClick = { showReviewDialog = true },
                modifier = Modifier.fillMaxWidth()
            )

            Spacer(modifier = Modifier.height(OpheliaSpacing.xxl))
        }
    }
}
