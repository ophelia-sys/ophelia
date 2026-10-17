package com.ophelia.app.ui.screens

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ophelia.app.models.BingxConnectionStatusResponse
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AccountApiKeysScreen(
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val uriHandler = LocalUriHandler.current
    val scope = rememberCoroutineScope()

    var bingxConnection by remember { mutableStateOf<BingxConnectionStatusResponse?>(null) }
    var credentialSource by remember { mutableStateOf("APP") }
    var appApiKeyInput by remember { mutableStateOf("") }
    var appApiSecretInput by remember { mutableStateOf("") }
    var showSecret by remember { mutableStateOf(false) }
    var isSavingCredentials by remember { mutableStateOf(false) }
    var isConnLoading by remember { mutableStateOf(false) }
    var isLoading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }

    fun refreshConnectionStatus() {
        scope.launch {
            isLoading = true
            errorMessage = null
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                val connStatus = api.getBingxConnectionStatus()
                bingxConnection = connStatus
                credentialSource = connStatus.source
            } catch (e: Exception) {
                errorMessage = e.message ?: "Failed to fetch BingX connection status"
            } finally {
                isLoading = false
            }
        }
    }

    fun doConnectBingx() {
        scope.launch {
            isConnLoading = true
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                val res = api.connectBingx()
                Toast.makeText(context, "BingX Connection: ${res["status"] ?: "CONNECTED"}", Toast.LENGTH_SHORT).show()
                refreshConnectionStatus()
            } catch (e: Exception) {
                Toast.makeText(context, "Connect failed: ${e.message}", Toast.LENGTH_LONG).show()
            } finally {
                isConnLoading = false
            }
        }
    }

    fun doDisconnectBingx() {
        scope.launch {
            isConnLoading = true
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                api.disconnectBingx()
                Toast.makeText(context, "BingX Disconnected", Toast.LENGTH_SHORT).show()
                refreshConnectionStatus()
            } catch (e: Exception) {
                Toast.makeText(context, "Disconnect failed: ${e.message}", Toast.LENGTH_LONG).show()
            } finally {
                isConnLoading = false
            }
        }
    }

    fun doRefreshBingx() {
        scope.launch {
            isConnLoading = true
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                val res = api.refreshBingxConnection()
                bingxConnection = res
                credentialSource = res.source
                Toast.makeText(context, "Status: ${res.status} (${res.latencyMs}ms)", Toast.LENGTH_SHORT).show()
            } catch (e: Exception) {
                Toast.makeText(context, "Refresh failed: ${e.message}", Toast.LENGTH_LONG).show()
            } finally {
                isConnLoading = false
            }
        }
    }

    fun switchCredentialSource(newSrc: String) {
        scope.launch {
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                api.setCredentialSource(mapOf("source" to newSrc))
                credentialSource = newSrc
                Toast.makeText(context, "Credential source switched to $newSrc", Toast.LENGTH_SHORT).show()
                refreshConnectionStatus()
            } catch (e: Exception) {
                Toast.makeText(context, "Failed switching source: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    fun saveAppCredentials() {
        if (appApiKeyInput.isBlank() || appApiSecretInput.isBlank()) {
            Toast.makeText(context, "API Key and API Secret are required", Toast.LENGTH_SHORT).show()
            return
        }
        scope.launch {
            isSavingCredentials = true
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                api.saveUserBingxCredentials(mapOf("api_key" to appApiKeyInput.trim(), "api_secret" to appApiSecretInput.trim()))
                appApiSecretInput = ""
                Toast.makeText(context, "App API credentials saved successfully", Toast.LENGTH_SHORT).show()
                refreshConnectionStatus()
            } catch (e: Exception) {
                Toast.makeText(context, "Failed saving credentials: ${e.message}", Toast.LENGTH_LONG).show()
            } finally {
                isSavingCredentials = false
            }
        }
    }

    LaunchedEffect(Unit) {
        refreshConnectionStatus()
    }

    Scaffold(
        containerColor = BackgroundCanvas,
        topBar = {
            OpheliaTopBar(
                title = "ACCOUNT & API KEYS",
                subtitle = "BingX Exchange Connection & Credential Provisioning",
                onBack = onBack,
                onRefresh = { refreshConnectionStatus() }
            )
        }
    ) { padding ->
        if (isLoading) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(color = AccentBlue)
            }
        } else if (errorMessage != null) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(16.dp),
                contentAlignment = Alignment.Center
            ) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Text("Error: $errorMessage", color = BearishRed, fontWeight = FontWeight.Bold)
                    OpheliaButton(text = "RETRY", onClick = { refreshConnectionStatus() })
                }
            }
        } else {
            val conn = bingxConnection
            val connStatus = conn?.status ?: "CONNECTED"
            val isConnected = connStatus == "CONNECTED"
            val isVps = credentialSource == "VPS" || credentialSource == "ADMIN"
            val lastCheckTime = if (conn != null && conn.lastCheckMs > 0) {
                val dt = java.util.Date(conn.lastCheckMs)
                java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.US).format(dt)
            } else "Just now"

            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 14.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                // 1. PRIMARY BINGX ACCOUNT CONNECTION CARD (Exact replica of referenced card)
                item {
                    OpheliaGlassCard(
                        borderColor = if (isConnected) BullishGreen.copy(alpha = 0.5f) else WarningAmber.copy(alpha = 0.5f)
                    ) {
                        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            // Header
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text(
                                        text = "BINGX ACCOUNT CONNECTION",
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.Bold,
                                        color = TextPrimary
                                    )
                                    Text(
                                        text = "Exchange link status & credential provisioning (SHADOW compliant)",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = TextMuted,
                                        fontSize = 11.sp
                                    )
                                }
                                OpheliaStatusBadge(
                                    status = connStatus,
                                    color = if (isConnected) BullishGreen else WarningAmber,
                                    showDot = isConnected
                                )
                            }

                            OpheliaDivider()

                            // Key Metrics Grid
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                OpheliaMetric(
                                    label = "Connection Status",
                                    value = connStatus,
                                    valueColor = if (isConnected) BullishGreen else WarningAmber,
                                    subValue = if (conn?.latencyMs != null && conn.latencyMs > 0) "${conn.latencyMs} ms" else "Active"
                                )
                                OpheliaMetric(
                                    label = "Credential Source",
                                    value = conn?.source ?: credentialSource,
                                    valueColor = AccentBlue,
                                    subValue = if ((conn?.source ?: credentialSource) == "APP") "User App Key" else "VPS Host Key"
                                )
                                OpheliaMetric(
                                    label = "Last Checked",
                                    value = lastCheckTime,
                                    valueColor = TextPrimary,
                                    subValue = "Verified ping"
                                )
                                OpheliaMetric(
                                    label = "Withdrawal Perm",
                                    value = "BLOCKED",
                                    valueColor = BearishRed,
                                    subValue = "Safety enforced"
                                )
                            }

                            // Connection Action Buttons
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(10.dp)
                            ) {
                                OpheliaOutlinedButton(
                                    text = if (isConnLoading) "PINGING..." else "REFRESH PING",
                                    onClick = { doRefreshBingx() },
                                    modifier = Modifier.weight(1f)
                                )
                                if (isConnected) {
                                    OpheliaDangerButton(
                                        text = "DISCONNECT",
                                        onClick = { doDisconnectBingx() },
                                        modifier = Modifier.weight(1f)
                                    )
                                } else {
                                    OpheliaButton(
                                        text = "CONNECT",
                                        onClick = { doConnectBingx() },
                                        modifier = Modifier.weight(1f)
                                    )
                                }
                            }

                            OpheliaDivider()

                            // API Credential Source Selector (Admin Only)
                            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                Text(
                                    text = "API CREDENTIAL SOURCE (ADMIN ONLY)",
                                    style = MaterialTheme.typography.labelMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = TextPrimary
                                )
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    Box(
                                        modifier = Modifier
                                            .weight(1f)
                                            .clip(RoundedCornerShape(8.dp))
                                            .background(if (isVps) AccentBlue.copy(alpha = 0.25f) else GlassSurfaceL1)
                                            .border(
                                                1.dp,
                                                if (isVps) AccentBlue else GlassBorder,
                                                RoundedCornerShape(8.dp)
                                            )
                                            .clickable { switchCredentialSource("VPS") }
                                            .padding(vertical = 10.dp),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Text(
                                            text = "VPS HOST SOURCE",
                                            style = MaterialTheme.typography.labelSmall,
                                            fontWeight = if (isVps) FontWeight.Bold else FontWeight.Normal,
                                            color = if (isVps) AccentBlue else TextSecondary
                                        )
                                    }

                                    val isApp = credentialSource == "APP"
                                    Box(
                                        modifier = Modifier
                                            .weight(1f)
                                            .clip(RoundedCornerShape(8.dp))
                                            .background(if (isApp) AccentBlue.copy(alpha = 0.25f) else GlassSurfaceL1)
                                            .border(
                                                1.dp,
                                                if (isApp) AccentBlue else GlassBorder,
                                                RoundedCornerShape(8.dp)
                                            )
                                            .clickable { switchCredentialSource("APP") }
                                            .padding(vertical = 10.dp),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Text(
                                            text = "APP USER SOURCE",
                                            style = MaterialTheme.typography.labelSmall,
                                            fontWeight = if (isApp) FontWeight.Bold else FontWeight.Normal,
                                            color = if (isApp) AccentBlue else TextSecondary
                                        )
                                    }
                                }

                                Text(
                                    text = if (isVps) "Operational BingX credentials loaded from VPS environment (.env). No manual input needed." else "Enter custom API credentials to override server defaults.",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = TextMuted,
                                    fontSize = 11.sp
                                )
                            }

                            if (isVps) {
                                OpheliaGlassCard(
                                    level = GlassLevel.L3,
                                    borderColor = BullishGreen.copy(alpha = 0.5f)
                                ) {
                                    Column(
                                        modifier = Modifier.padding(12.dp),
                                        verticalArrangement = Arrangement.spacedBy(6.dp)
                                    ) {
                                        Row(
                                            verticalAlignment = Alignment.CenterVertically,
                                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                                        ) {
                                            Icon(
                                                Icons.Filled.CheckCircle,
                                                contentDescription = null,
                                                tint = BullishGreen,
                                                modifier = Modifier.size(18.dp)
                                            )
                                            Text(
                                                text = "VPS HOST CREDENTIALS ACTIVE",
                                                style = MaterialTheme.typography.titleSmall,
                                                fontWeight = FontWeight.Bold,
                                                color = BullishGreen
                                            )
                                        }
                                        Text(
                                            text = "Operational BingX API Key & Secret are grabbed directly from the VPS server host environment. Admin does not need to enter credentials manually.",
                                            style = MaterialTheme.typography.bodySmall,
                                            color = TextSecondary,
                                            fontSize = 12.sp
                                        )
                                    }
                                }
                            } else {
                                // App User Credentials Inputs
                                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                                    OutlinedTextField(
                                        value = appApiKeyInput,
                                        onValueChange = { appApiKeyInput = it },
                                        label = { Text("BingX API Key", style = MaterialTheme.typography.labelSmall) },
                                        placeholder = { Text("Enter API Key (e.g. bg_...)") },
                                        modifier = Modifier.fillMaxWidth(),
                                        singleLine = true,
                                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Ascii),
                                        colors = OutlinedTextFieldDefaults.colors(
                                            focusedBorderColor = AccentBlue,
                                            unfocusedBorderColor = GlassBorder,
                                            focusedTextColor = TextPrimary,
                                            unfocusedTextColor = TextPrimary
                                        ),
                                        shape = ShapeMedium
                                    )

                                    OutlinedTextField(
                                        value = appApiSecretInput,
                                        onValueChange = { appApiSecretInput = it },
                                        label = { Text("BingX API Secret", style = MaterialTheme.typography.labelSmall) },
                                        placeholder = { Text("Enter API Secret") },
                                        modifier = Modifier.fillMaxWidth(),
                                        singleLine = true,
                                        visualTransformation = if (showSecret) VisualTransformation.None else PasswordVisualTransformation(),
                                        trailingIcon = {
                                            IconButton(onClick = { showSecret = !showSecret }) {
                                                Icon(
                                                    imageVector = if (showSecret) Icons.Filled.Star else Icons.Filled.Lock,
                                                    contentDescription = "Toggle visibility",
                                                    tint = TextMuted
                                                )
                                            }
                                        },
                                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                                        colors = OutlinedTextFieldDefaults.colors(
                                            focusedBorderColor = AccentBlue,
                                            unfocusedBorderColor = GlassBorder,
                                            focusedTextColor = TextPrimary,
                                            unfocusedTextColor = TextPrimary
                                        ),
                                        shape = ShapeMedium
                                    )

                                    OpheliaButton(
                                        text = if (isSavingCredentials) "SAVING ENCRYPTED KEYS..." else "SAVE APP CREDENTIALS",
                                        onClick = { saveAppCredentials() },
                                        modifier = Modifier.fillMaxWidth()
                                    )
                                }
                            }
                        }
                    }
                }

                // 2. OFFICIAL BINGX SETUP & SECURITY CHECKLIST
                item {
                    OpheliaGlassCard(
                        level = GlassLevel.L2,
                        borderColor = AccentTeal.copy(alpha = 0.4f)
                    ) {
                        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Icon(Icons.Filled.Info, contentDescription = null, tint = AccentTeal, modifier = Modifier.size(18.dp))
                                    Text(
                                        text = "BINGX API PROVISIONING GUIDE",
                                        style = MaterialTheme.typography.titleSmall,
                                        fontWeight = FontWeight.Bold,
                                        color = TextPrimary
                                    )
                                }
                                OpheliaStatusBadge(status = "SECURITY RULES", color = AccentTeal)
                            }

                            OpheliaDivider()

                            val guideSteps = listOf(
                                "1. Log into BingX and navigate to Account -> API Management.",
                                "2. Click 'Create API' and select Perpetual Swap Futures contract permissions.",
                                "3. REQUIRED: Enable 'Read' and 'Futures Trading' permissions.",
                                "4. MANDATORY SAFETY: Keep 'Withdrawal' STRICTLY UNCHECKED. Ophelia permanently rejects any API key with withdrawal privileges enabled.",
                                "5. (Optional) Whitelist VPS IP address for enhanced security.",
                                "6. Paste the generated Key and Secret into the form above and tap 'SAVE APP CREDENTIALS'."
                            )

                            guideSteps.forEach { step ->
                                Text(
                                    text = step,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = TextSecondary,
                                    fontSize = 12.sp
                                )
                            }

                            Spacer(modifier = Modifier.height(4.dp))

                            OpheliaOutlinedButton(
                                text = "OPEN BINGX API MANAGEMENT",
                                onClick = {
                                    try {
                                        uriHandler.openUri("https://bingx.com/en/account/api/")
                                    } catch (e: Exception) {
                                        Toast.makeText(context, "Could not open browser", Toast.LENGTH_SHORT).show()
                                    }
                                },
                                modifier = Modifier.fillMaxWidth()
                            )
                        }
                    }
                }
            }
        }
    }
}
