package com.ophelia.app.ui.screens

import android.widget.Toast
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ophelia.app.auth.TokenManager
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.theme.*
import kotlinx.coroutines.launch
import java.util.UUID

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun UserLoginScreen(
    tokenManager: TokenManager,
    onLoginSuccess: (bingxConnected: Boolean) -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val tokens = OpheliaThemeTokens.colors

    var isAuthenticating by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var emailInput by remember { mutableStateOf("") }
    var showCustomSubject by remember { mutableStateOf(false) }

    fun executeGoogleAuth(email: String, subject: String, name: String) {
        scope.launch {
            isAuthenticating = true
            errorMessage = null
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                val res = api.googleAuth(
                    mapOf(
                        "google_subject" to subject,
                        "email" to email,
                        "display_name" to name,
                        "id_token" to "mock_google_id_token_${UUID.randomUUID()}"
                    )
                )
                tokenManager.saveToken(res.token)
                Toast.makeText(context, "Welcome to Ophelia, ${res.displayName ?: res.email}!", Toast.LENGTH_SHORT).show()
                onLoginSuccess(res.bingxConnected)
            } catch (e: Exception) {
                errorMessage = e.message ?: "Authentication failed"
            } finally {
                isAuthenticating = false
            }
        }
    }

    Scaffold(
        containerColor = tokens.surface
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(24.dp),
            contentAlignment = Alignment.Center
        ) {
            OpheliaGlassCard(
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier
                        .padding(24.dp)
                        .verticalScroll(rememberScrollState()),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    // Logo & Header
                    Text(
                        text = "OPHELIA USER",
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.Black,
                        letterSpacing = 2.sp,
                        color = AccentBlue,
                        fontFamily = FontFamily.Monospace
                    )

                    Text(
                        text = "BingX Quantitative Trade Replication",
                        style = MaterialTheme.typography.bodySmall,
                        color = tokens.secondaryText,
                        fontSize = 12.sp
                    )

                    Divider(color = tokens.border.copy(alpha = 0.5f))

                    Text(
                        text = "Welcome to Ophelia Replication Fleet. Authenticate with your Google account to automatically receive and execute eligible trades 24/7 on your BingX perpetual futures account.",
                        style = MaterialTheme.typography.bodySmall,
                        color = tokens.secondaryText,
                        textAlign = androidx.compose.ui.text.style.TextAlign.Center
                    )

                    errorMessage?.let { err ->
                        OpheliaGlassCard(modifier = Modifier.fillMaxWidth(), borderColor = BearishRed) {
                            Row(
                                modifier = Modifier.padding(12.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                Icon(Icons.Default.Warning, contentDescription = null, tint = BearishRed)
                                Text(text = err, color = BearishRed, style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }

                    Column(
                        modifier = Modifier.fillMaxWidth(),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Text(
                            text = "SELECT GOOGLE ACCOUNT IDENTITY",
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold,
                            color = tokens.secondaryText,
                            fontSize = 11.sp
                        )

                        // Quick account presets for testing and production
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            FilterChip(
                                selected = emailInput == "usera@ophelia.internal",
                                onClick = { emailInput = "usera@ophelia.internal" },
                                label = { Text("User A", fontSize = 11.sp) },
                                modifier = Modifier.weight(1f)
                            )
                            FilterChip(
                                selected = emailInput == "userb@ophelia.internal",
                                onClick = { emailInput = "userb@ophelia.internal" },
                                label = { Text("User B", fontSize = 11.sp) },
                                modifier = Modifier.weight(1f)
                            )
                        }

                        OutlinedTextField(
                            value = emailInput,
                            onValueChange = { emailInput = it },
                            label = { Text("Google Account Email") },
                            placeholder = { Text("e.g. userA@ophelia.internal") },
                            modifier = Modifier.fillMaxWidth(),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = AccentBlue,
                                unfocusedBorderColor = tokens.border,
                                focusedTextColor = tokens.primaryText,
                                unfocusedTextColor = tokens.primaryText
                            ),
                            singleLine = true
                        )
                    }

                    OpheliaButton(
                        text = if (isAuthenticating) "AUTHENTICATING..." else "CONTINUE WITH GOOGLE",
                        onClick = {
                            val targetEmail = if (emailInput.trim().isNotEmpty()) emailInput.trim().lowercase() else "usera@ophelia.internal"
                            val sub = "google_sub_" + targetEmail.replace("@", "_").replace(".", "_")
                            val name = targetEmail.substringBefore("@").replaceFirstChar { it.uppercase() }
                            executeGoogleAuth(targetEmail, sub, name)
                        },
                        modifier = Modifier.fillMaxWidth(),
                        enabled = !isAuthenticating
                    )

                    Text(
                        text = "Protected by VPS Authenticated Credential Vault\n24/7 autonomous replication • No VPS credentials required",
                        style = MaterialTheme.typography.labelSmall,
                        color = tokens.mutedText,
                        fontSize = 10.sp,
                        textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }
        }
    }
}
