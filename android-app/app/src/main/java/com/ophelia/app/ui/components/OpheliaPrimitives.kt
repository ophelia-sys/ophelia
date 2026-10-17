package com.ophelia.app.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ophelia.app.ui.theme.*

// ============================================================
// OPHELIA DESIGN SYSTEM — REUSABLE COMPONENT PRIMITIVES
// ============================================================

enum class GlassLevel {
    L1, // Standard Card
    L2, // Elevated / Nested Panel
    L3  // High Elevation / Dialog Modal
}

/**
 * Canonical Ophelia True 3D Liquid Glass Card.
 * Features:
 * - Rounded squircle/pill volume (24dp radius)
 * - Directional top-left specular highlight glaze
 * - Gradient rim bevel reflection (NO hard solid rectangular border strokes)
 * - Deep, soft floating ambient and spot shadows
 * - Adapts dynamically between Dark Liquid Obsidian and Light Luminous Ice
 */
@Composable
fun OpheliaGlassCard(
    modifier: Modifier = Modifier,
    level: GlassLevel = GlassLevel.L1,
    shape: Shape = ShapeLarge,
    borderWidth: Dp = 1.dp,
    borderColor: Color? = null,
    containerColor: Color? = null,
    onClick: (() -> Unit)? = null,
    content: @Composable BoxScope.() -> Unit
) {
    val isDark = MaterialTheme.colorScheme.surface.luminance() < 0.5f

    // 1. Directional Specular Bevel Border (Subtle light reflection along curved rim, NOT hard solid line)
    val specularRimBrush = if (borderColor != null) {
        Brush.linearGradient(listOf(borderColor, borderColor.copy(alpha = 0.2f)))
    } else if (isDark) {
        when (level) {
            GlassLevel.L1 -> Brush.linearGradient(
                listOf(Color(0x40FFFFFF), Color(0x1400F5FF), Color(0x05FFFFFF), Color(0x00000000))
            )
            GlassLevel.L2 -> Brush.linearGradient(
                listOf(Color(0x55FFFFFF), Color(0x20388BFD), Color(0x08FFFFFF), Color(0x00000000))
            )
            GlassLevel.L3 -> Brush.linearGradient(
                listOf(Color(0x70FFFFFF), Color(0x3000F5FF), Color(0x10FFFFFF), Color(0x00000000))
            )
        }
    } else {
        when (level) {
            GlassLevel.L1 -> Brush.linearGradient(
                listOf(Color(0x99FFFFFF), Color(0x33388BFD), Color(0x15BAE6FD), Color(0x05000000))
            )
            GlassLevel.L2 -> Brush.linearGradient(
                listOf(Color(0xB3FFFFFF), Color(0x4D0284C7), Color(0x20BAE6FD), Color(0x08000000))
            )
            GlassLevel.L3 -> Brush.linearGradient(
                listOf(Color(0xCCFFFFFF), Color(0x660369A1), Color(0x2EBAE6FD), Color(0x10000000))
            )
        }
    }

    // 2. Liquid Glass Substrate Gradient (Deep, rich translucent volume or dense override)
    val glassSubstrate = if (containerColor != null) {
        Brush.linearGradient(listOf(containerColor, containerColor))
    } else if (isDark) {
        when (level) {
            GlassLevel.L1 -> Brush.linearGradient(
                listOf(Color(0x261E293B), Color(0x1A101726), Color(0x140B101B))
            )
            GlassLevel.L2 -> Brush.linearGradient(
                listOf(Color(0x33283548), Color(0x24162032), Color(0x1C0E1724))
            )
            GlassLevel.L3 -> Brush.linearGradient(
                listOf(Color(0x47334155), Color(0x331E293B), Color(0x24121B2B))
            )
        }
    } else {
        when (level) {
            GlassLevel.L1 -> Brush.linearGradient(
                listOf(Color(0xF2FFFFFF), Color(0xE0F0F9FF), Color(0xD4E0F2FE))
            )
            GlassLevel.L2 -> Brush.linearGradient(
                listOf(Color(0xF8FFFFFF), Color(0xEBBAE6FD), Color(0xDFE0F2FE))
            )
            GlassLevel.L3 -> Brush.linearGradient(
                listOf(Color(0xFCFFFFFF), Color(0xF2BAE6FD), Color(0xE6E0F2FE))
            )
        }
    }

    // 3. Top-Left Directional Specular Sheen (Curved glass light catch)
    val topGlareSheen = if (isDark) {
        Brush.linearGradient(
            colors = listOf(
                Color(0x2BFFFFFF), // Specular apex
                Color(0x0D00F5FF), // Subtle cyan refraction
                Color(0x00000000)  // Fades softly
            )
        )
    } else {
        Brush.linearGradient(
            colors = listOf(
                Color(0x66FFFFFF), // Bright sunlit rim
                Color(0x1A388BFD), // Light azure propagation
                Color(0x00000000)
            )
        )
    }

    val clickModifier = if (onClick != null) {
        Modifier.clickable(onClick = onClick)
    } else Modifier

    // 4. Soft Floating Ambient & Spot Shadows
    val shadowElevation = when (level) {
        GlassLevel.L1 -> 8.dp
        GlassLevel.L2 -> 12.dp
        GlassLevel.L3 -> 18.dp
    }
    val ambientShadow = if (isDark) Color(0x40000000) else Color(0x140F172A)
    val spotShadow = if (isDark) Color(0x59000000) else Color(0x240284C7)

    Box(
        modifier = modifier
            .shadow(shadowElevation, shape, ambientColor = ambientShadow, spotColor = spotShadow)
            .clip(shape)
            .then(clickModifier)
            .background(glassSubstrate)
            .background(topGlareSheen)
            .border(borderWidth, specularRimBrush, shape)
            .padding(OpheliaSpacing.cardPadding),
        content = content
    )
}

/**
 * Compact nested panel with soft glass beveling for dense metrics.
 */
@Composable
fun OpheliaGlassPanel(
    modifier: Modifier = Modifier,
    shape: Shape = ShapeMedium,
    backgroundColor: Color? = null,
    borderColor: Color? = null,
    padding: Dp = OpheliaSpacing.panelPadding,
    content: @Composable BoxScope.() -> Unit
) {
    val tokens = OpheliaThemeTokens.colors
    val isDark = tokens.isDark
    val resolvedBg = backgroundColor ?: if (isDark) Color(0x1C1E293B) else Color(0xCCE0F2FE)
    val resolvedBorder = borderColor ?: if (isDark) Color(0x26FFFFFF) else Color(0x33388BFD)
    val panelShadow = if (isDark) Color(0x26000000) else Color(0x0D0284C7)

    Box(
        modifier = modifier
            .shadow(2.dp, shape, ambientColor = panelShadow, spotColor = panelShadow)
            .clip(shape)
            .background(resolvedBg)
            .border(0.75.dp, resolvedBorder, shape)
            .padding(padding),
        content = content
    )
}



/**
 * Key-Value metric display with tabular numeric styling.
 */
@Composable
fun OpheliaMetric(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
    valueColor: Color = Color.Unspecified,
    subValue: String? = null,
    subValueColor: Color = Color.Unspecified,
    isLarge: Boolean = false
) {
    val tokens = OpheliaThemeTokens.colors
    val resolvedValColor = if (valueColor != Color.Unspecified) valueColor else tokens.primaryText
    val resolvedSubColor = if (subValueColor != Color.Unspecified) subValueColor else tokens.secondaryText

    Column(modifier = modifier) {
        Text(
            text = label.uppercase(),
            style = MaterialTheme.typography.labelSmall,
            color = tokens.secondaryText,
            letterSpacing = 0.5.sp
        )
        Spacer(modifier = Modifier.height(2.dp))
        Text(
            text = value,
            style = if (isLarge) TabularNumberLargeStyle else TabularNumberStyle,
            color = resolvedValColor
        )
        if (subValue != null) {
            Spacer(modifier = Modifier.height(1.dp))
            Text(
                text = subValue,
                style = MaterialTheme.typography.labelSmall,
                color = resolvedSubColor
            )
        }
    }
}

/**
 * Standardized Section Header with crisp typography and optional trailing badge/action.
 */
@Composable
fun OpheliaSectionHeader(
    title: String,
    modifier: Modifier = Modifier,
    badgeText: String? = null,
    actionText: String? = null,
    onActionClick: (() -> Unit)? = null
) {
    val tokens = OpheliaThemeTokens.colors

    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = OpheliaSpacing.xs),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
        ) {
            Text(
                text = title.uppercase(),
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                color = tokens.secondaryText,
                letterSpacing = 0.6.sp
            )
            if (badgeText != null) {
                Surface(
                    shape = ShapeSmall,
                    color = tokens.surfaceElevated,
                    border = androidx.compose.foundation.BorderStroke(1.dp, tokens.border)
                ) {
                    Text(
                        text = badgeText,
                        style = MaterialTheme.typography.labelSmall,
                        color = tokens.primaryText,
                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 1.dp)
                    )
                }
            }
        }
        if (actionText != null && onActionClick != null) {
            Text(
                text = actionText.uppercase(),
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
                color = tokens.primaryAction,
                modifier = Modifier
                    .clip(ShapeSmall)
                    .clickable(onClick = onActionClick)
                    .padding(horizontal = 4.dp, vertical = 2.dp)
            )
        }
    }
}

/**
 * Standardized Status Badge with colored glow dot.
 */
@Composable
fun OpheliaStatusBadge(
    status: String?,
    modifier: Modifier = Modifier,
    color: Color? = null,
    showDot: Boolean = true
) {
    val s = status ?: "ACTIVE"
    val resolvedColor = color ?: when (s.uppercase()) {
        "LIVE", "CONNECTED", "ACTIVE", "HEALTHY", "NORMAL", "LONG", "BULLISH", "READY" -> BullishGreen
        "OFFLINE", "DISCONNECTED", "STOPPED", "BLOCKED", "CRITICAL", "SHORT", "BEARISH" -> BearishRed
        "SHADOW", "WARNING", "CAUTION", "PAUSED", "DEGRADED", "CONNECTING" -> WarningAmber
        else -> AccentBlue
    }

    val bgBrush = Brush.horizontalGradient(
        colors = listOf(resolvedColor.copy(alpha = 0.18f), resolvedColor.copy(alpha = 0.08f))
    )

    Surface(
        modifier = modifier,
        shape = ShapeSmall,
        color = Color.Transparent,
        border = androidx.compose.foundation.BorderStroke(1.dp, resolvedColor.copy(alpha = 0.35f))
    ) {
        Row(
            modifier = Modifier
                .background(bgBrush)
                .padding(horizontal = 7.dp, vertical = 3.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            if (showDot) {
                Box(
                    modifier = Modifier
                        .size(5.dp)
                        .clip(CircleShape)
                        .background(resolvedColor)
                )
            }
            Text(
                text = s.uppercase(),
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Bold,
                color = resolvedColor,
                letterSpacing = 0.5.sp,
                maxLines = 1,
                softWrap = false
            )
        }
    }
}

/**
 * Primary tactile button with subtle 3D gradient depth.
 */
@Composable
fun OpheliaButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    isLoading: Boolean = false,
    icon: ImageVector? = null
) {
    val tokens = OpheliaThemeTokens.colors

    Button(
        onClick = onClick,
        modifier = modifier
            .height(38.dp)
            .border(1.dp, tokens.primaryAction.copy(alpha = 0.5f), ShapeMedium),
        enabled = enabled && !isLoading,
        shape = ShapeMedium,
        colors = ButtonDefaults.buttonColors(
            containerColor = tokens.primaryAction,
            contentColor = Color.White,
            disabledContainerColor = tokens.surfaceElevated,
            disabledContentColor = tokens.mutedText
        ),
        contentPadding = PaddingValues(horizontal = 14.dp, vertical = 0.dp)
    ) {
        if (isLoading) {
            CircularProgressIndicator(
                modifier = Modifier.size(16.dp),
                color = Color.White,
                strokeWidth = 2.dp
            )
        } else {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                if (icon != null) {
                    Icon(imageVector = icon, contentDescription = null, modifier = Modifier.size(16.dp), tint = Color.White)
                }
                Text(
                    text = text,
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Bold,
                    color = Color.White
                )
            }
        }
    }
}

/**
 * Outlined / Secondary Glass button.
 */
@Composable
fun OpheliaOutlinedButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    icon: ImageVector? = null,
    textColor: Color = Color.Unspecified
) {
    val tokens = OpheliaThemeTokens.colors
    val resolvedColor = if (textColor != Color.Unspecified) textColor else tokens.primaryText

    OutlinedButton(
        onClick = onClick,
        modifier = modifier.height(38.dp),
        enabled = enabled,
        shape = ShapeMedium,
        border = androidx.compose.foundation.BorderStroke(1.dp, tokens.border),
        colors = ButtonDefaults.outlinedButtonColors(
            containerColor = tokens.surfaceElevated,
            contentColor = resolvedColor
        ),
        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 0.dp)
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            if (icon != null) {
                Icon(imageVector = icon, contentDescription = null, modifier = Modifier.size(15.dp), tint = resolvedColor)
            }
            Text(
                text = text,
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.SemiBold,
                color = resolvedColor
            )
        }
    }
}

/**
 * Distinct Destructive / Danger button for emergency actions.
 */
@Composable
fun OpheliaDangerButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true
) {
    Button(
        onClick = onClick,
        modifier = modifier
            .height(38.dp)
            .border(1.dp, BearishRedBorder, ShapeMedium),
        enabled = enabled,
        shape = ShapeMedium,
        colors = ButtonDefaults.buttonColors(
            containerColor = BearishRed,
            contentColor = Color.White
        ),
        contentPadding = PaddingValues(horizontal = 14.dp, vertical = 0.dp)
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelLarge,
            fontWeight = FontWeight.Bold,
            color = Color.White
        )
    }
}

/**
 * Filter Chip / Selection Pill for Timeframes, Strategies, Regimes.
 */
@Composable
fun OpheliaChip(
    text: String,
    isSelected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val tokens = OpheliaThemeTokens.colors
    val bg = if (isSelected) tokens.primaryAction.copy(alpha = 0.22f) else tokens.surfaceElevated
    val border = if (isSelected) tokens.primaryAction else tokens.border
    val txtColor = if (isSelected) tokens.primaryAction else tokens.secondaryText

    Surface(
        modifier = modifier
            .clip(ShapePill)
            .clickable(onClick = onClick),
        shape = ShapePill,
        color = bg,
        border = androidx.compose.foundation.BorderStroke(1.dp, border)
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelMedium,
            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
            color = txtColor,
            modifier = Modifier.padding(horizontal = 11.dp, vertical = 5.dp)
        )
    }
}

/**
 * Crisp 1px Divider using semantic border token.
 */
@Composable
fun OpheliaDivider(
    modifier: Modifier = Modifier,
    color: Color = Color.Unspecified
) {
    val tokens = OpheliaThemeTokens.colors
    val resolvedColor = if (color != Color.Unspecified) color else tokens.border
    Divider(modifier = modifier, thickness = 1.dp, color = resolvedColor)
}

/**
 * Unified Ophelia Top App Bar with Title, Subtitle/Status, Back Arrow, Refresh Action.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OpheliaTopBar(
    title: String,
    subtitle: String? = null,
    statusText: String? = null,
    statusColor: Color? = null,
    onBack: (() -> Unit)? = null,
    onRefresh: (() -> Unit)? = null,
    actions: @Composable RowScope.() -> Unit = {}
) {
    val tokens = OpheliaThemeTokens.colors

    TopAppBar(
        title = {
            Column {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = title,
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.Bold,
                        color = tokens.primaryText
                    )
                    if (statusText != null) {
                        Spacer(modifier = Modifier.width(OpheliaSpacing.sm))
                        OpheliaStatusBadge(status = statusText, color = statusColor)
                    }
                }
                if (subtitle != null) {
                    Text(
                        text = subtitle,
                        style = MaterialTheme.typography.labelSmall,
                        color = tokens.mutedText
                    )
                }
            }
        },
        navigationIcon = {
            if (onBack != null) {
                IconButton(onClick = onBack) {
                    Icon(
                        imageVector = Icons.Filled.ArrowBack,
                        contentDescription = "Back",
                        tint = tokens.primaryText
                    )
                }
            }
        },
        actions = {
            if (onRefresh != null) {
                IconButton(onClick = onRefresh) {
                    Icon(
                        imageVector = Icons.Filled.Refresh,
                        contentDescription = "Refresh",
                        tint = tokens.icon,
                        modifier = Modifier.size(20.dp)
                    )
                }
            }
            actions()
        },
        colors = TopAppBarDefaults.topAppBarColors(
            containerColor = MaterialTheme.colorScheme.background
        )
    )
}

/**
 * Compact embedded loading skeleton.
 */
@Composable
fun OpheliaLoadingState(
    modifier: Modifier = Modifier,
    message: String = "Loading terminal data..."
) {
    val tokens = OpheliaThemeTokens.colors
    Box(
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = OpheliaSpacing.xxl),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
        ) {
            CircularProgressIndicator(
                modifier = Modifier.size(24.dp),
                color = tokens.primaryAction,
                strokeWidth = 2.5.dp
            )
            Text(
                text = message,
                style = MaterialTheme.typography.labelSmall,
                color = tokens.secondaryText
            )
        }
    }
}

/**
 * Compact embedded error banner with optional retry.
 */
@Composable
fun OpheliaErrorState(
    message: String,
    onRetry: (() -> Unit)? = null,
    modifier: Modifier = Modifier
) {
    val tokens = OpheliaThemeTokens.colors
    OpheliaGlassPanel(
        modifier = modifier.fillMaxWidth(),
        backgroundColor = BearishRedSoft,
        borderColor = BearishRedBorder
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f).padding(end = OpheliaSpacing.sm)) {
                Text(
                    text = "DATA UNAVAILABLE",
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = BearishRed
                )
                Text(
                    text = message,
                    style = MaterialTheme.typography.bodySmall,
                    color = tokens.primaryText
                )
            }
            if (onRetry != null) {
                OpheliaOutlinedButton(
                    text = "RETRY",
                    onClick = onRetry,
                    textColor = BearishRed
                )
            }
        }
    }
}

/**
 * Tactile value text ensuring exact typographic and dimensional parity between Bullish/Bearish states.
 */
@Composable
fun TactileValueText(
    value: String,
    isPositive: Boolean?,
    modifier: Modifier = Modifier,
    style: androidx.compose.ui.text.TextStyle = TactileValueStyle
) {
    val color = when (isPositive) {
        true -> BullishGreen
        false -> BearishRed
        null -> MaterialTheme.colorScheme.onSurface
    }
    Text(
        text = value,
        style = style,
        color = color,
        modifier = modifier
    )
}

