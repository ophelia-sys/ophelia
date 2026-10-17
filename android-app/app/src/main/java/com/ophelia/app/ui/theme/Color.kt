package com.ophelia.app.ui.theme

import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color

// ============================================================
// OPHELIA DESIGN SYSTEM — SEMANTIC COLOR SYSTEM FOR DUAL THEMES
// ============================================================

@Immutable
data class OpheliaSemanticColors(
    val primaryText: Color,
    val secondaryText: Color,
    val mutedText: Color,
    val positiveText: Color,
    val negativeText: Color,
    val warningText: Color,
    val primaryAction: Color,
    val surface: Color,
    val surfaceElevated: Color,
    val border: Color,
    val icon: Color,
    val isDark: Boolean = true
)

val DarkSemanticColors = OpheliaSemanticColors(
    primaryText = Color(0xFFF8FAFC),
    secondaryText = Color(0xFF94A3B8),
    mutedText = Color(0xFF64748B),
    positiveText = Color(0xFF10B981),
    negativeText = Color(0xFFF43F5E),
    warningText = Color(0xFFF59E0B),
    primaryAction = Color(0xFF388BFD),
    surface = Color(0xFF101726),
    surfaceElevated = Color(0xFF162032),
    border = Color(0x33FFFFFF),
    icon = Color(0xFF94A3B8),
    isDark = true
)

val LightSemanticColors = OpheliaSemanticColors(
    primaryText = Color(0xFF0F172A),      // Slate 900 high contrast
    secondaryText = Color(0xFF1E293B),    // Slate 800 high contrast
    mutedText = Color(0xFF475569),        // Slate 600
    positiveText = Color(0xFF059669),    // Emerald 600
    negativeText = Color(0xFFE11D48),    // Rose 600
    warningText = Color(0xFFD97706),     // Amber 600
    primaryAction = Color(0xFF0284C7),   // Sky 600
    surface = Color(0xECF0F9FF),         // Pale cyan translucent glass
    surfaceElevated = Color(0xF2E0F2FE), // Sky-blue elevated translucent glass
    border = Color(0x59388BFD),          // Crisp sky-blue refractive border
    icon = Color(0xFF334155),            // Slate 700
    isDark = false
)

val LocalOpheliaSemanticColors = staticCompositionLocalOf { DarkSemanticColors }

object OpheliaThemeTokens {
    val colors: OpheliaSemanticColors
        @Composable
        @ReadOnlyComposable
        get() = LocalOpheliaSemanticColors.current
}

// Brand Accents
val AccentBlue = Color(0xFF388BFD)          // Cyan-Blue primary action
val AccentBlueGlow = Color(0x33388BFD)      // Soft ambient blue glow
val AccentTeal = Color(0xFF2DD4BF)          // Secondary metric teal
val AccentPurple = Color(0xFFA855F7)        // Strategy/Intelligence accent

// Semantic Trading Colors
val BullishGreen = Color(0xFF10B981)        // Clean emerald profit/LONG
val BullishGreenSoft = Color(0x2610B981)    // 15% green background
val BullishGreenBorder = Color(0x6610B981)  // 40% green border
val BearishRed = Color(0xFFF43F5E)          // Rose/Coral loss/SHORT
val BearishRedSoft = Color(0x26F43F5E)      // 15% red background
val BearishRedBorder = Color(0x66F43F5E)    // 40% red border

// System & Warning Colors
val WarningAmber = Color(0xFFF59E0B)        // Amber caution
val WarningAmberSoft = Color(0x26F59E0B)    // 15% amber background
val AccentYellow = Color(0xFFF59E0B)        // Accent yellow / warning amber
val InfoBlue = Color(0xFF0EA5E9)            // Informational badge
val NeutralGray = Color(0xFF64748B)         // Slate 500

// High-Density Dynamic Semantic Typography & Backgrounds
val TextPrimary: Color
    @Composable
    @ReadOnlyComposable
    get() = OpheliaThemeTokens.colors.primaryText

val TextSecondary: Color
    @Composable
    @ReadOnlyComposable
    get() = OpheliaThemeTokens.colors.secondaryText

val TextMuted: Color
    @Composable
    @ReadOnlyComposable
    get() = OpheliaThemeTokens.colors.mutedText

val TextDisabled: Color
    @Composable
    @ReadOnlyComposable
    get() = OpheliaThemeTokens.colors.mutedText.copy(alpha = 0.6f)

val BackgroundCanvas: Color
    @Composable
    @ReadOnlyComposable
    get() = if (OpheliaThemeTokens.colors.isDark) Color(0xFF0B101B) else Color(0xFFEBF3FA)

val BackgroundElevated: Color
    @Composable
    @ReadOnlyComposable
    get() = OpheliaThemeTokens.colors.surfaceElevated

val BackgroundVoid: Color
    @Composable
    @ReadOnlyComposable
    get() = if (OpheliaThemeTokens.colors.isDark) Color(0xFF070B12) else Color(0xFFE2E8F0)

// Glass Surface Tones
val GlassSurfaceL1: Color
    @Composable
    @ReadOnlyComposable
    get() = if (OpheliaThemeTokens.colors.isDark) Color(0x18FFFFFF) else Color(0xECF0F9FF)

val GlassSurfaceL2: Color
    @Composable
    @ReadOnlyComposable
    get() = if (OpheliaThemeTokens.colors.isDark) Color(0x24FFFFFF) else Color(0xF2E0F2FE)

val GlassSurfaceL3: Color
    @Composable
    @ReadOnlyComposable
    get() = if (OpheliaThemeTokens.colors.isDark) Color(0x38FFFFFF) else Color(0xF5E0F2FE)

val GlassSurfaceDark = Color(0x990A0F1D)

// Borders & Highlights
val GlassBorderSubtle: Color
    @Composable
    @ReadOnlyComposable
    get() = if (OpheliaThemeTokens.colors.isDark) Color(0x33FFFFFF) else Color(0x40388BFD)

val GlassBorderMedium: Color
    @Composable
    @ReadOnlyComposable
    get() = if (OpheliaThemeTokens.colors.isDark) Color(0x4D388BFD) else Color(0x660284C7)

val GlassBorderStrong: Color
    @Composable
    @ReadOnlyComposable
    get() = if (OpheliaThemeTokens.colors.isDark) Color(0x8000E5FF) else Color(0x8C0369A1)


val GlassTopHighlight = Color(0x40FFFFFF)

// 3D Glass Gradients
val GlassCardGradient = Brush.verticalGradient(
    colors = listOf(
        Color(0x2E00F5FF),
        Color(0x1A101726)
    )
)

val GlassElevatedGradient = Brush.verticalGradient(
    colors = listOf(
        Color(0x3D388BFD),
        Color(0x24162032)
    )
)

val LightGlassCardGradient = Brush.verticalGradient(
    colors = listOf(
        Color(0xF0FFFFFF), // 94% translucent reflective top edge
        Color(0xD9E0F2FE), // 85% translucent sky-blue refractive glass
        Color(0xE6F0F9FF)  // 90% translucent pale cyan glass base
    )
)

val LightGlassElevatedGradient = Brush.verticalGradient(
    colors = listOf(
        Color(0xF5FFFFFF), // 96% translucent specular top
        Color(0xE0BAE6FD), // 88% translucent cyan-blue glass
        Color(0xECF0F9FF)  // 92% translucent pale ice glass
    )
)

val PrimaryButtonGradient = Brush.horizontalGradient(
    colors = listOf(
        Color(0xFF2563EB),
        Color(0xFF3B82F6)
    )
)

val DangerButtonGradient = Brush.horizontalGradient(
    colors = listOf(
        Color(0xFFE11D48),
        Color(0xFFF43F5E)
    )
)

val BullishBadgeGradient = Brush.horizontalGradient(
    colors = listOf(
        Color(0x3310B981),
        Color(0x1A10B981)
    )
)

val BearishBadgeGradient = Brush.horizontalGradient(
    colors = listOf(
        Color(0x33F43F5E),
        Color(0x1AF43F5E)
    )
)

// Legacy aliases for backwards compatibility
val PrimaryBlue = AccentBlue
val PrimaryBlueLight = AccentBlue
val SecondaryTeal = AccentTeal
val WarningOrange = WarningAmber
val BackgroundDark: Color
    @Composable
    @ReadOnlyComposable
    get() = BackgroundCanvas
val SurfaceDark: Color
    @Composable
    @ReadOnlyComposable
    get() = BackgroundElevated
val SurfaceLight = Color(0xFF1E293B)
val TextTertiary: Color
    @Composable
    @ReadOnlyComposable
    get() = TextMuted
val GlassOverlay: Color
    @Composable
    @ReadOnlyComposable
    get() = GlassSurfaceL1
val GlassBorder: Color
    @Composable
    @ReadOnlyComposable
    get() = GlassBorderSubtle

// Fast UI aliases
val PrimaryText = Color(0xFFF8FAFC)
val SecondaryText = Color(0xFF94A3B8)
val AccentCyan = Color(0xFF00E5FF)
val AccentGreen = BullishGreen
val CardBackground = Color(0xFF162032)
val BorderColor = Color(0x33FFFFFF)

