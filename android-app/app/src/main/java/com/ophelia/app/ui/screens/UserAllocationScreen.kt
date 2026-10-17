package com.ophelia.app.ui.screens

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.theme.*
import kotlinx.coroutines.launch
import java.util.Locale

data class UserAllocationItemState(
    val automationId: Int,
    val strategy: String?,
    val symbol: String?,
    val timeframe: String?,
    val name: String?,
    var allocatedAmount: Double,
    var enabled: Boolean,
    val minExecutableNotional: Double = 5.0
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun UserAllocationScreen(
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val tokens = OpheliaThemeTokens.colors

    var isLoading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var availableCapital by remember { mutableDoubleStateOf(0.0) }
    var totalAllocated by remember { mutableDoubleStateOf(0.0) }
    var remainingAllocatable by remember { mutableDoubleStateOf(0.0) }
    val allocations = remember { mutableStateListOf<UserAllocationItemState>() }

    fun loadAllocations() {
        scope.launch {
            isLoading = true
            errorMessage = null
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                val res = api.getUserAllocations()
                availableCapital = (res["available_capital"] as? Number)?.toDouble() ?: 0.0
                totalAllocated = (res["total_allocated"] as? Number)?.toDouble() ?: 0.0
                remainingAllocatable = (res["remaining_allocatable"] as? Number)?.toDouble() ?: 0.0

                allocations.clear()
                val rawList = res["allocations"] as? List<Map<String, Any>> ?: emptyList()
                for (item in rawList) {
                    allocations.add(
                        UserAllocationItemState(
                            automationId = (item["automation_id"] as? Number)?.toInt() ?: 0,
                            strategy = item["strategy"] as? String,
                            symbol = item["symbol"] as? String,
                            timeframe = item["timeframe"] as? String,
                            name = item["name"] as? String,
                            allocatedAmount = (item["allocated_amount"] as? Number)?.toDouble() ?: 0.0,
                            enabled = item["enabled"] as? Boolean ?: true,
                            minExecutableNotional = (item["min_executable_notional"] as? Number)?.toDouble() ?: 5.0
                        )
                    )
                }
            } catch (e: Exception) {
                errorMessage = e.message ?: "Failed to load allocations"
            } finally {
                isLoading = false
            }
        }
    }

    fun saveAllocation(item: UserAllocationItemState) {
        scope.launch {
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                api.setUserAllocation(
                    mapOf(
                        "automation_id" to item.automationId,
                        "allocated_amount" to item.allocatedAmount,
                        "enabled" to item.enabled
                    )
                )
                Toast.makeText(context, "Allocation saved for Automation #${item.automationId}", Toast.LENGTH_SHORT).show()
                loadAllocations()
            } catch (e: Exception) {
                Toast.makeText(context, "Error saving: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    LaunchedEffect(Unit) {
        loadAllocations()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = "RISK & ALLOCATION",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = tokens.primaryText
                        )
                        Text(
                            text = "USER CAPITAL BUDGETING",
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
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background)
            )
        },
        containerColor = tokens.surface
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Summary Card
            item {
                OpheliaGlassCard(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Text(
                            text = "CAPITAL BUDGET ALLOCATION",
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold,
                            color = AccentBlue,
                            fontSize = 11.sp
                        )

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Column {
                                Text("Available Margin", style = MaterialTheme.typography.labelSmall, color = tokens.secondaryText)
                                Text(
                                    text = "$${String.format(Locale.US, "%.2f", availableCapital)} USDT",
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = BullishGreen,
                                    fontFamily = FontFamily.Monospace
                                )
                            }
                            Column {
                                Text("Total Allocated", style = MaterialTheme.typography.labelSmall, color = tokens.secondaryText)
                                Text(
                                    text = "$${String.format(Locale.US, "%.2f", totalAllocated)} USDT",
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = if (totalAllocated > availableCapital && availableCapital > 0) BearishRed else tokens.primaryText,
                                    fontFamily = FontFamily.Monospace
                                )
                            }
                            Column {
                                Text("Remaining", style = MaterialTheme.typography.labelSmall, color = tokens.secondaryText)
                                Text(
                                    text = "$${String.format(Locale.US, "%.2f", remainingAllocatable)} USDT",
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = AccentBlue,
                                    fontFamily = FontFamily.Monospace
                                )
                            }
                        }

                        Text(
                            text = "User capital allocation bounds maximum copy trade margin. If user allocation generates a quantity below BingX minimum notional ($5 USDT), VPS cleanly blocks execution without altering Admin strategy.",
                            style = MaterialTheme.typography.bodySmall,
                            color = tokens.secondaryText,
                            fontSize = 11.sp
                        )
                    }
                }
            }

            if (isLoading) {
                item {
                    Box(modifier = Modifier.fillMaxWidth().padding(32.dp), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = AccentBlue)
                    }
                }
            } else if (errorMessage != null) {
                item {
                    OpheliaGlassCard(modifier = Modifier.fillMaxWidth(), borderColor = BearishRed) {
                        Row(modifier = Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Icon(Icons.Default.Warning, contentDescription = null, tint = BearishRed)
                            Text(errorMessage ?: "", color = BearishRed, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            } else if (allocations.isEmpty()) {
                item {
                    OpheliaGlassCard(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                            Text("No active master automations available for allocation.", color = tokens.secondaryText, style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
            } else {
                items(allocations) { item ->
                    var inputStr by remember(item.automationId) { mutableStateOf(String.format(Locale.US, "%.2f", item.allocatedAmount)) }
                    var isItemEnabled by remember(item.automationId) { mutableStateOf(item.enabled) }

                    OpheliaGlassCard(modifier = Modifier.fillMaxWidth()) {
                        Column(
                            modifier = Modifier.padding(16.dp),
                            verticalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text(
                                        text = item.symbol ?: "ALL_WATCHLIST",
                                        style = MaterialTheme.typography.titleSmall,
                                        fontWeight = FontWeight.Bold,
                                        color = tokens.primaryText,
                                        fontFamily = FontFamily.Monospace
                                    )
                                    Text(
                                        text = "${item.strategy ?: "CORE"} (${item.timeframe ?: "5m"}) • Auto #${item.automationId}",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = tokens.secondaryText
                                    )
                                }

                                Switch(
                                    checked = isItemEnabled,
                                    onCheckedChange = {
                                        isItemEnabled = it
                                        item.enabled = it
                                        saveAllocation(item)
                                    },
                                    colors = SwitchDefaults.colors(
                                        checkedThumbColor = BullishGreen,
                                        checkedTrackColor = BullishGreen.copy(alpha = 0.3f)
                                    )
                                )
                            }

                            Divider(color = tokens.border.copy(alpha = 0.3f))

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(12.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                OutlinedTextField(
                                    value = inputStr,
                                    onValueChange = { inputStr = it },
                                    label = { Text("Budget (USDT)") },
                                    modifier = Modifier.weight(1f),
                                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                                    singleLine = true,
                                    colors = OutlinedTextFieldDefaults.colors(
                                        focusedBorderColor = AccentBlue,
                                        unfocusedBorderColor = tokens.border,
                                        focusedTextColor = tokens.primaryText,
                                        unfocusedTextColor = tokens.primaryText
                                    )
                                )

                                OpheliaButton(
                                    text = "SAVE",
                                    onClick = {
                                        val amt = inputStr.toDoubleOrNull() ?: 0.0
                                        if (amt < 0.0) {
                                            Toast.makeText(context, "Cannot be negative", Toast.LENGTH_SHORT).show()
                                            return@OpheliaButton
                                        }
                                        item.allocatedAmount = amt
                                        item.enabled = isItemEnabled
                                        saveAllocation(item)
                                    },
                                    modifier = Modifier.width(90.dp)
                                )
                            }

                            if ((inputStr.toDoubleOrNull() ?: 0.0) in 0.01..4.99) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                                ) {
                                    Icon(Icons.Default.Info, contentDescription = null, tint = AccentYellow, modifier = Modifier.size(14.dp))
                                    Text(
                                        text = "Below BingX minimum notional ($5 USDT). Sizing may block execution.",
                                        color = AccentYellow,
                                        fontSize = 11.sp
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
