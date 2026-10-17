package com.ophelia.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.RectangleShape
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.ophelia.app.auth.TokenManager
import com.ophelia.app.ui.screens.*
import com.ophelia.app.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OpheliaApp(tokenManager: TokenManager) {
    val navController = rememberNavController()
    val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)
    val scope = rememberCoroutineScope()

    val startDestination = if (tokenManager.getToken() != null) "home" else "login"

    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentDestination = navBackStackEntry?.destination

    // Exactly 4 primary bottom navigation tabs as mandated by spec
    val bottomNavTabs = listOf(
        Triple("home", "HOME", Icons.Filled.Home),
        Triple("ml", "Ophelia ML", Icons.Filled.Star),
        Triple("world", "WORLD", Icons.Filled.Place),
        Triple("autonomous_trading", "AUTO", Icons.Filled.PlayArrow)
    )
    val topLevelRoutes = listOf("home", "ml", "world", "autonomous_trading")
    val showBottomBar = currentDestination?.route in topLevelRoutes

    var systemMode by remember { mutableStateOf("SHADOW") }
    LaunchedEffect(Unit) {
        while (true) {
            try {
                val api = com.ophelia.app.network.RetrofitClient.apiService
                if (api != null) {
                    val res = api.getMode()
                    systemMode = res.mode.uppercase()
                }
            } catch (_: Exception) {}
            kotlinx.coroutines.delay(5000)
        }
    }

    ModalNavigationDrawer(
        drawerState = drawerState,
        gesturesEnabled = showBottomBar,
        drawerContent = {
            ModalDrawerSheet(
                drawerContainerColor = MaterialTheme.colorScheme.surface,
                drawerContentColor = MaterialTheme.colorScheme.onSurface,
                modifier = Modifier.width(300.dp)
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .statusBarsPadding()
                        .verticalScroll(rememberScrollState())
                        .padding(horizontal = 16.dp, vertical = 20.dp)
                ) {
                    // Drawer Header: Brand & Mode
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text(
                                text = "OPHELIA ADMIN",
                                style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.Black,
                                letterSpacing = 2.sp,
                                color = MaterialTheme.colorScheme.primary
                            )
                            Text(
                                text = "BingX Perpetual Swaps • Admin Core",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(6.dp))
                                .background(if (systemMode == "LIVE") Color(0x33E53935) else MaterialTheme.colorScheme.primaryContainer)
                                .padding(horizontal = 8.dp, vertical = 4.dp)
                        ) {
                            Text(
                                text = systemMode,
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.Bold,
                                color = if (systemMode == "LIVE") Color(0xFFE53935) else MaterialTheme.colorScheme.primary
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    // SECTION 1: TRADING
                    Text(
                        text = "TRADING",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary,
                        letterSpacing = 1.sp,
                        modifier = Modifier.padding(start = 12.dp, top = 4.dp, bottom = 2.dp)
                    )
                    val tradingItems = listOf(
                        Triple("autonomous_trading", "Autonomous Trading", Icons.Filled.PlayArrow),
                        Triple("us_market", "US Market Intelligence", Icons.Filled.Star),
                        Triple("market", "Market", Icons.Filled.List),
                        Triple("home", "Positions & Exposure", Icons.Filled.Home),
                        Triple("trade_history", "Position/History", Icons.Filled.DateRange),
                        Triple("risk", "Risk & Allocation", Icons.Filled.Lock)
                    )
                    tradingItems.forEach { (route, label, icon) ->
                        NavigationDrawerItem(
                            icon = { Icon(icon, contentDescription = label, modifier = Modifier.size(18.dp)) },
                            label = { Text(label, style = MaterialTheme.typography.bodyMedium) },
                            selected = currentDestination?.route == route,
                            onClick = {
                                scope.launch { drawerState.close() }
                                navController.navigate(route) { launchSingleTop = true }
                            },
                            modifier = Modifier.padding(vertical = 1.dp),
                            shape = RoundedCornerShape(8.dp)
                        )
                    }

                    Spacer(modifier = Modifier.height(10.dp))
                    Divider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.2f))

                    // SECTION 2: RESEARCH
                    Text(
                        text = "RESEARCH",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary,
                        letterSpacing = 1.sp,
                        modifier = Modifier.padding(start = 12.dp, top = 8.dp, bottom = 2.dp)
                    )
                    val researchItems = listOf(
                        Triple("analytics", "Order Flow Analytics", Icons.Filled.Info)
                    )
                    researchItems.forEach { (route, label, icon) ->
                        NavigationDrawerItem(
                            icon = { Icon(icon, contentDescription = label, modifier = Modifier.size(18.dp)) },
                            label = { Text(label, style = MaterialTheme.typography.bodyMedium) },
                            selected = currentDestination?.route == route,
                            onClick = {
                                scope.launch { drawerState.close() }
                                navController.navigate(route) { launchSingleTop = true }
                            },
                            modifier = Modifier.padding(vertical = 1.dp),
                            shape = RoundedCornerShape(8.dp)
                        )
                    }

                    Spacer(modifier = Modifier.height(10.dp))
                    Divider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.2f))

                    // SECTION 3: SYSTEM
                    Text(
                        text = "SYSTEM",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary,
                        letterSpacing = 1.sp,
                        modifier = Modifier.padding(start = 12.dp, top = 8.dp, bottom = 2.dp)
                    )
                    val systemItems = listOf(
                        Triple("god_eye", "God Eye", Icons.Filled.Info),
                        Triple("activity", "Notification Centre", Icons.Filled.Notifications),
                        Triple("system_control", "System Control", Icons.Filled.Lock),
                        Triple("engine_health", "Engine Health & Audit Logs", Icons.Filled.List)
                    )
                    systemItems.forEach { (route, label, icon) ->
                        NavigationDrawerItem(
                            icon = { Icon(icon, contentDescription = label, modifier = Modifier.size(18.dp)) },
                            label = { Text(label, style = MaterialTheme.typography.bodyMedium) },
                            selected = currentDestination?.route == route,
                            onClick = {
                                scope.launch { drawerState.close() }
                                navController.navigate(route) { launchSingleTop = true }
                            },
                            modifier = Modifier.padding(vertical = 1.dp),
                            shape = RoundedCornerShape(8.dp)
                        )
                    }

                    Spacer(modifier = Modifier.height(10.dp))
                    Divider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.2f))

                    // SECTION 5: ACCOUNT & SYSTEM
                    Text(
                        text = "ACCOUNT & FIRMWARE",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary,
                        letterSpacing = 1.sp,
                        modifier = Modifier.padding(start = 12.dp, top = 8.dp, bottom = 4.dp)
                    )
                    NavigationDrawerItem(
                        icon = { Icon(Icons.Filled.Settings, contentDescription = "Settings", modifier = Modifier.size(18.dp)) },
                        label = { Text("Account & API Keys", style = MaterialTheme.typography.bodyMedium) },
                        selected = currentDestination?.route == "account_api_keys",
                        onClick = {
                            scope.launch { drawerState.close() }
                            navController.navigate("account_api_keys") { launchSingleTop = true }
                        },
                        modifier = Modifier.padding(vertical = 1.dp),
                        shape = RoundedCornerShape(8.dp)
                    )
                    NavigationDrawerItem(
                        icon = { Icon(Icons.Filled.Share, contentDescription = "Download User Ophelia", modifier = Modifier.size(18.dp)) },
                        label = { Text("Download User Ophelia", style = MaterialTheme.typography.bodyMedium) },
                        selected = currentDestination?.route == "download_user_app",
                        onClick = {
                            scope.launch { drawerState.close() }
                            navController.navigate("download_user_app") { launchSingleTop = true }
                        },
                        modifier = Modifier.padding(vertical = 1.dp),
                        shape = RoundedCornerShape(8.dp)
                    )
                    NavigationDrawerItem(
                        icon = { Icon(Icons.Filled.Build, contentDescription = "Software Update", modifier = Modifier.size(18.dp)) },
                        label = { Text("Software Update", style = MaterialTheme.typography.bodyMedium) },
                        selected = currentDestination?.route == "software_update",
                        onClick = {
                            scope.launch { drawerState.close() }
                            navController.navigate("software_update") { launchSingleTop = true }
                        },
                        modifier = Modifier.padding(vertical = 1.dp),
                        shape = RoundedCornerShape(8.dp)
                    )
                    NavigationDrawerItem(
                        icon = { Icon(Icons.Filled.ExitToApp, contentDescription = "Sign Out", tint = MaterialTheme.colorScheme.error, modifier = Modifier.size(18.dp)) },
                        label = { Text("Sign Out", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold) },
                        selected = false,
                        onClick = {
                            scope.launch { drawerState.close() }
                            tokenManager.clearToken()
                            navController.navigate("login") {
                                popUpTo("home") { inclusive = true }
                            }
                        },
                        modifier = Modifier.padding(vertical = 1.dp),
                        shape = RoundedCornerShape(8.dp)
                    )
                    Spacer(modifier = Modifier.weight(1f, fill = false))
                    Spacer(modifier = Modifier.height(28.dp))
                    Box(
                        modifier = Modifier
                            .padding(start = 12.dp, bottom = 16.dp)
                            .size(46.dp)
                            .clip(CircleShape)
                            .background(Color(0xFF0C1017))
                            .border(1.dp, Color(0xFF1E2638), CircleShape)
                            .clickable {
                                scope.launch { drawerState.close() }
                            },
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Filled.Refresh,
                            contentDescription = "Sync",
                            tint = Color.White,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                }
            }
        }
    ) {
        Scaffold(
            containerColor = MaterialTheme.colorScheme.background,
            topBar = {
                if (showBottomBar) {
                    TopAppBar(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(
                                Brush.verticalGradient(
                                    listOf(
                                        Color(0xCC050A18), // deep cosmic nebula ~60-80%
                                        Color(0x990A1128),
                                        Color(0x44080D1D),
                                        Color.Transparent   // seamless fade into app body, no rectangular image border
                                    )
                                )
                            ),
                        title = {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(12.dp)
                            ) {
                                Column {
                                    Text(
                                        text = "OPHELIA",
                                        style = EpicProHeaderStyle.copy(
                                            fontSize = 18.sp,
                                            letterSpacing = 2.8.sp,
                                            fontWeight = FontWeight.Medium
                                        ),
                                        color = Color(0xFFF1F5F9)
                                    )
                                    Text(
                                        text = "ML & INTELLIGENCE",
                                        style = EpicProBadgeStyle.copy(
                                            fontSize = 8.5.sp,
                                            letterSpacing = 1.8.sp,
                                            fontWeight = FontWeight.Bold
                                        ),
                                        color = Color(0xFF94A3B8)
                                    )
                                }
                                // Liquid Glass Capsule Status Pill (Image 4)
                                Box(
                                    modifier = Modifier
                                        .clip(RoundedCornerShape(20.dp))
                                        .background(
                                            Brush.horizontalGradient(
                                                listOf(
                                                    Color(0x3338BDF8),
                                                    Color(0x1A818CF8),
                                                    Color(0x3338BDF8)
                                                )
                                            )
                                        )
                                        .border(
                                            width = 1.dp,
                                            brush = Brush.linearGradient(
                                                listOf(
                                                    Color(0x66FFFFFF),
                                                    Color(0x2238BDF8),
                                                    Color(0x44FFFFFF)
                                                )
                                            ),
                                            shape = RoundedCornerShape(20.dp)
                                        )
                                        .padding(horizontal = 10.dp, vertical = 4.dp)
                                ) {
                                    Text(
                                        text = systemMode,
                                        style = MaterialTheme.typography.labelSmall,
                                        fontWeight = FontWeight.Bold,
                                        color = if (systemMode == "LIVE") Color(0xFFE53935) else Color(0xFF38BDF8),
                                        fontSize = 10.sp,
                                        letterSpacing = 1.2.sp
                                    )
                                }
                            }
                        },
                        navigationIcon = {
                            IconButton(onClick = { scope.launch { drawerState.open() } }) {
                                Icon(Icons.Filled.Menu, contentDescription = "Open Drawer", tint = Color.White)
                            }
                        },
                        actions = {},
                        colors = TopAppBarDefaults.topAppBarColors(
                            containerColor = Color.Transparent,
                            titleContentColor = Color.White
                        )
                    )
                }
            },
            bottomBar = {
                if (showBottomBar) {
                    Surface(
                        modifier = Modifier
                            .fillMaxWidth()
                            .navigationBarsPadding()
                            .border(
                                width = 1.dp,
                                brush = Brush.verticalGradient(
                                    listOf(MaterialTheme.colorScheme.outline.copy(alpha = 0.4f), Color.Transparent)
                                ),
                                shape = RectangleShape
                            ),
                        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.95f),
                        tonalElevation = 2.dp
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 12.dp, vertical = 8.dp),
                            horizontalArrangement = Arrangement.SpaceAround,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            bottomNavTabs.forEach { (route, label, icon) ->
                                val isSelected = currentDestination?.hierarchy?.any { it.route == route } == true
                                Box(
                                    modifier = Modifier
                                        .weight(1f)
                                        .padding(horizontal = 4.dp)
                                        .clip(RoundedCornerShape(12.dp))
                                        .then(
                                            if (isSelected) {
                                                Modifier
                                                    .background(
                                                        Brush.verticalGradient(
                                                            listOf(
                                                                MaterialTheme.colorScheme.primary.copy(alpha = 0.22f),
                                                                MaterialTheme.colorScheme.primary.copy(alpha = 0.08f)
                                                            )
                                                        )
                                                    )
                                                    .border(
                                                        width = 1.5.dp,
                                                        brush = Brush.verticalGradient(
                                                            listOf(
                                                                MaterialTheme.colorScheme.primary.copy(alpha = 0.90f),
                                                                MaterialTheme.colorScheme.primary.copy(alpha = 0.50f)
                                                            )
                                                        ),
                                                        shape = RoundedCornerShape(12.dp)
                                                    )
                                            } else {
                                                Modifier.background(Color.Transparent)
                                            }
                                        )
                                        .clickable(
                                            interactionSource = remember { MutableInteractionSource() },
                                            indication = null,
                                            onClick = {
                                                navController.navigate(route) {
                                                    popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                                                    launchSingleTop = true
                                                    restoreState = true
                                                }
                                            }
                                        )
                                        .padding(vertical = 8.dp),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Column(
                                        horizontalAlignment = Alignment.CenterHorizontally,
                                        verticalArrangement = Arrangement.spacedBy(3.dp)
                                    ) {
                                        Icon(
                                            imageVector = icon,
                                            contentDescription = label,
                                            modifier = Modifier.size(22.dp),
                                            tint = if (isSelected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                        Text(
                                            text = label,
                                            style = MaterialTheme.typography.labelSmall,
                                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                                            color = if (isSelected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                                            letterSpacing = 0.4.sp,
                                            fontSize = 11.sp,
                                            maxLines = 1
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }
        ) { innerPadding ->
            NavHost(
                navController = navController,
                startDestination = startDestination,
                modifier = Modifier.padding(innerPadding)
            ) {
                composable("login") {
                    LoginScreen(
                        onLoginSuccess = {
                            navController.navigate("home") {
                                popUpTo("login") { inclusive = true }
                            }
                        }
                    )
                }
                composable("home") {
                    HomeDashboardScreen(
                        onLogout = {
                            tokenManager.clearToken()
                            navController.navigate("login") {
                                popUpTo("home") { inclusive = true }
                            }
                        },
                        onNavigateToHistory = { navController.navigate("trade_history") },
                        onNavigateToRisk = { navController.navigate("risk") },
                        onNavigateToNews = { navController.navigate("world") },
                        onNavigateToActivity = { navController.navigate("activity") },
                        onNavigateToSymbol = { sym -> navController.navigate("symbol_detail/$sym") }
                    )
                }
                composable("market") {
                    DashboardScreen(
                        onLogout = {
                            tokenManager.clearToken()
                            navController.navigate("login") {
                                popUpTo("home") { inclusive = true }
                            }
                        },
                        onNavigateToSymbol = { symbol ->
                            navController.navigate("symbol_detail/$symbol")
                        }
                    )
                }
                composable("ml") {
                    MlScreen(
                        onBack = { navController.popBackStack() },
                        onNavigateToAutomationBuilder = {
                            navController.navigate("automation_builder")
                        },
                        onNavigateToReviewSetup = { setupId ->
                            navController.navigate("ml_review/$setupId")
                        },
                        onNavigateToBacktest = { setupId ->
                            navController.navigate("backtest?setupId=$setupId")
                        }
                    )
                }

                composable(
                    route = "ml_review/{setupId}",
                    arguments = listOf(navArgument("setupId") { type = NavType.StringType })
                ) { backStackEntry ->
                    val setupId = backStackEntry.arguments?.getString("setupId") ?: ""
                    MlSetupReviewScreen(
                        setupId = setupId,
                        onBack = { navController.popBackStack() },
                        onCreated = {
                            navController.navigate("automations") {
                                popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        }
                    )
                }
                composable("system_control") {
                    SystemControlCenterScreen(
                        onBack = { navController.popBackStack() },
                        onNavigateToAccountApiKeys = {
                            navController.navigate("account_api_keys") { launchSingleTop = true }
                        }
                    )
                }
                composable("account_api_keys") {
                    AccountApiKeysScreen(onBack = { navController.popBackStack() })
                }
                composable("world") {
                    WorldScreen(onBack = { navController.popBackStack() })
                }
                composable("automations") {
                    AutomationListScreen(
                        onNavigateToBuilder = {
                            navController.navigate("automation_builder")
                        },
                        onNavigateToMl = {
                            navController.navigate("ml") {
                                popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        }
                    )
                }
                composable("automation_builder") {
                    AutomationBuilderScreen(
                        viewModel = androidx.lifecycle.viewmodel.compose.viewModel(
                            factory = object : androidx.lifecycle.ViewModelProvider.Factory {
                                override fun <T : androidx.lifecycle.ViewModel> create(modelClass: Class<T>): T {
                                    return com.ophelia.app.ui.viewmodels.AutomationViewModel(tokenManager) as T
                                }
                            }
                        ),
                        onBack = { navController.popBackStack() }
                    )
                }
                composable(
                    route = "symbol_detail/{symbol}",
                    arguments = listOf(navArgument("symbol") { type = NavType.StringType })
                ) { backStackEntry ->
                    val symbol = backStackEntry.arguments?.getString("symbol") ?: ""
                    SymbolDetailScreen(
                        symbol = symbol,
                        onBack = { navController.popBackStack() }
                    )
                }
                composable(
                    route = "backtest?setupId={setupId}",
                    arguments = listOf(navArgument("setupId") {
                        type = NavType.StringType
                        nullable = true
                        defaultValue = null
                    })
                ) { backStackEntry ->
                    val setupId = backStackEntry.arguments?.getString("setupId")
                    BacktestScreen(
                        initialSetupId = setupId,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable("trade_history") {
                    TradeHistoryScreen(onBack = { navController.popBackStack() })
                }
                composable("analytics") {
                    AnalyticsScreen(onBack = { navController.popBackStack() })
                }
                composable("risk") {
                    RiskScreen(onBack = { navController.popBackStack() })
                }
                composable("news") {
                    NewsScreen(onBack = { navController.popBackStack() })
                }
                composable("activity") {
                    NotificationCentreScreen(onBack = { navController.popBackStack() })
                }
                composable("notifications") {
                    NotificationCentreScreen(onBack = { navController.popBackStack() })
                }
                composable("god_eye") {
                    GodEyeScreen(onBack = { navController.popBackStack() })
                }
                composable("download_user_app") {
                    DownloadUserAppScreen(onBack = { navController.popBackStack() })
                }
                composable("engine_health") {
                    EngineHealthAuditScreen(onBack = { navController.popBackStack() })
                }
                composable("software_update") {
                    UpdateAppScreen(onNavigateBack = { navController.popBackStack() })
                }
                composable("autonomous_trading") {
                    AutonomousTradingScreen(
                        onBack = { navController.popBackStack() },
                        isAdminRole = true
                    )
                }
                composable("us_market") {
                    UsMarketScreen(
                        onBack = { navController.popBackStack() },
                        onSelectStock = { sym -> navController.navigate("stock_dossier/$sym") },
                        isAdminRole = true
                    )
                }
                composable(
                    route = "stock_dossier/{symbol}",
                    arguments = listOf(navArgument("symbol") { type = NavType.StringType })
                ) { backStackEntry ->
                    val sym = backStackEntry.arguments?.getString("symbol") ?: "NVDA"
                    StockDetailDossierScreen(
                        symbol = sym,
                        onBack = { navController.popBackStack() },
                        isAdminRole = true
                    )
                }
                composable("settings") {
                    SettingsScreen(
                        onBack = { navController.popBackStack() },
                        onLogout = {
                            tokenManager.clearToken()
                            navController.navigate("login") {
                                popUpTo("home") { inclusive = true }
                            }
                        }
                    )
                }
            }
        }
    }
}
