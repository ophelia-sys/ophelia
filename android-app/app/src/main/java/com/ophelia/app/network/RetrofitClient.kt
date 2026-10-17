package com.ophelia.app.network

import com.ophelia.app.auth.TokenManager
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object RetrofitClient {
    // Target VPS HTTPS endpoint
    private const val BASE_URL = "https://15.235.193.47/" 

    private var retrofit: Retrofit? = null
    var apiService: OpheliaApiService? = null
        private set

    val api: OpheliaApiService
        get() = apiService ?: synchronized(this) {
            apiService ?: run {
                val okHttpClient = OkHttpClient.Builder()
                    .connectTimeout(15, TimeUnit.SECONDS)
                    .readTimeout(15, TimeUnit.SECONDS)
                    .build()
                val r = Retrofit.Builder()
                    .baseUrl(BASE_URL)
                    .client(okHttpClient)
                    .addConverterFactory(GsonConverterFactory.create())
                    .build()
                val svc = r.create(OpheliaApiService::class.java)
                apiService = svc
                svc
            }
        }

    fun initialize(tokenManager: TokenManager) {
        if (retrofit == null) {
            val okHttpClient = OkHttpClient.Builder()
                .addInterceptor(AuthInterceptor(tokenManager))
                .connectTimeout(15, TimeUnit.SECONDS)
                .readTimeout(15, TimeUnit.SECONDS)
                .build()

            retrofit = Retrofit.Builder()
                .baseUrl(BASE_URL)
                .client(okHttpClient)
                .addConverterFactory(GsonConverterFactory.create())
                .build()

            apiService = retrofit?.create(OpheliaApiService::class.java)
        }
    }
}
