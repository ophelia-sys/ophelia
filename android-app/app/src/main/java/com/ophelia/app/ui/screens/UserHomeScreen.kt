package com.ophelia.app.ui.screens

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
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
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ophelia.app.auth.TokenManager
import com.ophelia.app.models.CopyExecutionDto
import com.ophelia.app.models.UserDashboardResponse
import com.ophelia.app.models.UserPositionDto
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.theme.*
import kotlinx.coroutines.launch
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun UserHomeScreen(
    tokenManager: TokenManager,
    onNavigateToBingxSetup: () -> Unit,
    onNavigateToWorld: () -> Unit,
    onNavigateToUpdate: () -> Unit,
    onLogout: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val tokens = OpheliaThemeTokens.colors

    var dashboard by remember { mutableStateOf<UserDashboardResponse?>(null) }
    var isLoading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var isTogglingCopy by remember { mutableStateOf(false) }

    fun refreshDashboard() {
        scope.launch {
            isLoading = true
            errorMessage = null
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                val res = api.getUserDashboard()
                dashboard = res
            } catch (e: Exception) {
                errorMessage = e.message ?: "Failed to connect to Ophelia VPS"
            } finally {
                isLoading = false
            }
        }
    }

    fun toggleMasterCopy(currentEnabled: Boolean) {
        scope.launch {
            isTogglingCopy = true
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                val newEnabled = !currentEnabled
                api.updateUserCopySettings(mapOf("copy_enabled" to newEnabled))
                Toast.makeText(
                    context,
                    if (newEnabled) "Master Copy Execution: ON" else "Master Copy Execution: PAUSED BY USER",
                    Toast.LENGTH_SHORT
                ).show()
                refreshDashboard()
            } catch (e: Exception) {
                Toast.makeText(context, "Failed to update copy toggle: ${e.message}", Toast.LENGTH_LONG).show()
            } finally {
                isTogglingCopy = false
            }
        }
    }

    LaunchedEffect(Unit) {
        refreshDashboard()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = "OPHELIA USER",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = tokens.primaryText
                        )
                        Text(
                            text = "QUANTITATIVE TRADE REPLICATION",
                            style = MaterialTheme.typography.labelSmall,
                            color = tokens.secondaryText
                        )
                    }
                },
                actions = {
                    IconButton(onClick = { refreshDashboard() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = AccentBlue)
                    }
                    IconButton(onClick = onNavigateToWorld) {
                        Icon(Icons.Default.Info, contentDescription = "World Macro", tint = tokens.secondaryText)
                    }
                    IconButton(onClick = onNavigateToUpdate) {
                        Icon(Icons.Default.Build, contentDescription = "Update App", tint = tokens.secondaryText)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background
                )
            )
        },
        containerColor = tokens.surface
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            item {
                Spacer(modifier = Modifier.height(4.dp))

                // Welcome / Identity Banner
                dashboard?.let { dash ->
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text(
                                text = "FLEET ACCOUNT",
                                style = MaterialTheme.typography.labelSmall,
                                color = tokens.secondaryText,
                                fontSize = 10.sp,
                                fontFamily = FontFamily.Monospace
                            )
                            Text(
                                text = dash.displayName ?: dash.email ?: "User #${dash.userId}",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold,
                                color = tokens.primaryText
                            )
                        }
                        TextButton(onClick = onLogout) {
                            Text("Sign Out", color = BearishRed, style = MaterialTheme.typography.labelSmall)
                        }
                    }
                }
            }

            // Master Copy Trading Authoritative Toggle Card
            item {
                dashboard?.let { dash ->
                    val isCopyOn = dash.copyEnabled
                    val currentModeTitle = if (isCopyOn) "COPY OPHELIA" else "MY OPHELIA / AUTONOMOUS"
                    val currentModeDesc = if (isCopyOn)
                        "Master Follower Active: Trades initiated by Ophelia Master are copied to your BingX account using your slot margin and limits."
                    else
                        "Autonomous & Manual Active: Your independent ML Slots and Manual AUTO orders execute within your configured limits."

                    OpheliaGlassCard(
                        modifier = Modifier.fillMaxWidth(),
                        borderColor = if (isCopyOn) BullishGreen.copy(alpha = 0.5f) else AccentBlue.copy(alpha = 0.5f)
                    ) {
                        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = currentModeTitle,
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.Black,
                                        color = if (isCopyOn) BullishGreen else AccentBlue,
                                        letterSpacing = 0.5.sp
                                    )
                                    Spacer(Modifier.height(2.dp))
                                    Text(
                                        text = currentModeDesc,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = tokens.secondaryText,
                                        fontSize = 11.sp,
                                        lineHeight = 15.sp
                                    )
                                }

                                Switch(
                                    checked = isCopyOn,
                                    onCheckedChange = { toggleMasterCopy(isCopyOn) },
                                    enabled = !isTogglingCopy,
                                    colors = SwitchDefaults.colors(
                                        checkedThumbColor = Color.White,
                                        checkedTrackColor = BullishGreen,
                                        uncheckedThumbColor = AccentBlue,
                                        uncheckedTrackColor = tokens.surfaceElevated
                                    )
                                )
                            }

                            Divider(color = tokens.border.copy(alpha = 0.4f))

                            // Authoritative VPS Engine State Pill
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "OPHELIA ML & INTELLIGENCE",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = tokens.secondaryText,
                                    fontSize = 10.sp,
                                    fontFamily = FontFamily.Monospace
                                )
                                val engineColor = when (dash.copyEngineStatus) {
                                    "ACTIVE" -> BullishGreen
                                    "PAUSED BY USER" -> WarningAmber
                                    else -> BearishRed
                                }
                                OpheliaStatusBadge(
                                    status = dash.copyEngineStatus,
                                    color = engineColor
                                )
                            }
                        }
                    }
                }
            }

            // BingX Connection Card
            item {
                dashboard?.let { dash ->
                    val isConnected = dash.bingxStatus == "CONNECTED"
                    OpheliaGlassCard(modifier = Modifier.fillMaxWidth()) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(16.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column {
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    Text(
                                        text = "BINGX ACCOUNT",
                                        style = MaterialTheme.typography.titleSmall,
                                        fontWeight = FontWeight.Bold,
                                        color = tokens.primaryText,
                                        fontFamily = FontFamily.Monospace
                                    )
                                    OpheliaStatusBadge(
                                        status = dash.bingxStatus,
                                        color = if (isConnected) BullishGreen else BearishRed
                                    )
                                }
                                dash.bingxIdentifier?.let { id ->
                                    Text(
                                        text = "Key: $id",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = AccentBlue,
                                        fontFamily = FontFamily.Monospace,
                                        fontSize = 11.sp
                                    )
                                }
                            }

                            OpheliaOutlinedButton(
                                text = if (isConnected) "SETTINGS" else "CONNECT",
                                onClick = onNavigateToBingxSetup
                            )
                        }
                    }
                }
            }

            // Account Balances
            item {
                dashboard?.let { dash ->
                    OpheliaGlassCard(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            Text(
                                text = "FUTURES MARGIN ACCOUNT",
                                style = MaterialTheme.typography.labelSmall,
                                color = tokens.secondaryText,
                                fontWeight = FontWeight.Bold,
                                fontFamily = FontFamily.Monospace
                            )

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                AccountStatBox(
                                    label = "BALANCE",
                                    value = "$${String.format(Locale.US, "%.2f", dash.balance)}",
                                    color = tokens.primaryText,
                                    modifier = Modifier.weight(1f)
                                )
                                Spacer(modifier = Modifier.width(8.dp))
                                AccountStatBox(
                                    label = "EQUITY",
                                    value = "$${String.format(Locale.US, "%.2f", dash.equity)}",
                                    color = tokens.primaryText,
                                    modifier = Modifier.weight(1f)
                                )
                                Spacer(modifier = Modifier.width(8.dp))
                                AccountStatBox(
                                    label = "AVAILABLE",
                                    value = "$${String.format(Locale.US, "%.2f", dash.availableMargin)}",
                                    color = AccentBlue,
                                    modifier = Modifier.weight(1f)
                                )
                            }
                        }
                    }
                }
            }

            if (isLoading && dashboard == null) {
                item {
                    Box(modifier = Modifier.fillMaxWidth().padding(32.dp), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = AccentBlue)
                    }
                }
            }

            errorMessage?.let { err ->
                item {
                    OpheliaGlassCard(modifier = Modifier.fillMaxWidth(), borderColor = BearishRed) {
                        Row(
                            modifier = Modifier.padding(16.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            Icon(Icons.Default.Warning, contentDescription = null, tint = BearishRed)
                            Text(text = err, color = BearishRed, style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
            }

            // Active Copied Positions
            item {
                Text(
                    text = "ACTIVE COPIED POSITIONS (${dashboard?.positions?.size ?: 0})",
                    style = MaterialTheme.typography.labelMedium,
                    color = tokens.secondaryText,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                    modifier = Modifier.padding(top = 4.dp)
                )
            }

            dashboard?.let { dash ->
                if (dash.positions.isEmpty()) {
                    item {
                        OpheliaGlassCard(modifier = Modifier.fillMaxWidth()) {
                            Box(modifier = Modifier.fillMaxWidth().padding(24.dp), contentAlignment = Alignment.Center) {
                                Text(
                                    text = "No open positions.\nEligible trades triggered by Ophelia ML & Intelligence will replicate here automatically 24/7.",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = tokens.secondaryText,
                                    textAlign = androidx.compose.ui.text.style.TextAlign.Center
                                )
                            }
                        }
                    }
                } else {
                    items(dash.positions, key = { it.id }) { pos ->
                        UserPositionReadOnlyCard(pos)
                    }
                }
            }

            // Recent Trade Executions
            dashboard?.recentTrades?.let { trades ->
                if (trades.isNotEmpty()) {
                    item {
                        Text(
                            text = "RECENT REPLICATION EXECUTIONS (${trades.size})",
                            style = MaterialTheme.typography.labelMedium,
                            color = tokens.secondaryText,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace,
                            modifier = Modifier.padding(top = 8.dp)
                        )
                    }

                    items(trades, key = { it.copyExecutionId }) { exec ->
                        CopyExecutionRow(exec)
                    }
                }
            }

            item {
                Spacer(modifier = Modifier.height(24.dp))
            }
        }
    }
}

@Composable
fun AccountStatBox(
    label: String,
    value: String,
    color: Color,
    modifier: Modifier = Modifier
) {
    val tokens = OpheliaThemeTokens.colors
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(8.dp))
            .background(tokens.surfaceElevated)
            .border(1.dp, tokens.border, RoundedCornerShape(8.dp))
            .padding(vertical = 8.dp, horizontal = 8.dp)
    ) {
        Column {
            Text(text = label, style = MaterialTheme.typography.labelSmall, fontSize = 9.sp, color = tokens.secondaryText)
            Text(text = value, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold, color = color, fontFamily = FontFamily.Monospace)
        }
    }
}

@Composable
fun UserPositionReadOnlyCard(pos: UserPositionDto) {
    val tokens = OpheliaThemeTokens.colors
    val isLong = pos.direction.uppercase() == "LONG"

    OpheliaGlassCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(
                        text = pos.symbol,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                        color = tokens.primaryText
                    )
                    OpheliaStatusBadge(
                        status = "${pos.direction} ${pos.leverage.toInt()}x",
                        color = if (isLong) BullishGreen else BearishRed
                    )
                    OpheliaStatusBadge(
                        status = pos.lifecycleState,
                        color = when (pos.lifecycleState) {
                            "FILLED", "PROTECTED" -> AccentBlue
                            "TP1", "BREAKEVEN" -> BullishGreen
                            "TRAILING" -> AccentBlue
                            "EXITING", "CLOSED", "RECONCILED" -> WarningAmber
                            else -> tokens.secondaryText
                        }
                    )
                }

                Text(
                    text = "${if (pos.unrealizedPnl >= 0) "+" else ""}$${String.format(Locale.US, "%.2f", pos.unrealizedPnl)}",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = if (pos.unrealizedPnl >= 0) BullishGreen else BearishRed,
                    fontFamily = FontFamily.Monospace
                )
            }

            Divider(color = tokens.border.copy(alpha = 0.4f))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text(text = "ENTRY", style = MaterialTheme.typography.labelSmall, fontSize = 9.sp, color = tokens.secondaryText)
                    Text(text = "$${pos.actualEntryPrice ?: pos.entryPrice}", style = MaterialTheme.typography.bodySmall, color = tokens.primaryText, fontFamily = FontFamily.Monospace)
                }
                Column {
                    Text(text = "QUANTITY", style = MaterialTheme.typography.labelSmall, fontSize = 9.sp, color = tokens.secondaryText)
                    Text(text = "${pos.remainingQuantity ?: pos.quantity}", style = MaterialTheme.typography.bodySmall, color = tokens.primaryText, fontFamily = FontFamily.Monospace)
                }
                Column {
                    Text(text = "MARGIN", style = MaterialTheme.typography.labelSmall, fontSize = 9.sp, color = tokens.secondaryText)
                    Text(text = "$${String.format(Locale.US, "%.2f", pos.margin)}", style = MaterialTheme.typography.bodySmall, color = tokens.primaryText, fontFamily = FontFamily.Monospace)
                }
            }

            // Target Levels (Admin Authoritative Read-Only)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(6.dp))
                    .background(tokens.surfaceElevated)
                    .padding(6.dp),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "SL: ${pos.currentTrailingStop?.let { "$$it (T)" } ?: pos.breakevenStop?.let { "$$it (BE)" } ?: pos.slPrice?.let { "$$it" } ?: "NONE"}",
                    style = MaterialTheme.typography.labelSmall,
                    color = if (pos.breakevenStop != null || pos.currentTrailingStop != null) AccentBlue else BearishRed,
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace
                )
                Text(
                    text = "TP1: ${pos.tp1Price?.let { "$$it" } ?: "-"}",
                    style = MaterialTheme.typography.labelSmall,
                    color = BullishGreen,
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace
                )
                Text(
                    text = "TP2: ${pos.tp2Price?.let { "$$it" } ?: "-"}",
                    style = MaterialTheme.typography.labelSmall,
                    color = BullishGreen,
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace
                )
                Text(
                    text = "TP3: ${pos.tp3Price?.let { "$$it" } ?: "-"}",
                    style = MaterialTheme.typography.labelSmall,
                    color = BullishGreen,
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace
                )
            }

            if (pos.breakevenStop != null || pos.currentTrailingStop != null || pos.lastManagementEvent != null) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    pos.breakevenStop?.let {
                        Text("BE: $$it", fontSize = 9.sp, color = BullishGreen, fontFamily = FontFamily.Monospace)
                    }
                    pos.currentTrailingStop?.let {
                        Text("TRAIL: $$it", fontSize = 9.sp, color = AccentBlue, fontFamily = FontFamily.Monospace)
                    }
                    pos.lastManagementEvent?.let {
                        Text("EVT: $it", fontSize = 9.sp, color = tokens.secondaryText, maxLines = 1)
                    }
                }
            }
        }
    }
}

@Composable
fun CopyExecutionRow(exec: CopyExecutionDto) {
    val tokens = OpheliaThemeTokens.colors
    val isFilled = exec.status == "FILLED"

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(6.dp))
            .background(tokens.surfaceElevated)
            .border(1.dp, tokens.border.copy(alpha = 0.5f), RoundedCornerShape(6.dp))
            .padding(10.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column {
            Text(
                text = "Trade #${exec.masterTradeId.take(8)}",
                style = MaterialTheme.typography.bodySmall,
                fontWeight = FontWeight.Bold,
                color = tokens.primaryText,
                fontFamily = FontFamily.Monospace
            )
            exec.blockedReason?.let { reason ->
                Text(
                    text = reason,
                    style = MaterialTheme.typography.labelSmall,
                    color = WarningAmber,
                    fontSize = 10.sp
                )
            } ?: run {
                exec.executedQuantity?.let { qty ->
                    Text(
                        text = "Qty: $qty @ $${exec.executedPrice ?: 0.0}",
                        style = MaterialTheme.typography.labelSmall,
                        color = tokens.secondaryText,
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }
        }

        OpheliaStatusBadge(
            status = exec.status,
            color = if (isFilled) BullishGreen else if (exec.status == "BLOCKED") WarningAmber else BearishRed
        )
    }
}
