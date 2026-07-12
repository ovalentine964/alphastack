# Alpha Stack — Mobile Application UI Architecture

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Mobile UI Architect  
> **Framework:** Flutter (Dart) · **Platforms:** Android + iOS (any phone)  
> **Scope:** Complete mobile UI architecture — dashboard, charts, trading, notifications, settings, agent monitoring, biometrics, offline mode, widgets, voice, low-data mode  
> **Design Philosophy:** Dark-first, one-thumb usable, information-dense yet uncluttered — a trading cockpit that fits in your pocket

---

## Table of Contents

1. [Design System & Foundations](#1-design-system--foundations)
2. [Application Architecture](#2-application-architecture)
3. [Navigation & Screen Map](#3-navigation--screen-map)
4. [Dashboard Layout (Simplified for Mobile)](#4-dashboard-layout-simplified-for-mobile)
5. [Chart Integration](#5-chart-integration)
6. [Quick Trade Execution](#6-quick-trade-execution)
7. [Push Notifications](#7-push-notifications)
8. [Settings UI](#8-settings-ui)
9. [Agent Monitoring (Simplified View)](#9-agent-monitoring-simplified-view)
10. [Biometric Authentication](#10-biometric-authentication)
11. [Dark Mode as Default](#11-dark-mode-as-default)
12. [Offline Mode](#12-offline-mode)
13. [Home Screen Widgets](#13-home-screen-widgets)
14. [Voice Commands](#14-voice-commands)
15. [Low Data Usage Mode](#15-low-data-usage-mode)
16. [Accessibility & Responsive Design](#16-accessibility--responsive-design)
17. [File & Directory Layout](#17-file--directory-layout)
18. [State Management & Data Flow](#18-state-management--data-flow)
19. [Performance Budget & Optimization](#19-performance-budget--optimization)
20. [Development Roadmap](#20-development-roadmap)

---

## 1. Design System & Foundations

### 1.1 Color Palette (Dark Mode Default)

```dart
// lib/theme/alpha_colors.dart

class AlphaColors {
  // Backgrounds — deep navy-black hierarchy
  static const Color bgPrimary    = Color(0xFF0A0E1A);  // Main background
  static const Color bgSecondary  = Color(0xFF111827);  // Card/panel background
  static const Color bgTertiary   = Color(0xFF1F2937);  // Elevated surfaces
  static const Color bgHover      = Color(0xFF283548);  // Interactive hover state

  // Text hierarchy
  static const Color textPrimary   = Color(0xFFF9FAFB);  // Headlines, prices
  static const Color textSecondary = Color(0xFF9CA3AF);  // Labels, descriptions
  static const Color textTertiary  = Color(0xFF6B7280);  // Hints, timestamps

  // Trading colors — universally understood
  static const Color bull    = Color(0xFF10B981);  // Green — profit, buy, long
  static const Color bear    = Color(0xFFEF4444);  // Red — loss, sell, short
  static const Color bullDim = Color(0xFF065F46);  // Muted green (backgrounds)
  static const Color bearDim = Color(0xFF7F1D1D);  // Muted red (backgrounds)

  // Accent colors
  static const Color accent       = Color(0xFF3B82F6);  // Primary action blue
  static const Color accentLight  = Color(0xFF60A5FA);  // Links, highlights
  static const Color warning      = Color(0xFFF59E0B);  // Caution, pending
  static const Color critical     = Color(0xFFDC2626);  // Alerts, margin call

  // Agent status colors
  static const Color agentOnline  = Color(0xFF10B981);  // Agent healthy
  static const Color agentWarning = Color(0xFFF59E0B);  // Agent degraded
  static const Color agentOffline = Color(0xFF6B7280);  // Agent disconnected
  static const Color agentError   = Color(0xFFEF4444);  // Agent failed

  // Signal confidence gradient
  static const List<Color> confidenceGradient = [
    Color(0xFFEF4444),  // 0-30% — Low (red)
    Color(0xFFF59E0B),  // 30-60% — Medium (amber)
    Color(0xFF10B981),  // 60-85% — High (green)
    Color(0xFF3B82F6),  // 85-100% — Very High (blue glow)
  ];
}
```

### 1.2 Typography Scale

```dart
// lib/theme/alpha_typography.dart

class AlphaTypography {
  // Font family — Inter for UI, JetBrains Mono for numbers
  static const String fontUI    = 'Inter';
  static const String fontMono  = 'JetBrains Mono';

  // Price display — monospace for alignment
  static const TextStyle priceLarge = TextStyle(
    fontFamily: fontMono,
    fontSize: 28,
    fontWeight: FontWeight.w700,
    letterSpacing: -0.5,
    height: 1.2,
  );

  static const TextStyle priceMedium = TextStyle(
    fontFamily: fontMono,
    fontSize: 18,
    fontWeight: FontWeight.w600,
    letterSpacing: -0.3,
  );

  static const TextStyle priceSmall = TextStyle(
    fontFamily: fontMono,
    fontSize: 14,
    fontWeight: FontWeight.w500,
  );

  // P&L display — colored dynamically
  static const TextStyle pnlDisplay = TextStyle(
    fontFamily: fontMono,
    fontSize: 20,
    fontWeight: FontWeight.w700,
    letterSpacing: -0.3,
  );

  // Labels and descriptions
  static const TextStyle labelLarge = TextStyle(
    fontFamily: fontUI,
    fontSize: 14,
    fontWeight: FontWeight.w600,
    letterSpacing: 0.2,
  );

  static const TextStyle bodyMedium = TextStyle(
    fontFamily: fontUI,
    fontSize: 14,
    fontWeight: FontWeight.w400,
    height: 1.5,
  );

  static const TextStyle caption = TextStyle(
    fontFamily: fontUI,
    fontSize: 12,
    fontWeight: FontWeight.w400,
    letterSpacing: 0.3,
  );
}
```

### 1.3 Spacing & Layout Grid

```dart
// lib/theme/alpha_spacing.dart

class AlphaSpacing {
  static const double xs  = 4;
  static const double sm  = 8;
  static const double md  = 12;
  static const double lg  = 16;
  static const double xl  = 24;
  static const double xxl = 32;

  // Card border radius
  static const double radiusSm  = 8;
  static const double radiusMd  = 12;
  static const double radiusLg  = 16;
  static const double radiusXl  = 24;  // Bottom sheets

  // Minimum touch target (WCAG + Apple HIG)
  static const double touchTarget = 44;
}
```

### 1.4 Animation Constants

```dart
// lib/theme/alpha_motion.dart

class AlphaMotion {
  static const Duration fast    = Duration(milliseconds: 150);  // Micro-interactions
  static const Duration normal  = Duration(milliseconds: 250);  // Page transitions
  static const Duration slow    = Duration(milliseconds: 400);  // Complex animations

  // Price flash animation duration
  static const Duration priceFlash = Duration(milliseconds: 600);

  // Chart update interval
  static const Duration chartTick = Duration(milliseconds: 100);

  // Spring curves for natural motion
  static const Curve springIn   = Curves.easeOutBack;
  static const Curve springOut  = Curves.easeInBack;
  static const Curve smooth     = Curves.easeInOut;
}
```

---

## 2. Application Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUTTER MOBILE APP                            │
│                                                                  │
│  ═══════════════════════════════════════════════════════════════  │
│  PRESENTATION LAYER                                              │
│  ═══════════════════════════════════════════════════════════════  │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐   │
│  │  Screens   │ │  Widgets   │ │  Charts    │ │  Sheets    │   │
│  │  (Pages)   │ │ (Reusable) │ │ (Custom)   │ │ (Modal)    │   │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘   │
│        └───────────────┴───────────────┴──────────────┘          │
│                           │                                      │
│  ═════════════════════════╪═════════════════════════════════════  │
│  STATE MANAGEMENT LAYER  │                                      │
│  ═════════════════════════╪═════════════════════════════════════  │
│  ┌───────────────────────┴───────────────────────────────────┐   │
│  │                    Riverpod Providers                      │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐ │   │
│  │  │ Market   │ │ Trading  │ │ Agent    │ │ Settings     │ │   │
│  │  │ State    │ │ State    │ │ State    │ │ State        │ │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘ │   │
│  └───────────────────────────────────────────────────────────┘   │
│                           │                                      │
│  ═════════════════════════╪═════════════════════════════════════  │
│  DOMAIN LAYER            │                                      │
│  ═════════════════════════╪═════════════════════════════════════  │
│  ┌───────────────────────┴───────────────────────────────────┐   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐ │   │
│  │  │ Trading  │ │ Signal   │ │ Risk     │ │ Portfolio    │ │   │
│  │  │ Service  │ │ Service  │ │ Service  │ │ Service      │ │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘ │   │
│  └───────────────────────────────────────────────────────────┘   │
│                           │                                      │
│  ═════════════════════════╪═════════════════════════════════════  │
│  DATA LAYER              │                                      │
│  ═════════════════════════╪═════════════════════════════════════  │
│  ┌───────────────────────┴───────────────────────────────────┐   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐ │   │
│  │  │ WebSocket│ │ REST API │ │ Isar DB  │ │ Secure       │ │   │
│  │  │ Client   │ │ Client   │ │ (Local)  │ │ Storage      │ │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘ │   │
│  └───────────────────────────────────────────────────────────┘   │
│                           │                                      │
│  ═════════════════════════╪═════════════════════════════════════  │
│  PLATFORM LAYER          │                                      │
│  ═════════════════════════╪═════════════════════════════════════  │
│  ┌───────────────────────┴───────────────────────────────────┐   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐ │   │
│  │  │ FCM/APNs │ │ Biometric│ │ Widgets  │ │ Voice/       │ │   │
│  │  │ Push     │ │ Auth     │ │ (Native) │ │ Speech       │ │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘ │   │
│  └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Package Dependencies

```yaml
# pubspec.yaml (key dependencies)

dependencies:
  # State Management
  flutter_riverpod: ^2.6.0
  riverpod_annotation: ^2.6.0

  # Navigation
  go_router: ^14.6.0

  # Networking
  web_socket_channel: ^3.0.0
  dio: ^5.7.0
  connectivity_plus: ^6.1.0

  # Local Storage
  isar: ^4.0.0
  flutter_secure_storage: ^9.2.0
  shared_preferences: ^2.3.0

  # Charts
  flutter_custom_paint: ^1.0.0  # Custom chart rendering
  webview_flutter: ^4.10.0      # TradingView Lightweight Charts fallback

  # Notifications
  firebase_messaging: ^15.1.0
  flutter_local_notifications: ^18.0.0

  # Biometrics
  local_auth: ^2.3.0

  # Voice
  speech_to_text: ^7.0.0
  flutter_tts: ^4.0.0

  # Widgets
  home_widget: ^0.7.0

  # UI
  flutter_animate: ^4.5.0
  shimmer: ^3.0.0
  cached_network_image: ^3.4.0
  flutter_slidable: ^3.1.0

  # Utilities
  intl: ^0.19.0
  uuid: ^4.5.0
  equatable: ^2.0.0
  freezed_annotation: ^2.4.0
  json_annotation: ^4.9.0
```

### 2.3 Core Provider Architecture

```dart
// lib/providers/app_providers.dart

// ── Connectivity ──
final connectivityProvider = StreamProvider<ConnectivityResult>((ref) {
  return Connectivity().onConnectivityChanged;
});

final isOnlineProvider = Provider<bool>((ref) {
  final connectivity = ref.watch(connectivityProvider);
  return connectivity.whenData((c) => c != ConnectivityResult.none) ?? true;
});

// ── Authentication ──
final authStateProvider = StateNotifierProvider<AuthStateNotifier, AuthState>((ref) {
  return AuthStateNotifier(ref);
});

final isBiometricEnabledProvider = FutureProvider<bool>((ref) async {
  final prefs = ref.watch(sharedPreferencesProvider);
  return prefs.getBool('biometric_enabled') ?? true;
});

// ── WebSocket ──
final webSocketProvider = StateNotifierProvider<WebSocketNotifier, WebSocketState>((ref) {
  return WebSocketNotifier(ref);
});

// ── Market Data ──
final priceStreamProvider = StreamProvider.family<PriceTick, String>((ref, symbol) {
  final ws = ref.watch(webSocketProvider.notifier);
  return ws.priceStream(symbol);
});

final watchlistProvider = StateNotifierProvider<WatchlistNotifier, List<String>>((ref) {
  return WatchlistNotifier(ref);
});

// ── Trading ──
final positionsProvider = StateNotifierProvider<PositionsNotifier, List<Position>>((ref) {
  return PositionsNotifier(ref);
});

final portfolioSummaryProvider = Provider<PortfolioSummary>((ref) {
  final positions = ref.watch(positionsProvider);
  return PortfolioSummary.fromPositions(positions);
});

// ── Agents ──
final agentStatusProvider = StreamProvider<List<AgentStatus>>((ref) {
  final ws = ref.watch(webSocketProvider.notifier);
  return ws.agentStatusStream();
});

// ── Settings ──
final settingsProvider = StateNotifierProvider<SettingsNotifier, AppSettings>((ref) {
  return SettingsNotifier(ref);
});

final lowDataModeProvider = Provider<bool>((ref) {
  return ref.watch(settingsProvider).lowDataMode;
});
```

---

## 3. Navigation & Screen Map

### 3.1 Navigation Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  ROOT NAVIGATION                         │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │              Shell (Bottom Nav Bar)               │   │
│  │                                                    │   │
│  │   ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐  │   │
│  │   │ 🏠   │ │ 📈   │ │ ⚡   │ │ 🤖   │ │ ⚙️   │  │   │
│  │   │ Home │ │Trade │ │Quick │ │Agent │ │Config│  │   │
│  │   └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘  │   │
│  │      │        │        │        │        │       │   │
│  │      ▼        ▼        ▼        ▼        ▼       │   │
│  │   ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐  │   │
│  │   │Dash- │ │Chart │ │Quick │ │Agent │ │Set-  │  │   │
│  │   │board │ │View  │ │Trade │ │Mon.  │ │tings │  │   │
│  │   └──────┘ └──┬───┘ └──────┘ └──┬───┘ └──┬───┘  │   │
│  │               │                  │        │       │   │
│  │          ┌────┴────┐        ┌───┴───┐ ┌──┴───┐   │   │
│  │          │Order    │        │Agent  │ │Broker│   │   │
│  │          │Entry    │        │Detail │ │Config│   │   │
│  │          └─────────┘        └───────┘ └──────┘   │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  OVERLAY SCREENS (modal/fullscreen):                     │
│  • Biometric Lock Screen                                 │
│  • Trade Confirmation Sheet                              │
│  • Signal Detail Sheet                                   │
│  • Notification Inbox                                    │
│  • Voice Command Overlay                                 │
│  • Offline Banner                                        │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Route Definitions

```dart
// lib/router/app_router.dart

final appRouter = GoRouter(
  initialLocation: '/dashboard',
  redirect: _authGuard,
  routes: [
    // Auth gate
    GoRoute(
      path: '/lock',
      builder: (context, state) => const BiometricLockScreen(),
    ),

    // Main shell with bottom navigation
    ShellRoute(
      builder: (context, state, child) => MainShell(child: child),
      routes: [
        // Tab 1: Dashboard
        GoRoute(
          path: '/dashboard',
          pageBuilder: (context, state) => const NoTransitionPage(
            child: DashboardScreen(),
          ),
          routes: [
            GoRoute(
              path: 'notifications',
              builder: (context, state) => const NotificationInboxScreen(),
            ),
          ],
        ),

        // Tab 2: Trade / Charts
        GoRoute(
          path: '/trade',
          pageBuilder: (context, state) => const NoTransitionPage(
            child: TradeScreen(),
          ),
          routes: [
            GoRoute(
              path: 'chart/:symbol',
              builder: (context, state) => ChartDetailScreen(
                symbol: state.pathParameters['symbol']!,
              ),
              routes: [
                GoRoute(
                  path: 'order',
                  builder: (context, state) => OrderEntryScreen(
                    symbol: state.pathParameters['symbol']!,
                  ),
                ),
              ],
            ),
          ],
        ),

        // Tab 3: Quick Trade
        GoRoute(
          path: '/quick',
          pageBuilder: (context, state) => const NoTransitionPage(
            child: QuickTradeScreen(),
          ),
        ),

        // Tab 4: Agent Monitor
        GoRoute(
          path: '/agents',
          pageBuilder: (context, state) => const NoTransitionPage(
            child: AgentMonitorScreen(),
          ),
          routes: [
            GoRoute(
              path: ':agentId',
              builder: (context, state) => AgentDetailScreen(
                agentId: state.pathParameters['agentId']!,
              ),
            ),
          ],
        ),

        // Tab 5: Settings
        GoRoute(
          path: '/settings',
          pageBuilder: (context, state) => const NoTransitionPage(
            child: SettingsScreen(),
          ),
          routes: [
            GoRoute(path: 'broker', builder: (c, s) => const BrokerConfigScreen()),
            GoRoute(path: 'strategy', builder: (c, s) => const StrategyConfigScreen()),
            GoRoute(path: 'notifications', builder: (c, s) => const NotificationSettingsScreen()),
            GoRoute(path: 'security', builder: (c, s) => const SecuritySettingsScreen()),
            GoRoute(path: 'data', builder: (c, s) => const DataUsageScreen()),
            GoRoute(path: 'about', builder: (c, s) => const AboutScreen()),
          ],
        ),
      ],
    ),
  ],
);
```

---

## 4. Dashboard Layout (Simplified for Mobile)

### 4.1 Dashboard Structure

The mobile dashboard prioritizes **glanceable information** — the user should understand their portfolio status within 2 seconds of opening the app.

```
┌─────────────────────────────────────────┐
│ STATUS BAR (system)                      │
├─────────────────────────────────────────┤
│ ┌─────────────────────────────────────┐ │
│ │ HEADER                              │ │
│ │ Alpha Stack        🔔 3   🟢 Live  │ │
│ │ Jul 11, 2026 21:47                 │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ ┌─────────────────────────────────────┐ │
│ │ PORTFOLIO SUMMARY CARD              │ │
│ │                                     │ │
│ │  Balance          Equity            │ │
│ │  $7.23           $7.18             │ │
│ │                                     │ │
│ │  Today's P&L      Open P&L         │ │
│ │  +$0.18          -$0.05           │ │
│ │  +2.55%           ▼0.70%          │ │
│ │                                     │ │
│ │  ┌───────────────────────────────┐ │ │
│ │  │ ▁▂▃▅▆▇▆▅▆▇█▇▆ (equity spark)│ │ │
│ │  └───────────────────────────────┘ │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ ┌─────────────────────────────────────┐ │
│ │ ACTIVE POSITIONS (horizontal scroll)│ │
│ │                                     │ │
│ │ ┌─────────┐ ┌─────────┐ ┌────────┐│ │
│ │ │ EUR/USD │ │ GBP/USD │ │ XAU/USD││ │
│ │ │ BUY     │ │ SELL    │ │ BUY    ││ │
│ │ │ 0.01 lot│ │ 0.01 lot│ │ 0.01   ││ │
│ │ │ +$0.12  │ │ -$0.08  │ │ +$0.03 ││ │
│ │ │ ▲ 12 pips││ ▼ 8 pips│ │ ▲ 3 pips││ │
│ │ └─────────┘ └─────────┘ └────────┘│ │
│ └─────────────────────────────────────┘ │
│                                         │
│ ┌─────────────────────────────────────┐ │
│ │ AI SIGNALS (latest 3)               │ │
│ │                                     │ │
│ │ 🟢 EUR/USD BUY   Confidence: 85%   │ │
│ │    Entry: 1.0845  SL: 1.0820       │ │
│ │    TP: 1.0900     2 min ago        │ │
│ │                      [BUY NOW →]    │ │
│ │                                     │ │
│ │ 🟡 USD/JPY WAIT   Confidence: 42%  │ │
│ │    Watching for SMC structure       │ │
│ │                                     │ │
│ │ 🔴 GBP/USD AVOID  Confidence: 91%  │ │
│ │    High impact news in 30 min       │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ ┌─────────────────────────────────────┐ │
│ │ AGENT HEALTH BAR                    │ │
│ │                                     │ │
│ │ 🟢 Orch 🟢 Fund 🟢 SMC 🟢 Risk    │ │
│ │ 🟢 Exec 🟢 Mon  🟡 Reﬂ 🟢 Jrnl   │ │
│ │                                     │ │
│ │ All agents nominal · 47 trades today│ │
│ └─────────────────────────────────────┘ │
│                                         │
│ ┌─────────────────────────────────────┐ │
│ │ QUICK WATCHLIST                     │ │
│ │                                     │ │
│ │ EUR/USD  1.0845  ▲ +0.12%          │ │
│ │ GBP/USD  1.2720  ▼ -0.08%          │ │
│ │ USD/JPY  149.85  ▲ +0.05%          │ │
│ │ XAU/USD  2385.40 ▲ +0.32%          │ │
│ │ BTC/USD  68420   ▼ -1.20%          │ │
│ └─────────────────────────────────────┘ │
│                                         │
├─────────────────────────────────────────┤
│  🏠      📈      ⚡      🤖      ⚙️    │
│  Home   Trade   Quick   Agents  Settings│
└─────────────────────────────────────────┘
```

### 4.2 Dashboard Screen Implementation

```dart
// lib/screens/dashboard/dashboard_screen.dart

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isOnline = ref.watch(isOnlineProvider);
    final portfolio = ref.watch(portfolioSummaryProvider);
    final positions = ref.watch(positionsProvider);
    final signals = ref.watch(activeSignalsProvider);
    final agents = ref.watch(agentStatusProvider);

    return Scaffold(
      body: CustomScrollView(
        physics: const BouncingScrollPhysics(),
        slivers: [
          // ── App Bar ──
          SliverAppBar(
            floating: true,
            title: const Text('Alpha Stack'),
            actions: [
              _ConnectionIndicator(isOnline: isOnline),
              _NotificationBell(ref: ref),
            ],
          ),

          // ── Offline Banner ──
          if (!isOnline)
            SliverToBoxAdapter(
              child: _OfflineBanner(),
            ),

          // ── Portfolio Summary Card ──
          SliverToBoxAdapter(
            child: PortfolioSummaryCard(
              portfolio: portfolio,
              onTap: () => context.push('/dashboard/portfolio'),
            ),
          ),

          // ── Active Positions (Horizontal) ──
          SliverToBoxAdapter(
            child: ActivePositionsCarousel(
              positions: positions,
              onPositionTap: (pos) => _showPositionSheet(context, pos),
            ),
          ),

          // ── AI Signals ──
          SliverToBoxAdapter(
            child: SignalsSection(
              signals: signals.take(3).toList(),
              onSignalTap: (signal) => _showSignalSheet(context, signal),
              onQuickTrade: (signal) => _executeQuickTrade(context, ref, signal),
            ),
          ),

          // ── Agent Health ──
          SliverToBoxAdapter(
            child: AgentHealthBar(
              agents: agents.whenData((a) => a) ?? [],
              onTap: () => context.go('/agents'),
            ),
          ),

          // ── Watchlist ──
          SliverToBoxAdapter(
            child: WatchlistSection(
              onPairTap: (symbol) => context.push('/trade/chart/$symbol'),
            ),
          ),

          // Bottom padding for nav bar
          const SliverToBoxAdapter(
            child: SizedBox(height: 100),
          ),
        ],
      ),
    );
  }
}
```

### 4.3 Portfolio Summary Card

```dart
// lib/widgets/portfolio_summary_card.dart

class PortfolioSummaryCard extends StatelessWidget {
  final PortfolioSummary portfolio;

  const PortfolioSummaryCard({required this.portfolio});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.all(AlphaSpacing.md),
      padding: const EdgeInsets.all(AlphaSpacing.lg),
      decoration: BoxDecoration(
        color: AlphaColors.bgSecondary,
        borderRadius: BorderRadius.circular(AlphaSpacing.radiusLg),
        border: Border.all(color: AlphaColors.bgTertiary, width: 1),
      ),
      child: Column(
        children: [
          // Balance & Equity row
          Row(
            children: [
              _MetricColumn(
                label: 'Balance',
                value: _formatCurrency(portfolio.balance),
                valueStyle: AlphaTypography.priceLarge.copyWith(
                  color: AlphaColors.textPrimary,
                ),
              ),
              const Spacer(),
              _MetricColumn(
                label: 'Equity',
                value: _formatCurrency(portfolio.equity),
                valueStyle: AlphaTypography.priceLarge.copyWith(
                  color: AlphaColors.textPrimary,
                ),
                crossAxisAlignment: CrossAxisAlignment.end,
              ),
            ],
          ),

          const SizedBox(height: AlphaSpacing.lg),

          // P&L row
          Row(
            children: [
              _PnLMetric(
                label: "Today's P&L",
                value: portfolio.dailyPnl,
                percent: portfolio.dailyPnlPercent,
              ),
              const Spacer(),
              _PnLMetric(
                label: 'Open P&L',
                value: portfolio.openPnl,
                percent: portfolio.openPnlPercent,
              ),
            ],
          ),

          const SizedBox(height: AlphaSpacing.md),

          // Equity sparkline
          SizedBox(
            height: 48,
            child: EquitySparkline(
              data: portfolio.equityHistory,
              color: portfolio.dailyPnl >= 0
                  ? AlphaColors.bull
                  : AlphaColors.bear,
            ),
          ),
        ],
      ),
    );
  }
}
```

---

## 5. Chart Integration

### 5.1 Dual-Strategy Chart Architecture

We use a **hybrid approach**: a custom Flutter `CustomPaint` engine for the primary chart (maximum performance, native feel) with a TradingView Lightweight Charts WebView fallback for advanced features.

```
┌─────────────────────────────────────────────────────────┐
│                 CHART RENDERING PIPELINE                  │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  PHASE 1: Custom Flutter Paint Engine (PRIMARY)      │ │
│  │                                                      │ │
│  │  CustomPaint widget → Dart Canvas API                │ │
│  │  ├── Candlestick rendering (60fps)                   │ │
│  │  ├── Volume bars                                     │ │
│  │  ├── SMA/EMA overlays                                │ │
│  │  ├── RSI/MACD sub-indicators                         │ │
│  │  ├── Support/Resistance lines                        │ │
│  │  ├── Order Block / FVG zones (SMC)                   │ │
│  │  └── Gesture handling (pinch-zoom, pan, crosshair)   │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  PHASE 2: TradingView Lightweight Charts (FALLBACK)  │ │
│  │                                                      │ │
│  │  WebView → TradingView Lightweight Charts JS         │ │
│  │  ├── 80+ built-in indicators                         │ │
│  │  ├── Professional drawing tools                      │ │
│  │  └── Used when: advanced analysis needed, or         │ │
│  │      custom engine can't render specific indicator   │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 5.2 Custom Chart Widget

```dart
// lib/widgets/charts/alpha_candlestick_chart.dart

class AlphaCandlestickChart extends StatefulWidget {
  final List<Candle> candles;
  final List<Indicator> overlays;
  final List<Indicator> subIndicators;
  final List<Zone> zones;         // Order blocks, FVG
  final List<Line> srLines;       // Support/Resistance
  final ValueChanged<Candle>? onCrosshair;
  final bool isRealtime;

  const AlphaCandlestickChart({
    required this.candles,
    this.overlays = const [],
    this.subIndicators = const [],
    this.zones = const [],
    this.srLines = const [],
    this.onCrosshair,
    this.isRealtime = true,
  });

  @override
  State<AlphaCandlestickChart> createState() => _AlphaCandlestickChartState();
}

class _AlphaCandlestickChartState extends State<AlphaCandlestickChart>
    with SingleTickerProviderStateMixin {
  
  late ChartController _controller;
  late AnimationController _animController;

  @override
  void initState() {
    super.initState();
    _controller = ChartController(
      candles: widget.candles,
      visibleCandles: 60,           // Show 60 candles by default
      candleWidth: 8.0,
      candleSpacing: 2.0,
    );
    _animController = AnimationController(
      vsync: this,
      duration: AlphaMotion.chartTick,
    );
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onScaleStart: _onScaleStart,
      onScaleUpdate: _onScaleUpdate,
      onScaleEnd: _onScaleEnd,
      onHorizontalDragUpdate: _onPanUpdate,
      onLongPressStart: _onCrosshairStart,
      onLongPressMoveUpdate: _onCrosshairUpdate,
      onLongPressEnd: _onCrosshairEnd,
      child: AnimatedBuilder(
        animation: _animController,
        builder: (context, child) {
          return CustomPaint(
            painter: CandlestickPainter(
              controller: _controller,
              overlays: widget.overlays,
              zones: widget.zones,
              srLines: widget.srLines,
              theme: Theme.of(context),
            ),
            size: Size.infinite,
          );
        },
      ),
    );
  }
}
```

### 5.3 Candlestick Painter

```dart
// lib/widgets/charts/painters/candlestick_painter.dart

class CandlestickPainter extends CustomPainter {
  final ChartController controller;
  final List<Indicator> overlays;
  final List<Zone> zones;
  final List<Line> srLines;
  final ThemeData theme;

  CandlestickPainter({
    required this.controller,
    required this.overlays,
    required this.zones,
    required this.srLines,
    required this.theme,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final chartArea = Rect.fromLTWH(
      0, 0,
      size.width,
      size.height * 0.7,  // 70% for candles, 30% for sub-indicator
    );

    final subArea = Rect.fromLTWH(
      0, size.height * 0.75,
      size.width,
      size.height * 0.25,
    );

    // 1. Draw background grid
    _drawGrid(canvas, chartArea);

    // 2. Draw price scale (right axis)
    _drawPriceScale(canvas, chartArea, size.width);

    // 3. Draw time scale (bottom axis)
    _drawTimeScale(canvas, subArea, size.height);

    // 4. Draw zones (order blocks, FVG)
    for (final zone in zones) {
      _drawZone(canvas, chartArea, zone);
    }

    // 5. Draw support/resistance lines
    for (final line in srLines) {
      _drawSRLine(canvas, chartArea, line);
    }

    // 6. Draw candlesticks
    for (int i = controller.firstVisibleIndex;
         i <= controller.lastVisibleIndex;
         i++) {
      _drawCandle(canvas, chartArea, controller.candles[i], i);
    }

    // 7. Draw overlays (SMA, EMA)
    for (final overlay in overlays) {
      _drawLineIndicator(canvas, chartArea, overlay);
    }

    // 8. Draw sub-indicator (RSI, MACD)
    if (controller.subIndicator != null) {
      _drawSubIndicator(canvas, subArea, controller.subIndicator!);
    }

    // 9. Draw crosshair (if active)
    if (controller.crosshairPosition != null) {
      _drawCrosshair(canvas, size, controller.crosshairPosition!);
    }

    // 10. Draw current price line
    _drawCurrentPriceLine(canvas, chartArea, size.width);
  }

  void _drawCandle(Canvas canvas, Rect area, Candle candle, int index) {
    final x = controller.candleToX(index);
    final isBull = candle.close >= candle.open;

    final bodyTop = controller.priceToY(candle.high, area);
    final bodyBottom = controller.priceToY(candle.low, area);
    final openY = controller.priceToY(candle.open, area);
    final closeY = controller.priceToY(candle.close, area);

    final color = isBull ? AlphaColors.bull : AlphaColors.bear;
    final bodyColor = isBull ? AlphaColors.bull : AlphaColors.bear;

    // Wick (thin vertical line)
    final wickPaint = Paint()
      ..color = color
      ..strokeWidth = 1.0;
    canvas.drawLine(
      Offset(x, bodyTop),
      Offset(x, bodyBottom),
      wickPaint,
    );

    // Body (thicker rectangle)
    final bodyRect = Rect.fromLTRB(
      x - controller.candleWidth / 2,
      openY,
      x + controller.candleWidth / 2,
      closeY,
    );
    final bodyPaint = Paint()
      ..color = isBull ? bodyColor.withOpacity(0.8) : bodyColor
      ..style = PaintingStyle.fill;
    canvas.drawRect(bodyRect, bodyPaint);
  }

  @override
  bool shouldRepaint(covariant CandlestickPainter oldDelegate) {
    return true; // Always repaint for real-time updates
  }
}
```

### 5.4 Chart Gesture Handling

```dart
// lib/widgets/charts/chart_controller.dart

class ChartController extends ChangeNotifier {
  List<Candle> candles;
  int visibleCandles;
  double candleWidth;
  double candleSpacing;
  double _scrollOffset = 0;
  double _scale = 1.0;
  Offset? crosshairPosition;
  Indicator? subIndicator;

  // ── Gesture Handlers ──

  void onScaleStart(ScaleStartDetails details) {
    _scaleStartCandleWidth = candleWidth;
    _scaleStartOffset = _scrollOffset;
  }

  void onScaleUpdate(ScaleUpdateDetails details) {
    // Pinch to zoom
    final newWidth = (_scaleStartCandleWidth * details.scale)
        .clamp(3.0, 24.0);
    if (newWidth != candleWidth) {
      candleWidth = newWidth;
      visibleCandles = (chartWidth / (candleWidth + candleSpacing)).floor();
      notifyListeners();
    }
  }

  void onPanUpdate(DragUpdateDetails details) {
    // Horizontal scroll
    final candleStep = candleWidth + candleSpacing;
    final deltaCandles = (-details.delta.dx / candleStep).round();
    _scrollOffset = (_scrollOffset + deltaCandles)
        .clamp(0, candles.length - visibleCandles);
    notifyListeners();
  }

  void onCrosshairUpdate(LongPressMoveUpdateDetails details) {
    final index = xToCandleIndex(details.localPosition.dx);
    if (index >= 0 && index < candles.length) {
      crosshairPosition = details.localPosition;
      notifyListeners();
    }
  }

  // ── Coordinate Transforms ──

  double priceToY(double price, Rect area) {
    final priceRange = visibleHigh - visibleLow;
    if (priceRange == 0) return area.center.dy;
    final normalized = (price - visibleLow) / priceRange;
    return area.bottom - (normalized * area.height);
  }

  double candleToX(int index) {
    final visibleIndex = index - firstVisibleIndex;
    return visibleIndex * (candleWidth + candleSpacing) + candleWidth / 2;
  }

  // ── Auto-scroll for real-time ──

  void appendTick(PriceTick tick) {
    final lastCandle = candles.last;
    if (tick.time.isAfter(lastCandle.time.add(const Duration(minutes: 1)))) {
      // New candle
      candles.add(Candle.fromTick(tick));
    } else {
      // Update current candle
      candles[candles.length - 1] = lastCandle.copyWith(
        high: math.max(lastCandle.high, tick.price),
        low: math.min(lastCandle.low, tick.price),
        close: tick.price,
        volume: lastCandle.volume + tick.volume,
      );
    }

    // Auto-scroll if at the end
    if (_scrollOffset >= candles.length - visibleCandles - 2) {
      _scrollOffset = (candles.length - visibleCandles).toDouble();
    }

    notifyListeners();
  }
}
```

### 5.5 Timeframe Selector

```dart
// lib/widgets/charts/timeframe_selector.dart

class TimeframeSelector extends StatelessWidget {
  final String selected;
  final ValueChanged<String> onSelected;

  static const timeframes = ['1m', '5m', '15m', '1H', '4H', '1D', '1W'];

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 36,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        itemCount: timeframes.length,
        padding: const EdgeInsets.symmetric(horizontal: AlphaSpacing.md),
        itemBuilder: (context, index) {
          final tf = timeframes[index];
          final isSelected = tf == selected;
          return Padding(
            padding: const EdgeInsets.only(right: AlphaSpacing.sm),
            child: ChoiceChip(
              label: Text(tf),
              selected: isSelected,
              onSelected: (_) => onSelected(tf),
              selectedColor: AlphaColors.accent,
              backgroundColor: AlphaColors.bgTertiary,
              labelStyle: TextStyle(
                color: isSelected ? Colors.white : AlphaColors.textSecondary,
                fontWeight: FontWeight.w600,
                fontSize: 12,
              ),
              showCheckmark: false,
              padding: const EdgeInsets.symmetric(horizontal: 8),
            ),
          );
        },
      ),
    );
  }
}
```

---

## 6. Quick Trade Execution

### 6.1 Quick Trade Actions

Quick trade provides **three entry points** for immediate execution without navigating deep into the app:

```
┌──────────────────────────────────────────────────────────┐
│              QUICK TRADE ENTRY POINTS                      │
│                                                           │
│  1. SWIPE ACTIONS (from Dashboard positions)              │
│  ┌───────────────────────────────────────────────┐       │
│  │  ← SLIDE LEFT →                               │       │
│  │                                               │       │
│  │  ┌─────────────────────────────────────────┐  │       │
│  │  │ EUR/USD BUY  0.01 lot   +$0.12         │  │       │
│  │  │ Entry: 1.0845  SL: 1.0820  TP: 1.0900  │  │       │
│  │  └─────────────────────────────────────────┘  │       │
│  │                                               │       │
│  │  ┌────────┐ ┌────────┐ ┌──────────────────┐  │       │
│  │  │ 🔒     │ │ ✏️     │ │ ❌               │  │       │
│  │  │ Close  │ │ Modify │ │ Close All        │  │       │
│  │  │ Profit │ │ SL/TP  │ │                  │  │       │
│  │  └────────┘ └────────┘ └──────────────────┘  │       │
│  └───────────────────────────────────────────────┘       │
│                                                           │
│  2. NOTIFICATION ACTIONS (from push notification)         │
│  ┌───────────────────────────────────────────────┐       │
│  │ 🔔 EUR/USD Signal: BUY at 1.0845             │       │
│  │    Confidence: 85% | SL: 1.0820 | TP: 1.0900 │       │
│  │                                               │       │
│  │    [ BUY NOW ]  [ VIEW CHART ]  [ DISMISS ]   │       │
│  └───────────────────────────────────────────────┘       │
│                                                           │
│  3. FLOATING ACTION BUTTON (always accessible)           │
│  ┌───────────────────────────────────────────────┐       │
│  │                                               │       │
│  │                           ┌─────┐             │       │
│  │                           │ ⚡  │ ← FAB       │       │
│  │                           └─────┘             │       │
│  │                                               │       │
│  │  Tap → Opens Quick Trade Bottom Sheet         │       │
│  │  Long Press → Last trade pair quick entry     │       │
│  └───────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────┘
```

### 6.2 Swipe Action Implementation

```dart
// lib/widgets/trading/position_card.dart

class PositionCard extends ConsumerWidget {
  final Position position;

  const PositionCard({required this.position});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Slidable(
      key: ValueKey(position.ticket),
      // Left swipe — Close at profit
      startActionPane: ActionPane(
        motion: const StretchMotion(),
        extentRatio: 0.4,
        children: [
          SlidableAction(
            onPressed: (_) => _closePosition(context, ref, position),
            backgroundColor: AlphaColors.bull,
            foregroundColor: Colors.white,
            icon: Icons.lock_outline,
            label: 'Close\nProfit',
            borderRadius: BorderRadius.circular(AlphaSpacing.radiusMd),
          ),
          SlidableAction(
            onPressed: (_) => _showModifySheet(context, ref, position),
            backgroundColor: AlphaColors.accent,
            foregroundColor: Colors.white,
            icon: Icons.edit_outlined,
            label: 'Modify',
            borderRadius: BorderRadius.circular(AlphaSpacing.radiusMd),
          ),
        ],
      ),

      // Right swipe — Emergency close all
      endActionPane: ActionPane(
        motion: const StretchMotion(),
        extentRatio: 0.3,
        children: [
          SlidableAction(
            onPressed: (_) => _closeAllPositions(context, ref),
            backgroundColor: AlphaColors.critical,
            foregroundColor: Colors.white,
            icon: Icons.close,
            label: 'Close\nAll',
            borderRadius: BorderRadius.circular(AlphaSpacing.radiusMd),
          ),
        ],
      ),

      // Card body
      child: _PositionCardBody(position: position),
    );
  }

  Future<void> _closePosition(
    BuildContext context, WidgetRef ref, Position position
  ) async {
    // Require biometric confirmation
    final authenticated = await _requireBiometric(context);
    if (!authenticated) return;

    // Show confirmation sheet
    final confirmed = await _showConfirmationSheet(
      context,
      title: 'Close Position',
      subtitle: '${position.symbol} ${position.direction}',
      pnl: position.unrealizedPnl,
    );

    if (confirmed) {
      await ref.read(tradingServiceProvider).closePosition(position.ticket);
    }
  }
}
```

### 6.3 Quick Trade Bottom Sheet

```dart
// lib/widgets/trading/quick_trade_sheet.dart

class QuickTradeSheet extends ConsumerStatefulWidget {
  final String initialSymbol;

  const QuickTradeSheet({this.initialSymbol = 'EUR/USD'});

  @override
  ConsumerState<QuickTradeSheet> createState() => _QuickTradeSheetState();
}

class _QuickTradeSheetState extends ConsumerState<QuickTradeSheet> {
  late String _symbol;
  TradeDirection _direction = TradeDirection.buy;
  double _lotSize = 0.01;
  double? _stopLoss;
  double? _takeProfit;

  @override
  Widget build(BuildContext context) {
    final price = ref.watch(priceStreamProvider(_symbol));

    return Container(
      padding: const EdgeInsets.all(AlphaSpacing.lg),
      decoration: const BoxDecoration(
        color: AlphaColors.bgSecondary,
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(AlphaSpacing.radiusXl),
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Drag handle
          Container(
            width: 40, height: 4,
            decoration: BoxDecoration(
              color: AlphaColors.textTertiary,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(height: AlphaSpacing.lg),

          // Symbol selector
          _SymbolPicker(
            selected: _symbol,
            onChanged: (s) => setState(() => _symbol = s),
          ),

          const SizedBox(height: AlphaSpacing.lg),

          // Live price display
          price.when(
            data: (tick) => _LivePriceDisplay(tick: tick),
            loading: () => const ShimmerBox(width: 200, height: 48),
            error: (e, _) => Text('Price unavailable',
              style: AlphaTypography.bodyMedium.copyWith(
                color: AlphaColors.textTertiary,
              ),
            ),
          ),

          const SizedBox(height: AlphaSpacing.lg),

          // Buy / Sell toggle
          _DirectionToggle(
            selected: _direction,
            onChanged: (d) => setState(() => _direction = d),
          ),

          const SizedBox(height: AlphaSpacing.lg),

          // Lot size stepper
          _LotSizeStepper(
            value: _lotSize,
            onChanged: (v) => setState(() => _lotSize = v),
            min: 0.01,
            max: 1.0,
            step: 0.01,
          ),

          const SizedBox(height: AlphaSpacing.md),

          // SL / TP (collapsible)
          _ExpandableSLTP(
            stopLoss: _stopLoss,
            takeProfit: _takeProfit,
            onChanged: (sl, tp) => setState(() {
              _stopLoss = sl;
              _takeProfit = tp;
            }),
          ),

          const SizedBox(height: AlphaSpacing.xl),

          // Execute button
          SizedBox(
            width: double.infinity,
            height: 56,
            child: ElevatedButton(
              onPressed: () => _executeTrade(context),
              style: ElevatedButton.styleFrom(
                backgroundColor: _direction == TradeDirection.buy
                    ? AlphaColors.bull
                    : AlphaColors.bear,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(AlphaSpacing.radiusMd),
                ),
              ),
              child: Text(
                '${_direction == TradeDirection.buy ? "BUY" : "SELL"} $_symbol',
                style: AlphaTypography.labelLarge.copyWith(
                  color: Colors.white,
                  fontSize: 16,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _executeTrade(BuildContext context) async {
    // 1. Require biometric
    final auth = await _requireBiometric(context);
    if (!auth) return;

    // 2. Execute
    final result = await ref.read(tradingServiceProvider).placeOrder(
      symbol: _symbol,
      direction: _direction,
      lotSize: _lotSize,
      stopLoss: _stopLoss,
      takeProfit: _takeProfit,
    );

    // 3. Feedback
    if (result.success) {
      HapticFeedback.heavyImpact();
      _showSuccessSnackBar(context, result);
    } else {
      HapticFeedback.vibrate();
      _showErrorSnackBar(context, result.error);
    }
  }
}
```

### 6.4 Trade Confirmation Sheet

```dart
// lib/widgets/trading/trade_confirmation_sheet.dart

class TradeConfirmationSheet extends StatelessWidget {
  final String symbol;
  final TradeDirection direction;
  final double lotSize;
  final double? stopLoss;
  final double? takeProfit;
  final double currentPrice;

  @override
  Widget build(BuildContext context) {
    final isBuy = direction == TradeDirection.buy;

    return Container(
      padding: const EdgeInsets.all(AlphaSpacing.xl),
      decoration: const BoxDecoration(
        color: AlphaColors.bgSecondary,
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(AlphaSpacing.radiusXl),
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Header
          Icon(
            isBuy ? Icons.trending_up : Icons.trending_down,
            size: 48,
            color: isBuy ? AlphaColors.bull : AlphaColors.bear,
          ),
          const SizedBox(height: AlphaSpacing.md),
          Text(
            '${isBuy ? "BUY" : "SELL"} $symbol',
            style: AlphaTypography.priceLarge.copyWith(
              color: isBuy ? AlphaColors.bull : AlphaColors.bear,
            ),
          ),

          const SizedBox(height: AlphaSpacing.xl),

          // Details grid
          _DetailRow('Entry Price', _formatPrice(currentPrice)),
          _DetailRow('Lot Size', _formatLot(lotSize)),
          if (stopLoss != null)
            _DetailRow('Stop Loss', _formatPrice(stopLoss!),
              valueColor: AlphaColors.bear),
          if (takeProfit != null)
            _DetailRow('Take Profit', _formatPrice(takeProfit!),
              valueColor: AlphaColors.bull),
          _DetailRow('Risk', _calculateRisk()),

          const SizedBox(height: AlphaSpacing.xl),

          // Confirm button
          SizedBox(
            width: double.infinity,
            height: 56,
            child: ElevatedButton(
              onPressed: () => Navigator.of(context).pop(true),
              style: ElevatedButton.styleFrom(
                backgroundColor: isBuy ? AlphaColors.bull : AlphaColors.bear,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(AlphaSpacing.radiusMd),
                ),
              ),
              child: const Text('Confirm Trade',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
            ),
          ),

          const SizedBox(height: AlphaSpacing.md),

          // Cancel
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: Text('Cancel',
              style: AlphaTypography.bodyMedium.copyWith(
                color: AlphaColors.textTertiary,
              )),
          ),
        ],
      ),
    );
  }
}
```

---

## 7. Push Notifications

### 7.1 Notification Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 PUSH NOTIFICATION FLOW                        │
│                                                              │
│  ┌──────────────────────┐                                    │
│  │ Alpha Stack Backend   │                                    │
│  │ (Rust + Python)       │                                    │
│  │                       │                                    │
│  │  Signal Generated ────┼──→ Push Service                   │
│  │  Trade Executed  ─────┼──→ (FCM + APNs)                  │
│  │  Risk Warning    ─────┼──→                                │
│  │  Agent Alert     ─────┼──→                                │
│  └──────────────────────┘         │                          │
│                                   ▼                          │
│              ┌────────────────────────────────┐              │
│              │   Firebase Cloud Messaging      │              │
│              │   (FCM for Android)             │              │
│              │   (APNs relay for iOS)          │              │
│              └───────────────┬────────────────┘              │
│                              │                               │
│              ┌───────────────┴────────────────┐              │
│              │   Flutter App (firebase_messaging)            │
│              │                                │              │
│              │  ┌──────────────────────────┐  │              │
│              │  │ Notification Service     │  │              │
│              │  │ ├── Foreground handler   │  │              │
│              │  │ ├── Background handler   │  │              │
│              │  │ ├── Terminated handler   │  │              │
│              │  │ └── Action handler       │  │              │
│              │  └──────────────────────────┘  │              │
│              └────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 Notification Categories & Channels

```dart
// lib/services/notification_service.dart

class NotificationService {
  // ── Android Notification Channels ──
  static const _tradeSignalsChannel = AndroidNotificationChannel(
    'trade_signals',
    'Trade Signals',
    description: 'AI trading signals with BUY/SELL recommendations',
    importance: Importance.max,
    playSound: true,
    enableVibration: true,
    vibrationPattern: Int64List.fromList([0, 200, 100, 200]),
    ledColor: AlphaColors.accent,
  );

  static const _tradeExecutionChannel = AndroidNotificationChannel(
    'trade_execution',
    'Trade Execution',
    description: 'Order fills, position closes, stop/limit triggers',
    importance: Importance.high,
    playSound: true,
  );

  static const _riskWarningsChannel = AndroidNotificationChannel(
    'risk_warnings',
    'Risk Warnings',
    description: 'Margin warnings, drawdown alerts, correlation alerts',
    importance: Importance.max,
    playSound: true,
    enableVibration: true,
    vibrationPattern: Int64List.fromList([0, 500, 200, 500]),
  );

  static const _agentAlertsChannel = AndroidNotificationChannel(
    'agent_alerts',
    'Agent Alerts',
    description: 'Agent health warnings, model confidence drops',
    importance: Importance.defaultImportance,
  );

  static const _systemChannel = AndroidNotificationChannel(
    'system',
    'System',
    description: 'Connection status, updates, maintenance',
    importance: Importance.low,
  );

  // ── Notification Payload Structure ──

  static Future<void> showTradeSignal({
    required String symbol,
    required String direction,
    required double confidence,
    required double entry,
    required double stopLoss,
    required double takeProfit,
  }) async {
    final notification = FlutterLocalNotificationsPlugin();

    // Android: BigTextStyle with action buttons
    final androidDetails = AndroidNotificationDetails(
      _tradeSignalsChannel.id,
      _tradeSignalsChannel.name,
      channelDescription: _tradeSignalsChannel.description,
      importance: _tradeSignalsChannel.importance,
      priority: Priority.max,
      category: AndroidNotificationCategory.message,
      fullScreenIntent: true,
      actions: [
        AndroidNotificationAction(
          'buy_now',
          'BUY NOW',
          icon: DrawableResourceAndroidBitmap('ic_buy'),
          contextual: true,
        ),
        AndroidNotificationAction(
          'view_chart',
          'VIEW CHART',
          icon: DrawableResourceAndroidBitmap('ic_chart'),
        ),
        AndroidNotificationAction(
          'dismiss',
          'DISMISS',
          cancelNotification: true,
        ),
      ],
    );

    // iOS: with action buttons
    final iosDetails = DarwinNotificationDetails(
      presentAlert: true,
      presentBadge: true,
      presentSound: true,
      categoryIdentifier: 'trade_signal',
    );

    await notification.show(
      symbol.hashCode,
      '🔔 $symbol Signal: $direction',
      'Confidence: ${(confidence * 100).toInt()}% | '
      'Entry: $entry | SL: $stopLoss | TP: $takeProfit',
      NotificationDetails(
        android: androidDetails,
        iOS: iosDetails,
      ),
      payload: jsonEncode({
        'type': 'trade_signal',
        'symbol': symbol,
        'direction': direction,
        'confidence': confidence,
        'entry': entry,
        'stopLoss': stopLoss,
        'takeProfit': takeProfit,
      }),
    );
  }

  // ── Background Message Handler ──

  @pragma('vm:entry-point')
  static Future<void> firebaseMessagingBackgroundHandler(
    RemoteMessage message
  ) async {
    // Process background notification
    // Store in local DB for notification inbox
    await _storeNotification(message);
  }
}
```

### 7.3 iOS Notification Actions Setup

```dart
// lib/services/ios_notification_actions.dart

Future<void> setupIOSCategories() async {
  final notification = FlutterLocalNotificationsPlugin();

  await notification
      .resolvePlatformSpecificImplementation<
          IOSFlutterLocalNotificationsPlugin>()
      ?.initialize(
        const DarwinInitializationSettings(
          requestAlertPermission: true,
          requestBadgePermission: true,
          requestSoundPermission: true,
          notificationCategories: [
            DarwinNotificationCategory(
              'trade_signal',
              actions: [
                DarwinNotificationAction.plain('buy_now', 'BUY NOW'),
                DarwinNotificationAction.plain('view_chart', 'VIEW CHART'),
                DarwinNotificationAction.destructive('dismiss', 'DISMISS'),
              ],
            ),
            DarwinNotificationCategory(
              'trade_execution',
              actions: [
                DarwinNotificationAction.plain('view_position', 'VIEW'),
              ],
            ),
            DarwinNotificationCategory(
              'risk_warning',
              actions: [
                DarwinNotificationAction.plain('acknowledge', 'ACKNOWLEDGE'),
                DarwinNotificationAction.destructive('close_all', 'CLOSE ALL'),
              ],
            ),
          ],
        ),
      );
}
```

### 7.4 Notification Inbox Screen

```dart
// lib/screens/notifications/notification_inbox_screen.dart

class NotificationInboxScreen extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notifications = ref.watch(notificationInboxProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Notifications'),
        actions: [
          TextButton(
            onPressed: () => ref.read(notificationInboxProvider.notifier).markAllRead(),
            child: const Text('Mark all read'),
          ),
        ],
      ),
      body: notifications.when(
        data: (items) => ListView.builder(
          itemCount: items.length,
          itemBuilder: (context, index) {
            final notif = items[index];
            return Dismissible(
              key: ValueKey(notif.id),
              onDismissed: (_) => _dismissNotification(ref, notif.id),
              background: Container(
                color: AlphaColors.bear,
                alignment: Alignment.centerRight,
                padding: const EdgeInsets.only(right: AlphaSpacing.lg),
                child: const Icon(Icons.delete, color: Colors.white),
              ),
              child: _NotificationTile(
                notification: notif,
                onTap: () => _handleNotificationTap(context, ref, notif),
              ),
            );
          },
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Error: $e')),
      ),
    );
  }
}
```

---

## 8. Settings UI

### 8.1 Settings Screen Layout

```
┌─────────────────────────────────────────┐
│ ⬅ Settings                              │
├─────────────────────────────────────────┤
│                                         │
│ BROKER CONNECTION                       │
│ ┌─────────────────────────────────────┐ │
│ │ 🟢 FXPesa — MT5 Connected          │ │
│ │ Account: 12345678                   │ │
│ │ Server: FXPesa-Live                 │ │
│ │ Balance: $7.23                      │ │
│ │                    [Configure →]    │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ STRATEGY CONFIGURATION                  │
│ ┌─────────────────────────────────────┐ │
│ │ Active Strategy: Alpha AlphaStack v1.0    │ │
│ │ Risk per trade: 2%                  │ │
│ │ Max open positions: 3               │ │
│ │ Trading pairs: EUR/USD, GBP/USD... │ │
│ │                    [Configure →]    │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ SECURITY                                │
│ ┌─────────────────────────────────────┐ │
│ │ 🔐 Biometric Lock        [✓ ON]    │ │
│ │ 🔑 Auto-lock timeout     [5 min ▾] │ │
│ │ 📱 Device Management     [→]       │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ NOTIFICATIONS                           │
│ ┌─────────────────────────────────────┐ │
│ │ 🔔 Trade Signals         [✓ ON]    │ │
│ │ 📊 Execution Alerts      [✓ ON]    │ │
│ │ ⚠️  Risk Warnings         [✓ ON]    │ │
│ │ 🤖 Agent Alerts          [✓ ON]    │ │
│ │ 📰 Market News           [✗ OFF]   │ │
│ │ 🔊 Sound               [✓ ON]     │ │
│ │ 📳 Vibration           [✓ ON]     │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ DATA & PERFORMANCE                      │
│ ┌─────────────────────────────────────┐ │
│ │ 📶 Low Data Mode         [✗ OFF]   │ │
│ │ 📊 Chart Quality         [High ▾]  │ │
│ │ 🔄 Update Frequency      [100ms ▾] │ │
│ │ 💾 Offline Data Size     [12 MB]   │ │
│ │                    [Clear Cache]    │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ APPEARANCE                              │
│ ┌─────────────────────────────────────┐ │
│ │ 🌙 Dark Mode             [System ▾]│ │
│ │ 📐 Compact Layout        [✗ OFF]   │ │
│ │ 🔤 Font Size             [Medium ▾] │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ ABOUT                                   │
│ ┌─────────────────────────────────────┐ │
│ │ Version 1.0.0 (build 42)           │ │
│ │ Terms of Service            [→]    │ │
│ │ Privacy Policy              [→]    │ │
│ │ Open Source Licenses        [→]    │ │
│ └─────────────────────────────────────┘ │
│                                         │
└─────────────────────────────────────────┘
```

### 8.2 Broker Configuration Screen

```dart
// lib/screens/settings/broker_config_screen.dart

class BrokerConfigScreen extends ConsumerStatefulWidget {
  @override
  ConsumerState<BrokerConfigScreen> createState() => _BrokerConfigScreenState();
}

class _BrokerConfigScreenState extends ConsumerState<BrokerConfigScreen> {
  final _formKey = GlobalKey<FormState>();
  late TextEditingController _loginController;
  late TextEditingController _serverController;
  bool _isConnecting = false;
  ConnectionStatus _status = ConnectionStatus.disconnected;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Broker Connection')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(AlphaSpacing.lg),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Connection status card
              _ConnectionStatusCard(status: _status),

              const SizedBox(height: AlphaSpacing.xl),

              // Broker type selector
              Text('Broker', style: AlphaTypography.labelLarge),
              const SizedBox(height: AlphaSpacing.sm),
              _BrokerSelector(
                selected: 'FXPesa',
                options: ['FXPesa', 'IC Markets', 'OANDA', 'Exness'],
              ),

              const SizedBox(height: AlphaSpacing.lg),

              // Login field
              Text('MT5 Login', style: AlphaTypography.labelLarge),
              const SizedBox(height: AlphaSpacing.sm),
              TextFormField(
                controller: _loginController,
                keyboardType: TextInputType.number,
                decoration: _inputDecoration('Enter your MT5 login number'),
                validator: (v) => v?.isEmpty ?? true ? 'Required' : null,
              ),

              const SizedBox(height: AlphaSpacing.lg),

              // Password field
              Text('Password', style: AlphaTypography.labelLarge),
              const SizedBox(height: AlphaSpacing.sm),
              TextFormField(
                obscureText: true,
                decoration: _inputDecoration('Enter your MT5 password'),
                validator: (v) => v?.isEmpty ?? true ? 'Required' : null,
              ),

              const SizedBox(height: AlphaSpacing.lg),

              // Server field
              Text('Server', style: AlphaTypography.labelLarge),
              const SizedBox(height: AlphaSpacing.sm),
              TextFormField(
                controller: _serverController,
                decoration: _inputDecoration('e.g., FXPesa-Live'),
                validator: (v) => v?.isEmpty ?? true ? 'Required' : null,
              ),

              const SizedBox(height: AlphaSpacing.xl),

              // Test connection button
              SizedBox(
                width: double.infinity,
                height: 52,
                child: OutlinedButton.icon(
                  onPressed: _isConnecting ? null : _testConnection,
                  icon: _isConnecting
                      ? const SizedBox(width: 20, height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.wifi_tethering),
                  label: Text(_isConnecting ? 'Connecting...' : 'Test Connection'),
                ),
              ),

              const SizedBox(height: AlphaSpacing.md),

              // Save button
              SizedBox(
                width: double.infinity,
                height: 52,
                child: ElevatedButton(
                  onPressed: _saveConfiguration,
                  child: const Text('Save Configuration'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
```

### 8.3 Strategy Configuration Screen

```dart
// lib/screens/settings/strategy_config_screen.dart

class StrategyConfigScreen extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final strategy = ref.watch(strategyConfigProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Strategy Configuration')),
      body: ListView(
        padding: const EdgeInsets.all(AlphaSpacing.lg),
        children: [
          // Strategy name
          _SectionHeader('Active Strategy'),
          _InfoTile(
            icon: Icons.psychology,
            title: strategy.name,
            subtitle: 'Version ${strategy.version}',
          ),

          const SizedBox(height: AlphaSpacing.xl),

          // Risk parameters
          _SectionHeader('Risk Management'),
          _SliderTile(
            label: 'Risk per Trade',
            value: strategy.riskPerTrade,
            min: 0.5,
            max: 5.0,
            step: 0.5,
            suffix: '%',
            onChanged: (v) => _updateStrategy(ref, 'riskPerTrade', v),
          ),
          _SliderTile(
            label: 'Max Open Positions',
            value: strategy.maxPositions.toDouble(),
            min: 1,
            max: 10,
            step: 1,
            suffix: '',
            onChanged: (v) => _updateStrategy(ref, 'maxPositions', v.toInt()),
          ),
          _SliderTile(
            label: 'Max Daily Drawdown',
            value: strategy.maxDailyDrawdown,
            min: 1.0,
            max: 10.0,
            step: 0.5,
            suffix: '%',
            onChanged: (v) => _updateStrategy(ref, 'maxDailyDrawdown', v),
          ),

          const SizedBox(height: AlphaSpacing.xl),

          // Trading pairs
          _SectionHeader('Trading Pairs'),
          ...strategy.pairs.map((pair) => SwitchListTile(
            title: Text(pair.symbol),
            subtitle: Text('${pair.pipValue} pip value'),
            value: pair.enabled,
            onChanged: (v) => _togglePair(ref, pair.symbol, v),
            activeColor: AlphaColors.bull,
          )),

          const SizedBox(height: AlphaSpacing.xl),

          // Agent configuration
          _SectionHeader('Agent Weights'),
          Text('Adjust how much each agent influences the final signal',
            style: AlphaTypography.caption.copyWith(
              color: AlphaColors.textTertiary,
            )),
          const SizedBox(height: AlphaSpacing.md),
          ...strategy.agentWeights.entries.map((e) => _SliderTile(
            label: e.key,
            value: e.value,
            min: 0.0,
            max: 1.0,
            step: 0.1,
            suffix: '',
            onChanged: (v) => _updateAgentWeight(ref, e.key, v),
          )),
        ],
      ),
    );
  }
}
```

---

## 9. Agent Monitoring (Simplified View)

### 9.1 Agent Monitor Screen

```
┌─────────────────────────────────────────┐
│ ⬅ Agent Monitor            🔄 Refresh  │
├─────────────────────────────────────────┤
│                                         │
│ SYSTEM STATUS: 🟢 ALL NOMINAL           │
│ Last pipeline run: 2 min ago            │
│ Decisions today: 47 | Signals: 12       │
│                                         │
│ ┌─────────────────────────────────────┐ │
│ │ ORCHESTRATOR                        │ │
│ │ 🟢 Online · Uptime: 14h 23m       │ │
│ │ Decisions routed: 47               │ │
│ │ Avg latency: 1.2s                  │ │
│ │ Last action: Routed BUY signal     │ │
│ │                      [Details →]   │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ ┌─────────────────────────────────────┐ │
│ │ ANALYSIS AGENTS                     │ │
│ │                                     │ │
│ │ 🟢 Fundamental    Latency: 0.8s    │ │
│ │ 🟢 Structure (SMC) Latency: 1.1s   │ │
│ │ 🟢 Liquidity      Latency: 0.6s    │ │
│ │ 🟢 SMC Detector   Latency: 1.4s    │ │
│ │ 🟢 Momentum       Latency: 0.3s    │ │
│ │ 🟢 Candlestick    Latency: 0.2s    │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ ┌─────────────────────────────────────┐ │
│ │ EXECUTION AGENTS                    │ │
│ │                                     │ │
│ │ 🟢 Signal Aggregator  Score: 78%   │ │
│ │ 🟢 Risk Gate          Approved: 42  │ │
│ │ 🟢 Entry Manager      Entries: 8    │ │
│ │ 🟢 Take-Profit Mgr    Exits: 5     │ │
│ │ 🟢 Execution Agent    Orders: 47   │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ ┌─────────────────────────────────────┐ │
│ │ SUPPORT AGENTS                      │ │
│ │                                     │ │
│ │ 🟢 Monitor        Alerts: 3        │ │
│ │ 🟡 Reflection     Last run: 6h ago │ │
│ │ 🟢 Journal        Entries: 12      │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ ┌─────────────────────────────────────┐ │
│ │ PIPELINE FLOW (Last Signal)         │ │
│ │                                     │ │
│ │ ┌───┐   ┌───┐   ┌───┐   ┌───┐    │ │
│ │ │Fun│──▶│SMC│──▶│RSI│──▶│Agg│    │ │
│ │ │85%│   │72%│   │68%│   │78%│    │ │
│ │ └───┘   └───┘   └───┘   └─┬─┘    │ │
│ │                            │       │ │
│ │ ┌───┐   ┌───┐   ┌───┐   ┌▼─┐    │ │
│ │ │Exe│◀──│Ent│◀──│TP │◀──│Rsk│    │ │
│ │ │ ✓ │   │ ✓ │   │ ✓ │   │ ✓ │    │ │
│ │ └───┘   └───┘   └───┘   └───┘    │ │
│ └─────────────────────────────────────┘ │
│                                         │
├─────────────────────────────────────────┤
│  🏠      📈      ⚡      🤖      ⚙️    │
└─────────────────────────────────────────┘
```

### 9.2 Agent Card Widget

```dart
// lib/widgets/agents/agent_card.dart

class AgentCard extends StatelessWidget {
  final AgentStatus agent;

  const AgentCard({required this.agent});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => context.push('/agents/${agent.id}'),
      child: Container(
        margin: const EdgeInsets.only(bottom: AlphaSpacing.sm),
        padding: const EdgeInsets.all(AlphaSpacing.md),
        decoration: BoxDecoration(
          color: AlphaColors.bgSecondary,
          borderRadius: BorderRadius.circular(AlphaSpacing.radiusMd),
          border: Border.all(
            color: _statusBorderColor(agent.status),
            width: agent.status == AgentStatusType.error ? 2 : 1,
          ),
        ),
        child: Row(
          children: [
            // Status indicator
            _StatusDot(status: agent.status),
            const SizedBox(width: AlphaSpacing.md),

            // Agent info
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    agent.displayName,
                    style: AlphaTypography.labelLarge.copyWith(
                      color: AlphaColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    agent.statusMessage,
                    style: AlphaTypography.caption.copyWith(
                      color: AlphaColors.textTertiary,
                    ),
                  ),
                ],
              ),
            ),

            // Metrics
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                if (agent.latencyMs != null)
                  Text(
                    '${agent.latencyMs}ms',
                    style: AlphaTypography.priceSmall.copyWith(
                      color: _latencyColor(agent.latencyMs!),
                    ),
                  ),
                if (agent.metric != null)
                  Text(
                    agent.metric!,
                    style: AlphaTypography.caption.copyWith(
                      color: AlphaColors.textSecondary,
                    ),
                  ),
              ],
            ),

            const SizedBox(width: AlphaSpacing.sm),
            Icon(
              Icons.chevron_right,
              color: AlphaColors.textTertiary,
              size: 20,
            ),
          ],
        ),
      ),
    );
  }

  Color _statusBorderColor(AgentStatusType status) {
    switch (status) {
      case AgentStatusType.online:
        return AlphaColors.agentOnline.withOpacity(0.3);
      case AgentStatusType.warning:
        return AlphaColors.agentWarning.withOpacity(0.5);
      case AgentStatusType.offline:
        return AlphaColors.agentOffline.withOpacity(0.3);
      case AgentStatusType.error:
        return AlphaColors.agentError.withOpacity(0.6);
    }
  }
}
```

### 9.3 Pipeline Flow Visualization

```dart
// lib/widgets/agents/pipeline_flow.dart

class PipelineFlow extends StatelessWidget {
  final List<PipelineStep> steps;

  const PipelineFlow({required this.steps});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AlphaSpacing.md),
      decoration: BoxDecoration(
        color: AlphaColors.bgSecondary,
        borderRadius: BorderRadius.circular(AlphaSpacing.radiusMd),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Pipeline Flow', style: AlphaTypography.labelLarge),
          const SizedBox(height: AlphaSpacing.md),

          // First row: Analysis agents
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: steps
                  .where((s) => s.type == PipelineStepType.analysis)
                  .expand((s) => [
                    _PipelineNode(step: s),
                    if (s != steps.where(
                      (s) => s.type == PipelineStepType.analysis).last)
                      _PipelineArrow(),
                  ])
                  .toList(),
            ),
          ),

          // Connector arrow down
          Center(
            child: RotatedBox(
              quarterTurns: 1,
              child: _PipelineArrow(),
            ),
          ),

          // Second row: Execution agents
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: steps
                  .where((s) => s.type == PipelineStepType.execution)
                  .expand((s) => [
                    _PipelineNode(step: s),
                    if (s != steps.where(
                      (s) => s.type == PipelineStepType.execution).last)
                      _PipelineArrow(),
                  ])
                  .toList(),
            ),
          ),
        ],
      ),
    );
  }
}

class _PipelineNode extends StatelessWidget {
  final PipelineStep step;

  const _PipelineNode({required this.step});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 64,
      padding: const EdgeInsets.symmetric(vertical: AlphaSpacing.sm),
      decoration: BoxDecoration(
        color: _stepColor(step.status).withOpacity(0.2),
        borderRadius: BorderRadius.circular(AlphaSpacing.radiusSm),
        border: Border.all(
          color: _stepColor(step.status),
          width: 1.5,
        ),
      ),
      child: Column(
        children: [
          Text(
            step.shortName,
            style: AlphaTypography.caption.copyWith(
              fontWeight: FontWeight.w700,
              color: _stepColor(step.status),
            ),
          ),
          if (step.score != null)
            Text(
              '${step.score}%',
              style: AlphaTypography.priceSmall.copyWith(
                color: _stepColor(step.status),
              ),
            ),
          Icon(
            step.status == PipelineStepStatus.completed
                ? Icons.check_circle
                : step.status == PipelineStepStatus.failed
                    ? Icons.cancel
                    : Icons.circle_outlined,
            size: 14,
            color: _stepColor(step.status),
          ),
        ],
      ),
    );
  }
}
```

---

## 10. Biometric Authentication

### 10.1 Authentication Flow

```
┌─────────────────────────────────────────────────────────────┐
│                BIOMETRIC AUTHENTICATION FLOW                  │
│                                                              │
│  App Launch / Resume from Background (>5 min)                │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────────┐                                    │
│  │ Biometric available?│                                    │
│  └──────┬──────┬───────┘                                    │
│         │      │                                            │
│        YES     NO                                           │
│         │      │                                            │
│         ▼      ▼                                            │
│  ┌──────────┐ ┌──────────┐                                  │
│  │ Show     │ │ Show PIN │                                  │
│  │ Face ID /│ │ Entry    │                                  │
│  │ Touch ID │ │ Screen   │                                  │
│  └────┬─────┘ └────┬─────┘                                  │
│       │             │                                       │
│       ▼             ▼                                       │
│  ┌─────────────────────┐                                    │
│  │   Authenticated?    │                                    │
│  └──────┬──────┬───────┘                                    │
│        YES     NO                                           │
│         │      │                                            │
│         ▼      ▼                                            │
│  ┌──────────┐ ┌──────────┐                                  │
│  │ Show     │ │ Show     │                                  │
│  │ Main App │ │ Error +  │                                  │
│  │          │ │ Retry    │                                  │
│  └──────────┘ └──────────┘                                  │
│                                                              │
│  AUTH LEVELS:                                                │
│  • View prices/dashboard → No auth needed (quick view)       │
│  • View positions/P&L → Biometric once per session           │
│  • Execute trades → Biometric EVERY time                     │
│  • Change settings → Biometric + confirmation                │
│  • View sensitive data → Biometric + 2FA                     │
└─────────────────────────────────────────────────────────────┘
```

### 10.2 Biometric Service

```dart
// lib/services/biometric_service.dart

class BiometricService {
  final LocalAuthentication _localAuth = LocalAuthentication();
  final FlutterSecureStorage _secureStorage = const FlutterSecureStorage();

  // ── Check Availability ──

  Future<BiometricCapability> getCapability() async {
    final isAvailable = await _localAuth.canCheckBiometrics;
    final isDeviceSupported = await _localAuth.isDeviceSupported();

    if (!isAvailable || !isDeviceSupported) {
      return BiometricCapability.none;
    }

    final biometrics = await _localAuth.getAvailableBiometrics();
    if (biometrics.contains(BiometricType.face)) {
      return BiometricCapability.face;
    } else if (biometrics.contains(BiometricType.fingerprint)) {
      return BiometricCapability.fingerprint;
    } else if (biometrics.contains(BiometricType.strong)) {
      return BiometricCapability.strong;
    }
    return BiometricCapability.none;
  }

  // ── Authenticate ──

  Future<AuthResult> authenticate({
    required String reason,
    bool useErrorDialogs = true,
    bool stickyAuth = true,
  }) async {
    try {
      final didAuthenticate = await _localAuth.authenticate(
        localizedReason: reason,
        options: AuthenticationOptions(
          useErrorDialogs: useErrorDialogs,
          stickyAuth: stickyAuth,
          biometricOnly: false,      // Allow PIN fallback
          sensitiveTransaction: true, // Higher security on Android
        ),
      );

      if (didAuthenticate) {
        await _recordAuthTimestamp();
        return AuthResult.success;
      }
      return AuthResult.cancelled;
    } on PlatformException catch (e) {
      if (e.code == 'NotAvailable' || e.code == 'NotEnrolled') {
        return AuthResult.notAvailable;
      }
      if (e.code == 'LockedOut') {
        return AuthResult.lockedOut;
      }
      return AuthResult.error(e.message ?? 'Unknown error');
    }
  }

  // ── Quick View Mode ──

  Future<bool> isQuickViewAllowed() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool('quick_view_enabled') ?? true;
  }

  Future<bool> needsReauth({Duration threshold = const Duration(minutes: 5)}) async {
    final lastAuth = await _getLastAuthTimestamp();
    if (lastAuth == null) return true;
    return DateTime.now().difference(lastAuth) > threshold;
  }

  // ── Secure Token Storage ──

  Future<void> storeAuthToken(String token) async {
    await _secureStorage.write(
      key: 'auth_token',
      value: token,
      aOptions: _getAndroidOptions(),
      iOptions: _getIOSOptions(),
    );
  }

  AndroidOptions _getAndroidOptions() => const AndroidOptions(
    encryptedSharedPreferences: true,
    keyCipherAlgorithm: KeyCipherAlgorithm.RSA_ECB_OAEPwithSHA_256andMGF1Padding,
    storageCipherAlgorithm: StorageCipherAlgorithm.AES_GCM_NoPadding,
  );

  IOSOptions _getIOSOptions() => const IOSOptions(
    accessibility: KeychainAccessibility.first_unlock_this_device,
    synchronizable: false,
  );
}
```

### 10.3 Biometric Lock Screen

```dart
// lib/screens/auth/biometric_lock_screen.dart

class BiometricLockScreen extends ConsumerStatefulWidget {
  @override
  ConsumerState<BiometricLockScreen> createState() => _BiometricLockScreenState();
}

class _BiometricLockScreenState extends ConsumerState<BiometricLockScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;
  BiometricCapability _capability = BiometricCapability.none;
  bool _isAuthenticating = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat(reverse: true);
    _checkCapability();
    _autoAuthenticate();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AlphaColors.bgPrimary,
      body: SafeArea(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // App logo
            const Icon(
              Icons.show_chart,
              size: 64,
              color: AlphaColors.accent,
            ),
            const SizedBox(height: AlphaSpacing.lg),
            Text(
              'Alpha Stack',
              style: AlphaTypography.priceLarge.copyWith(
                color: AlphaColors.textPrimary,
                fontSize: 32,
              ),
            ),

            const SizedBox(height: AlphaSpacing.xxl),

            // Biometric icon with pulse animation
            AnimatedBuilder(
              animation: _pulseController,
              builder: (context, child) {
                return Transform.scale(
                  scale: 1.0 + (_pulseController.value * 0.05),
                  child: Container(
                    width: 96,
                    height: 96,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: AlphaColors.accent.withOpacity(0.1),
                      border: Border.all(
                        color: AlphaColors.accent.withOpacity(
                          0.3 + (_pulseController.value * 0.3),
                        ),
                        width: 2,
                      ),
                    ),
                    child: Icon(
                      _biometricIcon,
                      size: 48,
                      color: AlphaColors.accent,
                    ),
                  ),
                );
              },
            ),

            const SizedBox(height: AlphaSpacing.xl),

            // Instruction text
            Text(
              _instructionText,
              style: AlphaTypography.bodyMedium.copyWith(
                color: AlphaColors.textSecondary,
              ),
            ),

            if (_errorMessage != null) ...[
              const SizedBox(height: AlphaSpacing.md),
              Text(
                _errorMessage!,
                style: AlphaTypography.caption.copyWith(
                  color: AlphaColors.critical,
                ),
              ),
            ],

            const SizedBox(height: AlphaSpacing.xxl),

            // Authenticate button
            if (_isAuthenticating)
              const CircularProgressIndicator(color: AlphaColors.accent)
            else
              TextButton(
                onPressed: _authenticate,
                child: Text(
                  'Tap to authenticate',
                  style: AlphaTypography.labelLarge.copyWith(
                    color: AlphaColors.accentLight,
                  ),
                ),
              ),

            const SizedBox(height: AlphaSpacing.lg),

            // Quick view option
            TextButton(
              onPressed: _quickView,
              child: Text(
                'Quick View (limited access)',
                style: AlphaTypography.caption.copyWith(
                  color: AlphaColors.textTertiary,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  IconData get _biometricIcon {
    switch (_capability) {
      case BiometricCapability.face:
        return Icons.face;
      case BiometricCapability.fingerprint:
        return Icons.fingerprint;
      default:
        return Icons.lock;
    }
  }
}
```

---

## 11. Dark Mode as Default

### 11.1 Theme Architecture

```dart
// lib/theme/alpha_theme.dart

class AlphaTheme {
  // ── Dark Theme (DEFAULT) ──

  static ThemeData get darkTheme => ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    scaffoldBackgroundColor: AlphaColors.bgPrimary,
    colorScheme: const ColorScheme.dark(
      primary: AlphaColors.accent,
      secondary: AlphaColors.accentLight,
      surface: AlphaColors.bgSecondary,
      error: AlphaColors.critical,
      onPrimary: Colors.white,
      onSecondary: Colors.white,
      onSurface: AlphaColors.textPrimary,
      onError: Colors.white,
    ),

    // AppBar
    appBarTheme: const AppBarTheme(
      backgroundColor: AlphaColors.bgPrimary,
      foregroundColor: AlphaColors.textPrimary,
      elevation: 0,
      scrolledUnderElevation: 1,
      titleTextStyle: TextStyle(
        fontFamily: AlphaTypography.fontUI,
        fontSize: 18,
        fontWeight: FontWeight.w700,
        color: AlphaColors.textPrimary,
      ),
    ),

    // Cards
    cardTheme: CardTheme(
      color: AlphaColors.bgSecondary,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AlphaSpacing.radiusMd),
        side: BorderSide(color: AlphaColors.bgTertiary, width: 1),
      ),
    ),

    // Bottom Navigation
    bottomNavigationBarTheme: const BottomNavigationBarThemeData(
      backgroundColor: AlphaColors.bgSecondary,
      selectedItemColor: AlphaColors.accent,
      unselectedItemColor: AlphaColors.textTertiary,
      type: BottomNavigationBarType.fixed,
      elevation: 8,
    ),

    // Input fields
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: AlphaColors.bgTertiary,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AlphaSpacing.radiusSm),
        borderSide: BorderSide.none,
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AlphaSpacing.radiusSm),
        borderSide: const BorderSide(color: AlphaColors.accent, width: 2),
      ),
      labelStyle: const TextStyle(color: AlphaColors.textSecondary),
      hintStyle: const TextStyle(color: AlphaColors.textTertiary),
    ),

    // Buttons
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: AlphaColors.accent,
        foregroundColor: Colors.white,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AlphaSpacing.radiusMd),
        ),
        padding: const EdgeInsets.symmetric(
          horizontal: AlphaSpacing.xl,
          vertical: AlphaSpacing.md,
        ),
      ),
    ),

    // Slider
    sliderTheme: SliderThemeData(
      activeTrackColor: AlphaColors.accent,
      inactiveTrackColor: AlphaColors.bgTertiary,
      thumbColor: AlphaColors.accent,
      overlayColor: AlphaColors.accent.withOpacity(0.2),
    ),

    // Switch
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) {
          return AlphaColors.bull;
        }
        return AlphaColors.textTertiary;
      }),
      trackColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) {
          return AlphaColors.bullDim;
        }
        return AlphaColors.bgTertiary;
      }),
    ),

    // Text
    textTheme: const TextTheme(
      headlineLarge: AlphaTypography.priceLarge,
      bodyLarge: AlphaTypography.bodyMedium,
      labelLarge: AlphaTypography.labelLarge,
      bodySmall: AlphaTypography.caption,
    ),
  );

  // ── Light Theme (OPTIONAL) ──

  static ThemeData get lightTheme => ThemeData(
    useMaterial3: true,
    brightness: Brightness.light,
    // ... light theme overrides
    // Note: Chart colors remain green/red in both themes
    // Only backgrounds and text colors change
  );
}
```

### 11.2 Theme Mode Provider

```dart
// lib/providers/theme_provider.dart

final themeModeProvider = StateNotifierProvider<ThemeModeNotifier, ThemeMode>((ref) {
  return ThemeModeNotifier(ref);
});

class ThemeModeNotifier extends StateNotifier<ThemeMode> {
  final Ref ref;

  ThemeModeNotifier(this.ref) : super(ThemeMode.dark) {  // DEFAULT: Dark
    _loadSavedTheme();
  }

  Future<void> _loadSavedTheme() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString('theme_mode') ?? 'dark';
    state = ThemeMode.values.firstWhere(
      (m) => m.name == saved,
      orElse: () => ThemeMode.dark,
    );
  }

  Future<void> setThemeMode(ThemeMode mode) async {
    state = mode;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('theme_mode', mode.name);
  }
}
```

### 11.3 Chart Colors in Both Themes

```dart
// lib/theme/chart_colors.dart

class ChartColors {
  // These remain consistent in both light and dark mode
  // because green/red are universally understood in trading

  static const Color bullCandle     = Color(0xFF10B981);
  static const Color bearCandle     = Color(0xFFEF4444);
  static const Color bullCandleFill = Color(0xFF10B981);
  static const Color bearCandleFill = Color(0xFFEF4444);

  // Background adapts to theme
  static Color chartBackground(Brightness brightness) {
    return brightness == Brightness.dark
        ? const Color(0xFF0D1117)
        : const Color(0xFFFAFAFA);
  }

  static Color gridColor(Brightness brightness) {
    return brightness == Brightness.dark
        ? const Color(0xFF1C2333)
        : const Color(0xFFE5E7EB);
  }

  static Color crosshairColor(Brightness brightness) {
    return brightness == Brightness.dark
        ? const Color(0xFF374151)
        : const Color(0xFF9CA3AF);
  }

  // Volume bars
  static Color volumeBull(Brightness brightness) {
    return bullCandle.withOpacity(brightness == Brightness.dark ? 0.3 : 0.2);
  }

  static Color volumeBear(Brightness brightness) {
    return bearCandle.withOpacity(brightness == Brightness.dark ? 0.3 : 0.2);
  }

  // Indicator colors
  static const Color sma20 = Color(0xFF3B82F6);   // Blue
  static const Color sma50 = Color(0xFFF59E0B);   // Amber
  static const Color sma200 = Color(0xFF8B5CF6);  // Purple
  static const Color rsi = Color(0xFF06B6D4);     // Cyan
  static const Color macdLine = Color(0xFF3B82F6);
  static const Color macdSignal = Color(0xFFEF4444);
  static const Color macdHistogram = Color(0xFF10B981);

  // SMC zones
  static Color orderBlockBull = const Color(0xFF10B981).withOpacity(0.15);
  static Color orderBlockBear = const Color(0xFFEF4444).withOpacity(0.15);
  static Color fvgZone = const Color(0xFFF59E0B).withOpacity(0.1);
  static Color liquidityLevel = const Color(0xFF8B5CF6).withOpacity(0.3);
}
```

---

## 12. Offline Mode

### 12.1 Offline Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   OFFLINE MODE ARCHITECTURE                   │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ UI LAYER (Always reads from local cache)                │ │
│  │ ├── Shows cached prices with "Last updated: X ago"      │ │
│  │ ├── Disables trade execution buttons                    │ │
│  │ ├── Shows offline banner at top                         │ │
│  │ └── Allows viewing all cached data                      │ │
│  └─────────────────────────────────────────────────────────┘ │
│                           │                                  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ LOCAL DATABASE (Isar)                                   │ │
│  │ ├── Cached prices (last 24h)                            │ │
│  │ ├── Open positions (snapshot)                           │ │
│  │ ├── Trade history (full)                                │ │
│  │ ├── Signal history (last 7 days)                        │ │
│  │ ├── Watchlist                                           │ │
│  │ ├── Settings & preferences                              │ │
│  │ └── Notification inbox                                  │ │
│  └─────────────────────────────────────────────────────────┘ │
│                           │                                  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ SYNC ENGINE                                             │ │
│  │ ├── Detects reconnection                                │ │
│  │ ├── Fetches delta updates since last sync               │ │
│  │ ├── Reconciles local vs server state                    │ │
│  │ ├── Server wins for financial data                      │ │
│  │ └── LWW for preferences                                │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 12.2 Isar Database Schema

```dart
// lib/data/models/isar_models.dart

@Collection()
class CachedPrice {
  Id id = Isar.autoIncrement;
  late String symbol;
  late double bid;
  late double ask;
  late double high;
  late double low;
  late DateTime timestamp;

  @Index(composite: [CompositeIndex('symbol')])
  late int timestampMillis;
}

@Collection()
class CachedPosition {
  Id id = Isar.autoIncrement;
  late int ticket;
  late String symbol;
  late String direction;
  late double lotSize;
  late double openPrice;
  late double currentPrice;
  late double stopLoss;
  late double takeProfit;
  late double unrealizedPnl;
  late DateTime openTime;
  late DateTime lastUpdated;
}

@Collection()
class CachedTrade {
  Id id = Isar.autoIncrement;
  late int ticket;
  late String symbol;
  late String direction;
  late double lotSize;
  late double openPrice;
  late double closePrice;
  late double pnl;
  late DateTime openTime;
  late DateTime closeTime;
  late String? notes;

  @Index()
  late int closeTimeMillis;
}

@Collection()
class CachedSignal {
  Id id = Isar.autoIncrement;
  late String symbol;
  late String direction;
  late double confidence;
  late double entry;
  late double? stopLoss;
  late double? takeProfit;
  late String status; // 'active', 'expired', 'executed'
  late DateTime createdAt;
  late Map<String, double> agentScores;

  @Index()
  late int createdAtMillis;
}
```

### 12.3 Offline Indicator Widget

```dart
// lib/widgets/offline_banner.dart

class OfflineBanner extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isOnline = ref.watch(isOnlineProvider);
    final lastSync = ref.watch(lastSyncTimeProvider);

    if (isOnline) return const SizedBox.shrink();

    return AnimatedContainer(
      duration: AlphaMotion.normal,
      height: 40,
      color: AlphaColors.warning.withOpacity(0.2),
      padding: const EdgeInsets.symmetric(
        horizontal: AlphaSpacing.md,
        vertical: AlphaSpacing.sm,
      ),
      child: Row(
        children: [
          const Icon(
            Icons.wifi_off,
            size: 16,
            color: AlphaColors.warning,
          ),
          const SizedBox(width: AlphaSpacing.sm),
          Expanded(
            child: Text(
              'Offline · Trading disabled · Last sync: ${_formatTime(lastSync)}',
              style: AlphaTypography.caption.copyWith(
                color: AlphaColors.warning,
              ),
            ),
          ),
          TextButton(
            onPressed: () => ref.read(webSocketProvider.notifier).reconnect(),
            style: TextButton.styleFrom(
              padding: EdgeInsets.zero,
              minimumSize: Size.zero,
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            child: Text(
              'Retry',
              style: AlphaTypography.caption.copyWith(
                color: AlphaColors.accentLight,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
```

### 12.4 Stale Data Indicator

```dart
// lib/widgets/stale_data_indicator.dart

class StaleDataIndicator extends StatelessWidget {
  final DateTime lastUpdated;
  final bool isOnline;

  const StaleDataIndicator({
    required this.lastUpdated,
    required this.isOnline,
  });

  @override
  Widget build(BuildContext context) {
    final age = DateTime.now().difference(lastUpdated);
    final isStale = age > const Duration(minutes: 5);

    if (isOnline && !isStale) return const SizedBox.shrink();

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 6, height: 6,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: isStale ? AlphaColors.warning : AlphaColors.bull,
          ),
        ),
        const SizedBox(width: 4),
        Text(
          _formatAge(age),
          style: AlphaTypography.caption.copyWith(
            color: isStale ? AlphaColors.warning : AlphaColors.textTertiary,
            fontSize: 10,
          ),
        ),
      ],
    );
  }

  String _formatAge(Duration age) {
    if (age.inMinutes < 1) return 'just now';
    if (age.inMinutes < 60) return '${age.inMinutes}m ago';
    if (age.inHours < 24) return '${age.inHours}h ago';
    return '${age.inDays}d ago';
  }
}
```

---

## 13. Home Screen Widgets

### 13.1 Widget Architecture

```
┌─────────────────────────────────────────────────────────────┐
│               HOME SCREEN WIDGET SYSTEM                       │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ SHARED DATA LAYER                                       │ │
│  │                                                         │ │
│  │  Flutter App ←→ SharedPreferences / App Groups          │ │
│  │       │              (shared data container)             │ │
│  │       │                                                 │ │
│  │       └── Writes: portfolio, prices, P&L                │ │
│  │           Widget reads from shared container             │ │
│  └──────────────────────┬──────────────────────────────────┘ │
│                         │                                    │
│          ┌──────────────┴──────────────┐                     │
│          ▼                             ▼                     │
│  ┌───────────────┐           ┌───────────────┐              │
│  │ ANDROID WIDGET│           │ iOS WIDGET    │              │
│  │ (Kotlin)      │           │ (SwiftUI)     │              │
│  │               │           │               │              │
│  │ AppWidget     │           │ WidgetKit     │              │
│  │ Provider      │           │ Timeline      │              │
│  │               │           │ Provider      │              │
│  │ Sizes:        │           │ Sizes:        │              │
│  │ • 2x1 (small) │           │ • Small       │              │
│  │ • 2x2 (medium)│           │ • Medium      │              │
│  │ • 4x2 (large) │           │ • Large       │              │
│  └───────────────┘           └───────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### 13.2 Widget Data Provider (Flutter → Native)

```dart
// lib/services/widget_service.dart

class WidgetService {
  static const _homeWidget = HomeWidget();

  // ── Update Widget Data ──

  static Future<void> updatePortfolioWidget({
    required double balance,
    required double dailyPnl,
    required double dailyPnlPercent,
    required List<PriceSnapshot> topPairs,
  }) async {
    await _homeWidget.saveWidgetData<String>(
      'portfolio',
      jsonEncode({
        'balance': balance,
        'dailyPnl': dailyPnl,
        'dailyPnlPercent': dailyPnlPercent,
        'updatedAt': DateTime.now().toIso8601String(),
      }),
    );

    await _homeWidget.saveWidgetData<String>(
      'top_pairs',
      jsonEncode(topPairs.map((p) => {
        'symbol': p.symbol,
        'price': p.price,
        'change': p.changePercent,
      }).toList()),
    );

    // Trigger widget update
    await _homeWidget.updateWidget(
      name: 'AlphaStackWidget',
      iOSName: 'AlphaStackWidget',
    );
  }

  // ── Handle Widget Tap ──

  static void registerInteractivity() {
    _homeWidget.registerInteractivityCallback(_onWidgetAction);
  }

  static Future<void> _onWidgetAction(Uri? uri) async {
    if (uri == null) return;

    switch (uri.host) {
      case 'open_trade':
        // Navigate to quick trade screen
        final symbol = uri.queryParameters['symbol'];
        // Deep link into app
        break;
      case 'open_portfolio':
        // Navigate to dashboard
        break;
    }
  }
}
```

### 13.3 Android Widget (Kotlin)

```kotlin
// android/app/src/main/kotlin/.../AlphaStackWidget.kt

class AlphaStackWidget : AppWidgetProvider() {

    override fun onUpdate(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetIds: IntArray
    ) {
        for (appWidgetId in appWidgetIds) {
            updateAppWidget(context, appWidgetManager, appWidgetId)
        }
    }

    companion object {
        fun updateAppWidget(
            context: Context,
            appWidgetManager: AppWidgetManager,
            appWidgetId: Int
        ) {
            val prefs = context.getSharedPreferences("HomeWidgetPreferences", Context.MODE_PRIVATE)
            val portfolioJson = prefs.getString("portfolio", null) ?: return
            val portfolio = JSONObject(portfolioJson)

            val balance = portfolio.getDouble("balance")
            val dailyPnl = portfolio.getDouble("dailyPnl")
            val dailyPnlPercent = portfolio.getDouble("dailyPnlPercent")
            val updatedAt = portfolio.getString("updatedAt")

            // Build RemoteViews
            val views = RemoteViews(context.packageName, R.layout.widget_portfolio).apply {
                setTextViewText(R.id.balance, "$${String.format("%.2f", balance)}")

                val pnlColor = if (dailyPnl >= 0) 0xFF10B981.toInt() else 0xFFEF4444.toInt()
                val pnlSign = if (dailyPnl >= 0) "+" else ""
                setTextViewText(R.id.daily_pnl, "$pnlSign$${String.format("%.2f", dailyPnl)} (${pnlSign}${String.format("%.2f", dailyPnlPercent)}%)")
                setInt(R.id.daily_pnl, "setTextColor", pnlColor)

                setTextViewText(R.id.updated, "Updated: $updatedAt")

                // Click to open app
                val intent = Intent(context, MainActivity::class.java)
                val pendingIntent = PendingIntent.getActivity(context, 0, intent, PendingIntent.FLAG_IMMUTABLE)
                setOnClickPendingIntent(R.id.widget_root, pendingIntent)
            }

            appWidgetManager.updateAppWidget(appWidgetId, views)
        }
    }
}
```

### 13.4 iOS Widget (Swift)

```swift
// ios/AlphaStackWidget/AlphaStackWidget.swift

import WidgetKit
import SwiftUI

struct AlphaStackProvider: TimelineProvider {
    func placeholder(in context: Context) -> AlphaStackEntry {
        AlphaStackEntry(
            date: Date(),
            balance: 7.23,
            dailyPnl: 0.18,
            dailyPnlPercent: 2.55,
            topPairs: [
                PriceSnapshot(symbol: "EUR/USD", price: 1.0845, change: 0.12),
                PriceSnapshot(symbol: "GBP/USD", price: 1.2720, change: -0.08),
            ]
        )
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<AlphaStackEntry>) -> Void) {
        let data = loadSharedData()
        let entry = AlphaStackEntry(
            date: Date(),
            balance: data.balance,
            dailyPnl: data.dailyPnl,
            dailyPnlPercent: data.dailyPnlPercent,
            topPairs: data.topPairs
        )

        // Update every 15 minutes
        let nextUpdate = Calendar.current.date(byAdding: .minute, value: 15, to: Date())!
        let timeline = Timeline(entries: [entry], policy: .after(nextUpdate))
        completion(timeline)
    }

    private func loadSharedData() -> PortfolioData {
        let defaults = UserDefaults(suiteName: "group.com.alphastack.app")
        guard let jsonString = defaults?.string(forKey: "portfolio"),
              let data = jsonString.data(using: .utf8),
              let decoded = try? JSONDecoder().decode(PortfolioData.self, from: data)
        else {
            return PortfolioData.empty
        }
        return decoded
    }
}

struct AlphaStackWidgetEntryView: View {
    var entry: AlphaStackProvider.Entry

    @Environment(\.widgetFamily) var family

    var body: some View {
        switch family {
        case .systemSmall:
            SmallWidgetView(entry: entry)
        case .systemMedium:
            MediumWidgetView(entry: entry)
        case .systemLarge:
            LargeWidgetView(entry: entry)
        default:
            SmallWidgetView(entry: entry)
        }
    }
}

struct SmallWidgetView: View {
    let entry: AlphaStackEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "chart.line.uptrend.xyaxis")
                    .foregroundColor(.blue)
                Text("Alpha Stack")
                    .font(.caption)
                    .fontWeight(.bold)
                Spacer()
            }

            Text("$\(String(format: "%.2f", entry.balance))")
                .font(.system(size: 24, weight: .bold, design: .monospaced))

            HStack {
                Text(entry.dailyPnl >= 0 ? "+" : "")
                    + Text("$\(String(format: "%.2f", entry.dailyPnl))")
                Spacer()
                Text("\(entry.dailyPnl >= 0 ? "+" : "")\(String(format: "%.2f", entry.dailyPnlPercent))%")
            }
            .font(.system(size: 14, weight: .semibold, design: .monospaced))
            .foregroundColor(entry.dailyPnl >= 0 ? .green : .red)
        }
        .padding()
        .background(Color(red: 0.04, green: 0.055, blue: 0.1))
    }
}
```

---

## 14. Voice Commands

### 14.1 Voice Command Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   VOICE COMMAND SYSTEM                        │
│                                                              │
│  ┌──────────┐     ┌──────────┐     ┌──────────────────┐    │
│  │  Micro-  │────▶│ Speech   │────▶│ Command Parser   │    │
│  │  phone   │     │ to Text  │     │ (NLP / Regex)    │    │
│  │  Input   │     │ Engine   │     │                  │    │
│  └──────────┘     └──────────┘     └────────┬─────────┘    │
│                                              │              │
│                                    ┌─────────▼─────────┐   │
│                                    │ Command Router     │   │
│                                    │                    │   │
│                                    │ "buy EUR/USD"     │   │
│                                    │ "close all"       │   │
│                                    │ "show positions"  │   │
│                                    │ "what's my P&L"   │   │
│                                    │ "pause trading"   │   │
│                                    └─────────┬─────────┘   │
│                                              │              │
│                                    ┌─────────▼─────────┐   │
│                                    │ Action Executor    │   │
│                                    │ + Voice Feedback   │   │
│                                    └───────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 14.2 Voice Command Service

```dart
// lib/services/voice_command_service.dart

class VoiceCommandService {
  final SpeechToText _speech = SpeechToText();
  final FlutterTts _tts = FlutterTts();
  bool _isListening = false;

  // ── Command Patterns ──

  static final _commandPatterns = <RegExp, VoiceCommand Function(Match)>{
    // Trade commands
    RegExp(r'buy\s+(\w+/?\w+)', caseSensitive: false):
      (m) => VoiceCommand.trade(m.group(1)!, TradeDirection.buy),
    RegExp(r'sell\s+(\w+/?\w+)', caseSensitive: false):
      (m) => VoiceCommand.trade(m.group(1)!, TradeDirection.sell),
    RegExp(r'close\s+(?:all|everything)', caseSensitive: false):
      (_) => VoiceCommand.closeAll(),
    RegExp(r'close\s+(\w+/?\w+)', caseSensitive: false):
      (m) => VoiceCommand.closePosition(m.group(1)!),

    // Query commands
    RegExp(r"(?:what'?s?|show)\s+(?:my\s+)?(?:p\s*&?\s*l|profit|pnl)", caseSensitive: false):
      (_) => VoiceCommand.queryPnl(),
    RegExp(r'show\s+(?:my\s+)?positions?', caseSensitive: false):
      (_) => VoiceCommand.queryPositions(),
    RegExp(r"(?:what'?s?|show)\s+(?:my\s+)?balance", caseSensitive: false):
      (_) => VoiceCommand.queryBalance(),
    RegExp(r"(?:what'?s?|show)\s+(\w+/?\w+)\s+(?:price|at)", caseSensitive: false):
      (m) => VoiceCommand.queryPrice(m.group(1)!),

    // Control commands
    RegExp(r'pause\s+(?:trading|bot)', caseSensitive: false):
      (_) => VoiceCommand.pauseTrading(),
    RegExp(r'resume\s+(?:trading|bot)', caseSensitive: false):
      (_) => VoiceCommand.resumeTrading(),
    RegExp(r'status', caseSensitive: false):
      (_) => VoiceCommand.queryStatus(),
  };

  // ── Listening ──

  Future<void> startListening({
    required Function(VoiceCommand) onCommand,
    required Function(String) onPartial,
    required Function(String) onError,
  }) async {
    final available = await _speech.initialize(
      onStatus: (status) {
        if (status == 'done' || status == 'notListening') {
          _isListening = false;
        }
      },
      onError: (error) => onError(error.errorMsg),
    );

    if (!available) {
      onError('Speech recognition not available');
      return;
    }

    _isListening = true;
    await _speech.listen(
      onResult: (result) {
        final text = result.recognizedWords;
        onPartial(text);

        if (result.finalResult) {
          final command = _parseCommand(text);
          if (command != null) {
            _confirmCommand(command);
            onCommand(command);
          } else {
            _speak("Sorry, I didn't understand that command.");
          }
        }
      },
      listenFor: const Duration(seconds: 30),
      pauseFor: const Duration(seconds: 3),
      localeId: 'en_US',
      cancelOnError: true,
    );
  }

  Future<void> stopListening() async {
    await _speech.stop();
    _isListening = false;
  }

  // ── Command Parsing ──

  VoiceCommand? _parseCommand(String text) {
    for (final entry in _commandPatterns.entries) {
      final match = entry.key.firstMatch(text);
      if (match != null) {
        return entry.value(match);
      }
    }
    return null;
  }

  // ── Voice Feedback ──

  Future<void> _confirmCommand(VoiceCommand command) async {
    switch (command.type) {
      case CommandType.trade:
        await _speak(
          "Executing ${command.direction.name} on ${command.symbol}. "
          "Please confirm with biometric."
        );
        break;
      case CommandType.closeAll:
        await _speak("Closing all positions. Please confirm.");
        break;
      case CommandType.queryPnl:
        // Fetch actual P&L and speak it
        break;
    }
  }

  Future<void> _speak(String text) async {
    await _tts.setLanguage("en-US");
    await _tts.setSpeechRate(0.5);
    await _tts.setVolume(1.0);
    await _tts.setPitch(1.0);
    await _tts.speak(text);
  }
}
```

### 14.3 Voice Command Overlay

```dart
// lib/widgets/voice/voice_command_overlay.dart

class VoiceCommandOverlay extends ConsumerStatefulWidget {
  @override
  ConsumerState<VoiceCommandOverlay> createState() => _VoiceCommandOverlayState();
}

class _VoiceCommandOverlayState extends ConsumerState<VoiceCommandOverlay>
    with SingleTickerProviderStateMixin {
  late AnimationController _waveController;
  bool _isListening = false;
  String _partialText = '';
  VoiceCommand? _parsedCommand;

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: AlphaMotion.normal,
      height: _isListening ? 200 : 64,
      decoration: BoxDecoration(
        color: AlphaColors.bgSecondary,
        borderRadius: const BorderRadius.vertical(
          top: Radius.circular(AlphaSpacing.radiusXl),
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.3),
            blurRadius: 20,
            offset: const Offset(0, -5),
          ),
        ],
      ),
      child: _isListening ? _buildListeningUI() : _buildIdleUI(),
    );
  }

  Widget _buildListeningUI() {
    return Column(
      children: [
        const SizedBox(height: AlphaSpacing.md),

        // Sound wave visualization
        AnimatedBuilder(
          animation: _waveController,
          builder: (context, child) {
            return CustomPaint(
              size: const Size(200, 40),
              painter: SoundWavePainter(
                amplitude: _waveController.value,
                color: AlphaColors.accent,
              ),
            );
          },
        ),

        const SizedBox(height: AlphaSpacing.md),

        // Partial text
        Text(
          _partialText.isEmpty ? 'Listening...' : _partialText,
          style: AlphaTypography.bodyMedium.copyWith(
            color: AlphaColors.textPrimary,
          ),
          textAlign: TextAlign.center,
        ),

        if (_parsedCommand != null) ...[
          const SizedBox(height: AlphaSpacing.sm),
          _ParsedCommandPreview(command: _parsedCommand!),
        ],

        const Spacer(),

        // Stop button
        TextButton(
          onPressed: _stopListening,
          child: Text(
            'Tap to stop',
            style: AlphaTypography.caption.copyWith(
              color: AlphaColors.textTertiary,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildIdleUI() {
    return Center(
      child: GestureDetector(
        onTap: _startListening,
        child: Container(
          width: 48, height: 48,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: AlphaColors.accent.withOpacity(0.2),
          ),
          child: const Icon(
            Icons.mic,
            color: AlphaColors.accent,
          ),
        ),
      ),
    );
  }
}
```

---

## 15. Low Data Usage Mode

### 15.1 Data Usage Tiers

```
┌─────────────────────────────────────────────────────────────┐
│                 DATA USAGE MODES                              │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ FULL MODE (default on WiFi)                             │ │
│  │ ├── WebSocket: 100ms tick updates                       │ │
│  │ ├── Charts: Full resolution, all indicators             │ │
│  │ ├── Images: High quality                                │ │
│  │ ├── Animations: All enabled                             │ │
│  │ └── Est. usage: ~50-100 MB/day                          │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ BALANCED MODE (default on mobile data)                  │ │
│  │ ├── WebSocket: 500ms tick updates                       │ │
│  │ ├── Charts: Reduced indicators (SMA only)               │ │
│  │ ├── Images: Compressed                                  │ │
│  │ ├── Animations: Reduced                                 │ │
│  │ └── Est. usage: ~15-30 MB/day                           │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ LOW DATA MODE (manual toggle)                           │ │
│  │ ├── WebSocket: 2s tick updates (batched)                │ │
│  │ ├── Charts: Text-only prices, no charts                 │ │
│  │ ├── Images: Off                                         │ │
│  │ ├── Animations: Off                                     │ │
│  │ ├── Push: Only critical alerts                          │ │
│  │ └── Est. usage: ~2-5 MB/day                             │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ DATA SAVER (extreme)                                    │ │
│  │ ├── WebSocket: 10s updates, only watched pairs          │ │
│  │ ├── Everything text-only                                │ │
│  │ ├── No images, no charts, no animations                 │ │
│  │ ├── Push: Only risk warnings and margin calls           │ │
│  │ └── Est. usage: <1 MB/day                               │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 15.2 Data Usage Manager

```dart
// lib/services/data_usage_manager.dart

enum DataMode { full, balanced, lowData, dataSaver }

class DataUsageManager extends StateNotifier<DataMode> {
  final Ref ref;

  DataUsageManager(this.ref) : super(DataMode.full) {
    _autoDetectMode();
  }

  // ── Auto-detect based on connection type ──

  Future<void> _autoDetectMode() async {
    final connectivity = ref.read(connectivityProvider);
    connectivity.whenData((result) {
      switch (result) {
        case ConnectivityResult.wifi:
          state = DataMode.full;
          break;
        case ConnectivityResult.mobile:
          state = DataMode.balanced;
          break;
        case ConnectivityResult.none:
          // Offline mode handled separately
          break;
        default:
          state = DataMode.balanced;
      }
    });
  }

  // ── Get current settings ──

  Duration get tickInterval {
    switch (state) {
      case DataMode.full:
        return const Duration(milliseconds: 100);
      case DataMode.balanced:
        return const Duration(milliseconds: 500);
      case DataMode.lowData:
        return const Duration(seconds: 2);
      case DataMode.dataSaver:
        return const Duration(seconds: 10);
    }
  }

  bool get showCharts => state != DataMode.dataSaver;
  bool get showImages => state == DataMode.full || state == DataMode.balanced;
  bool get enableAnimations => state == DataMode.full;
  int get maxIndicators => state == DataMode.full ? 5 : state == DataMode.balanced ? 2 : 0;
  bool get compressWebSocket => state != DataMode.full;

  // ── WebSocket configuration ──

  Map<String, dynamic> get wsConfig => {
    'tick_interval_ms': tickInterval.inMilliseconds,
    'batch_updates': state == DataMode.lowData || state == DataMode.dataSaver,
    'compress': compressWebSocket,
    'subscribe_only_watched': state == DataMode.dataSaver,
    'use_binary_protocol': state != DataMode.full,  // MessagePack instead of JSON
  };
}
```

### 15.3 Data Usage Settings UI

```dart
// lib/screens/settings/data_usage_screen.dart

class DataUsageScreen extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentMode = ref.watch(dataModeProvider);
    final usageStats = ref.watch(dataUsageStatsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Data & Performance')),
      body: ListView(
        padding: const EdgeInsets.all(AlphaSpacing.lg),
        children: [
          // Current usage stats
          _UsageStatsCard(stats: usageStats),

          const SizedBox(height: AlphaSpacing.xl),

          // Data mode selector
          Text('Data Mode', style: AlphaTypography.labelLarge),
          const SizedBox(height: AlphaSpacing.md),

          ...DataMode.values.map((mode) => _DataModeTile(
            mode: mode,
            isSelected: mode == currentMode,
            onTap: () => ref.read(dataModeProvider.notifier).setMode(mode),
          )),

          const SizedBox(height: AlphaSpacing.xl),

          // Manual toggles
          Text('Manual Overrides', style: AlphaTypography.labelLarge),
          const SizedBox(height: AlphaSpacing.md),

          SwitchListTile(
            title: const Text('Show Charts'),
            subtitle: const Text('Disable for text-only prices'),
            value: ref.watch(showChartsProvider),
            onChanged: (v) => ref.read(showChartsProvider.notifier).toggle(v),
            activeColor: AlphaColors.bull,
          ),

          SwitchListTile(
            title: const Text('Animations'),
            subtitle: const Text('Disable for better performance'),
            value: ref.watch(animationsEnabledProvider),
            onChanged: (v) => ref.read(animationsEnabledProvider.notifier).toggle(v),
            activeColor: AlphaColors.bull,
          ),

          SwitchListTile(
            title: const Text('Auto-detect Connection'),
            subtitle: const Text('Switch mode based on WiFi/mobile data'),
            value: ref.watch(autoDetectModeProvider),
            onChanged: (v) => ref.read(autoDetectModeProvider.notifier).toggle(v),
            activeColor: AlphaColors.bull,
          ),

          const SizedBox(height: AlphaSpacing.xl),

          // Cache management
          Text('Cache', style: AlphaTypography.labelLarge),
          const SizedBox(height: AlphaSpacing.md),

          ListTile(
            title: const Text('Cached Data'),
            subtitle: Text('${usageStats.cacheSize} MB'),
            trailing: TextButton(
              onPressed: () => _clearCache(context, ref),
              child: const Text('Clear'),
            ),
          ),
        ],
      ),
    );
  }
}
```

---

## 16. Accessibility & Responsive Design

### 16.1 Responsive Breakpoints

```dart
// lib/utils/responsive.dart

class AlphaResponsive {
  // Flutter handles phone sizes naturally, but we optimize for:
  // • Small phones (iPhone SE, 320dp width)
  // • Standard phones (iPhone 14, 390dp width)
  // • Large phones (iPhone 15 Pro Max, 430dp width)
  // • Foldables (unfolded, 600dp+ width)

  static bool isSmallPhone(BuildContext context) {
    return MediaQuery.of(context).size.width < 360;
  }

  static bool isLargePhone(BuildContext context) {
    return MediaQuery.of(context).size.width >= 430;
  }

  static bool isFoldable(BuildContext context) {
    return MediaQuery.of(context).size.width >= 600;
  }

  // Adjust font scale
  static double fontScale(BuildContext context) {
    if (isSmallPhone(context)) return 0.9;
    if (isLargePhone(context)) return 1.1;
    return 1.0;
  }

  // Adjust chart candle width
  static double candleWidth(BuildContext context) {
    if (isSmallPhone(context)) return 6.0;
    if (isLargePhone(context)) return 10.0;
    return 8.0;
  }

  // Adjust visible candles
  static int visibleCandles(BuildContext context) {
    if (isSmallPhone(context)) return 40;
    if (isLargePhone(context)) return 80;
    return 60;
  }
}
```

### 16.2 Accessibility Standards

```dart
// lib/utils/accessibility.dart

class AlphaAccessibility {
  // Minimum touch targets (44x44 per Apple HIG, 48x48 per Material)
  static const double minTouchTarget = 44;

  // Semantic labels for screen readers
  static String priceLabel(String symbol, double price, double change) {
    final direction = change >= 0 ? 'up' : 'down';
    return '$symbol at ${price.toStringAsFixed(5)}, '
           '$direction ${change.abs().toStringAsFixed(2)} percent';
  }

  static String pnlLabel(double pnl, double pnlPercent) {
    final direction = pnl >= 0 ? 'profit' : 'loss';
    return 'Today\'s $direction: ${pnl.abs().toStringAsFixed(2)} dollars, '
           '${pnlPercent.abs().toStringAsFixed(2)} percent';
  }

  static String positionLabel(String symbol, String direction, double pnl) {
    return '$direction $symbol position, '
           '${pnl >= 0 ? "profit" : "loss"} of '
           '${pnl.abs().toStringAsFixed(2)} dollars';
  }

  // Color contrast verification (WCAG AA: 4.5:1 for text)
  static bool meetsContrastRatio(Color foreground, Color background) {
    final ratio = _contrastRatio(foreground, background);
    return ratio >= 4.5;
  }
}
```

---

## 17. File & Directory Layout

### 17.1 Project Structure

```
alpha_stack_mobile/
├── lib/
│   ├── main.dart                         # App entry point
│   ├── app.dart                          # MaterialApp with theme, router
│   │
│   ├── theme/                            # Design system
│   │   ├── alpha_colors.dart
│   │   ├── alpha_typography.dart
│   │   ├── alpha_spacing.dart
│   │   ├── alpha_motion.dart
│   │   ├── alpha_theme.dart
│   │   └── chart_colors.dart
│   │
│   ├── router/                           # Navigation
│   │   ├── app_router.dart
│   │   └── auth_guard.dart
│   │
│   ├── providers/                        # Riverpod providers
│   │   ├── app_providers.dart
│   │   ├── theme_provider.dart
│   │   ├── auth_provider.dart
│   │   ├── market_provider.dart
│   │   ├── trading_provider.dart
│   │   ├── agent_provider.dart
│   │   └── settings_provider.dart
│   │
│   ├── screens/                          # Screen pages
│   │   ├── auth/
│   │   │   └── biometric_lock_screen.dart
│   │   ├── dashboard/
│   │   │   └── dashboard_screen.dart
│   │   ├── trade/
│   │   │   ├── trade_screen.dart
│   │   │   ├── chart_detail_screen.dart
│   │   │   └── order_entry_screen.dart
│   │   ├── quick_trade/
│   │   │   └── quick_trade_screen.dart
│   │   ├── agents/
│   │   │   ├── agent_monitor_screen.dart
│   │   │   └── agent_detail_screen.dart
│   │   ├── settings/
│   │   │   ├── settings_screen.dart
│   │   │   ├── broker_config_screen.dart
│   │   │   ├── strategy_config_screen.dart
│   │   │   ├── notification_settings_screen.dart
│   │   │   ├── security_settings_screen.dart
│   │   │   ├── data_usage_screen.dart
│   │   │   └── about_screen.dart
│   │   └── notifications/
│   │       └── notification_inbox_screen.dart
│   │
│   ├── widgets/                          # Reusable components
│   │   ├── charts/
│   │   │   ├── alpha_candlestick_chart.dart
│   │   │   ├── timeframe_selector.dart
│   │   │   ├── indicator_selector.dart
│   │   │   ├── equity_sparkline.dart
│   │   │   └── painters/
│   │   │       ├── candlestick_painter.dart
│   │   │       ├── grid_painter.dart
│   │   │       ├── indicator_painter.dart
│   │   │       └── crosshair_painter.dart
│   │   ├── trading/
│   │   │   ├── position_card.dart
│   │   │   ├── quick_trade_sheet.dart
│   │   │   ├── trade_confirmation_sheet.dart
│   │   │   ├── signal_card.dart
│   │   │   └── direction_toggle.dart
│   │   ├── agents/
│   │   │   ├── agent_card.dart
│   │   │   ├── agent_health_bar.dart
│   │   │   └── pipeline_flow.dart
│   │   ├── dashboard/
│   │   │   ├── portfolio_summary_card.dart
│   │   │   ├── active_positions_carousel.dart
│   │   │   ├── signals_section.dart
│   │   │   └── watchlist_section.dart
│   │   ├── voice/
│   │   │   ├── voice_command_overlay.dart
│   │   │   └── sound_wave_painter.dart
│   │   └── common/
│   │       ├── offline_banner.dart
│   │       ├── stale_data_indicator.dart
│   │       ├── connection_indicator.dart
│   │       ├── notification_bell.dart
│   │       ├── shimmer_box.dart
│   │       ├── section_header.dart
│   │       └── loading_skeleton.dart
│   │
│   ├── services/                         # Business logic
│   │   ├── notification_service.dart
│   │   ├── biometric_service.dart
│   │   ├── voice_command_service.dart
│   │   ├── widget_service.dart
│   │   ├── data_usage_manager.dart
│   │   ├── trading_service.dart
│   │   └── sync_service.dart
│   │
│   ├── data/                             # Data layer
│   │   ├── models/
│   │   │   ├── price.dart
│   │   │   ├── position.dart
│   │   │   ├── signal.dart
│   │   │   ├── agent_status.dart
│   │   │   ├── portfolio.dart
│   │   │   └── isar_models.dart
│   │   ├── repositories/
│   │   │   ├── market_repository.dart
│   │   │   ├── trading_repository.dart
│   │   │   └── settings_repository.dart
│   │   └── api/
│   │       ├── ws_client.dart
│   │       ├── rest_client.dart
│   │       └── api_endpoints.dart
│   │
│   └── utils/                            # Utilities
│       ├── formatters.dart
│       ├── responsive.dart
│       ├── accessibility.dart
│       ├── haptic.dart
│       └── constants.dart
│
├── android/
│   └── app/src/main/kotlin/.../
│       ├── AlphaStackWidget.kt           # Android home widget
│       └── MainActivity.kt
│
├── ios/
│   ├── Runner/
│   │   └── AppDelegate.swift
│   └── AlphaStackWidget/
│       ├── AlphaStackWidget.swift         # iOS home widget
│       ├── Info.plist
│       └── Assets.xcassets/
│
├── assets/
│   ├── icons/
│   ├── sounds/                           # Notification sounds
│   └── fonts/
│       ├── Inter-*.ttf
│       └── JetBrainsMono-*.ttf
│
├── test/
│   ├── unit/
│   ├── widget/
│   └── integration/
│
└── pubspec.yaml
```

---

## 18. State Management & Data Flow

### 18.1 Riverpod Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              STATE MANAGEMENT ARCHITECTURE                     │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ RIVERPOD PROVIDERS (Dependency Graph)                   │ │
│  │                                                         │ │
│  │  ┌───────────────┐    ┌───────────────┐                 │ │
│  │  │ Connectivity  │───▶│ WebSocket     │                 │ │
│  │  │ Provider      │    │ Provider      │                 │ │
│  │  └───────────────┘    └───────┬───────┘                 │ │
│  │                               │                         │ │
│  │           ┌───────────────────┼───────────────────┐     │ │
│  │           │                   │                   │     │ │
│  │           ▼                   ▼                   ▼     │ │
│  │  ┌───────────────┐  ┌───────────────┐  ┌────────────┐  │ │
│  │  │ Price Stream  │  │ Positions     │  │ Agent      │  │ │
│  │  │ Provider      │  │ Provider      │  │ Status     │  │ │
│  │  └───────┬───────┘  └───────┬───────┘  └─────┬──────┘  │ │
│  │          │                  │                 │         │ │
│  │          ▼                  ▼                 ▼         │ │
│  │  ┌───────────────┐  ┌───────────────┐  ┌────────────┐  │ │
│  │  │ Portfolio     │  │ Trading       │  │ Signal     │  │ │
│  │  │ Summary       │  │ Service       │  │ Provider   │  │ │
│  │  └───────────────┘  └───────────────┘  └────────────┘  │ │
│  │                                                         │ │
│  │  ┌───────────────────────────────────────────────────┐  │ │
│  │  │ Settings Provider (persists to SharedPreferences) │  │ │
│  │  └───────────────────────────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────┘ │
│                           │                                  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ LOCAL DATABASE (Isar)                                   │ │
│  │ ├── Price cache                                         │ │
│  │ ├── Position cache                                      │ │
│  │ ├── Trade history                                       │ │
│  │ └── Signal history                                      │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 18.2 WebSocket State Machine

```dart
// lib/data/api/ws_client.dart

enum WsState { disconnected, connecting, connected, reconnecting, failed }

class WebSocketClient extends StateNotifier<WsState> {
  WebSocketChannel? _channel;
  Timer? _heartbeatTimer;
  Timer? _reconnectTimer;
  int _reconnectAttempts = 0;
  final StreamController<Map<String, dynamic>> _messageController =
      StreamController.broadcast();

  Stream<Map<String, dynamic>> get messages => _messageController.stream;

  // ── Connection Management ──

  Future<void> connect(String url, {String? authToken}) async {
    state = WsState.connecting;

    try {
      _channel = WebSocketChannel.connect(
        Uri.parse(url),
        protocols: authToken != null ? ['auth-$authToken'] : null,
      );

      await _channel!.ready;
      state = WsState.connected;
      _reconnectAttempts = 0;

      // Start heartbeat
      _heartbeatTimer = Timer.periodic(
        const Duration(seconds: 30),
        (_) => _sendHeartbeat(),
      );

      // Listen for messages
      _channel!.stream.listen(
        (data) {
          final message = _decodeMessage(data);
          _messageController.add(message);
        },
        onError: (error) => _handleDisconnect(error),
        onDone: () => _handleDisconnect(null),
      );
    } catch (e) {
      state = WsState.failed;
      _scheduleReconnect();
    }
  }

  void _handleDisconnect(dynamic error) {
    _heartbeatTimer?.cancel();
    state = WsState.disconnected;
    _scheduleReconnect();
  }

  void _scheduleReconnect() {
    if (_reconnectAttempts >= 10) {
      state = WsState.failed;
      return;
    }

    state = WsState.reconnecting;

    // Exponential backoff with jitter
    final baseDelay = math.min(
      math.pow(2, _reconnectAttempts).toDouble(),
      30.0,
    );
    final jitter = math.Random().nextDouble() * 0.3 * baseDelay;
    final delay = Duration(milliseconds: ((baseDelay + jitter) * 1000).toInt());

    _reconnectTimer = Timer(delay, () {
      _reconnectAttempts++;
      connect(_lastUrl!, authToken: _lastAuthToken);
    });
  }

  // ── Subscription Management ──

  void subscribe(String channel) {
    _send({'type': 'subscribe', 'channel': channel});
  }

  void unsubscribe(String channel) {
    _send({'type': 'unsubscribe', 'channel': channel});
  }

  // ── Binary Protocol (for low data mode) ──

  dynamic _decodeMessage(dynamic data) {
    if (data is List<int>) {
      // MessagePack decode (binary protocol)
      return msgpack.decode(data);
    } else {
      // JSON decode (standard)
      return jsonDecode(data as String);
    }
  }

  void _send(Map<String, dynamic> message) {
    if (state != WsState.connected) return;

    final data = _useBinaryProtocol
        ? msgpack.encode(message)
        : jsonEncode(message);

    _channel!.sink.add(data);
  }
}
```

---

## 19. Performance Budget & Optimization

### 19.1 Performance Targets

| Metric | Target | Why |
|--------|--------|-----|
| **Cold start** | < 2 seconds | Trader needs dashboard fast |
| **Warm start** | < 500ms | App resume from background |
| **Chart render (60 candles)** | < 16ms (60fps) | Smooth scrolling and zooming |
| **Price update latency** | < 100ms from tick to display | Real-time feel |
| **Trade execution** | < 2 seconds from tap to confirmation | Speed matters for entries |
| **Memory usage** | < 150MB | Background-friendly, no OOM kills |
| **Battery drain** | < 5%/hour (foreground) | All-day usage |
| **App size** | < 30MB (download) | Fast install on slow networks |

### 19.2 Optimization Techniques

```dart
// Performance optimization checklist

// 1. RepaintBoundary for chart isolation
RepaintBoundary(
  child: AlphaCandlestickChart(
    candles: candles,
    // ... chart is isolated from parent rebuilds
  ),
);

// 2. Const constructors everywhere possible
const PortfolioSummaryCard(portfolio: portfolio);  // Won't rebuild if data unchanged

// 3. Selective rebuilding with Riverpod .select()
final dailyPnl = ref.watch(
  portfolioSummaryProvider.select((p) => p.dailyPnl),
);
// Only rebuilds when dailyPnl changes, not when other portfolio fields change

// 4. ListView.builder with automatic keep-alive
ListView.builder(
  itemCount: items.length,
  itemBuilder: (context, index) => _PositionCard(
    position: items[index],
    key: ValueKey(items[index].ticket),  // Stable keys for efficient diffing
  ),
);

// 5. Image caching
CachedNetworkImage(
  imageUrl: url,
  memCacheWidth: 200,   // Limit memory cache size
  placeholder: (context, url) => const ShimmerBox(),
);

// 6. Isolate for heavy computation
Future<List<Indicator>> computeIndicators(List<Candle> candles) async {
  return compute(_calculateIndicators, candles);
}

// 7. Debounce rapid updates
final debouncedPrices = ref.watch(priceStreamProvider(symbol))
    .debounceTime(const Duration(milliseconds: 50));

// 8. Lazy initialization of expensive resources
late final Isar _db = await Isar.open([CachedPriceSchema, ...]);
```

---

## 20. Development Roadmap

### Phase 1: Foundation (Weeks 1–3)

| Task | Duration | Deliverable |
|------|----------|-------------|
| Project scaffolding + theme | 3 days | Flutter project, dark theme, design system |
| Riverpod state management setup | 2 days | Provider architecture, WebSocket client |
| Biometric authentication | 2 days | Lock screen, secure storage |
| Bottom navigation shell | 1 day | 5-tab navigation |
| Basic dashboard layout | 3 days | Portfolio card, positions, watchlist |
| Isar database setup | 2 days | Offline cache schema |

### Phase 2: Core Trading (Weeks 4–6)

| Task | Duration | Deliverable |
|------|----------|-------------|
| Custom chart engine (CustomPaint) | 5 days | Candlestick chart, zoom, pan, crosshair |
| Real-time price streaming | 3 days | WebSocket → chart pipeline |
| Position management | 3 days | Position cards, P&L display, swipe actions |
| Quick trade bottom sheet | 2 days | One-tap trade execution |
| Trade confirmation flow | 2 days | Biometric + confirmation sheet |
| Order entry screen | 3 days | Full order form with SL/TP |

### Phase 3: Signals & Notifications (Weeks 7–8)

| Task | Duration | Deliverable |
|------|----------|-------------|
| Push notification setup (FCM + APNs) | 3 days | Both platforms receiving notifications |
| Notification action handlers | 2 days | BUY/SELL/DISMISS from notification |
| Signal display cards | 2 days | Confidence, entry, SL/TP |
| Notification inbox | 2 days | History, read/unread, swipe dismiss |

### Phase 4: Agent Monitor & Settings (Weeks 9–10)

| Task | Duration | Deliverable |
|------|----------|-------------|
| Agent status display | 3 days | Health bar, agent cards, pipeline flow |
| Agent detail screens | 2 days | Per-agent metrics, logs |
| Settings screens (all) | 4 days | Broker, strategy, security, notifications, data |
| Broker connection flow | 2 days | MT5 configuration, test connection |

### Phase 5: Advanced Features (Weeks 11–14)

| Task | Duration | Deliverable |
|------|----------|-------------|
| Home screen widgets (Android + iOS) | 4 days | Portfolio widget, price widget |
| Voice commands | 3 days | Speech-to-text, command parsing, TTS feedback |
| Low data mode | 2 days | Data tiers, auto-detect, manual override |
| Offline mode polish | 3 days | Sync engine, stale indicators, offline banner |
| Chart indicators (RSI, MACD, SMA) | 4 days | Sub-indicator panel, overlays |
| SMC zones on chart | 3 days | Order blocks, FVG, liquidity levels |

### Phase 6: Polish & Release (Weeks 15–16)

| Task | Duration | Deliverable |
|------|----------|-------------|
| Performance optimization | 3 days | 60fps charts, memory optimization |
| Accessibility audit | 2 days | Screen reader, contrast, touch targets |
| App store assets | 2 days | Screenshots, descriptions, icons |
| Beta testing (TestFlight + Play Console) | 5 days | Real device testing |
| Bug fixes and polish | 3 days | Final refinements |

---

## Appendix A: Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Framework** | Flutter (Dart) | Single codebase, proven in trading (Zerodha), custom chart rendering |
| **State management** | Riverpod | Type-safe, testable, excellent for reactive streams |
| **Charts** | CustomPaint (primary) + WebView fallback | Native 60fps performance, full control |
| **Navigation** | GoRouter | Declarative, deep linking support, shell routes |
| **Local database** | Isar | Fast, type-safe, reactive queries, Flutter-native |
| **Secure storage** | flutter_secure_storage | Keychain (iOS) + Keystore (Android) |
| **Push notifications** | Firebase Messaging | Unified FCM + APNs, reliable, free |
| **Biometrics** | local_auth | Official Flutter plugin, supports Face ID + fingerprint |
| **Voice** | speech_to_text + flutter_tts | In-app, works offline, full control |
| **Widgets** | home_widget | Cross-platform widget data sharing |
| **Default theme** | Dark mode | Industry standard for trading apps, reduces eye strain |
| **Offline strategy** | Isar cache + delta sync | Server-authoritative for financial data, local for reads |

## Appendix B: Notification Sound Design

| Notification Type | Sound | Vibration Pattern |
|-------------------|-------|-------------------|
| **Trade Signal (high confidence)** | Custom chime (bright) | [0, 200, 100, 200] |
| **Trade Execution** | Subtle click | [0, 100] |
| **Risk Warning** | Alert tone (urgent) | [0, 500, 200, 500] |
| **Margin Call** | Alarm (continuous until dismissed) | [0, 1000, 500, 1000] |
| **Agent Alert** | Soft notification | [0, 150] |
| **System** | Silent | None |

## Appendix C: Gesture Reference

| Gesture | Context | Action |
|---------|---------|--------|
| **Tap** | Price chart | Show crosshair at point |
| **Long press + drag** | Price chart | Move crosshair |
| **Pinch** | Price chart | Zoom in/out |
| **Horizontal drag** | Price chart | Scroll candles |
| **Double tap** | Price chart | Reset zoom |
| **Swipe left** | Position card | Close / Modify actions |
| **Swipe right** | Position card | Close all (emergency) |
| **Swipe down** | Dashboard | Refresh data |
| **Tap** | FAB | Quick trade sheet |
| **Long press FAB** | Quick trade | Last-pair quick entry |
| **Tap + hold** | Signal card | Preview chart |

---

*Architecture designed for Alpha Stack v1.0 — Institutional-grade AI trading in your pocket.*
*Mobile UI Architect · 2026-07-11*
