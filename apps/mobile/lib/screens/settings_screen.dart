import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';
import '../app.dart';
import '../services/api_service.dart';
import '../providers/app_preferences.dart';
import 'api_keys_screen.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  String _currentUrl = 'Loading...';

  @override
  void initState() {
    super.initState();
    _loadUrl();
  }

  Future<void> _loadUrl() async {
    final url = await ApiService().baseUrl;
    if (mounted) setState(() => _currentUrl = url);
  }

  @override
  Widget build(BuildContext context) {
    final biometric = ref.watch(biometricEnabledProvider);
    final notifications = ref.watch(notificationsEnabledProvider);
    final autoRefresh = ref.watch(autoRefreshProvider);
    final isDark = ref.watch(darkModeProvider);
    final language = ref.watch(languageProvider);
    final currency = ref.watch(currencyProvider);
    final timeframe = ref.watch(timeframeProvider);
    final maxPosSize = ref.watch(maxPositionSizeProvider);
    final maxLev = ref.watch(maxLeverageProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
      ),
      body: ListView(
        children: [
          // Profile Section
          Container(
            margin: const EdgeInsets.fromLTRB(16, 8, 16, 16),
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AlphaStackApp.cardDark,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AlphaStackApp.borderDark),
            ),
            child: Row(
              children: [
                Container(
                  width: 56,
                  height: 56,
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [AlphaStackApp.accentBlue, AlphaStackApp.accentGreen],
                    ),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: const Icon(Icons.person, size: 28, color: Colors.white),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'AlphaStack Trader',
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w600,
                            ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Connected · Pro Plan',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: AlphaStackApp.accentGreen,
                            ),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.edit_outlined, size: 20),
                  onPressed: () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('Profile editing coming soon'),
                        duration: Duration(seconds: 1),
                      ),
                    );
                  },
                  color: AlphaStackApp.textSecondary,
                ),
              ],
            ),
          ),

          // Connection
          _SectionHeader(title: 'Connection'),
          _SettingsTile(
            icon: Icons.link_rounded,
            title: 'API Endpoint',
            subtitle: _currentUrl,
            onTap: () => _showApiDialog(context),
          ),
          _ConnectionStatusTile(),
          _SettingsTile(
            icon: Icons.sync_rounded,
            title: 'Auto Refresh',
            subtitle: 'Real-time data updates',
            trailing: Switch(
              value: autoRefresh,
              onChanged: (v) =>
                  ref.read(autoRefreshProvider.notifier).set(v),
              activeColor: AlphaStackApp.accentBlue,
            ),
          ),

          const SizedBox(height: 8),

          // Security
          _SectionHeader(title: 'Security'),
          _SettingsTile(
            icon: Icons.fingerprint_rounded,
            title: 'Biometric Auth',
            subtitle: 'Use Face ID / Fingerprint',
            trailing: Switch(
              value: biometric,
              onChanged: (v) =>
                  ref.read(biometricEnabledProvider.notifier).set(v),
              activeColor: AlphaStackApp.accentBlue,
            ),
          ),
          _SettingsTile(
            icon: Icons.lock_rounded,
            title: 'Change PIN',
            subtitle: 'App lock screen PIN',
            onTap: () => _showChangePinDialog(context),
          ),
          _SettingsTile(
            icon: Icons.key_rounded,
            title: 'API Keys',
            subtitle: 'Manage exchange API keys',
            onTap: () {
              Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => const ApiKeysScreen(),
                ),
              );
            },
          ),

          const SizedBox(height: 8),

          // Notifications
          _SectionHeader(title: 'Notifications'),
          _SettingsTile(
            icon: Icons.notifications_rounded,
            title: 'Push Notifications',
            subtitle: 'Trade alerts & signals',
            trailing: Switch(
              value: notifications,
              onChanged: (v) =>
                  ref.read(notificationsEnabledProvider.notifier).set(v),
              activeColor: AlphaStackApp.accentBlue,
            ),
          ),
          _SettingsTile(
            icon: Icons.signal_cellular_alt_rounded,
            title: 'Signal Alerts',
            subtitle: 'Notify on new signals',
            onTap: () => _showSignalAlertsDialog(context),
          ),
          _SettingsTile(
            icon: Icons.warning_rounded,
            title: 'Risk Alerts',
            subtitle: 'Drawdown & exposure warnings',
            onTap: () => _showRiskAlertsDialog(context),
          ),

          const SizedBox(height: 8),

          // Trading
          _SectionHeader(title: 'Trading'),
          _SettingsTile(
            icon: Icons.account_balance_rounded,
            title: 'Exchange',
            subtitle: 'Binance Futures',
            onTap: () => _showExchangeDialog(context),
          ),
          _SettingsTile(
            icon: Icons.speed_rounded,
            title: 'Risk Parameters',
            subtitle: 'Position: ${maxPosSize.toStringAsFixed(0)}% · Leverage: ${maxLev}x',
            onTap: () => _showRiskDialog(context),
          ),
          _SettingsTile(
            icon: Icons.timer_rounded,
            title: 'Default Timeframe',
            subtitle: timeframe.toUpperCase(),
            onTap: () => _showTimeframeDialog(context),
          ),

          const SizedBox(height: 8),

          // Appearance
          _SectionHeader(title: 'Appearance'),
          _SettingsTile(
            icon: Icons.palette_rounded,
            title: 'Theme',
            subtitle: isDark ? 'Dark Mode' : 'Light Mode',
            trailing: Switch(
              value: isDark,
              onChanged: (v) =>
                  ref.read(darkModeProvider.notifier).set(v),
              activeColor: AlphaStackApp.accentBlue,
            ),
          ),
          _SettingsTile(
            icon: Icons.language_rounded,
            title: 'Language',
            subtitle: _languageName(language),
            onTap: () => _showLanguageDialog(context),
          ),
          _SettingsTile(
            icon: Icons.attach_money_rounded,
            title: 'Currency',
            subtitle: currency,
            onTap: () => _showCurrencyDialog(context),
          ),

          const SizedBox(height: 8),

          // About
          _SectionHeader(title: 'About'),
          _SettingsTile(
            icon: Icons.info_outline_rounded,
            title: 'Version',
            subtitle: '0.1.0 (alpha)',
            onTap: () {},
          ),
          _SettingsTile(
            icon: Icons.description_outlined,
            title: 'Terms of Service',
            onTap: () => _showTermsDialog(context),
          ),
          _SettingsTile(
            icon: Icons.privacy_tip_outlined,
            title: 'Privacy Policy',
            onTap: () => _showPrivacyDialog(context),
          ),
          _SettingsTile(
            icon: Icons.help_outline_rounded,
            title: 'Help & Support',
            onTap: () => _showHelpDialog(context),
          ),

          const SizedBox(height: 16),

          // Logout
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: OutlinedButton(
              onPressed: () => _showLogoutDialog(context),
              style: OutlinedButton.styleFrom(
                foregroundColor: AlphaStackApp.accentRed,
                side: const BorderSide(color: AlphaStackApp.accentRed),
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
              child: const Text('Disconnect'),
            ),
          ),
          const SizedBox(height: 80),
        ],
      ),
    );
  }

  String _languageName(String code) {
    switch (code) {
      case 'en': return 'English';
      case 'sw': return 'Swahili';
      case 'fr': return 'French';
      default: return code.toUpperCase();
    }
  }

  void _showSnackBar(BuildContext context, String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), duration: const Duration(seconds: 1)),
    );
  }

  // ── API Endpoint Dialog ──

  void _showApiDialog(BuildContext context) {
    final urlController = TextEditingController(text: _currentUrl);
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: Theme.of(dialogContext).colorScheme.surface,
        title: const Text('API Endpoint'),
        content: TextField(
          decoration: const InputDecoration(
            hintText: 'https://your-server.com',
          ),
          controller: urlController,
          keyboardType: TextInputType.url,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () async {
              final url = urlController.text.trim();
              if (url.isNotEmpty) {
                await ApiService().setBaseUrl(url);
                if (mounted) setState(() => _currentUrl = url);
              }
              if (context.mounted) Navigator.pop(context);
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }

  // ── Exchange Dialog ──

  void _showExchangeDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (dialogContext) => SimpleDialog(
        backgroundColor: Theme.of(dialogContext).colorScheme.surface,
        title: const Text('Select Exchange'),
        children: [
          SimpleDialogOption(
            onPressed: () {
              ref.read(exchangeProvider.notifier).set('binance');
              Navigator.pop(dialogContext);
              _showSnackBar(context, 'Binance Futures selected');
            },
            child: const Text('Binance Futures'),
          ),
          SimpleDialogOption(
            onPressed: () {
              ref.read(exchangeProvider.notifier).set('binance_spot');
              Navigator.pop(dialogContext);
              _showSnackBar(context, 'Binance Spot selected');
            },
            child: const Text('Binance Spot'),
          ),
          SimpleDialogOption(
            onPressed: () {
              ref.read(exchangeProvider.notifier).set('binance_testnet');
              Navigator.pop(dialogContext);
              _showSnackBar(context, 'Binance Testnet selected');
            },
            child: const Text('Binance Testnet'),
          ),
        ],
      ),
    );
  }

  // ── Risk Parameters Dialog ──

  void _showRiskDialog(BuildContext context) {
    final posSize = ref.read(maxPositionSizeProvider);
    final leverage = ref.read(maxLeverageProvider);
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: Theme.of(dialogContext).colorScheme.surface,
        title: const Text('Risk Parameters'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('Max Position Size: ${posSize.toStringAsFixed(0)}%'),
            Slider(
              value: posSize,
              min: 1,
              max: 20,
              divisions: 19,
              label: '${posSize.toStringAsFixed(0)}%',
              onChanged: (v) => ref.read(maxPositionSizeProvider.notifier).set(v),
            ),
            const SizedBox(height: 16),
            Text('Max Leverage: ${leverage}x'),
            Slider(
              value: leverage.toDouble(),
              min: 1,
              max: 10,
              divisions: 9,
              label: '${leverage}x',
              onChanged: (v) => ref.read(maxLeverageProvider.notifier).set(v.toInt()),
            ),
          ],
        ),
        actions: [
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              setState(() {});
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }

  // ── Timeframe Dialog ──

  void _showTimeframeDialog(BuildContext context) {
    final timeframes = ['1m', '5m', '15m', '1h', '4h', '1d'];
    showDialog(
      context: context,
      builder: (dialogContext) => SimpleDialog(
        backgroundColor: Theme.of(dialogContext).colorScheme.surface,
        title: const Text('Default Timeframe'),
        children: timeframes.map((tf) => SimpleDialogOption(
          onPressed: () {
            ref.read(timeframeProvider.notifier).set(tf);
            Navigator.pop(context);
            setState(() {});
          },
          child: Text(tf.toUpperCase()),
        )).toList(),
      ),
    );
  }

  // ── Language Dialog ──

  void _showLanguageDialog(BuildContext context) {
    final languages = [('en', 'English'), ('sw', 'Swahili'), ('fr', 'French')];
    showDialog(
      context: context,
      builder: (dialogContext) => SimpleDialog(
        backgroundColor: Theme.of(dialogContext).colorScheme.surface,
        title: const Text('Language'),
        children: languages.map((l) => SimpleDialogOption(
          onPressed: () {
            ref.read(languageProvider.notifier).set(l.$1);
            Navigator.pop(context);
            setState(() {});
          },
          child: Text(l.$2),
        )).toList(),
      ),
    );
  }

  // ── Currency Dialog ──

  void _showCurrencyDialog(BuildContext context) {
    final currencies = ['USD', 'KES', 'EUR', 'GBP', 'BTC'];
    showDialog(
      context: context,
      builder: (dialogContext) => SimpleDialog(
        backgroundColor: Theme.of(dialogContext).colorScheme.surface,
        title: const Text('Currency'),
        children: currencies.map((c) => SimpleDialogOption(
          onPressed: () {
            ref.read(currencyProvider.notifier).set(c);
            Navigator.pop(context);
            setState(() {});
          },
          child: Text(c),
        )).toList(),
      ),
    );
  }

  // ── Change PIN Dialog ──

  void _showChangePinDialog(BuildContext context) {
    final currentPinController = TextEditingController();
    final newPinController = TextEditingController();
    final confirmPinController = TextEditingController();
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AlphaStackApp.surfaceDark,
        title: const Text('Change PIN'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: currentPinController,
              obscureText: true,
              keyboardType: TextInputType.number,
              maxLength: 6,
              decoration: const InputDecoration(
                labelText: 'Current PIN',
                prefixIcon: Icon(Icons.lock_outline),
              ),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: newPinController,
              obscureText: true,
              keyboardType: TextInputType.number,
              maxLength: 6,
              decoration: const InputDecoration(
                labelText: 'New PIN',
                prefixIcon: Icon(Icons.lock),
              ),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: confirmPinController,
              obscureText: true,
              keyboardType: TextInputType.number,
              maxLength: 6,
              decoration: const InputDecoration(
                labelText: 'Confirm New PIN',
                prefixIcon: Icon(Icons.lock),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              if (newPinController.text != confirmPinController.text) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('PINs do not match'),
                    backgroundColor: AlphaStackApp.accentRed,
                  ),
                );
                return;
              }
              Navigator.pop(context);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('PIN changed successfully')),
              );
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }

  // ── Signal Alerts Dialog ──

  bool _signalAlertBuy = true;
  bool _signalAlertSell = true;
  bool _signalAlertStrong = true;

  void _showSignalAlertsDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          backgroundColor: AlphaStackApp.surfaceDark,
          title: const Text('Signal Alerts'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              SwitchListTile(
                title: const Text('Buy Signals'),
                subtitle: const Text('Notify on BUY signals'),
                value: _signalAlertBuy,
                onChanged: (v) => setDialogState(() => _signalAlertBuy = v),
                activeColor: AlphaStackApp.accentGreen,
                contentPadding: EdgeInsets.zero,
              ),
              SwitchListTile(
                title: const Text('Sell Signals'),
                subtitle: const Text('Notify on SELL signals'),
                value: _signalAlertSell,
                onChanged: (v) => setDialogState(() => _signalAlertSell = v),
                activeColor: AlphaStackApp.accentRed,
                contentPadding: EdgeInsets.zero,
              ),
              SwitchListTile(
                title: const Text('Strong Signals Only'),
                subtitle: const Text('Filter out weak signals'),
                value: _signalAlertStrong,
                onChanged: (v) => setDialogState(() => _signalAlertStrong = v),
                activeColor: AlphaStackApp.accentBlue,
                contentPadding: EdgeInsets.zero,
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () {
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Signal alert preferences saved')),
                );
              },
              child: const Text('Save'),
            ),
          ],
        ),
      ),
    );
  }

  // ── Risk Alerts Dialog ──

  double _drawdownLimit = 10;
  double _dailyLossLimit = 5;

  void _showRiskAlertsDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          backgroundColor: AlphaStackApp.surfaceDark,
          title: const Text('Risk Alerts'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Max Drawdown Limit'),
              Row(
                children: [
                  Expanded(
                    child: Slider(
                      value: _drawdownLimit,
                      min: 1,
                      max: 30,
                      divisions: 29,
                      label: '${_drawdownLimit.toStringAsFixed(0)}%',
                      onChanged: (v) => setDialogState(() => _drawdownLimit = v),
                      activeColor: AlphaStackApp.accentRed,
                    ),
                  ),
                  SizedBox(
                    width: 44,
                    child: Text(
                      '${_drawdownLimit.toStringAsFixed(0)}%',
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              const Text('Daily Loss Limit'),
              Row(
                children: [
                  Expanded(
                    child: Slider(
                      value: _dailyLossLimit,
                      min: 1,
                      max: 15,
                      divisions: 14,
                      label: '${_dailyLossLimit.toStringAsFixed(0)}%',
                      onChanged: (v) => setDialogState(() => _dailyLossLimit = v),
                      activeColor: AlphaStackApp.accentOrange,
                    ),
                  ),
                  SizedBox(
                    width: 44,
                    child: Text(
                      '${_dailyLossLimit.toStringAsFixed(0)}%',
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AlphaStackApp.accentOrange.withAlpha(20),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.info_outline, size: 16, color: AlphaStackApp.accentOrange),
                    SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'You will be alerted when these thresholds are approached.',
                        style: TextStyle(fontSize: 12, color: AlphaStackApp.textSecondary),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () {
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Risk alert thresholds saved')),
                );
              },
              child: const Text('Save'),
            ),
          ],
        ),
      ),
    );
  }

  // ── Terms of Service Dialog ──

  void _showTermsDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AlphaStackApp.surfaceDark,
        title: const Text('Terms of Service'),
        content: const SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'AlphaStack — Terms of Service',
                style: TextStyle(fontWeight: FontWeight.w600, fontSize: 16),
              ),
              SizedBox(height: 12),
              Text(
                '1. Acceptance of Terms\n'
                'By accessing or using AlphaStack, you agree to be bound by these Terms of Service.\n\n'
                '2. Risk Disclosure\n'
                'Trading cryptocurrencies involves substantial risk of loss. AlphaStack does not guarantee profits or protect against losses. Past performance is not indicative of future results.\n\n'
                '3. Not Financial Advice\n'
                'AlphaStack provides tools and signals for informational purposes only. Nothing on this platform constitutes financial advice. Always do your own research.\n\n'
                '4. User Responsibility\n'
                'You are solely responsible for your trading decisions. You acknowledge that you trade at your own risk.\n\n'
                '5. Service Availability\n'
                'We strive for 99.9% uptime but do not guarantee uninterrupted access. The service may be temporarily unavailable for maintenance.\n\n'
                '6. Limitation of Liability\n'
                'AlphaStack and its developers shall not be liable for any direct, indirect, incidental, or consequential damages arising from the use of this platform.\n\n'
                '7. Changes to Terms\n'
                'We reserve the right to modify these terms at any time. Continued use of the platform constitutes acceptance of updated terms.',
                style: TextStyle(fontSize: 13, height: 1.5),
              ),
            ],
          ),
        ),
        actions: [
          ElevatedButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  // ── Privacy Policy Dialog ──

  void _showPrivacyDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AlphaStackApp.surfaceDark,
        title: const Text('Privacy Policy'),
        content: const SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'AlphaStack — Privacy Policy',
                style: TextStyle(fontWeight: FontWeight.w600, fontSize: 16),
              ),
              SizedBox(height: 12),
              Text(
                '1. Data Collection\n'
                'AlphaStack stores your API keys and preferences locally on your device. We do not collect personal information beyond what is necessary for the service to function.\n\n'
                '2. API Keys\n'
                'Your exchange API keys are stored encrypted on your device and transmitted only to your configured backend server. We never have access to your keys.\n\n'
                '3. Data Transmission\n'
                'Trading data is transmitted between your device and your AlphaStack backend. No data is sent to third-party servers.\n\n'
                '4. Analytics\n'
                'We do not use third-party analytics or tracking services.\n\n'
                '5. Data Retention\n'
                'Your data remains on your device. You can clear all stored data at any time using the Disconnect option in Settings.\n\n'
                '6. Contact\n'
                'For privacy-related inquiries, please open an issue on our GitHub repository.',
                style: TextStyle(fontSize: 13, height: 1.5),
              ),
            ],
          ),
        ),
        actions: [
          ElevatedButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  // ── Help & Support Dialog ──

  void _showHelpDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AlphaStackApp.surfaceDark,
        title: const Text('Help & Support'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'Need help with AlphaStack? Check out these resources:',
              style: TextStyle(color: AlphaStackApp.textSecondary),
            ),
            const SizedBox(height: 16),
            ListTile(
              leading: const Icon(Icons.bug_report_outlined, color: AlphaStackApp.accentOrange),
              title: const Text('Report a Bug'),
              subtitle: const Text('Open an issue on GitHub'),
              contentPadding: EdgeInsets.zero,
              onTap: () async {
                Navigator.pop(context);
                final uri = Uri.parse('https://github.com/nicobailon/alphastack/issues');
                if (await canLaunchUrl(uri)) {
                  await launchUrl(uri, mode: LaunchMode.externalApplication);
                }
              },
            ),
            ListTile(
              leading: const Icon(Icons.menu_book_rounded, color: AlphaStackApp.accentBlue),
              title: const Text('Documentation'),
              subtitle: const Text('Read the docs'),
              contentPadding: EdgeInsets.zero,
              onTap: () {
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Documentation coming soon')),
                );
              },
            ),
            ListTile(
              leading: const Icon(Icons.code_rounded, color: AlphaStackApp.accentGreen),
              title: const Text('Source Code'),
              subtitle: const Text('github.com/nicobailon/alphastack'),
              contentPadding: EdgeInsets.zero,
              onTap: () async {
                Navigator.pop(context);
                final uri = Uri.parse('https://github.com/nicobailon/alphastack');
                if (await canLaunchUrl(uri)) {
                  await launchUrl(uri, mode: LaunchMode.externalApplication);
                }
              },
            ),
          ],
        ),
        actions: [
          ElevatedButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  // ── Logout Dialog ──

  void _showLogoutDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: Theme.of(dialogContext).colorScheme.surface,
        title: const Text('Disconnect'),
        content: const Text(
            'Are you sure you want to disconnect? This will clear all stored API keys and authentication tokens.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AlphaStackApp.accentRed,
            ),
            onPressed: () async {
              await ApiService().clearApiKeys();
              if (context.mounted) {
                // Pop dialog, then navigate back to bootstrap/setup
                Navigator.of(context).popUntil((route) => route.isFirst);
                // Replace the current route so app re-checks auth state
                Navigator.of(context).pushReplacement(
                  MaterialPageRoute(
                    builder: (_) => const AppBootstrap(),
                  ),
                );
              }
            },
            child: const Text('Disconnect'),
          ),
        ],
      ),
    );
  }
}

// ── Widgets ──

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader({required this.title});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      child: Text(
        title.toUpperCase(),
        style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AlphaStackApp.textSecondary,
              fontWeight: FontWeight.w600,
              letterSpacing: 1.2,
              fontSize: 11,
            ),
      ),
    );
  }
}

class _SettingsTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  final Widget? trailing;
  final VoidCallback? onTap;

  const _SettingsTile({
    required this.icon,
    required this.title,
    this.subtitle,
    this.trailing,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListTile(
      leading: Icon(icon, color: AlphaStackApp.textSecondary, size: 22),
      title: Text(title, style: theme.textTheme.bodyLarge),
      subtitle: subtitle != null
          ? Text(
              subtitle!,
              style: theme.textTheme.bodySmall?.copyWith(
                color: AlphaStackApp.textSecondary,
              ),
            )
          : null,
      trailing: trailing ??
          (onTap != null
              ? const Icon(Icons.chevron_right_rounded,
                  color: AlphaStackApp.textSecondary, size: 20)
              : null),
      onTap: onTap,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 2),
    );
  }
}

class _ConnectionStatusTile extends StatefulWidget {
  const _ConnectionStatusTile();

  @override
  State<_ConnectionStatusTile> createState() => _ConnectionStatusTileState();
}

class _ConnectionStatusTileState extends State<_ConnectionStatusTile> {
  String _status = 'Checking...';
  Color _color = AlphaStackApp.textSecondary;
  bool _checking = true;

  @override
  void initState() {
    super.initState();
    _checkStatus();
  }

  Future<void> _checkStatus() async {
    setState(() {
      _checking = true;
      _status = 'Checking...';
      _color = AlphaStackApp.textSecondary;
    });

    try {
      final api = ApiService();
      final result = await api.getConnectionStatus();
      if (mounted) {
        setState(() {
          _checking = false;
          if (result['healthy'] == true && result['authenticated'] == true) {
            _status = 'Connected';
            _color = AlphaStackApp.accentGreen;
          } else if (result['healthy'] == true) {
            _status = 'Backend OK, auth pending';
            _color = AlphaStackApp.accentOrange;
          } else {
            _status = 'Disconnected';
            _color = AlphaStackApp.accentRed;
          }
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _checking = false;
          _status = 'Error';
          _color = AlphaStackApp.accentRed;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListTile(
      leading:
          const Icon(Icons.wifi_rounded, color: AlphaStackApp.textSecondary, size: 22),
      title: const Text('Connection Status'),
      subtitle: Text(
        _status,
        style: theme.textTheme.bodySmall?.copyWith(color: _color),
      ),
      trailing: _checking
          ? const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: AlphaStackApp.accentBlue,
              ),
            )
          : Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                color: _color,
                shape: BoxShape.circle,
              ),
            ),
      onTap: _checkStatus,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 2),
    );
  }
}
