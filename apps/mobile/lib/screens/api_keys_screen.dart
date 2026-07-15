import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app.dart';
import '../services/api_service.dart';
import '../providers/connection_status.dart';

/// Provider that tracks whether API keys are configured.
final apiKeysConfiguredProvider = FutureProvider<bool>((ref) async {
  final api = ApiService();
  return await api.hasStoredKeys();
});

/// Local provider for the API keys screen connection check.
final apiKeysConnectionProvider =
    StateProvider<ConnectionStatus>((ref) => ConnectionStatus.disconnected);

/// Provider for connection status message.
final connectionMessageProvider = StateProvider<String>((ref) => '');

class ApiKeysScreen extends ConsumerStatefulWidget {
  /// Called when keys are saved successfully (used by first-launch bootstrap).
  final VoidCallback? onSaved;

  const ApiKeysScreen({super.key, this.onSaved});

  @override
  ConsumerState<ApiKeysScreen> createState() => _ApiKeysScreenState();
}

class _ApiKeysScreenState extends ConsumerState<ApiKeysScreen> {
  final _formKey = GlobalKey<FormState>();
  final _binanceKeyController = TextEditingController();
  final _binanceSecretController = TextEditingController();
  final _mimoKeyController = TextEditingController();
  final _backendUrlController = TextEditingController();

  bool _isTestnet = true;
  bool _obscureBinanceSecret = true;
  bool _obscureMimoKey = true;
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _loadExistingKeys();
  }

  Future<void> _loadExistingKeys() async {
    final api = ApiService();
    final keys = await api.getStoredApiKeys();
    final backendUrl = await api.baseUrl;

    if (mounted) {
      setState(() {
        _binanceKeyController.text = keys['binanceApiKey'] ?? '';
        _binanceSecretController.text = keys['binanceApiSecret'] ?? '';
        _mimoKeyController.text = keys['mimoApiKey'] ?? '';
        _isTestnet = keys['isTestnet'] != 'false';
        _backendUrlController.text = backendUrl;
      });
    }
  }

  @override
  void dispose() {
    _binanceKeyController.dispose();
    _binanceSecretController.dispose();
    _mimoKeyController.dispose();
    _backendUrlController.dispose();
    super.dispose();
  }

  Future<void> _saveAndVerify() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isLoading = true);
    ref.read(apiKeysConnectionProvider.notifier).state =
        ConnectionStatus.connecting;
    ref.read(connectionMessageProvider.notifier).state = 'Saving keys...';

    try {
      final api = ApiService();

      // Save backend URL
      await api.setBaseUrl(_backendUrlController.text.trim());

      // Save API keys
      await api.storeApiKeys(
        binanceApiKey: _binanceKeyController.text.trim(),
        binanceApiSecret: _binanceSecretController.text.trim(),
        mimoApiKey: _mimoKeyController.text.trim(),
        isTestnet: _isTestnet,
      );

      // Authenticate with the backend
      ref.read(connectionMessageProvider.notifier).state =
          'Authenticating with backend...';

      try {
        await api.authenticate(
          apiKey: _binanceKeyController.text.trim(),
          apiSecret: _binanceSecretController.text.trim(),
        );
      } catch (e) {
        // Auth may fail if backend isn't running — that's OK, keys are saved
        debugPrint('Auth failed (backend may be offline): $e');
      }

      // Check health
      ref.read(connectionMessageProvider.notifier).state =
          'Checking backend health...';
      final healthy = await api.checkHealth();

      if (healthy) {
        ref.read(apiKeysConnectionProvider.notifier).state =
            ConnectionStatus.connected;
        ref.read(connectionMessageProvider.notifier).state =
            'Connected to backend successfully';
      } else {
        ref.read(apiKeysConnectionProvider.notifier).state =
            ConnectionStatus.error;
        ref.read(connectionMessageProvider.notifier).state =
            'Keys saved, but backend is unreachable. It will connect when available.';
      }

      // Invalidate the configured provider so other screens know
      ref.invalidate(apiKeysConfiguredProvider);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(ref.read(connectionMessageProvider)),
            backgroundColor: healthy
                ? AlphaStackApp.accentGreen
                : AlphaStackApp.accentOrange,
          ),
        );
      }

      // Notify parent (first-launch flow)
      widget.onSaved?.call();
    } catch (e) {
      ref.read(apiKeysConnectionProvider.notifier).state =
          ConnectionStatus.error;
      ref.read(connectionMessageProvider.notifier).state = 'Error: $e';

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to save: $e'),
            backgroundColor: AlphaStackApp.accentRed,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _testConnection() async {
    setState(() => _isLoading = true);
    ref.read(apiKeysConnectionProvider.notifier).state =
        ConnectionStatus.connecting;
    ref.read(connectionMessageProvider.notifier).state =
        'Testing connection...';

    try {
      final api = ApiService();
      final healthy = await api.checkHealth();

      if (healthy) {
        ref.read(apiKeysConnectionProvider.notifier).state =
            ConnectionStatus.connected;
        ref.read(connectionMessageProvider.notifier).state =
            'Backend is reachable and healthy';
      } else {
        ref.read(apiKeysConnectionProvider.notifier).state =
            ConnectionStatus.error;
        ref.read(connectionMessageProvider.notifier).state =
            'Backend is not responding';
      }
    } catch (e) {
      ref.read(apiKeysConnectionProvider.notifier).state =
          ConnectionStatus.error;
      ref.read(connectionMessageProvider.notifier).state = 'Error: $e';
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final connStatus = ref.watch(apiKeysConnectionProvider);
    final connMessage = ref.watch(connectionMessageProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('API Keys & Connection'),
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // ── Connection Status Banner ──
            _buildStatusBanner(connStatus, connMessage),
            const SizedBox(height: 24),

            // ── Backend Server ──
            _SectionHeader(title: 'Backend Server'),
            const SizedBox(height: 8),
            _buildBackendUrlField(),
            const SizedBox(height: 8),
            _buildTestConnectionButton(),
            const SizedBox(height: 24),

            // ── Binance API Keys ──
            _SectionHeader(title: 'Binance API Keys'),
            const SizedBox(height: 4),
            Text(
              'Required for executing trades on Binance Futures.',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AlphaStackApp.textSecondary,
                  ),
            ),
            const SizedBox(height: 12),
            _buildBinanceKeyField(),
            const SizedBox(height: 12),
            _buildBinanceSecretField(),
            const SizedBox(height: 12),
            _buildTestnetToggle(),
            const SizedBox(height: 24),

            // ── MiMo API Key ──
            _SectionHeader(title: 'MiMo AI API Key'),
            const SizedBox(height: 4),
            Text(
              'Used for AI-powered trade reasoning and signal analysis.',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AlphaStackApp.textSecondary,
                  ),
            ),
            const SizedBox(height: 12),
            _buildMimoKeyField(),
            const SizedBox(height: 32),

            // ── Save Button ──
            _buildSaveButton(),
            const SizedBox(height: 16),

            // ── Help Text ──
            _buildHelpCard(),
            const SizedBox(height: 80),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusBanner(ConnectionStatus status, String message) {
    Color bgColor;
    Color borderColor;
    IconData icon;
    String title;

    switch (status) {
      case ConnectionStatus.disconnected:
        bgColor = AlphaStackApp.cardDark;
        borderColor = AlphaStackApp.borderDark;
        icon = Icons.info_outline;
        title = 'Configure your API keys to get started';
      case ConnectionStatus.connecting:
        bgColor = AlphaStackApp.cardDark;
        borderColor = AlphaStackApp.accentBlue.withAlpha(100);
        icon = Icons.sync_rounded;
        title = 'Checking connection...';
      case ConnectionStatus.authenticated:
      case ConnectionStatus.connected:
        bgColor = AlphaStackApp.accentGreen.withAlpha(20);
        borderColor = AlphaStackApp.accentGreen.withAlpha(80);
        icon = Icons.check_circle_outline;
        title = 'Connected';
      case ConnectionStatus.error:
        bgColor = AlphaStackApp.accentOrange.withAlpha(20);
        borderColor = AlphaStackApp.accentOrange.withAlpha(80);
        icon = Icons.warning_amber_rounded;
        title = 'Connection Issue';
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: borderColor),
      ),
      child: Row(
        children: [
          if (status == ConnectionStatus.connecting)
            const SizedBox(
              width: 24,
              height: 24,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: AlphaStackApp.accentBlue,
              ),
            )
          else
            Icon(icon,
                color: status == ConnectionStatus.connected
                    ? AlphaStackApp.accentGreen
                    : status == ConnectionStatus.error
                        ? AlphaStackApp.accentOrange
                        : AlphaStackApp.textSecondary,
                size: 24),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                ),
                if (message.isNotEmpty) ...[
                  const SizedBox(height: 2),
                  Text(
                    message,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: AlphaStackApp.textSecondary,
                        ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBackendUrlField() {
    return TextFormField(
      controller: _backendUrlController,
      keyboardType: TextInputType.url,
      decoration: const InputDecoration(
        labelText: 'Backend URL',
        hintText: 'http://localhost:8000/api/v1',
        prefixIcon: Icon(Icons.dns_rounded),
      ),
      validator: (value) {
        if (value == null || value.trim().isEmpty) {
          return 'Backend URL is required';
        }
        final uri = Uri.tryParse(value.trim());
        if (uri == null || !uri.hasScheme) {
          return 'Enter a valid URL (e.g., http://localhost:8000/api/v1)';
        }
        return null;
      },
    );
  }

  Widget _buildTestConnectionButton() {
    return OutlinedButton.icon(
      onPressed: _isLoading ? null : _testConnection,
      icon: const Icon(Icons.wifi_find_rounded, size: 18),
      label: const Text('Test Connection'),
      style: OutlinedButton.styleFrom(
        foregroundColor: AlphaStackApp.accentBlue,
        side: const BorderSide(color: AlphaStackApp.accentBlue),
        padding: const EdgeInsets.symmetric(vertical: 12),
      ),
    );
  }

  Widget _buildBinanceKeyField() {
    return TextFormField(
      controller: _binanceKeyController,
      decoration: const InputDecoration(
        labelText: 'API Key',
        hintText: 'Enter your Binance API key',
        prefixIcon: Icon(Icons.vpn_key_rounded),
      ),
      validator: (value) {
        if (value == null || value.trim().isEmpty) {
          return 'Binance API Key is required';
        }
        if (value.trim().length < 10) {
          return 'API key seems too short';
        }
        return null;
      },
    );
  }

  Widget _buildBinanceSecretField() {
    return TextFormField(
      controller: _binanceSecretController,
      obscureText: _obscureBinanceSecret,
      decoration: InputDecoration(
        labelText: 'API Secret',
        hintText: 'Enter your Binance API secret',
        prefixIcon: const Icon(Icons.lock_rounded),
        suffixIcon: IconButton(
          icon: Icon(
            _obscureBinanceSecret
                ? Icons.visibility_off_rounded
                : Icons.visibility_rounded,
          ),
          onPressed: () =>
              setState(() => _obscureBinanceSecret = !_obscureBinanceSecret),
        ),
      ),
      validator: (value) {
        if (value == null || value.trim().isEmpty) {
          return 'Binance API Secret is required';
        }
        if (value.trim().length < 10) {
          return 'API secret seems too short';
        }
        return null;
      },
    );
  }

  Widget _buildTestnetToggle() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AlphaStackApp.cardDark,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AlphaStackApp.borderDark),
      ),
      child: Row(
        children: [
          Icon(
            _isTestnet ? Icons.science_rounded : Icons.rocket_launch_rounded,
            color: _isTestnet ? AlphaStackApp.accentOrange : AlphaStackApp.accentGreen,
            size: 24,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _isTestnet ? 'Testnet (Demo)' : 'Live Trading',
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                ),
                const SizedBox(height: 2),
                Text(
                  _isTestnet
                      ? 'Paper trading with test funds — no real money at risk'
                      : '⚠️ Real money — trades will execute on Binance',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: _isTestnet
                            ? AlphaStackApp.textSecondary
                            : AlphaStackApp.accentRed,
                      ),
                ),
              ],
            ),
          ),
          Switch(
            value: !_isTestnet,
            onChanged: (value) {
              if (value) {
                // Show warning before enabling live trading
                showDialog(
                  context: context,
                  builder: (ctx) => AlertDialog(
                    backgroundColor: AlphaStackApp.surfaceDark,
                    title: const Text('Enable Live Trading?'),
                    content: const Text(
                      'Live trading uses real funds on Binance. '
                      'Make sure you understand the risks before proceeding.\n\n'
                      'AlphaStack is not responsible for any losses.',
                    ),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(ctx),
                        child: const Text('Cancel'),
                      ),
                      ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AlphaStackApp.accentRed,
                        ),
                        onPressed: () {
                          Navigator.pop(ctx);
                          setState(() => _isTestnet = false);
                        },
                        child: const Text('Enable Live'),
                      ),
                    ],
                  ),
                );
              } else {
                setState(() => _isTestnet = true);
              }
            },
            activeColor: AlphaStackApp.accentRed,
            inactiveThumbColor: AlphaStackApp.accentOrange,
          ),
        ],
      ),
    );
  }

  Widget _buildMimoKeyField() {
    return TextFormField(
      controller: _mimoKeyController,
      obscureText: _obscureMimoKey,
      decoration: InputDecoration(
        labelText: 'MiMo API Key',
        hintText: 'Enter your MiMo API key for AI reasoning',
        prefixIcon: const Icon(Icons.psychology_rounded),
        suffixIcon: IconButton(
          icon: Icon(
            _obscureMimoKey
                ? Icons.visibility_off_rounded
                : Icons.visibility_rounded,
          ),
          onPressed: () =>
              setState(() => _obscureMimoKey = !_obscureMimoKey),
        ),
      ),
    );
  }

  Widget _buildSaveButton() {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        onPressed: _isLoading ? null : _saveAndVerify,
        icon: _isLoading
            ? const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: Colors.white,
                ),
              )
            : const Icon(Icons.save_rounded),
        label: Text(_isLoading ? 'Saving...' : 'Save & Verify'),
        style: ElevatedButton.styleFrom(
          padding: const EdgeInsets.symmetric(vertical: 16),
        ),
      ),
    );
  }

  Widget _buildHelpCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AlphaStackApp.accentBlue.withAlpha(15),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AlphaStackApp.accentBlue.withAlpha(40)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.help_outline_rounded,
                  color: AlphaStackApp.accentBlue, size: 20),
              const SizedBox(width: 8),
              Text(
                'How to get API keys',
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                      color: AlphaStackApp.accentBlue,
                      fontWeight: FontWeight.w600,
                    ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _helpItem(
            'Binance',
            'Go to Binance → API Management → Create API. Enable Futures trading permissions.',
          ),
          const SizedBox(height: 8),
          _helpItem(
            'MiMo AI',
            'Request an API key from the AlphaStack dashboard or your admin.',
          ),
          const SizedBox(height: 8),
          _helpItem(
            'Backend',
            'The AlphaStack backend server URL. Default: http://localhost:8000/api/v1',
          ),
        ],
      ),
    );
  }

  Widget _helpItem(String title, String desc) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '• $title: ',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                fontWeight: FontWeight.w600,
                color: AlphaStackApp.textPrimary,
              ),
        ),
        Expanded(
          child: Text(
            desc,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: AlphaStackApp.textSecondary,
                ),
          ),
        ),
      ],
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader({required this.title});

  @override
  Widget build(BuildContext context) {
    return Text(
      title.toUpperCase(),
      style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: AlphaStackApp.textSecondary,
            fontWeight: FontWeight.w600,
            letterSpacing: 1.2,
            fontSize: 11,
          ),
    );
  }
}
