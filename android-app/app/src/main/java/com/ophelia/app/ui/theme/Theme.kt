package com.ophelia.app.ui.theme

import android.app.Activity
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

// ============================================================
// OPHELIA DESIGN SYSTEM — DUAL THEME CONFIGURATION
// 1. Dark Glass (3D Glass, subtle depth, high contrast)
// 2. Light Clean (Crisp white/slate surfaces, sharp typography)
// ============================================================

private val OpheliaDarkColorScheme = darkColorScheme(
    primary = AccentBlue,
    onPrimary = Color(0xFFF8FAFC),
    primaryContainer = Color(0xFF162032),
    onPrimaryContainer = Color(0xFFF8FAFC),
    secondary = AccentTeal,
    onSecondary = Color(0xFFF8FAFC),
    secondaryContainer = Color(0xFF0F172A),
    onSecondaryContainer = Color(0xFFF8FAFC),
    tertiary = AccentPurple,
    onTertiary = Color(0xFFF8FAFC),
    background = Color(0xFF0B101B),
    onBackground = Color(0xFFF8FAFC),
    surface = Color(0xFF101726),
    onSurface = Color(0xFFF8FAFC),
    surfaceVariant = Color(0xFF162032),
    onSurfaceVariant = Color(0xFF94A3B8),
    outline = Color(0x33FFFFFF),
    outlineVariant = Color(0x1FFFFFFF),
    error = BearishRed,
    onError = Color(0xFFF8FAFC)
)

private val OpheliaLightColorScheme = lightColorScheme(
    primary = Color(0xFF0284C7), // Sky 600
    onPrimary = Color.White,
    primaryContainer = Color(0xFFE0F2FE),
    onPrimaryContainer = Color(0xFF0369A1),
    secondary = Color(0xFF0D9488), // Teal 600
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFCCFBF1),
    onSecondaryContainer = Color(0xFF0F766E),
    tertiary = Color(0xFF7C3AED), // Purple 600
    onTertiary = Color.White,
    background = Color(0xFFEBF3FA), // Pale ice-blue background with depth
    onBackground = Color(0xFF0F172A), // Slate 900 high contrast text
    surface = Color(0xECF0F9FF), // Translucent pale cyan glass
    onSurface = Color(0xFF0F172A), // Slate 900 text
    surfaceVariant = Color(0xF2E0F2FE), // Sky-blue elevated translucent glass
    onSurfaceVariant = Color(0xFF1E293B), // Slate 800 high contrast
    outline = Color(0x59388BFD), // Sky-blue refractive border
    outlineVariant = Color(0x3300E5FF),
    error = Color(0xFFE11D48), // Rose 600
    onError = Color.White
)

@Composable
fun OpheliaTheme(
    darkTheme: Boolean = true,
    content: @Composable () -> Unit
) {
    // Obsidian Dark Theme is permanent
    val colorScheme = OpheliaDarkColorScheme
    val semanticColors = DarkSemanticColors
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            val bg = Color(0xFF0B101B)
            window.statusBarColor = bg.toArgb()
            window.navigationBarColor = bg.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = false
            WindowCompat.getInsetsController(window, view).isAppearanceLightNavigationBars = false
        }
    }

    CompositionLocalProvider(LocalOpheliaSemanticColors provides semanticColors) {
        MaterialTheme(
            colorScheme = colorScheme,
            typography = Typography,
            content = content
        )
    }
}
