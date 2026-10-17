package com.ophelia.app.ui.screens

import android.widget.Toast
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
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
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
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
import kotlin.math.max
import kotlin.math.min

class WorldViewModel(private val tokenManager: TokenManager) : ViewModel() {
    private val _worldState = MutableStateFlow<UiState<WorldContextDto>>(UiState.Loading)
    val worldState = _worldState.asStateFlow()

    private val _mapState = MutableStateFlow<UiState<WorldMapResponse>>(UiState.Loading)
    val mapState = _mapState.asStateFlow()

    private val _newsCategories = MutableStateFlow<UiState<Map<String, List<WorldNewsItemDto>>>>(UiState.Loading)
    val newsCategories = _newsCategories.asStateFlow()

    private val _tradeCandidates = MutableStateFlow<UiState<List<NewsTradeCandidateDto>>>(UiState.Loading)
    val tradeCandidates = _tradeCandidates.asStateFlow()

    private val _economicEvents = MutableStateFlow<UiState<List<EconomicEventDto>>>(UiState.Loading)
    val economicEvents = _economicEvents.asStateFlow()

    var selectedCategory by mutableStateOf("MACRO")
        private set

    var selectedEvent by mutableStateOf<WorldEventDto?>(null)
        private set

    var isCreatingAutomation by mutableStateOf(false)
        private set

    var automationMessage by mutableStateOf<String?>(null)
        private set

    init {
        fetchWorldData()
    }

    fun selectCategory(cat: String) {
        selectedCategory = cat
    }

    fun selectEvent(event: WorldEventDto?) {
        selectedEvent = event
    }

    fun fetchWorldData() {
        viewModelScope.launch {
            _worldState.value = UiState.Loading
            _mapState.value = UiState.Loading
            _newsCategories.value = UiState.Loading
            _tradeCandidates.value = UiState.Loading
            _economicEvents.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val ctx = api.getWorldContext()
                _worldState.value = UiState.Success(ctx)

                val mapRes = api.getWorldMap()
                _mapState.value = UiState.Success(mapRes)
                if (mapRes.events.isNotEmpty() && selectedEvent == null) {
                    selectedEvent = mapRes.events.first()
                }

                try {
                    val catMap = api.getNewsCategories()
                    _newsCategories.value = UiState.Success(catMap)
                } catch (e: Exception) {
                    _newsCategories.value = UiState.Error(e.message ?: "Failed to load news feeds")
                }

                try {
                    val cand = api.getNewsTradeCandidates()
                    _tradeCandidates.value = UiState.Success(cand)
                } catch (e: Exception) {
                    _tradeCandidates.value = UiState.Error(e.message ?: "Failed to load trade candidates")
                }

                try {
                    val events = api.getEconomicEvents()
                    _economicEvents.value = UiState.Success(events)
                } catch (e: Exception) {
                    _economicEvents.value = UiState.Error(e.message ?: "Failed to load economic events")
                }
            } catch (e: Exception) {
                _worldState.value = UiState.Error(e.message ?: "Failed to load World context")
                _mapState.value = UiState.Error(e.message ?: "Failed to load map data")
            }
        }
    }

    fun createAutomationFromCandidate(candidateId: String, onComplete: () -> Unit) {
        viewModelScope.launch {
            isCreatingAutomation = true
            automationMessage = null
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val res = api.createAutomationFromNewsSetup(mapOf("candidate_id" to candidateId))
                automationMessage = "Created News Automation #${res.automationId} for ${res.symbol}!"
                onComplete()
            } catch (e: Exception) {
                automationMessage = "Error: ${e.message ?: "Failed to create news automation"}"
            } finally {
                isCreatingAutomation = false
            }
        }
    }

    fun clearMessage() {
        automationMessage = null
    }
}

@Composable
fun WorldScreen(
    onBack: (() -> Unit)? = null,
    onNavigateToAutomationBuilder: (() -> Unit)? = null
) {
    val context = LocalContext.current
    val tokenManager = remember { TokenManager(context) }
    val viewModel: WorldViewModel = viewModel(
        factory = object : androidx.lifecycle.ViewModelProvider.Factory {
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                @Suppress("UNCHECKED_CAST")
                return WorldViewModel(tokenManager) as T
            }
        }
    )

    val worldState by viewModel.worldState.collectAsState()
    val mapState by viewModel.mapState.collectAsState()
    val newsCategories by viewModel.newsCategories.collectAsState()
    val tradeCandidates by viewModel.tradeCandidates.collectAsState()
    val economicEvents by viewModel.economicEvents.collectAsState()

    val categories = listOf("MACRO", "GEOPOLITICS", "MARKETS", "CRYPTO", "ENERGY", "CENTRAL BANKS", "REGULATION")

    LaunchedEffect(viewModel.automationMessage) {
        viewModel.automationMessage?.let { msg ->
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
        // Top Header: WORLD CONTROL • FEED STATUS
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
                        text = "WORLD CONTROL",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Black,
                        letterSpacing = 1.sp,
                        color = MaterialTheme.colorScheme.onBackground
                    )
                    Text(
                        text = "Macro Intelligence & Geopolitical Event Hub",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                val currentFeedStatus = (worldState as? UiState.Success)?.data?.let {
                    it.feedStatus ?: it.marketEnvironment.feedStatus
                } ?: "LIVE"
                val feedColor = when (currentFeedStatus.uppercase()) {
                    "LIVE" -> BullishGreen
                    "DEGRADED" -> WarningAmber
                    else -> BearishRed
                }
                OpheliaStatusBadge(
                    status = "FEED: ${currentFeedStatus.uppercase()}",
                    color = feedColor,
                    showDot = (currentFeedStatus.uppercase() == "LIVE")
                )
                IconButton(onClick = { viewModel.fetchWorldData() }) {
                    Icon(Icons.Filled.Refresh, contentDescription = "Refresh", tint = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }

        when (val state = worldState) {
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
                val mapData = (mapState as? UiState.Success)?.data

                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 6.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp)
                ) {
                    // 1. Live Global Macro Benchmarks Strip
                    item {
                        OpheliaSectionHeader(title = "GLOBAL MACRO BENCHMARKS")
                        Spacer(Modifier.height(6.dp))
                        LazyRow(
                            horizontalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            val instruments = data.yahooInstruments
                            val defaultKeys = listOf("DXY", "US10Y", "SPX", "GOLD", "OIL", "BTC", "ETH")

                            items(defaultKeys) { key ->
                                val inst = instruments[key]
                                val priceStr = inst?.price?.let { String.format(java.util.Locale.US, "%.2f", it) } ?: "—"
                                val chg = inst?.changePct ?: 0.0
                                val isUp = chg >= 0.0
                                val chgColor = if (isUp) BullishGreen else BearishRed

                                Box(
                                    modifier = Modifier
                                        .width(130.dp)
                                        .clip(RoundedCornerShape(12.dp))
                                        .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.7f))
                                        .border(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.3f), RoundedCornerShape(12.dp))
                                        .padding(12.dp)
                                ) {
                                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                        Text(
                                            text = key,
                                            style = MaterialTheme.typography.labelSmall,
                                            fontWeight = FontWeight.Bold,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                        Text(
                                            text = priceStr,
                                            style = MaterialTheme.typography.bodyMedium,
                                            fontWeight = FontWeight.Black,
                                            color = MaterialTheme.colorScheme.onSurface
                                        )
                                        Text(
                                            text = "${if (isUp) "+" else ""}${String.format(java.util.Locale.US, "%.2f", chg)}%",
                                            style = MaterialTheme.typography.labelSmall,
                                            fontWeight = FontWeight.Bold,
                                            color = chgColor
                                        )
                                    }
                                }
                            }
                        }
                    }

                    // 2. News Category Selector
                    item {
                        OpheliaSectionHeader(title = "INTELLIGENCE CATEGORIES")
                        Spacer(Modifier.height(4.dp))
                        LazyRow(
                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            items(categories) { cat ->
                                val isSelected = cat == viewModel.selectedCategory
                                Box(
                                    modifier = Modifier
                                        .clip(RoundedCornerShape(8.dp))
                                        .background(if (isSelected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant)
                                        .border(
                                            1.dp,
                                            if (isSelected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline.copy(alpha = 0.3f),
                                            RoundedCornerShape(8.dp)
                                        )
                                        .clickable { viewModel.selectCategory(cat) }
                                        .padding(horizontal = 12.dp, vertical = 6.dp)
                                ) {
                                    Text(
                                        text = cat,
                                        fontSize = 11.sp,
                                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                                        color = if (isSelected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            }
                        }
                    }

                    // 3. Category News Feed (3-5 Items with Source Diversity & Provenance)
                    val catNewsList = (newsCategories as? UiState.Success)?.data?.get(viewModel.selectedCategory)
                        ?: emptyList()

                    if (catNewsList.isNotEmpty()) {
                        items(catNewsList) { item ->
                            ExpandableWorldNewsCard(item = item)
                        }
                    }

                    // 4. Interactive Global Event Map
                    item {
                        OpheliaSectionHeader(title = "INTERACTIVE GLOBAL EVENT MAP")
                        Spacer(Modifier.height(4.dp))

                        val allEvents = if (mapData?.events.isNullOrEmpty()) defaultWorldEvents else mapData!!.events
                        val activeEv = viewModel.selectedEvent ?: allEvents.firstOrNull()

                        InteractiveWorldMapCanvas(
                            events = allEvents,
                            selectedEvent = activeEv,
                            activeCategory = viewModel.selectedCategory,
                            onEventSelected = { viewModel.selectEvent(it) }
                        )

                        Spacer(Modifier.height(8.dp))

                        // Quick Event Selector Strip under map
                        LazyRow(
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            items(allEvents) { ev ->
                                val isSelected = ev.id == activeEv?.id
                                val catColor = when (ev.category.uppercase()) {
                                    "MACRO" -> AccentBlue
                                    "GEOPOLITICS" -> WarningAmber
                                    "MARKETS" -> AccentPurple
                                    "CRYPTO" -> AccentTeal
                                    "ENERGY" -> BearishRed
                                    else -> MaterialTheme.colorScheme.primary
                                }
                                Box(
                                    modifier = Modifier
                                        .clip(RoundedCornerShape(8.dp))
                                        .background(if (isSelected) catColor.copy(alpha = 0.25f) else MaterialTheme.colorScheme.surfaceVariant)
                                        .border(
                                            1.dp,
                                            if (isSelected) catColor else MaterialTheme.colorScheme.outline.copy(alpha = 0.3f),
                                            RoundedCornerShape(8.dp)
                                        )
                                        .clickable { viewModel.selectEvent(ev) }
                                        .padding(horizontal = 10.dp, vertical = 6.dp)
                                ) {
                                    Row(
                                        verticalAlignment = Alignment.CenterVertically,
                                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                                    ) {
                                        Box(
                                            modifier = Modifier
                                                .size(6.dp)
                                                .clip(CircleShape)
                                                .background(catColor)
                                        )
                                        Text(
                                            text = "${ev.category.uppercase()} • ${ev.title.take(24)}${if (ev.title.length > 24) "..." else ""}",
                                            fontSize = 10.sp,
                                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                                            color = if (isSelected) catColor else MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                    }
                                }
                            }
                        }
                    }

                    // 5. Selected Event Dossier
                    viewModel.selectedEvent?.let { ev ->
                        item {
                            OpheliaGlassCard(
                                borderColor = MaterialTheme.colorScheme.primary.copy(alpha = 0.5f)
                            ) {
                                Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                            Box(
                                                modifier = Modifier
                                                    .clip(RoundedCornerShape(6.dp))
                                                    .background(MaterialTheme.colorScheme.primaryContainer)
                                                    .padding(horizontal = 8.dp, vertical = 3.dp)
                                            ) {
                                                Text(
                                                    text = ev.category.uppercase(),
                                                    style = MaterialTheme.typography.labelSmall,
                                                    fontWeight = FontWeight.Bold,
                                                    color = MaterialTheme.colorScheme.primary
                                                )
                                            }
                                            val eventStatus = when ((ev.status ?: ev.dataStatus ?: "REFERENCE").uppercase()) {
                                                "LIVE" -> "LIVE"
                                                "STALE" -> "STALE"
                                                else -> "REFERENCE"
                                            }
                                            val eventColor = when (eventStatus) {
                                                "LIVE" -> BullishGreen
                                                "STALE" -> WarningAmber
                                                else -> AccentBlue
                                            }
                                            OpheliaStatusBadge(
                                                status = eventStatus,
                                                color = eventColor,
                                                showDot = (eventStatus == "LIVE")
                                            )
                                        }
                                        Text(
                                            text = ev.region ?: "GLOBAL",
                                            style = MaterialTheme.typography.labelSmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                    }

                                    Text(
                                        text = ev.title ?: "World Event",
                                        style = MaterialTheme.typography.titleSmall,
                                        fontWeight = FontWeight.Bold,
                                        color = MaterialTheme.colorScheme.onSurface
                                    )

                                    Text(
                                        text = ev.summary ?: "",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )

                                    if (ev.affectedAssets.isNotEmpty()) {
                                        Row(
                                            verticalAlignment = Alignment.CenterVertically,
                                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                                        ) {
                                            Text(
                                                text = "AFFECTED:",
                                                style = MaterialTheme.typography.labelSmall,
                                                fontWeight = FontWeight.Bold,
                                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                                fontSize = 10.sp
                                            )
                                            ev.affectedAssets.forEach { asset ->
                                                Box(
                                                    modifier = Modifier
                                                        .clip(RoundedCornerShape(4.dp))
                                                        .background(MaterialTheme.colorScheme.surfaceVariant)
                                                        .padding(horizontal = 6.dp, vertical = 2.dp)
                                                ) {
                                                    Text(asset, fontSize = 10.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface)
                                                }
                                            }
                                        }
                                    }

                                    if (!ev.opheliaRelevance.isNullOrEmpty()) {
                                        Divider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.2f))
                                        Text(
                                            text = "Ophelia Impact: ${ev.opheliaRelevance}",
                                            style = MaterialTheme.typography.bodySmall,
                                            fontWeight = FontWeight.SemiBold,
                                            color = MaterialTheme.colorScheme.primary,
                                            fontSize = 11.sp
                                        )
                                    }
                                }
                            }
                        }
                    }

                    // 6. News Trade Candidates (Deterministic News Trade Engine)
                    val candidates = (tradeCandidates as? UiState.Success)?.data ?: emptyList()
                    if (candidates.isNotEmpty()) {
                        item {
                            OpheliaSectionHeader(title = "HIGH-IMPACT NEWS TRADE CANDIDATES")
                        }
                        items(candidates) { cand ->
                            val isLong = cand.direction.uppercase() == "LONG"
                            val dirColor = if (isLong) BullishGreen else BearishRed

                            OpheliaGlassCard(borderColor = dirColor.copy(alpha = 0.45f)) {
                                Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                            Box(
                                                modifier = Modifier
                                                    .clip(RoundedCornerShape(6.dp))
                                                    .background(dirColor.copy(alpha = 0.15f))
                                                    .padding(horizontal = 8.dp, vertical = 4.dp)
                                            ) {
                                                Text(cand.direction, fontWeight = FontWeight.Bold, color = dirColor, style = MaterialTheme.typography.labelMedium)
                                            }
                                            Text(cand.symbol, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface, style = MaterialTheme.typography.titleMedium)
                                            Text("${cand.timeframe}m", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelSmall)
                                        }
                                        OpheliaStatusBadge(status = "TRADE ELIGIBLE", color = BullishGreen, showDot = true)
                                    }

                                    Text(
                                        text = "${cand.eventName} • ${cand.surprise}",
                                        style = MaterialTheme.typography.labelMedium,
                                        fontWeight = FontWeight.SemiBold,
                                        color = MaterialTheme.colorScheme.primary
                                    )

                                    Text(
                                        text = cand.thesis,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurface
                                    )

                                    // Targets & R:R Grid
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween
                                    ) {
                                        Column {
                                            Text("ENTRY", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 10.sp)
                                            Text(String.format(java.util.Locale.US, "%.2f", cand.entryPrice), style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface)
                                        }
                                        Column {
                                            Text("SL", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 10.sp)
                                            Text(String.format(java.util.Locale.US, "%.2f", cand.suggestedSl), style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold, color = BearishRed)
                                            Text("-${String.format(java.util.Locale.US, "%.2f", cand.slDistancePct)}%", fontSize = 9.sp, color = BearishRed)
                                        }
                                        Column {
                                            Text("TP1", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 10.sp)
                                            Text(String.format(java.util.Locale.US, "%.2f", cand.suggestedTp1), style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold, color = BullishGreen)
                                            Text("+${String.format(java.util.Locale.US, "%.2f", cand.tp1DistancePct)}%", fontSize = 9.sp, color = BullishGreen)
                                        }
                                        Column(horizontalAlignment = Alignment.End) {
                                            Text("R:R", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 10.sp)
                                            Text("${String.format(java.util.Locale.US, "%.2f", cand.rewardRiskRatio)}:1", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
                                        }
                                    }

                                    // Action Buttons: [VIEW NEWS TRADE] & [CREATE NEWS AUTOMATION]
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                                    ) {
                                        OutlinedButton(
                                            onClick = {
                                                Toast.makeText(context, "${cand.symbol} news candidate: ${cand.relevanceExplanation}", Toast.LENGTH_LONG).show()
                                            },
                                            modifier = Modifier.weight(1f),
                                            shape = RoundedCornerShape(10.dp)
                                        ) {
                                            Text("VIEW NEWS TRADE", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
                                        }

                                        Button(
                                            onClick = {
                                                viewModel.createAutomationFromCandidate(cand.candidateId) {
                                                    onNavigateToAutomationBuilder?.invoke()
                                                }
                                            },
                                            enabled = !viewModel.isCreatingAutomation,
                                            modifier = Modifier.weight(1.5f),
                                            shape = RoundedCornerShape(10.dp),
                                            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                                        ) {
                                            Icon(Icons.Filled.PlayArrow, contentDescription = null, modifier = Modifier.size(16.dp))
                                            Spacer(Modifier.width(4.dp))
                                            Text("CREATE AUTOMATION", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // 7. Daily Market Bias & Synthesis Card
                    item {
                        OpheliaSectionHeader(title = "DAILY MARKET BIAS & SYNTHESIS")
                        Spacer(Modifier.height(6.dp))
                        OpheliaGlassCard {
                            Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Column {
                                        Text("COMPOSITE BIAS", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        val bias = data.marketEnvironment.riskSentiment
                                        val biasColor = when {
                                            bias.contains("RISK_ON") || bias.contains("BULLISH") -> BullishGreen
                                            bias.contains("RISK_OFF") || bias.contains("BEARISH") -> BearishRed
                                            else -> WarningAmber
                                        }
                                        Text(bias, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Black, color = biasColor)
                                    }
                                    Box(
                                        modifier = Modifier
                                            .clip(RoundedCornerShape(8.dp))
                                            .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.15f))
                                            .padding(horizontal = 10.dp, vertical = 5.dp)
                                    ) {
                                        Text("ACTIVE TRADING ADVISORY", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
                                    }
                                }

                                if (data.bullishReasons.isNotEmpty()) {
                                    Text("KEY DRIVERS:", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    data.bullishReasons.forEach { r ->
                                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                                            Icon(Icons.Filled.KeyboardArrowUp, contentDescription = null, tint = BullishGreen, modifier = Modifier.size(12.dp))
                                            Text(r, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurface, fontSize = 11.sp)
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // 8. Scheduled Macro Events / Economic Calendar
                    item {
                        OpheliaSectionHeader(title = "SCHEDULED MACRO EVENTS")
                    }

                    val econEvents = (economicEvents as? UiState.Success)?.data ?: data.macroEvents.map { ev ->
                        EconomicEventDto(
                            eventId = null,
                            title = ev.title.ifBlank { ev.event ?: "Economic Event" },
                            impact = ev.impact,
                            currency = ev.currency,
                            timeUtc = ev.timeUtc ?: "Scheduled",
                            forecast = ev.forecast,
                            previous = ev.previous,
                            category = "MACRO",
                            status = "SCHEDULED"
                        )
                    }

                    if (econEvents.isEmpty()) {
                        item {
                            OpheliaGlassCard {
                                Box(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(16.dp),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text(
                                        text = "No scheduled high-impact releases recorded today.",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            }
                        }
                    } else {
                        items(econEvents) { ev ->
                            OpheliaGlassCard {
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(12.dp),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                        val evTitle = ev.title.ifBlank { ev.event ?: "Economic Event" }
                                        Text(
                                            text = evTitle,
                                            style = MaterialTheme.typography.bodyMedium,
                                            fontWeight = FontWeight.Bold,
                                            color = MaterialTheme.colorScheme.onSurface
                                        )
                                        val timeStr = ev.timeUtc ?: ev.scheduledTime ?: "Scheduled"
                                        Text(
                                            text = "${ev.currency} • $timeStr",
                                            style = MaterialTheme.typography.labelSmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                        val dataStr = buildString {
                                            ev.actual?.let { append("Actual: $it | ") }
                                            ev.forecast?.let { append("Forecast: $it | ") }
                                            ev.previous?.let { append("Prev: $it") }
                                        }.trim().removeSuffix("|")
                                        if (dataStr.isNotBlank()) {
                                            Text(
                                                text = dataStr,
                                                style = MaterialTheme.typography.bodySmall,
                                                fontSize = 10.sp,
                                                color = MaterialTheme.colorScheme.primary
                                            )
                                        }
                                        ev.surprise?.let { sur ->
                                            Text(
                                                text = "Surprise: $sur",
                                                style = MaterialTheme.typography.bodySmall,
                                                fontSize = 10.sp,
                                                fontWeight = FontWeight.SemiBold,
                                                color = if (sur.contains("Above") || sur.contains("+")) BullishGreen else WarningAmber
                                            )
                                        }
                                    }
                                    val impactText = ev.impact.uppercase()
                                    val isCritical = impactText == "CRITICAL" || impactText == "HIGH"
                                    Box(
                                        modifier = Modifier
                                            .clip(RoundedCornerShape(6.dp))
                                            .background(if (isCritical) BearishRed.copy(alpha = 0.15f) else MaterialTheme.colorScheme.primaryContainer)
                                            .padding(horizontal = 8.dp, vertical = 4.dp)
                                    ) {
                                        Text(
                                            text = impactText,
                                            style = MaterialTheme.typography.labelSmall,
                                            fontWeight = FontWeight.Bold,
                                            color = if (isCritical) BearishRed else MaterialTheme.colorScheme.primary
                                        )
                                    }
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

val defaultWorldEvents = listOf(
    WorldEventDto(
        id = "geo_redsea",
        title = "Red Sea Shipping Corridor Flow Disruption",
        category = "ENERGY",
        importance = "HIGH",
        lat = 14.5,
        lng = 42.8,
        region = "Middle East / Bab-el-Mandeb",
        summary = "Container freight re-routing around Cape of Good Hope sustaining elevated tanker spot rates.",
        affectedAssets = listOf("OIL", "BRENT", "GOLD"),
        opheliaRelevance = "Inflationary supply-chain friction; strengthens commodity hedges.",
        status = "REFERENCE"
    ),
    WorldEventDto(
        id = "geo_us_sec",
        title = "US Treasury Quarterly Refunding & Liquidity Guidance",
        category = "MACRO",
        importance = "CRITICAL",
        lat = 38.8951,
        lng = -77.0364,
        region = "Washington D.C., United States",
        summary = "Treasury maintains weighted issuance toward short-dated T-Bills, preserving banking reserve liquidity.",
        affectedAssets = listOf("US10Y", "DXY", "BTC"),
        opheliaRelevance = "Net positive liquidity environment for crypto and high-beta assets.",
        status = "REFERENCE"
    ),
    WorldEventDto(
        id = "geo_asia_tech",
        title = "Taiwan Semiconductor / Asian Chip Supply Acceleration",
        category = "MARKETS",
        importance = "MEDIUM",
        lat = 24.77,
        lng = 121.0,
        region = "Hsinchu, Taiwan",
        summary = "AI datacenter accelerator demand surges with 28% quarter-over-quarter wafer expansion.",
        affectedAssets = listOf("SPX", "NVDA", "SOL"),
        opheliaRelevance = "Bullish tech risk appetite spilling into decentralized compute tokens.",
        status = "REFERENCE"
    ),
    WorldEventDto(
        id = "geo_crypto_reg",
        title = "EU MiCA Stablecoin Compliance Enforcement Framework",
        category = "CRYPTO",
        importance = "HIGH",
        lat = 50.8503,
        lng = 4.3517,
        region = "Brussels, European Union",
        summary = "Tier-1 exchange orderbooks complete transition to licensed EUR/USDT pairings without capital outflow.",
        affectedAssets = listOf("BTC-USDT", "ETH-USDT", "XRP-USDT"),
        opheliaRelevance = "Regulatory derisking completed; institutional perpetual flow normalized.",
        status = "REFERENCE"
    ),
    WorldEventDto(
        id = "geo_strait_hormuz",
        title = "Persian Gulf Maritime Logistics & Energy Corridor Monitoring",
        category = "GEOPOLITICS",
        importance = "HIGH",
        lat = 26.56,
        lng = 56.25,
        region = "Strait of Hormuz",
        summary = "Naval patrol presence maintained amid regional diplomatic negotiations; crude volatility compressed.",
        affectedAssets = listOf("OIL", "GOLD"),
        opheliaRelevance = "Geopolitical risk premium steady; no immediate panic flight from crypto.",
        status = "REFERENCE"
    )
)

private fun buildContinentPaths(width: Float, height: Float, scale: Float, offsetX: Float, offsetY: Float): List<Path> {
    fun toPx(nx: Float, ny: Float): Offset {
        return Offset(nx * width * scale + offsetX, ny * height * scale + offsetY)
    }

    val paths = mutableListOf<Path>()

    // North America
    val naPoints = listOf(
        Pair(0.08f, 0.18f), Pair(0.13f, 0.13f), Pair(0.20f, 0.14f), Pair(0.26f, 0.10f),
        Pair(0.32f, 0.18f), Pair(0.31f, 0.28f), Pair(0.29f, 0.36f), Pair(0.27f, 0.42f),
        Pair(0.24f, 0.40f), Pair(0.22f, 0.44f), Pair(0.20f, 0.50f), Pair(0.18f, 0.45f),
        Pair(0.15f, 0.40f), Pair(0.16f, 0.30f), Pair(0.11f, 0.24f), Pair(0.08f, 0.18f)
    )
    val naPath = Path().apply {
        val first = toPx(naPoints[0].first, naPoints[0].second)
        moveTo(first.x, first.y)
        for (i in 1 until naPoints.size) {
            val pt = toPx(naPoints[i].first, naPoints[i].second)
            lineTo(pt.x, pt.y)
        }
        close()
    }
    paths.add(naPath)

    // Greenland
    val grPoints = listOf(
        Pair(0.34f, 0.08f), Pair(0.40f, 0.07f), Pair(0.42f, 0.14f), Pair(0.36f, 0.16f), Pair(0.34f, 0.08f)
    )
    val grPath = Path().apply {
        val first = toPx(grPoints[0].first, grPoints[0].second)
        moveTo(first.x, first.y)
        for (i in 1 until grPoints.size) {
            val pt = toPx(grPoints[i].first, grPoints[i].second)
            lineTo(pt.x, pt.y)
        }
        close()
    }
    paths.add(grPath)

    // South America
    val saPoints = listOf(
        Pair(0.27f, 0.52f), Pair(0.33f, 0.50f), Pair(0.40f, 0.55f), Pair(0.42f, 0.62f),
        Pair(0.39f, 0.72f), Pair(0.35f, 0.82f), Pair(0.32f, 0.88f), Pair(0.30f, 0.82f),
        Pair(0.28f, 0.70f), Pair(0.26f, 0.58f), Pair(0.27f, 0.52f)
    )
    val saPath = Path().apply {
        val first = toPx(saPoints[0].first, saPoints[0].second)
        moveTo(first.x, first.y)
        for (i in 1 until saPoints.size) {
            val pt = toPx(saPoints[i].first, saPoints[i].second)
            lineTo(pt.x, pt.y)
        }
        close()
    }
    paths.add(saPath)

    // Europe
    val euPoints = listOf(
        Pair(0.46f, 0.28f), Pair(0.48f, 0.22f), Pair(0.52f, 0.14f), Pair(0.57f, 0.12f),
        Pair(0.58f, 0.20f), Pair(0.61f, 0.24f), Pair(0.58f, 0.32f), Pair(0.54f, 0.35f),
        Pair(0.50f, 0.30f), Pair(0.46f, 0.28f)
    )
    val euPath = Path().apply {
        val first = toPx(euPoints[0].first, euPoints[0].second)
        moveTo(first.x, first.y)
        for (i in 1 until euPoints.size) {
            val pt = toPx(euPoints[i].first, euPoints[i].second)
            lineTo(pt.x, pt.y)
        }
        close()
    }
    paths.add(euPath)

    // Africa
    val afPoints = listOf(
        Pair(0.46f, 0.36f), Pair(0.56f, 0.35f), Pair(0.64f, 0.40f), Pair(0.66f, 0.46f),
        Pair(0.64f, 0.54f), Pair(0.60f, 0.68f), Pair(0.56f, 0.74f), Pair(0.51f, 0.70f),
        Pair(0.48f, 0.56f), Pair(0.44f, 0.46f), Pair(0.46f, 0.36f)
    )
    val afPath = Path().apply {
        val first = toPx(afPoints[0].first, afPoints[0].second)
        moveTo(first.x, first.y)
        for (i in 1 until afPoints.size) {
            val pt = toPx(afPoints[i].first, afPoints[i].second)
            lineTo(pt.x, pt.y)
        }
        close()
    }
    paths.add(afPath)

    // Asia
    val asPoints = listOf(
        Pair(0.62f, 0.22f), Pair(0.72f, 0.14f), Pair(0.85f, 0.14f), Pair(0.92f, 0.22f),
        Pair(0.90f, 0.32f), Pair(0.84f, 0.38f), Pair(0.82f, 0.48f), Pair(0.76f, 0.52f),
        Pair(0.73f, 0.42f), Pair(0.68f, 0.38f), Pair(0.64f, 0.42f), Pair(0.62f, 0.34f),
        Pair(0.62f, 0.22f)
    )
    val asPath = Path().apply {
        val first = toPx(asPoints[0].first, asPoints[0].second)
        moveTo(first.x, first.y)
        for (i in 1 until asPoints.size) {
            val pt = toPx(asPoints[i].first, asPoints[i].second)
            lineTo(pt.x, pt.y)
        }
        close()
    }
    paths.add(asPath)

    // Australia
    val auPoints = listOf(
        Pair(0.78f, 0.66f), Pair(0.84f, 0.62f), Pair(0.90f, 0.66f), Pair(0.89f, 0.76f),
        Pair(0.82f, 0.78f), Pair(0.78f, 0.72f), Pair(0.78f, 0.66f)
    )
    val auPath = Path().apply {
        val first = toPx(auPoints[0].first, auPoints[0].second)
        moveTo(first.x, first.y)
        for (i in 1 until auPoints.size) {
            val pt = toPx(auPoints[i].first, auPoints[i].second)
            lineTo(pt.x, pt.y)
        }
        close()
    }
    paths.add(auPath)

    return paths
}

@Composable
fun InteractiveWorldMapCanvas(
    events: List<WorldEventDto>,
    selectedEvent: WorldEventDto?,
    activeCategory: String = "ALL",
    onEventSelected: (WorldEventDto) -> Unit
) {
    var scale by remember { mutableStateOf(1f) }
    var offsetX by remember { mutableStateOf(0f) }
    var offsetY by remember { mutableStateOf(0f) }

    val primaryColor = MaterialTheme.colorScheme.primary
    val outlineColor = MaterialTheme.colorScheme.outline

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(240.dp)
            .clip(RoundedCornerShape(16.dp))
            .background(Color(0xFF0C1017))
            .border(1.dp, outlineColor.copy(alpha = 0.4f), RoundedCornerShape(16.dp))
            .pointerInput(events, scale, offsetX, offsetY) {
                detectTapGestures { tapOffset ->
                    val width = size.width
                    val height = size.height
                    var closestEvent: WorldEventDto? = null
                    var closestDist = Float.MAX_VALUE

                    events.forEach { ev ->
                        val normX = (ev.lng + 180f) / 360f
                        val normY = (90f - ev.lat) / 180f
                        val px = normX.toFloat() * width * scale + offsetX
                        val py = normY.toFloat() * height * scale + offsetY
                        val dx = tapOffset.x - px
                        val dy = tapOffset.y - py
                        val dist = kotlin.math.sqrt(dx * dx + dy * dy)
                        if (dist < 100f && dist < closestDist) {
                            closestDist = dist
                            closestEvent = ev
                        }
                    }
                    closestEvent?.let { onEventSelected(it) }
                }
            }
            .pointerInput(Unit) {
                detectTransformGestures { _, pan, zoom, _ ->
                    scale = max(0.8f, min(scale * zoom, 3.5f))
                    offsetX += pan.x
                    offsetY += pan.y
                }
            }
    ) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val width = size.width
            val height = size.height

            // 1. Coordinate Graticule Grid
            val lats = listOf(0.167f, 0.333f, 0.500f, 0.667f, 0.833f)
            lats.forEach { frac ->
                val y = frac * height * scale + offsetY
                val isEquator = frac == 0.5f
                drawLine(
                    color = if (isEquator) AccentBlue.copy(alpha = 0.35f) else outlineColor.copy(alpha = 0.12f),
                    start = Offset(0f, y),
                    end = Offset(width, y),
                    strokeWidth = if (isEquator) 1.5f else 1f
                )
            }
            val lngs = listOf(0.167f, 0.333f, 0.500f, 0.667f, 0.833f)
            lngs.forEach { frac ->
                val x = frac * width * scale + offsetX
                val isPrime = frac == 0.5f
                drawLine(
                    color = if (isPrime) AccentBlue.copy(alpha = 0.35f) else outlineColor.copy(alpha = 0.12f),
                    start = Offset(x, 0f),
                    end = Offset(x, height),
                    strokeWidth = if (isPrime) 1.5f else 1f
                )
            }

            // 2. High-Tech Continental Landmass Silhouettes
            val continentPaths = buildContinentPaths(width, height, scale, offsetX, offsetY)
            continentPaths.forEach { path ->
                drawPath(path = path, color = Color(0xFF141C28))
                drawPath(path = path, color = Color(0xFF263852), style = Stroke(width = 1.2f))
            }

            // 3. Global Financial Session Hubs (NY, London, Tokyo, Singapore, Dubai, Hong Kong)
            val hubs = listOf(
                Pair("NY", Pair(-74.00f, 40.71f)),
                Pair("LDN", Pair(-0.12f, 51.50f)),
                Pair("TYO", Pair(139.65f, 35.67f)),
                Pair("SIN", Pair(103.82f, 1.35f)),
                Pair("DXB", Pair(55.27f, 25.20f)),
                Pair("HKG", Pair(114.16f, 22.31f))
            )
            hubs.forEach { (_, coords) ->
                val nx = (coords.first + 180f) / 360f
                val ny = (90f - coords.second) / 180f
                val px = nx * width * scale + offsetX
                val py = ny * height * scale + offsetY
                val pt = Offset(px, py)
                drawCircle(color = AccentBlue.copy(alpha = 0.25f), radius = 6f * scale, center = pt)
                drawCircle(color = AccentBlue, radius = 2.5f * scale, center = pt)
            }

            // 4. Plot Geolocated Event Markers
            events.forEach { ev ->
                val normX = (ev.lng + 180f) / 360f
                val normY = (90f - ev.lat) / 180f
                val px = normX.toFloat() * width * scale + offsetX
                val py = normY.toFloat() * height * scale + offsetY
                val pt = Offset(px, py)

                val isSel = ev.id == selectedEvent?.id
                val isCatMatch = activeCategory == "ALL" || ev.category.equals(activeCategory, ignoreCase = true)
                val markerColor = when (ev.category.uppercase()) {
                    "MACRO" -> AccentBlue
                    "GEOPOLITICS" -> WarningAmber
                    "MARKETS" -> AccentPurple
                    "CRYPTO" -> AccentTeal
                    "ENERGY" -> BearishRed
                    else -> primaryColor
                }

                val baseAlpha = if (isCatMatch || isSel) 1f else 0.6f

                // Halo glow if selected
                if (isSel) {
                    drawCircle(color = markerColor.copy(alpha = 0.25f), radius = 22f * scale, center = pt)
                    drawCircle(color = markerColor.copy(alpha = 0.50f), radius = 14f * scale, center = pt, style = Stroke(width = 2f))
                    drawCircle(color = markerColor, radius = 7f * scale, center = pt)
                    drawCircle(color = Color.White, radius = 2.5f * scale, center = pt)
                } else {
                    if (isCatMatch) {
                        drawCircle(color = markerColor.copy(alpha = 0.20f), radius = 12f * scale, center = pt)
                    }
                    drawCircle(color = markerColor.copy(alpha = baseAlpha), radius = 5.5f * scale, center = pt)
                    drawCircle(color = Color.White.copy(alpha = baseAlpha), radius = 2f * scale, center = pt)
                }
            }
        }

        // Overlay Navigation Controls (+ / - / Reset)
        Column(
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(8.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            SmallFloatingActionButton(
                onClick = { scale = min(scale * 1.3f, 3.5f) },
                containerColor = MaterialTheme.colorScheme.surfaceVariant,
                contentColor = MaterialTheme.colorScheme.onSurface,
                modifier = Modifier.size(32.dp)
            ) {
                Icon(Icons.Filled.Add, contentDescription = "Zoom In", modifier = Modifier.size(16.dp))
            }
            SmallFloatingActionButton(
                onClick = { scale = max(scale / 1.3f, 0.8f) },
                containerColor = MaterialTheme.colorScheme.surfaceVariant,
                contentColor = MaterialTheme.colorScheme.onSurface,
                modifier = Modifier.size(32.dp)
            ) {
                Icon(Icons.Filled.Close, contentDescription = "Zoom Out", modifier = Modifier.size(16.dp))
            }
            SmallFloatingActionButton(
                onClick = {
                    scale = 1f
                    offsetX = 0f
                    offsetY = 0f
                },
                containerColor = MaterialTheme.colorScheme.surfaceVariant,
                contentColor = MaterialTheme.colorScheme.onSurface,
                modifier = Modifier.size(32.dp)
            ) {
                Icon(Icons.Filled.Refresh, contentDescription = "Reset", modifier = Modifier.size(16.dp))
            }
        }
    }
}

fun cleanNewsSource(source: String, category: String): String {
    val cat = category.uppercase().trim()
    return when {
        cat == "MACRO" -> "MACRO DESK"
        cat == "CENTRAL BANKS" || cat.contains("CENTRAL") -> "CENTRAL BANK WIRE"
        cat == "CRYPTO" -> "CRYPTO STRUCTURE DESK"
        cat == "GEOPOLITICS" -> "GEOPOLITICAL INTELLIGENCE"
        cat == "ENERGY" -> "ENERGY & COMMODITIES DESK"
        cat == "MARKETS" -> "GLOBAL MARKETS DESK"
        cat == "REGULATION" -> "REGULATORY SURVEILLANCE"
        else -> "${cat} DESK"
    }
}

fun cleanNewsText(text: String?): String {
    if (text.isNullOrBlank()) return ""
    return text
        .replace(Regex("(?i)Reported by\\s+[a-zA-Z0-9\\s&]+", RegexOption.IGNORE_CASE), "")
        .replace(Regex("(?i)Reported by Yahoo Finance", RegexOption.IGNORE_CASE), "")
        .replace(Regex("(?i)\\bYahoo Finance\\b", RegexOption.IGNORE_CASE), "Macro Intelligence")
        .replace(Regex("(?i)\\bCNBC\\b", RegexOption.IGNORE_CASE), "Financial Desk")
        .replace(Regex("(?i)\\bMarketWatch\\b", RegexOption.IGNORE_CASE), "Macro Wire")
        .replace(Regex("\\s{2,}", RegexOption.IGNORE_CASE), " ")
        .trim()
}

@Composable
fun ExpandableWorldNewsCard(item: com.ophelia.app.models.WorldNewsItemDto) {
    var expanded by remember { mutableStateOf(false) }
    val uriHandler = androidx.compose.ui.platform.LocalUriHandler.current

    val displaySource = remember(item.source, item.category) {
        cleanNewsSource(item.source, item.category)
    }
    val displayTitle = remember(item.title) {
        cleanNewsText(item.title)
    }
    val displaySummary = remember(item.shortSummary, item.summary) {
        cleanNewsText(item.shortSummary ?: item.summary)
    }

    OpheliaGlassCard {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            // Source & Status Row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(
                        text = displaySource,
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary
                    )
                    item.countryRegion?.let { reg ->
                        Text("• $reg", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    item.publishedTimeUtc?.let { pt ->
                        Text("• $pt", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 9.sp)
                    }
                }
                val itemStatus = (item.status ?: "LIVE").uppercase()
                val statusColor = if (itemStatus.contains("LIVE")) BullishGreen else AccentBlue
                OpheliaStatusBadge(status = itemStatus, color = statusColor, showDot = itemStatus.contains("LIVE"))
            }

            // Headline / Title
            Text(
                text = displayTitle,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurface
            )

            // Short Summary
            if (displaySummary.isNotBlank()) {
                Text(
                    text = displaySummary,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    lineHeight = 15.sp
                )
            }

            // Affected Assets
            if (item.affectedAssets.isNotEmpty()) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Text("AFFECTED:", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 9.sp)
                    item.affectedAssets.forEach { asset ->
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(4.dp))
                                .background(MaterialTheme.colorScheme.surfaceVariant)
                                .padding(horizontal = 6.dp, vertical = 2.dp)
                        ) {
                            Text(asset, fontSize = 9.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface)
                        }
                    }
                }
            }

            // 10-Point Expandable Dossier
            if (expanded) {
                Divider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.2f))

                item.whatChanged?.let {
                    val what = cleanNewsText(it)
                    if (what.isNotBlank()) {
                        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text("WHAT CHANGED", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary, fontSize = 10.sp)
                            Text(what, style = MaterialTheme.typography.bodySmall, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface)
                        }
                    }
                }

                item.whyItMatters?.let {
                    val why = cleanNewsText(it)
                    if (why.isNotBlank()) {
                        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text("WHY IT MATTERS", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = AccentPurple, fontSize = 10.sp)
                            Text(why, style = MaterialTheme.typography.bodySmall, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface)
                        }
                    }
                }

                item.marketTransmission?.let {
                    val trans = cleanNewsText(it)
                    if (trans.isNotBlank()) {
                        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text("MARKET TRANSMISSION", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = AccentTeal, fontSize = 10.sp)
                            Text(trans, style = MaterialTheme.typography.bodySmall, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface)
                        }
                    }
                }

                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    item.btcImpact?.let {
                        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text("BTC IMPACT", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = WarningAmber, fontSize = 10.sp)
                            Text(cleanNewsText(it), style = MaterialTheme.typography.bodySmall, fontSize = 10.sp, color = MaterialTheme.colorScheme.onSurface)
                        }
                    }
                    item.goldImpact?.let {
                        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text("GOLD IMPACT", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = WarningAmber, fontSize = 10.sp)
                            Text(cleanNewsText(it), style = MaterialTheme.typography.bodySmall, fontSize = 10.sp, color = MaterialTheme.colorScheme.onSurface)
                        }
                    }
                }

                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    item.bullishCase?.let {
                        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text("BULLISH CASE", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = BullishGreen, fontSize = 10.sp)
                            Text(cleanNewsText(it), style = MaterialTheme.typography.bodySmall, fontSize = 10.sp, color = MaterialTheme.colorScheme.onSurface)
                        }
                    }
                    item.bearishCase?.let {
                        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text("BEARISH CASE", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = BearishRed, fontSize = 10.sp)
                            Text(cleanNewsText(it), style = MaterialTheme.typography.bodySmall, fontSize = 10.sp, color = MaterialTheme.colorScheme.onSurface)
                        }
                    }
                }

                item.currentMarketConfirmation?.let {
                    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text("CURRENT MARKET CONFIRMATION", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = AccentBlue, fontSize = 10.sp)
                        Text(cleanNewsText(it), style = MaterialTheme.typography.bodySmall, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface)
                    }
                }

                (item.tradeRelevance ?: item.relevance)?.let {
                    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text("OPHELIA TRADE RELEVANCE", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = BullishGreen, fontSize = 10.sp)
                        Text(cleanNewsText(it), style = MaterialTheme.typography.bodySmall, fontSize = 11.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
                    }
                }

                item.url?.let { newsUrl ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable {
                                try { uriHandler.openUri(newsUrl) } catch (_: Exception) {}
                            }
                            .padding(vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        Icon(Icons.Filled.Share, contentDescription = "Dispatch Link", tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(14.dp))
                        Text(
                            text = "DISPATCH LINK: ${newsUrl.take(60)}...",
                            style = MaterialTheme.typography.labelSmall,
                            fontSize = 9.sp,
                            color = MaterialTheme.colorScheme.primary,
                            maxLines = 1
                        )
                    }
                }
            }

            // Expand / Collapse Action
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { expanded = !expanded }
                    .padding(vertical = 2.dp),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = if (expanded) "COLLAPSE DOSSIER ▲" else "EXPAND 10-POINT DOSSIER ▼",
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary,
                    fontSize = 10.sp
                )
            }
        }
    }
}

