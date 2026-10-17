package com.ophelia.app.ui.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.ophelia.app.auth.TokenManager
import com.ophelia.app.network.RetrofitClient
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed class AuthState {
    object Idle : AuthState()
    object Loading : AuthState()
    data class Success(val userId: Long) : AuthState()
    data class Error(val message: String) : AuthState()
}

class AuthViewModel(private val tokenManager: TokenManager) : ViewModel() {
    private val _authState = MutableStateFlow<AuthState>(AuthState.Idle)
    val authState: StateFlow<AuthState> = _authState.asStateFlow()

    fun login(identifier: String, pass: String) {
        _authState.value = AuthState.Loading
        viewModelScope.launch {
            try {
                val api = RetrofitClient.apiService
                if (api == null) {
                    _authState.value = AuthState.Error("API Service not initialized")
                    return@launch
                }
                val response = api.login(mapOf(
                    "user_id" to identifier,
                    "username" to identifier,
                    "email" to identifier,
                    "password" to pass
                ))
                tokenManager.saveToken(response.token)
                _authState.value = AuthState.Success(response.userId)
            } catch (e: Exception) {
                _authState.value = AuthState.Error(e.message ?: "Unknown login error")
            }
        }
    }

    fun register(email: String, pass: String) {
        _authState.value = AuthState.Loading
        viewModelScope.launch {
            try {
                val api = RetrofitClient.apiService
                if (api == null) {
                    _authState.value = AuthState.Error("API Service not initialized")
                    return@launch
                }
                val response = api.register(mapOf("email" to email, "password" to pass))
                tokenManager.saveToken(response.token)
                _authState.value = AuthState.Success(response.userId)
            } catch (e: Exception) {
                _authState.value = AuthState.Error(e.message ?: "Unknown register error")
            }
        }
    }
}
