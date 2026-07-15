import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'screens/dashboard_screen.dart';
import 'screens/trades_screen.dart';
import 'screens/signals_screen.dart';
import 'screens/analytics_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/api_keys_screen.dart';
import 'services/api_service.dart';

class AlphaStackApp extends StatelessWidget {
  const AlphaStackApp({super.key});

  static const Color primaryDark = Color(0xFF0D1117);
  static const Color surfaceDark = Color(0xFF161B22);
  static const Color cardDark = Color(0xFF1C2128);
  static const Color borderDark = Color(0xFF30363D);
  static const Color accentGreen = Color(0xFF3FB950);
  static const Color accentRed = Color(0xFFF85149);
  static const Color accentBlue = Color(0xFF58A6FF);
  static const Color accentOrange = Color(0xFFD29922);
  static const Color textPrimary = Color(0xFFE6EDF3);
  static const Color textSecondary = Color(0xFF8B949E);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AlphaStack',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: primaryDark,
        colorScheme: const ColorScheme.dark(
          primary: accentBlue,
          secondary: accentGreen,
          surface: surfaceDark,
          error: accentRed,
          onPrimary: Colors.white,
          onSecondary: Colors.white,
          onSurface: textPrimary,
        ),
        textTheme: GoogleFonts.interTextTheme(
          ThemeData.dark().textTheme,
        ).copyWith(
          headlineLarge: GoogleFonts.inter(
            fontSize: 28,
            fontWeight: FontWeight.w700,
            color: textPrimary,
          ),
          headlineMedium: GoogleFonts.inter(
            fontSize: 22,
            fontWeight: FontWeight.w600,
            color: textPrimary,
          ),
          titleLarge: GoogleFonts.inter(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: textPrimary,
          ),
          titleMedium: GoogleFonts.inter(
            fontSize: 16,
            fontWeight: FontWeight.w500,
            color: textPrimary,
          ),
          bodyLarge: GoogleFonts.inter(
            fontSize: 16,
            color: textPrimary,
          ),
          bodyMedium: GoogleFonts.inter(
            fontSize: 14,
            color: textSecondary,
          ),
          labelLarge: GoogleFonts.inter(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            color: textPrimary,
          ),
        ),
        cardTheme: CardTheme(
          color: cardDark,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: const BorderSide(color: borderDark, width: 1),
          ),
        ),
        appBarTheme: AppBarTheme(
          backgroundColor: primaryDark,
          elevation: 0,
          centerTitle: false,
          titleTextStyle: GoogleFonts.inter(
            fontSize: 20,
            fontWeight: FontWeight.w700,
            color: textPrimary,
          ),
        ),
        bottomNavigationBarTheme: const BottomNavigationBarThemeData(
          backgroundColor: surfaceDark,
          selectedItemColor: accentBlue,
          unselectedItemColor: textSecondary,
          type: BottomNavigationBarType.fixed,
          elevation: 8,
        ),
        dividerTheme: const DividerThemeData(
          color: borderDark,
          thickness: 1,
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: surfaceDark,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(8),
            borderSide: const BorderSide(color: borderDark),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(8),
            borderSide: const BorderSide(color: borderDark),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(8),
            borderSide: const BorderSide(color: accentBlue, width: 2),
          ),
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: accentBlue,
            foregroundColor: Colors.white,
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(8),
            ),
            textStyle: GoogleFonts.inter(
              fontSize: 14,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ),
      home: const _AppBootstrap(),
    );
  }
}

/// Bootstrap widget that checks if API keys are configured.
/// Shows the API keys screen on first launch, then navigates to main app.
class _AppBootstrap extends StatefulWidget {
  const _AppBootstrap();

  @override
  State<_AppBootstrap> createState() => _AppBootstrapState();
}

class _AppBootstrapState extends State<_AppBootstrap> {
  bool? _keysConfigured;

  @override
  void initState() {
    super.initState();
    _checkKeys();
  }

  Future<void> _checkKeys() async {
    final api = ApiService();
    final configured = await api.hasStoredKeys();
    if (mounted) {
      setState(() => _keysConfigured = configured);
    }
  }

  @override
  Widget build(BuildContext context) {
    // Still loading
    if (_keysConfigured == null) {
      return const Scaffold(
        body: Center(
          child: CircularProgressIndicator(color: AlphaStackApp.accentBlue),
        ),
      );
    }

    // Keys not configured — show setup screen
    if (!_keysConfigured!) {
      return _ApiKeysSetupScreen(
        onConfigured: () {
          setState(() => _keysConfigured = true);
        },
      );
    }

    // Keys configured — show main app
    return const MainNavigation();
  }
}

/// Wrapper for the API keys screen during first-launch setup.
class _ApiKeysSetupScreen extends StatelessWidget {
  final VoidCallback onConfigured;

  const _ApiKeysSetupScreen({required this.onConfigured});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [AlphaStackApp.accentBlue, AlphaStackApp.accentGreen],
                ),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.auto_graph_rounded,
                  size: 20, color: Colors.white),
            ),
            const SizedBox(width: 10),
            const Text('Welcome to AlphaStack'),
          ],
        ),
        automaticallyImplyLeading: false,
      ),
      body: Column(
        children: [
          // Welcome message
          Container(
            width: double.infinity,
            margin: const EdgeInsets.all(16),
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  AlphaStackApp.accentBlue.withAlpha(30),
                  AlphaStackApp.accentGreen.withAlpha(15),
                ],
              ),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                  color: AlphaStackApp.accentBlue.withAlpha(60)),
            ),
            child: Column(
              children: [
                const Icon(Icons.rocket_launch_rounded,
                    size: 48, color: AlphaStackApp.accentBlue),
                const SizedBox(height: 12),
                Text(
                  'Set up your API keys',
                  style:
                      Theme.of(context).textTheme.titleLarge?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                ),
                const SizedBox(height: 8),
                Text(
                  'Connect your Binance account and configure the backend server to start trading with AI.',
                  textAlign: TextAlign.center,
                  style:
                      Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: AlphaStackApp.textSecondary,
                          ),
                ),
              ],
            ),
          ),
          // The API keys form
          Expanded(
            child: ApiKeysScreen(
              onSaved: onConfigured,
            ),
          ),
        ],
      ),
    );
  }
}

class MainNavigation extends StatefulWidget {
  const MainNavigation({super.key});

  @override
  State<MainNavigation> createState() => _MainNavigationState();
}

class _MainNavigationState extends State<MainNavigation> {
  int _currentIndex = 0;

  final List<Widget> _screens = const [
    DashboardScreen(),
    TradesScreen(),
    SignalsScreen(),
    AnalyticsScreen(),
    SettingsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (index) => setState(() => _currentIndex = index),
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.dashboard_rounded),
            activeIcon: Icon(Icons.dashboard_rounded),
            label: 'Dashboard',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.candlestick_chart_rounded),
            activeIcon: Icon(Icons.candlestick_chart_rounded),
            label: 'Trades',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.signal_cellular_alt_rounded),
            activeIcon: Icon(Icons.signal_cellular_alt_rounded),
            label: 'Signals',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.analytics_rounded),
            activeIcon: Icon(Icons.analytics_rounded),
            label: 'Analytics',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.settings_rounded),
            activeIcon: Icon(Icons.settings_rounded),
            label: 'Settings',
          ),
        ],
      ),
    );
  }
}
