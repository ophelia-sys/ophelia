package com.ophelia.app.ui.screens

import android.widget.Toast
import kotlin.math.round
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
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
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ophelia.app.models.*
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AutonomousTradingScreen(
    onBack: () -> Unit,
    isAdminRole: Boolean = true
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var currentTerminalTab by remember { mutableStateOf(0) }
    var summary by remember { mutableStateOf<AutonomousSlotsSummaryResponse?>(null) }
    var replication by remember { mutableStateOf<ReplicationStatusResponse?>(null) }
    var isLoading by remember { mutableStateOf(true) }
    var isTogglingMaster by remember { mutableStateOf(false) }
    var isTogglingCopy by remember { mutableStateOf(false) }

    var isAutonomousExpanded by remember { mutableStateOf(true) }
    var isReplicationExpanded by remember { mutableStateOf(true) }

    var showAddDialog by remember { mutableStateOf(false) }
    var editingSlot by remember { mutableStateOf<AutonomousTradeSlotDto?>(null) }
    var slotToDelete by remember { mutableStateOf<AutonomousTradeSlotDto?>(null) }

    var diagnosticsPipeline by remember { mutableStateOf<List<AutomationPipelineItemDto>>(emptyList()) }
    var isLoadingPipeline by remember { mutableStateOf(false) }
    var timesfmDiagnostics by remember { mutableStateOf<TimesFmDiagnosticsResponse?>(null) }
    var isTimesfmExpanded by remember { mutableStateOf(false) }
    var microstructureSummary by remember { mutableStateOf<MicrostructureSummaryResponse?>(null) }
    var isMicrostructureExpanded by remember { mutableStateOf(false) }

    fun refreshPipeline() {
        scope.launch {
            isLoadingPipeline = true
            try {
                val res = RetrofitClient.api.getAutomationPipelineDiagnostics()
                diagnosticsPipeline = res.pipeline
            } catch (e: Exception) {
                Toast.makeText(context, "Pipeline diagnostics error: ${e.message}", Toast.LENGTH_SHORT).show()
            } finally {
                isLoadingPipeline = false
            }
        }
    }

    fun refreshData() {
        scope.launch {
            isLoading = true
            try {
                summary = RetrofitClient.api.getAutonomousSlots()
                try {
                    replication = RetrofitClient.api.getReplicationStatus()
                } catch (_: Exception) {}
                try {
                    timesfmDiagnostics = RetrofitClient.api.getTimesFmDiagnostics()
                } catch (_: Exception) {}
                try {
                    microstructureSummary = RetrofitClient.api.getMicrostructureSummary("BTC-USDT")
                } catch (_: Exception) {}
            } catch (e: Exception) {
                Toast.makeText(context, "Error loading autonomous status: ${e.message}", Toast.LENGTH_SHORT).show()
            } finally {
                isLoading = false
            }
        }
    }

    LaunchedEffect(Unit) {
        refreshData()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            if (currentTerminalTab == 0) "Manual Order Terminal" else "Autonomous Trading & Copy",
                            fontSize = 18.sp,
                            fontWeight = FontWeight.Bold,
                            color = PrimaryText
                        )
                        Text(
                            if (currentTerminalTab == 0) "Unified Terminal • Crypto • US Equities • Gold" else "Dynamic Trade Slots • 24/7 VPS Position Manager",
                            fontSize = 11.sp,
                            color = SecondaryText
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back", tint = PrimaryText)
                    }
                },
                actions = {
                    IconButton(onClick = { refreshData() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = AccentCyan)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = BackgroundDark)
            )
        },
        containerColor = BackgroundDark
    ) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            TabRow(
                selectedTabIndex = currentTerminalTab,
                containerColor = CardBackground,
                contentColor = AccentCyan
            ) {
                Tab(
                    selected = currentTerminalTab == 0,
                    onClick = { currentTerminalTab = 0 },
                    text = { Text("MANUAL ORDER", fontSize = 11.sp, fontWeight = FontWeight.Bold) }
                )
                Tab(
                    selected = currentTerminalTab == 1,
                    onClick = { currentTerminalTab = 1 },
                    text = { Text("ML SLOTS & COPY", fontSize = 11.sp, fontWeight = FontWeight.Bold) }
                )
                Tab(
                    selected = currentTerminalTab == 2,
                    onClick = {
                        currentTerminalTab = 2
                        refreshPipeline()
                    },
                    text = { Text("DIAGNOSTICS", fontSize = 11.sp, fontWeight = FontWeight.Bold) }
                )
            }

            when (currentTerminalTab) {
                0 -> ManualOrderTerminalContent(isAdmin = isAdminRole)
                1 -> {
                if (isLoading && summary == null) {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = AccentCyan)
                    }
                } else {
                    val data = summary
                    val rep = replication

                    LazyColumn(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(horizontal = 16.dp),
                        verticalArrangement = Arrangement.spacedBy(14.dp)
                    ) {
                item { Spacer(Modifier.height(4.dp)) }

                // ==========================================
                // COLLAPSIBLE 1: AUTONOMOUS TRADING SLOTS
                // ==========================================
                item {
                    GlassCard(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { isAutonomousExpanded = !isAutonomousExpanded },
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(
                                        if (isAutonomousExpanded) Icons.Default.KeyboardArrowDown else Icons.Default.KeyboardArrowRight,
                                        contentDescription = null,
                                        tint = AccentCyan,
                                        modifier = Modifier.size(24.dp)
                                    )
                                    Spacer(Modifier.width(8.dp))
                                    Column {
                                        Text(
                                            "AUTONOMOUS TRADING",
                                            fontSize = 14.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = PrimaryText,
                                            letterSpacing = 1.sp
                                        )
                                        Text(
                                            "Slots: ${data?.enabledSlots ?: 0} / ${data?.totalSlots ?: 0} ACTIVE • ${data?.availableSlots ?: 0} Available",
                                            fontSize = 11.sp,
                                            color = AccentGreen
                                        )
                                    }
                                }

                                val globalOn = data?.globalEnabled ?: true
                                Surface(
                                    shape = RoundedCornerShape(6.dp),
                                    color = if (globalOn) AccentGreen.copy(alpha = 0.15f) else Color(0xFFEF4444).copy(alpha = 0.15f),
                                    border = androidx.compose.foundation.BorderStroke(1.dp, if (globalOn) AccentGreen.copy(alpha = 0.4f) else Color(0xFFEF4444).copy(alpha = 0.4f))
                                ) {
                                    Text(
                                        if (globalOn) "SYSTEM ON" else "SYSTEM OFF",
                                        fontSize = 10.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = if (globalOn) AccentGreen else Color(0xFFEF4444),
                                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                                    )
                                }
                            }

                            if (isAutonomousExpanded) {
                                Spacer(Modifier.height(14.dp))
                                Divider(color = BorderColor.copy(alpha = 0.3f))
                                Spacer(Modifier.height(12.dp))

                                // Master Switch Row (Admin switch, user indicator)
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Column(modifier = Modifier.weight(1f)) {
                                        Text(
                                            "GLOBAL EXECUTION AUTHORITY",
                                            fontSize = 11.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = SecondaryText
                                        )
                                        Text(
                                            if (data?.globalEnabled == true) "24/7 VPS Daemon Evaluating Opportunities" else "Autonomous Execution Paused",
                                            fontSize = 12.sp,
                                            color = PrimaryText
                                        )
                                    }
                                    if (isAdminRole && data?.isAdmin != false) {
                                        Switch(
                                            checked = data?.globalEnabled ?: true,
                                            enabled = !isTogglingMaster,
                                            onCheckedChange = { newState ->
                                                scope.launch {
                                                    isTogglingMaster = true
                                                    try {
                                                        RetrofitClient.api.toggleAutonomousMaster(
                                                            ToggleAutonomousMasterRequest(enabled = newState)
                                                        )
                                                        refreshData()
                                                    } catch (e: Exception) {
                                                        Toast.makeText(context, "Failed: ${e.message}", Toast.LENGTH_SHORT).show()
                                                    } finally {
                                                        isTogglingMaster = false
                                                    }
                                                }
                                            },
                                            colors = SwitchDefaults.colors(
                                                checkedThumbColor = Color.White,
                                                checkedTrackColor = AccentGreen
                                            )
                                        )
                                    }
                                }

                                Spacer(Modifier.height(8.dp))
                                Text(
                                    text = "SYSTEM MAX CONCURRENT: ${data?.systemMaxSlots ?: 4} | USER CONFIGURED: ${data?.totalSlots ?: 0}",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = TextMuted
                                )
                                Spacer(Modifier.height(8.dp))

                                // Metrics Grid
                                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                    MetricColumn("CONFIGURED", "${data?.totalSlots ?: 0}", AccentCyan)
                                    MetricColumn("AVAILABLE", "${data?.availableSlots ?: 0}", AccentGreen)
                                    MetricColumn("OCCUPIED", "${data?.occupiedSlots ?: 0}", Color(0xFFF59E0B))
                                    MetricColumn("AUTHORIZED", "${data?.totalAuthorizedMarginUsdt ?: 0.0} USDT", PrimaryText)
                                    MetricColumn("ALLOCATED", "${data?.reservedMarginUsdt ?: 0.0} USDT", Color(0xFFA855F7))
                                }
                            }
                        }
                    }
                }

                // ==========================================
                // COLLAPSIBLE 2: COPY OPHELIA TRADES
                // ==========================================
                item {
                    GlassCard(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { isReplicationExpanded = !isReplicationExpanded },
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(
                                        if (isReplicationExpanded) Icons.Default.KeyboardArrowDown else Icons.Default.KeyboardArrowRight,
                                        contentDescription = null,
                                        tint = AccentCyan,
                                        modifier = Modifier.size(24.dp)
                                    )
                                    Spacer(Modifier.width(8.dp))
                                    Column {
                                        Text(
                                            "COPY OPHELIA TRADES",
                                            fontSize = 14.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = PrimaryText,
                                            letterSpacing = 1.sp
                                        )
                                        Text(
                                            "Master: OPHELIA • ${if (rep?.copyEnabled == true) "ENABLED" else "PAUSED"}",
                                            fontSize = 11.sp,
                                            color = if (rep?.copyEnabled == true) AccentGreen else SecondaryText
                                        )
                                    }
                                }

                                Switch(
                                    checked = rep?.copyEnabled ?: false,
                                    enabled = !isTogglingCopy,
                                    onCheckedChange = { newState ->
                                        scope.launch {
                                            isTogglingCopy = true
                                            try {
                                                RetrofitClient.api.updateUserCopySettings(
                                                    UserCopySettingsRequest(copyEnabled = newState)
                                                )
                                                refreshData()
                                                Toast.makeText(context, "Copy Trading ${if (newState) "ENABLED" else "PAUSED"}", Toast.LENGTH_SHORT).show()
                                            } catch (e: Exception) {
                                                Toast.makeText(context, "Failed: ${e.message}", Toast.LENGTH_SHORT).show()
                                            } finally {
                                                isTogglingCopy = false
                                            }
                                        }
                                    },
                                    colors = SwitchDefaults.colors(
                                        checkedThumbColor = Color.White,
                                        checkedTrackColor = AccentGreen
                                    )
                                )
                            }

                            if (isReplicationExpanded) {
                                Spacer(Modifier.height(14.dp))
                                Divider(color = BorderColor.copy(alpha = 0.3f))
                                Spacer(Modifier.height(12.dp))

                                // Master Status Details
                                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                    MetricColumn("MASTER STATUS", rep?.masterStatus ?: "ONLINE", AccentGreen)
                                    MetricColumn("MASTER TRADES", "${rep?.masterTradesCount ?: 0}", AccentCyan)
                                    MetricColumn("FOLLOWERS", "${rep?.authorizedFollowersCount ?: 0} ACTIVE", Color(0xFF38BDF8))
                                    MetricColumn("TOTAL COPIED", "${rep?.totalExecutions ?: 0}", PrimaryText)
                                }

                                Spacer(Modifier.height(14.dp))
                                Text(
                                    "ACTIVE COPIED TRADES",
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = SecondaryText,
                                    letterSpacing = 1.sp
                                )
                                Spacer(Modifier.height(8.dp))

                                val copied = rep?.activeCopiedTrades ?: emptyList()
                                if (copied.isEmpty()) {
                                    Box(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .clip(RoundedCornerShape(8.dp))
                                            .background(Color.White.copy(alpha = 0.03f))
                                            .padding(16.dp),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Text(
                                            "No active copy trades running. Follower slots are standing by.",
                                            color = SecondaryText,
                                            fontSize = 12.sp
                                        )
                                    }
                                } else {
                                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                        copied.forEach { c ->
                                            CopiedTradeRow(c)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // ==========================================
                // COLLAPSIBLE 3: TIMESFM 3.0 DIAGNOSTICS (SHADOW)
                // ==========================================
                item {
                    GlassCard(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { isTimesfmExpanded = !isTimesfmExpanded },
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(
                                        if (isTimesfmExpanded) Icons.Default.KeyboardArrowDown else Icons.Default.KeyboardArrowRight,
                                        contentDescription = null,
                                        tint = AccentCyan,
                                        modifier = Modifier.size(24.dp)
                                    )
                                    Spacer(Modifier.width(8.dp))
                                    Column {
                                        Row(verticalAlignment = Alignment.CenterVertically) {
                                            Text(
                                                "TIMESFM 3.0 DIAGNOSTICS",
                                                fontSize = 14.sp,
                                                fontWeight = FontWeight.Bold,
                                                color = PrimaryText,
                                                letterSpacing = 1.sp
                                            )
                                            Spacer(Modifier.width(8.dp))
                                            OpheliaStatusBadge(
                                                status = "SHADOW",
                                                color = AccentCyan,
                                                showDot = false
                                            )
                                        }
                                        Text(
                                            "google/timesfm-3.0-pytorch • ${timesfmDiagnostics?.lifecycleState ?: "READY"}",
                                            fontSize = 11.sp,
                                            color = if (timesfmDiagnostics?.modelLoaded == true) AccentGreen else WarningAmber
                                        )
                                    }
                                }
                            }

                            if (isTimesfmExpanded) {
                                Spacer(Modifier.height(14.dp))
                                Divider(color = BorderColor.copy(alpha = 0.3f))
                                Spacer(Modifier.height(12.dp))

                                // Section 1: SYSTEM MODEL HEALTH
                                Text(
                                    "SYSTEM MODEL HEALTH",
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = AccentCyan,
                                    letterSpacing = 1.sp
                                )
                                Spacer(Modifier.height(6.dp))
                                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                    MetricColumn("MODEL", timesfmDiagnostics?.version ?: "3.0", PrimaryText)
                                    MetricColumn("STATE", timesfmDiagnostics?.lifecycleState ?: "READY", if (timesfmDiagnostics?.modelLoaded == true) AccentGreen else WarningAmber)
                                    MetricColumn("PID", "${timesfmDiagnostics?.providerPid ?: "N/A"}", SecondaryText)
                                    MetricColumn("P50 LAT", "${timesfmDiagnostics?.p50LatencyMs ?: timesfmDiagnostics?.lastInferenceMs ?: 0.0}ms", AccentGreen)
                                    MetricColumn("P95 LAT", "${timesfmDiagnostics?.p95LatencyMs ?: timesfmDiagnostics?.lastInferenceMs ?: 0.0}ms", AccentCyan)
                                }

                                Spacer(Modifier.height(10.dp))
                                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                    Text(
                                        "RAM: ${timesfmDiagnostics?.systemRamAvailableMb ?: 0.0}MB Avail / ${timesfmDiagnostics?.systemRamTotalMb ?: 0.0}MB (${timesfmDiagnostics?.systemRamUsedPct ?: 0.0}%)",
                                        fontSize = 11.sp,
                                        color = SecondaryText
                                    )
                                    Text(
                                        "SWAP: ${timesfmDiagnostics?.systemSwapUsedMb ?: 0.0}MB",
                                        fontSize = 11.sp,
                                        color = SecondaryText
                                    )
                                    Text(
                                        "CPU: ${timesfmDiagnostics?.systemCpuPct ?: 0.0}%",
                                        fontSize = 11.sp,
                                        color = SecondaryText
                                    )
                                }

                                Spacer(Modifier.height(12.dp))
                                Divider(color = BorderColor.copy(alpha = 0.2f))
                                Spacer(Modifier.height(8.dp))

                                // Section 2: FORECAST QUALITY & EVALUATION
                                Text(
                                    "FORECAST QUALITY & EVALUATION",
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFFF59E0B),
                                    letterSpacing = 1.sp
                                )
                                Spacer(Modifier.height(6.dp))
                                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                                    MetricColumn("FORECASTS", "${timesfmDiagnostics?.forecastCount ?: 0}", Color(0xFFF59E0B))
                                    MetricColumn("EVAL COUNT", "${timesfmDiagnostics?.evaluationCount ?: 0}", SecondaryText)
                                    Column {
                                        Text("EVAL STATUS", fontSize = 10.sp, color = SecondaryText)
                                        OpheliaStatusBadge(
                                            status = timesfmDiagnostics?.evaluationStatus ?: "INSUFFICIENT_SAMPLE",
                                            color = WarningAmber,
                                            showDot = false
                                        )
                                    }
                                    Column {
                                        Text("AUTHORITY", fontSize = 10.sp, color = SecondaryText)
                                        Text("DISABLED", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = BearishRed)
                                    }
                                }

                                if (!timesfmDiagnostics?.lastError.isNullOrBlank()) {
                                    Spacer(Modifier.height(8.dp))
                                    Text(
                                        "Last Error: ${timesfmDiagnostics?.lastError}",
                                        fontSize = 11.sp,
                                        color = BearishRed
                                    )
                                }
                            }
                        }
                    }
                }

                // COLLAPSIBLE 4: MICROSTRUCTURE RESEARCH (PHASE 6A & 6B)
                item {
                    val tf = microstructureSummary?.tradeFlow
                    val td = microstructureSummary?.tradeDuration
                    val ob = microstructureSummary?.orderBook
                    val ls = microstructureSummary?.liquidityStress
                    val pi = microstructureSummary?.priceImpact
                    val tox = microstructureSummary?.toxicity
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp),
                        colors = CardDefaults.cardColors(containerColor = SurfaceDark),
                        shape = RoundedCornerShape(12.dp)
                    ) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { isMicrostructureExpanded = !isMicrostructureExpanded },
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(
                                        if (isMicrostructureExpanded) Icons.Default.KeyboardArrowDown else Icons.Default.KeyboardArrowRight,
                                        contentDescription = null,
                                        tint = SecondaryText,
                                        modifier = Modifier.size(20.dp)
                                    )
                                    Spacer(Modifier.width(8.dp))
                                    Column {
                                        Text(
                                            "MICROSTRUCTURE RESEARCH (PHASE 6A, 6B & 6C)",
                                            fontSize = 12.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = PrimaryText,
                                            letterSpacing = 1.sp
                                        )
                                        Text(
                                            "BTC-USDT • RESEARCH ONLY • ZERO TRADING AUTHORITY",
                                            fontSize = 10.sp,
                                            color = AccentCyan
                                        )
                                    }
                                }
                                Box(
                                    modifier = Modifier
                                        .background(Color(0xFF3B82F6).copy(alpha = 0.15f), RoundedCornerShape(4.dp))
                                        .padding(horizontal = 6.dp, vertical = 2.dp)
                                ) {
                                    Text(
                                        pi?.qualityState ?: tox?.qualityState ?: ob?.qualityState ?: tf?.qualityState ?: "RESEARCH",
                                        fontSize = 10.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = Color(0xFF60A5FA)
                                    )
                                }
                            }

                            if (isMicrostructureExpanded) {
                                Spacer(Modifier.height(12.dp))
                                Divider(color = BorderColor.copy(alpha = 0.3f))
                                Spacer(Modifier.height(8.dp))

                                Text("TRADE-FLOW INNOVATION (MODULE 1)", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = AccentCyan)
                                Spacer(Modifier.height(4.dp))
                                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                    MetricColumn("SIGNED FLOW", "${tf?.signedFlow ?: 0.0}", PrimaryText)
                                    MetricColumn("INNOVATION", "${tf?.flowInnovation ?: 0.0}", if ((tf?.flowInnovation ?: 0.0) >= 0) AccentGreen else BearishRed)
                                    MetricColumn("Z-SCORE", "${tf?.flowZscore ?: 0.0}", AccentCyan)
                                    MetricColumn("PERSIST", "${tf?.flowPersistence ?: 0.0}", SecondaryText)
                                }
                                Spacer(Modifier.height(4.dp))
                                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                    Text("Aggressor: ${tf?.aggressorSource ?: "DIRECT"}", fontSize = 10.sp, color = SecondaryText)
                                    Text("Freshness: ${tf?.freshnessState ?: "FRESH"}", fontSize = 10.sp, color = SecondaryText)
                                    Text("Samples: ${tf?.sampleCount ?: 0}", fontSize = 10.sp, color = SecondaryText)
                                }

                                Spacer(Modifier.height(10.dp))
                                Divider(color = BorderColor.copy(alpha = 0.3f))
                                Spacer(Modifier.height(8.dp))

                                Text("TRADE DURATION & ARRIVAL (MODULE 2 - NON-DIRECTIONAL)", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = AccentPurple)
                                Spacer(Modifier.height(4.dp))
                                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                    MetricColumn("DURATION", "${td?.durationMs ?: 0.0}ms", PrimaryText)
                                    MetricColumn("EXPECTED", "${td?.expectedDurationMs ?: 0.0}ms", SecondaryText)
                                    MetricColumn("INTENSITY", "${td?.arrivalIntensity ?: 0.0}/ms", AccentPurple)
                                    MetricColumn("PRESSURE", "${td?.durationPressure ?: 0.0}", AccentCyan)
                                }
                                Spacer(Modifier.height(4.dp))
                                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                    Text("Z-Score: ${td?.durationZscore ?: 0.0}", fontSize = 10.sp, color = SecondaryText)
                                    Text("Persistence: ${td?.persistence ?: 0.0}", fontSize = 10.sp, color = SecondaryText)
                                    Text("Quality: ${td?.qualityState ?: "VALID"}", fontSize = 10.sp, color = AccentGreen)
                                }

                                Spacer(Modifier.height(10.dp))
                                Divider(color = BorderColor.copy(alpha = 0.3f))
                                Spacer(Modifier.height(8.dp))

                                Text("ORDER-BOOK IMBALANCE (MODULE 3)", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = Color(0xFFF59E0B))
                                Spacer(Modifier.height(4.dp))
                                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                    MetricColumn("BID DEPTH", "${ob?.bidDepth ?: 0.0}", AccentGreen)
                                    MetricColumn("ASK DEPTH", "${ob?.askDepth ?: 0.0}", BearishRed)
                                    MetricColumn("OBI (TOP)", "${ob?.obiTop ?: "N/A"}", Color(0xFFF59E0B))
                                    MetricColumn("OBI (L${ob?.depthUsed ?: 10})", "${ob?.obiDepthN ?: "N/A"}", PrimaryText)
                                }
                                Spacer(Modifier.height(4.dp))
                                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                    Text("Levels: L1/L5/L10", fontSize = 10.sp, color = SecondaryText)
                                    Text("Persistence: ${ob?.imbalancePersistence ?: "N/A"}", fontSize = 10.sp, color = SecondaryText)
                                    Text("Freshness: ${ob?.freshnessState ?: "FRESH"}", fontSize = 10.sp, color = SecondaryText)
                                    Text("Quality: ${ob?.qualityState ?: "VALID"}", fontSize = 10.sp, color = AccentGreen)
                                }

                                Spacer(Modifier.height(10.dp))
                                Divider(color = BorderColor.copy(alpha = 0.3f))
                                Spacer(Modifier.height(8.dp))

                                Text("SPREAD & LIQUIDITY STRESS (MODULE 4 - NON-DIRECTIONAL)", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = Color(0xFFEC4899))
                                Spacer(Modifier.height(4.dp))
                                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                    MetricColumn("SPREAD", "${ls?.spread ?: "N/A"}", PrimaryText)
                                    MetricColumn("REL SPREAD", "${if (ls?.relativeSpread != null) String.format("%.5f", ls.relativeSpread) else "N/A"}", SecondaryText)
                                    MetricColumn("SPREAD STRESS", "${ls?.spreadStress ?: "N/A"}", if ((ls?.spreadStress ?: 0.0) > 1.0) BearishRed else AccentGreen)
                                    MetricColumn("DEPTH STRESS", "${ls?.depthStress ?: "N/A"}", AccentCyan)
                                }
                                Spacer(Modifier.height(4.dp))
                                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                    Text("Thinning: ${if (ls?.bookThinning == true) "YES" else if (ls?.bookThinning == false) "NO" else "N/A"}", fontSize = 10.sp, color = if (ls?.bookThinning == true) BearishRed else SecondaryText)
                                    Text("Recovery: ${ls?.liquidityRecoveryState ?: "NOT_AVAILABLE"}", fontSize = 10.sp, color = Color(0xFFEC4899))
                                    Text("Freshness: ${ls?.freshnessState ?: "FRESH"}", fontSize = 10.sp, color = SecondaryText)
                                    Text("Quality: ${ls?.qualityState ?: "VALID"}", fontSize = 10.sp, color = AccentGreen)
                                }

                                Spacer(Modifier.height(10.dp))
                                Divider(color = BorderColor.copy(alpha = 0.3f))
                                Spacer(Modifier.height(8.dp))

                                Text("EMPIRICAL PRICE IMPACT (MODULE 5 - KYLE-INSPIRED)", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = Color(0xFF38BDF8))
                                Spacer(Modifier.height(4.dp))
                                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                    MetricColumn("IMPACT (λ)", "${pi?.impactCoefficient?.let { String.format("%.6f", it) } ?: "N/A"}", PrimaryText)
                                    MetricColumn("R² STABILITY", "${pi?.impactStability?.let { String.format("%.3f", it) } ?: "N/A"}", AccentCyan)
                                    MetricColumn("ASYMMETRY", "${pi?.impactAsymmetry?.let { String.format("%.6f", it) } ?: "N/A"}", Color(0xFFF59E0B))
                                    MetricColumn("FLOW RESP", "${pi?.flowResponse?.let { String.format("%.6f", it) } ?: "N/A"}", SecondaryText)
                                }
                                Spacer(Modifier.height(4.dp))
                                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                    Text("Horizon: ${pi?.horizonSteps ?: 1} step", fontSize = 10.sp, color = SecondaryText)
                                    Text("Buy λ: ${pi?.buyImpact?.let { String.format("%.5f", it) } ?: "N/A"}", fontSize = 10.sp, color = AccentGreen)
                                    Text("Sell λ: ${pi?.sellImpact?.let { String.format("%.5f", it) } ?: "N/A"}", fontSize = 10.sp, color = BearishRed)
                                    Text("Quality: ${pi?.qualityState ?: "INSUFFICIENT_SAMPLE"}", fontSize = 10.sp, color = AccentGreen)
                                }

                                Spacer(Modifier.height(10.dp))
                                Divider(color = BorderColor.copy(alpha = 0.3f))
                                Spacer(Modifier.height(8.dp))

                                Text("TOXICITY & ADVERSE FLOW (MODULE 6 - VPIN-INSPIRED)", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = Color(0xFFA78BFA))
                                Spacer(Modifier.height(4.dp))
                                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                    MetricColumn("TOXICITY (VPIN)", "${tox?.toxicityMetric?.let { String.format("%.3f", it) } ?: "N/A"}", if ((tox?.toxicityMetric ?: 0.0) > 0.5) BearishRed else AccentGreen)
                                    MetricColumn("STATE", "${tox?.toxicityState ?: "NOT_AVAILABLE"}", if (tox?.toxicityState in listOf("TOXIC", "ELEVATED")) BearishRed else AccentGreen)
                                    MetricColumn("FLOW INTENSITY", "${tox?.flowIntensity?.let { String.format("%.3f", it) } ?: "N/A"}", AccentCyan)
                                    MetricColumn("ADVERSE RESP", "${tox?.adversePriceResponse?.let { String.format("%.5f", it) } ?: "N/A"}", SecondaryText)
                                }
                                Spacer(Modifier.height(4.dp))
                                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                    Text("Arrival Stress: ${tox?.tradeArrivalStress?.let { String.format("%.2f", it) } ?: "N/A"}", fontSize = 10.sp, color = SecondaryText)
                                    Text("Spread Ctx: ${tox?.spreadStressContext?.let { String.format("%.2f", it) } ?: "N/A"}", fontSize = 10.sp, color = SecondaryText)
                                    Text("Samples: ${tox?.sampleCount ?: 0}", fontSize = 10.sp, color = SecondaryText)
                                    Text("Quality: ${tox?.qualityState ?: "INSUFFICIENT_SAMPLE"}", fontSize = 10.sp, color = AccentGreen)
                                }
                            }
                        }
                    }
                }

                // ==========================================
                // DYNAMIC TRADE SLOTS HEADER & ADD BUTTON
                // ==========================================
                item {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            "DYNAMIC TRADE SLOTS (${data?.slots?.size ?: 0})",
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold,
                            color = SecondaryText,
                            letterSpacing = 1.sp
                        )

                        // Accessible to BOTH User and Admin
                        Button(
                            onClick = { showAddDialog = true },
                            colors = ButtonDefaults.buttonColors(containerColor = AccentCyan),
                            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp),
                            shape = RoundedCornerShape(8.dp)
                        ) {
                            Icon(Icons.Default.Add, contentDescription = null, tint = BackgroundDark, modifier = Modifier.size(16.dp))
                            Spacer(Modifier.width(4.dp))
                            Text("ADD TRADE SLOT", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = BackgroundDark)
                        }
                    }
                }

                // ==========================================
                // SLOTS LIST RENDERING
                // ==========================================
                val slots = data?.slots ?: emptyList()
                if (slots.isEmpty()) {
                    item {
                        GlassCard(modifier = Modifier.fillMaxWidth()) {
                            Box(modifier = Modifier.padding(32.dp).fillMaxWidth(), contentAlignment = Alignment.Center) {
                                Text("No trade slots configured. Tap '+ ADD TRADE SLOT' to create one.", color = SecondaryText, fontSize = 13.sp)
                            }
                        }
                    }
                } else {
                    items(slots, key = { it.id }) { slot ->
                        SlotCard(
                            slot = slot,
                            canManage = true,
                            onToggleEnabled = { newEnabled ->
                                scope.launch {
                                    try {
                                        RetrofitClient.api.updateAutonomousSlot(
                                            slot.id,
                                            UpdateTradeSlotRequest(enabled = newEnabled)
                                        )
                                        refreshData()
                                    } catch (e: Exception) {
                                        Toast.makeText(context, "Failed: ${e.message}", Toast.LENGTH_SHORT).show()
                                    }
                                }
                            },
                            onEdit = { editingSlot = slot },
                            onDelete = { slotToDelete = slot }
                        )
                    }
                }

                item { Spacer(Modifier.height(24.dp)) }
            }
        }
    }
    2 -> {
        AutomationPipelineDiagnosticsContent(
            pipeline = diagnosticsPipeline,
            isLoading = isLoadingPipeline,
            onRefresh = { refreshPipeline() },
            onRecoverStale = {
                scope.launch {
                    try {
                        val res = RetrofitClient.api.recoverStaleReservations()
                        Toast.makeText(context, "Recovered ${res.recoveredCount} stale slot(s)", Toast.LENGTH_SHORT).show()
                        refreshPipeline()
                    } catch (e: Exception) {
                        Toast.makeText(context, "Recovery error: ${e.message}", Toast.LENGTH_SHORT).show()
                    }
                }
            }
        )
    }
}
}

    // Dialog: Add Trade Slot
    if (showAddDialog) {
        AddSlotDialog(
            onDismiss = { showAddDialog = false },
            onConfirm = { req ->
                scope.launch {
                    try {
                        RetrofitClient.api.createAutonomousSlot(req)
                        Toast.makeText(context, "Slot created successfully", Toast.LENGTH_SHORT).show()
                        showAddDialog = false
                        refreshData()
                    } catch (e: Exception) {
                        Toast.makeText(context, "Error: ${e.message}", Toast.LENGTH_SHORT).show()
                    }
                }
            }
        )
    }

    // Dialog: Edit Trade Slot
    editingSlot?.let { slot ->
        EditSlotDialog(
            slot = slot,
            onDismiss = { editingSlot = null },
            onConfirm = { req ->
                scope.launch {
                    try {
                        RetrofitClient.api.updateAutonomousSlot(slot.id, req)
                        Toast.makeText(context, "Slot updated successfully", Toast.LENGTH_SHORT).show()
                        editingSlot = null
                        refreshData()
                    } catch (e: Exception) {
                        Toast.makeText(context, "Error: ${e.message}", Toast.LENGTH_SHORT).show()
                    }
                }
            }
        )
    }

    // Dialog: Delete Trade Slot
    slotToDelete?.let { slot ->
        AlertDialog(
            onDismissRequest = { slotToDelete = null },
            containerColor = CardBackground,
            title = { Text("Delete ${slot.name}?", color = PrimaryText, fontWeight = FontWeight.Bold) },
            text = { Text("Are you sure you want to delete this trade slot? This action cannot be undone.", color = SecondaryText) },
            confirmButton = {
                Button(
                    onClick = {
                        scope.launch {
                            try {
                                RetrofitClient.api.deleteAutonomousSlot(slot.id)
                                Toast.makeText(context, "Slot deleted", Toast.LENGTH_SHORT).show()
                                slotToDelete = null
                                refreshData()
                            } catch (e: Exception) {
                                Toast.makeText(context, "Failed: ${e.message}", Toast.LENGTH_SHORT).show()
                            }
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFEF4444))
                ) {
                    Text("Delete", color = Color.White, fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                TextButton(onClick = { slotToDelete = null }) { Text("Cancel", color = SecondaryText) }
            }
        )
    }
}
}

@Composable
fun CopiedTradeRow(c: CopiedPositionDto) {
    val statusColor = when (c.status) {
        "SYNCED" -> AccentGreen
        "DELAYED" -> Color(0xFFF59E0B)
        else -> Color(0xFFEF4444)
    }

    Surface(
        shape = RoundedCornerShape(8.dp),
        color = CardBackground.copy(alpha = 0.5f),
        border = androidx.compose.foundation.BorderStroke(1.dp, BorderColor.copy(alpha = 0.3f)),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(c.symbol, fontSize = 13.sp, fontWeight = FontWeight.Bold, color = PrimaryText)
                    Spacer(Modifier.width(6.dp))
                    Surface(
                        shape = RoundedCornerShape(4.dp),
                        color = if (c.side == "LONG") AccentGreen.copy(alpha = 0.2f) else Color(0xFFEF4444).copy(alpha = 0.2f)
                    ) {
                        Text(
                            c.side,
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            color = if (c.side == "LONG") AccentGreen else Color(0xFFEF4444),
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                        )
                    }
                }

                Surface(
                    shape = RoundedCornerShape(4.dp),
                    color = statusColor.copy(alpha = 0.2f)
                ) {
                    Text(
                        c.status,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold,
                        color = statusColor,
                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                    )
                }
            }

            Spacer(Modifier.height(8.dp))

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Text("MASTER ENTRY", fontSize = 9.sp, color = SecondaryText)
                    Text("$${c.masterEntry}", fontSize = 12.sp, fontWeight = FontWeight.Medium, color = PrimaryText)
                }
                Column {
                    Text("YOUR ENTRY", fontSize = 9.sp, color = SecondaryText)
                    Text("$${c.followerEntry}", fontSize = 12.sp, fontWeight = FontWeight.Medium, color = AccentCyan)
                }
                Column {
                    Text("SLIPPAGE", fontSize = 9.sp, color = SecondaryText)
                    Text("${c.slippagePct}%", fontSize = 12.sp, fontWeight = FontWeight.Medium, color = if (c.slippagePct < 0.2) AccentGreen else Color(0xFFF59E0B))
                }
                Column {
                    Text("PNL", fontSize = 9.sp, color = SecondaryText)
                    Text(
                        "${if (c.unrealizedPnl >= 0) "+" else ""}${c.unrealizedPnl} USDT",
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        color = if (c.unrealizedPnl >= 0) AccentGreen else Color(0xFFEF4444)
                    )
                }
            }
        }
    }
}

@Composable
fun SlotCard(
    slot: AutonomousTradeSlotDto,
    canManage: Boolean,
    onToggleEnabled: (Boolean) -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit
) {
    val statusColor = when (slot.status) {
        "AVAILABLE" -> AccentGreen
        "OCCUPIED" -> Color(0xFFF59E0B)
        "RESERVED" -> Color(0xFFA855F7)
        else -> Color(0xFF6B7280)
    }

    GlassCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            // Header Row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Surface(
                        shape = RoundedCornerShape(6.dp),
                        color = statusColor.copy(alpha = 0.15f),
                        border = androidx.compose.foundation.BorderStroke(1.dp, statusColor.copy(alpha = 0.4f))
                    ) {
                        Text(
                            slot.status,
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            color = statusColor,
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp)
                        )
                    }
                    Spacer(Modifier.width(8.dp))
                    Text(
                        slot.name,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Bold,
                        color = PrimaryText
                    )
                    Spacer(Modifier.width(6.dp))
                    Surface(
                        shape = RoundedCornerShape(4.dp),
                        color = Color.White.copy(alpha = 0.08f)
                    ) {
                        Text(
                            slot.slotMode,
                            fontSize = 9.sp,
                            fontWeight = FontWeight.Medium,
                            color = SecondaryText,
                            modifier = Modifier.padding(horizontal = 5.dp, vertical = 2.dp)
                        )
                    }
                }

                if (canManage) {
                    Switch(
                        checked = slot.enabled,
                        onCheckedChange = onToggleEnabled,
                        colors = SwitchDefaults.colors(
                            checkedThumbColor = Color.White,
                            checkedTrackColor = AccentGreen
                        )
                    )
                }
            }

            Spacer(Modifier.height(12.dp))

            // Primary Metrics Row
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Text("ALLOCATED MARGIN", fontSize = 10.sp, color = SecondaryText)
                    Text("${slot.allocatedMarginUsdt} USDT", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = PrimaryText)
                }
                Column {
                    Text("MAX LEVERAGE", fontSize = 10.sp, color = SecondaryText)
                    Text("${slot.maxLeverage.toInt()}x", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = AccentCyan)
                }
                Column {
                    Text("ASSET SCOPE", fontSize = 10.sp, color = SecondaryText)
                    Text(slot.assetScope, fontSize = 13.sp, fontWeight = FontWeight.Bold, color = PrimaryText)
                }
                Column {
                    Text("MAX LOSS", fontSize = 10.sp, color = SecondaryText)
                    Text("${slot.maxLossPct}%", fontSize = 13.sp, fontWeight = FontWeight.Medium, color = Color(0xFFEF4444))
                }
            }

            Spacer(Modifier.height(8.dp))

            // Position Management Rules
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(
                    "Trailing: ${if (slot.trailingEnabled) "${slot.trailingPct}%" else "OFF"}",
                    fontSize = 11.sp,
                    color = if (slot.trailingEnabled) AccentGreen else SecondaryText
                )
                Text(
                    "TP1: ${if (slot.tp1Enabled) "${slot.tp1Pct.toInt()}%" else "OFF"}",
                    fontSize = 11.sp,
                    color = if (slot.tp1Enabled) AccentCyan else SecondaryText
                )
                Text(
                    "Breakeven: ${if (slot.breakevenEnabled) slot.breakevenMode else "OFF"}",
                    fontSize = 11.sp,
                    color = if (slot.breakevenEnabled) AccentGreen else SecondaryText
                )
            }

            // Occupied details
            if (slot.status == "OCCUPIED" && slot.currentPositionId != null) {
                Spacer(Modifier.height(10.dp))
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(8.dp),
                    color = Color(0xFFF59E0B).copy(alpha = 0.1f),
                    border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFFF59E0B).copy(alpha = 0.3f))
                ) {
                    Column(modifier = Modifier.padding(10.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.Lock, contentDescription = null, tint = Color(0xFFF59E0B), modifier = Modifier.size(14.dp))
                            Spacer(Modifier.width(6.dp))
                            Text(
                                "ACTIVE POSITION: ${slot.currentPositionId}",
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFFF59E0B)
                            )
                        }
                        Text(
                            "SLOT LOCKED FOR DURATION OF TRADE • RELEASED UPON EXIT",
                            fontSize = 10.sp,
                            color = SecondaryText
                        )
                    }
                }
            }

            // Action Buttons
            if (canManage) {
                Spacer(Modifier.height(12.dp))
                Divider(color = BorderColor.copy(alpha = 0.3f))
                Spacer(Modifier.height(8.dp))

                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    TextButton(onClick = onEdit) {
                        Icon(Icons.Default.Edit, contentDescription = null, tint = AccentCyan, modifier = Modifier.size(14.dp))
                        Spacer(Modifier.width(4.dp))
                        Text("Edit", fontSize = 12.sp, color = AccentCyan)
                    }
                    Spacer(Modifier.width(8.dp))
                    TextButton(
                        onClick = onDelete,
                        enabled = slot.status != "OCCUPIED"
                    ) {
                        Icon(Icons.Default.Delete, contentDescription = null, tint = if (slot.status == "OCCUPIED") Color.Gray else Color(0xFFEF4444), modifier = Modifier.size(14.dp))
                        Spacer(Modifier.width(4.dp))
                        Text("Delete", fontSize = 12.sp, color = if (slot.status == "OCCUPIED") Color.Gray else Color(0xFFEF4444))
                    }
                }
            }
        }
    }
}

@Composable
fun MetricColumn(label: String, value: String, color: Color) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(value, fontSize = 15.sp, fontWeight = FontWeight.Bold, color = color)
        Text(label, fontSize = 9.sp, color = SecondaryText)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AddSlotDialog(
    onDismiss: () -> Unit,
    onConfirm: (AddTradeSlotRequest) -> Unit
) {
    var name by remember { mutableStateOf("") }
    var marginStr by remember { mutableStateOf("50") }
    var leverageStr by remember { mutableStateOf("5") }
    var selectedScope by remember { mutableStateOf("ALL") }
    var maxLossPctStr by remember { mutableStateOf("10.0") }
    var trailingPctStr by remember { mutableStateOf("1.5") }
    var tp1PctStr by remember { mutableStateOf("50.0") }
    var breakevenEnabled by remember { mutableStateOf(true) }
    var slotMode by remember { mutableStateOf("BOTH") }

    val scopes = listOf("ALL", "CRYPTO", "COMMODITIES", "US_MARKET")
    val modes = listOf("BOTH", "AUTONOMOUS", "COPY_OPHELIA")

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = CardBackground,
        title = { Text("Add Autonomous Trade Slot", color = PrimaryText, fontWeight = FontWeight.Bold, fontSize = 16.sp) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Slot Name (e.g. Slot 3 - US Equities)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )

                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = marginStr,
                        onValueChange = { marginStr = it },
                        label = { Text("Margin (USDT)") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        singleLine = true,
                        modifier = Modifier.weight(1f)
                    )
                    OutlinedTextField(
                        value = leverageStr,
                        onValueChange = { leverageStr = it },
                        label = { Text("Leverage (1-10x)") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        singleLine = true,
                        modifier = Modifier.weight(1f)
                    )
                }

                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = maxLossPctStr,
                        onValueChange = { maxLossPctStr = it },
                        label = { Text("Max Loss %") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        singleLine = true,
                        modifier = Modifier.weight(1f)
                    )
                    OutlinedTextField(
                        value = trailingPctStr,
                        onValueChange = { trailingPctStr = it },
                        label = { Text("Trailing Stop %") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        singleLine = true,
                        modifier = Modifier.weight(1f)
                    )
                }

                Text("Asset Scope", fontSize = 11.sp, color = SecondaryText)
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    scopes.forEach { sc ->
                        FilterChip(
                            selected = (selectedScope == sc),
                            onClick = { selectedScope = sc },
                            label = { Text(sc, fontSize = 9.sp) }
                        )
                    }
                }

                Text("Slot Mode", fontSize = 11.sp, color = SecondaryText)
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    modes.forEach { md ->
                        FilterChip(
                            selected = (slotMode == md),
                            onClick = { slotMode = md },
                            label = { Text(md, fontSize = 9.sp) }
                        )
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    val m = marginStr.toDoubleOrNull() ?: 50.0
                    val lev = leverageStr.toIntOrNull() ?: 5
                    val lossPct = maxLossPctStr.toDoubleOrNull() ?: 10.0
                    val trailPct = trailingPctStr.toDoubleOrNull() ?: 1.5
                    val tp1Pct = tp1PctStr.toDoubleOrNull() ?: 50.0
                    val slotName = if (name.isBlank()) "TRADE SLOT" else name
                    onConfirm(
                        AddTradeSlotRequest(
                            name = slotName,
                            allocatedMarginUsdt = m,
                            maxLeverage = lev,
                            assetScope = selectedScope,
                            maxLossPct = lossPct,
                            trailingPct = trailPct,
                            tp1Pct = tp1Pct,
                            breakevenEnabled = breakevenEnabled,
                            slotMode = slotMode
                        )
                    )
                },
                colors = ButtonDefaults.buttonColors(containerColor = AccentCyan)
            ) {
                Text("Create Slot", color = BackgroundDark, fontWeight = FontWeight.Bold)
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel", color = SecondaryText) }
        }
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EditSlotDialog(
    slot: AutonomousTradeSlotDto,
    onDismiss: () -> Unit,
    onConfirm: (UpdateTradeSlotRequest) -> Unit
) {
    var name by remember { mutableStateOf(slot.name) }
    var marginStr by remember { mutableStateOf(slot.allocatedMarginUsdt.toString()) }
    var leverageStr by remember { mutableStateOf(slot.maxLeverage.toInt().toString()) }
    var selectedScope by remember { mutableStateOf(slot.assetScope) }
    var maxLossPctStr by remember { mutableStateOf(slot.maxLossPct.toString()) }
    var trailingPctStr by remember { mutableStateOf(slot.trailingPct.toString()) }
    var trailingEnabled by remember { mutableStateOf(slot.trailingEnabled) }
    var slotMode by remember { mutableStateOf(slot.slotMode) }

    val scopes = listOf("ALL", "CRYPTO", "COMMODITIES", "US_MARKET")
    val modes = listOf("BOTH", "AUTONOMOUS", "COPY_OPHELIA")

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = CardBackground,
        title = { Text("Edit ${slot.name}", color = PrimaryText, fontWeight = FontWeight.Bold, fontSize = 16.sp) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Slot Name") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )

                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = marginStr,
                        onValueChange = { marginStr = it },
                        label = { Text("Margin (USDT)") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        singleLine = true,
                        modifier = Modifier.weight(1f)
                    )
                    OutlinedTextField(
                        value = leverageStr,
                        onValueChange = { leverageStr = it },
                        label = { Text("Leverage (1-10x)") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        singleLine = true,
                        modifier = Modifier.weight(1f)
                    )
                }

                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = maxLossPctStr,
                        onValueChange = { maxLossPctStr = it },
                        label = { Text("Max Loss %") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        singleLine = true,
                        modifier = Modifier.weight(1f)
                    )
                    OutlinedTextField(
                        value = trailingPctStr,
                        onValueChange = { trailingPctStr = it },
                        label = { Text("Trailing Stop %") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        singleLine = true,
                        modifier = Modifier.weight(1f)
                    )
                }

                Text("Asset Scope", fontSize = 11.sp, color = SecondaryText)
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    scopes.forEach { sc ->
                        FilterChip(
                            selected = (selectedScope == sc),
                            onClick = { selectedScope = sc },
                            label = { Text(sc, fontSize = 9.sp) }
                        )
                    }
                }

                Text("Slot Mode", fontSize = 11.sp, color = SecondaryText)
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    modes.forEach { md ->
                        FilterChip(
                            selected = (slotMode == md),
                            onClick = { slotMode = md },
                            label = { Text(md, fontSize = 9.sp) }
                        )
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    val m = marginStr.toDoubleOrNull() ?: slot.allocatedMarginUsdt
                    val lev = leverageStr.toIntOrNull() ?: slot.maxLeverage.toInt()
                    val lossPct = maxLossPctStr.toDoubleOrNull() ?: slot.maxLossPct
                    val trailPct = trailingPctStr.toDoubleOrNull() ?: slot.trailingPct
                    onConfirm(
                        UpdateTradeSlotRequest(
                            name = name,
                            allocatedMarginUsdt = m,
                            maxLeverage = lev,
                            assetScope = selectedScope,
                            maxLossPct = lossPct,
                            trailingPct = trailPct,
                            trailingEnabled = trailingEnabled,
                            slotMode = slotMode
                        )
                    )
                },
                colors = ButtonDefaults.buttonColors(containerColor = AccentCyan)
            ) {
                Text("Save Changes", color = BackgroundDark, fontWeight = FontWeight.Bold)
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel", color = SecondaryText) }
        }
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ManualOrderTerminalContent(isAdmin: Boolean = true) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var searchQuery by remember { mutableStateOf("") }
    var searchResults by remember { mutableStateOf<List<MarketSearchItem>>(emptyList()) }
    var isSearching by remember { mutableStateOf(false) }

    var selectedSymbol by remember { mutableStateOf("BTC-USDT") }
    var selectedBingxSymbol by remember { mutableStateOf("BTC-USDT") }
    var selectedAssetClass by remember { mutableStateOf("CRYPTO") }
    var selectedVenueProduct by remember { mutableStateOf("STANDARD_PERPETUAL") }
    var isResolved by remember { mutableStateOf(true) }
    var isTradable by remember { mutableStateOf(true) }
    var side by remember { mutableStateOf("LONG") }
    var orderType by remember { mutableStateOf("MARKET") }

    var entryPriceStr by remember { mutableStateOf("65000.0") }
    var marginStr by remember { mutableStateOf("50.0") }
    var leverage by remember { mutableStateOf(5) }
    var slStr by remember { mutableStateOf("") }
    var tp1Str by remember { mutableStateOf("") }
    var tp2Str by remember { mutableStateOf("") }
    var tp3Str by remember { mutableStateOf("") }
    var trailingEnabled by remember { mutableStateOf(false) }
    var trailingPctStr by remember { mutableStateOf("1.5") }
    var moveSlToCost by remember { mutableStateOf(true) }

    var isSubmitting by remember { mutableStateOf(false) }
    var orderResult by remember { mutableStateOf<ManualOrderResponse?>(null) }

    LaunchedEffect(searchQuery) {
        if (searchQuery.trim().isNotEmpty()) {
            isSearching = true
            try {
                val res = RetrofitClient.api.searchMarket(searchQuery.trim())
                searchResults = res.results
            } catch (_: Exception) {
                searchResults = emptyList()
            } finally {
                isSearching = false
            }
        } else {
            searchResults = emptyList()
        }
    }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        item { Spacer(Modifier.height(4.dp)) }

        // 1. Unified Search
        item {
            GlassCard(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(14.dp)) {
                    Text(
                        "UNIFIED INSTRUMENT SEARCH",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        color = SecondaryText
                    )
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = searchQuery,
                        onValueChange = { searchQuery = it },
                        placeholder = { Text("Type symbol: BTC, NV, AAPL, GOLD...") },
                        leadingIcon = { Icon(Icons.Default.Search, contentDescription = null, tint = AccentCyan) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )

                    if (isSearching) {
                        Spacer(Modifier.height(8.dp))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp, color = AccentCyan)
                            Spacer(Modifier.width(8.dp))
                            Text("Searching Crypto, US, Commodities...", fontSize = 11.sp, color = SecondaryText)
                        }
                    }

                    if (searchResults.isNotEmpty()) {
                        Spacer(Modifier.height(8.dp))
                        Text("Matching Instruments:", fontSize = 10.sp, color = SecondaryText)
                        Spacer(Modifier.height(4.dp))
                        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            searchResults.take(6).forEach { item ->
                                Surface(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clickable {
                                            selectedSymbol = item.symbol
                                            selectedBingxSymbol = item.bingxSymbol
                                            selectedAssetClass = item.assetClass
                                            selectedVenueProduct = item.venueProduct ?: (if (item.assetClass == "CRYPTO") "STANDARD_PERPETUAL" else "TRADFI_PERPETUAL")
                                            isResolved = item.bingxSymbol.isNotEmpty()
                                            isTradable = item.executable
                                            if (item.price > 0) {
                                                entryPriceStr = item.price.toString()
                                            }
                                            searchQuery = ""
                                            searchResults = emptyList()
                                        },
                                    shape = RoundedCornerShape(6.dp),
                                    color = CardBackground,
                                    border = androidx.compose.foundation.BorderStroke(1.dp, BorderColor.copy(alpha = 0.3f))
                                ) {
                                    Row(
                                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Row(verticalAlignment = Alignment.CenterVertically) {
                                            Text(item.symbol, fontSize = 13.sp, fontWeight = FontWeight.Bold, color = PrimaryText)
                                            Spacer(Modifier.width(6.dp))
                                            Surface(
                                                shape = RoundedCornerShape(3.dp),
                                                color = when (item.assetClass) {
                                                    "US_MARKET" -> Color(0xFF38BDF8).copy(alpha = 0.2f)
                                                    "COMMODITIES" -> Color(0xFFF59E0B).copy(alpha = 0.2f)
                                                    else -> AccentGreen.copy(alpha = 0.2f)
                                                }
                                            ) {
                                                Text(
                                                    item.assetClass,
                                                    fontSize = 9.sp,
                                                    fontWeight = FontWeight.Bold,
                                                    color = when (item.assetClass) {
                                                        "US_MARKET" -> Color(0xFF38BDF8)
                                                        "COMMODITIES" -> Color(0xFFF59E0B)
                                                        else -> AccentGreen
                                                    },
                                                    modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp)
                                                )
                                            }
                                        }
                                        Text(
                                            if (item.price > 0) "$${item.price}" else "",
                                            fontSize = 12.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = PrimaryText
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // 2. Order Configuration Card
        item {
            GlassCard(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text("SELECTED ASSET", fontSize = 10.sp, color = SecondaryText)
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(selectedSymbol, fontSize = 18.sp, fontWeight = FontWeight.Bold, color = PrimaryText)
                                Spacer(Modifier.width(8.dp))
                                Surface(
                                    shape = RoundedCornerShape(4.dp),
                                    color = when (selectedAssetClass) {
                                        "US_MARKET", "US_EQUITY" -> Color(0xFF38BDF8).copy(alpha = 0.2f)
                                        "COMMODITIES" -> Color(0xFFF59E0B).copy(alpha = 0.2f)
                                        else -> AccentGreen.copy(alpha = 0.2f)
                                    }
                                ) {
                                    Text(
                                        selectedAssetClass.replace("_", " "),
                                        fontSize = 10.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = when (selectedAssetClass) {
                                            "US_MARKET", "US_EQUITY" -> Color(0xFF38BDF8)
                                            "COMMODITIES" -> Color(0xFFF59E0B)
                                            else -> AccentGreen
                                        },
                                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                    )
                                }
                            }
                            Spacer(Modifier.height(2.dp))
                            Text(
                                "BINGX ${selectedVenueProduct.replace("_", " ")}",
                                fontSize = 10.sp,
                                fontWeight = FontWeight.SemiBold,
                                color = AccentCyan
                            )
                        }
                        Column(horizontalAlignment = Alignment.End) {
                            Surface(
                                shape = RoundedCornerShape(4.dp),
                                color = if (isTradable) CardBackground else Color(0xFFEF4444).copy(alpha = 0.15f),
                                border = androidx.compose.foundation.BorderStroke(1.dp, if (isTradable) BorderColor else Color(0xFFEF4444).copy(alpha = 0.5f))
                            ) {
                                Text(
                                    "VENUE SYMBOL: $selectedBingxSymbol",
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = if (isTradable) PrimaryText else Color(0xFFEF4444),
                                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                                )
                            }
                            Spacer(Modifier.height(4.dp))
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Surface(
                                    shape = RoundedCornerShape(50),
                                    color = if (isResolved && isTradable) AccentGreen else Color(0xFFEF4444),
                                    modifier = Modifier.size(6.dp)
                                ) {}
                                Spacer(Modifier.width(4.dp))
                                Text(
                                    if (isResolved && isTradable) "TRADABLE" else if (!isResolved) "UNRESOLVED" else "SUSPENDED",
                                    fontSize = 9.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = if (isResolved && isTradable) AccentGreen else Color(0xFFEF4444)
                                )
                            }
                        }
                    }

                    Spacer(Modifier.height(14.dp))

                    // Side: LONG / SHORT
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        Button(
                            onClick = { side = "LONG" },
                            modifier = Modifier.weight(1f),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = if (side == "LONG") AccentGreen else CardBackground
                            ),
                            border = androidx.compose.foundation.BorderStroke(1.dp, if (side == "LONG") AccentGreen else BorderColor)
                        ) {
                            Text("BUY / LONG", fontWeight = FontWeight.Bold, color = if (side == "LONG") BackgroundDark else PrimaryText)
                        }
                        Button(
                            onClick = { side = "SHORT" },
                            modifier = Modifier.weight(1f),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = if (side == "SHORT") Color(0xFFEF4444) else CardBackground
                            ),
                            border = androidx.compose.foundation.BorderStroke(1.dp, if (side == "SHORT") Color(0xFFEF4444) else BorderColor)
                        ) {
                            Text("SELL / SHORT", fontWeight = FontWeight.Bold, color = if (side == "SHORT") Color.White else PrimaryText)
                        }
                    }

                    Spacer(Modifier.height(12.dp))

                    // Order Type: MARKET / LIMIT
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf("MARKET", "LIMIT").forEach { t ->
                            FilterChip(
                                selected = (orderType == t),
                                onClick = { orderType = t },
                                label = { Text(t, fontSize = 11.sp, fontWeight = FontWeight.Bold) },
                                modifier = Modifier.weight(1f)
                            )
                        }
                    }

                    Spacer(Modifier.height(10.dp))

                    // Price & Margin
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        OutlinedTextField(
                            value = entryPriceStr,
                            onValueChange = { entryPriceStr = it },
                            label = { Text(if (orderType == "LIMIT") "Limit Price" else "Entry Ref Price") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            singleLine = true,
                            modifier = Modifier.weight(1f)
                        )
                        OutlinedTextField(
                            value = marginStr,
                            onValueChange = { marginStr = it },
                            label = { Text("Margin (USDT)") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            singleLine = true,
                            modifier = Modifier.weight(1f)
                        )
                    }

                    Spacer(Modifier.height(10.dp))

                    // Leverage
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("Leverage: ${leverage}x", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = PrimaryText)
                        val mVal = marginStr.toDoubleOrNull() ?: 0.0
                        Text("Notional: $${round(mVal * leverage)}", fontSize = 12.sp, color = AccentCyan)
                    }
                    Slider(
                        value = leverage.toFloat(),
                        onValueChange = { leverage = it.toInt() },
                        valueRange = 1f..20f,
                        steps = 19,
                        colors = SliderDefaults.colors(thumbColor = AccentCyan, activeTrackColor = AccentCyan)
                    )

                    Spacer(Modifier.height(10.dp))

                    // Stop Loss & TP1
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        OutlinedTextField(
                            value = slStr,
                            onValueChange = { slStr = it },
                            label = { Text("Stop Loss (SL)") },
                            placeholder = { Text("Optional") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            singleLine = true,
                            modifier = Modifier.weight(1f)
                        )
                        OutlinedTextField(
                            value = tp1Str,
                            onValueChange = { tp1Str = it },
                            label = { Text("TP1 (50% partial)") },
                            placeholder = { Text("Optional") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            singleLine = true,
                            modifier = Modifier.weight(1f)
                        )
                    }

                    Spacer(Modifier.height(10.dp))

                    // TP2 & TP3
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        OutlinedTextField(
                            value = tp2Str,
                            onValueChange = { tp2Str = it },
                            label = { Text("TP2 (Optional)") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            singleLine = true,
                            modifier = Modifier.weight(1f)
                        )
                        OutlinedTextField(
                            value = tp3Str,
                            onValueChange = { tp3Str = it },
                            label = { Text("TP3 (Optional)") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            singleLine = true,
                            modifier = Modifier.weight(1f)
                        )
                    }

                    Spacer(Modifier.height(12.dp))

                    // Protective Management Checkboxes
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("Move SL to Cost after TP1", fontSize = 12.sp, color = PrimaryText)
                        Switch(
                            checked = moveSlToCost,
                            onCheckedChange = { moveSlToCost = it },
                            colors = SwitchDefaults.colors(checkedThumbColor = AccentCyan)
                        )
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("Dynamic Trailing Stop", fontSize = 12.sp, color = PrimaryText)
                        }
                        Switch(
                            checked = trailingEnabled,
                            onCheckedChange = { trailingEnabled = it },
                            colors = SwitchDefaults.colors(checkedThumbColor = AccentCyan)
                        )
                    }

                    if (trailingEnabled) {
                        Spacer(Modifier.height(6.dp))
                        OutlinedTextField(
                            value = trailingPctStr,
                            onValueChange = { trailingPctStr = it },
                            label = { Text("Trailing Distance %") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth()
                        )
                    }

                    Spacer(Modifier.height(16.dp))

                    Spacer(Modifier.height(16.dp))

                    // Submit Button with Strict Gating: RESOLVED && TRADABLE && VALIDATED
                    val mVal = marginStr.toDoubleOrNull() ?: 0.0
                    val isValidated = mVal > 0.0 && isResolved && isTradable

                    Button(
                        onClick = {
                            if (!isValidated) {
                                val reason = if (!isResolved) "Instrument not resolved"
                                    else if (!isTradable) "Venue instrument suspended"
                                    else "Please enter a valid margin"
                                Toast.makeText(context, reason, Toast.LENGTH_SHORT).show()
                                return@Button
                            }
                            val px = entryPriceStr.toDoubleOrNull()
                            val sl = slStr.toDoubleOrNull()
                            val tp1 = tp1Str.toDoubleOrNull()
                            val tp2 = tp2Str.toDoubleOrNull()
                            val tp3 = tp3Str.toDoubleOrNull()
                            val trail = if (trailingEnabled) trailingPctStr.toDoubleOrNull() else null

                            scope.launch {
                                isSubmitting = true
                                try {
                                    val req = ManualOrderRequest(
                                        symbol = selectedSymbol,
                                        side = side,
                                        orderType = orderType,
                                        entryPrice = px,
                                        margin = mVal,
                                        leverage = leverage,
                                        sl = sl,
                                        tp1 = tp1,
                                        tp2 = tp2,
                                        tp3 = tp3,
                                        trailingPct = trail,
                                        moveSlToCost = moveSlToCost,
                                        assetClass = selectedAssetClass,
                                        reason = "Manual AUTO Terminal Order"
                                    )
                                    val res = RetrofitClient.api.executeManualOrder(req)
                                    orderResult = res
                                    val oid = res.internalOrderId ?: res.orderId ?: "OK"
                                    Toast.makeText(context, "Order ${res.status}: $oid", Toast.LENGTH_LONG).show()
                                } catch (e: Exception) {
                                    Toast.makeText(context, "Order failed: ${e.message}", Toast.LENGTH_LONG).show()
                                } finally {
                                    isSubmitting = false
                                }
                            }
                        },
                        enabled = !isSubmitting && isValidated,
                        modifier = Modifier.fillMaxWidth().height(48.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = if (side == "LONG") AccentGreen else Color(0xFFEF4444),
                            disabledContainerColor = Color(0xFF374151)
                        )
                    ) {
                        if (isSubmitting) {
                            CircularProgressIndicator(modifier = Modifier.size(20.dp), color = Color.White, strokeWidth = 2.dp)
                        } else {
                            val btnText = if (!isResolved) "INSTRUMENT NOT RESOLVED"
                                else if (!isTradable) "VENUE TRADING SUSPENDED"
                                else "SUBMIT ${side} ORDER (${orderType})"
                            Text(
                                btnText,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Bold,
                                color = if (isValidated && side == "LONG") BackgroundDark else Color.White
                            )
                        }
                    }

                    // Order Result Feedback Card
                    orderResult?.let { res ->
                        Spacer(Modifier.height(14.dp))
                        val isAck = res.status == "ACKNOWLEDGED" || res.status == "FILLED"
                        Surface(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(8.dp),
                            color = (if (isAck) AccentGreen else Color(0xFFEF4444)).copy(alpha = 0.15f),
                            border = androidx.compose.foundation.BorderStroke(1.dp, (if (isAck) AccentGreen else Color(0xFFEF4444)).copy(alpha = 0.5f))
                        ) {
                            Column(modifier = Modifier.padding(12.dp)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(
                                        if (isAck) Icons.Default.CheckCircle else Icons.Default.Warning,
                                        contentDescription = null,
                                        tint = if (isAck) AccentGreen else Color(0xFFEF4444),
                                        modifier = Modifier.size(16.dp)
                                    )
                                    Spacer(Modifier.width(6.dp))
                                    Text(
                                        "EXCHANGE STATUS: ${res.status}",
                                        fontSize = 11.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = if (isAck) AccentGreen else Color(0xFFEF4444)
                                    )
                                }
                                Spacer(Modifier.height(4.dp))
                                Text(
                                    "Order ID: ${res.internalOrderId ?: res.orderId} • Venue Symbol: ${res.venueSymbol ?: res.bingxSymbol}",
                                    fontSize = 11.sp,
                                    color = PrimaryText
                                )
                                Text(
                                    "Price: $${res.price} • Margin: $${res.margin} • Qty: ${res.quantity} (${res.mode})",
                                    fontSize = 11.sp,
                                    color = SecondaryText
                                )
                            }
                        }
                    }
                }
            }
        }

        item { Spacer(Modifier.height(20.dp)) }
    }
}

@Composable
fun AutomationPipelineDiagnosticsContent(
    pipeline: List<AutomationPipelineItemDto>,
    isLoading: Boolean,
    onRefresh: () -> Unit,
    onRecoverStale: () -> Unit
) {
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        item { Spacer(Modifier.height(4.dp)) }

        item {
            GlassCard(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text(
                                "AUTOMATION EXECUTION PIPELINE",
                                fontSize = 14.sp,
                                fontWeight = FontWeight.Bold,
                                color = PrimaryText,
                                letterSpacing = 1.sp
                            )
                            Text(
                                "Drill-down: Automation → Candidate → Slot → Intent → Position",
                                fontSize = 11.sp,
                                color = SecondaryText
                            )
                        }
                        IconButton(onClick = onRefresh) {
                            Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = AccentCyan)
                        }
                    }

                    Spacer(Modifier.height(10.dp))
                    Button(
                        onClick = onRecoverStale,
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.buttonColors(containerColor = AccentCyan.copy(alpha = 0.2f))
                    ) {
                        Icon(Icons.Default.Refresh, contentDescription = null, tint = AccentCyan, modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(8.dp))
                        Text("RECOVER STALE RESERVATIONS (>60s)", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = AccentCyan)
                    }
                }
            }
        }

        if (isLoading) {
            item {
                Box(Modifier.fillMaxWidth().padding(32.dp), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = AccentCyan)
                }
            }
        } else if (pipeline.isEmpty()) {
            item {
                GlassCard(modifier = Modifier.fillMaxWidth()) {
                    Box(Modifier.fillMaxWidth().padding(24.dp), contentAlignment = Alignment.Center) {
                        Text("NO ACTIVE PIPELINE EXECUTIONS", fontSize = 12.sp, color = SecondaryText)
                    }
                }
            }
        } else {
            items(pipeline) { item ->
                PipelineDrilldownCard(item)
            }
        }

        item { Spacer(Modifier.height(20.dp)) }
    }
}

@Composable
private fun PipelineDrilldownCard(item: AutomationPipelineItemDto) {
    GlassCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        "AUTO #${item.automationId}: ${item.strategy ?: "UNKNOWN"} (${item.symbol ?: "N/A"})",
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Bold,
                        color = PrimaryText
                    )
                    Text(
                        "User #${item.userId} • Acc #${item.accountId} • Status: ${item.status ?: "UNKNOWN"}",
                        fontSize = 10.sp,
                        color = SecondaryText
                    )
                }
                val candState = item.candidate?.get("current_state") as? String
                Surface(
                    shape = RoundedCornerShape(4.dp),
                    color = AccentCyan.copy(alpha = 0.15f),
                    border = androidx.compose.foundation.BorderStroke(1.dp, AccentCyan.copy(alpha = 0.4f))
                ) {
                    Text(
                        item.waitingReason ?: candState ?: "MONITORING",
                        fontSize = 9.sp,
                        fontWeight = FontWeight.Bold,
                        color = AccentCyan,
                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                    )
                }
            }

            Divider(color = BorderColor.copy(alpha = 0.2f))

            // 1. CANDIDATE
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("1. CANDIDATE", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = AccentCyan)
                val cState = item.candidate?.get("current_state")?.toString() ?: "NONE"
                val cConf = item.candidate?.get("confidence_pct")?.toString() ?: "0"
                Text(
                    if (item.candidate != null) "$cState (Conf: $cConf%)" else "NONE",
                    fontSize = 10.sp,
                    color = PrimaryText
                )
            }
            if (item.candidate != null) {
                val cId = item.candidate["candidate_id"]?.toString() ?: ""
                val cRetest = item.candidate["retest_state"]?.toString() ?: "NONE"
                Text(
                    "ID: $cId • Retest: $cRetest",
                    fontSize = 9.sp,
                    color = SecondaryText
                )
            }

            // 2. SLOT ALLOCATION
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("2. SLOT ALLOCATION", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = AccentCyan)
                val sName = item.slot?.get("name")?.toString() ?: "NO SLOT ELIGIBLE"
                val sStatus = item.slot?.get("status")?.toString() ?: ""
                Text(
                    if (item.slot != null) "$sName ($sStatus)" else "NO SLOT ELIGIBLE",
                    fontSize = 10.sp,
                    color = if (item.slot != null) AccentGreen else Color(0xFFEF4444)
                )
            }
            if (item.slot != null) {
                val sId = item.slot["id"]?.toString() ?: ""
                val sScope = item.slot["scope"]?.toString() ?: "ALL"
                val sMargin = item.slot["allocated_margin_usdt"]?.toString() ?: "0"
                val sLev = item.slot["max_leverage"]?.toString() ?: "1"
                val sResv = item.slot["reservation_id"]?.toString() ?: "NONE"
                Text(
                    "ID #$sId • $sScope • Margin: $$sMargin • Lev: ${sLev}x • Resv: $sResv",
                    fontSize = 9.sp,
                    color = SecondaryText
                )
            }

            // 3. EXECUTION INTENT
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("3. EXECUTION INTENT", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = AccentCyan)
                val iStatus = item.executionIntent?.get("status")?.toString() ?: "NONE"
                Text(
                    iStatus,
                    fontSize = 10.sp,
                    color = if (iStatus == "FILLED") AccentGreen else WarningAmber
                )
            }
            if (item.executionIntent != null) {
                val iId = item.executionIntent["execution_intent_id"]?.toString() ?: ""
                val iMargin = item.executionIntent["requested_margin"]?.toString() ?: "0"
                Text(
                    "Intent: $iId • Req Margin: $$iMargin",
                    fontSize = 9.sp,
                    color = SecondaryText
                )
            }

            // 4. POSITION EXECUTION
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("4. POSITION EXECUTION", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = AccentCyan)
                val pId = item.position?.get("position_id")?.toString() ?: ""
                val pStatus = item.position?.get("status")?.toString() ?: ""
                Text(
                    if (item.position != null) "POS #$pId ($pStatus)" else "NO OPEN POSITION",
                    fontSize = 10.sp,
                    color = if (item.position != null) AccentGreen else SecondaryText
                )
            }
            if (item.position != null) {
                val pSym = item.position["symbol"]?.toString() ?: ""
                val pDir = item.position["direction"]?.toString() ?: ""
                val pEntry = item.position["entry"]?.toString() ?: "0"
                val pMargin = item.position["margin_usdt"]?.toString() ?: "0"
                Text(
                    "$pSym $pDir @ $$pEntry • Margin: $$pMargin",
                    fontSize = 9.sp,
                    color = SecondaryText
                )
            }

            // 5. TP1 PARTIAL EXIT
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("5. TP1 PARTIAL EXIT", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = AccentCyan)
                val tp1Status = item.tp1?.get("status")?.toString() ?: "PENDING"
                Text(
                    tp1Status,
                    fontSize = 10.sp,
                    color = if (tp1Status == "EXECUTED") AccentGreen else SecondaryText
                )
            }
            if (item.tp1 != null && item.tp1["status"] == "EXECUTED") {
                val exitPx = item.tp1["exit_price"]?.toString() ?: "0"
                val tp1Qty = item.tp1["qty"]?.toString() ?: "0"
                val pnl = item.tp1["realized_pnl"]?.toString() ?: "0"
                Text(
                    "Exit: $$exitPx • Qty: $tp1Qty • PnL: +$$pnl",
                    fontSize = 9.sp,
                    color = SecondaryText
                )
            }

            // 6. NET BREAKEVEN
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("6. NET BREAKEVEN", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = AccentCyan)
                val beStatus = item.breakeven?.get("status")?.toString() ?: "PENDING"
                Text(
                    beStatus,
                    fontSize = 10.sp,
                    color = if (beStatus == "APPLIED") AccentGreen else SecondaryText
                )
            }
            if (item.breakeven != null && item.breakeven["status"] == "APPLIED") {
                val beStop = item.breakeven["stop"]?.toString() ?: "-"
                val costBasis = item.breakeven["cost_basis"]?.toString() ?: "-"
                Text(
                    "Stop: $$beStop • Cost Basis: $$costBasis",
                    fontSize = 9.sp,
                    color = SecondaryText
                )
            }

            // 7. DYNAMIC TRAILING
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("7. DYNAMIC TRAILING", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = AccentCyan)
                val trStatus = item.trailing?.get("status")?.toString() ?: "INACTIVE"
                Text(
                    trStatus,
                    fontSize = 10.sp,
                    color = if (trStatus == "ACTIVE") AccentGreen else SecondaryText
                )
            }
            if (item.trailing != null && item.trailing["status"] == "ACTIVE") {
                val curStop = item.trailing["current_stop"]?.toString() ?: "-"
                val prevStop = item.trailing["previous_stop"]?.toString() ?: "-"
                val method = item.trailing["method"]?.toString() ?: "DYNAMIC_ATR"
                Text(
                    "Trailing Stop: $$curStop (Prev: $$prevStop) • Method: $method",
                    fontSize = 9.sp,
                    color = SecondaryText
                )
            }

            // 8. EXIT & RECONCILIATION
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("8. EXIT & RECONCILIATION", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = AccentCyan)
                val reconStatus = item.reconciliation?.get("status")?.toString() ?: "RECONCILED"
                Text(
                    reconStatus,
                    fontSize = 10.sp,
                    color = if (reconStatus == "RECONCILED") AccentGreen else WarningAmber
                )
            }
            if (item.exit != null) {
                val lifecycle = item.exit["status"]?.toString() ?: "IDLE"
                val lastEvt = item.exit["last_event"]?.toString() ?: "NONE"
                Text(
                    "Lifecycle: $lifecycle • Event: $lastEvt",
                    fontSize = 9.sp,
                    color = SecondaryText
                )
            }
        }
    }
}

