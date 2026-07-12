# AlphaStack Installation Guide

## 📥 Download

**Latest Release:** [GitHub Releases](https://github.com/ovalentine964/alphastack/releases/latest)

### Quick Install (One Command)

**Desktop — Linux / macOS:**
```bash
curl -sSL https://alphastack.app/install | bash
```

**Desktop — Windows (PowerShell as Admin):**
```powershell
irm https://alphastack.app/install.ps1 | iex
```

**Mobile — All Phones (Android + iOS):**
```bash
curl -sSL https://alphastack.app/install | bash -s -- mobile
```

---

## 🖥️ Desktop App (Windows / macOS / Linux)

### Windows
```powershell
# Option 1: Download installer
# Go to: https://github.com/ovalentine964/alphastack/releases/latest
# Download: AlphaStack-Setup-x.x.x.exe
# Double-click to install

# Option 2: Build from source
git clone https://github.com/ovalentine964/alphastack.git
cd alphastack/apps/desktop
npm install
npm run tauri build
# Installer will be in src-tauri/target/release/bundle/
```

### macOS
```bash
# Option 1: Download DMG
# Go to: https://github.com/ovalentine964/alphastack/releases/latest
# Download: AlphaStack-x.x.x.dmg
# Drag to Applications folder

# Option 2: Build from source
git clone https://github.com/ovalentine964/alphastack.git
cd alphastack/apps/desktop
npm install
npm run tauri build
# DMG will be in src-tauri/target/release/bundle/dmg/
```

### Linux
```bash
# Option 1: AppImage (universal)
# Go to: https://github.com/ovalentine964/alphastack/releases/latest
# Download: AlphaStack-x.x.x.AppImage
chmod +x AlphaStack-x.x.x.AppImage
./AlphaStack-x.x.x.AppImage

# Option 2: Build from source
git clone https://github.com/ovalentine964/alphastack.git
cd alphastack/apps/desktop
npm install
npm run tauri build
# AppImage will be in src-tauri/target/release/bundle/appimage/
```

---

## 📱 Mobile App (Android / iOS)

### Android
```bash
# Option 1: Download APK
# Go to: https://github.com/ovalentine964/alphastack/releases/latest
# Download: AlphaStack-x.x.x.apk
# Enable "Install from unknown sources" in Settings
# Tap the APK to install

# Option 2: Build from source
git clone https://github.com/ovalentine964/alphastack.git
cd alphastack/apps/mobile
flutter pub get
flutter build apk --release
# APK will be in build/app/outputs/flutter-apk/
```

### iOS
```bash
# Requires Mac with Xcode
git clone https://github.com/ovalentine964/alphastack.git
cd alphastack/apps/mobile
flutter pub get
flutter build ios --release
# Open ios/Runner.xcarchive in Xcode
# Archive and distribute via TestFlight
```

---

## 🌐 Web App

The web app runs in any browser. Access it at:
- **Production:** [https://alphastack.app](https://alphastack.app)
- **Self-hosted:** See below

### Self-Host Web App
```bash
git clone https://github.com/ovalentine964/alphastack.git
cd alphastack/apps/web
npm install
npm run build
# Output in .next/ — deploy to Vercel, Netlify, or any static host
```

---

## 🔧 Backend (Trading Engine)

The trading engine is the Python backend that powers everything.

### Quick Start
```bash
# Clone the repo
git clone https://github.com/ovalentine964/alphastack.git
cd alphastack

# Install Python dependencies
pip install -r requirements.txt

# Copy and edit config
cp config/alphastack.yaml config/alphastack.local.yaml
# Edit config/alphastack.local.yaml with your broker credentials

# Start the trading engine
python -m alphastack.main

# Or with Docker
docker-compose -f infra/docker/docker-compose.yml up -d
```

### Docker (Recommended)
```bash
# One-command start
docker-compose -f infra/docker/docker-compose.yml up -d

# Check status
docker-compose -f infra/docker/docker-compose.yml ps

# View logs
docker-compose -f infra/docker/docker-compose.yml logs -f trading-engine
```

---

## ⚙️ Configuration

After installation, configure your broker connection:

```yaml
# config/alphastack.local.yaml
broker:
  mt5:
    login: "your_mt5_login"
    password: "your_mt5_password"
    server: "FXPesa-Demo"  # or "FXPesa-Live"
  ccxt:
    exchange: "binance"
    api_key: "your_api_key"
    secret: "your_secret"

risk:
  max_drawdown_pct: 10.0
  max_daily_loss_pct: 5.0
  max_position_size: 0.01  # lots

api:
  host: "0.0.0.0"
  port: 8000
```

---

## 📊 Quick Verification

After installation, verify everything works:

```bash
# Check trading engine
curl http://localhost:8000/health

# Check web dashboard
open http://localhost:3000

# Check API docs
open http://localhost:8000/docs
```

---

## 🆘 Troubleshooting

| Issue | Solution |
|-------|----------|
| Desktop app won't start | Check system requirements (Windows 10+, macOS 12+, Ubuntu 20.04+) |
| APK won't install | Enable "Install from unknown sources" in Android Settings |
| Backend connection failed | Check `config/alphastack.local.yaml` credentials |
| Port 8000 in use | Change port in config or stop conflicting service |
| MT5 connection error | Ensure MT5 terminal is running (Windows only, or use VPS) |

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/ovalentine964/alphastack/issues)
- **Discussions:** [GitHub Discussions](https://github.com/ovalentine964/alphastack/discussions)
- **Email:** support@alphastack.app

---

*AlphaStack — Institutional-Grade AI Trading System*
