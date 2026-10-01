package com.ophelia.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Star
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
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import com.ophelia.app.auth.TokenManager
import com.ophelia.app.models.AutomationConfig
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.viewmodels.AutomationViewModel
import com.ophelia.app.ui.viewmodels.UiState
import com.ophelia.app.ui.theme.*

@Composable
fun AutomationListScreen(
    onNavigateToBuilder: () -> Unit,
    onNavigateToMl: () -> Unit = {},
    sharedViewModel: AutomationViewModel? = null
) {
    val context = LocalContext.current
    val tokenManager = remember { TokenManager(context) }

    val viewModel: AutomationViewModel = sharedViewModel ?: viewModel(
        factory = object : ViewModelProvider.Factory {
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                @Suppress("UNCHECKED_CAST")
                return AutomationViewModel(tokenManager) as T
            }
        }
    )

    val automationsState by viewModel.automations.collectAsState()
    val accountCapacity by viewModel.accountCapacity.collectAsState()
    var deletingAutomation by remember { mutableStateOf<AutomationConfig?>(null) }

    LaunchedEffect(Unit) {
        viewModel.fetchAutomations()
        viewModel.fetchCapacity()
    }

    val colors = OpheliaThemeTokens.colors

    if (deletingAutomation != null) {
        OpheliaDialog(
            onDismissRequest = { deletingAutomation = null },
            title = "DELETE AUTOMATION",
            subtitle = "Permanent configuration removal",
            badgeText = "DANGER",
            badgeColor = BearishRed,
            confirmButton = {
                OpheliaDangerButton(
                    text = "CONFIRM DELETE",
                    onClick = {
                        deletingAutomation?.id?.let { viewModel.deleteAutomation(it) }
                        deletingAutomation = null
                    }
                )
            },
            dismissButton = {
                OpheliaOutlinedButton(
                    text = "CANCEL",
                    onClick = { deletingAutomation = null }
                )
            }
        ) {
            Text(
                text = "Are you sure you want to permanently delete automation #${deletingAutomation?.id} (${deletingAutomation?.strategy})?",
                style = MaterialTheme.typography.bodyMedium,
                color = colors.primaryText
            )
        }
    }

    Scaffold(
        containerColor = BackgroundCanvas,
        topBar = {
            OpheliaTopBar(
                title = "STRATEGY AUTOMATIONS",
                subtitle = "Algorithmic Order Engines",
                onRefresh = {
                    viewModel.fetchAutomations()
                    viewModel.fetchCapacity()
                },
                actions = {
                    IconButton(onClick = onNavigateToBuilder) {
                        Icon(
                            imageVector = Icons.Filled.Add,
                            contentDescription = "New Automation",
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
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            item { Spacer(modifier = Modifier.height(4.dp)) }

            // TOP CAPACITY & EXECUTION SLOTS STRIP
            item {
                val cap = accountCapacity
                val configuredCap = cap?.configuredMaxOpenTrades ?: 2
                val openPositions = cap?.openPositionsCount ?: 0
                val activeAutomations = cap?.activeAutomationsCount ?: 0
                val availSlots = cap?.availableExecutionSlots ?: maxOf(0, configuredCap - openPositions)
                val isCapBelowExposure = cap?.capState == "BELOW_EXPOSURE" || configuredCap < openPositions

                OpheliaGlassCard(
                    level = GlassLevel.L2,
                    borderColor = if (isCapBelowExposure) BearishRed.copy(alpha = 0.6f) else AccentBlue.copy(alpha = 0.45f)
                ) {

                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "EXECUTION CAPACITY & SLOTS",
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.Bold,
                                color = colors.secondaryText,
                                letterSpacing = 0.8.sp
                            )
                            OpheliaStatusBadge(
                                status = if (isCapBelowExposure) "CAP BELOW EXPOSURE" else if (availSlots > 0) "SLOTS OPEN" else "CAP FILLED",
                                color = if (isCapBelowExposure) BearishRed else if (availSlots > 0) BullishGreen else WarningAmber,
                                showDot = true
                            )
                        }

                        OpheliaDivider()

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            OpheliaMetric(
                                label = "Active Automations",
                                value = "$activeAutomations",
                                valueColor = AccentBlue,
                                subValue = "Decoupled triggers"
                            )
                            OpheliaMetric(
                                label = "Open Positions",
                                value = "$openPositions / $configuredCap",
                                valueColor = if (isCapBelowExposure) BearishRed else (if (openPositions > 0) WarningAmber else BullishGreen),
                                subValue = "Trade cap: $configuredCap"
                            )
                            OpheliaMetric(
                                label = "Available Slots",
                                value = "$availSlots",
                                valueColor = if (availSlots > 0) BullishGreen else BearishRed,
                                subValue = if (isCapBelowExposure) "Blocked" else "Free slots"
                            )
                        }

                        if (isCapBelowExposure) {
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clip(RoundedCornerShape(6.dp))
                                    .background(BearishRed.copy(alpha = 0.12f))
                                    .border(1.dp, BearishRed.copy(alpha = 0.4f), RoundedCornerShape(6.dp))
                                    .padding(8.dp)
                            ) {
                                Text(
                                    text = "CAP BELOW CURRENT EXPOSURE: Open trades ($openPositions) exceed cap ($configuredCap). Existing positions are preserved; new entries are blocked.",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = BearishRed,
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.SemiBold
                                )
                            }
                        }
                    }
                }
            }

            // TWO EXPLICIT ENTRY POINTS (Sections 14, 15, 17)
            item {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(
                        text = "NEW AUTOMATION PATHS",

                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = colors.mutedText,
                        letterSpacing = 1.sp
                    )

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        // OPTION 1: IMPORT FROM ML SETUP (Raised Liquid Panel)
                        OpheliaGlassCard(
                            level = GlassLevel.L2,
                            modifier = Modifier.weight(1f),
                            borderColor = AccentPurple.copy(alpha = 0.55f),
                            onClick = onNavigateToMl
                        ) {
                            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    Icon(Icons.Filled.Star, contentDescription = null, tint = AccentPurple, modifier = Modifier.size(18.dp))
                                    Text("OPTION 1", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Black, color = AccentPurple)
                                }
                                Text("IMPORT FROM ML SETUP", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold, color = colors.primaryText)
                                Text("Ophelia ML Intelligence advisory review. Preserves ML conditions with NO generic manual VWAP gate.", style = MaterialTheme.typography.bodySmall, fontSize = 10.sp, color = colors.secondaryText, lineHeight = 13.sp)
                            }
                        }

                        // OPTION 2: BUILD MANUALLY (Raised Liquid Panel)
                        OpheliaGlassCard(
                            level = GlassLevel.L2,
                            modifier = Modifier.weight(1f),
                            borderColor = AccentBlue.copy(alpha = 0.55f),
                            onClick = onNavigateToBuilder
                        ) {
                            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    Icon(Icons.Filled.PlayArrow, contentDescription = null, tint = AccentBlue, modifier = Modifier.size(18.dp))
                                    Text("OPTION 2", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Black, color = AccentBlue)
                                }
                                Text("BUILD MANUALLY", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold, color = colors.primaryText)
                                Text("Complete Strategy Builder with custom rules, indicators, targets, and manual VWAP Directional Gate.", style = MaterialTheme.typography.bodySmall, fontSize = 10.sp, color = colors.secondaryText, lineHeight = 13.sp)
                            }
                        }
                    }

                }
            }

            item {
                OpheliaSectionHeader(title = "ACTIVE AUTOMATIONS")
            }

            when (val state = automationsState) {
                is UiState.Loading -> {
                    item {
                        OpheliaLoadingState(
                            modifier = Modifier.fillMaxWidth().padding(vertical = 24.dp),
                            message = "Loading automation engines..."
                        )
                    }
                }
                is UiState.Error -> {
                    item {
                        OpheliaErrorState(
                            message = state.message,
                            onRetry = { viewModel.fetchAutomations() }
                        )
                    }
                }
                is UiState.Success -> {
                    val list = state.data
                    if (list.isEmpty()) {
                        item {
                            OpheliaGlassCard {
                                Box(
                                    modifier = Modifier.fillMaxWidth().padding(24.dp),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Column(
                                        horizontalAlignment = Alignment.CenterHorizontally,
                                        verticalArrangement = Arrangement.spacedBy(8.dp)
                                    ) {
                                        Text(
                                            text = "NO ACTIVE AUTOMATIONS",
                                            style = MaterialTheme.typography.labelMedium,
                                            fontWeight = FontWeight.Bold,
                                            color = colors.mutedText
                                        )
                                        Text(
                                            text = "Choose Option 1 to import a high-probability ML setup or Option 2 to build manually.",
                                            style = MaterialTheme.typography.bodySmall,
                                            color = colors.secondaryText,
                                            fontSize = 11.sp
                                        )
                                    }
                                }
                            }
                        }
                    } else {
                        items(list) { auto ->
                            AutomationCard(
                                auto = auto,
                                onStatusChange = { isChecked ->
                                    auto.id?.let { id ->
                                        viewModel.setAutomationStatus(id, if (isChecked) "ACTIVE" else "PAUSED")
                                    }
                                },
                                onDelete = { deletingAutomation = auto }
                            )
                        }
                    }
                }
                else -> {}
            }

            item { Spacer(modifier = Modifier.height(16.dp)) }
        }
    }
}

@Composable
private fun AutomationCard(
    auto: AutomationConfig,
    onStatusChange: (Boolean) -> Unit,
    onDelete: () -> Unit
) {
    val isActive = auto.status == "ACTIVE"
    val tfStr = if (!auto.timeframe.isNullOrEmpty()) " (${auto.timeframe})" else ""
    val dir = auto.direction ?: auto.directionPref ?: "ANY"
    val isLong = dir.uppercase() == "LONG"
    val dirColor = if (isLong) BullishGreen else (if (dir.uppercase() == "SHORT") BearishRed else AccentBlue)

    val colors = OpheliaThemeTokens.colors

    val isMlImport = auto.strategy?.contains("RETEST", ignoreCase = true) == true ||
            auto.name?.contains("ML", ignoreCase = true) == true

    OpheliaGlassCard(
        level = GlassLevel.L1,
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            // Header: Name, Strategy, Active Switch, Delete Button
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(
                            text = auto.name ?: "Automation #${auto.id}",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = colors.primaryText
                        )
                        OpheliaStatusBadge(
                            status = dir,
                            color = dirColor,
                            showDot = false
                        )
                    }
                    Text(
                        text = "${auto.strategy}$tfStr",
                        style = MaterialTheme.typography.labelSmall,
                        color = if (isMlImport) AccentPurple else AccentBlue
                    )
                }
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Switch(
                        checked = isActive,
                        onCheckedChange = onStatusChange,
                        colors = SwitchDefaults.colors(
                            checkedThumbColor = Color.White,
                            checkedTrackColor = BullishGreen,
                            uncheckedThumbColor = colors.mutedText,
                            uncheckedTrackColor = colors.surfaceElevated
                        )
                    )
                    IconButton(onClick = onDelete) {
                        Icon(
                            imageVector = Icons.Filled.Delete,
                            contentDescription = "Delete",
                            tint = BearishRed.copy(alpha = 0.7f),
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }

            // Source Attribution Tag (Section 31)
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                if (isMlImport) {
                    OpheliaStatusBadge(
                        status = "SOURCE: OPHELIA ML INTELLIGENCE",
                        color = AccentPurple,
                        showDot = true
                    )
                } else {
                    OpheliaStatusBadge(
                        status = "SOURCE: MANUAL",
                        color = AccentBlue,
                        showDot = false
                    )
                }

                OpheliaStatusBadge(
                    status = "DIRECTION: $dir",
                    color = dirColor,
                    showDot = true
                )
            }

            OpheliaDivider()

            // Scope & VWAP Gate Status
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                val scopeText = when {
                    !auto.symbol.isNullOrEmpty() -> auto.symbol
                    !auto.symbols.isNullOrEmpty() -> auto.symbols.joinToString(", ")
                    else -> auto.symbolScope ?: "ALL_WATCHLIST"
                }
                Text(
                    text = "SCOPE: $scopeText",
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.SemiBold,
                    color = colors.primaryText
                )
                val vwapOn = auto.vwapGateEnabled != false
                if (isMlImport) {
                    OpheliaStatusBadge(
                        status = "VWAP GATE: EXCLUDED (ML LOGIC)",
                        color = colors.mutedText,
                        showDot = false
                    )
                } else {
                    OpheliaStatusBadge(
                        status = if (vwapOn) "VWAP GATE: ON" else "VWAP GATE: OFF",
                        color = if (vwapOn) BullishGreen else WarningAmber,
                        showDot = false
                    )
                }
            }

            // Margin & Leverage
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                val marginDisplay = when {
                    auto.fixedMargin != null && auto.fixedMargin > 0 -> "$${auto.fixedMargin} USDT"
                    auto.marginUsdt != null && auto.marginUsdt > 0 -> "$${auto.marginUsdt} USDT"
                    auto.marginPct != null && auto.marginPct > 0 -> "${auto.marginPct}%"
                    auto.marginUsagePct != null && auto.marginUsagePct > 0 -> "${auto.marginUsagePct}%"
                    else -> "25 USDT"
                }
                Text(
                    text = "MARGIN: $marginDisplay • LEVERAGE: ${auto.leverage}x",
                    style = MaterialTheme.typography.labelSmall,
                    color = colors.secondaryText
                )
            }

            // Candidate & Waiting State
            if (!auto.waitingReason.isNullOrBlank() || !auto.candidateState.isNullOrBlank()) {
                val waitText = auto.waitingReason ?: auto.candidateState ?: "WAITING"
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    OpheliaStatusBadge(
                        status = "WAITING: $waitText",
                        color = WarningAmber,
                        showDot = true
                    )
                    if (!auto.positionStatus.isNullOrBlank()) {
                        OpheliaStatusBadge(
                            status = "POS: ${auto.positionStatus}",
                            color = if (auto.positionStatus == "OPEN") BullishGreen else colors.mutedText,
                            showDot = auto.positionStatus == "OPEN"
                        )
                    }
                }
            }

            // Reserved / Occupied Slot Information
            if (auto.slotInfo != null) {
                val sName = auto.slotInfo["name"] as? String ?: "SLOT #${auto.slotInfo["id"]}"
                val sScope = auto.slotInfo["scope"] as? String ?: "ALL"
                val sMargin = auto.slotInfo["allocated_margin_usdt"] ?: auto.slotInfo["margin"] ?: ""
                val sLev = auto.slotInfo["max_leverage"] ?: auto.slotInfo["leverage"] ?: ""
                val sStatus = auto.slotInfo["status"] as? String ?: "OCCUPIED"
                Surface(
                    shape = RoundedCornerShape(6.dp),
                    color = AccentCyan.copy(alpha = 0.08f),
                    border = androidx.compose.foundation.BorderStroke(1.dp, AccentCyan.copy(alpha = 0.3f)),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(modifier = Modifier.padding(horizontal = 8.dp, vertical = 6.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text(
                                text = "SLOT: $sName ($sScope)",
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.Bold,
                                color = AccentCyan
                            )
                            Text(
                                text = sStatus,
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.Bold,
                                color = if (sStatus == "OCCUPIED") BullishGreen else WarningAmber
                            )
                        }
                        Text(
                            text = "Allocated: $$sMargin USDT • Leverage: ${sLev}x",
                            style = MaterialTheme.typography.bodySmall,
                            fontSize = 10.sp,
                            color = colors.secondaryText
                        )
                    }
                }
            }

            // Evaluation Reason & Timestamps
            if (!auto.lastEvalReason.isNullOrBlank() || auto.lastEvaluatedMs != null) {
                val evalTime = if (auto.lastEvaluatedMs != null && auto.lastEvaluatedMs > 0) {
                    val secAgo = maxOf(0L, (System.currentTimeMillis() - auto.lastEvaluatedMs) / 1000)
                    if (secAgo < 60) "${secAgo}s ago" else "${secAgo / 60}m ago"
                } else null

                val reasonText = auto.lastEvalReason ?: "Evaluated"
                Text(
                    text = if (evalTime != null) "EVAL ($evalTime): $reasonText" else "EVAL: $reasonText",
                    style = MaterialTheme.typography.labelSmall,
                    color = colors.mutedText,
                    maxLines = 2,
                    fontSize = 10.sp
                )
            }
        }
    }
}
