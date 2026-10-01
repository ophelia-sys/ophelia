package com.ophelia.app.ui.screens

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.ophelia.app.auth.TokenManager
import com.ophelia.app.models.*
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.theme.*
import com.ophelia.app.ui.viewmodels.UiState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class MlViewModel(private val tokenManager: TokenManager) : ViewModel() {
    private val _mlState = MutableStateFlow<UiState<MlStateDto>>(UiState.Loading)
    val mlState = _mlState.asStateFlow()

    private val _setupsState = MutableStateFlow<UiState<List<SetupCandidateDto>>>(UiState.Loading)
    val setupsState = _setupsState.asStateFlow()

    var selectedSymbol by mutableStateOf("ALL")
        private set

    var selectedTimeframe by mutableStateOf("ALL")
        private set

    var isCreatingAutomation by mutableStateOf(false)
        private set

    var creationMessage by mutableStateOf<String?>(null)
        private set

    private val _timesfmForecast = MutableStateFlow<TimesFmForecastResponse?>(null)
    val timesfmForecast = _timesfmForecast.asStateFlow()

    fun fetchTimesFmForecast(symbol: String = "BTC-USDT") {
        viewModelScope.launch {
            try {
                val targetSym = if (symbol == "ALL") "BTC-USDT" else symbol
                val res = RetrofitClient.api.getTimesFmForecast(instrument = targetSym, timeframe = "15m", horizon = 10)
                _timesfmForecast.value = res
            } catch (_: Exception) {}
        }
    }

    init {
        fetchMlState("BTC-USDT")
        fetchSetups()
        fetchTimesFmForecast("BTC-USDT")
    }

    fun selectSymbol(sym: String) {
        selectedSymbol = sym
        fetchMlState(if (sym == "ALL") "BTC-USDT" else sym)
        fetchSetups()
        fetchTimesFmForecast(sym)
    }

    fun selectTimeframe(tf: String) {
        selectedTimeframe = tf
        fetchSetups()
    }

    fun fetchMlState(symbol: String) {
        viewModelScope.launch {
            _mlState.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val res = api.getMlState(symbol)
                _mlState.value = UiState.Success(res)
            } catch (e: Exception) {
                _mlState.value = UiState.Error(e.message ?: "Failed to load ML state")
            }
        }
    }

    fun fetchSetups() {
        viewModelScope.launch {
            _setupsState.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val symParam = if (selectedSymbol == "ALL") null else selectedSymbol
                val tfParam = if (selectedTimeframe == "ALL") null else {
                    if (selectedTimeframe == "1h") 60 else selectedTimeframe.replace("m", "").toIntOrNull()
                }
                val res = api.getMlSetups(symbol = symParam, timeframe = tfParam)
                _setupsState.value = UiState.Success(res.setups)
            } catch (e: Exception) {
                _setupsState.value = UiState.Error(e.message ?: "Failed to load active setups")
            }
        }
    }

    fun createAutomationFromSetup(setupId: String, onComplete: () -> Unit) {
        viewModelScope.launch {
            isCreatingAutomation = true
            creationMessage = null
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val res = api.createAutomationFromSetup(mapOf("setup_id" to setupId))
                creationMessage = "Automation #${res.automationId} successfully created for ${res.symbol}!"
                onComplete()
            } catch (e: Exception) {
                creationMessage = "Error: ${e.message ?: "Failed to create automation"}"
            } finally {
                isCreatingAutomation = false
            }
        }
    }

    fun clearMessage() {
        creationMessage = null
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MlScreen(
    onBack: (() -> Unit)? = null,
    onNavigateToAutomationBuilder: (() -> Unit)? = null,
    onNavigateToReviewSetup: ((String) -> Unit)? = null,
    onNavigateToBacktest: ((String) -> Unit)? = null
) {

    val context = LocalContext.current
    val tokenManager = remember { TokenManager(context) }
    val viewModel: MlViewModel = viewModel(
        factory = object : androidx.lifecycle.ViewModelProvider.Factory {
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                @Suppress("UNCHECKED_CAST")
                return MlViewModel(tokenManager) as T
            }
        }
    )

    val mlState by viewModel.mlState.collectAsState()
    val setupsState by viewModel.setupsState.collectAsState()

    var selectedDomain by remember { mutableStateOf("CRYPTO") }
    var cryptoExpanded by remember { mutableStateOf(true) }
    var usMarketExpanded by remember { mutableStateOf(false) }
    var goldExpanded by remember { mutableStateOf(false) }

    val cryptoSymbols = listOf("ALL", "BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT")
    val usSymbols = listOf("ALL", "SPY", "QQQ", "NVDA", "AAPL", "MSFT", "TSLA", "AMZN")
    val goldSymbols = listOf("GOLD (XAU)")

    val activeDomainSymbols = when (selectedDomain) {
        "US MARKET" -> usSymbols
        "COMMODITIES / GOLD" -> goldSymbols
        else -> cryptoSymbols
    }

    val timeframes = listOf("ALL", "3m", "5m", "15m", "30m", "1h")
    var priorityTradesOnly by remember { mutableStateOf(false) }

    LaunchedEffect(viewModel.creationMessage) {
        viewModel.creationMessage?.let { msg ->
            Toast.makeText(context, msg, Toast.LENGTH_LONG).show()
            viewModel.clearMessage()
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .statusBarsPadding()
    ) {
        // Header
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (onBack != null) {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = "Back", tint = MaterialTheme.colorScheme.onBackground)
                    }
                }
                Column {
                    Text(
                        text = "OPHELIA ML INTELLIGENCE",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Black,
                        letterSpacing = 1.sp,
                        color = MaterialTheme.colorScheme.onBackground
                    )
                    Text(
                        text = "AI-assisted market intelligence & setup research",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            IconButton(onClick = {
                viewModel.fetchMlState(viewModel.selectedSymbol)
                viewModel.fetchSetups()
            }) {
                Icon(Icons.Filled.Refresh, contentDescription = "Refresh", tint = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }

        // Mandatory AI Advisory Banner
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 4.dp)
                .clip(RoundedCornerShape(12.dp))
                .background(WarningAmber.copy(alpha = 0.10f))
                .border(1.dp, WarningAmber.copy(alpha = 0.40f), RoundedCornerShape(12.dp))
                .padding(12.dp)
        ) {
            Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Icon(
                    Icons.Filled.Warning,
                    contentDescription = "Advisory",
                    tint = WarningAmber,
                    modifier = Modifier.size(20.dp)
                )
                Column {
                    Text(
                        text = "AI ADVISORY ONLY — NO AUTONOMOUS EXECUTION",
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.Bold,
                        color = WarningAmber,
                        letterSpacing = 0.5.sp
                    )
                    Spacer(modifier = Modifier.height(2.dp))
                    Text(
                        text = "Ophelia ML Intelligence generates hypotheses and detects setups. The deterministic Ophelia engine is the sole execution authority.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 11.sp,
                        lineHeight = 15.sp
                    )
                }
            }
        }

        // TimesFM 3.0 Forecast Card (Shadow Mode)
        val tfmForecast by viewModel.timesfmForecast.collectAsState()
        if (tfmForecast != null) {
            val f = tfmForecast!!
            val q10 = f.quantiles["q10"]?.lastOrNull() ?: 0.0
            val q50 = f.quantiles["q50"]?.lastOrNull() ?: f.forecastValues.lastOrNull() ?: 0.0
            val q90 = f.quantiles["q90"]?.lastOrNull() ?: 0.0
            val isBull = f.forecastReturnPct > 0.05
            val isBear = f.forecastReturnPct < -0.05
            val dirColor = if (isBull) BullishGreen else if (isBear) BearishRed else TextSecondary

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(CardBackground)
                    .border(1.dp, BorderColor.copy(alpha = 0.5f), RoundedCornerShape(12.dp))
                    .padding(12.dp)
            ) {
                Column {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                "TIMESFM 3.0",
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.Bold,
                                color = PrimaryText,
                                letterSpacing = 0.5.sp
                            )
                            Spacer(Modifier.width(6.dp))
                            OpheliaStatusBadge(
                                status = "SHADOW",
                                color = AccentCyan,
                                showDot = false
                            )
                            Spacer(Modifier.width(6.dp))
                            OpheliaStatusBadge(
                                status = "CALIBRATING",
                                color = WarningAmber,
                                showDot = false
                            )
                        }
                        Text(
                            text = "${f.instrument} • ${f.timeframe}",
                            style = MaterialTheme.typography.labelSmall,
                            color = AccentCyan
                        )
                    }

                    Spacer(Modifier.height(8.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text(
                                text = "PROJECTED RETURN (H=${f.horizon} • 5m)",
                                style = MaterialTheme.typography.labelSmall,
                                color = TextMuted
                            )
                            Text(
                                text = "${f.direction}: ${if (f.forecastReturnPct >= 0) "+" else ""}${f.forecastReturnPct}%",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold,
                                color = dirColor
                            )
                        }
                        Column(horizontalAlignment = Alignment.End) {
                            Text(
                                text = "UNCERTAINTY SPREAD",
                                style = MaterialTheme.typography.labelSmall,
                                color = TextMuted
                            )
                            Text(
                                text = "±${f.quantileSpreadPct}%",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold,
                                color = WarningAmber
                            )
                        }
                    }

                    Spacer(Modifier.height(8.dp))
                    val q10Str = String.format(java.util.Locale.US, "%.2f", q10)
                    val q50Str = String.format(java.util.Locale.US, "%.2f", q50)
                    val q90Str = String.format(java.util.Locale.US, "%.2f", q90)
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(6.dp))
                            .background(SurfaceDark.copy(alpha = 0.6f))
                            .padding(horizontal = 8.dp, vertical = 4.dp),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("Q10: \$$q10Str", style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                        Text("Q50: \$$q50Str", style = MaterialTheme.typography.labelSmall, color = PrimaryText)
                        Text("Q90: \$$q90Str", style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                    }

                    Spacer(Modifier.height(6.dp))
                    val timeStr = if (f.forecastTimestamp > 0) java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.US).format(java.util.Date(f.forecastTimestamp)) else "LIVE"
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = "FRESHNESS: ${f.dataFreshness}",
                            style = MaterialTheme.typography.labelSmall,
                            color = if (f.dataFreshness == "FRESH") AccentGreen else WarningAmber,
                            fontSize = 10.sp
                        )
                        Text(
                            text = "TS: $timeStr",
                            style = MaterialTheme.typography.labelSmall,
                            color = TextMuted,
                            fontSize = 10.sp
                        )
                    }

                    Spacer(Modifier.height(4.dp))
                    Text(
                        text = "CALIBRATING: Shadow only. Zero direct trading authority. Confidence metric disabled pending empirical calibration sample.",
                        style = MaterialTheme.typography.labelSmall,
                        color = TextMuted,
                        fontSize = 10.sp
                    )
                }
            }
        }

        Spacer(Modifier.height(8.dp))

        // Three Collapsible Domain Navigation Sections (Crypto, US Market, Commodities / Gold)
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            listOf("CRYPTO", "US MARKET", "COMMODITIES / GOLD").forEach { domainName ->
                val isDomainActive = selectedDomain == domainName
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .clip(RoundedCornerShape(8.dp))
                        .background(if (isDomainActive) MaterialTheme.colorScheme.primary.copy(alpha = 0.22f) else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.4f))
                        .border(
                            1.dp,
                            if (isDomainActive) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline.copy(alpha = 0.2f),
                            RoundedCornerShape(8.dp)
                        )
                        .clickable {
                            selectedDomain = domainName
                            when (domainName) {
                                "CRYPTO" -> {
                                    cryptoExpanded = true
                                    viewModel.selectSymbol("ALL")
                                }
                                "US MARKET" -> {
                                    usMarketExpanded = true
                                    viewModel.selectSymbol("ALL")
                                }
                                "COMMODITIES / GOLD" -> {
                                    goldExpanded = true
                                    viewModel.selectSymbol("GOLD (XAU)")
                                }
                            }
                        }
                        .padding(vertical = 8.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "▼ $domainName",
                        fontWeight = if (isDomainActive) FontWeight.Bold else FontWeight.Medium,
                        color = if (isDomainActive) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 10.sp,
                        letterSpacing = 0.3.sp
                    )
                }
            }
        }

        Spacer(Modifier.height(8.dp))

        // Watchlist Selector Chips for Active Domain
        LazyRow(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(activeDomainSymbols) { sym ->
                val isSelected = sym == viewModel.selectedSymbol
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(10.dp))
                        .background(if (isSelected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant)
                        .border(
                            1.dp,
                            if (isSelected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline.copy(alpha = 0.3f),
                            RoundedCornerShape(10.dp)
                        )
                        .clickable { viewModel.selectSymbol(sym) }
                        .padding(horizontal = 14.dp, vertical = 6.dp)
                ) {
                    Text(
                        text = sym,
                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                        color = if (isSelected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 12.sp
                    )
                }
            }
        }

        Spacer(Modifier.height(6.dp))

        // Timeframe Selector Chips
        LazyRow(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            items(timeframes) { tf ->
                val isSelected = tf == viewModel.selectedTimeframe
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .background(if (isSelected) MaterialTheme.colorScheme.primary.copy(alpha = 0.20f) else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.50f))
                        .border(
                            1.dp,
                            if (isSelected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline.copy(alpha = 0.2f),
                            RoundedCornerShape(8.dp)
                        )
                        .clickable { viewModel.selectTimeframe(tf) }
                        .padding(horizontal = 10.dp, vertical = 4.dp)
                ) {
                    Text(
                        text = tf,
                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                        color = if (isSelected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 11.sp
                    )
                }
            }
            item {
                val isSelected = priorityTradesOnly
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .background(if (isSelected) BullishGreen.copy(alpha = 0.25f) else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.50f))
                        .border(
                            1.dp,
                            if (isSelected) BullishGreen else MaterialTheme.colorScheme.outline.copy(alpha = 0.2f),
                            RoundedCornerShape(8.dp)
                        )
                        .clickable { priorityTradesOnly = !priorityTradesOnly }
                        .padding(horizontal = 10.dp, vertical = 4.dp)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        Icon(
                            Icons.Filled.Star,
                            contentDescription = null,
                            tint = if (isSelected) BullishGreen else MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(12.dp)
                        )
                        Text(
                            text = "PRIORITY TRADES",
                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                            color = if (isSelected) BullishGreen else MaterialTheme.colorScheme.onSurfaceVariant,
                            fontSize = 11.sp
                        )
                    }
                }
            }
        }

        Spacer(Modifier.height(8.dp))

        when (val state = mlState) {
            is UiState.Loading -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
                }
            }
            is UiState.Error -> {
                Box(modifier = Modifier.fillMaxSize().padding(16.dp), contentAlignment = Alignment.Center) {
                    Text("Error: ${state.message}", color = MaterialTheme.colorScheme.error)
                }
            }
            is UiState.Success -> {
                val data = state.data
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp)
                ) {
                    // 1. Live Intelligence Status Strip
                    item {
                        OpheliaGlassCard {
                            Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                        Box(
                                            modifier = Modifier
                                                .size(8.dp)
                                                .clip(CircleShape)
                                                .background(BullishGreen)
                                        )
                                        Text(
                                            text = "OPHELIA ML INTELLIGENCE",
                                            style = MaterialTheme.typography.labelSmall,
                                            fontWeight = FontWeight.Bold,
                                            color = MaterialTheme.colorScheme.onSurface
                                        )
                                    }
                                    Text(
                                        text = "OLLAMA ACTIVE",
                                        style = MaterialTheme.typography.labelSmall,
                                        fontWeight = FontWeight.Bold,
                                        color = BullishGreen
                                    )
                                }

                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Column {
                                        Text("CONTINUOUS SCAN", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        Text("Rotating (5 Assets)", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface)
                                    }
                                    Column(horizontalAlignment = Alignment.End) {
                                        Text("MAX OPEN POSITIONS", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        val maxTrades = data.diagnostics["max_open_trades"] ?: data.features["max_open_trades"] ?: "Dynamic Cap"
                                        Text("$maxTrades (Authoritative Cap)", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
                                    }
                                }
                            }
                        }
                    }

                    // 1b. Institutional Daily Structural Bias Report
                    data.dailyBias?.let { bias ->
                        item {
                            DailyStructuralBiasCard(bias = bias)
                        }
                    }

                    // 2. Active Setup Discovery Feed
                    item {
                        OpheliaSectionHeader(title = "ACTIVE HIGH-PROBABILITY SETUPS")
                    }

                    when (val setups = setupsState) {
                        is UiState.Success -> {
                            val filteredSetups = setups.data.filter { setup ->
                                val matchesDomain = when (selectedDomain) {
                                    "CRYPTO" -> !setup.symbol.contains("GOLD") && !setup.symbol.contains("XAU") && !setup.symbol.contains("NCCO") && (setup.symbol.contains("-USDT") || setup.symbol.contains("USDT") || setup.symbol in listOf("BTC", "ETH", "SOL", "XRP"))
                                    "COMMODITIES / GOLD" -> setup.symbol.contains("GOLD") || setup.symbol.contains("XAU") || setup.symbol.contains("NCCO")
                                    "US MARKET" -> setup.symbol.startsWith("US.") || (!setup.symbol.contains("-USDT") && !setup.symbol.contains("XAU") && !setup.symbol.contains("GOLD"))
                                    else -> true
                                }
                                val matchesSymbol = when (viewModel.selectedSymbol) {
                                    "ALL" -> true
                                    "GOLD (XAU)" -> setup.symbol.contains("GOLD") || setup.symbol.contains("XAU") || setup.symbol.contains("NCCO")
                                    else -> setup.symbol.equals(viewModel.selectedSymbol, ignoreCase = true)
                                }
                                val matchesTf = if (viewModel.selectedTimeframe == "ALL") true else {
                                    val targetMinutes = if (viewModel.selectedTimeframe == "1h") 60 else viewModel.selectedTimeframe.replace("m", "").toIntOrNull() ?: 3
                                    setup.timeframe == targetMinutes
                                }
                                val isPriority = setup.priority == "HIGH" || setup.isPriority == true || (setup.priority == null && (setup.confidencePct ?: 0.0) >= 60.0 && setup.isGeometryValid != false)
                                matchesDomain && matchesSymbol && matchesTf && (!priorityTradesOnly || isPriority)
                            }

                            if (filteredSetups.isEmpty()) {
                                item {
                                    OpheliaGlassCard(
                                        borderColor = MaterialTheme.colorScheme.outline.copy(alpha = 0.3f)
                                    ) {
                                        Box(
                                            modifier = Modifier
                                                .fillMaxWidth()
                                                .padding(24.dp),
                                            contentAlignment = Alignment.Center
                                        ) {
                                            Column(
                                                horizontalAlignment = Alignment.CenterHorizontally,
                                                verticalArrangement = Arrangement.spacedBy(8.dp)
                                            ) {
                                                Icon(
                                                    Icons.Default.Search,
                                                    contentDescription = null,
                                                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                                                    modifier = Modifier.size(32.dp)
                                                )
                                                Text(
                                                    text = if (priorityTradesOnly) "No Priority Setups Found" else "No Setups Found",
                                                    style = MaterialTheme.typography.titleMedium,
                                                    color = MaterialTheme.colorScheme.onSurface,
                                                    fontWeight = FontWeight.Bold
                                                )
                                                Text(
                                                    text = if (priorityTradesOnly)
                                                        "No actionable priority setups currently found. Ophelia is scanning for setups approaching causal entry conditions (breakout confirmation, retest zone proximity, and volume confirmation)."
                                                    else
                                                        "Try selecting a different symbol or timeframe to see available breakout/retest candidates.",
                                                    style = MaterialTheme.typography.bodySmall,
                                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                                    textAlign = androidx.compose.ui.text.style.TextAlign.Center
                                                )
                                            }
                                        }
                                    }
                                }
                            } else {
                                items(filteredSetups, key = { it.setupId }) { setup ->
                                    Phase4SetupCandidateCard(
                                        setup = setup,
                                        viewModel = viewModel,
                                        onNavigateToBacktest = onNavigateToBacktest,
                                        onNavigateToReviewSetup = onNavigateToReviewSetup,
                                        onNavigateToAutomationBuilder = onNavigateToAutomationBuilder
                                    )
                                }
                            }
                        }
                        is UiState.Error -> {
                            item {
                                OpheliaGlassCard(
                                    borderColor = MaterialTheme.colorScheme.error.copy(alpha = 0.5f)
                                ) {
                                    Column(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(16.dp),
                                        horizontalAlignment = Alignment.CenterHorizontally,
                                        verticalArrangement = Arrangement.spacedBy(8.dp)
                                    ) {
                                        Text(
                                            text = "Failed to load candidate setups",
                                            style = MaterialTheme.typography.titleSmall,
                                            color = MaterialTheme.colorScheme.error,
                                            fontWeight = FontWeight.Bold
                                        )
                                        Text(
                                            text = setups.message,
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                            textAlign = androidx.compose.ui.text.style.TextAlign.Center
                                        )
                                        Button(
                                            onClick = { viewModel.fetchSetups() },
                                            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                                        ) {
                                            Text("Retry", style = MaterialTheme.typography.labelSmall)
                                        }
                                    }
                                }
                            }
                        }
                        else -> {
                            item {
                                Box(modifier = Modifier.fillMaxWidth().padding(16.dp), contentAlignment = Alignment.Center) {
                                    CircularProgressIndicator(modifier = Modifier.size(24.dp), color = MaterialTheme.colorScheme.primary)
                                }
                            }
                        }
                    }

                    // 3. Ophelia ML Multi-Agent Regime & Thesis Card
                    item {
                        OpheliaSectionHeader(title = "OPHELIA ML REGIME & THESIS")
                        Spacer(Modifier.height(6.dp))
                        OpheliaGlassCard {
                            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Column {
                                        Text(
                                            text = data.symbol,
                                            style = MaterialTheme.typography.titleLarge,
                                            fontWeight = FontWeight.Bold,
                                            color = MaterialTheme.colorScheme.onSurface
                                        )
                                        Text(
                                            text = "Framework: ${data.framework ?: "TauricResearch/TradingAgents v0.4.0"}",
                                            style = MaterialTheme.typography.bodySmall,
                                            fontWeight = FontWeight.SemiBold,
                                            color = MaterialTheme.colorScheme.primary
                                        )
                                        Text(
                                            text = "Engine: ${data.modelName}",
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                    }
                                    val biasColor = when (data.directionalBias) {
                                        "LONG" -> BullishGreen
                                        "SHORT" -> BearishRed
                                        else -> WarningAmber
                                    }
                                    Box(
                                        modifier = Modifier
                                            .clip(RoundedCornerShape(8.dp))
                                            .background(biasColor.copy(alpha = 0.15f))
                                            .border(1.dp, biasColor.copy(alpha = 0.40f), RoundedCornerShape(8.dp))
                                            .padding(horizontal = 12.dp, vertical = 6.dp)
                                    ) {
                                        Text(
                                            text = data.directionalBias,
                                            style = MaterialTheme.typography.labelMedium,
                                            fontWeight = FontWeight.Black,
                                            color = biasColor,
                                            letterSpacing = 1.sp
                                        )
                                    }
                                }

                                data.thesis?.let { th ->
                                    Box(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .clip(RoundedCornerShape(8.dp))
                                            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.4f))
                                            .padding(10.dp)
                                    ) {
                                        Text(
                                            text = th,
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurface,
                                            lineHeight = 16.sp
                                        )
                                    }
                                }

                                if (!data.bullCase.isNullOrBlank() || !data.bearCase.isNullOrBlank()) {
                                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                        data.bullCase?.takeIf { it.isNotBlank() }?.let { bull ->
                                            Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.Top) {
                                                Text("BULL:", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = BullishGreen)
                                                Text(bull, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 11.sp)
                                            }
                                        }
                                        data.bearCase?.takeIf { it.isNotBlank() }?.let { bear ->
                                            Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.Top) {
                                                Text("BEAR:", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = BearishRed)
                                                Text(bear, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 11.sp)
                                            }
                                        }
                                    }
                                }

                                Divider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.3f), thickness = 1.dp)

                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Column {
                                        Text("MARKET REGIME", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        Text(data.regime, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface)
                                    }
                                    Column {
                                        Text("FLOW SENTIMENT", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        Text(data.sentiment, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface)
                                    }
                                    Column(horizontalAlignment = Alignment.End) {
                                        Text("CONFIDENCE", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        Text("${(data.confidence * 100).toInt()}%", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
                                    }
                                }
                            }
                        }
                    }

                    // 4. Institutional Orderflow Features
                    item {
                        OpheliaSectionHeader(title = "INSTITUTIONAL METRICS")
                        Spacer(Modifier.height(6.dp))
                        OpheliaGlassCard {
                            Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                data.features.forEach { (k, v) ->
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Text(
                                            text = k.replace("_", " ").uppercase(),
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                            fontSize = 11.sp
                                        )
                                        val valColor = when (v) {
                                            "BULLISH", "SURGE", "BUY_DOMINANT", "IMPULSE_UP", "CLEAR_ABOVE" -> BullishGreen
                                            "BEARISH", "SELL_DOMINANT", "IMPULSE_DOWN", "CLEAR_BELOW" -> BearishRed
                                            "EXPANDED", "CHOP", "DIVERGENT" -> WarningAmber
                                            else -> MaterialTheme.colorScheme.onSurface
                                        }
                                        Text(
                                            text = v,
                                            style = MaterialTheme.typography.bodySmall,
                                            fontWeight = FontWeight.Bold,
                                            color = valColor,
                                            fontSize = 11.sp
                                        )
                                    }
                                    Divider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.2f), thickness = 1.dp)
                                }
                            }
                        }
                    }

                    // 5. System Safety Diagnostics
                    item {
                        OpheliaSectionHeader(title = "SYSTEM SAFETY & RISK BARRIERS")
                        Spacer(Modifier.height(6.dp))
                        OpheliaGlassCard {
                            Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Text("Execution Authority", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    Text("BLOCKED (Advisory Only)", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold, color = BearishRed)
                                }
                                Divider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.2f), thickness = 1.dp)
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Text("Fail-Closed Risk Barrier", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    Text("ENFORCED", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold, color = BullishGreen)
                                }
                                Divider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.2f), thickness = 1.dp)
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Text("Max Concurrent Positions", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    val maxTrades = data.diagnostics["max_open_trades"] ?: data.features["max_open_trades"] ?: "Dynamic Cap"
                                    Text("$maxTrades (Authoritative Cap)", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
                                }
                            }
                        }
                    }
                }
            }
            else -> {}
        }
    }
}

@Composable
fun DailyStructuralBiasCard(bias: com.ophelia.app.models.DailyStructuralBiasDto) {
    var expanded by remember { mutableStateOf(false) }
    val isLong = bias.dailyPreference.uppercase() == "LONG"
    val isShort = bias.dailyPreference.uppercase() == "SHORT"
    val prefColor = if (isLong) BullishGreen else if (isShort) BearishRed else WarningAmber

    OpheliaGlassCard(
        borderColor = prefColor.copy(alpha = 0.45f)
    ) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            // Header Row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(6.dp))
                            .background(prefColor.copy(alpha = 0.15f))
                            .padding(horizontal = 8.dp, vertical = 4.dp)
                    ) {
                        Text(
                            text = bias.dailyPreference,
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Black,
                            color = prefColor
                        )
                    }
                    Text(
                        text = "DAILY STRUCTURAL BIAS",
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                }
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(6.dp))
                        .background(MaterialTheme.colorScheme.surfaceVariant)
                        .padding(horizontal = 8.dp, vertical = 3.dp)
                ) {
                    Text(
                        text = bias.biasState,
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary,
                        fontSize = 10.sp
                    )
                }
            }

            // Metrics Strip
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text("CONFIDENCE", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 10.sp)
                    Text("${bias.confidencePct.toInt()}%", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold, color = prefColor)
                }
                Column {
                    Text("MULTI-FACTOR SCORE", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 10.sp)
                    Text(String.format(java.util.Locale.US, "%.2f", bias.multiFactorScore), style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text("COUNTER-TREND", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 10.sp)
                    Text(if (bias.allowsCounterTrend) "ALLOWED" else "BLOCKED", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold, color = if (bias.allowsCounterTrend) BullishGreen else BearishRed)
                }
            }

            // Structural Thesis
            Text(
                text = bias.structuralThesis,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurface,
                lineHeight = 16.sp
            )

            // Key Levels Preview
            if (bias.keyLevels.isNotEmpty()) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    bias.keyLevels.entries.take(4).forEach { (k, v) ->
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(4.dp))
                                .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f))
                                .padding(horizontal = 6.dp, vertical = 2.dp)
                        ) {
                            Text("$k: $v", fontSize = 9.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
                        }
                    }
                }
            }

            // Expandable Details (Supporting / Contradicting / Invalidation / Flips)
            if (expanded) {
                Divider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.2f))

                if (bias.supportingFactors.isNotEmpty()) {
                    Text("SUPPORTING FACTORS:", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = BullishGreen)
                    bias.supportingFactors.forEach { factor ->
                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.Top) {
                            Text("•", color = BullishGreen, fontWeight = FontWeight.Bold)
                            Text(factor, style = MaterialTheme.typography.bodySmall, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface)
                        }
                    }
                }

                if (bias.contradictingFactors.isNotEmpty()) {
                    Text("CONTRADICTING FACTORS:", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = BearishRed)
                    bias.contradictingFactors.forEach { factor ->
                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.Top) {
                            Text("•", color = BearishRed, fontWeight = FontWeight.Bold)
                            Text(factor, style = MaterialTheme.typography.bodySmall, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface)
                        }
                    }
                }

                if (bias.orderFlowCondition.isNotBlank()) {
                    Text("ORDER FLOW CONDITION: ${bias.orderFlowCondition}", style = MaterialTheme.typography.bodySmall, fontSize = 11.sp, color = MaterialTheme.colorScheme.primary)
                }

                if (bias.newsMacroBias.isNotBlank()) {
                    Text("NEWS / MACRO CONTEXT: ${bias.newsMacroBias}", style = MaterialTheme.typography.bodySmall, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }

                if (bias.invalidation.isNotBlank()) {
                    Text("INVALIDATION: ${bias.invalidation}", style = MaterialTheme.typography.bodySmall, fontSize = 11.sp, fontWeight = FontWeight.SemiBold, color = BearishRed)
                }

                if (bias.whatFlipsBias.isNotBlank()) {
                    Text("WHAT FLIPS THE BIAS: ${bias.whatFlipsBias}", style = MaterialTheme.typography.bodySmall, fontSize = 11.sp, color = WarningAmber)
                }

                Text(
                    text = bias.disclaimer.ifBlank { "Advisory preference report. Does NOT force execution. Setups validated on technical merits." },
                    style = MaterialTheme.typography.labelSmall,
                    fontSize = 9.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            // Expand / Collapse Toggle
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { expanded = !expanded }
                    .padding(vertical = 4.dp),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = if (expanded) "COLLAPSE DETAILS ▲" else "EXPAND INSTITUTIONAL FACTORS ▼",
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary,
                    fontSize = 10.sp
                )
            }
        }
    }
}

@Composable
fun Phase4SetupCandidateCard(
    setup: SetupCandidateDto,
    viewModel: MlViewModel,
    onNavigateToBacktest: ((String) -> Unit)?,
    onNavigateToReviewSetup: ((String) -> Unit)?,
    onNavigateToAutomationBuilder: (() -> Unit)?
) {
    val isLong = setup.direction.uppercase() == "LONG"
    val accentColor = if (isLong) BullishGreen else BearishRed
    val displaySymbol = setup.displaySymbol ?: setup.symbol
    var showReasons by remember { mutableStateOf(false) }
    var showConditions by remember { mutableStateOf(false) }

    val prio = setup.priority ?: if (setup.isPriority == true) "HIGH" else "MEDIUM"
    val prioColor = when (prio) {
        "HIGH" -> BullishGreen
        "MEDIUM" -> AccentTeal
        "LOW" -> MaterialTheme.colorScheme.onSurfaceVariant
        else -> BearishRed
    }

    OpheliaGlassCard(
        level = GlassLevel.L2,
        borderColor = if (prio == "HIGH") BullishGreen.copy(alpha = 0.6f) else accentColor.copy(alpha = 0.5f)
    ) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            // 1. Header: Direction, Priority, Symbol, Timeframe, Confidence
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(6.dp))
                            .background(accentColor.copy(alpha = 0.15f))
                            .padding(horizontal = 8.dp, vertical = 4.dp)
                    ) {
                        Text(
                            text = setup.direction,
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold,
                            color = accentColor
                        )
                    }
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(6.dp))
                            .background(prioColor.copy(alpha = 0.2f))
                            .padding(horizontal = 8.dp, vertical = 4.dp)
                    ) {
                        Text(
                            text = if (setup.actionabilityScore != null) "$prio (${setup.actionabilityScore?.toInt()})" else prio,
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold,
                            color = prioColor
                        )
                    }
                    Text(
                        text = displaySymbol,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Text(
                        text = "${setup.timeframe}m",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        text = "AI CONF: ${setup.confidencePct.toInt()}%",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = accentColor
                    )
                    Text(
                        text = "EMPIRICAL: NOT CALIBRATED",
                        style = MaterialTheme.typography.labelSmall,
                        fontSize = 9.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            // 2. HERO: "WHAT OPHELIA IS WAITING FOR"
            val waitingText = setup.waitingFor ?: "Scanning for setup confirmation"
            val nextEvent = setup.nextRequiredEvent ?: "CONFIRMATION"
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(10.dp))
                    .background(WarningAmber.copy(alpha = 0.08f))
                    .border(1.dp, WarningAmber.copy(alpha = 0.35f), RoundedCornerShape(10.dp))
                    .padding(10.dp)
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            Icon(
                                Icons.Filled.Info,
                                contentDescription = null,
                                tint = WarningAmber,
                                modifier = Modifier.size(14.dp)
                            )
                            Text(
                                text = "WHAT OPHELIA IS WAITING FOR",
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.Bold,
                                color = WarningAmber,
                                fontSize = 10.sp,
                                letterSpacing = 0.5.sp
                            )
                        }
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(4.dp))
                                .background(MaterialTheme.colorScheme.surfaceVariant)
                                .padding(horizontal = 6.dp, vertical = 2.dp)
                        ) {
                            Text(
                                text = "NEXT: $nextEvent",
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.Bold,
                                fontSize = 9.sp,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                        }
                    }

                    Text(
                        text = waitingText,
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface,
                        fontSize = 13.sp
                    )

                    // Real Retest Interval Display (Mandatory Retest Zone Monitor)
                    val zoneLow = (setup.zone?.get("low") as? Number)?.toDouble()
                        ?: (setup.entryConditions["zone_low"] as? Number)?.toDouble()
                    val zoneHigh = (setup.zone?.get("high") as? Number)?.toDouble()
                        ?: (setup.entryConditions["zone_high"] as? Number)?.toDouble()

                    if (zoneLow != null && zoneHigh != null && zoneLow > 0.0 && zoneHigh > 0.0) {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(6.dp))
                                .background(AccentTeal.copy(alpha = 0.12f))
                                .border(1.dp, AccentTeal.copy(alpha = 0.35f), RoundedCornerShape(6.dp))
                                .padding(horizontal = 8.dp, vertical = 4.dp)
                        ) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "RETEST ZONE: ${String.format(java.util.Locale.US, "%.2f", zoneLow)} → ${String.format(java.util.Locale.US, "%.2f", zoneHigh)}",
                                    style = MaterialTheme.typography.labelSmall,
                                    fontWeight = FontWeight.Bold,
                                    color = AccentTeal,
                                    fontSize = 11.sp
                                )
                                Text(
                                    text = "LIVE RETEST MONITOR",
                                    style = MaterialTheme.typography.labelSmall,
                                    fontSize = 9.sp,
                                    fontWeight = FontWeight.SemiBold,
                                    color = AccentTeal.copy(alpha = 0.8f)
                                )
                            }
                        }
                    }

                    // Volatility-Aware Distance & Retest State
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        val distPct = setup.distancePct ?: 0.0
                        val distAtr = setup.distanceAtr ?: 0.0
                        val proximityLabel = when {
                            distAtr <= 0.25 -> "ZONE TOUCH / AT ZONE"
                            distAtr <= 0.5 -> "NEAR RETEST ZONE"
                            distAtr <= 1.0 -> "APPROACHING ZONE"
                            else -> "DISTANT"
                        }
                        val proximityColor = when {
                            distAtr <= 0.25 -> BullishGreen
                            distAtr <= 0.5 -> AccentTeal
                            else -> MaterialTheme.colorScheme.onSurfaceVariant
                        }

                        Text(
                            text = "DISTANCE: ${String.format(java.util.Locale.US, "%.2f", distPct)}% (${String.format(java.util.Locale.US, "%.2f", distAtr)} ATR)",
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.SemiBold,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            fontSize = 10.sp
                        )
                        Text(
                            text = proximityLabel,
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold,
                            color = proximityColor,
                            fontSize = 10.sp
                        )
                    }
                }
            }

            // 3. Maturity Lifecycle Progress Strip
            val stages = listOf("ID", "WAITING", "TOUCHED", "REJECTION", "READY")
            val currentStageIdx = when (setup.currentState) {
                "IDENTIFIED" -> 0
                "WAITING_FOR_RETEST" -> 1
                "RETEST_TOUCHED" -> 2
                "CONFIRMING_REJECTION" -> 3
                "ENTRY_READY", "TRIGGERED" -> 4
                else -> 1
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                stages.forEachIndexed { idx, stageName ->
                    val isPastOrCurrent = idx <= currentStageIdx
                    val isCurrent = idx == currentStageIdx
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .size(if (isCurrent) 10.dp else 7.dp)
                                .clip(CircleShape)
                                .background(
                                    when {
                                        isCurrent -> BullishGreen
                                        isPastOrCurrent -> MaterialTheme.colorScheme.primary
                                        else -> MaterialTheme.colorScheme.outline.copy(alpha = 0.3f)
                                    }
                                )
                        )
                        Spacer(Modifier.width(4.dp))
                        Text(
                            text = stageName,
                            fontSize = 9.sp,
                            fontWeight = if (isCurrent) FontWeight.Bold else FontWeight.Normal,
                            color = if (isCurrent) BullishGreen else if (isPastOrCurrent) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f)
                        )
                    }
                }
            }

            // Thesis Text
            Text(
                text = setup.thesis,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurface
            )

            // 4. Strategy Conditions Dropdown/Grid
            if (setup.conditions.isNotEmpty()) {
                val metCount = setup.conditions.count { it.status == "MET" }
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(8.dp))
                        .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.35f))
                        .clickable { showConditions = !showConditions }
                        .padding(horizontal = 10.dp, vertical = 6.dp)
                ) {
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "STRATEGY CONDITIONS ($metCount/${setup.conditions.size} MET)",
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onSurface,
                                fontSize = 10.sp
                            )
                            Icon(
                                if (showConditions) Icons.Filled.KeyboardArrowUp else Icons.Filled.KeyboardArrowDown,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.size(16.dp)
                            )
                        }
                        if (showConditions) {
                            setup.conditions.forEach { cond ->
                                Row(
                                    modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(
                                        text = cond.name,
                                        style = MaterialTheme.typography.bodySmall,
                                        fontSize = 10.sp,
                                        color = MaterialTheme.colorScheme.onSurface,
                                        modifier = Modifier.weight(1f)
                                    )
                                    val (badgeText, badgeColor) = when (cond.status) {
                                        "MET" -> "✓ MET" to BullishGreen
                                        "PENDING" -> "● PENDING" to WarningAmber
                                        "NOT_AVAILABLE" -> "⊘ NOT AVAILABLE" to MaterialTheme.colorScheme.onSurfaceVariant
                                        "NOT_APPLICABLE" -> "— N/A" to MaterialTheme.colorScheme.onSurfaceVariant
                                        "INVALID" -> "✕ INVALID" to BearishRed
                                        else -> cond.status to MaterialTheme.colorScheme.onSurfaceVariant
                                    }
                                    Box(
                                        modifier = Modifier
                                            .clip(RoundedCornerShape(4.dp))
                                            .background(badgeColor.copy(alpha = 0.15f))
                                            .padding(horizontal = 6.dp, vertical = 2.dp)
                                    ) {
                                        Text(text = badgeText, fontSize = 9.sp, fontWeight = FontWeight.Bold, color = badgeColor)
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // 5. Explainable Priority Reasons Dropdown
            if (setup.priorityReasons.isNotEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(8.dp))
                        .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.35f))
                        .clickable { showReasons = !showReasons }
                        .padding(horizontal = 10.dp, vertical = 6.dp)
                ) {
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "WHY THIS PRIORITY? (${setup.priorityReasons.size} reasons)",
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.primary,
                                fontSize = 10.sp
                            )
                            Icon(
                                if (showReasons) Icons.Filled.KeyboardArrowUp else Icons.Filled.KeyboardArrowDown,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.size(16.dp)
                            )
                        }
                        if (showReasons) {
                            setup.priorityReasons.forEach { reason ->
                                Row(
                                    modifier = Modifier.fillMaxWidth().padding(vertical = 1.dp),
                                    verticalAlignment = Alignment.Top,
                                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                                ) {
                                    Text("•", fontSize = 10.sp, color = MaterialTheme.colorScheme.primary)
                                    Text(
                                        text = reason,
                                        style = MaterialTheme.typography.bodySmall,
                                        fontSize = 10.sp,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        lineHeight = 13.sp
                                    )
                                }
                            }
                        }
                    }
                }
            }

            // 6. Geometry Validity & Invalidation
            if (!setup.isGeometryValid) {
                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = BearishRedSoft,
                    border = androidx.compose.foundation.BorderStroke(1.dp, BearishRedBorder),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "⚠️ INVALID TARGET GEOMETRY: ${setup.geometryValidationError ?: "Hierarchy violation"}",
                            style = MaterialTheme.typography.labelSmall,
                            color = BearishRed,
                            fontWeight = FontWeight.Bold,
                            fontSize = 10.sp
                        )
                    }
                }
            }

            // Structural Targets & Stops Grid
            val isShort = setup.direction.uppercase() == "SHORT"
            val slDistMag = kotlin.math.abs(setup.slDistancePct ?: 0.50)
            val tp1DistMag = kotlin.math.abs(setup.tp1DistancePct ?: 0.75)
            val tp2DistMag = kotlin.math.abs(setup.tp2DistancePct ?: 1.25)
            val tp3DistMag = kotlin.math.abs(setup.tp3DistancePct ?: 2.20)

            val slDisplay = if (isShort) "+${String.format(java.util.Locale.US, "%.2f", slDistMag)}%" else "-${String.format(java.util.Locale.US, "%.2f", slDistMag)}%"
            val tp1Display = if (isShort) "-${String.format(java.util.Locale.US, "%.2f", tp1DistMag)}%" else "+${String.format(java.util.Locale.US, "%.2f", tp1DistMag)}%"
            val tp2Display = if (isShort) "-${String.format(java.util.Locale.US, "%.2f", tp2DistMag)}%" else "+${String.format(java.util.Locale.US, "%.2f", tp2DistMag)}%"
            val tp3Display = if (isShort) "-${String.format(java.util.Locale.US, "%.2f", tp3DistMag)}%" else "+${String.format(java.util.Locale.US, "%.2f", tp3DistMag)}%"

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text("ENTRY", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 10.sp)
                    val entPx = setup.entryPrice ?: setup.breakoutPrice ?: 0.0
                    Text(if (entPx > 0) String.format(java.util.Locale.US, "%.2f", entPx) else "—", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface)
                }
                Column {
                    Text("STRUCTURAL SL", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 10.sp)
                    Text("${setup.suggestedSl}", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold, color = BearishRed)
                    Text(slDisplay, fontSize = 9.sp, color = BearishRed)
                }
                Column {
                    Text("TARGET 1", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 10.sp)
                    Text("${setup.suggestedTp1}", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold, color = BullishGreen)
                    Text(tp1Display, fontSize = 9.sp, color = BullishGreen)
                }
                Column {
                    Text("TARGET 2", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 10.sp)
                    Text("${setup.suggestedTp2}", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold, color = BullishGreen)
                    Text(tp2Display, fontSize = 9.sp, color = BullishGreen)
                }
                if (setup.suggestedTp3 != null && setup.suggestedTp3 > 0) {
                    Column {
                        Text("TARGET 3", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 10.sp)
                        Text("${setup.suggestedTp3}", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold, color = BullishGreen)
                        Text(tp3Display, fontSize = 9.sp, color = BullishGreen)
                    }
                } else {
                    Column {
                        Text("TARGET 3", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 10.sp)
                        Text("UNAVAILABLE", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text("No swing level", fontSize = 9.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }

            // Canonical R:R Row (Reward / Risk)
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                val rrTp1 = setup.rewardRiskTp1 ?: setup.rewardRiskRatio ?: setup.riskReward
                val rrTp2 = setup.rewardRiskTp2 ?: (rrTp1 * 2.0)
                val rrTp3 = if (setup.suggestedTp3 != null && setup.suggestedTp3 > 0) setup.rewardRiskTp3 else null
                Text(
                    text = "R:R TP1 = ${String.format(java.util.Locale.US, "%.2f", rrTp1)}:1",
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary,
                    fontSize = 11.sp
                )
                Text(
                    text = "TP2 = ${String.format(java.util.Locale.US, "%.2f", rrTp2)}:1",
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = AccentTeal,
                    fontSize = 11.sp
                )
                if (rrTp3 != null) {
                    Text(
                        text = "TP3 = ${String.format(java.util.Locale.US, "%.2f", rrTp3)}:1",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = AccentPurple,
                        fontSize = 11.sp
                    )
                } else {
                    Text(
                        text = "TP3: N/A",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 11.sp
                    )
                }
            }

            // Action Buttons: [BACKTEST THIS SETUP], [REVIEW], [CREATE AUTO]
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                Button(
                    onClick = {
                        onNavigateToBacktest?.invoke(setup.setupId)
                    },
                    enabled = setup.isGeometryValid,
                    modifier = Modifier.weight(1.3f),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = AccentPurple)
                ) {
                    Icon(Icons.Filled.PlayArrow, contentDescription = null, modifier = Modifier.size(13.dp))
                    Spacer(Modifier.width(2.dp))
                    Text("BACKTEST THIS SETUP", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, fontSize = 9.sp)
                }

                OutlinedButton(
                    onClick = {
                        if (onNavigateToReviewSetup != null) {
                            onNavigateToReviewSetup(setup.setupId)
                        } else {
                            viewModel.selectSymbol(setup.symbol)
                        }
                    },
                    modifier = Modifier.weight(0.9f),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text("REVIEW", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, fontSize = 10.sp)
                }

                Button(
                    onClick = {
                        if (onNavigateToReviewSetup != null) {
                            onNavigateToReviewSetup(setup.setupId)
                        } else {
                            viewModel.createAutomationFromSetup(setup.setupId) {
                                onNavigateToAutomationBuilder?.invoke()
                            }
                        }
                    },
                    enabled = setup.isGeometryValid && !viewModel.isCreatingAutomation,
                    modifier = Modifier.weight(1.1f),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                ) {
                    Text("CREATE AUTO", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, fontSize = 10.sp)
                }
            }
        }
    }
}

