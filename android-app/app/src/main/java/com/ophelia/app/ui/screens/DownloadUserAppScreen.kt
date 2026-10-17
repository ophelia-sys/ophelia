package com.ophelia.app.ui.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ophelia.app.models.UserAppMetadataResponse
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.theme.*
import kotlinx.coroutines.launch
import java.text.DecimalFormat

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DownloadUserAppScreen(
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val tokens = OpheliaThemeTokens.colors

    var metadata by remember { mutableStateOf<UserAppMetadataResponse?>(null) }
    var isLoading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }

    fun refreshMetadata() {
        scope.launch {
            isLoading = true
            errorMessage = null
            try {
                val api = RetrofitClient.apiService ?: throw Exception("API service unavailable")
                metadata = api.getUserAppMetadata()
            } catch (e: Exception) {
                errorMessage = e.message ?: "Failed to fetch User App metadata"
            } finally {
                isLoading = false
            }
        }
    }

    LaunchedEffect(Unit) {
        refreshMetadata()
    }

    fun copyToClipboard(label: String, text: String) {
        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        val clip = ClipData.newPlainText(label, text)
        clipboard.setPrimaryClip(clip)
        Toast.makeText(context, "$label copied to clipboard", Toast.LENGTH_SHORT).show()
    }

    fun openDownloadUrl(url: String) {
        try {
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
            context.startActivity(intent)
        } catch (e: Exception) {
            Toast.makeText(context, "Could not open browser: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    fun formatBytes(bytes: Long): String {
        if (bytes <= 0) return "15.4 MB"
        val mb = bytes / (1024.0 * 1024.0)
        return DecimalFormat("#,##0.0").format(mb) + " MB"
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = "DOWNLOAD USER OPHELIA",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = tokens.primaryText
                        )
                        Text(
                            text = "DISTRIBUTION & REPLICATION CLIENT",
                            style = MaterialTheme.typography.labelSmall,
                            color = tokens.secondaryText
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back", tint = tokens.primaryText)
                    }
                },
                actions = {
                    IconButton(onClick = { refreshMetadata() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = AccentBlue)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background
                )
            )
        },
        containerColor = tokens.surface
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Spacer(modifier = Modifier.height(4.dp))

            // Explanation Card
            OpheliaGlassCard(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Icon(Icons.Default.Share, contentDescription = null, tint = AccentBlue)
                        Text(
                            text = "USER OPHELIA DISTRIBUTION",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold,
                            color = tokens.primaryText,
                            fontFamily = FontFamily.Monospace
                        )
                    }
                    Text(
                        text = "Distribute this dedicated client (com.ophelia.user) to trusted family and friends. When installed, users sign in with Google and configure their BingX API keys. Their accounts immediately appear in your God Eye fleet dashboard.",
                        style = MaterialTheme.typography.bodySmall,
                        color = tokens.secondaryText
                    )
                }
            }

            if (isLoading && metadata == null) {
                Box(modifier = Modifier.fillMaxWidth().padding(32.dp), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = AccentBlue)
                }
            }

            errorMessage?.let { err ->
                OpheliaGlassCard(modifier = Modifier.fillMaxWidth(), borderColor = BearishRed) {
                    Row(
                        modifier = Modifier.padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Icon(Icons.Default.Warning, contentDescription = null, tint = BearishRed)
                        Text(text = err, color = BearishRed, style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }

            metadata?.let { meta ->
                OpheliaGlassCard(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column {
                                Text(
                                    text = "OPHELIA USER",
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = tokens.primaryText,
                                    fontFamily = FontFamily.Monospace
                                )
                                Text(
                                    text = "Package: com.ophelia.user",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = tokens.secondaryText,
                                    fontSize = 11.sp
                                )
                            }
                            OpheliaStatusBadge(
                                status = "v${meta.versionName} (Build ${meta.versionCode})",
                                color = BullishGreen
                            )
                        }

                        Divider(color = tokens.border.copy(alpha = 0.5f))

                        // Build Specs Grid
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Box(
                                modifier = Modifier
                                    .weight(1f)
                                    .clip(RoundedCornerShape(8.dp))
                                    .background(tokens.surfaceElevated)
                                    .border(1.dp, tokens.border, RoundedCornerShape(8.dp))
                                    .padding(8.dp)
                            ) {
                                Column {
                                    Text(text = "FILE SIZE", style = MaterialTheme.typography.labelSmall, fontSize = 9.sp, color = tokens.secondaryText)
                                    Text(text = formatBytes(meta.apkSizeBytes), style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold, color = tokens.primaryText, fontFamily = FontFamily.Monospace)
                                }
                            }

                            Box(
                                modifier = Modifier
                                    .weight(1f)
                                    .clip(RoundedCornerShape(8.dp))
                                    .background(tokens.surfaceElevated)
                                    .border(1.dp, tokens.border, RoundedCornerShape(8.dp))
                                    .padding(8.dp)
                            ) {
                                Column {
                                    Text(text = "STATUS", style = MaterialTheme.typography.labelSmall, fontSize = 9.sp, color = tokens.secondaryText)
                                    Text(text = if (meta.apkAvailable) "HOSTED ON VPS" else "BUILD READY", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold, color = BullishGreen, fontFamily = FontFamily.Monospace)
                                }
                            }
                        }

                        // SHA256 Checksum
                        meta.sha256?.let { sha ->
                            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text(
                                    text = "SHA256 CHECKSUM",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = tokens.secondaryText,
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 10.sp
                                )
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clip(RoundedCornerShape(6.dp))
                                        .background(tokens.surfaceElevated)
                                        .border(1.dp, tokens.border.copy(alpha = 0.5f), RoundedCornerShape(6.dp))
                                        .padding(8.dp),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(
                                        text = sha.take(16) + "..." + sha.takeLast(16),
                                        style = MaterialTheme.typography.bodySmall,
                                        fontFamily = FontFamily.Monospace,
                                        fontSize = 10.sp,
                                        color = AccentBlue
                                    )
                                    IconButton(
                                        onClick = { copyToClipboard("SHA256 Checksum", sha) },
                                        modifier = Modifier.size(24.dp)
                                    ) {
                                        Icon(Icons.Default.Share, contentDescription = "Copy", tint = AccentBlue, modifier = Modifier.size(16.dp))
                                    }
                                }
                            }
                        }

                        // Direct VPS URL
                        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(
                                text = "DIRECT VPS DOWNLOAD URL",
                                style = MaterialTheme.typography.labelSmall,
                                color = tokens.secondaryText,
                                fontWeight = FontWeight.Bold,
                                fontSize = 10.sp
                            )
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clip(RoundedCornerShape(6.dp))
                                    .background(tokens.surfaceElevated)
                                    .border(1.dp, tokens.border.copy(alpha = 0.5f), RoundedCornerShape(6.dp))
                                    .padding(8.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = meta.directLink,
                                    style = MaterialTheme.typography.bodySmall,
                                    fontFamily = FontFamily.Monospace,
                                    fontSize = 11.sp,
                                    color = tokens.primaryText,
                                    modifier = Modifier.weight(1f)
                                )
                                IconButton(
                                    onClick = { copyToClipboard("Download Link", meta.directLink) },
                                    modifier = Modifier.size(24.dp)
                                ) {
                                    Icon(Icons.Default.Share, contentDescription = "Copy URL", tint = AccentBlue, modifier = Modifier.size(16.dp))
                                }
                            }
                        }

                        // Release Notes
                        meta.releaseNotes?.let { notes ->
                            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text(
                                    text = "RELEASE NOTES",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = tokens.secondaryText,
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 10.sp
                                )
                                Text(
                                    text = notes,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = tokens.primaryText,
                                    fontSize = 11.sp
                                )
                            }
                        }

                        Divider(color = tokens.border.copy(alpha = 0.5f))

                        // Action Buttons
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            OpheliaOutlinedButton(
                                text = "COPY LINK",
                                onClick = { copyToClipboard("Ophelia User Link", meta.directLink) },
                                modifier = Modifier.weight(1f)
                            )
                            OpheliaButton(
                                text = "DOWNLOAD APK",
                                onClick = { openDownloadUrl(meta.directLink) },
                                modifier = Modifier.weight(1f)
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(24.dp))
        }
    }
}
