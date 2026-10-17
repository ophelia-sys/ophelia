package com.ophelia.app.ui.screens

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ophelia.app.models.SetupCandidateDto
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MlSetupReviewScreen(
    setupId: String,
    onBack: () -> Unit,
    onCreated: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var setup by remember { mutableStateOf<SetupCandidateDto?>(null) }
    var isLoading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var isSubmitting by remember { mutableStateOf(false) }

    // Mode: "ML" (Use ML Parameters) vs "CUSTOM" (Customize)
    var reviewMode by remember { mutableStateOf("ML") }

    // Editable Parameters
    var slInput by remember { mutableStateOf("") }
    var tp1Input by remember { mutableStateOf("") }
    var tp2Input by remember { mutableStateOf("") }
    var tp3Input by remember { mutableStateOf("") }
    var tp1QtyInput by remember { mutableStateOf("30.0") }
    var tp2QtyInput by remember { mutableStateOf("40.0") }
    var tp3QtyInput by remember { mutableStateOf("30.0") }
    var marginInput by remember { mutableStateOf("") }
    var suggestedMarginRef by remember { mutableStateOf(25.0) }
    var leverageInput by remember { mutableStateOf("15.0") }

    val marginParsed = marginInput.toDoubleOrNull()
    val isMarginValid = marginParsed != null && marginParsed > 0.0

    // Fetch setup details
    LaunchedEffect(setupId) {
        isLoading = true
        errorMessage = null
        try {
            val api = RetrofitClient.apiService ?: throw Exception("API service not initialized")
            val res = api.getMlSetups()
            val match = res.setups.find { it.setupId == setupId }
                ?: res.setups.firstOrNull()
            if (match != null) {
                setup = match
                slInput = match.suggestedSl.toString()
                tp1Input = match.suggestedTp1.toString()
                tp2Input = match.suggestedTp2.toString()
                if (match.suggestedTp3 != null && match.suggestedTp3 > 0) {
                    tp3Input = String.format(java.util.Locale.US, "%.2f", match.suggestedTp3)
                    tp1QtyInput = (match.tp1QtyPct ?: 30.0).toString()
                    tp2QtyInput = (match.tp2QtyPct ?: 40.0).toString()
                    tp3QtyInput = (match.tp3QtyPct ?: 30.0).toString()
                } else {
                    tp3Input = ""
                    tp1QtyInput = (match.tp1QtyPct ?: 30.0).toString()
                    tp2QtyInput = (match.tp2QtyPct ?: 40.0).toString()
                    tp3QtyInput = "0"
                }
                suggestedMarginRef = match.marginRecommendation ?: 25.0
                marginInput = "" // RULE 13: Must require explicit admin/user input!
                leverageInput = (match.leverageRecommendation ?: 15.0).toInt().toString()
            } else {
                errorMessage = "Setup candidate $setupId not found or expired."
            }
        } catch (e: Exception) {
            errorMessage = e.message ?: "Failed to load setup candidate"
        } finally {
            isLoading = false
        }
    }

    val colors = OpheliaThemeTokens.colors

    Scaffold(
        containerColor = BackgroundCanvas,
        topBar = {
            OpheliaTopBar(
                title = "IMPORT FROM ML SETUP",
                subtitle = "Option 1: TradingAgents Advisory Review",
                onBack = onBack
            )
        }
    ) { padding ->
        if (isLoading) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
            }
        } else if (errorMessage != null || setup == null) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(16.dp),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text(errorMessage ?: "Unknown error", color = BearishRed, fontWeight = FontWeight.Bold)
                    OpheliaButton(text = "GO BACK", onClick = onBack)
                }
            }
        } else {
            val s = setup!!
            val isLong = s.direction.uppercase() == "LONG"
            val dirColor = if (isLong) BullishGreen else BearishRed

            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                // Notice: No generic manual VWAP gate
                item {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(10.dp))
                            .background(AccentBlue.copy(alpha = 0.10f))
                            .border(1.dp, AccentBlue.copy(alpha = 0.35f), RoundedCornerShape(10.dp))
                            .padding(12.dp)
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Icon(Icons.Filled.Check, contentDescription = null, tint = AccentBlue, modifier = Modifier.size(18.dp))
                            Text(
                                text = "IMPORTED ML AUTOMATION — VWAP gate analyzed by Ophelia ML Intelligence; NO generic manual VWAP gate added.",
                                style = MaterialTheme.typography.bodySmall,
                                color = colors.primaryText,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }
                }

                // Section 1: AI / TRADINGAGENTS SETUP
                item {
                    OpheliaGlassCard(borderColor = dirColor.copy(alpha = 0.4f)) {
                        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Box(
                                        modifier = Modifier
                                            .clip(RoundedCornerShape(6.dp))
                                            .background(dirColor.copy(alpha = 0.15f))
                                            .padding(horizontal = 8.dp, vertical = 4.dp)
                                    ) {
                                        Text(text = s.direction, fontWeight = FontWeight.Bold, color = dirColor, style = MaterialTheme.typography.labelMedium)
                                    }
                                    Text(text = s.symbol, fontWeight = FontWeight.Bold, color = colors.primaryText, style = MaterialTheme.typography.titleMedium)
                                    Text(text = "${s.timeframe}m", color = colors.mutedText, style = MaterialTheme.typography.labelSmall)
                                }
                                OpheliaStatusBadge(status = s.status, color = BullishGreen, showDot = true)
                            }

                            OpheliaDivider()

                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                OpheliaMetric(label = "AI Confidence", value = "${s.confidencePct.toInt()}%", valueColor = dirColor)
                                OpheliaMetric(label = "Calibration", value = s.calibrationStatus ?: "NOT CALIBRATED", valueColor = colors.mutedText)
                                val rrVal = s.rewardRiskTp1 ?: s.rewardRiskRatio ?: s.riskReward
                                OpheliaMetric(label = "R:R (Reward:Risk)", value = "${String.format(java.util.Locale.US, "%.2f", rrVal)}:1", valueColor = AccentBlue)
                            }
                        }
                    }
                }

                // Section 2: WHY THIS TRADE (Thesis, Bull/Bear)
                item {
                    OpheliaGlassCard {
                        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text("WHY THIS TRADE", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = AccentPurple)
                            Text(text = s.thesis, style = MaterialTheme.typography.bodyMedium, color = colors.primaryText)

                            if (!s.bullCase.isNullOrBlank()) {
                                Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    Text("BULL CASE:", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = BullishGreen)
                                    Text(text = s.bullCase, style = MaterialTheme.typography.bodySmall, color = colors.secondaryText)
                                }
                            }
                            if (!s.bearCase.isNullOrBlank()) {
                                Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    Text("BEAR CASE:", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = BearishRed)
                                    Text(text = s.bearCase, style = MaterialTheme.typography.bodySmall, color = colors.secondaryText)
                                }
                            }
                        }
                    }
                }

                // Section 3: SERIALIZED DETERMINISTIC EVIDENCE ("WHY THIS TRADE")
                item {
                    val reasons = s.reasons ?: emptyMap()
                    @Suppress("UNCHECKED_CAST")
                    val entryMap = reasons["entry_detail"] as? Map<String, Any>
                    @Suppress("UNCHECKED_CAST")
                    val slMap = reasons["sl_detail"] as? Map<String, Any>
                    @Suppress("UNCHECKED_CAST")
                    val tp1Map = reasons["why_tp1"] as? Map<String, Any>
                    @Suppress("UNCHECKED_CAST")
                    val tp2Map = reasons["why_tp2"] as? Map<String, Any>
                    @Suppress("UNCHECKED_CAST")
                    val tp3Map = reasons["why_tp3"] as? Map<String, Any>

                    OpheliaGlassCard {
                        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            Text("DETERMINISTIC SETUP EVIDENCE (WHY THIS TRADE)", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = AccentBlue)

                            // 1. ENTRY DETAIL
                            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                val entPx = s.entryPrice ?: s.breakoutPrice ?: 0.0
                                Text("ENTRY (${String.format(java.util.Locale.US, "%.2f", entPx)})", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold, color = colors.primaryText)
                                Text("• Condition: ${entryMap?.get("condition") ?: "Breakout & Retest Confirmation"}", fontSize = 11.sp, color = colors.secondaryText)
                                Text("• Breakout/Displacement: ${entryMap?.get("breakout_reasoning") ?: "Displacement impulse with confirmed ATR expansion"}", fontSize = 11.sp, color = colors.secondaryText)
                                Text("• Retest: ${entryMap?.get("retest_reasoning") ?: "Causal zone retest within confirmed lookback window"}", fontSize = 11.sp, color = colors.secondaryText)
                                Text("• Retest Horizon: ESTIMATED / NOT CALIBRATED (3-12 bars)", fontSize = 11.sp, color = colors.secondaryText)
                                Text("• Confirmation: ${entryMap?.get("confirmation_condition") ?: "Rejection wick with directional volume"}", fontSize = 11.sp, color = BullishGreen)
                            }
                            OpheliaDivider()

                            // 2. STOP LOSS DETAIL
                            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text("STOP LOSS (${s.suggestedSl})", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold, color = BearishRed)
                                slMap?.get("structural_swing")?.let {
                                    Text("• Structural Swing Level: $it", fontSize = 11.sp, color = colors.secondaryText)
                                }
                                slMap?.get("atr_buffer_0_5x")?.let {
                                    Text("• 0.5x ATR Buffer: $it", fontSize = 11.sp, color = colors.secondaryText)
                                }
                                Text("• Invalidation: ${slMap?.get("invalidation_logic") ?: "Structural swing invalidation"}", fontSize = 11.sp, color = colors.secondaryText)
                                Text("• Risk Distance: ${s.slDistancePct ?: slMap?.get("sl_distance_pct") ?: 0.5}%", fontSize = 11.sp, color = BearishRed)
                            }
                            OpheliaDivider()

                            // 3. TARGETS DETAIL
                            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                Text("TAKE PROFIT TARGETS & ALLOCATIONS", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold, color = BullishGreen)
                                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                    Column(modifier = Modifier.weight(1f)) {
                                        Text("TP1: ${s.suggestedTp1}", fontWeight = FontWeight.Bold, fontSize = 11.sp, color = BullishGreen)
                                        Text("${tp1Map?.get("structural_reason") ?: "1.5x Risk"} (30% exit)", fontSize = 10.sp, color = colors.secondaryText)
                                    }
                                    Column(modifier = Modifier.weight(1f)) {
                                        Text("TP2: ${s.suggestedTp2}", fontWeight = FontWeight.Bold, fontSize = 11.sp, color = BullishGreen)
                                        Text("${tp2Map?.get("structural_reason") ?: "2.5x Risk"} (40% exit)", fontSize = 10.sp, color = colors.secondaryText)
                                    }
                                    if (s.suggestedTp3 != null && s.suggestedTp3 > 0) {
                                        Column(modifier = Modifier.weight(1f)) {
                                            Text("TP3: ${s.suggestedTp3}", fontWeight = FontWeight.Bold, fontSize = 11.sp, color = BullishGreen)
                                            Text("${tp3Map?.get("structural_reason") ?: "4.0x Risk"} (30% exit)", fontSize = 10.sp, color = colors.secondaryText)
                                        }
                                    } else {
                                        Column(modifier = Modifier.weight(1f)) {
                                            Text("TP3: UNAVAILABLE", fontWeight = FontWeight.Bold, fontSize = 11.sp, color = colors.secondaryText)
                                            Text("No swing level", fontSize = 10.sp, color = colors.secondaryText)
                                        }
                                    }
                                }
                            }
                            OpheliaDivider()

                            // 4. ORDER FLOW & INDICATOR EVIDENCE
                            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text("ORDER FLOW & INDICATOR EVIDENCE", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold, color = colors.primaryText)
                                Text("• VWAP: ${reasons["vwap_evidence"] ?: "Price confirmed with volume-weighted benchmark"}", fontSize = 11.sp, color = colors.secondaryText)
                                Text("• Gate: ${reasons["vwap_gate_status"] ?: "VWAP: ANALYZED BY ML (GENERIC MANUAL VWAP GATE: NOT ADDED)"}", fontSize = 11.sp, color = AccentBlue)
                                Text("• CVD / Order Flow: ${reasons["cvd_order_flow"] ?: "CVD aggression confirmed"}", fontSize = 11.sp, color = colors.secondaryText)
                                Text("• RVOL: ${reasons["rvol"] ?: "RVOL > 1.2 baseline volume expansion"}", fontSize = 11.sp, color = colors.secondaryText)
                                Text("• FVG: ${reasons["fvg"] ?: "Fair Value Gap magnet interaction"}", fontSize = 11.sp, color = colors.secondaryText)
                                Text("• MTF Context: ${reasons["mtf_context"] ?: "Multi-timeframe structural alignment"}", fontSize = 11.sp, color = colors.secondaryText)
                            }
                            OpheliaDivider()

                            // 5. CALIBRATION NOTICE
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                Icon(Icons.Filled.Info, contentDescription = null, tint = WarningAmber, modifier = Modifier.size(16.dp))
                                Text(
                                    text = reasons["empirical_calibration_notice"] as? String ?: "EMPIRICAL SUCCESS PROBABILITY: NOT CALIBRATED",
                                    style = MaterialTheme.typography.labelSmall,
                                    fontWeight = FontWeight.Bold,
                                    color = WarningAmber
                                )
                            }
                        }
                    }
                }

                // Section 4: MODE SWITCHER (USE ML PARAMETERS vs CUSTOMIZE)
                item {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(10.dp))
                            .background(MaterialTheme.colorScheme.surfaceVariant)
                            .padding(4.dp),
                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        Box(
                            modifier = Modifier
                                .weight(1f)
                                .clip(RoundedCornerShape(8.dp))
                                .background(if (reviewMode == "ML") MaterialTheme.colorScheme.primary else Color.Transparent)
                                .clickable { reviewMode = "ML" }
                                .padding(vertical = 10.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                "USE ML PARAMETERS",
                                fontWeight = FontWeight.Bold,
                                fontSize = 12.sp,
                                color = if (reviewMode == "ML") Color.White else colors.secondaryText
                            )
                        }
                        Box(
                            modifier = Modifier
                                .weight(1f)
                                .clip(RoundedCornerShape(8.dp))
                                .background(if (reviewMode == "CUSTOM") MaterialTheme.colorScheme.primary else Color.Transparent)
                                .clickable { reviewMode = "CUSTOM" }
                                .padding(vertical = 10.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                "CUSTOMIZE",
                                fontWeight = FontWeight.Bold,
                                fontSize = 12.sp,
                                color = if (reviewMode == "CUSTOM") Color.White else colors.secondaryText
                            )
                        }
                    }
                }

                // Section 5: TARGETS, STOPS & QUANTITY ALLOCATION
                item {
                    val entryVal = s.entryPrice ?: s.breakoutPrice ?: s.suggestedSl
                    val slVal = slInput.toDoubleOrNull() ?: s.suggestedSl
                    val tp1Val = tp1Input.toDoubleOrNull() ?: s.suggestedTp1
                    val tp2Val = tp2Input.toDoubleOrNull() ?: s.suggestedTp2
                    val tp3Val = tp3Input.toDoubleOrNull() ?: s.suggestedTp3

                    val isLongDir = s.direction.uppercase() == "LONG"
                    val riskDist = if (isLongDir) kotlin.math.abs(entryVal - slVal) else kotlin.math.abs(slVal - entryVal)
                    val rewDistTp1 = if (isLongDir) kotlin.math.abs(tp1Val - entryVal) else kotlin.math.abs(entryVal - tp1Val)
                    val rewDistTp2 = if (isLongDir) kotlin.math.abs(tp2Val - entryVal) else kotlin.math.abs(entryVal - tp2Val)
                    val rewDistTp3 = if (tp3Val != null) (if (isLongDir) kotlin.math.abs(tp3Val - entryVal) else kotlin.math.abs(entryVal - tp3Val)) else null

                    val dynamicRrTp1 = if (riskDist > 0) rewDistTp1 / riskDist else 1.5
                    val dynamicRrTp2 = if (riskDist > 0) rewDistTp2 / riskDist else 3.0
                    val dynamicRrTp3 = if (rewDistTp3 != null && riskDist > 0) rewDistTp3 / riskDist else null

                    val slPctDyn = if (entryVal > 0) (riskDist / entryVal) * 100.0 else 0.5
                    val tp1PctDyn = if (entryVal > 0) (rewDistTp1 / entryVal) * 100.0 else 0.75
                    val tp2PctDyn = if (entryVal > 0) (rewDistTp2 / entryVal) * 100.0 else 1.25
                    val tp3PctDyn = if (rewDistTp3 != null && entryVal > 0) (rewDistTp3 / entryVal) * 100.0 else null

                    val marginVal = marginParsed ?: 0.0
                    val levVal = leverageInput.toDoubleOrNull() ?: 15.0
                    val notionalVal = marginVal * levVal
                    val maxLossVal = marginVal * (slPctDyn / 100.0) * levVal
                    val qtyVal = if (entryVal > 0) notionalVal / entryVal else 0.0

                    OpheliaGlassCard {
                        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text("TRADE EXECUTION PARAMETERS", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = colors.primaryText)
                                val originTag = if (reviewMode == "CUSTOM") "USER MODIFIED FROM ML RECOMMENDATION" else "ORIGINAL ML RECOMMENDATION"
                                val originColor = if (reviewMode == "CUSTOM") WarningAmber else BullishGreen
                                OpheliaStatusBadge(status = originTag, color = originColor)
                            }

                            // Dynamic Live R:R Strip
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text("R:R TP1 = ${String.format(java.util.Locale.US, "%.2f", dynamicRrTp1)}:1", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
                                Text("TP2 = ${String.format(java.util.Locale.US, "%.2f", dynamicRrTp2)}:1", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = AccentTeal)
                                if (dynamicRrTp3 != null) {
                                    Text("TP3 = ${String.format(java.util.Locale.US, "%.2f", dynamicRrTp3)}:1", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = AccentPurple)
                                } else {
                                    Text("TP3: N/A", style = MaterialTheme.typography.labelSmall, color = colors.secondaryText)
                                }
                            }

                            // SL
                            OutlinedTextField(
                                value = slInput,
                                onValueChange = { if (reviewMode == "CUSTOM") slInput = it },
                                readOnly = reviewMode == "ML",
                                label = { Text("Stop Loss (SL)") },
                                supportingText = {
                                    Text("Distance: -${String.format(java.util.Locale.US, "%.2f", slPctDyn)}% • Structural invalidation", color = BearishRed)
                                },
                                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                                modifier = Modifier.fillMaxWidth()
                            )

                            // TP1
                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                OutlinedTextField(
                                    value = tp1Input,
                                    onValueChange = { if (reviewMode == "CUSTOM") tp1Input = it },
                                    readOnly = reviewMode == "ML",
                                    label = { Text("Target 1 (TP1)") },
                                    supportingText = {
                                        Text("+${String.format(java.util.Locale.US, "%.2f", tp1PctDyn)}% distance", color = BullishGreen)
                                    },
                                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                                    modifier = Modifier.weight(1.5f)
                                )
                                OutlinedTextField(
                                    value = tp1QtyInput,
                                    onValueChange = { if (reviewMode == "CUSTOM") tp1QtyInput = it },
                                    readOnly = reviewMode == "ML",
                                    label = { Text("Exit %") },
                                    supportingText = { Text("Default: 30%") },
                                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                                    modifier = Modifier.weight(1f)
                                )
                            }

                            // TP2
                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                OutlinedTextField(
                                    value = tp2Input,
                                    onValueChange = { if (reviewMode == "CUSTOM") tp2Input = it },
                                    readOnly = reviewMode == "ML",
                                    label = { Text("Target 2 (TP2)") },
                                    supportingText = {
                                        Text("+${String.format(java.util.Locale.US, "%.2f", tp2PctDyn)}% distance", color = BullishGreen)
                                    },
                                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                                    modifier = Modifier.weight(1.5f)
                                )
                                OutlinedTextField(
                                    value = tp2QtyInput,
                                    onValueChange = { if (reviewMode == "CUSTOM") tp2QtyInput = it },
                                    readOnly = reviewMode == "ML",
                                    label = { Text("Exit %") },
                                    supportingText = { Text("Default: 40%") },
                                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                                    modifier = Modifier.weight(1f)
                                )
                            }

                            // TP3
                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                OutlinedTextField(
                                    value = tp3Input,
                                    onValueChange = { if (reviewMode == "CUSTOM") tp3Input = it },
                                    readOnly = reviewMode == "ML",
                                    label = { Text("Target 3 (TP3)") },
                                    supportingText = {
                                        Text("+${String.format(java.util.Locale.US, "%.2f", tp3PctDyn)}% distance", color = BullishGreen)
                                    },
                                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                                    modifier = Modifier.weight(1.5f)
                                )
                                OutlinedTextField(
                                    value = tp3QtyInput,
                                    onValueChange = { if (reviewMode == "CUSTOM") tp3QtyInput = it },
                                    readOnly = reviewMode == "ML",
                                    label = { Text("Exit %") },
                                    supportingText = { Text("Default: 30%") },
                                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                                    modifier = Modifier.weight(1f)
                                )
                            }

                            // Partial Exit Management Note
                            val totalExitPct = (tp1QtyInput.toDoubleOrNull() ?: 30.0) + (tp2QtyInput.toDoubleOrNull() ?: 40.0) + (tp3QtyInput.toDoubleOrNull() ?: 30.0)
                            val remainingPct = kotlin.math.max(0.0, 100.0 - totalExitPct)
                            Text(
                                text = "Partial Exits: Total ${totalExitPct.toInt()}% | Remaining: ${remainingPct.toInt()}% → TRAIL TO BREAKEVEN / FINAL TARGET",
                                style = MaterialTheme.typography.bodySmall,
                                fontSize = 10.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )

                            // ML Reference Advisory (Rule 13: distinguish suggested reference from execution input)
                            Text(
                                text = "ML Reference Suggested: $${String.format(java.util.Locale.US, "%.1f", suggestedMarginRef)} USDT (Advisory Only — Explicit Authorization Required)",
                                style = MaterialTheme.typography.bodySmall,
                                fontSize = 11.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )

                            // Margin & Leverage (Admin Execution Config: always editable)
                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                OutlinedTextField(
                                    value = marginInput,
                                    onValueChange = { marginInput = it },
                                    readOnly = false,
                                    label = { Text("Margin (USDT)") },
                                    isError = !isMarginValid && marginInput.isNotEmpty(),
                                    supportingText = {
                                        if (marginInput.isEmpty()) {
                                            Text("MARGIN REQUIRED", color = WarningAmber, fontWeight = FontWeight.Bold)
                                        } else if (!isMarginValid) {
                                            Text("Invalid Margin", color = MaterialTheme.colorScheme.error)
                                        } else {
                                            Text("Notional: $${String.format(java.util.Locale.US, "%.2f", notionalVal)}")
                                        }
                                    },
                                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                                    modifier = Modifier.weight(1f)
                                )
                                OutlinedTextField(
                                    value = leverageInput,
                                    onValueChange = { leverageInput = it },
                                    readOnly = false,
                                    label = { Text("Leverage (x)") },
                                    supportingText = { Text("Max Loss: $${String.format(java.util.Locale.US, "%.2f", maxLossVal)}") },
                                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                                    modifier = Modifier.weight(1f)
                                )
                            }

                            Text(
                                text = "Estimated Position Quantity: ${String.format(java.util.Locale.US, "%.4f", qtyVal)} contracts",
                                style = MaterialTheme.typography.bodySmall,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.SemiBold,
                                color = MaterialTheme.colorScheme.primary
                            )
                        }
                    }
                }

                // CTA: CREATE AUTOMATION
                item {
                    OpheliaButton(
                        text = if (isSubmitting) "CREATING AUTOMATION..."
                               else if (!isMarginValid) "MARGIN REQUIRED — ENTER MARGIN"
                               else "CONFIRM & CREATE AUTOMATION",
                        enabled = !isSubmitting && isMarginValid,
                        onClick = {
                            if (!isMarginValid) {
                                Toast.makeText(context, "MARGIN REQUIRED: Please enter explicit margin", Toast.LENGTH_SHORT).show()
                                return@OpheliaButton
                            }

                            val tp1Pct = tp1QtyInput.toDoubleOrNull() ?: 30.0
                            val tp2Pct = tp2QtyInput.toDoubleOrNull() ?: 40.0
                            val tp3Pct = tp3QtyInput.toDoubleOrNull() ?: 30.0

                            if (tp1Pct + tp2Pct + tp3Pct > 100.0) {
                                Toast.makeText(context, "Sum of exit quantities cannot exceed 100%", Toast.LENGTH_SHORT).show()
                                return@OpheliaButton
                            }

                            scope.launch {
                                isSubmitting = true
                                try {
                                    val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                                    val marginVal = marginParsed!!
                                    val levVal = leverageInput.toDoubleOrNull() ?: 15.0
                                    val payload = mutableMapOf<String, Any>(
                                        "setup_id" to s.setupId,
                                        "origin" to if (reviewMode == "CUSTOM") "USER_MODIFIED_FROM_ML" else "ML_RECOMMENDATION",
                                        "tp1_qty_pct" to tp1Pct,
                                        "tp2_qty_pct" to tp2Pct,
                                        "tp3_qty_pct" to tp3Pct,
                                        "margin" to marginVal,
                                        "margin_usdt" to marginVal,
                                        "leverage" to levVal
                                    )
                                    if (reviewMode == "CUSTOM") {
                                        slInput.toDoubleOrNull()?.let { payload["custom_sl"] = it }
                                        tp1Input.toDoubleOrNull()?.let { payload["custom_tp1"] = it }
                                        tp2Input.toDoubleOrNull()?.let { payload["custom_tp2"] = it }
                                        tp3Input.toDoubleOrNull()?.let { payload["custom_tp3"] = it }
                                    }

                                    val res = api.createAutomationFromSetup(payload)
                                    Toast.makeText(context, "Created Automation #${res.automationId} for ${res.symbol}!", Toast.LENGTH_LONG).show()
                                    onCreated()
                                } catch (e: Exception) {
                                    Toast.makeText(context, "Error: ${e.message}", Toast.LENGTH_LONG).show()
                                } finally {
                                    isSubmitting = false
                                }
                            }
                        },
                        modifier = Modifier.fillMaxWidth()
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                }
            }
        }
    }
}
