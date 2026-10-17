package com.ophelia.app.ui.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.ophelia.app.auth.TokenManager
import com.ophelia.app.models.*
import com.ophelia.app.network.RetrofitClient
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class AutomationViewModel(private val tokenManager: TokenManager) : ViewModel() {

    // Researched Candidates from Forensic Screening
    val strategies = listOf("OPHELIA_COMPOSITE", "D_WITHOUT_CVD")
    val symbolScopes = listOf("SINGLE", "MULTIPLE", "ALL_WATCHLIST")
    val directions = listOf("LONG", "SHORT", "ANY")
    val timeframes = listOf(1, 3, 5, 15, 30, 60, 240)
    val lifecycles = listOf("CONTINUOUS", "ONE_SHOT")

    // Form State
    var selectedStrategies = MutableStateFlow<Set<String>>(setOf("OPHELIA_COMPOSITE"))
    var strategy = MutableStateFlow("OPHELIA_COMPOSITE")
    var symbolScope = MutableStateFlow("ALL_WATCHLIST")
    var selectedSymbols = MutableStateFlow<List<String>>(emptyList())
    var direction = MutableStateFlow("ANY")
    var vwapGateEnabled = MutableStateFlow(false)
    
    var marginPct = MutableStateFlow("45.0")
    var isFixedMargin = MutableStateFlow(false)
    var leverage = MutableStateFlow("15")
    var lifecycle = MutableStateFlow("CONTINUOUS")

    // Stop Loss Presets: 3m/5m -> 0.7%, 15m -> 1.0%, user configurable
    var selectedTimeframes = MutableStateFlow<Set<Int>>(setOf(5))
    var selectedTimeframe = MutableStateFlow(5)
    var hardStopPct = MutableStateFlow("0.7")
    var trailingEnabled = MutableStateFlow(true)
    var trailingTrailPct = MutableStateFlow("0.5")
    var breakEven = MutableStateFlow(true)
    var targets = MutableStateFlow(listOf(TargetConfig(1.1, 40.0), TargetConfig(1.8, 30.0), TargetConfig(2.5, 30.0)))

    fun toggleStrategy(strat: String) {
        val current = selectedStrategies.value.toMutableSet()
        if (current.contains(strat)) {
            if (current.size > 1) {
                current.remove(strat)
            }
        } else {
            current.add(strat)
        }
        selectedStrategies.value = current
        strategy.value = current.firstOrNull() ?: strat
    }

    fun toggleTimeframe(tf: Int) {
        val current = selectedTimeframes.value.toMutableSet()
        if (current.contains(tf)) {
            if (current.size > 1) {
                current.remove(tf)
            }
        } else {
            current.add(tf)
        }
        selectedTimeframes.value = current
        selectedTimeframe.value = current.firstOrNull() ?: tf
        updateSlDefault()
    }

    fun setTimeframePreset(tf: Int) {
        selectedTimeframe.value = tf
        selectedTimeframes.value = setOf(tf)
        updateSlDefault()
    }

    private fun updateSlDefault() {
        val tf = selectedTimeframe.value
        if (tf in listOf(3, 5)) {
            hardStopPct.value = "0.7"
        } else if (tf == 15) {
            hardStopPct.value = "1.0"
        }
    }

    // Compatibility bridges
    var stVwapTimeframe = selectedTimeframe
    var stVwapHardStopPct = hardStopPct
    var stVwapStructuralVwapEnabled = MutableStateFlow(true)
    var stVwapStructuralVwapPct = MutableStateFlow("0.2")
    var stVwapStructuralStEnabled = MutableStateFlow(true)
    var stVwapStructuralStPct = MutableStateFlow("0.2")
    var stVwapBreakEven = breakEven
    var stVwapTargets = targets
    var stVwapTrailingEnabled = trailingEnabled
    var stVwapTrailingTrailPct = trailingTrailPct

    var emaTimeframe = selectedTimeframe
    var emaHardStopPct = hardStopPct
    var emaStructuralEnabled = MutableStateFlow(true)
    var emaStructuralPct = MutableStateFlow("0.2")
    var emaReverseExit = MutableStateFlow(true)
    var emaBreakEven = breakEven
    var emaTargets = targets
    var emaTrailingEnabled = trailingEnabled
    var emaTrailingTrailPct = trailingTrailPct

    // Data lists
    private val _watchlist = MutableStateFlow<List<String>>(emptyList())
    val watchlist = _watchlist.asStateFlow()

    private val _automations = MutableStateFlow<UiState<List<AutomationConfig>>>(UiState.Loading)
    val automations = _automations.asStateFlow()

    private val _accountCapacity = MutableStateFlow<AccountCapacity?>(null)
    val accountCapacity = _accountCapacity.asStateFlow()

    private val _currentMode = MutableStateFlow("SHADOW")
    val currentMode = _currentMode.asStateFlow()

    private val _saveState = MutableStateFlow<UiState<Boolean>>(UiState.Idle)
    val saveState = _saveState.asStateFlow()

    init {
        fetchWatchlist()
        fetchAutomations()
        fetchCapacity()
        fetchCurrentMode()
    }

    fun fetchCurrentMode() {
        viewModelScope.launch {
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val health = api.getHealth()
                val mode = health["mode"]?.toString() ?: "SHADOW"
                _currentMode.value = mode
            } catch (e: Exception) {}
        }
    }

    fun fetchCapacity() {
        viewModelScope.launch {
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val cap = api.getAccountCapacity()
                _accountCapacity.value = cap
            } catch (e: Exception) {}
        }
    }

    private fun fetchWatchlist() {
        viewModelScope.launch {
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val res = api.getWatchlist()
                _watchlist.value = res.symbols
            } catch (e: Exception) {}
        }
    }

    fun fetchAutomations() {
        viewModelScope.launch {
            _automations.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val res = api.getAutomations()
                _automations.value = UiState.Success(res.automations)
            } catch (e: Exception) {
                _automations.value = UiState.Error(e.message ?: "Failed to fetch automations")
            }
        }
    }

    fun toggleSymbol(symbol: String) {
        val current = selectedSymbols.value.toMutableList()
        if (current.contains(symbol)) {
            current.remove(symbol)
        } else {
            current.add(symbol)
        }
        selectedSymbols.value = current
    }

    fun addStVwapTarget() {
        val current = stVwapTargets.value.toMutableList()
        current.add(TargetConfig(0.0, 0.0))
        stVwapTargets.value = current
    }

    fun updateStVwapTarget(index: Int, distance: Double, qty: Double) {
        val current = stVwapTargets.value.toMutableList()
        if (index in current.indices) {
            current[index] = TargetConfig(distance, qty)
            stVwapTargets.value = current
        }
    }

    fun removeStVwapTarget(index: Int) {
        val current = stVwapTargets.value.toMutableList()
        if (index in current.indices) {
            current.removeAt(index)
            stVwapTargets.value = current
        }
    }

    fun addEmaTarget() {
        val current = emaTargets.value.toMutableList()
        current.add(TargetConfig(0.0, 0.0))
        emaTargets.value = current
    }

    fun updateEmaTarget(index: Int, distance: Double, qty: Double) {
        val current = emaTargets.value.toMutableList()
        if (index in current.indices) {
            current[index] = TargetConfig(distance, qty)
            emaTargets.value = current
        }
    }

    fun removeEmaTarget(index: Int) {
        val current = emaTargets.value.toMutableList()
        if (index in current.indices) {
            current.removeAt(index)
            emaTargets.value = current
        }
    }

    fun saveAutomation() {
        viewModelScope.launch {
            _saveState.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService ?: return@launch
                
                val riskMap = StrategyRiskMap(
                    vwapSupertrend = if (strategy.value == "VWAP_SUPERTREND" || strategy.value == "BOTH") {
                        StrategyRiskConfig(
                            timeframe = stVwapTimeframe.value,
                            hardStopPct = stVwapHardStopPct.value.toDoubleOrNull() ?: 1.0,
                            structuralStopPct = stVwapStructuralVwapPct.value.toDoubleOrNull() ?: 0.2, 
                            targets = stVwapTargets.value,
                            breakEvenAfterPartial = stVwapBreakEven.value,
                            trailingStop = if (stVwapTrailingEnabled.value) TrailingStopConfig(true, 1.0, stVwapTrailingTrailPct.value.toDoubleOrNull() ?: 0.8) else null
                        )
                    } else null,
                    emaCrossover = if (strategy.value == "EMA_CROSSOVER" || strategy.value == "BOTH") {
                        StrategyRiskConfig(
                            timeframe = emaTimeframe.value,
                            hardStopPct = emaHardStopPct.value.toDoubleOrNull() ?: 0.5,
                            structuralStopPct = emaStructuralPct.value.toDoubleOrNull() ?: 0.2,
                            reverseExit = emaReverseExit.value,
                            targets = emaTargets.value,
                            breakEvenAfterPartial = emaBreakEven.value,
                            trailingStop = if (emaTrailingEnabled.value) TrailingStopConfig(true, 1.0, emaTrailingTrailPct.value.toDoubleOrNull() ?: 0.5) else null
                        )
                    } else null
                )

                val mPct = if (isFixedMargin.value) null else (marginPct.value.toDoubleOrNull() ?: 45.0)
                val mFix = if (isFixedMargin.value) (marginPct.value.toDoubleOrNull() ?: 100.0) else null

                val scopeDto = SymbolScopeDto(
                    mode = symbolScope.value,
                    symbols = if (symbolScope.value == "ALL_WATCHLIST") emptyList() else selectedSymbols.value
                )

                val config = AutomationConfig(
                    strategy = strategy.value,
                    symbolScope = scopeDto,
                    symbols = if (symbolScope.value == "ALL_WATCHLIST") null else selectedSymbols.value,
                    direction = direction.value,
                    directionPreference = direction.value,
                    marginPct = mPct,
                    marginUsagePct = mPct,
                    fixedMargin = mFix,
                    marginUsdt = mFix,
                    leverage = leverage.value.toIntOrNull() ?: 15,
                    mode = _currentMode.value,
                    lifecycle = lifecycle.value,
                    vwapGateEnabled = vwapGateEnabled.value,
                    strategyRisk = riskMap,
                    strategyTimeframes = mapOf(
                        "VWAP_SUPERTREND" to stVwapTimeframe.value,
                        "EMA_CROSSOVER" to emaTimeframe.value
                    )
                )

                api.createAutomation(config)
                _saveState.value = UiState.Success(true)
                fetchAutomations()
                fetchCapacity()
            } catch (e: retrofit2.HttpException) {
                val errBody = e.response()?.errorBody()?.string()
                val parsedMsg = try {
                    val json = org.json.JSONObject(errBody ?: "")
                    json.optString("detail", e.message())
                } catch (_: Exception) {
                    errBody ?: e.message()
                }
                _saveState.value = UiState.Error(parsedMsg.ifBlank { "Deployment rejected by backend." })
            } catch (e: Exception) {
                _saveState.value = UiState.Error(e.message ?: "Save Failed")
            }
        }
    }

    fun toggleAutomationStatus(id: Long, currentStatus: String) {
        viewModelScope.launch {
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val newStatus = if (currentStatus == "ACTIVE") "PAUSED" else "ACTIVE"
                api.updateAutomation(id, mapOf("status" to newStatus))
                fetchAutomations()
                fetchCapacity()
            } catch (e: Exception) {
                _automations.value = UiState.Error("Failed to update status: ${e.message}")
            }
        }
    }

    fun setAutomationStatus(id: Long, newStatus: String) {
        viewModelScope.launch {
            try {
                val api = RetrofitClient.apiService ?: return@launch
                api.updateAutomation(id, mapOf("status" to newStatus))
                fetchAutomations()
                fetchCapacity()
            } catch (e: Exception) {
                _automations.value = UiState.Error("Failed to update status: ${e.message}")
            }
        }
    }

    fun deleteAutomation(id: Long) {
        viewModelScope.launch {
            try {
                val api = RetrofitClient.apiService ?: return@launch
                api.deleteAutomation(id)
                fetchAutomations()
                fetchCapacity()
            } catch (e: Exception) {
                _automations.value = UiState.Error("Failed to delete automation: ${e.message}")
            }
        }
    }

    private val _simState = MutableStateFlow<UiState<SimulateResponse>>(UiState.Idle)
    val simState = _simState.asStateFlow()

    fun simulateStrategy() {
        viewModelScope.launch {
            _simState.value = UiState.Loading
            try {
                val api = RetrofitClient.apiService ?: return@launch
                val slVal = hardStopPct.value.toDoubleOrNull() ?: (if (selectedTimeframe.value in listOf(3, 5)) 0.7 else 1.0)
                val trailVal = trailingTrailPct.value.toDoubleOrNull() ?: 0.5
                val req = mutableMapOf<String, Any>(
                    "strategies" to selectedStrategies.value.toList(),
                    "strategy" to (selectedStrategies.value.firstOrNull() ?: strategy.value),
                    "symbol" to (if (symbolScope.value == "SINGLE") selectedSymbols.value.firstOrNull() ?: "BTC-USDT" else symbolScope.value),
                    "symbols" to if (symbolScope.value == "ALL_WATCHLIST") listOf("ALL_WATCHLIST") else selectedSymbols.value,
                    "timeframes" to selectedTimeframes.value.toList(),
                    "timeframe" to "${selectedTimeframe.value}m",
                    "direction" to direction.value,
                    "sl_pct" to slVal,
                    "sl_preset_pct" to slVal,
                    "use_trailing" to trailingEnabled.value,
                    "trailing_pct" to trailVal,
                    "leverage" to (leverage.value.toDoubleOrNull() ?: 15.0),
                    "hours" to 96
                )

                val currentTargets = stVwapTargets.value
                if (currentTargets.isNotEmpty()) {
                    currentTargets.getOrNull(0)?.let { if (it.qtyPct > 0) req["tp1_pct"] = it.qtyPct }
                    currentTargets.getOrNull(1)?.let { if (it.qtyPct > 0) req["tp2_pct"] = it.qtyPct }
                    currentTargets.getOrNull(2)?.let { if (it.qtyPct > 0) req["tp3_pct"] = it.qtyPct }
                }

                if (isFixedMargin.value) {
                    req["fixed_margin"] = marginPct.value.toDoubleOrNull() ?: 100.0
                } else {
                    req["margin_pct"] = marginPct.value.toDoubleOrNull() ?: 45.0
                }

                val res = api.simulateAutomation(req)
                _simState.value = UiState.Success(res)
            } catch (e: Exception) {
                _simState.value = UiState.Error(e.message ?: "Simulation failed")
            }
        }
    }

    fun dismissSimulation() {
        _simState.value = UiState.Idle
    }

    fun resetSimState() {
        _simState.value = UiState.Idle
    }

    fun resetSaveState() {
        _saveState.value = UiState.Idle
    }
}
