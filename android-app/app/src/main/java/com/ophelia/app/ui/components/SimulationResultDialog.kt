package com.ophelia.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ophelia.app.models.SimulateResponse
import com.ophelia.app.models.SimulateTradeItem
import com.ophelia.app.ui.theme.*

// ============================================================
// OPHELIA DESIGN SYSTEM — SIMULATION RESULT DIALOG
// Elevated 24H Simulation Audit Modal with IST Execution Details
// ============================================================

@Composable
fun SimulationResultDialog(
    response: SimulateResponse,
    onDismiss: () -> Unit
) {
    val strategiesText = response.strategies?.joinToString(", ") ?: response.strategy
    val timeframesText = response.timeframes?.joinToString(", ") ?: response.timeframe ?: "5m"
    val slPresetText = response.fixedSlPreset ?: "0.7% SL"

    OpheliaDialog(
        onDismissRequest = onDismiss,
        title = "STRATEGY SIMULATION AUDIT",
        subtitle = response.dateRangeIst ?: "4-Day Historical Lookback (96H)",
        badgeText = "$strategiesText | $slPresetText",
        badgeColor = AccentPurple,
        containerColor = Color(0xFF090D14),
        confirmButton = {
            OpheliaButton(text = "CLOSE", onClick = onDismiss)
        }
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(max = 560.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.md)
        ) {
            // Configuration & Scope Recap Panel
            OpheliaGlassPanel(modifier = Modifier.fillMaxWidth()) {
                Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "SCOPE: ${response.symbolsChecked.joinToString(", ")}",
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold,
                            color = TextPrimary
                        )
                        OpheliaStatusBadge(
                            status = "TF: $timeframesText",
                            color = AccentTeal
                        )
                    }
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "SL PRESET: $slPresetText",
                            style = MaterialTheme.typography.labelSmall,
                            color = TextSecondary
                        )
                        Text(
                            text = "PERIOD: 96H (4 DAYS)",
                            style = MaterialTheme.typography.labelSmall,
                            color = TextMuted
                        )
                    }
                }
            }

            // Causal Funnel Diagnostics (Always render when available)
            if (response.funnel != null) {
                val f = response.funnel
                OpheliaGlassCard(
                    level = GlassLevel.L2,
                    modifier = Modifier.fillMaxWidth(),
                    borderColor = AccentBlue.copy(alpha = 0.5f)
                ) {
                    Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "CAUSAL RETEST FUNNEL",
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.Bold,
                                color = AccentBlue
                            )
                            OpheliaStatusBadge(
                                status = if ((response.simulatedTradesCount ?: 0) > 0) "CONVERTED" else "HONEST ZERO",
                                color = if ((response.simulatedTradesCount ?: 0) > 0) BullishGreen else WarningAmber
                            )
                        }
                        OpheliaDivider()
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            OpheliaMetric(label = "Breakouts", value = "${f.breakoutCandidates}")
                            OpheliaMetric(label = "Retests", value = "${f.retestCandidates}")
                            OpheliaMetric(label = "Rejections", value = "${f.rejectionConfirmations}")
                            OpheliaMetric(
                                label = "Entries",
                                value = "${f.finalEntries}",
                                valueColor = if (f.finalEntries > 0) BullishGreen else TextSecondary
                            )
                        }
                        if (!f.reason.isNullOrBlank()) {
                            Spacer(modifier = Modifier.height(2.dp))
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clip(ShapeSmall)
                                    .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.35f))
                                    .padding(horizontal = 8.dp, vertical = 6.dp)
                            ) {
                                Text(
                                    text = "Diagnostic: ${f.reason}",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = WarningAmber
                                )
                            }
                        }
                    }
                }
            }

            // High-Density Simulation Metrics Grid
            OpheliaGlassCard(level = GlassLevel.L2, modifier = Modifier.fillMaxWidth()) {
                Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        OpheliaMetric(
                            label = "Raw Signals",
                            value = "${response.signalsCount ?: 0}",
                            valueColor = TextPrimary
                        )
                        OpheliaMetric(
                            label = "Eligible",
                            value = "${response.eligibleSignalsCount ?: 0}",
                            valueColor = BullishGreen
                        )
                        OpheliaMetric(
                            label = "Blocked",
                            value = "${response.blockedSignalsCount ?: 0}",
                            valueColor = WarningAmber
                        )
                        OpheliaMetric(
                            label = "Sim Trades",
                            value = "${response.simulatedTradesCount ?: 0}",
                            valueColor = AccentBlue
                        )
                    }

                    if ((response.simulatedTradesCount ?: 0) > 0) {
                        OpheliaDivider()
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            val winRate = response.winRatePct ?: 0.0
                            val netPnl = response.netPnlPct ?: 0.0
                            val pf = response.profitFactor ?: 0.0
                            val netR = response.netR ?: 0.0

                            OpheliaMetric(
                                label = "Win Rate",
                                value = "${winRate}%",
                                valueColor = if (winRate >= 50.0) BullishGreen else BearishRed
                            )
                            OpheliaMetric(
                                label = "Net PnL",
                                value = "${if (netPnl >= 0) "+" else ""}${netPnl}%",
                                valueColor = if (netPnl >= 0) BullishGreen else BearishRed
                            )
                            OpheliaMetric(
                                label = "Profit Factor",
                                value = "$pf",
                                valueColor = if (pf >= 1.0) BullishGreen else BearishRed
                            )
                            OpheliaMetric(
                                label = "Net R",
                                value = "${if (netR >= 0) "+" else ""}${netR}R",
                                valueColor = if (netR >= 0) BullishGreen else BearishRed
                            )
                        }
                    }
                }
            }

            // Multi-Strategy Breakdown (When multiple strategies selected)
            if (!response.resultsByStrategy.isNullOrEmpty()) {
                OpheliaSectionHeader(
                    title = "Strategy Breakdown",
                    badgeText = "${response.resultsByStrategy.size} STRATEGIES"
                )
                response.resultsByStrategy.forEach { (stratName, sRes) ->
                    OpheliaGlassPanel(modifier = Modifier.fillMaxWidth()) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column {
                                Text(
                                    text = stratName,
                                    style = MaterialTheme.typography.labelMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = TextPrimary
                                )
                                val winRate = sRes.winRatePct ?: 0.0
                                Text(
                                    text = "Signals: ${sRes.signalsCount} | Trades: ${sRes.tradesCount} | Win: ${winRate}%",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = TextSecondary
                                )
                            }
                            val pnl = sRes.netPnlPct ?: 0.0
                            Text(
                                text = "${if (pnl >= 0) "+" else ""}${pnl}%",
                                style = TabularNumberStyle,
                                color = if (pnl >= 0) BullishGreen else BearishRed,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                }
            }

            // Simulated Trade Journeys
            OpheliaSectionHeader(
                title = "Simulated Executions",
                badgeText = "${response.simulatedTradesCount ?: 0} TRADES"
            )

            if (response.trades.isNullOrEmpty()) {
                OpheliaGlassPanel(modifier = Modifier.fillMaxWidth()) {
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(
                            text = "No trades simulated in this historical window.",
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = TextPrimary
                        )
                        val reasonText = response.funnel?.reason
                            ?: "Selected strategy filters and structural target requirements did not produce an eligible execution candidate in the 96H period."
                        Text(
                            text = reasonText,
                            style = MaterialTheme.typography.bodySmall,
                            color = TextSecondary
                        )
                    }
                }
            } else {
                response.trades.forEach { tr ->
                    SimulatedTradeCard(trade = tr)
                }
            }

            // Historical Signal Candidate Audit
            if (response.signals.isNotEmpty()) {
                OpheliaSectionHeader(
                    title = "Raw Signal Audit",
                    badgeText = "${response.signals.size} SIGNALS"
                )
                response.signals.take(15).forEach { sig ->
                    OpheliaGlassPanel(modifier = Modifier.fillMaxWidth()) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)
                                ) {
                                    Text(
                                        text = "${sig.symbol} ${sig.direction}",
                                        style = MaterialTheme.typography.labelMedium,
                                        fontWeight = FontWeight.Bold,
                                        color = if (sig.direction == "LONG") BullishGreen else BearishRed
                                    )
                                    Text(
                                        text = sig.timeIst ?: sig.isoUtc ?: "",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = TextMuted
                                    )
                                }
                                Text(
                                    text = "Price: $${sig.price} | ST: ${sig.stLine?.toString() ?: "N/A"} | VWAP: ${sig.vwap?.toString() ?: "N/A"}",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = TextSecondary
                                )
                            }
                            val isEligible = sig.status == "ELIGIBLE"
                            OpheliaStatusBadge(
                                status = sig.status,
                                color = if (isEligible) BullishGreen else WarningAmber
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SimulatedTradeCard(trade: SimulateTradeItem) {
    val movePct = trade.symbolMovePct ?: trade.grossPnlPct ?: trade.realizedPnlPct
    val isMoveProfit = movePct >= 0
    val moveColor = if (isMoveProfit) BullishGreen else BearishRed
    val formattedMove = String.format(java.util.Locale.US, "%s%.2f%%", if (isMoveProfit) "+" else "", movePct)

    val netPnl = trade.realizedPnlPct
    val isNetProfit = netPnl >= 0
    val netColor = if (isNetProfit) BullishGreen else BearishRed
    val formattedNet = String.format(java.util.Locale.US, "%s%.2f%%", if (isNetProfit) "+" else "", netPnl)

    OpheliaGlassCard(
        level = GlassLevel.L2,
        modifier = Modifier.fillMaxWidth(),
        borderColor = if (isMoveProfit) BullishGreenBorder else BearishRedBorder
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)) {
            // Header: Trade Number, Symbol, Direction, PnL
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)
                ) {
                    Text(
                        text = "[#${trade.tradeId ?: 1}] ${trade.symbol}",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                        color = TextPrimary
                    )
                    OpheliaStatusBadge(
                        status = trade.direction,
                        color = if (trade.direction == "LONG") BullishGreen else BearishRed
                    )
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        text = formattedMove,
                        style = TabularNumberLargeStyle,
                        color = moveColor
                    )
                    Text(
                        text = "Net: $formattedNet",
                        style = MaterialTheme.typography.labelSmall,
                        color = netColor
                    )
                }
            }

            OpheliaDivider()

            // Entry & Exit Details with Timestamps & Candle Windows
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text("ENTRY", style = MaterialTheme.typography.labelSmall, color = TextMuted)
                    val entryTimeStr = if (trade.entryTimeIst.isNotBlank()) trade.entryTimeIst else (trade.entryTime ?: "—")
                    Text(entryTimeStr, style = MaterialTheme.typography.labelMedium, color = TextPrimary)
                    if (trade.entryCandleWindowIst != null) {
                        Text(trade.entryCandleWindowIst, style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                    }
                    Text("$${trade.entryPrice}", style = TabularNumberStyle, color = TextPrimary)
                }
                Column(modifier = Modifier.weight(1f), horizontalAlignment = Alignment.End) {
                    Text("EXIT", style = MaterialTheme.typography.labelSmall, color = TextMuted)
                    val exitTimeStr = if (trade.exitTimeIst.isNotBlank()) trade.exitTimeIst else (trade.exitTime ?: "—")
                    Text(exitTimeStr, style = MaterialTheme.typography.labelMedium, color = TextPrimary)
                    if (trade.exitCandleWindowIst != null) {
                        Text(trade.exitCandleWindowIst, style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                    }
                    Text("$${trade.exitPrice}", style = TabularNumberStyle, color = TextPrimary)
                }
            }

            // Cost & Return Breakdown Panel: Gross Symbol Move %, Fees %, Slippage %, Net %
            OpheliaGlassPanel(
                modifier = Modifier.fillMaxWidth(),
                backgroundColor = Color(0xFF0D131F),
                padding = 6.dp
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "MOVE: $formattedMove",
                        style = MaterialTheme.typography.labelSmall,
                        color = moveColor,
                        fontWeight = FontWeight.Bold
                    )
                    val feeStr = String.format(java.util.Locale.US, "%.2f", trade.feePct ?: 0.10)
                    Text(
                        text = "FEES: -$feeStr%",
                        style = MaterialTheme.typography.labelSmall,
                        color = TextMuted
                    )
                    val slipStr = String.format(java.util.Locale.US, "%.2f", trade.slippagePct ?: 0.04)
                    Text(
                        text = "SLIP: -$slipStr%",
                        style = MaterialTheme.typography.labelSmall,
                        color = TextMuted
                    )
                    Text(
                        text = "NET: $formattedNet",
                        style = MaterialTheme.typography.labelSmall,
                        color = netColor,
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            // Partial Exits
            if (trade.partialExits.isNotEmpty()) {
                Spacer(modifier = Modifier.height(2.dp))
                trade.partialExits.forEach { pe ->
                    OpheliaGlassPanel(
                        modifier = Modifier.fillMaxWidth(),
                        backgroundColor = GlassSurfaceL1,
                        padding = 6.dp
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text(
                                text = "-> ${pe.stage} (${pe.qtyPct}% qty @ $${pe.price})",
                                style = MaterialTheme.typography.labelSmall,
                                color = AccentTeal
                            )
                            val peFormatted = String.format(java.util.Locale.US, "%s%.2f%%", if (pe.pnlPct >= 0) "+" else "", pe.pnlPct)
                            Text(
                                text = peFormatted,
                                style = TabularNumberStyle,
                                color = if (pe.pnlPct >= 0) BullishGreen else BearishRed
                            )
                        }
                    }
                }
            }

            // Trailing & Breakeven Status
            if (trade.trailingActivated || trade.breakevenActivated) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(OpheliaSpacing.xs)
                ) {
                    if (trade.breakevenActivated) {
                        OpheliaStatusBadge(status = "BE ACTIVE", color = WarningAmber, showDot = false)
                    }
                    if (trade.trailingActivated) {
                        val peak = if (trade.peakPriceAfterTp != null) " ($${trade.peakPriceAfterTp})" else ""
                        OpheliaStatusBadge(status = "TRAILING$peak", color = AccentPurple, showDot = false)
                    }
                }
            }

            // Footer: Exit Reason & Duration
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "Exit: ${trade.exitReason}",
                    style = MaterialTheme.typography.labelSmall,
                    color = TextSecondary
                )
                Text(
                    text = "Duration: ${trade.durationMin ?: 0}m",
                    style = MaterialTheme.typography.labelSmall,
                    color = TextMuted
                )
            }
        }
    }
}
