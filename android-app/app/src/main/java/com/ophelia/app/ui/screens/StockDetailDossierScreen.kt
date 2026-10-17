package com.ophelia.app.ui.screens

import android.widget.Toast
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ophelia.app.models.*
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.GlassCard
import com.ophelia.app.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StockDetailDossierScreen(
    symbol: String,
    onBack: () -> Unit,
    isAdminRole: Boolean = true
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var dossier by remember { mutableStateOf<UsStockDossier?>(null) }
    var isLoading by remember { mutableStateOf(true) }
    var showTradeDialog by remember { mutableStateOf(false) }

    fun refreshDossier() {
        scope.launch {
            isLoading = true
            try {
                dossier = RetrofitClient.api.getUsStockDossier(symbol)
            } catch (e: Exception) {
                Toast.makeText(context, "Failed to load dossier: ${e.message}", Toast.LENGTH_SHORT).show()
            } finally {
                isLoading = false
            }
        }
    }

    LaunchedEffect(symbol) {
        refreshDossier()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(symbol, fontSize = 18.sp, fontWeight = FontWeight.Bold, color = PrimaryText)
                        Text(dossier?.name ?: "Stock Intelligence Dossier", fontSize = 11.sp, color = SecondaryText)
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back", tint = PrimaryText)
                    }
                },
                actions = {
                    IconButton(onClick = { refreshDossier() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = AccentCyan)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = BackgroundDark)
            )
        },
        containerColor = BackgroundDark
    ) { padding ->
        if (isLoading && dossier == null) {
            Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = AccentCyan)
            }
        } else {
            val d = dossier
            if (d == null) {
                Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                    Text("Stock data not found", color = SecondaryText)
                }
            } else {
                val changeColor = if (d.changePct >= 0) AccentGreen else Color(0xFFEF4444)
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding)
                        .verticalScroll(rememberScrollState())
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp)
                ) {
                    // Price & Primary Bias Card
                    GlassCard(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text("$${d.price}", fontSize = 26.sp, fontWeight = FontWeight.Bold, color = PrimaryText)
                                    Text(
                                        "${if (d.changePct >= 0) "+" else ""}${d.changePct}% Intraday",
                                        fontSize = 13.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = changeColor
                                    )
                                }
                                Column(horizontalAlignment = Alignment.End) {
                                    Surface(
                                        shape = RoundedCornerShape(6.dp),
                                        color = if (d.bias.contains("BULL")) AccentGreen.copy(alpha = 0.2f) else Color(0xFFEF4444).copy(alpha = 0.2f)
                                    ) {
                                        Text(
                                            d.bias,
                                            fontSize = 11.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = if (d.bias.contains("BULL")) AccentGreen else Color(0xFFEF4444),
                                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp)
                                        )
                                    }
                                    Spacer(Modifier.height(4.dp))
                                    val displayConf = if (d.confidence in 0.001..1.0) (d.confidence * 100.0).toInt() else d.confidence.toInt()
                                    Text("Confidence: ${displayConf}%", fontSize = 11.sp, color = AccentCyan)
                                }
                            }
                        }
                    }

                    // BingX TradFi Perpetual Mapping Card
                    GlassCard(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Text("BINGX TRADFI CONTRACT VERIFICATION", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = SecondaryText)
                            Spacer(Modifier.height(6.dp))
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text(d.bingxSymbol, fontSize = 14.sp, fontWeight = FontWeight.Bold, color = PrimaryText)
                                    Text("Continuous TradFi Perpetual Swap", fontSize = 10.sp, color = SecondaryText)
                                }
                                Surface(
                                    shape = RoundedCornerShape(4.dp),
                                    color = if (d.bingxState == "VERIFIED") AccentGreen.copy(alpha = 0.15f) else Color.Gray.copy(alpha = 0.15f)
                                ) {
                                    Text(
                                        d.bingxState,
                                        fontSize = 10.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = if (d.bingxState == "VERIFIED") AccentGreen else SecondaryText,
                                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                    )
                                }
                            }
                        }
                    }

                    // Volume & Market Structure
                    GlassCard(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Text("VOLUME & STRUCTURE TELEMETRY", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = SecondaryText)
                            Spacer(Modifier.height(10.dp))
                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Column {
                                    Text("RVOL", fontSize = 10.sp, color = SecondaryText)
                                    Text("${d.rvol}x", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = if (d.rvol > 1.5) AccentCyan else PrimaryText)
                                }
                                Column {
                                    Text("VWAP", fontSize = 10.sp, color = SecondaryText)
                                    Text("$${d.vwap}", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = PrimaryText)
                                }
                                Column {
                                    Text("VWAP RELATION", fontSize = 10.sp, color = SecondaryText)
                                    Text(d.vwapState, fontSize = 12.sp, fontWeight = FontWeight.Bold, color = if (d.vwapState == "ABOVE_VWAP") AccentGreen else Color(0xFFEF4444))
                                }
                                Column {
                                    Text("ORDER FLOW", fontSize = 10.sp, color = SecondaryText)
                                    Text(d.orderFlow, fontSize = 11.sp, color = SecondaryText)
                                }
                            }
                        }
                    }

                    // Options & GEX Telemetry
                    GlassCard(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Text("OPTIONS CHAINS & GEX TELEMETRY", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = SecondaryText)
                            Spacer(Modifier.height(6.dp))
                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text("Real Options Chains:", fontSize = 12.sp, color = SecondaryText)
                                Text(d.optionsState, fontSize = 12.sp, fontWeight = FontWeight.Bold, color = if (d.optionsState == "REAL_LIVE_FEED") AccentGreen else SecondaryText)
                            }
                            Spacer(Modifier.height(4.dp))
                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text("GEX Regime State:", fontSize = 12.sp, color = SecondaryText)
                                Text(d.gexState, fontSize = 12.sp, fontWeight = FontWeight.Bold, color = PrimaryText)
                            }
                        }
                    }

                    // Structural Targets & R:R
                    GlassCard(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Text("CANONICAL STRUCTURAL TARGETS & RISK", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = SecondaryText)
                            Spacer(Modifier.height(10.dp))
                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Column {
                                    Text("ENTRY REF", fontSize = 10.sp, color = SecondaryText)
                                    val displayEntry = if (d.entryReferencePrice > 0.0) "$${d.entryReferencePrice}" else if (d.price > 0.0) "$${d.price}" else "NOT_AVAILABLE"
                                    Text(displayEntry, fontSize = 13.sp, fontWeight = FontWeight.Bold, color = PrimaryText)
                                }
                                Column {
                                    Text("STOP LOSS", fontSize = 10.sp, color = SecondaryText)
                                    Text(if (d.slPrice != null && d.slPrice > 0.0) "$${d.slPrice}" else "EVALUATING", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFFEF4444))
                                }
                                Column {
                                    Text("REWARD/RISK", fontSize = 10.sp, color = SecondaryText)
                                    Text("${d.rrRatio} R", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = AccentGreen)
                                }
                            }
                            if (d.targets.isNotEmpty()) {
                                Spacer(Modifier.height(8.dp))
                                d.targets.forEachIndexed { i, t ->
                                    Row(
                                        modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp),
                                        horizontalArrangement = Arrangement.SpaceBetween
                                    ) {
                                        Text("TP${i+1} (${t.targetType}):", fontSize = 11.sp, color = SecondaryText)
                                        Text("$${t.targetPrice} (${t.rewardR}R)", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = AccentGreen)
                                    }
                                }
                            } else {
                                Spacer(Modifier.height(8.dp))
                                Text("Structural liquidity targets evaluating", fontSize = 11.sp, color = SecondaryText)
                            }
                        }
                    }

                    // What Ophelia Is Waiting For
                    GlassCard(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Text("WHAT OPHELIA IS WAITING FOR", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = AccentCyan)
                            Spacer(Modifier.height(6.dp))
                            Text(d.waitingFor, fontSize = 13.sp, color = PrimaryText, fontWeight = FontWeight.Medium)
                            Spacer(Modifier.height(4.dp))
                            Text("Status: ${d.candidateState} • Strategy: ${d.overnightBias}", fontSize = 11.sp, color = SecondaryText)
                        }
                    }

                    // Admin Manual Execution Button
                    if (isAdminRole) {
                        Button(
                            onClick = { showTradeDialog = true },
                            colors = ButtonDefaults.buttonColors(containerColor = AccentCyan),
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(10.dp)
                        ) {
                            Icon(Icons.Default.PlayArrow, contentDescription = null, tint = BackgroundDark)
                            Spacer(Modifier.width(6.dp))
                            Text("EXECUTE SHADOW/PAPER TRADE", color = BackgroundDark, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                        }
                    }
                }
            }
        }
    }

    // Trade Dialog
    if (showTradeDialog && dossier != null) {
        val d = dossier!!
        var direction by remember { mutableStateOf(if (d.bias.contains("BEAR")) "SHORT" else "LONG") }
        var leverage by remember { mutableStateOf(5) }
        var marginStr by remember { mutableStateOf("50") }

        AlertDialog(
            onDismissRequest = { showTradeDialog = false },
            containerColor = CardBackground,
            title = { Text("Execute Trade for ${d.symbol}", color = PrimaryText, fontWeight = FontWeight.Bold) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("BingX Contract: ${d.bingxSymbol}", fontSize = 11.sp, color = AccentCyan)

                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(
                            onClick = { direction = "LONG" },
                            colors = ButtonDefaults.buttonColors(containerColor = if (direction == "LONG") AccentGreen else Color.DarkGray),
                            modifier = Modifier.weight(1f)
                        ) {
                            Text("LONG", color = Color.White)
                        }
                        Button(
                            onClick = { direction = "SHORT" },
                            colors = ButtonDefaults.buttonColors(containerColor = if (direction == "SHORT") Color(0xFFEF4444) else Color.DarkGray),
                            modifier = Modifier.weight(1f)
                        ) {
                            Text("SHORT", color = Color.White)
                        }
                    }

                    OutlinedTextField(
                        value = marginStr,
                        onValueChange = { marginStr = it },
                        label = { Text("Margin (USDT)") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        scope.launch {
                            try {
                                val m = marginStr.toDoubleOrNull() ?: 50.0
                                val res = RetrofitClient.api.executeUsManualTrade(
                                    UsManualTradeRequest(
                                        symbol = d.symbol,
                                        direction = direction,
                                        leverage = leverage,
                                        marginUsdt = m,
                                        reason = "Manual Admin Dossier Execution"
                                    )
                                )
                                Toast.makeText(context, "Trade Executed: ${res.positionId}", Toast.LENGTH_LONG).show()
                                showTradeDialog = false
                            } catch (e: Exception) {
                                Toast.makeText(context, "Failed: ${e.message}", Toast.LENGTH_SHORT).show()
                            }
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = AccentCyan)
                ) {
                    Text("Confirm Execution", color = BackgroundDark, fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                TextButton(onClick = { showTradeDialog = false }) { Text("Cancel", color = SecondaryText) }
            }
        )
    }
}
