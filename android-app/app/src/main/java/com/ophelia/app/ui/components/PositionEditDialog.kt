package com.ophelia.app.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ophelia.app.models.DashboardPositionSummary
import com.ophelia.app.ui.theme.*

// ============================================================
// OPHELIA DESIGN SYSTEM — POSITION MANAGEMENT MODAL
// ============================================================

@Composable
fun PositionEditDialog(
    position: DashboardPositionSummary,
    onDismiss: () -> Unit,
    onSave: (stopLoss: Double?, takeProfit: Double?, trailing: Boolean) -> Unit,
    onPartialClose: (qtyPct: Double) -> Unit = {},
    onClosePosition: () -> Unit
) {
    var slText by remember { mutableStateOf("") }
    var tpText by remember { mutableStateOf("") }
    var trailingEnabled by remember { mutableStateOf(false) }
    var showCloseConfirm by remember { mutableStateOf(false) }

    val isManual = position.source == "BINGX MANUAL" || position.managementStatus == "EXTERNAL POSITION"
    val pnlColor = if (position.unrealizedPnl >= 0) BullishGreen else BearishRed

    if (showCloseConfirm) {
        OpheliaDialog(
            onDismissRequest = { showCloseConfirm = false },
            title = "EMERGENCY MARKET CLOSE",
            subtitle = "Immediate position termination",
            badgeText = "DANGER",
            badgeColor = BearishRed,
            confirmButton = {
                OpheliaDangerButton(
                    text = "CONFIRM MARKET CLOSE",
                    onClick = {
                        showCloseConfirm = false
                        onClosePosition()
                    }
                )
            },
            dismissButton = {
                OpheliaOutlinedButton(
                    text = "CANCEL",
                    onClick = { showCloseConfirm = false }
                )
            }
        ) {
            Text(
                text = "Are you sure you want to execute an immediate market close for ${position.symbol} (${position.direction})?",
                style = MaterialTheme.typography.bodyMedium,
                color = TextPrimary
            )
            Spacer(modifier = Modifier.height(OpheliaSpacing.sm))
            Text(
                text = "This will submit a market exit order directly to BingX and terminate the position.",
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary
            )
        }
    }

    OpheliaDialog(
        onDismissRequest = onDismiss,
        title = "${position.symbol} (${position.direction})",
        subtitle = if (isManual) "External BingX Position" else "Ophelia Core Managed",
        badgeText = position.direction,
        badgeColor = if (position.direction == "LONG") BullishGreen else BearishRed,
        confirmButton = {
            OpheliaButton(
                text = "APPLY CHANGES",
                onClick = {
                    onSave(
                        slText.toDoubleOrNull(),
                        tpText.toDoubleOrNull(),
                        trailingEnabled
                    )
                }
            )
        },
        dismissButton = {
            OpheliaOutlinedButton(
                text = "CANCEL",
                onClick = onDismiss
            )
        }
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(max = 480.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.md)
        ) {
            // Key Position Metrics Panel
            OpheliaGlassCard(level = GlassLevel.L2, modifier = Modifier.fillMaxWidth()) {
                Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        OpheliaMetric(label = "Entry", value = "$${position.entry}")
                        OpheliaMetric(label = "Mark", value = "$${position.currentPrice}")
                        OpheliaMetric(label = "Margin", value = "$${position.margin} (${position.leverage.toInt()}x)")
                        OpheliaMetric(
                            label = "PnL",
                            value = "$${position.unrealizedPnl}",
                            valueColor = pnlColor,
                            subValue = "${position.unrealizedPnlPct}%",
                            subValueColor = pnlColor
                        )
                    }
                    if (position.liquidationPrice != null && position.liquidationPrice > 0.0) {
                        OpheliaDivider()
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("EST. LIQUIDATION", style = MaterialTheme.typography.labelSmall, color = BearishRed)
                            Text("$${position.liquidationPrice}", style = TabularNumberStyle, color = BearishRed)
                        }
                    }
                }
            }

            // Partial Exit Controls
            OpheliaSectionHeader(title = "Partial Exit")
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.sm)
            ) {
                OpheliaOutlinedButton(
                    text = "25%",
                    onClick = { onPartialClose(25.0) },
                    modifier = Modifier.weight(1f)
                )
                OpheliaOutlinedButton(
                    text = "50%",
                    onClick = { onPartialClose(50.0) },
                    modifier = Modifier.weight(1f)
                )
                OpheliaOutlinedButton(
                    text = "75%",
                    onClick = { onPartialClose(75.0) },
                    modifier = Modifier.weight(1f)
                )
            }

            // Stop Loss & Take Profit Adjustments
            OpheliaSectionHeader(title = "Risk Management Orders")
            OutlinedTextField(
                value = slText,
                onValueChange = { slText = it },
                label = { Text("Stop Loss Price (USDT)") },
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
                value = tpText,
                onValueChange = { tpText = it },
                label = { Text("Take Profit Price (USDT)") },
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

            // Trailing Stop Toggle
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = OpheliaSpacing.xs),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text("Trailing Stop (0.8%)", style = MaterialTheme.typography.bodyMedium, color = TextPrimary)
                    Text("Dynamic high-water mark trailing", style = MaterialTheme.typography.labelSmall, color = TextMuted)
                }
                Switch(
                    checked = trailingEnabled,
                    onCheckedChange = { trailingEnabled = it },
                    colors = SwitchDefaults.colors(
                        checkedThumbColor = TextPrimary,
                        checkedTrackColor = AccentBlue,
                        uncheckedThumbColor = TextSecondary,
                        uncheckedTrackColor = BackgroundElevated
                    )
                )
            }

            // Emergency Market Close
            OpheliaDivider()
            OpheliaDangerButton(
                text = "CLOSE ENTIRE POSITION NOW",
                onClick = { showCloseConfirm = true },
                modifier = Modifier.fillMaxWidth()
            )
        }
    }
}
