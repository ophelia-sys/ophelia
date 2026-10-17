package com.ophelia.app.auth

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import java.io.File

class TokenManager(val context: Context) {
    private val prefs: SharedPreferences = createEncryptedPrefsWithFallback(context)

    fun saveToken(token: String) {
        try {
            prefs.edit().putString(KEY_TOKEN, token).apply()
        } catch (e: Exception) {
            Log.e(TAG, "Error saving token: ${e.message}")
        }
    }

    fun getToken(): String? {
        return try {
            prefs.getString(KEY_TOKEN, null)
        } catch (e: Exception) {
            Log.e(TAG, "Error getting token: ${e.message}")
            null
        }
    }

    fun clearToken() {
        try {
            prefs.edit().clear().apply()
        } catch (e: Exception) {
            Log.e(TAG, "Error clearing token: ${e.message}")
        }
    }

    companion object {
        private const val TAG = "TokenManager"
        private const val PREFS_FILE = "ophelia_secure_prefs"
        private const val FALLBACK_PREFS_FILE = "ophelia_app_prefs"
        private const val KEY_TOKEN = "jwt_token"

        private fun createEncryptedPrefsWithFallback(context: Context): SharedPreferences {
            return try {
                createEncryptedPrefs(context)
            } catch (e: Throwable) {
                Log.w(TAG, "EncryptedSharedPreferences failed, attempting recovery: ${e.message}")
                try {
                    deletePrefsFile(context, PREFS_FILE)
                    createEncryptedPrefs(context)
                } catch (e2: Throwable) {
                    Log.e(TAG, "Keystore recovery failed, using standard SharedPreferences fallback: ${e2.message}")
                    context.getSharedPreferences(FALLBACK_PREFS_FILE, Context.MODE_PRIVATE)
                }
            }
        }

        private fun createEncryptedPrefs(context: Context): SharedPreferences {
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()

            return EncryptedSharedPreferences.create(
                context,
                PREFS_FILE,
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
        }

        private fun deletePrefsFile(context: Context, fileName: String) {
            try {
                if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.N) {
                    context.deleteSharedPreferences(fileName)
                } else {
                    val prefsFile = File(context.filesDir.parent, "shared_prefs/$fileName.xml")
                    if (prefsFile.exists()) {
                        prefsFile.delete()
                    }
                }
            } catch (e: Exception) {
                Log.w(TAG, "Could not delete prefs file $fileName: ${e.message}")
            }
        }
    }
}

