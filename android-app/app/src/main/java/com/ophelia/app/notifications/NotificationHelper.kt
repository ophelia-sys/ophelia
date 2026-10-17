package com.ophelia.app.notifications

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import com.ophelia.app.MainActivity
import com.ophelia.app.models.NotificationItem

object NotificationHelper {

    const val CHANNEL_CRITICAL = "ophelia_critical"
    const val CHANNEL_TRADES = "ophelia_trades"
    const val CHANNEL_UPDATES = "ophelia_updates"

    fun initNotificationChannels(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val notificationManager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

            val criticalChannel = NotificationChannel(
                CHANNEL_CRITICAL,
                "Ophelia Critical & Risk Alerts",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "High priority liquidation warnings, risk barrier halts, and live errors"
                enableVibration(true)
                vibrationPattern = longArrayOf(0, 300, 150, 300)
            }

            val tradesChannel = NotificationChannel(
                CHANNEL_TRADES,
                "Ophelia Trade Fills & Signals",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Live order executions, partial take-profits, stop-loss triggers, and trailing moves"
                enableVibration(true)
                vibrationPattern = longArrayOf(0, 200, 100, 200)
            }

            val updatesChannel = NotificationChannel(
                CHANNEL_UPDATES,
                "Ophelia System & 4H Reports",
                NotificationManager.IMPORTANCE_DEFAULT
            ).apply {
                description = "Automations deployment, 4-Hour Equity Reports, and exchange sync"
            }

            notificationManager.createNotificationChannels(listOf(criticalChannel, tradesChannel, updatesChannel))
        }
    }

    fun postNotification(context: Context, item: NotificationItem) {
        val channelId = when (item.category) {
            "RISK" -> CHANNEL_CRITICAL
            "TRADES" -> CHANNEL_TRADES
            else -> if (item.severity == "CRITICAL") CHANNEL_CRITICAL else CHANNEL_UPDATES
        }

        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        }
        val pendingIntent = PendingIntent.getActivity(
            context,
            0,
            intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        val icon = when (item.severity) {
            "CRITICAL", "WARNING" -> android.R.drawable.stat_sys_warning
            "SUCCESS" -> android.R.drawable.stat_notify_chat
            else -> android.R.drawable.stat_notify_sync
        }

        val builder = NotificationCompat.Builder(context, channelId)
            .setSmallIcon(icon)
            .setContentTitle(item.title)
            .setContentText(item.message)
            .setStyle(NotificationCompat.BigTextStyle().bigText(item.message))
            .setPriority(if (channelId == CHANNEL_CRITICAL || channelId == CHANNEL_TRADES) NotificationCompat.PRIORITY_HIGH else NotificationCompat.PRIORITY_DEFAULT)
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)

        val notificationManager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val notifId = (item.id % Int.MAX_VALUE).toInt()
        try {
            notificationManager.notify(if (notifId > 0) notifId else (System.currentTimeMillis() % Int.MAX_VALUE).toInt(), builder.build())
        } catch (e: SecurityException) {
            // POST_NOTIFICATIONS permission not granted by user yet
        }
    }
}
