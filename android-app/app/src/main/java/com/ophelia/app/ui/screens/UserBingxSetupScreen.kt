package com.ophelia.app.ui.screens

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.theme.*
import kotlinx.coroutines.launch
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun UserBingxSetupScreen(
    onSetupComplete: () -> Unit,
    onBack: (() -> Unit)? = null
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val tokens = OpheliaThemeTokens.colors

    var apiKey by remember { mutableStateOf("") }
    var apiSecret by remember { mutableStateOf("") }
    var showSecret by remember { mutableStateOf(false) }

    var isSaving by remember { mutableStateOf(false) }
    var isCheckingStatus by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var bingxStatus by remember { mutableStateOf<Map<String, Any>?>(null) }

    fun refreshStatus() {
        scope.launch {
            isCheckingStatus = true
            errorMessage = null
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                val status = api.getUserBingxStatus()
                bingxStatus = status
            } catch (e: Exception) {
                errorMessage = e.message ?: "Failed to check BingX connection"
            } finally {
                isCheckingStatus = false
            }
        }
    }

    fun saveAndConnect() {
        if (apiKey.trim().isEmpty() || apiSecret.trim().isEmpty()) {
            errorMessage = "API Key and API Secret are required"
            return
        }
        scope.launch {
            isSaving = true
            errorMessage = null
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                val res = api.saveUserBingxCredentialsDirect(
                    mapOf(
                        "api_key" to apiKey.trim(),
                        "api_secret" to apiSecret.trim()
                    )
                )
                val status = res["status"] as? String ?: "CONNECTED"
                Toast.makeText(context, "BingX Account Connected: $status", Toast.LENGTH_SHORT).show()
                apiKey = ""
                apiSecret = ""
                refreshStatus()
            } catch (e: Exception) {
                errorMessage = e.message ?: "Failed to save BingX credentials"
            } finally {
                isSaving = false
            }
        }
    }

    var isDisconnecting by remember { mutableStateOf(false) }

    fun doDisconnect() {
        scope.launch {
            isDisconnecting = true
            errorMessage = null
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                api.disconnectUserBingx()
                Toast.makeText(context, "BingX Account Disconnected", Toast.LENGTH_SHORT).show()
                refreshStatus()
            } catch (e: Exception) {
                errorMessage = e.message ?: "Failed to disconnect account"
            } finally {
                isDisconnecting = false
            }
        }
    }

    LaunchedEffect(Unit) {
        refreshStatus()
    }

    val isConnected = bingxStatus?.get("connected") == true || bingxStatus?.get("status") == "CONNECTED"

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = "BINGX ACCOUNT & API",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = tokens.primaryText
                        )
                        Text(
                            text = "PERPETUAL FUTURES CREDENTIALS",
                            style = MaterialTheme.typography.labelSmall,
                            color = tokens.secondaryText
                        )
                    }
                },
                navigationIcon = {
                    if (onBack != null) {
                        IconButton(onClick = onBack) {
                            Icon(Icons.Default.ArrowBack, contentDescription = "Back", tint = tokens.primaryText)
                        }
                    }
                },
                actions = {
                    IconButton(onClick = { refreshStatus() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = AccentBlue)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background
                )
            )
        },
        containerColor = tokens.surface
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Spacer(modifier = Modifier.height(4.dp))

            // Safety & Permissions Instructions
            OpheliaGlassCard(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Icon(Icons.Default.Lock, contentDescription = null, tint = BullishGreen)
                        Text(
                            text = "SECURITY & PERMISSIONS MANDATE",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold,
                            color = tokens.primaryText,
                            fontFamily = FontFamily.Monospace
                        )
                    }

                    Text(
                        text = "• Required Permissions: Read/Account & Perpetual Futures Trading.\n• Withdrawal Permission: FORBIDDEN. Must NOT be enabled.\n• Credentials are encrypted on VPS using AES-256-GCM. Raw secrets are never stored, logged, or returned to clients.",
                        style = MaterialTheme.typography.bodySmall,
                        color = tokens.secondaryText,
                        fontSize = 11.sp,
                        lineHeight = 16.sp
                    )
                }
            }

            // Current Connection Status Card
            bingxStatus?.let { status ->
                OpheliaGlassCard(
                    modifier = Modifier.fillMaxWidth(),
                    borderColor = if (isConnected) BullishGreen.copy(alpha = 0.5f) else null
                ) {
                    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "BINGX CONNECTION",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.Bold,
                                color = tokens.primaryText,
                                fontFamily = FontFamily.Monospace
                            )
                            OpheliaStatusBadge(
                                status = if (isConnected) "CONNECTED" else "DISCONNECTED",
                                color = if (isConnected) BullishGreen else BearishRed
                            )
                        }

                        Divider(color = tokens.border.copy(alpha = 0.5f))

                        status["masked_key"]?.let { key ->
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(text = "API Key:", style = MaterialTheme.typography.bodySmall, color = tokens.secondaryText)
                                Text(text = key.toString(), style = MaterialTheme.typography.bodySmall, color = AccentBlue, fontFamily = FontFamily.Monospace)
                            }
                        }

                        val bal = (status["balance"] as? Number)?.toDouble() ?: 0.0
                        val eq = (status["equity"] as? Number)?.toDouble() ?: 0.0
                        val avail = (status["available_margin"] as? Number)?.toDouble() ?: 0.0

                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(8.dp))
                                .background(tokens.surfaceElevated)
                                .padding(8.dp),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Column {
                                Text(text = "BALANCE", style = MaterialTheme.typography.labelSmall, fontSize = 9.sp, color = tokens.secondaryText)
                                Text(text = "$${String.format(Locale.US, "%.2f", bal)}", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold, color = tokens.primaryText, fontFamily = FontFamily.Monospace)
                            }
                            Column {
                                Text(text = "EQUITY", style = MaterialTheme.typography.labelSmall, fontSize = 9.sp, color = tokens.secondaryText)
                                Text(text = "$${String.format(Locale.US, "%.2f", eq)}", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold, color = tokens.primaryText, fontFamily = FontFamily.Monospace)
                            }
                            Column {
                                Text(text = "AVAILABLE", style = MaterialTheme.typography.labelSmall, fontSize = 9.sp, color = tokens.secondaryText)
                                Text(text = "$${String.format(Locale.US, "%.2f", avail)}", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold, color = AccentBlue, fontFamily = FontFamily.Monospace)
                            }
                        }

                        if (isConnected) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                OpheliaOutlinedButton(
                                    text = if (isDisconnecting) "DISCONNECTING..." else "DISCONNECT",
                                    onClick = { doDisconnect() },
                                    modifier = Modifier.weight(1f),
                                    enabled = !isDisconnecting && !isSaving
                                )
                                OpheliaButton(
                                    text = "DASHBOARD",
                                    onClick = onSetupComplete,
                                    modifier = Modifier.weight(1f)
                                )
                            }
                        }
                    }
                }
            }

            // Input Form Card
            OpheliaGlassCard(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                    Text(
                        text = if (isConnected) "UPDATE BINGX CREDENTIALS" else "CONNECT BINGX ACCOUNT",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                        color = tokens.primaryText,
                        fontFamily = FontFamily.Monospace
                    )

                    OutlinedTextField(
                        value = apiKey,
                        onValueChange = { apiKey = it },
                        label = { Text("API KEY") },
                        placeholder = { Text("Paste BingX API Key") },
                        modifier = Modifier.fillMaxWidth(),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = AccentBlue,
                            unfocusedBorderColor = tokens.border,
                            focusedTextColor = tokens.primaryText,
                            unfocusedTextColor = tokens.primaryText
                        ),
                        singleLine = true
                    )

                    OutlinedTextField(
                        value = apiSecret,
                        onValueChange = { apiSecret = it },
                        label = { Text("API SECRET") },
                        placeholder = { Text("Paste BingX API Secret") },
                        modifier = Modifier.fillMaxWidth(),
                        visualTransformation = if (showSecret) VisualTransformation.None else PasswordVisualTransformation(),
                        trailingIcon = {
                            IconButton(onClick = { showSecret = !showSecret }) {
                                Icon(
                                    if (showSecret) Icons.Default.Check else Icons.Default.Lock,
                                    contentDescription = "Toggle Secret",
                                    tint = tokens.secondaryText
                                )
                            }
                        },
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = AccentBlue,
                            unfocusedBorderColor = tokens.border,
                            focusedTextColor = tokens.primaryText,
                            unfocusedTextColor = tokens.primaryText
                        ),
                        singleLine = true
                    )

                    errorMessage?.let { err ->
                        Text(
                            text = err,
                            style = MaterialTheme.typography.bodySmall,
                            color = BearishRed,
                            fontSize = 11.sp
                        )
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        OpheliaOutlinedButton(
                            text = if (isCheckingStatus) "CHECKING..." else "REFRESH STATUS",
                            onClick = { refreshStatus() },
                            modifier = Modifier.weight(1f),
                            enabled = !isCheckingStatus && !isSaving
                        )

                        OpheliaButton(
                            text = if (isSaving) "CONNECTING..." else "SAVE & CONNECT",
                            onClick = { saveAndConnect() },
                            modifier = Modifier.weight(1f),
                            enabled = !isSaving
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(24.dp))
        }
    }
}
