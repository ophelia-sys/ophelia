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
import com.ophelia.app.models.*
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.theme.*
import kotlinx.coroutines.launch
import java.util.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GodEyeScreen(
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val tokens = OpheliaThemeTokens.colors

    var overview by remember { mutableStateOf<GodEyeOverviewResponse?>(null) }
    var isLoading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }

    // Flash Close All dialog state
    var showFlashCloseDialog by remember { mutableStateOf(false) }
    var flashCloseReason by remember { mutableStateOf("") }
    var isExecutingFlashClose by remember { mutableStateOf(false) }

    // Single Position Close dialog state
    var positionToClose by remember { mutableStateOf<Pair<GodEyeUserDto, UserPositionDto>?>(null) }
    var isClosingPosition by remember { mutableStateOf(false) }

    fun refreshOverview() {
        scope.launch {
            isLoading = true
            errorMessage = null
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                overview = api.getGodEyeOverview()
            } catch (e: Exception) {
                errorMessage = e.message ?: "Failed to fetch God Eye overview"
            } finally {
                isLoading = false
            }
        }
    }

    fun toggleAdminCopy(user: GodEyeUserDto) {
        scope.launch {
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                val newAllowed = !user.adminCopyAllowed
                api.setUserCopyPermission(user.id, mapOf("allowed" to newAllowed))
                Toast.makeText(context, "Admin copy for ${user.name ?: user.email}: ${if (newAllowed) "ALLOWED" else "BLOCKED"}", Toast.LENGTH_SHORT).show()
                refreshOverview()
            } catch (e: Exception) {
                Toast.makeText(context, "Failed to update copy permission: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    fun toggleSuspension(user: GodEyeUserDto) {
        scope.launch {
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                val newSuspended = !user.suspended
                api.setUserSuspension(user.id, mapOf("suspended" to newSuspended))
                Toast.makeText(context, "User ${user.name ?: user.email} ${if (newSuspended) "SUSPENDED" else "REACTIVATED"}", Toast.LENGTH_SHORT).show()
                refreshOverview()
            } catch (e: Exception) {
                Toast.makeText(context, "Failed to update suspension: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    fun executePositionClose(userId: Long, symbol: String) {
        scope.launch {
            isClosingPosition = true
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                val res = api.closeUserPosition(mapOf("user_id" to userId, "symbol" to symbol))
                val status = res["status"] as? String ?: "EXECUTED"
                Toast.makeText(context, "Position close: $status", Toast.LENGTH_SHORT).show()
                positionToClose = null
                refreshOverview()
            } catch (e: Exception) {
                Toast.makeText(context, "Close failed: ${e.message}", Toast.LENGTH_LONG).show()
            } finally {
                isClosingPosition = false
            }
        }
    }

    fun executeFlashCloseAll() {
        if (flashCloseReason.trim().isEmpty()) {
            Toast.makeText(context, "Reason is mandatory for Flash Close All", Toast.LENGTH_SHORT).show()
            return
        }
        scope.launch {
            isExecutingFlashClose = true
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                val res = api.flashCloseAll(mapOf("reason" to flashCloseReason.trim()))
                val actionId = res["action_id"] as? String ?: "EMERGENCY"
                val totalClosed = res["total_closed"] ?: 0
                Toast.makeText(context, "Flash Close [$actionId] executed. Closed: $totalClosed positions", Toast.LENGTH_LONG).show()
                showFlashCloseDialog = false
                flashCloseReason = ""
                refreshOverview()
            } catch (e: Exception) {
                Toast.makeText(context, "Flash Close error: ${e.message}", Toast.LENGTH_LONG).show()
            } finally {
                isExecutingFlashClose = false
            }
        }
    }

    LaunchedEffect(Unit) {
        refreshOverview()
    }

    // Flash Close All Confirmation Dialog
    if (showFlashCloseDialog) {
        AlertDialog(
            onDismissRequest = { if (!isExecutingFlashClose) showFlashCloseDialog = false },
            title = {
                Text(
                    text = "FLASH CLOSE ALL USERS",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = BearishRed
                )
            },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text(
                        text = "This will immediately issue market close orders directly to BingX for every open position on all registered user accounts. Offline user apps will not block execution.",
                        style = MaterialTheme.typography.bodySmall,
                        color = tokens.secondaryText
                    )
                    Text(
                        text = "Mandatory Audit Reason:",
                        style = MaterialTheme.typography.labelSmall,
                        color = tokens.primaryText,
                        fontWeight = FontWeight.Bold
                    )
                    OutlinedTextField(
                        value = flashCloseReason,
                        onValueChange = { flashCloseReason = it },
                        placeholder = { Text("e.g. Extreme market event / Emergency risk mitigation") },
                        modifier = Modifier.fillMaxWidth(),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = BearishRed,
                            unfocusedBorderColor = tokens.border,
                            focusedTextColor = tokens.primaryText,
                            unfocusedTextColor = tokens.primaryText
                        ),
                        singleLine = false,
                        maxLines = 3
                    )
                }
            },
            confirmButton = {
                OpheliaDangerButton(
                    text = if (isExecutingFlashClose) "CLOSING..." else "CONFIRM FLASH CLOSE",
                    onClick = { executeFlashCloseAll() },
                    enabled = !isExecutingFlashClose && flashCloseReason.trim().isNotEmpty()
                )
            },
            dismissButton = {
                OpheliaOutlinedButton(
                    text = "CANCEL",
                    onClick = { showFlashCloseDialog = false },
                    enabled = !isExecutingFlashClose
                )
            },
            containerColor = tokens.surfaceElevated
        )
    }

    // Position Close Dialog
    positionToClose?.let { (user, pos) ->
        AlertDialog(
            onDismissRequest = { if (!isClosingPosition) positionToClose = null },
            title = {
                Text(
                    text = "CLOSE POSITION: ${pos.symbol}",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = tokens.primaryText
                )
            },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        text = "User: ${user.name ?: user.email}\nQty: ${pos.quantity} • Dir: ${pos.direction} • Leverage: ${pos.leverage}x",
                        style = MaterialTheme.typography.bodySmall,
                        color = tokens.secondaryText
                    )
                    Text(
                        text = "VPS will execute direct market close on BingX. This operation succeeds even if the user's phone is offline.",
                        style = MaterialTheme.typography.labelSmall,
                        color = AccentBlue,
                        fontFamily = FontFamily.Monospace
                    )
                }
            },
            confirmButton = {
                OpheliaDangerButton(
                    text = if (isClosingPosition) "CLOSING..." else "CLOSE NOW",
                    onClick = { executePositionClose(user.id, pos.symbol) },
                    enabled = !isClosingPosition
                )
            },
            dismissButton = {
                OpheliaOutlinedButton(
                    text = "CANCEL",
                    onClick = { positionToClose = null },
                    enabled = !isClosingPosition
                )
            },
            containerColor = tokens.surfaceElevated
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = "GOD EYE",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = tokens.primaryText
                        )
                        Text(
                            text = "FLEET MONITORING & REPLICATION CONTROL",
                            style = MaterialTheme.typography.labelSmall,
                            color = tokens.secondaryText
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back", tint = tokens.primaryText)
                    }
                },
                actions = {
                    IconButton(onClick = { refreshOverview() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = AccentBlue)
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
                // Top Fleet Summary Metrics
                overview?.summary?.let { summary ->
                    OpheliaGlassCard(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "FLEET OVERVIEW",
                                    style = MaterialTheme.typography.titleMedium,
                                    color = tokens.primaryText,
                                    fontWeight = FontWeight.Bold,
                                    fontFamily = FontFamily.Monospace
                                )
                                OpheliaStatusBadge(
                                    status = "${summary.connectedUsers} USERS REGISTERED",
                                    color = AccentBlue
                                )
                            }

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                FleetMetricBox(
                                    label = "ACTIVE COPY",
                                    value = summary.activeCopy.toString(),
                                    color = BullishGreen,
                                    modifier = Modifier.weight(1f)
                                )
                                FleetMetricBox(
                                    label = "PAUSED",
                                    value = summary.paused.toString(),
                                    color = WarningAmber,
                                    modifier = Modifier.weight(1f)
                                )
                                FleetMetricBox(
                                    label = "DISCONNECTED",
                                    value = summary.bingxDisconnected.toString(),
                                    color = if (summary.bingxDisconnected > 0) BearishRed else tokens.secondaryText,
                                    modifier = Modifier.weight(1f)
                                )
                            }

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                FleetMetricBox(
                                    label = "SUSPENDED",
                                    value = summary.suspended.toString(),
                                    color = if (summary.suspended > 0) WarningAmber else tokens.secondaryText,
                                    modifier = Modifier.weight(1f)
                                )
                                FleetMetricBox(
                                    label = "EXEC ERRORS",
                                    value = summary.executionErrors.toString(),
                                    color = if (summary.executionErrors > 0) BearishRed else BullishGreen,
                                    modifier = Modifier.weight(1f)
                                )
                            }

                            Divider(color = tokens.border.copy(alpha = 0.5f))

                            // Emergency Actions Bar
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text(
                                        text = "EMERGENCY SAFETY",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = tokens.secondaryText,
                                        fontWeight = FontWeight.Bold
                                    )
                                    Text(
                                        text = "Direct market close on all accounts",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = tokens.secondaryText,
                                        fontSize = 11.sp
                                    )
                                }
                                OpheliaDangerButton(
                                    text = "FLASH CLOSE ALL",
                                    onClick = { showFlashCloseDialog = true }
                                )
                            }
                        }
                    }
                }
            }

            if (isLoading && overview == null) {
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

            // Registered Users List
            overview?.users?.let { users ->
                if (users.isEmpty()) {
                    item {
                        OpheliaGlassCard(modifier = Modifier.fillMaxWidth()) {
                            Box(modifier = Modifier.fillMaxWidth().padding(24.dp), contentAlignment = Alignment.Center) {
                                Text(
                                    text = "No users registered yet.\nUsers authenticate via Google on Ophelia User.",
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = tokens.secondaryText,
                                    textAlign = androidx.compose.ui.text.style.TextAlign.Center
                                )
                            }
                        }
                    }
                } else {
                    item {
                        Text(
                            text = "CONNECTED REPLICATION FLEET (${users.size})",
                            style = MaterialTheme.typography.labelMedium,
                            color = tokens.secondaryText,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace,
                            modifier = Modifier.padding(top = 8.dp)
                        )
                    }

                    items(users, key = { it.id }) { user ->
                        UserFleetCard(
                            user = user,
                            onToggleAdminCopy = { toggleAdminCopy(user) },
                            onToggleSuspension = { toggleSuspension(user) },
                            onClosePosition = { pos -> positionToClose = Pair(user, pos) }
                        )
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
fun FleetMetricBox(
    label: String,
    value: String,
    color: Color,
    modifier: Modifier = Modifier
) {
    val tokens = OpheliaThemeTokens.colors
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(8.dp))
            .background(color.copy(alpha = 0.08f))
            .border(1.dp, color.copy(alpha = 0.25f), RoundedCornerShape(8.dp))
            .padding(vertical = 8.dp, horizontal = 10.dp)
    ) {
        Column {
            Text(
                text = label,
                style = MaterialTheme.typography.labelSmall,
                color = tokens.secondaryText,
                fontSize = 10.sp,
                fontWeight = FontWeight.SemiBold
            )
            Text(
                text = value,
                style = MaterialTheme.typography.titleMedium,
                color = color,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace
            )
        }
    }
}

@Composable
fun UserFleetCard(
    user: GodEyeUserDto,
    onToggleAdminCopy: () -> Unit,
    onToggleSuspension: () -> Unit,
    onClosePosition: (UserPositionDto) -> Unit
) {
    val tokens = OpheliaThemeTokens.colors
    val effectiveEligible = user.adminCopyAllowed && user.copyEnabled && !user.suspended && user.bingxConnection == "CONNECTED"

    OpheliaGlassCard(
        modifier = Modifier.fillMaxWidth(),
        borderColor = if (user.suspended) WarningAmber.copy(alpha = 0.5f) else null
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            // Header: Name, Email, Role, Account Status
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Top
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = user.name ?: user.email ?: "User #${user.id}",
                        style = MaterialTheme.typography.titleSmall,
                        color = tokens.primaryText,
                        fontWeight = FontWeight.Bold
                    )
                    user.email?.let {
                        Text(
                            text = it,
                            style = MaterialTheme.typography.bodySmall,
                            color = tokens.secondaryText,
                            fontSize = 11.sp
                        )
                    }
                    Text(
                        text = "ID: ${user.userUid ?: user.id} • App: ${user.appVersion ?: "v1.0.0"}",
                        style = MaterialTheme.typography.labelSmall,
                        color = tokens.mutedText,
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }

                Column(horizontalAlignment = Alignment.End) {
                    OpheliaStatusBadge(
                        status = if (user.suspended) "USER SUSPENDED" else "USER ${user.status}",
                        color = if (user.suspended) WarningAmber else BullishGreen
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    val repStatus = if (effectiveEligible) "REPLICATION ACTIVE" else if (user.bingxConnection != "CONNECTED") "BINGX NOT CONNECTED" else if (!user.copyEnabled) "COPY OFF" else "COPY BLOCKED"
                    OpheliaStatusBadge(
                        status = repStatus,
                        color = if (effectiveEligible) BullishGreen else if (user.bingxConnection != "CONNECTED") tokens.secondaryText else WarningAmber
                    )
                }
            }

            Divider(color = tokens.border.copy(alpha = 0.4f))

            // State Breakdown Matrix
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                val bingxState = when (user.bingxConnection) {
                    "CONNECTED" -> "CONNECTED"
                    "NOT_CONNECTED" -> "NOT CONNECTED"
                    "ERROR" -> "ERROR"
                    else -> user.bingxConnection.replace("_", " ")
                }
                val bingxColor = when (user.bingxConnection) {
                    "CONNECTED" -> BullishGreen
                    "NOT_CONNECTED" -> tokens.secondaryText
                    "ERROR" -> BearishRed
                    else -> tokens.secondaryText
                }
                StateMatrixPill(
                    label = "BINGX",
                    state = bingxState,
                    color = bingxColor,
                    modifier = Modifier.weight(1f)
                )
                StateMatrixPill(
                    label = "USER COPY",
                    state = if (user.copyEnabled) "ON" else "OFF",
                    color = if (user.copyEnabled) BullishGreen else tokens.secondaryText,
                    modifier = Modifier.weight(1f)
                )
                StateMatrixPill(
                    label = "ADMIN COPY",
                    state = if (user.adminCopyAllowed) "ON" else "OFF",
                    color = if (user.adminCopyAllowed) BullishGreen else BearishRed,
                    modifier = Modifier.weight(1f)
                )
            }

            // Account Balance & Equity
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(8.dp))
                    .background(tokens.surfaceElevated)
                    .padding(8.dp),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text(text = "BALANCE", style = MaterialTheme.typography.labelSmall, fontSize = 9.sp, color = tokens.secondaryText)
                    val balText = if (user.balance != null && user.bingxConnection == "CONNECTED") "$${String.format(Locale.US, "%.2f", user.balance)}" else "NOT CONNECTED"
                    Text(text = balText, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold, color = if (user.balance != null) tokens.primaryText else tokens.secondaryText, fontFamily = FontFamily.Monospace)
                }
                Column {
                    Text(text = "EQUITY", style = MaterialTheme.typography.labelSmall, fontSize = 9.sp, color = tokens.secondaryText)
                    val eqText = if (user.equity != null && user.bingxConnection == "CONNECTED") "$${String.format(Locale.US, "%.2f", user.equity)}" else "--"
                    Text(text = eqText, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold, color = tokens.primaryText, fontFamily = FontFamily.Monospace)
                }
                Column {
                    Text(text = "AVAIL MARGIN", style = MaterialTheme.typography.labelSmall, fontSize = 9.sp, color = tokens.secondaryText)
                    val availText = if (user.availableMargin != null && user.bingxConnection == "CONNECTED") "$${String.format(Locale.US, "%.2f", user.availableMargin)}" else "--"
                    Text(text = availText, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold, color = AccentBlue, fontFamily = FontFamily.Monospace)
                }
            }

            // Open Positions Section
            if (user.openPositions.isNotEmpty()) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        text = "OPEN POSITIONS (${user.openPositions.size})",
                        style = MaterialTheme.typography.labelSmall,
                        color = tokens.secondaryText,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace
                    )
                    user.openPositions.forEach { pos ->
                        UserPositionRow(
                            pos = pos,
                            onClose = { onClosePosition(pos) }
                        )
                    }
                }
            } else {
                Text(
                    text = "No open positions",
                    style = MaterialTheme.typography.bodySmall,
                    color = tokens.secondaryText,
                    fontSize = 11.sp
                )
            }

            user.lastError?.let { err ->
                if (err.isNotBlank()) {
                    Text(
                        text = "Last Error: $err",
                        style = MaterialTheme.typography.labelSmall,
                        color = BearishRed,
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }

            Divider(color = tokens.border.copy(alpha = 0.4f))

            // Action Buttons: Admin Copy Permission Toggle & Suspend/Reactivate Toggle
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OpheliaOutlinedButton(
                    text = if (user.adminCopyAllowed) "DISABLE COPY" else "ALLOW COPY",
                    onClick = onToggleAdminCopy,
                    modifier = Modifier.weight(1f)
                )

                if (user.suspended) {
                    OpheliaButton(
                        text = "REACTIVATE",
                        onClick = onToggleSuspension,
                        modifier = Modifier.weight(1f)
                    )
                } else {
                    OpheliaDangerButton(
                        text = "SUSPEND",
                        onClick = onToggleSuspension,
                        modifier = Modifier.weight(1f)
                    )
                }
            }
        }
    }
}

@Composable
fun StateMatrixPill(
    label: String,
    state: String,
    color: Color,
    modifier: Modifier = Modifier
) {
    val tokens = OpheliaThemeTokens.colors
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(6.dp))
            .background(color.copy(alpha = 0.08f))
            .border(1.dp, color.copy(alpha = 0.25f), RoundedCornerShape(6.dp))
            .padding(vertical = 4.dp, horizontal = 6.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(text = label, style = MaterialTheme.typography.labelSmall, fontSize = 8.sp, color = tokens.secondaryText)
            Text(text = state, style = MaterialTheme.typography.labelSmall, fontSize = 11.sp, fontWeight = FontWeight.Bold, color = color, fontFamily = FontFamily.Monospace)
        }
    }
}

@Composable
fun UserPositionRow(
    pos: UserPositionDto,
    onClose: () -> Unit
) {
    val tokens = OpheliaThemeTokens.colors
    val isLong = pos.direction.uppercase() == "LONG"

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(6.dp))
            .background(tokens.surfaceElevated)
            .border(1.dp, tokens.border.copy(alpha = 0.5f), RoundedCornerShape(6.dp))
            .padding(8.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(
                    text = pos.symbol,
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.Bold,
                    color = tokens.primaryText
                )
                OpheliaStatusBadge(
                    status = "${pos.direction} ${pos.leverage.toInt()}x",
                    color = if (isLong) BullishGreen else BearishRed
                )
            }
            Text(
                text = "Qty: ${pos.quantity} • Entry: $${pos.entryPrice} • PnL: ${if (pos.unrealizedPnl >= 0) "+" else ""}$${String.format(Locale.US, "%.2f", pos.unrealizedPnl)}",
                style = MaterialTheme.typography.labelSmall,
                color = if (pos.unrealizedPnl >= 0) BullishGreen else BearishRed,
                fontFamily = FontFamily.Monospace,
                fontSize = 10.sp
            )
        }

        OpheliaDangerButton(
            text = "CLOSE",
            onClick = onClose
        )
    }
}
