package com.ophelia.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ophelia.app.models.DetailedEngineHealthResponse
import com.ophelia.app.models.SubsystemHealthDto
import com.ophelia.app.models.SystemAuditLogDto
import com.ophelia.app.models.TerminalLineDto
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.GlassCard
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EngineHealthAuditScreen(
    onBack: () -> Unit
) {
    var selectedTab by remember { mutableStateOf(0) }
    val scope = rememberCoroutineScope()

    var healthData by remember { mutableStateOf<DetailedEngineHealthResponse?>(null) }
    var terminalLines by remember { mutableStateOf<List<TerminalLineDto>>(emptyList()) }
    var auditLogs by remember { mutableStateOf<List<SystemAuditLogDto>>(emptyList()) }
    var selectedAuditFilter by remember { mutableStateOf("ALL") }

    var isLoadingHealth by remember { mutableStateOf(true) }
    var isLoadingLogs by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }

    fun refreshAll() {
        scope.launch {
            try {
                val api = RetrofitClient.apiService ?: return@launch
                isLoadingHealth = true
                val h = api.getDetailedEngineHealth()
                healthData = h
                val term = api.getTerminalStream(limit = 60)
                terminalLines = term.lines
                isLoadingHealth = false

                isLoadingLogs = true
                val audit = api.getSystemAuditLogs(
                    limit = 50,
                    component = if (selectedAuditFilter == "ALL") null else selectedAuditFilter
                )
                auditLogs = audit.logs
                isLoadingLogs = false
            } catch (e: Exception) {
                errorMessage = e.message ?: "Failed to refresh health and telemetry"
                isLoadingHealth = false
                isLoadingLogs = false
            }
        }
    }

    // Auto-poll terminal stream every 4 seconds while screen active
    LaunchedEffect(Unit) {
        refreshAll()
        while (isActive) {
            delay(4000)
            try {
                val api = RetrofitClient.apiService
                if (api != null) {
                    val term = api.getTerminalStream(limit = 60)
                    terminalLines = term.lines
                }
            } catch (_: Exception) {}
        }
    }

    LaunchedEffect(selectedAuditFilter) {
        scope.launch {
            try {
                isLoadingLogs = true
                val api = RetrofitClient.apiService ?: return@launch
                val audit = api.getSystemAuditLogs(
                    limit = 50,
                    component = if (selectedAuditFilter == "ALL") null else selectedAuditFilter
                )
                auditLogs = audit.logs
                isLoadingLogs = false
            } catch (e: Exception) {
                isLoadingLogs = false
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = "Engine Health & Audit Logs",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "VPS Operational Telemetry & Immutable Audit Log",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = { refreshAll() }) {
                        Icon(Icons.Filled.Refresh, contentDescription = "Refresh")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background
                )
            )
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
        ) {
            TabRow(
                selectedTabIndex = selectedTab,
                containerColor = MaterialTheme.colorScheme.surface,
                contentColor = MaterialTheme.colorScheme.primary
            ) {
                Tab(
                    selected = selectedTab == 0,
                    onClick = { selectedTab = 0 },
                    text = {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text("Engine Health", fontWeight = FontWeight.SemiBold)
                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(4.dp))
                                    .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.15f))
                                    .padding(horizontal = 6.dp, vertical = 2.dp)
                            ) {
                                Text(
                                    text = healthData?.status ?: "ONLINE",
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = MaterialTheme.colorScheme.primary
                                )
                            }
                        }
                    }
                )
                Tab(
                    selected = selectedTab == 1,
                    onClick = { selectedTab = 1 },
                    text = {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text("Audit Logs", fontWeight = FontWeight.SemiBold)
                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(4.dp))
                                    .background(MaterialTheme.colorScheme.surfaceVariant)
                                    .padding(horizontal = 6.dp, vertical = 2.dp)
                            ) {
                                Text(
                                    text = "${auditLogs.size}",
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }
                    }
                )
            }

            if (selectedTab == 0) {
                // ==========================================
                // TAB 1: ENGINE HEALTH & LIVE TERMINAL
                // ==========================================
                LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(horizontal = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp),
                    contentPadding = PaddingValues(vertical = 16.dp)
                ) {
                    // Overall System Health Header
                    item {
                        GlassCard {
                            Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                        Box(
                                            modifier = Modifier
                                                .size(10.dp)
                                                .clip(CircleShape)
                                                .background(if (healthData?.status == "ONLINE") Color(0xFF10B981) else Color(0xFFF59E0B))
                                        )
                                        Text(
                                            text = "VPS CORE STATUS: ${healthData?.status ?: "ONLINE"}",
                                            style = MaterialTheme.typography.titleSmall,
                                            fontWeight = FontWeight.Black
                                        )
                                    }
                                    Box(
                                        modifier = Modifier
                                            .clip(RoundedCornerShape(6.dp))
                                            .background(MaterialTheme.colorScheme.primaryContainer)
                                            .padding(horizontal = 8.dp, vertical = 4.dp)
                                    ) {
                                        Text(
                                            text = healthData?.mode ?: "SHADOW",
                                            style = MaterialTheme.typography.labelSmall,
                                            fontWeight = FontWeight.Bold,
                                            color = MaterialTheme.colorScheme.primary
                                        )
                                    }
                                }

                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Column {
                                        Text("Uptime", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        val upHours = (healthData?.uptimeSeconds ?: 0L) / 3600
                                        val upDays = upHours / 24
                                        Text("${upDays}d ${upHours % 24}h", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
                                    }
                                    Column {
                                        Text("Active Autos", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        Text("${healthData?.activeAutomations ?: 0}", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
                                    }
                                    Column {
                                        Text("Open Trades / Cap", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        Text("${healthData?.openPositions ?: 0} / ${healthData?.maxOpenTrades ?: 4}", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
                                    }
                                    Column {
                                        Text("BingX Status", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        Text(
                                            text = healthData?.bingxConnection?.status ?: "CONNECTED",
                                            style = MaterialTheme.typography.bodyMedium,
                                            fontWeight = FontWeight.Bold,
                                            color = if (healthData?.bingxConnection?.status == "CONNECTED") Color(0xFF10B981) else MaterialTheme.colorScheme.error
                                        )
                                    }
                                }
                            }
                        }
                    }

                    // LIVE TERMINAL VIEW (Sanitized Real Log Stream)
                    item {
                        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    Icon(
                                        Icons.Filled.Build,
                                        contentDescription = "Terminal",
                                        tint = MaterialTheme.colorScheme.primary,
                                        modifier = Modifier.size(16.dp)
                                    )
                                    Text(
                                        text = "LIVE VPS EVENT STREAM",
                                        style = MaterialTheme.typography.labelMedium,
                                        fontWeight = FontWeight.Bold,
                                        letterSpacing = 1.sp
                                    )
                                }
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                                    Box(
                                        modifier = Modifier
                                            .size(6.dp)
                                            .clip(CircleShape)
                                            .background(Color(0xFF10B981))
                                    )
                                    Text(
                                        text = "STREAMING (READ-ONLY)",
                                        style = MaterialTheme.typography.labelSmall,
                                        fontSize = 9.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = Color(0xFF10B981)
                                    )
                                }
                            }

                            // Terminal Window Container
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(260.dp)
                                    .clip(RoundedCornerShape(8.dp))
                                    .background(Color(0xFF0D1117))
                                    .border(1.dp, Color(0xFF30363D), RoundedCornerShape(8.dp))
                                    .padding(10.dp)
                            ) {
                                val listState = rememberLazyListState()
                                LaunchedEffect(terminalLines.size) {
                                    if (terminalLines.isNotEmpty()) {
                                        listState.animateScrollToItem(terminalLines.size - 1)
                                    }
                                }

                                if (terminalLines.isEmpty()) {
                                    Text(
                                        text = "Connecting to sanitized VPS event feed...",
                                        style = MaterialTheme.typography.bodySmall,
                                        fontFamily = FontFamily.Monospace,
                                        color = Color(0xFF8B949E),
                                        modifier = Modifier.align(Alignment.Center)
                                    )
                                } else {
                                    LazyColumn(
                                        state = listState,
                                        modifier = Modifier.fillMaxSize(),
                                        verticalArrangement = Arrangement.spacedBy(4.dp)
                                    ) {
                                        items(terminalLines) { line ->
                                            Row(
                                                modifier = Modifier.fillMaxWidth(),
                                                horizontalArrangement = Arrangement.spacedBy(6.dp)
                                            ) {
                                                Text(
                                                    text = line.timestamp.takeLast(12).ifEmpty { "LIVE" },
                                                    style = MaterialTheme.typography.labelSmall,
                                                    fontFamily = FontFamily.Monospace,
                                                    fontSize = 10.sp,
                                                    color = Color(0xFF8B949E)
                                                )
                                                Text(
                                                    text = "[${line.component}]",
                                                    style = MaterialTheme.typography.labelSmall,
                                                    fontFamily = FontFamily.Monospace,
                                                    fontSize = 10.sp,
                                                    fontWeight = FontWeight.Bold,
                                                    color = when (line.component) {
                                                        "CORE", "SYSTEM" -> Color(0xFF58A6FF)
                                                        "API" -> Color(0xFF7EE787)
                                                        "RISK" -> Color(0xFFFFA657)
                                                        "ML" -> Color(0xFFD2A8FF)
                                                        else -> Color(0xFF79C0FF)
                                                    }
                                                )
                                                Text(
                                                    text = line.message,
                                                    style = MaterialTheme.typography.bodySmall,
                                                    fontFamily = FontFamily.Monospace,
                                                    fontSize = 11.sp,
                                                    color = Color(0xFFE6EDF3)
                                                )
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // OPERATIONAL SUBSYSTEMS LIST
                    item {
                        Text(
                            text = "OPERATIONAL SUBSYSTEMS (${healthData?.subsystems?.size ?: 12})",
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold,
                            letterSpacing = 1.sp
                        )
                    }

                    items(healthData?.subsystems ?: emptyList()) { sub ->
                        SubsystemCard(sub)
                    }
                }
            } else {
                // ==========================================
                // TAB 2: AUDIT LOGS
                // ==========================================
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(horizontal = 16.dp, vertical = 10.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    // Filter Chips Row
                    val filters = listOf("ALL", "SYSTEM", "API", "ACCOUNT", "CORE", "SCANNER", "ML", "AUTOMATION")
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        filters.forEach { filter ->
                            val isSelected = selectedAuditFilter == filter
                            FilterChip(
                                selected = isSelected,
                                onClick = { selectedAuditFilter = filter },
                                label = { Text(filter, fontSize = 11.sp, fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal) },
                                shape = RoundedCornerShape(8.dp)
                            )
                        }
                    }

                    if (auditLogs.isEmpty() && !isLoadingLogs) {
                        Box(
                            modifier = Modifier
                                .fillMaxSize()
                                .padding(top = 40.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                Icon(Icons.Filled.CheckCircle, contentDescription = "Empty", tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(36.dp))
                                Text("No audit events recorded yet", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    } else {
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            verticalArrangement = Arrangement.spacedBy(8.dp),
                            contentPadding = PaddingValues(bottom = 16.dp)
                        ) {
                            items(auditLogs) { log ->
                                AuditLogItemCard(log)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun SubsystemCard(sub: SubsystemHealthDto) {
    GlassCard {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        text = sub.name,
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = "${sub.latencyMs}ms",
                        style = MaterialTheme.typography.labelSmall,
                        fontFamily = FontFamily.Monospace,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
                Text(
                    text = sub.detail,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(6.dp))
                    .background(
                        when (sub.status) {
                            "ONLINE", "CONNECTED", "READY" -> Color(0xFF10B981).copy(alpha = 0.15f)
                            "DEGRADED" -> Color(0xFFF59E0B).copy(alpha = 0.15f)
                            else -> MaterialTheme.colorScheme.error.copy(alpha = 0.15f)
                        }
                    )
                    .padding(horizontal = 8.dp, vertical = 4.dp)
            ) {
                Text(
                    text = sub.status,
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = when (sub.status) {
                        "ONLINE", "CONNECTED", "READY" -> Color(0xFF10B981)
                        "DEGRADED" -> Color(0xFFF59E0B)
                        else -> MaterialTheme.colorScheme.error
                    }
                )
            }
        }
    }
}

@Composable
fun AuditLogItemCard(log: SystemAuditLogDto) {
    GlassCard {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(4.dp))
                            .background(MaterialTheme.colorScheme.primaryContainer)
                            .padding(horizontal = 6.dp, vertical = 2.dp)
                    ) {
                        Text(
                            text = log.component,
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.primary
                        )
                    }
                    Text(
                        text = log.action,
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Bold
                    )
                }
                Text(
                    text = log.timestampIso.ifEmpty { "${log.tsMs}" },
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            if (log.detail != null) {
                Text(
                    text = log.detail.toString(),
                    style = MaterialTheme.typography.bodySmall,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}
