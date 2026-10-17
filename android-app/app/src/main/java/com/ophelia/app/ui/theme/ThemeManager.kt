package com.ophelia.app.ui.theme

import android.content.Context
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

class ThemeManager(context: Context) {
    val isDarkTheme: Boolean
        get() = true

    fun toggleTheme() {
        // Obsidian Dark Theme is permanently locked
    }

    fun setDarkTheme(enabled: Boolean) {
        // Obsidian Dark Theme is permanently locked
    }
}

val LocalThemeManager = compositionLocalOf<ThemeManager> {
    error("No ThemeManager provided")
}
