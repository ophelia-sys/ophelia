package com.ophelia.app.ui.screens

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
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Star
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
import androidx.core.content.FileProvider
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.ophelia.app.models.AppVersionResponse
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.*
import com.ophelia.app.ui.theme.*
import com.ophelia.app.ui.viewmodels.UiState
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.text.DecimalFormat

sealed class UpdateDownloadState {
    object Idle : UpdateDownloadState()
    data class Downloading(val progressPct: Int, val bytesDownloaded: Long, val totalBytes: Long) : UpdateDownloadState()
    data class ReadyToInstall(val apkFile: File) : UpdateDownloadState()
    data class Error(val message: String) : UpdateDownloadState()
}

class UpdateAppViewModel : ViewModel() {
    private val _versionState = MutableStateFlow<UiState<AppVersionResponse>>(UiState.Loading)
    val versionState = _versionState.asStateFlow()

    private val _downloadState = MutableStateFlow<UpdateDownloadState>(UpdateDownloadState.Idle)
    val downloadState = _downloadState.asStateFlow()

    init {
        checkLatestVersion()
    }

    fun checkLatestVersion() {
        viewModelScope.launch {
            _versionState.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService
                if (api == null) {
                    _versionState.value = UiState.Error("API service unavailable")
                    return@launch
                }
                val versionInfo = api.getAppVersion(com.ophelia.app.BuildConfig.APP_CHANNEL)
                _versionState.value = UiState.Success(versionInfo)
            } catch (e: Exception) {
                _versionState.value = UiState.Error(e.message ?: "Failed to check update")
            }
        }
    }

    fun downloadAndInstall(context: Context) {
        viewModelScope.launch {
            _downloadState.value = UpdateDownloadState.Downloading(0, 0, 0)
            try {
                val api = RetrofitClient.apiService
                if (api == null) {
                    _downloadState.value = UpdateDownloadState.Error("API service unavailable")
                    return@launch
                }

                withContext(Dispatchers.IO) {
                    val responseBody = api.downloadApk(com.ophelia.app.BuildConfig.APP_CHANNEL)
                    val totalBytes = responseBody.contentLength()
                    val apkFile = File(context.cacheDir, "ophelia-update.apk")
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
                                    _downloadState.value = UpdateDownloadState.Downloading(pct, downloaded, totalBytes)
                                }
                            }
                            outputStream.flush()
                        }
                    }
                    _downloadState.value = UpdateDownloadState.ReadyToInstall(apkFile)
                }
            } catch (e: Exception) {
                _downloadState.value = UpdateDownloadState.Error(e.message ?: "Download failed")
            }
        }
    }

    fun installApk(context: Context, apkFile: File) {
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
            _downloadState.value = UpdateDownloadState.Error("Install failed: ${e.message}")
        }
    }
}

@Composable
fun UpdateAppScreen(
    onNavigateBack: () -> Unit,
    viewModel: UpdateAppViewModel = viewModel()
) {
    val context = LocalContext.current
    val versionState by viewModel.versionState.collectAsState()
    val downloadState by viewModel.downloadState.collectAsState()
    val currentVersion = "2.5.0"
    val currentCode = 25

    Scaffold(
        topBar = {
            OpheliaTopBar(
                title = "SOFTWARE UPDATE",
                subtitle = "In-App Distribution & Firmware Lifecycle",
                onBack = onNavigateBack,
                onRefresh = { viewModel.checkLatestVersion() }
            )
        },
        containerColor = MaterialTheme.colorScheme.background
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(horizontal = 16.dp, vertical = 8.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            // 1. Current Installed Version Glass Card
            OpheliaGlassCard {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "INSTALLED VERSION",
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.primary,
                            letterSpacing = 1.sp
                        )
                        OpheliaStatusBadge(
                            status = "ACTIVE",
                            color = BullishGreen,
                            showDot = true
                        )
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text(
                                text = "Ophelia v$currentVersion",
                                style = MaterialTheme.typography.headlineMedium,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                            Text(
                                text = "Build Code $currentCode • Architecture arm64-v8a",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }
            }

            // 2. Server Distribution Channel Card
            when (val state = versionState) {
                is UiState.Loading -> {
                    OpheliaLoadingState(message = "Querying production distribution server...")
                }
                is UiState.Error -> {
                    OpheliaErrorState(
                        message = state.message,
                        onRetry = { viewModel.checkLatestVersion() }
                    )
                }
                is UiState.Success -> {
                    val serverInfo = state.data
                    val isUpToDate = serverInfo.versionCode <= currentCode
                    val df = DecimalFormat("#,##0.0")
                    val sizeMb = if (serverInfo.apkSizeBytes > 0) df.format(serverInfo.apkSizeBytes / (1024.0 * 1024.0)) else "0.0"

                    OpheliaGlassCard {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(16.dp),
                            verticalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "SERVER DISTRIBUTION CHANNEL",
                                    style = MaterialTheme.typography.labelSmall,
                                    fontWeight = FontWeight.Bold,
                                    color = MaterialTheme.colorScheme.primary,
                                    letterSpacing = 1.sp
                                )
                                OpheliaStatusBadge(
                                    status = if (isUpToDate) "SYSTEM UP TO DATE" else "UPDATE AVAILABLE",
                                    color = if (isUpToDate) BullishGreen else WarningAmber,
                                    showDot = true
                                )
                            }

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text(
                                        text = "v${serverInfo.versionName} (Build ${serverInfo.versionCode})",
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.Bold,
                                        color = MaterialTheme.colorScheme.onSurface
                                    )
                                    Text(
                                        text = "Payload Size: $sizeMb MB • Status: ${if (serverInfo.apkAvailable) "Hosted on VPS" else "Compiling"}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            }

                            serverInfo.releaseNotes?.let { notes ->
                                OpheliaGlassPanel(
                                    modifier = Modifier.fillMaxWidth(),
                                    backgroundColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.4f)
                                ) {
                                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                        Text(
                                            text = "RELEASE NOTES",
                                            style = MaterialTheme.typography.labelSmall,
                                            fontWeight = FontWeight.Bold,
                                            color = AccentBlue,
                                            fontSize = 10.sp
                                        )
                                        Text(
                                            text = notes,
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurface
                                        )
                                    }
                                }
                            }

                            // 3. Download / Install Action & Progress
                            when (val dState = downloadState) {
                                is UpdateDownloadState.Idle -> {
                                    OpheliaButton(
                                        text = if (isUpToDate) "REINSTALL / FORCE UPDATE (v${serverInfo.versionName})" else "DOWNLOAD & INSTALL v${serverInfo.versionName}",
                                        onClick = { viewModel.downloadAndInstall(context) },
                                        modifier = Modifier.fillMaxWidth(),
                                        enabled = serverInfo.apkAvailable
                                    )
                                }
                                is UpdateDownloadState.Downloading -> {
                                    Column(
                                        modifier = Modifier.fillMaxWidth(),
                                        verticalArrangement = Arrangement.spacedBy(6.dp)
                                    ) {
                                        Row(
                                            modifier = Modifier.fillMaxWidth(),
                                            horizontalArrangement = Arrangement.SpaceBetween
                                        ) {
                                            Text(
                                                text = "DOWNLOADING FIRMWARE PAYLOAD...",
                                                style = MaterialTheme.typography.labelSmall,
                                                fontWeight = FontWeight.Bold,
                                                color = MaterialTheme.colorScheme.primary
                                            )
                                            Text(
                                                text = "${dState.progressPct}%",
                                                style = MaterialTheme.typography.labelSmall,
                                                fontWeight = FontWeight.Bold,
                                                color = AccentBlue
                                            )
                                        }
                                        LinearProgressIndicator(
                                            progress = dState.progressPct / 100f,
                                            modifier = Modifier
                                                .fillMaxWidth()
                                                .height(6.dp)
                                                .clip(RoundedCornerShape(3.dp)),
                                            color = AccentBlue,
                                            trackColor = MaterialTheme.colorScheme.surfaceVariant
                                        )
                                    }
                                }
                                is UpdateDownloadState.ReadyToInstall -> {
                                    Column(
                                        modifier = Modifier.fillMaxWidth(),
                                        verticalArrangement = Arrangement.spacedBy(8.dp)
                                    ) {
                                        Row(
                                            verticalAlignment = Alignment.CenterVertically,
                                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                                        ) {
                                            Icon(
                                                imageVector = Icons.Filled.Check,
                                                contentDescription = null,
                                                tint = BullishGreen,
                                                modifier = Modifier.size(16.dp)
                                            )
                                            Text(
                                                text = "Download Complete. Ready to install via FileProvider.",
                                                style = MaterialTheme.typography.bodySmall,
                                                color = BullishGreen,
                                                fontWeight = FontWeight.SemiBold
                                            )
                                        }
                                        OpheliaButton(
                                            text = "TRIGGER PACKAGE INSTALLER NOW",
                                            onClick = { viewModel.installApk(context, dState.apkFile) },
                                            modifier = Modifier.fillMaxWidth()
                                        )
                                    }
                                }
                                is UpdateDownloadState.Error -> {
                                    OpheliaErrorState(
                                        message = dState.message,
                                        onRetry = { viewModel.downloadAndInstall(context) }
                                    )
                                }
                            }
                        }
                    }
                }
                else -> {}
            }

            // 4. FileProvider & Security Notice
            OpheliaGlassPanel(
                modifier = Modifier.fillMaxWidth(),
                backgroundColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.25f)
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(
                        text = "INSTALLATION ARCHITECTURE",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 10.sp
                    )
                    Text(
                        text = "Ophelia distributes production APK builds directly from the dedicated VPS backend over secure HTTPS. Updates are verified through Android's secure FileProvider sandbox (REQUEST_INSTALL_PACKAGES permission).",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 11.sp,
                        lineHeight = 16.sp
                    )
                }
            }
        }
    }
}
