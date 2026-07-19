# AlphaStack Release Guide

Everything you need to ship AlphaStack to Valentine (and the world).

---

## 📋 Table of Contents

1. [Quick Release (One Command)](#-quick-release-one-command)
2. [What Gets Built](#-what-gets-built)
3. [Download the Apps](#-download-the-apps)
4. [Deploy the Web App](#-deploy-the-web-app)
5. [Manual Build (No Tag)](#-manual-build-no-tag)
6. [Troubleshooting](#-troubleshooting)

---

## 🚀 Quick Release (One Command)

```bash
# Option A: bump patch version (0.1.0 → 0.1.1)
./scripts/release.sh patch

# Option B: specify exact version
./scripts/release.sh 0.2.0

# Option C: interactive menu
./scripts/release.sh
```

This will:
1. Bump version in **all three apps** (desktop, web, mobile)
2. Commit the change
3. Create a git tag (`v0.2.0`)
4. Push to GitHub → **automatically triggers the release pipeline**

Wait ~10-15 minutes, then check [GitHub Releases](https://github.com/<owner>/alphastack/releases) for the new release with all artifacts.

---

## 🏗️ What Gets Built

When you push a `v*` tag, the `release-all.yml` workflow runs:

| Job | What | Output |
|-----|------|--------|
| `build-android` | Flutter APK | `AlphaStack-v0.2.0-android.apk` |
| `build-desktop` (×3) | Tauri for Win/Mac/Linux | `.exe` `.msi` `.dmg` `.AppImage` `.deb` |
| `build-web` | Next.js build | `AlphaStack-v0.2.0-web.tar.gz` |
| `publish` | GitHub Release | All files + SHA256 checksums |

---

## 📥 Download the Apps

### Android APK

**From GitHub Release (recommended):**
1. Go to [Releases](https://github.com/<owner>/alphastack/releases)
2. Click the latest release
3. Download `AlphaStack-vX.Y.Z-android.apk`
4. Transfer to phone and install (enable "Install unknown apps")

**From Actions (latest build):**
1. Go to [Actions → 🚀 Release All Platforms](https://github.com/<owner>/alphastack/actions/workflows/release-all.yml)
2. Click the latest run
3. Scroll to **Artifacts** section
4. Download `android-apk`

### Desktop App

**From GitHub Release:**
1. Go to [Releases](https://github.com/<owner>/alphastack/releases)
2. Click the latest release
3. Download the installer for your OS:
   - **Windows:** `.exe` or `.msi`
   - **macOS:** `.dmg`
   - **Linux:** `.AppImage` or `.deb`

**From Actions (CI build, no release):**
1. Go to [Actions → 🖥️ Build Desktop](https://github.com/<owner>/alphastack/actions/workflows/build-desktop.yml)
2. Click the latest run
3. Download `desktop-windows`, `desktop-macos`, or `desktop-linux` from Artifacts

### Web App

See [Deploy the Web App](#-deploy-the-web-app) below.

---

## 🌐 Deploy the Web App

### Option 1: Vercel (recommended)

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy from the web app directory
cd apps/web
vercel --prod
```

### Option 2: Fly.io

```bash
# From repo root (fly.toml already configured)
fly deploy --app alphastack-web
```

### Option 3: Docker

```bash
# Build
docker build -t alphastack-web -f Dockerfile .

# Run
docker run -p 3000:3000 alphastack-web
```

### Option 4: Static Export (any host)

```bash
cd apps/web

# Add to next.config.ts:  output: 'export'
npm run build

# The `out/` directory can be served by any static host
# (Nginx, Apache, S3, Cloudflare Pages, etc.)
```

---

## 🔧 Manual Build (No Tag)

If you just want to build locally without releasing:

### Android APK
```bash
cd apps/mobile
flutter pub get
flutter build apk --release
# Output: build/app/outputs/flutter-apk/app-release.apk
```

### Desktop (Tauri)
```bash
cd apps/desktop
npm install
npm run tauri build
# Output: src-tauri/target/release/bundle/
```

### Web
```bash
cd apps/web
npm install
npm run build
# Output: .next/
```

### Trigger CI Build Manually

Go to [Actions](https://github.com/<owner>/alphastack/actions) → select workflow → **Run workflow**:
- 🖥️ Build Desktop → builds for all platforms
- 🚀 Release All Platforms → full release (needs a tag or uses latest)

---

## 🔍 Troubleshooting

### Release workflow failed

1. Go to [Actions](https://github.com/<owner>/alphastack/actions/workflows/release-all.yml)
2. Click the failed run
3. Check which job failed (red ❌)
4. Click the job to see logs

### Desktop build fails on Linux

Make sure these system deps are installed (the workflow handles this, but for local builds):
```bash
sudo apt-get install -y libgtk-3-dev libwebkit2gtk-4.1-dev \
  libappindicator3-dev librsvg2-dev patchelf
```

### Flutter build fails

```bash
cd apps/mobile
flutter clean
flutter pub get
flutter build apk --release
```

### Tag already exists

```bash
# Delete local tag
git tag -d v0.2.0

# Delete remote tag
git push origin --delete v0.2.0

# Then re-run release.sh
```

### Want to re-run a failed release

Go to Actions → failed run → **Re-run all jobs**

---

## 📝 Version Scheme

We follow [Semantic Versioning](https://semver.org/):

- **Major** (1.0.0): Breaking changes
- **Minor** (0.2.0): New features, backward compatible
- **Patch** (0.1.1): Bug fixes

Pre-release tags are supported:
```bash
./scripts/release.sh 0.2.0-rc.1    # Release candidate
./scripts/release.sh 0.2.0-beta.1  # Beta
```

These will be marked as **pre-release** on GitHub automatically.

---

## 🔗 Quick Links

| What | Where |
|------|-------|
| Releases | [github.com/<owner>/alphastack/releases](https://github.com/<owner>/alphastack/releases) |
| CI Actions | [github.com/<owner>/alphastack/actions](https://github.com/<owner>/alphastack/actions) |
| Release workflow | `.github/workflows/release-all.yml` |
| Desktop CI workflow | `.github/workflows/build-desktop.yml` |
| Release script | `scripts/release.sh` |
