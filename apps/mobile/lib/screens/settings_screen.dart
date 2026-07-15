import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app.dart';
import '../services/api_service.dart';
import '../providers/app_preferences.dart';
import 'api_keys_screen.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final biometric = ref.watch(biometricEnabledProvider);
    final notifications = ref.watch(notificationsEnabledProvider);
    final autoRefresh = ref.watch(autoRefreshProvider);

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
                  onPressed: () {},
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
            subtitle: 'https://api.alphastack.io',
            onTap: () => _showApiDialog(context, ref),
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
            onTap: () {},
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
            onTap: () {},
          ),
          _SettingsTile(
            icon: Icons.warning_rounded,
            title: 'Risk Alerts',
            subtitle: 'Drawdown & exposure warnings',
            onTap: () {},
          ),

          const SizedBox(height: 8),

          // Trading
          _SectionHeader(title: 'Trading'),
          _SettingsTile(
            icon: Icons.account_balance_rounded,
            title: 'Exchange',
            subtitle: 'Binance Futures',
            onTap: () {},
          ),
          _SettingsTile(
            icon: Icons.speed_rounded,
            title: 'Risk Parameters',
            subtitle: 'Max position size, leverage limits',
            onTap: () {},
          ),
          _SettingsTile(
            icon: Icons.timer_rounded,
            title: 'Default Timeframe',
            subtitle: '4H',
            onTap: () {},
          ),

          const SizedBox(height: 8),

          // Appearance
          _SectionHeader(title: 'Appearance'),
          _SettingsTile(
            icon: Icons.palette_rounded,
            title: 'Theme',
            subtitle: 'Dark Mode',
            onTap: () {},
          ),
          _SettingsTile(
            icon: Icons.language_rounded,
            title: 'Language',
            subtitle: 'English',
            onTap: () {},
          ),
          _SettingsTile(
            icon: Icons.attach_money_rounded,
            title: 'Currency',
            subtitle: 'USD',
            onTap: () {},
          ),

          const SizedBox(height: 8),

          // About
          _SectionHeader(title: 'About'),
          _SettingsTile(
            icon: Icons.info_outline_rounded,
            title: 'Version',
            subtitle: '1.0.0 (build 1)',
            onTap: () {},
          ),
          _SettingsTile(
            icon: Icons.description_outlined,
            title: 'Terms of Service',
            onTap: () {},
          ),
          _SettingsTile(
            icon: Icons.privacy_tip_outlined,
            title: 'Privacy Policy',
            onTap: () {},
          ),
          _SettingsTile(
            icon: Icons.help_outline_rounded,
            title: 'Help & Support',
            onTap: () {},
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

  void _showApiDialog(BuildContext context, WidgetRef ref) {
    final urlController = TextEditingController(text: 'https://api.alphastack.io');
    // Load current URL
    ApiService().baseUrl.then((url) {
      urlController.text = url;
    });

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AlphaStackApp.surfaceDark,
        title: const Text('API Endpoint'),
        content: TextField(
          decoration: const InputDecoration(
            hintText: 'http://localhost:8000/api/v1',
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
              }
              if (context.mounted) Navigator.pop(context);
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }

  void _showLogoutDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AlphaStackApp.surfaceDark,
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
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Disconnected. API keys cleared.'),
                    backgroundColor: AlphaStackApp.accentOrange,
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
