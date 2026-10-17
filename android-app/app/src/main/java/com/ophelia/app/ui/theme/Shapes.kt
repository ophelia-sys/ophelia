package com.ophelia.app.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.unit.dp

// ============================================================
// OPHELIA DESIGN SYSTEM — SHAPES
// Minimal, controlled corner radii to avoid cartoonish pill bloat
// ============================================================

val ShapeSmall = RoundedCornerShape(8.dp)      // Badges, small tags, sub-metrics
val ShapeMedium = RoundedCornerShape(16.dp)    // Standard inputs, buttons, inner glass panels
val ShapeLarge = RoundedCornerShape(24.dp)     // Main cards, bottom nav bar, containers (Pill / Squircle)
val ShapeModal = RoundedCornerShape(28.dp)     // Full modals, bottom sheets, dialogs
val ShapePill = RoundedCornerShape(32.dp)      // Filter chips and status indicators

