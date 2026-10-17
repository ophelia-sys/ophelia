package com.ophelia.app.ui.components

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.core.content.FileProvider
import com.ophelia.app.BuildConfig
import com.ophelia.app.models.AppVersionResponse
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.screens.UpdateDownloadState
import com.ophelia.app.ui.theme.OpheliaThemeTokens
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.text.DecimalFormat

@Composable
fun ForceUpdateChecker() {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()
    var forceUpdateInfo by remember { mutableStateOf<AppVersionResponse?>(null) }
    var downloadState by remember { mutableStateOf<UpdateDownloadState>(UpdateDownloadState.Idle) }

    LaunchedEffect(Unit) {
        try {
            val api = RetrofitClient.apiService ?: return@LaunchedEffect
            val info = withContext(Dispatchers.IO) {
                api.getAppVersion(BuildConfig.APP_CHANNEL)
            }
            val currentCode = BuildConfig.VERSION_CODE
            // Mandatory update condition: current build < minVersionCode AND forceUpdate is enabled
            if (currentCode < info.minVersionCode && info.forceUpdate) {
                forceUpdateInfo = info
            }
        } catch (e: Exception) {
            // Graceful non-blocking fallback: if VPS is unreachable, offline, or transient error,
            // allow the app to operate normally without infinite blank loading loop.
        }
    }

    val update = forceUpdateInfo ?: return

    Dialog(
        onDismissRequest = { /* Non-dismissible: mandatory update */ },
        properties = DialogProperties(dismissOnBackPress = false, dismissOnClickOutside = false)
    ) {
        val colors = OpheliaThemeTokens.colors
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            elevation = CardDefaults.cardElevation(defaultElevation = 8.dp)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(20.dp)
                    .verticalScroll(rememberScrollState()),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Box(
                    modifier = Modifier
                        .size(54.dp)
                        .clip(RoundedCornerShape(12.dp))
                        .background(Color(0xFFE53935).copy(alpha = 0.15f))
                        .border(1.dp, Color(0xFFE53935).copy(alpha = 0.4f), RoundedCornerShape(12.dp)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = Icons.Filled.Warning,
                        contentDescription = null,
                        tint = Color(0xFFE53935),
                        modifier = Modifier.size(32.dp)
                    )
                }

                Spacer(modifier = Modifier.height(16.dp))

                Text(
                    text = "MANDATORY UPDATE",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Black,
                    letterSpacing = 1.5.sp,
                    color = MaterialTheme.colorScheme.onSurface
                )

                Spacer(modifier = Modifier.height(6.dp))

                Text(
                    text = "A critical update is required to continue using Ophelia ${BuildConfig.APP_CHANNEL.uppercase()}.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = androidx.compose.ui.text.style.TextAlign.Center
                )

                Spacer(modifier = Modifier.height(16.dp))

                // Version details box
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(8.dp))
                        .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f))
                        .padding(12.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = "Installed Version:",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            text = "v${BuildConfig.VERSION_NAME} (Build ${BuildConfig.VERSION_CODE})",
                            style = MaterialTheme.typography.bodySmall,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFFE53935)
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = "Required Version:",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            text = "v${update.versionName} (Build ${update.minVersionCode})",
                            style = MaterialTheme.typography.bodySmall,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF00E676)
                        )
                    }
                }

                if (!update.releaseNotes.isNullOrBlank()) {
                    Spacer(modifier = Modifier.height(12.dp))
                    Text(
                        text = "RELEASE NOTES",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.fillMaxWidth()
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = update.releaseNotes,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.fillMaxWidth()
                    )
                }

                Spacer(modifier = Modifier.height(20.dp))

                when (val state = downloadState) {
                    is UpdateDownloadState.Idle -> {
                        Button(
                            onClick = {
                                coroutineScope.launch {
                                    downloadAndInstallApk(context, update) { newState ->
                                        downloadState = newState
                                    }
                                }
                            },
                            modifier = Modifier.fillMaxWidth(),
                            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary),
                            shape = RoundedCornerShape(8.dp)
                        ) {
                            Text("UPDATE NOW", fontWeight = FontWeight.Bold)
                        }
                    }
                    is UpdateDownloadState.Downloading -> {
                        Column(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            LinearProgressIndicator(
                                progress = state.progressPct / 100f,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(8.dp)
                                    .clip(RoundedCornerShape(4.dp))
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            val df = DecimalFormat("#.#")
                            val dlMb = df.format(state.bytesDownloaded / (1024.0 * 1024.0))
                            val totalMb = df.format(state.totalBytes / (1024.0 * 1024.0))
                            Text(
                                text = "Downloading: ${state.progressPct}% ($dlMb MB / $totalMb MB)",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                    is UpdateDownloadState.ReadyToInstall -> {
                        Button(
                            onClick = {
                                triggerApkInstallation(context, state.apkFile)
                            },
                            modifier = Modifier.fillMaxWidth(),
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF00E676)),
                            shape = RoundedCornerShape(8.dp)
                        ) {
                            Text("INSTALL APK NOW", fontWeight = FontWeight.Bold, color = Color.Black)
                        }
                    }
                    is UpdateDownloadState.Error -> {
                        Text(
                            text = state.message,
                            style = MaterialTheme.typography.bodySmall,
                            color = Color(0xFFE53935)
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Button(
                            onClick = {
                                coroutineScope.launch {
                                    downloadAndInstallApk(context, update) { newState ->
                                        downloadState = newState
                                    }
                                }
                            },
                            modifier = Modifier.fillMaxWidth(),
                            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary),
                            shape = RoundedCornerShape(8.dp)
                        ) {
                            Text("RETRY DOWNLOAD", fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }
        }
    }
}

private suspend fun downloadAndInstallApk(
    context: Context,
    info: AppVersionResponse,
    onStateChange: (UpdateDownloadState) -> Unit
) {
    onStateChange(UpdateDownloadState.Downloading(0, 0, 0))
    try {
        val api = RetrofitClient.apiService
        if (api == null) {
            onStateChange(UpdateDownloadState.Error("API service unavailable"))
            return
        }

        withContext(Dispatchers.IO) {
            val responseBody = api.downloadApk(BuildConfig.APP_CHANNEL)
            val totalBytes = responseBody.contentLength()
            val apkFile = File(context.cacheDir, "ophelia-${BuildConfig.APP_CHANNEL}-update.apk")
            if (apkFile.exists()) {
                apkFile.delete()
            }

            responseBody.byteStream().use { inputStream ->
                FileOutputStream(apkFile).use { outputStream ->
                    val buffer = ByteArray(8192)
                    var bytesRead: Int
                    var downloaded: Long = 0
                    var lastReportTime = System.currentTimeMillis()

                    while (inputStream.read(buffer).also { bytesRead = it } != -1) {
                        outputStream.write(buffer, 0, bytesRead)
                        downloaded += bytesRead
                        val now = System.currentTimeMillis()
                        if (now - lastReportTime > 200) {
                            lastReportTime = now
                            val pct = if (totalBytes > 0) ((downloaded * 100) / totalBytes).toInt() else 0
                            onStateChange(UpdateDownloadState.Downloading(pct, downloaded, totalBytes))
                        }
                    }
                    outputStream.flush()
                }
            }
            onStateChange(UpdateDownloadState.ReadyToInstall(apkFile))
        }
    } catch (e: Exception) {
        onStateChange(UpdateDownloadState.Error(e.message ?: "Download failed"))
    }
}

private fun triggerApkInstallation(context: Context, apkFile: File) {
    try {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            if (!context.packageManager.canRequestPackageInstalls()) {
                val intent = Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES).apply {
                    data = Uri.parse("package:${context.packageName}")
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
                context.startActivity(intent)
                Toast.makeText(context, "Grant permission to install unknown apps, then tap Install again", Toast.LENGTH_LONG).show()
                return
            }
        }

        val contentUri = FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            apkFile
        )

        val installIntent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(contentUri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(installIntent)
    } catch (e: Exception) {
        Toast.makeText(context, "Install failed: ${e.message}", Toast.LENGTH_LONG).show()
    }
}
