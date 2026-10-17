package com.ophelia.app.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.ophelia.app.auth.TokenManager
import com.ophelia.app.models.NotificationItem
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.viewmodels.UiState
import com.ophelia.app.ui.theme.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.*

class ActivityViewModel(private val tokenManager: TokenManager) : ViewModel() {
    private val _notificationsState = MutableStateFlow<UiState<List<NotificationItem>>>(UiState.Loading)
    val notificationsState = _notificationsState.asStateFlow()

    private val _unreadCount = MutableStateFlow(0)
    val unreadCount = _unreadCount.asStateFlow()

    var selectedCategory = MutableStateFlow("ALL")

    init {
        fetchNotifications()
    }

    fun fetchNotifications() {
        viewModelScope.launch {
            _notificationsState.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val res = api.getNotifications(category = selectedCategory.value, limit = 50)
                _notificationsState.value = UiState.Success(res.notifications)
                _unreadCount.value = res.unreadCount
            } catch (e: Exception) {
                _notificationsState.value = UiState.Error(e.message ?: "Failed to load notifications")
            }
        }
    }

    fun setCategory(category: String) {
        selectedCategory.value = category
        fetchNotifications()
    }

    fun markAsRead(item: NotificationItem) {
        if (item.readState == 1) return
        viewModelScope.launch {
            try {
                val api = RetrofitClient.apiService ?: return@launch
                api.markNotificationRead(item.id)
                val current = (_notificationsState.value as? UiState.Success)?.data ?: return@launch
                val updated = current.map { if (it.id == item.id) it.copy(readState = 1) else it }
                _notificationsState.value = UiState.Success(updated)
                _unreadCount.value = maxOf(0, _unreadCount.value - 1)
            } catch (e: Exception) {}
        }
    }

    fun markAllAsRead() {
        viewModelScope.launch {
            try {
                val api = RetrofitClient.apiService ?: return@launch
                api.markAllNotificationsRead()
                val current = (_notificationsState.value as? UiState.Success)?.data ?: return@launch
                val updated = current.map { it.copy(readState = 1) }
                _notificationsState.value = UiState.Success(updated)
                _unreadCount.value = 0
            } catch (e: Exception) {}
        }
    }

    fun clearAll(onDone: () -> Unit = {}) {
        viewModelScope.launch {
            try {
                val api = RetrofitClient.apiService ?: return@launch
                api.clearAllNotifications()
                _notificationsState.value = UiState.Success(emptyList())
                _unreadCount.value = 0
                onDone()
            } catch (e: Exception) {}
        }
    }
}

@Composable
fun ActivityScreen(
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val tokenManager = remember { TokenManager(context) }

    val viewModel: ActivityViewModel = viewModel(
        factory = object : ViewModelProvider.Factory {
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return ActivityViewModel(tokenManager) as T
            }
        }
    )

    val notificationsState by viewModel.notificationsState.collectAsState()
    val unreadCount by viewModel.unreadCount.collectAsState()
    val selectedCategory by viewModel.selectedCategory.collectAsState()

    val categories = listOf("ALL", "TRADES", "AUTOMATIONS", "RISK", "SYSTEM", "ACCOUNT")

    var showClearConfirmDialog by remember { mutableStateOf(false) }

    if (showClearConfirmDialog) {
        OpheliaDialog(
            onDismissRequest = { showClearConfirmDialog = false },
            title = "CLEAR ALL ALERTS?",
            subtitle = "This will remove all notification dispatches. Permanent audit logs remain preserved.",
            badgeText = "CONFIRMATION",
            badgeColor = WarningAmber,
            confirmButton = {
                OpheliaDangerButton(
                    text = "CLEAR ALL",
                    onClick = {
                        viewModel.clearAll {
                            showClearConfirmDialog = false
                        }
                    }
                )
            },
            dismissButton = {
                OpheliaOutlinedButton(
                    text = "CANCEL",
                    onClick = { showClearConfirmDialog = false }
                )
            }
        ) {
            Text(
                text = "Are you sure you want to dismiss all alert notifications? This action only clears user notification history; engine health telemetry and operational audit logs remain permanently intact.",
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary
            )
        }
    }

    Scaffold(
        containerColor = BackgroundCanvas,
        topBar = {
            OpheliaTopBar(
                title = "NOTIFICATION CENTER",
                subtitle = if (unreadCount > 0) "$unreadCount UNREAD ALERTS" else "SYSTEM LOG & DISPATCHES",
                onBack = onBack,
                onRefresh = { viewModel.fetchNotifications() }
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

            // Category filter chips and Action Buttons
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                LazyRow(
                    horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs),
                    modifier = Modifier.weight(1f)
                ) {
                    items(categories) { cat ->
                        OpheliaChip(
                            text = cat,
                            isSelected = selectedCategory == cat,
                            onClick = { viewModel.setCategory(cat) }
                        )
                    }
                }

                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    if (unreadCount > 0) {
                        TextButton(
                            onClick = { viewModel.markAllAsRead() },
                            contentPadding = PaddingValues(horizontal = 6.dp, vertical = 4.dp)
                        ) {
                            Text("READ ALL", style = MaterialTheme.typography.labelSmall, color = AccentBlue)
                        }
                    }
                    TextButton(
                        onClick = { showClearConfirmDialog = true },
                        contentPadding = PaddingValues(horizontal = 6.dp, vertical = 4.dp)
                    ) {
                        Text("CLEAR ALL", style = MaterialTheme.typography.labelSmall, color = BearishRed)
                    }
                }
            }

            when (val state = notificationsState) {
                is UiState.Loading -> {
                    OpheliaLoadingState(message = "Fetching notification history...")
                }
                is UiState.Error -> {
                    OpheliaErrorState(
                        message = state.message,
                        onRetry = { viewModel.fetchNotifications() }
                    )
                }
                is UiState.Success -> {
                    val notifs = state.data
                    if (notifs.isEmpty()) {
                        Box(
                            modifier = Modifier
                                .fillMaxSize()
                                .padding(OpheliaSpacing.xxl),
                            contentAlignment = Alignment.Center
                        ) {
                            Column(
                                horizontalAlignment = Alignment.CenterHorizontally,
                                verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
                            ) {
                                Icon(
                                    Icons.Filled.Notifications,
                                    contentDescription = "No notifications",
                                    tint = TextMuted,
                                    modifier = Modifier.size(48.dp)
                                )
                                Text(
                                    text = "NO RECENT ALERTS",
                                    style = MaterialTheme.typography.bodyMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = TextSecondary
                                )
                            }
                        }
                    } else {
                        LazyColumn(
                            verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm),
                            contentPadding = PaddingValues(bottom = OpheliaSpacing.xl)
                        ) {
                            items(notifs, key = { it.id }) { item ->
                                val timeStr = SimpleDateFormat("MMM dd, HH:mm:ss", Locale.getDefault()).format(Date(item.createdMs))
                                val isUnread = item.readState == 0

                                val badgeColor = when (item.severity) {
                                    "CRITICAL" -> BearishRed
                                    "WARNING" -> WarningAmber
                                    "SUCCESS" -> BullishGreen
                                    else -> AccentBlue
                                }

                                OpheliaGlassCard(
                                    level = if (isUnread) GlassLevel.L2 else GlassLevel.L1,
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clickable { viewModel.markAsRead(item) },
                                    borderColor = if (isUnread) badgeColor.copy(alpha = 0.5f) else GlassBorderSubtle
                                ) {
                                    Column(
                                        modifier = Modifier.padding(OpheliaSpacing.sm),
                                        verticalArrangement = Arrangement.spacedBy(4.dp)
                                    ) {
                                        Row(
                                            modifier = Modifier.fillMaxWidth(),
                                            horizontalArrangement = Arrangement.SpaceBetween,
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            Row(
                                                verticalAlignment = Alignment.CenterVertically,
                                                horizontalArrangement = Arrangement.spacedBy(6.dp)
                                            ) {
                                                if (isUnread) {
                                                    Surface(
                                                        modifier = Modifier.size(8.dp),
                                                        shape = MaterialTheme.shapes.extraSmall,
                                                        color = badgeColor
                                                    ) {}
                                                }
                                                OpheliaStatusBadge(
                                                    status = item.category,
                                                    color = badgeColor,
                                                    showDot = false
                                                )
                                                Text(
                                                    text = item.title,
                                                    style = MaterialTheme.typography.titleSmall,
                                                    fontWeight = if (isUnread) FontWeight.Bold else FontWeight.Medium,
                                                    color = TextPrimary
                                                )
                                            }
                                            Text(
                                                text = timeStr,
                                                style = MaterialTheme.typography.labelSmall,
                                                color = TextMuted
                                            )
                                        }

                                        Text(
                                            text = item.message,
                                            style = MaterialTheme.typography.bodySmall,
                                            color = if (isUnread) TextPrimary else TextSecondary,
                                            lineHeight = 18.sp
                                        )
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
}

@Composable
fun NotificationCentreScreen(onBack: () -> Unit) {
    ActivityScreen(onBack = onBack)
}
