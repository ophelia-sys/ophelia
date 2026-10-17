package com.ophelia.app

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import androidx.core.content.ContextCompat
import com.ophelia.app.ui.theme.OpheliaTheme
import com.ophelia.app.ui.OpheliaApp
import com.ophelia.app.auth.TokenManager
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.notifications.NotificationHelper

class MainActivity : ComponentActivity() {

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { _ -> }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // Initialize Retrofit with TokenManager
        val tokenManager = TokenManager(applicationContext)
        RetrofitClient.initialize(tokenManager)

        // Initialize Notification Channels
        NotificationHelper.initNotificationChannels(applicationContext)

        // Request Notification Permission on Android 13+
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                requestPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }

        val themeManager = com.ophelia.app.ui.theme.ThemeManager(applicationContext)

        setContent {
            androidx.compose.runtime.CompositionLocalProvider(
                com.ophelia.app.ui.theme.LocalThemeManager provides themeManager
            ) {
                OpheliaTheme(darkTheme = themeManager.isDarkTheme) {
                    Surface(
                        modifier = Modifier.fillMaxSize(),
                        color = MaterialTheme.colorScheme.background
                    ) {
                        Box(modifier = Modifier.fillMaxSize()) {
                            if (BuildConfig.APP_ROLE == "USER") {
                                com.ophelia.app.ui.OpheliaUserApp(tokenManager)
                            } else {
                                OpheliaApp(tokenManager)
                            }
                            com.ophelia.app.ui.components.ForceUpdateChecker()
                        }
                    }
                }
            }
        }
    }
}

