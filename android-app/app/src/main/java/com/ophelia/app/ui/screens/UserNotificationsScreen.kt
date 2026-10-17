package com.ophelia.app.ui.screens

import android.widget.Toast
import androidx.compose.foundation.background
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
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.theme.*
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.*

data class UserNotificationItem(
    val id: Int,
    val title: String,
    val message: String,
    val severity: String,
    val category: String,
    val mode: String,
    val read: Boolean,
    val createdMs: Long
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun UserNotificationsScreen(
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val tokens = OpheliaThemeTokens.colors

    var isLoading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    val notifications = remember { mutableStateListOf<UserNotificationItem>() }
    var selectedCategory by remember { mutableStateOf("ALL") }

    fun loadNotifications() {
        scope.launch {
            isLoading = true
            errorMessage = null
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                val res = api.getUserNotifications(category = selectedCategory)
                notifications.clear()
                for (item in res) {
                    notifications.add(
                        UserNotificationItem(
                            id = (item["id"] as? Number)?.toInt() ?: 0,
                            title = item["title"] as? String ?: "Notification",
                            message = item["message"] as? String ?: "",
                            severity = item["severity"] as? String ?: "INFO",
                            category = item["category"] as? String ?: "SYSTEM",
                            mode = item["mode"] as? String ?: "SHADOW",
                            read = item["read"] as? Boolean ?: false,
                            createdMs = (item["created_ms"] as? Number)?.toLong() ?: System.currentTimeMillis()
                        )
                    )
                }
            } catch (e: Exception) {
                errorMessage = e.message ?: "Failed to load notifications"
            } finally {
                isLoading = false
            }
        }
    }

    fun clearAll() {
        scope.launch {
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                api.clearUserNotifications()
                Toast.makeText(context, "Notifications cleared", Toast.LENGTH_SHORT).show()
                loadNotifications()
            } catch (e: Exception) {
                Toast.makeText(context, "Failed to clear: ${e.message}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    fun markRead(id: Int) {
        scope.launch {
            try {
                val api = RetrofitClient.apiService ?: return@launch
                api.markUserNotificationRead(id)
                loadNotifications()
            } catch (_: Exception) {}
        }
    }

    LaunchedEffect(selectedCategory) {
        loadNotifications()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = "NOTIFICATIONS",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = tokens.primaryText
                        )
                        Text(
                            text = "ACCOUNT & FLEET REPLICATION ALERTS",
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
                    if (notifications.isNotEmpty()) {
                        IconButton(onClick = { clearAll() }) {
                            Icon(Icons.Default.Delete, contentDescription = "Clear All", tint = tokens.secondaryText)
                        }
                    }
                    IconButton(onClick = { loadNotifications() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = AccentBlue)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background)
            )
        },
        containerColor = tokens.surface
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            // Category Filter Chips
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                listOf("ALL", "TRADES", "RISK", "SYSTEM").forEach { cat ->
                    FilterChip(
                        selected = selectedCategory == cat,
                        onClick = { selectedCategory = cat },
                        label = { Text(cat, fontSize = 11.sp) }
                    )
                }
            }

            if (isLoading) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = AccentBlue)
                }
            } else if (errorMessage != null) {
                OpheliaGlassCard(modifier = Modifier.fillMaxWidth(), borderColor = BearishRed) {
                    Row(modifier = Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Icon(Icons.Default.Warning, contentDescription = null, tint = BearishRed)
                        Text(errorMessage ?: "", color = BearishRed, style = MaterialTheme.typography.bodySmall)
                    }
                }
            } else if (notifications.isEmpty()) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Icon(Icons.Default.Notifications, contentDescription = null, tint = tokens.secondaryText, modifier = Modifier.size(40.dp))
                        Text("No notifications in this category.", color = tokens.secondaryText, style = MaterialTheme.typography.bodyMedium)
                    }
                }
            } else {
                val dateFmt = SimpleDateFormat("HH:mm:ss • MMM dd", Locale.US)
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    items(notifications) { notif ->
                        val sevColor = when (notif.severity) {
                            "CRITICAL" -> BearishRed
                            "WARNING" -> AccentYellow
                            "SUCCESS" -> BullishGreen
                            else -> AccentBlue
                        }

                        OpheliaGlassCard(
                            modifier = Modifier.fillMaxWidth(),
                            borderColor = if (!notif.read) sevColor.copy(alpha = 0.5f) else tokens.border.copy(alpha = 0.2f)
                        ) {
                            Column(
                                modifier = Modifier.padding(14.dp),
                                verticalArrangement = Arrangement.spacedBy(6.dp)
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
                                        Box(
                                            modifier = Modifier
                                                .size(8.dp)
                                                .clip(RoundedCornerShape(4.dp))
                                                .background(sevColor)
                                        )
                                        Text(
                                            text = notif.title,
                                            style = MaterialTheme.typography.titleSmall,
                                            fontWeight = FontWeight.Bold,
                                            color = tokens.primaryText
                                        )
                                    }
                                    Text(
                                        text = dateFmt.format(Date(notif.createdMs)),
                                        style = MaterialTheme.typography.labelSmall,
                                        color = tokens.secondaryText,
                                        fontFamily = FontFamily.Monospace,
                                        fontSize = 10.sp
                                    )
                                }

                                Text(
                                    text = notif.message,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = tokens.primaryText,
                                    fontSize = 12.sp
                                )

                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(
                                        text = "${notif.category} • ${notif.mode}",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = tokens.secondaryText,
                                        fontSize = 10.sp
                                    )
                                    if (!notif.read) {
                                        TextButton(onClick = { markRead(notif.id) }, contentPadding = PaddingValues(0.dp)) {
                                            Text("Mark Read", fontSize = 11.sp, color = AccentBlue)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
