package com.ophelia.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import com.ophelia.app.auth.TokenManager
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.viewmodels.AuthState
import com.ophelia.app.ui.viewmodels.AuthViewModel
import com.ophelia.app.ui.theme.*

@Composable
fun LoginScreen(
    onLoginSuccess: () -> Unit
) {
    val context = LocalContext.current
    val tokenManager = remember { TokenManager(context) }
    
    val viewModel: AuthViewModel = viewModel(
        factory = object : ViewModelProvider.Factory {
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return AuthViewModel(tokenManager) as T
            }
        }
    )

    val authState by viewModel.authState.collectAsState()
    
    var userId by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }

    LaunchedEffect(authState) {
        if (authState is AuthState.Success) {
            onLoginSuccess()
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(BackgroundCanvas),
        contentAlignment = Alignment.Center
    ) {
        OpheliaGlassCard(
            level = GlassLevel.L2,
            modifier = Modifier
                .fillMaxWidth(0.9f)
                .padding(OpheliaSpacing.md)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(OpheliaSpacing.md),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.md)
            ) {
                // Header Branding
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(
                        text = "OPHELIA",
                        style = MaterialTheme.typography.displayMedium,
                        fontWeight = FontWeight.Bold,
                        color = TextPrimary,
                        letterSpacing = 2.sp
                    )
                    Text(
                        text = "Admin Perpetual Swap Terminal",
                        style = MaterialTheme.typography.labelSmall,
                        color = TextSecondary,
                        letterSpacing = 0.5.sp
                    )
                }

                OpheliaDivider()

                // Form Fields
                OutlinedTextField(
                    value = userId,
                    onValueChange = { userId = it },
                    label = { Text("User ID") },
                    placeholder = { Text("ophelia-sys") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text),
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = AccentBlue,
                        unfocusedBorderColor = GlassBorderSubtle,
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary,
                        focusedContainerColor = GlassSurfaceL1,
                        unfocusedContainerColor = GlassSurfaceL1
                    )
                )

                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it },
                    label = { Text("Password") },
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = AccentBlue,
                        unfocusedBorderColor = GlassBorderSubtle,
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary,
                        focusedContainerColor = GlassSurfaceL1,
                        unfocusedContainerColor = GlassSurfaceL1
                    )
                )

                if (authState is AuthState.Error) {
                    OpheliaErrorState(message = (authState as AuthState.Error).message)
                }

                // Action Buttons
                OpheliaButton(
                    text = "OPERATOR LOGIN",
                    onClick = { viewModel.login(userId, password) },
                    modifier = Modifier.fillMaxWidth(),
                    isLoading = authState is AuthState.Loading
                )
            }
        }
    }
}
