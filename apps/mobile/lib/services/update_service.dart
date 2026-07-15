import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter/foundation.dart';
import 'package:package_info_plus/package_info_plus.dart';

class UpdateInfo {
  final String latestVersion;
  final String downloadUrl;
  final String releaseNotes;
  final bool updateAvailable;

  UpdateInfo({
    required this.latestVersion,
    required this.downloadUrl,
    required this.releaseNotes,
    required this.updateAvailable,
  });
}

class UpdateService {
  static const String _owner = 'ovalentine964';
  static const String _repo = 'alphastack';

  /// Check GitHub releases for a newer version.
  static Future<UpdateInfo?> checkForUpdate() async {
    try {
      final uri = Uri.parse(
        'https://api.github.com/repos/$_owner/$_repo/releases/latest',
      );
      final response = await http.get(uri).timeout(const Duration(seconds: 10));

      if (response.statusCode != 200) return null;

      final data = jsonDecode(response.body);
      final tagName = data['tag_name'] as String? ?? '';
      final body = data['body'] as String? ?? '';
      final assets = data['assets'] as List? ?? [];

      // Find APK asset
      String? apkUrl;
      for (final asset in assets) {
        if ((asset['name'] as String? ?? '').endsWith('.apk')) {
          apkUrl = asset['browser_download_url'] as String?;
          break;
        }
      }

      if (apkUrl == null) return null;

      // Get current version
      final packageInfo = await PackageInfo.fromPlatform();
      final currentVersion = packageInfo.version;

      // Compare versions (strip 'v' prefix)
      final latestClean = tagName.replaceFirst('v', '');
      final hasUpdate = _isNewer(latestClean, currentVersion);

      return UpdateInfo(
        latestVersion: latestClean,
        downloadUrl: apkUrl,
        releaseNotes: body,
        updateAvailable: hasUpdate,
      );
    } catch (e) {
      debugPrint('Update check failed: $e');
      return null;
    }
  }

  /// Simple semver comparison: returns true if [latest] > [current].
  static bool _isNewer(String latest, String current) {
    final l = latest.split('.').map(int.tryParse).map((e) => e ?? 0).toList();
    final c = current.split('.').map(int.tryParse).map((e) => e ?? 0).toList();

    // Pad to 3 parts
    while (l.length < 3) l.add(0);
    while (c.length < 3) c.add(0);

    for (int i = 0; i < 3; i++) {
      if (l[i] > c[i]) return true;
      if (l[i] < c[i]) return false;
    }
    return false;
  }
}
