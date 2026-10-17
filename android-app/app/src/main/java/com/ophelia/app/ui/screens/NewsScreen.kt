package com.ophelia.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.ophelia.app.auth.TokenManager
import com.ophelia.app.models.NewsItem
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.viewmodels.UiState
import com.ophelia.app.ui.theme.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.*

class NewsViewModel(private val tokenManager: TokenManager) : ViewModel() {
    private val _newsState = MutableStateFlow<UiState<List<NewsItem>>>(UiState.Loading)
    val newsState = _newsState.asStateFlow()

    init {
        fetchNews()
    }

    fun fetchNews() {
        viewModelScope.launch {
            _newsState.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val res = api.getNews()
                _newsState.value = UiState.Success(res.news)
            } catch (e: Exception) {
                _newsState.value = UiState.Error(e.message ?: "Failed to load market intelligence")
            }
        }
    }
}

@Composable
fun NewsScreen(
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val tokenManager = remember { TokenManager(context) }

    val viewModel: NewsViewModel = viewModel(
        factory = object : ViewModelProvider.Factory {
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return NewsViewModel(tokenManager) as T
            }
        }
    )

    val newsState by viewModel.newsState.collectAsState()

    Scaffold(
        containerColor = BackgroundCanvas,
        topBar = {
            OpheliaTopBar(
                title = "MARKET INTELLIGENCE",
                subtitle = "Sentiment Analysis & Macro Feeds",
                onBack = onBack,
                onRefresh = { viewModel.fetchNews() }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = OpheliaSpacing.screenHorizontal),
            verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.md)
        ) {
            Spacer(modifier = Modifier.height(OpheliaSpacing.xs))

            when (val state = newsState) {
                is UiState.Loading -> {
                    OpheliaLoadingState(message = "Aggregating market intelligence...")
                }
                is UiState.Error -> {
                    OpheliaErrorState(
                        message = state.message,
                        onRetry = { viewModel.fetchNews() }
                    )
                }
                is UiState.Success -> {
                    val newsList = state.data
                    if (newsList.isEmpty()) {
                        Box(
                            modifier = Modifier
                                .fillMaxSize()
                                .padding(OpheliaSpacing.xxl),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = "No market intelligence updates available.",
                                style = MaterialTheme.typography.bodySmall,
                                color = TextSecondary
                            )
                        }
                    } else {
                        LazyColumn(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)) {
                            items(newsList) { item ->
                                val timeStr = SimpleDateFormat("MMM dd, HH:mm", Locale.getDefault()).format(Date(item.timestampMs))
                                val sentimentColor = when (item.sentiment) {
                                    "BULLISH" -> BullishGreen
                                    "BEARISH" -> BearishRed
                                    else -> TextSecondary
                                }

                                OpheliaGlassCard(
                                    level = GlassLevel.L1,
                                    modifier = Modifier.fillMaxWidth()
                                ) {
                                    Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                                        Row(
                                            modifier = Modifier.fillMaxWidth(),
                                            horizontalArrangement = Arrangement.SpaceBetween,
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            OpheliaStatusBadge(
                                                status = item.sentiment,
                                                color = sentimentColor
                                            )
                                            Text(
                                                text = timeStr,
                                                style = MaterialTheme.typography.labelSmall,
                                                color = TextMuted
                                            )
                                        }

                                        Text(
                                            text = item.headline,
                                            style = MaterialTheme.typography.bodyMedium,
                                            fontWeight = FontWeight.SemiBold,
                                            color = TextPrimary
                                        )

                                        OpheliaDivider()

                                        Row(
                                            modifier = Modifier.fillMaxWidth(),
                                            horizontalArrangement = Arrangement.SpaceBetween
                                        ) {
                                            Text(
                                                text = "Source: ${item.source}",
                                                style = MaterialTheme.typography.labelSmall,
                                                color = TextMuted
                                            )
                                            Text(
                                                text = item.symbols.joinToString(", "),
                                                style = MaterialTheme.typography.labelSmall,
                                                fontWeight = FontWeight.Bold,
                                                color = AccentTeal
                                            )
                                        }
                                    }
                                }
                            }
                            item { Spacer(modifier = Modifier.height(OpheliaSpacing.xxl)) }
                        }
                    }
                }
                else -> {}
            }
        }
    }
}
