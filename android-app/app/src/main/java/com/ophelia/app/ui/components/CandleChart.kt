package com.ophelia.app.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ophelia.app.models.CandleItem
import com.ophelia.app.ui.theme.*
import kotlin.math.max
import kotlin.math.min

@Composable
fun CandleChart(
    candles: List<CandleItem>,
    modifier: Modifier = Modifier
) {
    if (candles.isEmpty()) {
        Box(
            modifier = modifier.background(BackgroundElevated.copy(alpha = 0.5f)),
            contentAlignment = Alignment.Center
        ) {
            Text("No candle data available", style = MaterialTheme.typography.bodySmall, color = TextMuted)
        }
        return
    }

    var selectedIndex by remember { mutableStateOf<Int?>(null) }
    val displayCandles = remember(candles) { candles.takeLast(60) }

    val minPrice = remember(displayCandles) { displayCandles.minOfOrNull { it.low } ?: 0.0 }
    val maxPrice = remember(displayCandles) { displayCandles.maxOfOrNull { it.high } ?: 1.0 }
    val priceRange = remember(minPrice, maxPrice) { max(maxPrice - minPrice, 0.0001) }

    val maxVolume = remember(displayCandles) { displayCandles.maxOfOrNull { it.volume } ?: 1.0 }

    val gridColor = GlassBorderSubtle

    Column(modifier = modifier) {
        // Selected Candle Header Inspection Info
        val activeCandle = selectedIndex?.let { displayCandles.getOrNull(it) } ?: displayCandles.lastOrNull()
        if (activeCandle != null) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 4.dp, vertical = 2.dp),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text("O: ${activeCandle.open}", style = TabularNumberStyle, fontSize = 10.sp, color = TextSecondary)
                Text("H: ${activeCandle.high}", style = TabularNumberStyle, fontSize = 10.sp, color = TextSecondary)
                Text("L: ${activeCandle.low}", style = TabularNumberStyle, fontSize = 10.sp, color = TextSecondary)
                Text(
                    "C: ${activeCandle.close}",
                    style = TabularNumberStyle,
                    fontSize = 10.sp,
                    color = if (activeCandle.close >= activeCandle.open) BullishGreen else BearishRed
                )
                Text("V: ${activeCandle.volume.toInt()}", style = TabularNumberStyle, fontSize = 10.sp, color = TextMuted)
            }
        }

        Box(modifier = Modifier.fillMaxWidth().weight(1f)) {
            Canvas(
                modifier = Modifier
                    .fillMaxSize()
                    .pointerInput(displayCandles) {
                        detectTapGestures { offset ->
                            val candleWidth = size.width / displayCandles.size
                            val idx = (offset.x / candleWidth).toInt().coerceIn(0, displayCandles.size - 1)
                            selectedIndex = idx
                        }
                    }
            ) {
                val width = size.width
                val height = size.height
                val candleCount = displayCandles.size
                val candleWidth = width / candleCount
                val bodyWidth = candleWidth * 0.7f

                // Draw Horizontal Price Grid Lines
                val gridLines = 4
                for (i in 0..gridLines) {
                    val y = height * (i.toFloat() / gridLines)
                    drawLine(
                        color = gridColor,
                        start = Offset(0f, y),
                        end = Offset(width, y),
                        strokeWidth = 1f,
                        pathEffect = PathEffect.dashPathEffect(floatArrayOf(4f, 4f))
                    )
                }

                // Draw Candles & Volume Bars
                displayCandles.forEachIndexed { i, candle ->
                    val isBullish = candle.close >= candle.open
                    val color = if (isBullish) BullishGreen else BearishRed
                    val xCenter = i * candleWidth + (candleWidth / 2f)

                    // Price Y coordinates
                    val highY = height * (1f - ((candle.high - minPrice) / priceRange).toFloat())
                    val lowY = height * (1f - ((candle.low - minPrice) / priceRange).toFloat())
                    val openY = height * (1f - ((candle.open - minPrice) / priceRange).toFloat())
                    val closeY = height * (1f - ((candle.close - minPrice) / priceRange).toFloat())

                    // Wick
                    drawLine(
                        color = color,
                        start = Offset(xCenter, highY),
                        end = Offset(xCenter, lowY),
                        strokeWidth = 1.2f
                    )

                    // Body
                    val bodyTop = min(openY, closeY)
                    val bodyHeight = max(kotlin.math.abs(closeY - openY), 2f)
                    drawRect(
                        color = color,
                        topLeft = Offset(xCenter - (bodyWidth / 2f), bodyTop),
                        size = Size(bodyWidth, bodyHeight)
                    )

                    // Volume Bar (bottom 18% of canvas)
                    val volHeight = (candle.volume / maxVolume).toFloat() * (height * 0.18f)
                    drawRect(
                        color = color.copy(alpha = 0.25f),
                        topLeft = Offset(xCenter - (bodyWidth / 2f), height - volHeight),
                        size = Size(bodyWidth, volHeight)
                    )
                }

                // Highlight Selected Candle Vertical Line
                selectedIndex?.let { idx ->
                    val x = idx * candleWidth + (candleWidth / 2f)
                    drawLine(
                        color = Color.White.copy(alpha = 0.35f),
                        start = Offset(x, 0f),
                        end = Offset(x, height),
                        strokeWidth = 1f
                    )
                }
            }

            // Price Labels on right edge
            Column(
                modifier = Modifier
                    .align(Alignment.CenterEnd)
                    .fillMaxHeight()
                    .padding(end = 4.dp),
                verticalArrangement = Arrangement.SpaceBetween
            ) {
                Text("$maxPrice", style = MaterialTheme.typography.labelSmall, color = TextMuted, fontSize = 8.sp)
                Text("${(maxPrice + minPrice) / 2}", style = MaterialTheme.typography.labelSmall, color = TextMuted, fontSize = 8.sp)
                Text("$minPrice", style = MaterialTheme.typography.labelSmall, color = TextMuted, fontSize = 8.sp)
            }
        }
    }
}
