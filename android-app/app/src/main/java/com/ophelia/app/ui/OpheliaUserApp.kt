package com.ophelia.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
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
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.ophelia.app.auth.TokenManager
import com.ophelia.app.network.RetrofitClient
import com.ophelia.app.ui.components.OpheliaGlassCard
import com.ophelia.app.ui.screens.*
import com.ophelia.app.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OpheliaUserApp(tokenManager: TokenManager) {
    val navController = rememberNavController()
    val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    val tokens = OpheliaThemeTokens.colors

    val startDestination = if (tokenManager.getToken() != null) "user_home" else "user_login"

    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentDestination = navBackStackEntry?.destination

    val bottomNavTabs = listOf(
        Triple("user_home", "HOME", Icons.Filled.Home),
        Triple("user_ml", "Ophelia ML", Icons.Filled.Star),
        Triple("user_world", "WORLD", Icons.Filled.Place),
        Triple("user_autonomous_trading", "AUTO", Icons.Filled.PlayArrow)
    )
    val topLevelRoutes = listOf("user_home", "user_ml", "user_world", "user_autonomous_trading")
    val showBottomBar = currentDestination?.route in topLevelRoutes

    var systemMode by remember { mutableStateOf("SHADOW") }
    LaunchedEffect(Unit) {
        while (true) {
            try {
                val api = RetrofitClient.apiService
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
                    // Drawer Header
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text(
                                text = "OPHELIA USER",
                                style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.Black,
                                letterSpacing = 2.sp,
                                color = MaterialTheme.colorScheme.primary
                            )
                            Text(
                                text = "BingX Perpetual Swaps • Fleet Client",
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
                        Triple("user_autonomous_trading", "Autonomous Trading", Icons.Filled.PlayArrow),
                        Triple("user_us_market", "US Market Intelligence", Icons.Filled.Star),
                        Triple("user_market", "Market", Icons.Filled.List),
                        Triple("user_home", "Positions & Exposure", Icons.Filled.Home),
                        Triple("user_history", "Position/History", Icons.Filled.DateRange),
                        Triple("user_allocation", "Risk & Allocation", Icons.Filled.Lock)
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

                    // SECTION 2: INTELLIGENCE
                    Text(
                        text = "INTELLIGENCE",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary,
                        letterSpacing = 1.sp,
                        modifier = Modifier.padding(start = 12.dp, top = 6.dp, bottom = 2.dp)
                    )
                    val intelligenceItems = listOf(
                        Triple("user_ml", "Ophelia ML", Icons.Filled.Star),
                        Triple("user_world", "World", Icons.Filled.Place),
                        Triple("user_orderflow", "Order Flow Analytics", Icons.Filled.Share)
                    )
                    intelligenceItems.forEach { (route, label, icon) ->
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
                        modifier = Modifier.padding(start = 12.dp, top = 6.dp, bottom = 2.dp)
                    )
                    val systemItems = listOf(
                        Triple("user_copied_auto", "Copied Automations", Icons.Filled.PlayArrow),
                        Triple("user_system_control", "System Control", Icons.Filled.Settings),
                        Triple("user_engine_health", "Engine Health & Audit", Icons.Filled.CheckCircle),
                        Triple("user_notifications", "Notification Centre", Icons.Filled.Notifications),
                        Triple("user_bingx_setup", "Account & API", Icons.Filled.Person),
                        Triple("user_update", "Version & Update", Icons.Filled.Build)
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

                    Spacer(modifier = Modifier.weight(1f))
                    Spacer(modifier = Modifier.height(16.dp))

                    // Logout Button in Drawer Footer
                    NavigationDrawerItem(
                        icon = { Icon(Icons.Filled.ExitToApp, contentDescription = "Log Out", tint = BearishRed, modifier = Modifier.size(18.dp)) },
                        label = { Text("LOG OUT", color = BearishRed, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold) },
                        selected = false,
                        onClick = {
                            scope.launch { drawerState.close() }
                            tokenManager.clearToken()
                            navController.navigate("user_login") {
                                popUpTo(0) { inclusive = true }
                            }
                        },
                        modifier = Modifier.padding(vertical = 4.dp),
                        shape = RoundedCornerShape(8.dp)
                    )
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
                                        Color(0xCC050A18),
                                        Color(0x990A1128),
                                        Color(0x44080D1D),
                                        Color.Transparent
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
                                        text = "OPHELIA USER",
                                        style = EpicProHeaderStyle.copy(
                                            fontSize = 18.sp,
                                            letterSpacing = 2.8.sp,
                                            fontWeight = FontWeight.Medium
                                        ),
                                        color = Color.White
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
                composable("user_login") {
                    UserLoginScreen(
                        tokenManager = tokenManager,
                        onLoginSuccess = { bingxConnected ->
                            if (bingxConnected) {
                                navController.navigate("user_home") {
                                    popUpTo("user_login") { inclusive = true }
                                }
                            } else {
                                navController.navigate("user_bingx_setup") {
                                    popUpTo("user_login") { inclusive = true }
                                }
                            }
                        }
                    )
                }

                composable("user_home") {
                    UserHomeScreen(
                        tokenManager = tokenManager,
                        onNavigateToBingxSetup = { navController.navigate("user_bingx_setup") },
                        onNavigateToWorld = { navController.navigate("user_world") },
                        onNavigateToUpdate = { navController.navigate("user_update") },
                        onLogout = {
                            tokenManager.clearToken()
                            navController.navigate("user_login") {
                                popUpTo(0) { inclusive = true }
                            }
                        }
                    )
                }

                composable("user_bingx_setup") {
                    UserBingxSetupScreen(
                        onSetupComplete = {
                            navController.navigate("user_home") {
                                popUpTo("user_bingx_setup") { inclusive = true }
                            }
                        },
                        onBack = {
                            if (tokenManager.getToken() != null) {
                                navController.navigate("user_home")
                            } else {
                                navController.popBackStack()
                            }
                        }
                    )
                }

                composable("user_market") {
                    DashboardScreen(
                        onLogout = {
                            tokenManager.clearToken()
                            navController.navigate("user_login") { popUpTo(0) { inclusive = true } }
                        },
                        onNavigateToSymbol = { sym ->
                            navController.navigate("user_symbol_detail/$sym")
                        }
                    )
                }

                composable("user_history") {
                    TradeHistoryScreen(
                        onBack = { navController.popBackStack() }
                    )
                }

                composable("user_allocation") {
                    UserAllocationScreen(
                        onBack = { navController.popBackStack() }
                    )
                }

                composable("user_ml") {
                    MlScreen(
                        onBack = { navController.popBackStack() },
                        onNavigateToAutomationBuilder = {
                            // User app is read-only for builder; redirect to allocation
                            navController.navigate("user_allocation")
                        },
                        onNavigateToReviewSetup = { setupId ->
                            navController.navigate("user_ml_review/$setupId")
                        },
                        onNavigateToBacktest = { setupId ->
                            navController.navigate("user_backtest?setupId=$setupId")
                        }
                    )
                }

                composable(
                    route = "user_ml_review/{setupId}",
                    arguments = listOf(androidx.navigation.navArgument("setupId") { type = androidx.navigation.NavType.StringType })
                ) { backStackEntry ->
                    val setupId = backStackEntry.arguments?.getString("setupId") ?: ""
                    MlSetupReviewScreen(
                        setupId = setupId,
                        onBack = { navController.popBackStack() },
                        onCreated = {
                            navController.navigate("user_autonomous_trading") {
                                popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        }
                    )
                }

                composable("user_world") {
                    WorldScreen(
                        onBack = { navController.popBackStack() }
                    )
                }

                composable("user_copied_auto") {
                    UserCopiedAutomationsScreen(
                        onBack = { navController.popBackStack() },
                        onNavigateToAllocation = { navController.navigate("user_allocation") }
                    )
                }

                composable("user_system_control") {
                    UserSystemControlScreen(
                        onBack = { navController.popBackStack() }
                    )
                }

                composable("user_engine_health") {
                    UserEngineHealthScreen(
                        onBack = { navController.popBackStack() }
                    )
                }

                composable("user_notifications") {
                    UserNotificationsScreen(
                        onBack = { navController.popBackStack() }
                    )
                }

                composable("user_update") {
                    UpdateAppScreen(
                        onNavigateBack = { navController.popBackStack() }
                    )
                }

                composable("user_autonomous_trading") {
                    AutonomousTradingScreen(
                        onBack = { navController.popBackStack() },
                        isAdminRole = false
                    )
                }

                composable("user_us_market") {
                    UsMarketScreen(
                        onBack = { navController.popBackStack() },
                        onSelectStock = { sym -> navController.navigate("user_stock_dossier/$sym") },
                        isAdminRole = false
                    )
                }

                composable(
                    route = "user_stock_dossier/{symbol}",
                    arguments = listOf(androidx.navigation.navArgument("symbol") { type = androidx.navigation.NavType.StringType })
                ) { backStackEntry ->
                    val sym = backStackEntry.arguments?.getString("symbol") ?: "NVDA"
                    StockDetailDossierScreen(
                        symbol = sym,
                        onBack = { navController.popBackStack() },
                        isAdminRole = false
                    )
                }
            }
        }
    }
}
