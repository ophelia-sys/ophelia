package com.ophelia.app.ui.screens

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
fun UsMarketScreen(
    onBack: () -> Unit,
    onSelectStock: (String) -> Unit,
    isAdminRole: Boolean = true
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var overview by remember { mutableStateOf<UsMarketOverviewResponse?>(null) }
    var top100Stocks by remember { mutableStateOf<List<UsStockUniverseItem>>(emptyList()) }
    var marketMovers by remember { mutableStateOf<List<UsMoverItem>>(emptyList()) }
    var sectors by remember { mutableStateOf<List<UsSectorItem>>(emptyList()) }
    var overnightSetups by remember { mutableStateOf<List<UsOvernightCandidate>>(emptyList()) }
    var newsList by remember { mutableStateOf<List<UsNewsItem>>(emptyList()) }

    var selectedTab by remember { mutableStateOf(0) }
    var searchQuery by remember { mutableStateOf("") }
    var isLoading by remember { mutableStateOf(true) }

    fun refreshAll() {
        scope.launch {
            isLoading = true
            try {
                overview = RetrofitClient.api.getUsMarketOverview()
                top100Stocks = RetrofitClient.api.getUsTop100().stocks
                try {
                    marketMovers = RetrofitClient.api.getUsMarketMovers().movers
                } catch (e: Exception) {
                    marketMovers = emptyList()
                }
                sectors = RetrofitClient.api.getUsSectors().sectors
                overnightSetups = RetrofitClient.api.getUsOvernight().candidates
                newsList = RetrofitClient.api.getUsNews().news
            } catch (e: Exception) {
                Toast.makeText(context, "Error loading US Market: ${e.message}", Toast.LENGTH_SHORT).show()
            } finally {
                isLoading = false
            }
        }
    }

    LaunchedEffect(Unit) {
        refreshAll()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("US Market Intelligence", fontSize = 18.sp, fontWeight = FontWeight.Bold, color = PrimaryText)
                        Text("Top 100 Equities • Movers • Sectors • Overnight ML", fontSize = 11.sp, color = SecondaryText)
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back", tint = PrimaryText)
                    }
                },
                actions = {
                    IconButton(onClick = { refreshAll() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = AccentCyan)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = BackgroundDark)
            )
        },
        containerColor = BackgroundDark
    ) { padding ->
        if (isLoading && overview == null) {
            Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = AccentCyan)
            }
        } else {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
            ) {
                // Benchmarks & Session Banner
                overview?.let { ov ->
                    SessionAndBenchmarkHeader(ov)
                }

                // Tab Row
                ScrollableTabRow(
                    selectedTabIndex = selectedTab,
                    containerColor = CardBackground,
                    contentColor = AccentCyan,
                    edgePadding = 8.dp
                ) {
                    Tab(
                        selected = selectedTab == 0,
                        onClick = { selectedTab = 0 },
                        text = { Text("Top 100", fontSize = 12.sp, fontWeight = FontWeight.Bold) }
                    )
                    Tab(
                        selected = selectedTab == 1,
                        onClick = { selectedTab = 1 },
                        text = { Text("Movers", fontSize = 12.sp, fontWeight = FontWeight.Bold) }
                    )
                    Tab(
                        selected = selectedTab == 2,
                        onClick = { selectedTab = 2 },
                        text = { Text("Sectors", fontSize = 12.sp, fontWeight = FontWeight.Bold) }
                    )
                    Tab(
                        selected = selectedTab == 3,
                        onClick = { selectedTab = 3 },
                        text = { Text("Overnight ML", fontSize = 12.sp, fontWeight = FontWeight.Bold) }
                    )
                    Tab(
                        selected = selectedTab == 4,
                        onClick = { selectedTab = 4 },
                        text = { Text("News Wire", fontSize = 12.sp, fontWeight = FontWeight.Bold) }
                    )
                }

                when (selectedTab) {
                    0 -> Top100Tab(
                        stocks = top100Stocks,
                        searchQuery = searchQuery,
                        onSearchChange = { searchQuery = it },
                        onSelectStock = onSelectStock
                    )
                    1 -> MoversTab(
                        movers = marketMovers,
                        onSelectStock = onSelectStock
                    )
                    2 -> SectorsTab(sectors = sectors)
                    3 -> OvernightTab(
                        setups = overnightSetups,
                        isAdmin = isAdminRole,
                        onExecuteTrade = { cand ->
                            scope.launch {
                                try {
                                    val res = RetrofitClient.api.executeUsManualTrade(
                                        UsManualTradeRequest(
                                            symbol = cand.symbol,
                                            direction = cand.direction,
                                            reason = "Overnight candidate execution"
                                        )
                                    )
                                    Toast.makeText(context, "Trade Executed: ${res.positionId}", Toast.LENGTH_LONG).show()
                                    refreshAll()
                                } catch (e: Exception) {
                                    Toast.makeText(context, "Execution failed: ${e.message}", Toast.LENGTH_SHORT).show()
                                }
                            }
                        }
                    )
                    4 -> NewsTab(news = newsList)
                }
            }
        }
    }
}

@Composable
fun SessionAndBenchmarkHeader(ov: UsMarketOverviewResponse) {
    Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
        // Benchmarks Row 1: SPY, QQQ, IWM
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            listOf("SPY", "QQQ", "IWM").forEach { proxy ->
                val bm = ov.benchmarks[proxy]
                val change = bm?.changePct ?: 0.0
                val color = if (change >= 0) AccentGreen else Color(0xFFEF4444)
                Surface(
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(8.dp),
                    color = CardBackground,
                    border = androidx.compose.foundation.BorderStroke(1.dp, BorderColor.copy(alpha = 0.4f))
                ) {
                    Column(modifier = Modifier.padding(6.dp)) {
                        Text(proxy, fontSize = 10.sp, fontWeight = FontWeight.Bold, color = PrimaryText)
                        Text("$${bm?.price ?: 0.0}", fontSize = 11.sp, color = PrimaryText)
                        Text("${if (change >= 0) "+" else ""}$change%", fontSize = 9.sp, color = color, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }

        Spacer(Modifier.height(4.dp))

        // Benchmarks Row 2: S&P 500, NASDAQ, NYSE
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            listOf("S&P 500", "NASDAQ", "NYSE").forEach { proxy ->
                val bm = ov.benchmarks[proxy] ?: ov.benchmarks[if (proxy == "S&P 500") "^GSPC" else if (proxy == "NASDAQ") "^IXIC" else "^NYA"]
                val change = bm?.changePct ?: 0.0
                val color = if (change >= 0) AccentGreen else Color(0xFFEF4444)
                Surface(
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(8.dp),
                    color = CardBackground,
                    border = androidx.compose.foundation.BorderStroke(1.dp, BorderColor.copy(alpha = 0.4f))
                ) {
                    Column(modifier = Modifier.padding(6.dp)) {
                        Text(proxy, fontSize = 10.sp, fontWeight = FontWeight.Bold, color = AccentCyan)
                        Text("$${bm?.price ?: 0.0}", fontSize = 11.sp, color = PrimaryText)
                        Text("${if (change >= 0) "+" else ""}$change%", fontSize = 9.sp, color = color, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }

        Spacer(Modifier.height(8.dp))

        // Session Status Line
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Surface(
                    shape = RoundedCornerShape(4.dp),
                    color = Color(0xFF38BDF8).copy(alpha = 0.2f)
                ) {
                    Text(
                        ov.session.underlying,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF38BDF8),
                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                    )
                }
                Spacer(Modifier.width(6.dp))
                Text("BingX TradFi: ${ov.session.bingx}", fontSize = 10.sp, color = SecondaryText)
            }
            Text("Regime: ${ov.marketRegime}", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = if (ov.marketRegime == "RISK_ON") AccentGreen else AccentCyan)
        }
    }
}

@Composable
fun Top100Tab(
    stocks: List<UsStockUniverseItem>,
    searchQuery: String,
    onSearchChange: (String) -> Unit,
    onSelectStock: (String) -> Unit
) {
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        OutlinedTextField(
            value = searchQuery,
            onValueChange = onSearchChange,
            placeholder = { Text("Search by symbol, company, or sector...") },
            leadingIcon = { Icon(Icons.Default.Search, contentDescription = null, tint = SecondaryText) },
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )

        Spacer(Modifier.height(12.dp))

        val filtered = stocks.filter {
            searchQuery.isBlank() ||
            it.symbol.contains(searchQuery, ignoreCase = true) ||
            it.displayName.contains(searchQuery, ignoreCase = true) ||
            it.sector.contains(searchQuery, ignoreCase = true)
        }

        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(filtered, key = { it.symbol }) { stock ->
                val isPositive = stock.changePct >= 0
                val boxBgColor = if (isPositive) Color(0xFF064E3B).copy(alpha = 0.35f) else Color(0xFF7F1D1D).copy(alpha = 0.35f)
                val boxBorderColor = if (isPositive) AccentGreen.copy(alpha = 0.5f) else Color(0xFFEF4444).copy(alpha = 0.5f)
                val pctColor = if (isPositive) AccentGreen else Color(0xFFEF4444)

                Surface(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { onSelectStock(stock.symbol) },
                    shape = RoundedCornerShape(10.dp),
                    color = boxBgColor,
                    border = androidx.compose.foundation.BorderStroke(1.dp, boxBorderColor)
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text("#${stock.rank}", fontSize = 11.sp, color = SecondaryText)
                                Spacer(Modifier.width(6.dp))
                                Text(stock.symbol, fontSize = 16.sp, fontWeight = FontWeight.Bold, color = PrimaryText)
                                Spacer(Modifier.width(8.dp))
                                Surface(
                                    shape = RoundedCornerShape(4.dp),
                                    color = if (stock.isBingxSupported) AccentGreen.copy(alpha = 0.2f) else Color.Gray.copy(alpha = 0.2f)
                                ) {
                                    Text(
                                        if (stock.isBingxSupported) "BINGX" else "TRADFI",
                                        fontSize = 9.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = if (stock.isBingxSupported) AccentGreen else SecondaryText,
                                        modifier = Modifier.padding(horizontal = 5.dp, vertical = 1.dp)
                                    )
                                }
                            }
                            Column(horizontalAlignment = Alignment.End) {
                                Text(
                                    if (stock.price > 0.0) "$${stock.price}" else "--",
                                    fontSize = 14.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = PrimaryText
                                )
                                Text(
                                    "${if (isPositive) "+" else ""}${stock.changePct}%",
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = pctColor
                                )
                            }
                        }
                        Spacer(Modifier.height(6.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(stock.displayName, fontSize = 11.sp, color = SecondaryText, maxLines = 1, modifier = Modifier.weight(1f))
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Surface(
                                    shape = RoundedCornerShape(3.dp),
                                    color = CardBackground
                                ) {
                                    Text(stock.sector, fontSize = 10.sp, color = AccentCyan, modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
                                }
                                Spacer(Modifier.width(6.dp))
                                Surface(
                                    shape = RoundedCornerShape(3.dp),
                                    color = if (stock.bias.contains("BULL")) AccentGreen.copy(alpha = 0.2f) else if (stock.bias.contains("BEAR")) Color(0xFFEF4444).copy(alpha = 0.2f) else CardBackground
                                ) {
                                    Text(
                                        stock.bias,
                                        fontSize = 9.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = if (stock.bias.contains("BULL")) AccentGreen else if (stock.bias.contains("BEAR")) Color(0xFFEF4444) else SecondaryText,
                                        modifier = Modifier.padding(horizontal = 5.dp, vertical = 2.dp)
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

@Composable
fun MoversTab(
    movers: List<UsMoverItem>,
    onSelectStock: (String) -> Unit
) {
    if (movers.isEmpty()) {
        Box(Modifier.fillMaxSize().padding(32.dp), contentAlignment = Alignment.Center) {
            Text("Evaluating top impact market movers...", color = SecondaryText, fontSize = 13.sp)
        }
    } else {
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            item {
                Text(
                    "TOP 10 MARKET MOVERS (COMPOSITE IMPACT SCORE)",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    color = SecondaryText
                )
                Spacer(Modifier.height(4.dp))
            }
            items(movers) { m ->
                val isPositive = m.changePct >= 0
                val pctColor = if (isPositive) AccentGreen else Color(0xFFEF4444)
                GlassCard(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { onSelectStock(m.symbol) }
                ) {
                    Column(modifier = Modifier.padding(14.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(m.symbol, fontSize = 16.sp, fontWeight = FontWeight.Bold, color = PrimaryText)
                                Spacer(Modifier.width(8.dp))
                                Surface(
                                    shape = RoundedCornerShape(4.dp),
                                    color = AccentCyan.copy(alpha = 0.2f)
                                ) {
                                    Text(
                                        "Impact: ${m.impactScore}",
                                        fontSize = 10.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = AccentCyan,
                                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                    )
                                }
                            }
                            Column(horizontalAlignment = Alignment.End) {
                                Text("$${m.price}", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = PrimaryText)
                                Text("${if (isPositive) "+" else ""}${m.changePct}%", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = pctColor)
                            }
                        }
                        Spacer(Modifier.height(8.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text("${m.name} • ${m.sector}", fontSize = 11.sp, color = SecondaryText, maxLines = 1, modifier = Modifier.weight(1f))
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text("RVOL ${m.rvol}x", fontSize = 10.sp, color = AccentCyan, fontWeight = FontWeight.Bold)
                                Spacer(Modifier.width(6.dp))
                                Text("Bias: ${m.bias}", fontSize = 10.sp, color = if (m.bias.contains("BULL")) AccentGreen else if (m.bias.contains("BEAR")) Color(0xFFEF4444) else SecondaryText, fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun SectorsTab(sectors: List<UsSectorItem>) {
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        items(sectors) { sec ->
            val perfColor = if (sec.performance >= 0) AccentGreen else Color(0xFFEF4444)
            GlassCard(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(14.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text(sec.sector, fontSize = 14.sp, fontWeight = FontWeight.Bold, color = PrimaryText)
                            Text("Proxy: ${sec.displayProxy}", fontSize = 11.sp, color = SecondaryText)
                        }
                        Text(
                            "${if (sec.performance >= 0) "+" else ""}${sec.performance}%",
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold,
                            color = perfColor
                        )
                    }
                    Spacer(Modifier.height(8.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("Advancing: ${sec.advancingStocks} | Declining: ${sec.decliningStocks}", fontSize = 11.sp, color = SecondaryText)
                        Text("Breadth: ${sec.displayBreadth}", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = AccentCyan)
                    }
                }
            }
        }
    }
}

@Composable
fun OvernightTab(
    setups: List<UsOvernightCandidate>,
    isAdmin: Boolean,
    onExecuteTrade: (UsOvernightCandidate) -> Unit
) {
    if (setups.isEmpty()) {
        Box(Modifier.fillMaxSize().padding(32.dp), contentAlignment = Alignment.Center) {
            Text("No active overnight setups qualified at this hour.", color = SecondaryText, fontSize = 13.sp)
        }
    } else {
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            items(setups, key = { it.candidateId }) { cand ->
                val dirColor = if (cand.direction == "LONG") AccentGreen else Color(0xFFEF4444)
                GlassCard(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(cand.symbol, fontSize = 16.sp, fontWeight = FontWeight.Bold, color = PrimaryText)
                                Spacer(Modifier.width(8.dp))
                                Surface(
                                    shape = RoundedCornerShape(4.dp),
                                    color = dirColor.copy(alpha = 0.2f)
                                ) {
                                    Text(
                                        cand.direction,
                                        fontSize = 11.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = dirColor,
                                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                    )
                                }
                            }
                            Text("Conf: ${cand.confidence.toInt()}%", fontSize = 12.sp, color = AccentCyan, fontWeight = FontWeight.Bold)
                        }

                        Spacer(Modifier.height(8.dp))
                        Text(cand.thesis, fontSize = 12.sp, color = SecondaryText)
                        Spacer(Modifier.height(10.dp))

                        // Price and targets
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("Entry: $${cand.entryPrice}", fontSize = 11.sp, color = PrimaryText)
                            Text("SL: $${cand.slPrice}", fontSize = 11.sp, color = Color(0xFFEF4444))
                            Text("R:R: ${cand.rrRatio}", fontSize = 11.sp, color = AccentGreen, fontWeight = FontWeight.Bold)
                        }

                        if (isAdmin) {
                            Spacer(Modifier.height(12.dp))
                            Button(
                                onClick = { onExecuteTrade(cand) },
                                colors = ButtonDefaults.buttonColors(containerColor = dirColor),
                                modifier = Modifier.fillMaxWidth(),
                                shape = RoundedCornerShape(8.dp)
                            ) {
                                Text("Execute Shadow Trade", color = Color.White, fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun NewsTab(news: List<UsNewsItem>) {
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        items(news) { item ->
            val sentColor = when (item.displaySentiment) {
                "BULLISH" -> AccentGreen
                "BEARISH" -> Color(0xFFEF4444)
                else -> SecondaryText
            }
            GlassCard(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(14.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(item.displaySource, fontSize = 10.sp, color = SecondaryText)
                        Surface(
                            shape = RoundedCornerShape(4.dp),
                            color = sentColor.copy(alpha = 0.15f)
                        ) {
                            Text(
                                item.displaySentiment,
                                fontSize = 9.sp,
                                color = sentColor,
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp)
                            )
                        }
                    }
                    Spacer(Modifier.height(6.dp))
                    Text(item.displayHeadline, fontSize = 13.sp, fontWeight = FontWeight.Medium, color = PrimaryText)
                    if (item.safeSymbols.isNotEmpty()) {
                        Spacer(Modifier.height(6.dp))
                        Text("Tickers: ${item.safeSymbols.joinToString(", ")}", fontSize = 10.sp, color = AccentCyan)
                    }
                }
            }
        }
    }
}
