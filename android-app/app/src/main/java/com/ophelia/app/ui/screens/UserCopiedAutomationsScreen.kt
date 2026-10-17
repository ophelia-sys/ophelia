package com.ophelia.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun UserCopiedAutomationsScreen(
    onBack: () -> Unit,
    onNavigateToAllocation: () -> Unit
) {
    val scope = rememberCoroutineScope()
    val tokens = OpheliaThemeTokens.colors

    var isLoading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    val automations = remember { mutableStateListOf<com.ophelia.app.models.AutomationConfig>() }

    fun loadAutomations() {
        scope.launch {
            isLoading = true
            errorMessage = null
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                val res = api.getAutomations()
                automations.clear()
                automations.addAll(res.automations)
            } catch (e: Exception) {
                errorMessage = e.message ?: "Failed to load automations"
            } finally {
                isLoading = false
            }
        }
    }

    LaunchedEffect(Unit) {
        loadAutomations()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = "COPIED AUTOMATIONS",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = tokens.primaryText
                        )
                        Text(
                            text = "ACTIVE MASTER STRATEGIES",
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
                    IconButton(onClick = { loadAutomations() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = AccentBlue)
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
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            item {
                OpheliaGlassCard(modifier = Modifier.fillMaxWidth()) {
                    Row(
                        modifier = Modifier.padding(14.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Icon(Icons.Default.Lock, contentDescription = null, tint = AccentBlue)
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = "ADMIN CONTROLLED STRATEGIES",
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.Bold,
                                color = AccentBlue
                            )
                            Text(
                                text = "Automations execute autonomously on the VPS. To customize your budget per strategy, tap Risk & Allocation.",
                                style = MaterialTheme.typography.bodySmall,
                                color = tokens.secondaryText,
                                fontSize = 11.sp
                            )
                        }
                        OpheliaButton(
                            text = "BUDGET",
                            onClick = onNavigateToAllocation,
                            modifier = Modifier.width(85.dp)
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
            } else if (automations.isEmpty()) {
                item {
                    OpheliaGlassCard(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                            Text("No master automations currently active.", color = tokens.secondaryText)
                        }
                    }
                }
            } else {
                items(automations) { a ->
                    val sym = a.symbol ?: a.symbols?.firstOrNull() ?: "ALL_WATCHLIST"
                    val strat = a.strategy
                    val tf = a.timeframe ?: "5m"
                    val dir = a.direction ?: "ANY"
                    val status = a.status ?: "ACTIVE"
                    val aid = a.id?.toInt() ?: 0

                    OpheliaGlassCard(modifier = Modifier.fillMaxWidth()) {
                        Column(
                            modifier = Modifier.padding(16.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text(
                                        text = sym,
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.Bold,
                                        color = tokens.primaryText,
                                        fontFamily = FontFamily.Monospace
                                    )
                                    Text(
                                        text = "$strat ($tf) • Direction: $dir",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = tokens.secondaryText
                                    )
                                }
                                Box(
                                    modifier = Modifier
                                        .padding(horizontal = 8.dp, vertical = 4.dp)
                                ) {
                                    Text(
                                        text = status,
                                        style = MaterialTheme.typography.labelSmall,
                                        fontWeight = FontWeight.Bold,
                                        color = BullishGreen,
                                        fontFamily = FontFamily.Monospace
                                    )
                                }
                            }

                            Divider(color = tokens.border.copy(alpha = 0.3f))

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(
                                    text = "Auto ID: #$aid",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = tokens.secondaryText
                                )
                                Text(
                                    text = "Replication: 24/7 VPS",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = AccentBlue
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
