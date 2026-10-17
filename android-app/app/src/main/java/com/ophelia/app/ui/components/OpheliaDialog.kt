package com.ophelia.app.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.ophelia.app.ui.theme.*

// ============================================================
// OPHELIA DESIGN SYSTEM — STANDARDIZED MODAL DIALOG
// ============================================================

@Composable
fun OpheliaDialog(
    onDismissRequest: () -> Unit,
    title: String,
    modifier: Modifier = Modifier,
    subtitle: String? = null,
    badgeText: String? = null,
    badgeColor: Color? = null,
    containerColor: Color? = Color(0xFF090D14),
    confirmButton: (@Composable () -> Unit)? = null,
    dismissButton: (@Composable () -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit
) {
    Dialog(
        onDismissRequest = onDismissRequest,
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = OpheliaSpacing.md, vertical = OpheliaSpacing.xxl),
            contentAlignment = Alignment.Center
        ) {
            OpheliaGlassCard(
                modifier = modifier
                    .fillMaxWidth()
                    .wrapContentHeight(),
                level = GlassLevel.L3,
                shape = ShapeModal,
                borderColor = GlassBorderStrong,
                containerColor = containerColor
            ) {
                Column(
                    modifier = Modifier.fillMaxWidth()
                ) {
                    // Dialog Header
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(bottom = OpheliaSpacing.sm),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
                            ) {
                                Text(
                                    text = title,
                                    style = MaterialTheme.typography.titleLarge,
                                    fontWeight = FontWeight.Bold,
                                    color = TextPrimary
                                )
                                if (badgeText != null) {
                                    OpheliaStatusBadge(status = badgeText, color = badgeColor)
                                }
                            }
                            if (subtitle != null) {
                                Text(
                                    text = subtitle,
                                    style = MaterialTheme.typography.labelSmall,
                                    color = TextMuted
                                )
                            }
                        }
                    }

                    OpheliaDivider(modifier = Modifier.padding(bottom = OpheliaSpacing.md))

                    // Dialog Body
                    content()

                    // Dialog Actions Footer
                    if (confirmButton != null || dismissButton != null) {
                        Spacer(modifier = Modifier.height(OpheliaSpacing.md))
                        OpheliaDivider(modifier = Modifier.padding(bottom = OpheliaSpacing.md))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.End,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            if (dismissButton != null) {
                                dismissButton()
                                Spacer(modifier = Modifier.width(OpheliaSpacing.sm))
                            }
                            if (confirmButton != null) {
                                confirmButton()
                            }
                        }
                    }
                }
            }
        }
    }
}
