package com.ophelia.app.network

import com.ophelia.app.models.*
import retrofit2.http.*

interface OpheliaApiService {

    // --- Auth ---
    @POST("/api/auth/login")
    suspend fun login(@Body request: Map<String, String>): LoginResponse

    @POST("/api/auth/register")
    suspend fun register(@Body request: Map<String, String>): LoginResponse

    // --- Accounts ---
    @GET("/api/accounts")
    suspend fun getAccounts(): AccountListResponse

    @GET("/api/accounts/{id}")
    suspend fun getAccountDetail(@Path("id") id: Long): Account

    @POST("/api/accounts")
    suspend fun addAccount(@Body request: Map<String, String>): GenericSuccessResponse

    @PATCH("/api/accounts/{id}")
    suspend fun updateAccount(@Path("id") id: Long, @Body request: Map<String, String>): GenericSuccessResponse

    @DELETE("/api/accounts/{id}")
    suspend fun deleteAccount(@Path("id") id: Long): GenericSuccessResponse

    @POST("/api/accounts/{id}/test")
    suspend fun testAccount(@Path("id") id: Long): GenericSuccessResponse

    // --- Market ---
    @GET("/api/market/contracts")
    suspend fun getContracts(): ContractsResponse

    @GET("/api/market/watchlist")
    suspend fun getWatchlist(): WatchlistResponse

    @POST("/api/market/watchlist")
    suspend fun addWatchlist(@Body request: Map<String, String>): GenericSuccessResponse

    @DELETE("/api/market/watchlist/{symbol}")
    suspend fun removeWatchlist(@Path("symbol") symbol: String): GenericSuccessResponse

    @GET("/api/market/snapshot/{symbol}")
    suspend fun getMarketSnapshot(
        @Path("symbol") symbol: String,
        @Query("tf") tf: String = "5"
    ): MarketSnapshotResponse

    @GET("/api/market/candles/{symbol}")
    suspend fun getCandles(
        @Path("symbol") symbol: String,
        @Query("tf") tf: String = "5m",
        @Query("limit") limit: Int = 100
    ): CandlesResponse

    // --- Automations ---
    @GET("/api/automations")
    suspend fun getAutomations(@Query("status") status: String? = null): AutomationsListResponse

    @POST("/api/automations")
    suspend fun createAutomation(@Body request: AutomationConfig): AutomationResponse

    @PATCH("/api/automations/{id}")
    suspend fun updateAutomation(
        @Path("id") id: Long,
        @Body request: Map<String, @JvmSuppressWildcards Any>
    ): GenericSuccessResponse

    @DELETE("/api/automations/{id}")
    suspend fun deleteAutomation(@Path("id") id: Long): GenericSuccessResponse

    @POST("/api/automations/simulate")
    suspend fun simulateAutomation(
        @Body request: Map<String, @JvmSuppressWildcards Any>
    ): SimulateResponse

    // --- Positions ---
    @GET("/api/positions")
    suspend fun getPositions(@Query("mode") mode: String? = null): PositionsResponse

    @POST("/api/positions/{id}/edit")
    suspend fun editPosition(@Path("id") id: String, @Body request: Map<String, @JvmSuppressWildcards Any>): GenericSuccessResponse

    @POST("/api/positions/{id}/partial-close")
    suspend fun partialClosePosition(@Path("id") id: String, @Body request: Map<String, @JvmSuppressWildcards Any>): GenericSuccessResponse

    @POST("/api/positions/{id}/close")
    suspend fun closePosition(@Path("id") id: String): GenericSuccessResponse

    @POST("/api/positions/reconcile")
    suspend fun reconcilePositions(): GenericSuccessResponse

    @POST("/api/risk/pause-all")
    suspend fun pauseAllAutomations(): GenericSuccessResponse

    @POST("/api/risk/emergency-close-all")
    suspend fun emergencyCloseAll(): GenericSuccessResponse

    // --- History & Analytics ---
    @GET("/api/trades/history")
    suspend fun getTradeHistory(
        @Query("page") page: Int = 1,
        @Query("limit") limit: Int = 50,
        @Query("symbol") symbol: String? = null,
        @Query("status") status: String? = null,
        @Query("mode") mode: String? = null
    ): TradeHistoryResponse

    @GET("/api/analytics/performance")
    suspend fun getAnalytics(@Query("days") days: Int = 30): AnalyticsResponse

    @GET("/api/audit/logs")
    suspend fun getAuditLogs(@Query("limit") limit: Int = 50): AuditLogsResponse

    // --- System & Control ---
    @GET("/api/mode/preflight")
    suspend fun getPreflight(): PreflightResponse

    @GET("/api/system/live-readiness")
    suspend fun getLiveReadiness(): PreflightResponse

    @GET("/api/mode")
    suspend fun getMode(): ModeStatusResponse

    @GET("/api/system/control")
    suspend fun getSystemControl(): SystemControlResponse

    @POST("/api/mode")
    suspend fun setMode(@Body request: SetModeRequest): ModeResponse

    @GET("/api/system/health/detailed")
    suspend fun getDetailedEngineHealth(): DetailedEngineHealthResponse

    @GET("/api/system/terminal-stream")
    suspend fun getTerminalStream(@Query("limit") limit: Int = 50): TerminalStreamResponse

    @GET("/api/system/audit-logs")
    suspend fun getSystemAuditLogs(
        @Query("limit") limit: Int = 50,
        @Query("offset") offset: Int = 0,
        @Query("component") component: String? = null
    ): SystemAuditLogsResponse

    @GET("/api/account/connection-status")
    suspend fun getBingxConnectionStatus(): BingxConnectionStatusResponse

    @POST("/api/account/connect")
    suspend fun connectBingx(): Map<String, Any>

    @POST("/api/account/disconnect")
    suspend fun disconnectBingx(): Map<String, Any>

    @POST("/api/account/refresh")
    suspend fun refreshBingxConnection(): BingxConnectionStatusResponse

    @POST("/api/account/credential-source")
    suspend fun setCredentialSource(@Body request: Map<String, String>): Map<String, Any>

    @POST("/api/account/credentials")
    suspend fun saveUserBingxCredentials(@Body request: Map<String, String>): Map<String, Any>

    @GET("/api/health")
    suspend fun getHealth(): Map<String, Any>

    @GET("/api/account/capacity")
    suspend fun getAccountCapacity(): AccountCapacity

    @POST("/api/system/settings/trade-cap")
    suspend fun setTradeCap(@Body request: Map<String, Int>): AccountCapacity


    @GET("/api/dashboard")
    suspend fun getDashboard(): DashboardResponse

    @GET("/api/news")
    suspend fun getNews(): NewsResponse

    @POST("/api/ask")
    suspend fun askOphelia(@Body request: Map<String, String>): AskResponse

    // --- Notifications ---
    @GET("/api/notifications")
    suspend fun getNotifications(
        @Query("category") category: String = "ALL",
        @Query("limit") limit: Int = 50,
        @Query("offset") offset: Int = 0
    ): NotificationsResponse

    @POST("/api/notifications/{id}/read")
    suspend fun markNotificationRead(@Path("id") id: Long): GenericSuccessResponse

    @POST("/api/notifications/read-all")
    suspend fun markAllNotificationsRead(): GenericSuccessResponse

    @POST("/api/notifications/clear")
    suspend fun clearAllNotifications(): GenericSuccessResponse

    @GET("/api/notifications/unread-count")
    suspend fun getUnreadNotificationCount(): UnreadCountResponse

    @GET("/api/notifications/settings")
    suspend fun getNotificationSettings(): NotificationSettingsDto

    @POST("/api/notifications/settings")
    suspend fun saveNotificationSettings(@Body request: NotificationSettingsDto): NotificationSettingsDto

    // --- ML & TradingAgents Advisory ---
    @GET("api/ml/state")
    suspend fun getMlState(@Query("symbol") symbol: String = "BTC-USDT"): MlStateDto

    @GET("/api/ml/intelligence")
    suspend fun getMlIntelligence(): MlIntelligenceResponse

    @GET("/api/ml/setups")
    suspend fun getMlSetups(
        @Query("symbol") symbol: String? = null,
        @Query("timeframe") timeframe: Int? = null
    ): SetupCandidatesResponse

    @GET("/api/ml/setup/{id}")
    suspend fun getMlSetupById(@Path("id") id: String): SetupCandidateDto

    @POST("/api/automations/from_setup")
    suspend fun createAutomationFromSetup(@Body request: Map<String, @JvmSuppressWildcards Any>): CreateAutomationFromSetupResponse

    // --- WORLD Macro Context & Interactive Map ---
    @GET("/api/world/context")
    suspend fun getWorldContext(): WorldContextDto

    @GET("/api/world/map")
    suspend fun getWorldMap(): WorldMapResponse

    @GET("/api/world/yahoo")
    suspend fun getWorldYahoo(): Map<String, Any>

    @GET("/api/news/categories")
    suspend fun getNewsCategories(): Map<String, List<WorldNewsItemDto>>

    @GET("/api/news/events")
    suspend fun getEconomicEvents(): List<EconomicEventDto>

    @GET("/api/news/trade-candidates")
    suspend fun getNewsTradeCandidates(): List<NewsTradeCandidateDto>

    @POST("/api/automations/from_news_setup")
    suspend fun createAutomationFromNewsSetup(@Body request: Map<String, @JvmSuppressWildcards Any>): CreateAutomationFromSetupResponse

    // --- 48-Hour Historical Backtest ---
    @GET("/api/backtest/48h")
    suspend fun get48hBacktest(): BacktestResponseDto

    @POST("/api/backtest/run")
    suspend fun runBacktest(@Body request: Map<String, @JvmSuppressWildcards Any> = emptyMap()): BacktestResponseDto

    // --- Daily Structural Bias ---
    @GET("/api/ml/daily-bias")
    suspend fun getDailyBias(): Map<String, Any>

    @GET("/api/ml/daily-bias/{symbol}")
    suspend fun getSymbolDailyBias(@Path("symbol") symbol: String): DailyStructuralBiasDto

    // --- Primary ML Setup Historical Replay ---
    @GET("/api/ml/setup/{setup_id}/replay")
    suspend fun getMlSetupReplay(
        @Path("setup_id") setupId: String,
        @Query("hours") hours: Int = 48
    ): MLHistoricalReplayDto

    @POST("/api/ml/setup/replay")
    suspend fun runMlSetupReplay(
        @Body request: Map<String, @JvmSuppressWildcards Any>
    ): MLHistoricalReplayDto

    // --- God Eye Fleet Monitoring & Control (Admin Only) ---
    @GET("/api/admin/god-eye/overview")
    suspend fun getGodEyeOverview(): GodEyeOverviewResponse

    @POST("/api/admin/god-eye/close-position")
    suspend fun closeUserPosition(@Body req: Map<String, @JvmSuppressWildcards Any>): Map<String, Any>

    @POST("/api/admin/god-eye/flash-close-all")
    suspend fun flashCloseAll(@Body req: Map<String, @JvmSuppressWildcards Any>): Map<String, Any>

    @POST("/api/admin/users/{userId}/copy-permission")
    suspend fun setUserCopyPermission(
        @Path("userId") userId: Long,
        @Body req: Map<String, @JvmSuppressWildcards Any>
    ): Map<String, Any>

    @POST("/api/admin/users/{userId}/suspend")
    suspend fun setUserSuspension(
        @Path("userId") userId: Long,
        @Body req: Map<String, @JvmSuppressWildcards Any>
    ): Map<String, Any>

    @GET("/api/system/user-app-metadata")
    suspend fun getUserAppMetadata(): UserAppMetadataResponse

    // --- User App Endpoints (com.ophelia.user) ---
    @POST("/api/auth/google")
    suspend fun googleAuth(@Body req: Map<String, @JvmSuppressWildcards Any>): GoogleAuthResponse

    @POST("/api/user/bingx-credentials")
    suspend fun saveUserBingxCredentialsDirect(@Body req: Map<String, @JvmSuppressWildcards Any>): Map<String, Any>

    @GET("/api/user/bingx-status")
    suspend fun getUserBingxStatus(): Map<String, Any>

    @POST("/api/user/bingx-disconnect")
    suspend fun disconnectUserBingx(): Map<String, Any>

    @POST("/api/user/copy-settings")
    suspend fun updateUserCopySettings(@Body req: Map<String, @JvmSuppressWildcards Any>): Map<String, Any>

    @GET("/api/user/dashboard")
    suspend fun getUserDashboard(): UserDashboardResponse

    @GET("/api/user/allocations")
    suspend fun getUserAllocations(): Map<String, Any>

    @POST("/api/user/allocations")
    suspend fun setUserAllocation(@Body req: Map<String, @JvmSuppressWildcards Any>): Map<String, Any>

    @GET("/api/user/system-control")
    suspend fun getUserSystemControl(): Map<String, Any>

    @GET("/api/user/health")
    suspend fun getUserEngineHealth(): Map<String, Any>

    @GET("/api/user/notifications")
    suspend fun getUserNotifications(@Query("category") category: String? = null): List<Map<String, Any>>

    @POST("/api/user/notifications/clear-all")
    suspend fun clearUserNotifications(): Map<String, Any>

    @POST("/api/user/notifications/{notif_id}/read")
    suspend fun markUserNotificationRead(@Path("notif_id") notifId: Int): Map<String, Any>

    // --- In-App Updates (Dual-Channel Admin & User) ---
    @GET("/api/system/app-version")
    suspend fun getAppVersion(@Query("channel") channel: String? = null): AppVersionResponse

    @Streaming
    @GET("/api/system/app-download")
    suspend fun downloadApk(@Query("channel") channel: String? = null): okhttp3.ResponseBody

    // --- Global Autonomous Trade Slots ---
    @GET("/api/autonomous/slots")
    suspend fun getAutonomousSlots(): AutonomousSlotsSummaryResponse

    @POST("/api/autonomous/slots")
    suspend fun createAutonomousSlot(@Body req: AddTradeSlotRequest): GenericSuccessResponse

    @PUT("/api/autonomous/slots/{id}")
    suspend fun updateAutonomousSlot(@Path("id") id: Int, @Body req: UpdateTradeSlotRequest): GenericSuccessResponse

    @DELETE("/api/autonomous/slots/{id}")
    suspend fun deleteAutonomousSlot(@Path("id") id: Int): GenericSuccessResponse

    @POST("/api/autonomous/toggle")
    suspend fun toggleAutonomousMaster(@Body req: ToggleAutonomousMasterRequest): GenericSuccessResponse

    @GET("/api/replication/status")
    suspend fun getReplicationStatus(): ReplicationStatusResponse

    @POST("/api/user/copy-settings")
    suspend fun updateUserCopySettings(@Body req: UserCopySettingsRequest): Map<String, Any>

    // --- Slot Templates & Pipeline Diagnostics ---
    @GET("/api/user/slot-template")
    suspend fun getUserSlotTemplate(@Query("asset_class") assetClass: String = "CRYPTO"): UserSlotTemplateResponse

    @POST("/api/user/slot-template")
    suspend fun setUserSlotTemplate(@Body req: UserSlotTemplateDto): GenericSuccessResponse

    @GET("/api/admin/diagnostics/automation-pipeline")
    suspend fun getAutomationPipelineDiagnostics(): AutomationPipelineDiagnosticsResponse

    @POST("/api/admin/slots/recover-stale")
    suspend fun recoverStaleReservations(): RecoverStaleReservationsResponse

    // --- US Market Subsystem ---
    @GET("/api/us/overview")
    suspend fun getUsMarketOverview(): UsMarketOverviewResponse

    @GET("/api/us/top100")
    suspend fun getUsTop100(): UsTop100Response

    @GET("/api/us/stock/{symbol}")
    suspend fun getUsStockDossier(@Path("symbol") symbol: String): UsStockDossier

    @GET("/api/us/sectors")
    suspend fun getUsSectors(): UsSectorsResponse

    @GET("/api/us/news")
    suspend fun getUsNews(@Query("limit") limit: Int = 50): UsNewsResponse

    @GET("/api/us/overnight")
    suspend fun getUsOvernight(): UsOvernightResponse

    @GET("/api/us/opportunities")
    suspend fun getUsOpportunities(): UsOpportunitiesResponse

    @POST("/api/us/trade")
    suspend fun executeUsManualTrade(@Body req: UsManualTradeRequest): UsTradeResponse

    @GET("/api/us/movers")
    suspend fun getUsMarketMovers(@Query("limit") limit: Int = 10): UsMoversResponse

    @GET("/api/market/search")
    suspend fun searchMarket(@Query("q") query: String): MarketSearchResponse

    @POST("/api/orders/manual")
    suspend fun executeManualOrder(@Body req: ManualOrderRequest): ManualOrderResponse

    @POST("/api/admin/god-eye/purge-synthetic")
    suspend fun purgeSyntheticUsers(): Map<String, Any>
}




