package com.ophelia.app.ui.screens

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.ophelia.app.auth.TokenManager
import com.ophelia.app.models.AnalyticsResponse
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.viewmodels.UiState
import com.ophelia.app.ui.theme.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlin.math.max

class AnalyticsViewModel(private val tokenManager: TokenManager) : ViewModel() {
    private val _analyticsState = MutableStateFlow<UiState<AnalyticsResponse>>(UiState.Loading)
    val analyticsState = _analyticsState.asStateFlow()

    private val _selectedDays = MutableStateFlow(30)
    val selectedDays = _selectedDays.asStateFlow()

    init {
        fetchAnalytics()
    }

    fun setSelectedDays(days: Int) {
        _selectedDays.value = days
        fetchAnalytics()
    }

    fun fetchAnalytics() {
        viewModelScope.launch {
            _analyticsState.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val res = api.getAnalytics(days = _selectedDays.value)
                _analyticsState.value = UiState.Success(res)
            } catch (e: Exception) {
                _analyticsState.value = UiState.Error(e.message ?: "Failed to load analytics")
            }
        }
    }
}

@Composable
fun AnalyticsScreen(
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val tokenManager = remember { TokenManager(context) }
    
    val viewModel: AnalyticsViewModel = viewModel(
        factory = object : ViewModelProvider.Factory {
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return AnalyticsViewModel(tokenManager) as T
            }
        }
    )

    val analyticsState by viewModel.analyticsState.collectAsState()
    val selectedDays by viewModel.selectedDays.collectAsState()

    Scaffold(
        containerColor = BackgroundCanvas,
        topBar = {
            OpheliaTopBar(
                title = "PERFORMANCE ANALYTICS",
                subtitle = "Statistical Trade Journal Metrics",
                onBack = onBack,
                onRefresh = { viewModel.fetchAnalytics() }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = OpheliaSpacing.screenHorizontal),
            verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.md)
        ) {
            Spacer(modifier = Modifier.height(OpheliaSpacing.xs))

            // 1. Range Selection Chips
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
            ) {
                listOf(7, 30, 90).forEach { days ->
                    OpheliaChip(
                        text = "${days}D LOOKBACK",
                        isSelected = selectedDays == days,
                        onClick = { viewModel.setSelectedDays(days) },
                        modifier = Modifier.weight(1f)
                    )
                }
            }

            when (val state = analyticsState) {
                is UiState.Loading -> {
                    OpheliaLoadingState(message = "Aggregating performance analytics...")
                }
                is UiState.Error -> {
                    OpheliaErrorState(
                        message = state.message,
                        onRetry = { viewModel.fetchAnalytics() }
                    )
                }
                is UiState.Success -> {
                    val data = state.data

                    // 2. Primary KPI 2x2 Grid
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
                    ) {
                        OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.weight(1f)) {
                            OpheliaMetric(
                                label = "Win Rate",
                                value = "${data.winRate}%",
                                valueColor = if (data.winRate >= 50) BullishGreen else BearishRed,
                                subValue = "${data.wins}W / ${data.losses}L (${data.totalTrades} total)",
                                isLarge = true
                            )
                        }
                        OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.weight(1f)) {
                            OpheliaMetric(
                                label = "Profit Factor",
                                value = "${data.profitFactor}",
                                valueColor = if (data.profitFactor >= 1.5) BullishGreen else TextPrimary,
                                subValue = "Expectancy Multiplier",
                                isLarge = true
                            )
                        }
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
                    ) {
                        val netProfit = data.netPnl >= 0
                        OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.weight(1f)) {
                            OpheliaMetric(
                                label = "Net Realized PnL",
                                value = "${if (netProfit) "+" else ""}$${data.netPnl}",
                                valueColor = if (netProfit) BullishGreen else BearishRed,
                                isLarge = true
                            )
                        }
                        OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.weight(1f)) {
                            OpheliaMetric(
                                label = "Avg Win / Loss",
                                value = "+$${data.avgWin} / -$${data.avgLoss}",
                                valueColor = TextPrimary,
                                subValue = "Risk / Reward Profile",
                                isLarge = true
                            )
                        }
                    }

                    // 3. Equity Curve Trajectory Card
                    OpheliaGlassCard(level = GlassLevel.L1, modifier = Modifier.fillMaxWidth()) {
                        Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "EQUITY TRAJECTORY (USDT)",
                                    style = MaterialTheme.typography.labelSmall,
                                    fontWeight = FontWeight.Bold,
                                    color = TextSecondary
                                )
                                OpheliaStatusBadge(status = "CUMULATIVE", color = AccentBlue, showDot = false)
                            }

                            OpheliaDivider()

                            val points = data.equityCurve
                            if (points.isEmpty()) {
                                Box(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .height(160.dp),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text(
                                        text = "Accumulating balance snapshot data...",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = TextSecondary
                                    )
                                }
                            } else {
                                val minEq = points.minOf { it.equity }
                                val maxEq = points.maxOf { it.equity }
                                val range = max(maxEq - minEq, 0.01)

                                Canvas(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .height(160.dp)
                                ) {
                                    val w = size.width
                                    val h = size.height
                                    val step = if (points.size > 1) w / (points.size - 1) else w

                                    val linePath = Path()
                                    val fillPath = Path()

                                    points.forEachIndexed { i, pt ->
                                        val x = i * step
                                        val y = h * (1f - ((pt.equity - minEq) / range).toFloat())
                                        if (i == 0) {
                                            linePath.moveTo(x, y)
                                            fillPath.moveTo(x, h)
                                            fillPath.lineTo(x, y)
                                        } else {
                                            linePath.lineTo(x, y)
                                            fillPath.lineTo(x, y)
                                        }
                                        if (i == points.size - 1) {
                                            fillPath.lineTo(x, h)
                                            fillPath.close()
                                        }
                                    }

                                    // Draw background gradient fill
                                    drawPath(
                                        path = fillPath,
                                        brush = Brush.verticalGradient(
                                            listOf(BullishGreen.copy(alpha = 0.25f), Color.Transparent)
                                        )
                                    )

                                    // Draw stroke line
                                    drawPath(
                                        path = linePath,
                                        color = BullishGreen,
                                        style = Stroke(width = 2.5f)
                                    )
                                }

                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Text("Min: $$minEq", style = MaterialTheme.typography.labelSmall, color = TextMuted)
                                    Text("Max: $$maxEq", style = MaterialTheme.typography.labelSmall, color = TextMuted)
                                }
                            }
                        }
                    }
                }
                else -> {}
            }

            Spacer(modifier = Modifier.height(OpheliaSpacing.xxl))
        }
    }
}
