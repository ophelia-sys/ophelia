package com.ophelia.app.network

import com.ophelia.app.auth.TokenManager
import okhttp3.Interceptor
import okhttp3.Response
import android.util.Log

class AuthInterceptor(private val tokenManager: TokenManager) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()
        
        val token = tokenManager.getToken()
        val requestBuilder = originalRequest.newBuilder()
        
        if (token != null) {
            requestBuilder.addHeader("Authorization", "Bearer $token")
        }

        val finalRequest = requestBuilder.build()
        Log.d("OPHELIA_API", "--> ${finalRequest.method} ${finalRequest.url}")
        Log.d("OPHELIA_API", "--> Auth Header Present: ${finalRequest.header("Authorization") != null}")

        val response = chain.proceed(finalRequest)
        
        Log.d("OPHELIA_API", "<-- ${response.code} ${response.request.url}")
        
        if (response.code == 400) {
            val errorBody = response.peekBody(Long.MAX_VALUE).string()
            Log.d("OPHELIA_API", "<-- 400 Error Body: $errorBody")
        }

        if (response.code == 401) {
            Log.w("OPHELIA_API", "Received 401 Unauthorized. Token might be expired.")
            tokenManager.clearToken()
        }

        return response
    }
}
