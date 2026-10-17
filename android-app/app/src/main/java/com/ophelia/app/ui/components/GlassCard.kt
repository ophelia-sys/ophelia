package com.ophelia.app.ui.components

import androidx.compose.foundation.layout.BoxScope
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.ophelia.app.ui.theme.ShapeLarge

/**
 * Legacy GlassCard wrapper that routes directly into the new OpheliaGlassCard design system.
 */
@Composable
fun GlassCard(
    modifier: Modifier = Modifier,
    shape: Shape = ShapeLarge,
    level: GlassLevel = GlassLevel.L1,
    backgroundColor: Color? = null,
    borderColor: Color? = null,
    borderWidth: Dp = 1.dp,
    onClick: (() -> Unit)? = null,
    content: @Composable BoxScope.() -> Unit
) {
    OpheliaGlassCard(
        modifier = modifier,
        level = level,
        shape = shape,
        borderWidth = borderWidth,
        borderColor = borderColor,
        onClick = onClick,
        content = content
    )
}
