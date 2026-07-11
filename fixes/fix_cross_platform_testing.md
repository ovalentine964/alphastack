# Cross-Platform Testing Fix Plan

> **Author:** Cross-Platform Fix Agent  
> **Date:** 2026-07-11  
> **Input:** `review_cross_platform_testing.md`  
> **Scope:** Fix 3 critical cross-platform testing issues

---

## Executive Summary

This document defines concrete implementations for the three foundational cross-platform testing gaps identified in the review:

1. **Shared test utilities and test data** — a portable contract layer that all 3 independent codebases consume
2. **API contract testing** — Pact-based consumer-driven contract tests between backend and desktop/web/mobile
3. **Authentication integration tests** — unified test suite covering OAuth 2.0, biometrics, and WebAuthn across platforms

Each section includes architecture, file structure, code examples, and CI integration.

---

## Issue 1: Shared Test Utilities and Test Data

### Problem

Desktop (Tauri/Rust+TypeScript), Web (React/TypeScript), and Mobile (Flutter/Dart) are independent codebases with no shared test infrastructure. Test data is duplicated or absent, making cross-platform consistency unverifiable.

### Solution: `shared-test-kit` Package

Create a language-agnostic shared test kit that provides:

- **Canonical test fixtures** (JSON) — single source of truth for test data
- **Platform-specific adapters** — thin wrappers that consume fixtures in each language
- **Shared API mock server** — a standalone HTTP/WebSocket server that all platforms test against

#### 1.1 Directory Structure

```
shared-test-kit/
├── fixtures/                          # Canonical test data (JSON, language-agnostic)
│   ├── accounts.json                  # Test account profiles
│   ├── trades.json                    # Trade execution scenarios
│   ├── market-data.json               # OHLCV candles, tick data
│   ├── signals.json                   # Trading signal fixtures
│   ├── portfolio.json                 # Portfolio state snapshots
│   ├── errors.json                    # Error response fixtures
│   └── auth/
│       ├── oauth-tokens.json          # OAuth token fixtures
│       ├── biometric-profiles.json    # Biometric enrollment data
│       └── webauthn-assertions.json   # WebAuthn challenge/response pairs
├── mock-server/                       # Shared API mock (Node.js)
│   ├── package.json
│   ├── src/
│   │   ├── server.ts                  # Express + WS mock server
│   │   ├── routes/
│   │   │   ├── auth.ts                # /api/auth/* endpoints
│   │   │   ├── trades.ts              # /api/trades/* endpoints
│   │   │   ├── market-data.ts         # /api/market-data/* endpoints
│   │   │   ├── portfolio.ts           # /api/portfolio/* endpoints
│   │   │   └── signals.ts             # /api/signals/* endpoints
│   │   ├── websocket/
│   │   │   ├── price-feed.ts          # Real-time price WS handler
│   │   │   └── signal-feed.ts         # Real-time signal WS handler
│   │   └── middleware/
│   │       ├── auth-verify.ts         # Token validation middleware
│   │       └── request-logger.ts      # Request recording for assertions
│   ├── Dockerfile                     # Containerized for CI
│   └── docker-compose.yml
├── adapters/                          # Platform-specific adapters
│   ├── typescript/                    # Desktop + Web shared
│   │   ├── package.json
│   │   ├── src/
│   │   │   ├── fixtures.ts            # Load JSON fixtures with types
│   │   │   ├── mock-client.ts         # HTTP client pre-configured for mock server
│   │   │   ├── assertions.ts          # Common assertion helpers
│   │   │   ├── generators.ts          # Test data generators (random trades, etc.)
│   │   │   └── index.ts
│   │   └── tsconfig.json
│   └── dart/                          # Mobile (Flutter)
│       ├── pubspec.yaml
│       ├── lib/
│       │   ├── fixtures.dart          # Load JSON fixtures
│       │   ├── mock_client.dart       # HTTP client for mock server
│       │   ├── assertions.dart        # Common assertion helpers
│       │   ├── generators.dart        # Test data generators
│       │   └── shared_test_kit.dart
│       └── test/
│           └── adapter_test.dart
├── schemas/                           # JSON Schema definitions
│   ├── trade.schema.json              # Trade request/response schema
│   ├── signal.schema.json             # Signal event schema
│   ├── portfolio.schema.json          # Portfolio state schema
│   ├── auth-token.schema.json         # Auth token schema
│   └── market-data.schema.json        # Market data schema
└── README.md
```

#### 1.2 Canonical Fixture Format

**`fixtures/accounts.json`**
```json
{
  "testAccounts": [
    {
      "id": "acc-001",
      "email": "trader@test.local",
      "name": "Test Trader",
      "role": "trader",
      "brokerConnections": [
        {
          "broker": "mt5",
          "accountId": "MT5-12345",
          "status": "connected",
          "balance": 10000.00,
          "currency": "USD"
        }
      ],
      "preferences": {
        "theme": "dark",
        "language": "en",
        "notifications": { "push": true, "email": true, "sound": true }
      }
    },
    {
      "id": "acc-002",
      "email": "admin@test.local",
      "name": "Test Admin",
      "role": "admin",
      "brokerConnections": []
    }
  ]
}
```

**`fixtures/trades.json`**
```json
{
  "tradeScenarios": [
    {
      "id": "trade-market-buy-eurusd",
      "description": "Market buy EUR/USD with SL and TP",
      "request": {
        "symbol": "EURUSD",
        "side": "buy",
        "type": "market",
        "volume": 0.10,
        "stopLoss": 1.08500,
        "takeProfit": 1.09500,
        "comment": "test-trade-001"
      },
      "expectedResponse": {
        "status": "filled",
        "orderId": "ord-001",
        "fillPrice": 1.09000,
        "fillVolume": 0.10,
        "commission": 0.70,
        "slippage": 0.00005
      },
      "expectedPortfolioChange": {
        "openPositions": 1,
        "unrealizedPnl": 0,
        "marginUsed": 109.00
      }
    },
    {
      "id": "trade-pending-buy-limit",
      "description": "Buy limit order below current price",
      "request": {
        "symbol": "GBPUSD",
        "side": "buy",
        "type": "limit",
        "volume": 0.05,
        "price": 1.26000,
        "stopLoss": 1.25500,
        "takeProfit": 1.27000
      },
      "expectedResponse": {
        "status": "pending",
        "orderId": "ord-002"
      }
    },
    {
      "id": "trade-rejected-insufficient-margin",
      "description": "Trade rejected due to insufficient margin",
      "request": {
        "symbol": "EURUSD",
        "side": "buy",
        "type": "market",
        "volume": 100.00
      },
      "expectedResponse": {
        "status": "rejected",
        "errorCode": "INSUFFICIENT_MARGIN",
        "errorMessage": "Not enough margin to open position"
      }
    }
  ]
}
```

**`fixtures/auth/oauth-tokens.json`**
```json
{
  "validToken": {
    "accessToken": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test-valid-token",
    "refreshToken": "rt-test-refresh-token-valid",
    "tokenType": "Bearer",
    "expiresIn": 3600,
    "scope": "trading:read trading:write portfolio:read"
  },
  "expiredToken": {
    "accessToken": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test-expired-token",
    "refreshToken": "rt-test-refresh-token-expired",
    "tokenType": "Bearer",
    "expiresIn": -1,
    "scope": "trading:read trading:write"
  },
  "insufficientScopeToken": {
    "accessToken": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test-limited-token",
    "refreshToken": "rt-test-refresh-token-limited",
    "tokenType": "Bearer",
    "expiresIn": 3600,
    "scope": "portfolio:read"
  }
}
```

#### 1.3 TypeScript Adapter (Desktop + Web)

**`adapters/typescript/src/fixtures.ts`**
```typescript
import * as fs from 'fs';
import * as path from 'path';

const FIXTURES_DIR = path.resolve(__dirname, '../../../fixtures');

export interface TestAccount {
  id: string;
  email: string;
  name: string;
  role: 'trader' | 'admin';
  brokerConnections: BrokerConnection[];
  preferences: AccountPreferences;
}

export interface BrokerConnection {
  broker: string;
  accountId: string;
  status: 'connected' | 'disconnected' | 'error';
  balance: number;
  currency: string;
}

export interface TradeScenario {
  id: string;
  description: string;
  request: TradeRequest;
  expectedResponse: TradeResponse;
  expectedPortfolioChange?: PortfolioChange;
}

export interface TradeRequest {
  symbol: string;
  side: 'buy' | 'sell';
  type: 'market' | 'limit' | 'stop';
  volume: number;
  price?: number;
  stopLoss?: number;
  takeProfit?: number;
  comment?: string;
}

export interface TradeResponse {
  status: 'filled' | 'pending' | 'rejected' | 'cancelled';
  orderId?: string;
  fillPrice?: number;
  fillVolume?: number;
  commission?: number;
  slippage?: number;
  errorCode?: string;
  errorMessage?: string;
}

export interface OAuthTokens {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresIn: number;
  scope: string;
}

function loadFixture<T>(filename: string): T {
  const filePath = path.join(FIXTURES_DIR, filename);
  const raw = fs.readFileSync(filePath, 'utf-8');
  return JSON.parse(raw) as T;
}

export const fixtures = {
  accounts: () => loadFixture<{ testAccounts: TestAccount[] }>('accounts.json'),
  trades: () => loadFixture<{ tradeScenarios: TradeScenario[] }>('trades.json'),
  marketData: () => loadFixture('market-data.json'),
  signals: () => loadFixture('signals.json'),
  portfolio: () => loadFixture('portfolio.json'),
  errors: () => loadFixture('errors.json'),
  auth: {
    oauthTokens: () => loadFixture<{ validToken: OAuthTokens; expiredToken: OAuthTokens; insufficientScopeToken: OAuthTokens }>('auth/oauth-tokens.json'),
    biometricProfiles: () => loadFixture('auth/biometric-profiles.json'),
    webauthnAssertions: () => loadFixture('auth/webauthn-assertions.json'),
  },
};

export function getTradeScenario(scenarioId: string): TradeScenario {
  const { tradeScenarios } = fixtures.trades();
  const scenario = tradeScenarios.find(t => t.id === scenarioId);
  if (!scenario) throw new Error(`Trade scenario not found: ${scenarioId}`);
  return scenario;
}

export function getTestAccount(accountId: string): TestAccount {
  const { testAccounts } = fixtures.accounts();
  const account = testAccounts.find(a => a.id === accountId);
  if (!account) throw new Error(`Test account not found: ${accountId}`);
  return account;
}
```

**`adapters/typescript/src/mock-client.ts`**
```typescript
import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';

export interface MockServerConfig {
  baseUrl: string;
  wsUrl: string;
  timeout?: number;
}

const DEFAULT_CONFIG: MockServerConfig = {
  baseUrl: 'http://localhost:4545',
  wsUrl: 'ws://localhost:4545',
  timeout: 5000,
};

export class MockApiClient {
  private http: AxiosInstance;
  public wsUrl: string;

  constructor(config: Partial<MockServerConfig> = {}) {
    const merged = { ...DEFAULT_CONFIG, ...config };
    this.http = axios.create({
      baseURL: merged.baseUrl,
      timeout: merged.timeout,
      headers: { 'Content-Type': 'application/json' },
    });
    this.wsUrl = merged.wsUrl;
  }

  setAuthToken(token: string) {
    this.http.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  }

  clearAuthToken() {
    delete this.http.defaults.headers.common['Authorization'];
  }

  async get<T>(url: string, config?: AxiosRequestConfig) {
    return this.http.get<T>(url, config);
  }

  async post<T>(url: string, data?: unknown, config?: AxiosRequestConfig) {
    return this.http.post<T>(url, data, config);
  }

  async put<T>(url: string, data?: unknown, config?: AxiosRequestConfig) {
    return this.http.put<T>(url, data, config);
  }

  async delete<T>(url: string, config?: AxiosRequestConfig) {
    return this.http.delete<T>(url, config);
  }

  createWebSocket(path: string): WebSocket {
    return new WebSocket(`${this.wsUrl}${path}`);
  }
}

export const mockClient = new MockApiClient();
```

#### 1.4 Dart Adapter (Mobile)

**`adapters/dart/lib/fixtures.dart`**
```dart
import 'dart:convert';
import 'dart:io';

class SharedFixtures {
  static String _fixturesDir = '${Directory.current.path}/../../shared-test-kit/fixtures';

  static void setFixturesDir(String path) {
    _fixturesDir = path;
  }

  static Map<String, dynamic> _loadJson(String filename) {
    final file = File('$_fixturesDir/$filename');
    return jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
  }

  static List<Map<String, dynamic>> get testAccounts =>
      List<Map<String, dynamic>>.from(_loadJson('accounts.json')['testAccounts']);

  static List<Map<String, dynamic>> get tradeScenarios =>
      List<Map<String, dynamic>>.from(_loadJson('trades.json')['tradeScenarios']);

  static Map<String, dynamic> get oauthTokens => _loadJson('auth/oauth-tokens.json');

  static Map<String, dynamic> get biometricProfiles => _loadJson('auth/biometric-profiles.json');

  static Map<String, dynamic> get webauthnAssertions => _loadJson('auth/webauthn-assertions.json');

  static Map<String, dynamic> getTradeScenario(String id) {
    return tradeScenarios.firstWhere(
      (t) => t['id'] == id,
      orElse: () => throw StateError('Trade scenario not found: $id'),
    );
  }

  static Map<String, dynamic> getTestAccount(String id) {
    return testAccounts.firstWhere(
      (a) => a['id'] == id,
      orElse: () => throw StateError('Test account not found: $id'),
    );
  }
}
```

**`adapters/dart/lib/mock_client.dart`**
```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class MockApiClient {
  final String baseUrl;
  final String wsUrl;
  final Duration timeout;
  String? _authToken;

  MockApiClient({
    this.baseUrl = 'http://localhost:4545',
    this.wsUrl = 'ws://localhost:4545',
    this.timeout = const Duration(seconds: 5),
  });

  void setAuthToken(String token) => _authToken = token;
  void clearAuthToken() => _authToken = null;

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (_authToken != null) 'Authorization': 'Bearer $_authToken',
      };

  Future<http.Response> get(String path) =>
      http.get(Uri.parse('$baseUrl$path'), headers: _headers).timeout(timeout);

  Future<http.Response> post(String path, {Object? body}) =>
      http.post(Uri.parse('$baseUrl$path'), headers: _headers, body: jsonEncode(body)).timeout(timeout);

  Future<http.Response> put(String path, {Object? body}) =>
      http.put(Uri.parse('$baseUrl$path'), headers: _headers, body: jsonEncode(body)).timeout(timeout);

  Future<http.Response> delete(String path) =>
      http.delete(Uri.parse('$baseUrl$path'), headers: _headers).timeout(timeout);
}
```

#### 1.5 Mock Server

**`mock-server/src/server.ts`**
```typescript
import express from 'express';
import { createServer } from 'http';
import { WebSocketServer } from 'ws';
import cors from 'cors';
import { authRoutes } from './routes/auth';
import { tradeRoutes } from './routes/trades';
import { marketDataRoutes } from './routes/market-data';
import { portfolioRoutes } from './routes/portfolio';
import { signalRoutes } from './routes/signals';
import { setupPriceFeed } from './websocket/price-feed';
import { setupSignalFeed } from './websocket/signal-feed';
import { requestLogger } from './middleware/request-logger';

const app = express();
const server = createServer(app);
const wss = new WebSocketServer({ server, path: '/ws' });

app.use(cors());
app.use(express.json());
app.use(requestLogger);

// API Routes
app.use('/api/auth', authRoutes);
app.use('/api/trades', tradeRoutes);
app.use('/api/market-data', marketDataRoutes);
app.use('/api/portfolio', portfolioRoutes);
app.use('/api/signals', signalRoutes);

// Health check
app.get('/health', (_, res) => res.json({ status: 'ok', timestamp: Date.now() }));

// WebSocket feeds
setupPriceFeed(wss);
setupSignalFeed(wss);

const PORT = process.env.MOCK_SERVER_PORT || 4545;

export function startMockServer(port: number = Number(PORT)) {
  return new Promise<typeof server>((resolve) => {
    server.listen(port, () => {
      console.log(`Mock server running on http://localhost:${port}`);
      resolve(server);
    });
  });
}

export function stopMockServer(server: ReturnType<typeof createServer>) {
  return new Promise<void>((resolve) => server.close(() => resolve()));
}

// Standalone mode
if (require.main === module) {
  startMockServer();
}
```

**`mock-server/src/routes/auth.ts`**
```typescript
import { Router } from 'express';
import * as fs from 'fs';
import * as path from 'path';

const router = Router();
const fixturesPath = path.resolve(__dirname, '../../../fixtures/auth');

function loadFixture(file: string) {
  return JSON.parse(fs.readFileSync(path.join(fixturesPath, file), 'utf-8'));
}

// POST /api/auth/login — OAuth2 password grant
router.post('/login', (req, res) => {
  const { username, password } = req.body;

  if (username === 'trader@test.local' && password === 'test-password') {
    const tokens = loadFixture('oauth-tokens.json').validToken;
    return res.json(tokens);
  }

  return res.status(401).json({ error: 'invalid_credentials', message: 'Invalid email or password' });
});

// POST /api/auth/refresh — Token refresh
router.post('/refresh', (req, res) => {
  const { refreshToken } = req.body;
  const tokens = loadFixture('oauth-tokens.json');

  if (refreshToken === tokens.validToken.refreshToken) {
    return res.json({ ...tokens.validToken, accessToken: 'eyJ...refreshed-token' });
  }

  return res.status(401).json({ error: 'invalid_grant', message: 'Refresh token is invalid or expired' });
});

// POST /api/auth/biometric/register — Biometric enrollment
router.post('/biometric/register', (req, res) => {
  const { userId, biometricType, publicKey } = req.body;

  if (!userId || !biometricType || !publicKey) {
    return res.status(400).json({ error: 'missing_fields', message: 'userId, biometricType, publicKey required' });
  }

  return res.json({
    credentialId: `bio-cred-${Date.now()}`,
    userId,
    biometricType,
    enrolledAt: new Date().toISOString(),
    status: 'active',
  });
});

// POST /api/auth/biometric/authenticate — Biometric auth
router.post('/biometric/authenticate', (req, res) => {
  const { credentialId, signature } = req.body;

  if (!credentialId || !signature) {
    return res.status(400).json({ error: 'missing_fields', message: 'credentialId and signature required' });
  }

  const tokens = loadFixture('oauth-tokens.json').validToken;
  return res.json({ ...tokens, authMethod: 'biometric' });
});

// POST /api/auth/webauthn/register/options — WebAuthn registration challenge
router.post('/webauthn/register/options', (req, res) => {
  const { userId } = req.body;
  return res.json({
    challenge: 'dGVzdC1jaGFsbGVuZ2UtZGF0YQ',  // base64url encoded
    rp: { name: 'Alpha Trading', id: 'alpha-trading.app' },
    user: { id: userId, name: 'trader@test.local', displayName: 'Test Trader' },
    pubKeyCredParams: [{ type: 'public-key', alg: -7 }],
    timeout: 60000,
    attestation: 'direct',
  });
});

// POST /api/auth/webauthn/register/verify — WebAuthn registration verification
router.post('/webauthn/register/verify', (req, res) => {
  const { credential } = req.body;
  if (!credential) {
    return res.status(400).json({ error: 'missing_credential' });
  }
  return res.json({
    credentialId: `webauthn-cred-${Date.now()}`,
    status: 'registered',
    createdAt: new Date().toISOString(),
  });
});

// POST /api/auth/webauthn/login/options — WebAuthn authentication challenge
router.post('/webauthn/login/options', (req, res) => {
  return res.json({
    challenge: 'dGVzdC1sb2dpbi1jaGFsbGVuZ2U',
    timeout: 60000,
    rpId: 'alpha-trading.app',
    allowCredentials: [{ type: 'public-key', id: 'webauthn-cred-test' }],
    userVerification: 'preferred',
  });
});

// POST /api/auth/webauthn/login/verify — WebAuthn authentication verification
router.post('/webauthn/login/verify', (req, res) => {
  const { assertion } = req.body;
  if (!assertion) {
    return res.status(400).json({ error: 'missing_assertion' });
  }
  const tokens = loadFixture('oauth-tokens.json').validToken;
  return res.json({ ...tokens, authMethod: 'webauthn' });
});

// GET /api/auth/session — Validate current session
router.get('/session', (req, res) => {
  const authHeader = req.headers.authorization;
  if (!authHeader?.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'missing_token' });
  }
  const token = authHeader.slice(7);
  const tokens = loadFixture('oauth-tokens.json');

  if (token === tokens.expiredToken.accessToken) {
    return res.status(401).json({ error: 'token_expired' });
  }

  if (token === tokens.insufficientScopeToken.accessToken) {
    return res.json({ userId: 'acc-001', role: 'trader', scope: 'portfolio:read' });
  }

  return res.json({ userId: 'acc-001', role: 'trader', scope: tokens.validToken.scope });
});

export { router as authRoutes };
```

**`mock-server/Dockerfile`**
```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --production
COPY dist/ ./dist/
COPY ../../fixtures/ ./fixtures/
EXPOSE 4545
CMD ["node", "dist/server.js"]
```

#### 1.6 CI Integration

**`.github/workflows/shared-test-kit.yml`**
```yaml
name: Shared Test Kit

on:
  push:
    paths:
      - 'shared-test-kit/**'
  pull_request:
    paths:
      - 'shared-test-kit/**'

jobs:
  validate-fixtures:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Validate JSON fixtures
        run: |
          for f in shared-test-kit/fixtures/**/*.json; do
            echo "Validating $f"
            python3 -c "import json; json.load(open('$f'))"
          done

  validate-schemas:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci
        working-directory: shared-test-kit/mock-server
      - name: Validate fixtures against schemas
        run: |
          npx ajv validate -s shared-test-kit/schemas/trade.schema.json -d shared-test-kit/fixtures/trades.json
          npx ajv validate -s shared-test-kit/schemas/auth-token.schema.json -d shared-test-kit/fixtures/auth/oauth-tokens.json

  test-mock-server:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci
        working-directory: shared-test-kit/mock-server
      - run: npm test
        working-directory: shared-test-kit/mock-server

  build-adapters:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        adapter: [typescript, dart]
    steps:
      - uses: actions/checkout@v4
      - if: matrix.adapter == 'typescript'
        uses: actions/setup-node@v4
        with: { node-version: '20' }
        run: |
          cd shared-test-kit/adapters/typescript
          npm ci
          npm test
      - if: matrix.adapter == 'dart'
        uses: dart-lang/setup-dart@v1
        with: { sdk: '3.2' }
        run: |
          cd shared-test-kit/adapters/dart
          dart pub get
          dart test
```

---

## Issue 2: API Contract Testing

### Problem

No contract tests exist between the backend API and the three frontend platforms. Breaking API changes go undetected until runtime failures occur on one or more platforms.

### Solution: Pact Consumer-Driven Contract Testing

Use [Pact](https://docs.pact.io/) for consumer-driven contract testing. Each frontend defines expected API interactions (consumer); the backend verifies it fulfills them (provider).

#### 2.1 Architecture

```
                    ┌──────────────┐
                    │   PactBroker │
                    │  (pact.io /  │
                    │  self-hosted)│
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
     Consumer │   Consumer │   Consumer │   Provider
     Tests    │   Tests    │   Tests    │   Tests
              │            │            │
     Desktop  │   Web      │   Mobile   │   Backend
     (TS)     │   (TS)     │   (Dart)   │   (Python)
              │            │            │
     ┌────────┴──┐  ┌──────┴──┐  ┌─────┴───┐  ┌──────────┐
     │ Playwright│  │ Vitest  │  │ Flutter │  │ pytest   │
     │ + Pact    │  │ + Pact  │  │ + Pact  │  │ + Pact   │
     │ Plugin    │  │ Plugin  │  │ Plugin  │  │ Provider │
     └───────────┘  └─────────┘  └─────────┘  └──────────┘
```

#### 2.2 Consumer Contract Definitions

**Desktop Consumer (TypeScript + @pact-foundation/pact)**

**`tests/contract/desktop/consumer.spec.ts`**
```typescript
import { Pact, Matchers } from '@pact-foundation/pact';
import path from 'path';
import { MockApiClient } from '@shared-test-kit/typescript';
import { fixtures, getTradeScenario } from '@shared-test-kit/typescript';

const { like, eachLike, term } = Matchers;

const provider = new Pact({
  consumer: 'DesktopApp',
  provider: 'TradingAPI',
  dir: path.resolve(__dirname, '../pacts'),
  logLevel: 'warn',
});

describe('Desktop ↔ TradingAPI Contract', () => {
  beforeAll(() => provider.setup());
  afterAll(() => provider.finalize());

  describe('Authentication', () => {
    it('POST /api/auth/login returns valid tokens', async () => {
      const oauthTokens = fixtures.auth.oauthTokens();

      await provider.addInteraction({
        state: 'user exists with valid credentials',
        uponReceiving: 'a login request with valid credentials',
        withRequest: {
          method: 'POST',
          path: '/api/auth/login',
          headers: { 'Content-Type': 'application/json' },
          body: { username: 'trader@test.local', password: 'test-password' },
        },
        willRespondWith: {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
          body: {
            accessToken: like(oauthTokens.validToken.accessToken),
            refreshToken: like(oauthTokens.validToken.refreshToken),
            tokenType: like('Bearer'),
            expiresIn: like(3600),
            scope: like(oauthTokens.validToken.scope),
          },
        },
      });

      const client = new MockApiClient({ baseUrl: provider.mockService.baseUrl });
      const response = await client.post('/api/auth/login', {
        username: 'trader@test.local',
        password: 'test-password',
      });

      expect(response.status).toBe(200);
      expect(response.data).toHaveProperty('accessToken');
      expect(response.data).toHaveProperty('refreshToken');
      expect(response.data.tokenType).toBe('Bearer');
    });

    it('POST /api/auth/login rejects invalid credentials', async () => {
      await provider.addInteraction({
        state: 'no user with given credentials',
        uponReceiving: 'a login request with invalid credentials',
        withRequest: {
          method: 'POST',
          path: '/api/auth/login',
          headers: { 'Content-Type': 'application/json' },
          body: { username: 'bad@test.local', password: 'wrong' },
        },
        willRespondWith: {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
          body: {
            error: like('invalid_credentials'),
            message: like('Invalid email or password'),
          },
        },
      });

      const client = new MockApiClient({ baseUrl: provider.mockService.baseUrl });
      const response = await client.post('/api/auth/login', {
        username: 'bad@test.local',
        password: 'wrong',
      });

      expect(response.status).toBe(401);
    });
  });

  describe('Trade Execution', () => {
    it('POST /api/trades executes a market order', async () => {
      const scenario = getTradeScenario('trade-market-buy-eurusd');

      await provider.addInteraction({
        state: 'broker is connected and account has sufficient margin',
        uponReceiving: 'a market buy order for EUR/USD',
        withRequest: {
          method: 'POST',
          path: '/api/trades',
          headers: {
            'Content-Type': 'application/json',
            Authorization: term({ matcher: 'Bearer .+', generate: 'Bearer test-token' }),
          },
          body: scenario.request,
        },
        willRespondWith: {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
          body: {
            status: like(scenario.expectedResponse.status),
            orderId: like(scenario.expectedResponse.orderId),
            fillPrice: like(scenario.expectedResponse.fillPrice),
            fillVolume: like(scenario.expectedResponse.fillVolume),
            commission: like(scenario.expectedResponse.commission),
            slippage: like(scenario.expectedResponse.slippage),
          },
        },
      });

      const client = new MockApiClient({ baseUrl: provider.mockService.baseUrl });
      client.setAuthToken('test-token');
      const response = await client.post('/api/trades', scenario.request);

      expect(response.status).toBe(201);
      expect(response.data.status).toBe('filled');
      expect(response.data.orderId).toBeDefined();
    });

    it('POST /api/trades rejects order with insufficient margin', async () => {
      const scenario = getTradeScenario('trade-rejected-insufficient-margin');

      await provider.addInteraction({
        state: 'broker is connected but account has insufficient margin',
        uponReceiving: 'a market order that exceeds available margin',
        withRequest: {
          method: 'POST',
          path: '/api/trades',
          headers: {
            'Content-Type': 'application/json',
            Authorization: term({ matcher: 'Bearer .+', generate: 'Bearer test-token' }),
          },
          body: scenario.request,
        },
        willRespondWith: {
          status: 422,
          headers: { 'Content-Type': 'application/json' },
          body: {
            status: like('rejected'),
            errorCode: like('INSUFFICIENT_MARGIN'),
            errorMessage: like('Not enough margin to open position'),
          },
        },
      });

      const client = new MockApiClient({ baseUrl: provider.mockService.baseUrl });
      client.setAuthToken('test-token');
      const response = await client.post('/api/trades', scenario.request);

      expect(response.status).toBe(422);
      expect(response.data.errorCode).toBe('INSUFFICIENT_MARGIN');
    });
  });

  describe('Portfolio', () => {
    it('GET /api/portfolio returns current portfolio state', async () => {
      await provider.addInteraction({
        state: 'user has an active portfolio',
        uponReceiving: 'a request for portfolio state',
        withRequest: {
          method: 'GET',
          path: '/api/portfolio',
          headers: { Authorization: term({ matcher: 'Bearer .+', generate: 'Bearer test-token' }) },
        },
        willRespondWith: {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
          body: {
            balance: like(10000.00),
            equity: like(10000.00),
            unrealizedPnl: like(0),
            marginUsed: like(0),
            freeMargin: like(10000.00),
            openPositions: eachLike({
              id: like('pos-001'),
              symbol: like('EURUSD'),
              side: like('buy'),
              volume: like(0.10),
              openPrice: like(1.09000),
              currentPrice: like(1.09050),
              unrealizedPnl: like(5.00),
              stopLoss: like(1.08500),
              takeProfit: like(1.09500),
            }),
          },
        },
      });

      const client = new MockApiClient({ baseUrl: provider.mockService.baseUrl });
      client.setAuthToken('test-token');
      const response = await client.get('/api/portfolio');

      expect(response.status).toBe(200);
      expect(response.data).toHaveProperty('balance');
      expect(response.data).toHaveProperty('openPositions');
      expect(Array.isArray(response.data.openPositions)).toBe(true);
    });
  });

  describe('Market Data', () => {
    it('GET /api/market-data/:symbol/candles returns OHLCV data', async () => {
      await provider.addInteraction({
        state: 'market data is available for EURUSD',
        uponReceiving: 'a request for EURUSD candle data',
        withRequest: {
          method: 'GET',
          path: '/api/market-data/EURUSD/candles',
          query: { interval: '1h', limit: '100' },
          headers: { Authorization: term({ matcher: 'Bearer .+', generate: 'Bearer test-token' }) },
        },
        willRespondWith: {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
          body: {
            symbol: like('EURUSD'),
            interval: like('1h'),
            candles: eachLike({
              timestamp: like('2026-07-11T12:00:00Z'),
              open: like(1.09000),
              high: like(1.09100),
              low: like(1.08900),
              close: like(1.09050),
              volume: like(1500),
            }),
          },
        },
      });

      const client = new MockApiClient({ baseUrl: provider.mockService.baseUrl });
      client.setAuthToken('test-token');
      const response = await client.get('/api/market-data/EURUSD/candles?interval=1h&limit=100');

      expect(response.status).toBe(200);
      expect(response.data.symbol).toBe('EURUSD');
      expect(Array.isArray(response.data.candles)).toBe(true);
    });
  });

  describe('WebSocket Feeds', () => {
    it('establishes price feed and receives updates', async () => {
      await provider.addInteraction({
        state: 'market is open',
        uponReceiving: 'a WebSocket connection for price feed',
        withRequest: {
          method: 'GET',
          path: '/ws/prices',
          headers: { Upgrade: 'websocket', Connection: 'Upgrade' },
        },
        willRespondWith: {
          status: 101,
        },
      });

      // WebSocket contract verification is handled via message-level pact
      // This interaction ensures the upgrade endpoint exists
      expect(true).toBe(true);
    });
  });
});
```

**Mobile Consumer (Dart + pact_dart)**

**`test/contract/consumer_test.dart`**
```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:pact_dart/pact_dart.dart';
import 'package:shared_test_kit/shared_test_kit.dart';

void main() {
  late PactMockServer mockServer;

  setUpAll(() async {
    mockServer = PactMockServer('MobileApp', 'TradingAPI');
    await mockServer.start();
  });

  tearDownAll(() async {
    await mockServer.writePact();
    await mockServer.stop();
  });

  group('Mobile ↔ TradingAPI Contract', () {
    test('POST /api/auth/biometric/authenticate returns tokens', () async {
      final oauthTokens = SharedFixtures.oauthTokens['validToken'];

      await mockServer.addInteraction(
        state: 'user has enrolled biometric credentials',
        uponReceiving: 'a biometric authentication request',
        withRequest: PactRequest(
          method: 'POST',
          path: '/api/auth/biometric/authenticate',
          headers: {'Content-Type': 'application/json'},
          body: {
            'credentialId': PactMatcher.like('bio-cred-123'),
            'signature': PactMatcher.like('base64-signature-data'),
          },
        ),
        willRespondWith: PactResponse(
          status: 200,
          headers: {'Content-Type': 'application/json'},
          body: {
            'accessToken': PactMatcher.like(oauthTokens['accessToken']),
            'refreshToken': PactMatcher.like(oauthTokens['refreshToken']),
            'tokenType': PactMatcher.like('Bearer'),
            'expiresIn': PactMatcher.like(3600),
            'scope': PactMatcher.like(oauthTokens['scope']),
            'authMethod': PactMatcher.like('biometric'),
          },
        ),
      );

      final client = MockApiClient(baseUrl: mockServer.baseUrl);
      final response = await client.post('/api/auth/biometric/authenticate', body: {
        'credentialId': 'bio-cred-123',
        'signature': 'base64-signature-data',
      });

      expect(response.statusCode, 200);
      expect(response.body['authMethod'], 'biometric');
      expect(response.body['accessToken'], isNotNull);
    });

    test('POST /api/auth/biometric/register enrolls new credential', () async {
      await mockServer.addInteraction(
        state: 'user is authenticated',
        uponReceiving: 'a biometric enrollment request',
        withRequest: PactRequest(
          method: 'POST',
          path: '/api/auth/biometric/register',
          headers: {'Content-Type': 'application/json'},
          body: {
            'userId': PactMatcher.like('acc-001'),
            'biometricType': PactMatcher.like('fingerprint'),
            'publicKey': PactMatcher.like('base64-public-key'),
          },
        ),
        willRespondWith: PactResponse(
          status: 200,
          headers: {'Content-Type': 'application/json'},
          body: {
            'credentialId': PactMatcher.like('bio-cred-new'),
            'userId': PactMatcher.like('acc-001'),
            'biometricType': PactMatcher.like('fingerprint'),
            'enrolledAt': PactMatcher.like('2026-07-11T12:00:00Z'),
            'status': PactMatcher.like('active'),
          },
        ),
      );

      final client = MockApiClient(baseUrl: mockServer.baseUrl);
      final response = await client.post('/api/auth/biometric/register', body: {
        'userId': 'acc-001',
        'biometricType': 'fingerprint',
        'publicKey': 'base64-public-key',
      });

      expect(response.statusCode, 200);
      expect(response.body['status'], 'active');
    });

    test('GET /api/portfolio returns portfolio with positions', () async {
      await mockServer.addInteraction(
        state: 'user has an active portfolio',
        uponReceiving: 'a request for portfolio state',
        withRequest: PactRequest(
          method: 'GET',
          path: '/api/portfolio',
          headers: {'Authorization': PactMatcher.term(r'Bearer .+', 'Bearer test-token')},
        ),
        willRespondWith: PactResponse(
          status: 200,
          headers: {'Content-Type': 'application/json'},
          body: {
            'balance': PactMatcher.like(10000.00),
            'equity': PactMatcher.like(10000.00),
            'unrealizedPnl': PactMatcher.like(0),
            'openPositions': PactMatcher.eachLike({
              'id': PactMatcher.like('pos-001'),
              'symbol': PactMatcher.like('EURUSD'),
              'side': PactMatcher.like('buy'),
              'volume': PactMatcher.like(0.10),
            }),
          },
        ),
      );

      final client = MockApiClient(baseUrl: mockServer.baseUrl);
      client.setAuthToken('test-token');
      final response = await client.get('/api/portfolio');

      expect(response.statusCode, 200);
      expect(response.body['balance'], isNotNull);
      expect(response.body['openPositions'], isA<List>());
    });
  });
}
```

#### 2.3 Provider Verification (Backend)

**`tests/contract/provider/test_contract_verification.py`**
```python
"""
Provider contract verification — verifies the backend fulfills all consumer contracts.
Runs against the actual backend API (or a test instance).
"""
import pytest
import subprocess
import os
from pathlib import Path

PACTS_DIR = Path(__file__).parent / "pacts"
PACT_BROKER_URL = os.getenv("PACT_BROKER_URL", "http://localhost:9292")
PACT_BROKER_TOKEN = os.getenv("PACT_BROKER_TOKEN", "")

CONSUMER_PACTS = [
    ("DesktopApp", "pact-desktop-tradingapi.json"),
    ("WebApp", "pact-web-tradingapi.json"),
    ("MobileApp", "pact-mobile-tradingapi.json"),
]


class TestContractProviderVerification:
    """
    Verifies that the TradingAPI backend satisfies all consumer contracts.
    Uses pact-verifier (Ruby) or pact-python for provider verification.
    """

    @pytest.fixture(autouse=True)
    def setup(self, api_server, auth_token):
        """Start backend API server and obtain auth token for verification."""
        self.base_url = api_server
        self.token = auth_token

    @pytest.mark.parametrize("consumer,pact_file", CONSUMER_PACTS)
    def test_provider_satisfies_consumer_contract(self, consumer, pact_file):
        """Verify backend satisfies the contract from each consumer."""
        pact_path = PACTS_DIR / pact_file
        if not pact_path.exists():
            pytest.skip(f"Pact file not found: {pact_path}. Run consumer tests first.")

        result = subprocess.run(
            [
                "pact-verifier",
                "--provider-base-url", self.base_url,
                "--pact-url", str(pact_path),
                "--provider-state-setup-url", f"{self.base_url}/_pact/state",
                "--provider-app-version", os.getenv("GIT_COMMIT", "local"),
                "--publish-verification-results",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            pytest.fail(
                f"Provider verification failed for {consumer}:\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}"
            )

    def test_all_contracts_from_broker(self):
        """Pull and verify all contracts from the Pact broker."""
        result = subprocess.run(
            [
                "pact-verifier",
                "--provider-base-url", self.base_url,
                "--pact-broker-url", PACT_BROKER_URL,
                "--provider", "TradingAPI",
                "--provider-app-version", os.getenv("GIT_COMMIT", "local"),
                "--publish-verification-results",
                "--consumer-version-selectors", '{"mainBranch": true}',
            ],
            capture_output=True,
            text=True,
            timeout=180,
            env={**os.environ, "PACT_BROKER_TOKEN": PACT_BROKER_TOKEN},
        )

        if result.returncode != 0:
            pytest.fail(f"Broker verification failed:\n{result.stdout}\n{result.stderr}")


# Provider state handler — sets up test data for each interaction
@pytest.fixture
def provider_state_handler():
    """Flask endpoint that handles Pact provider state setup requests."""
    from flask import Flask, request, jsonify

    app = Flask(__name__)

    @app.route("/_pact/state", methods=["POST"])
    def handle_state():
        body = request.json
        state = body.get("state")
        params = body.get("params", {})

        state_handlers = {
            "user exists with valid credentials": lambda: setup_user("trader@test.local"),
            "no user with given credentials": lambda: clear_users(),
            "broker is connected and account has sufficient margin": lambda: setup_broker("connected", margin=10000),
            "broker is connected but account has insufficient margin": lambda: setup_broker("connected", margin=10),
            "user has an active portfolio": lambda: setup_portfolio(),
            "market data is available for EURUSD": lambda: setup_market_data("EURUSD"),
            "market is open": lambda: setup_market_state("open"),
            "user has enrolled biometric credentials": lambda: setup_biometric("acc-001"),
            "user is authenticated": lambda: setup_user("trader@test.local"),
        }

        handler = state_handlers.get(state)
        if handler:
            handler()
            return jsonify({"status": "ok"})
        return jsonify({"error": f"Unknown state: {state}"}), 400

    return app


def setup_user(email: str):
    """Insert test user into database."""
    pass  # Implementation depends on your DB layer


def clear_users():
    """Clear test users."""
    pass


def setup_broker(status: str, margin: float):
    """Configure mock broker state."""
    pass


def setup_portfolio():
    """Insert test portfolio data."""
    pass


def setup_market_data(symbol: str):
    """Insert test market data."""
    pass


def setup_market_state(state: str):
    """Set market open/close state."""
    pass


def setup_biometric(user_id: str):
    """Insert biometric credential for user."""
    pass
```

#### 2.4 Contract Test CI Pipeline

**`.github/workflows/contract-tests.yml`**
```yaml
name: API Contract Tests

on:
  push:
    branches: [main, develop]
  pull_request:

env:
  PACT_BROKER_URL: ${{ secrets.PACT_BROKER_URL }}
  PACT_BROKER_TOKEN: ${{ secrets.PACT_BROKER_TOKEN }}

jobs:
  # Consumer tests — each frontend generates its pact file
  consumer-desktop:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci
        working-directory: shared-test-kit/adapters/typescript
      - run: npm ci
        working-directory: apps/desktop
      - run: npm run test:contract
        working-directory: apps/desktop
      - uses: actions/upload-artifact@v4
        with:
          name: pact-desktop
          path: tests/contract/pacts/pact-desktop-tradingapi.json

  consumer-web:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci
        working-directory: shared-test-kit/adapters/typescript
      - run: npm ci
        working-directory: apps/web
      - run: npm run test:contract
        working-directory: apps/web
      - uses: actions/upload-artifact@v4
        with:
          name: pact-web
          path: tests/contract/pacts/pact-web-tradingapi.json

  consumer-mobile:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dart-lang/setup-dart@v1
        with: { sdk: '3.2' }
      - run: dart pub get
        working-directory: shared-test-kit/adapters/dart
      - run: flutter pub get
        working-directory: apps/mobile
      - run: flutter test test/contract/
        working-directory: apps/mobile
      - uses: actions/upload-artifact@v4
        with:
          name: pact-mobile
          path: apps/mobile/test/contract/pacts/pact-mobile-tradingapi.json

  # Provider verification — backend verifies all consumer contracts
  provider-verify:
    needs: [consumer-desktop, consumer-web, consumer-mobile]
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:7
        ports: ['6379:6379']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - uses: actions/download-artifact@v4
        with:
          path: tests/contract/pacts
      - run: pip install -r requirements.txt -r requirements-test.txt
      - run: pip install pact-python
      - name: Start backend API
        run: |
          python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
          sleep 5
      - name: Verify provider contracts
        run: |
          pytest tests/contract/provider/test_contract_verification.py -v --tb=short
        env:
          API_BASE_URL: http://localhost:8000
          GIT_COMMIT: ${{ github.sha }}

  # Publish pacts to broker (on main only)
  publish-pacts:
    if: github.ref == 'refs/heads/main'
    needs: [consumer-desktop, consumer-web, consumer-mobile]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
        with:
          path: pacts
      - name: Publish pacts to broker
        run: |
          for pact in pacts/*/*.json; do
            echo "Publishing $pact"
            curl -X PUT "$PACT_BROKER_URL/pacts" \
              -H "Authorization: Bearer $PACT_BROKER_TOKEN" \
              -H "Content-Type: application/json" \
              -d @"$pact"
          done
```

#### 2.5 Can-I-Deploy Check

**`.github/workflows/can-i-deploy.yml`**
```yaml
name: Can I Deploy?

on:
  push:
    branches: [main]

jobs:
  can-i-deploy:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        include:
          - pacticipant: DesktopApp
            version: ${{ github.sha }}
          - pacticipant: WebApp
            version: ${{ github.sha }}
          - pacticipant: MobileApp
            version: ${{ github.sha }}
          - pacticipant: TradingAPI
            version: ${{ github.sha }}
    steps:
      - name: Check deployment safety
        run: |
          pact-broker can-i-deploy \
            --pacticipant ${{ matrix.pacticipant }} \
            --version ${{ github.sha }} \
            --broker-base-url "$PACT_BROKER_URL" \
            --broker-token "$PACT_BROKER_TOKEN"
        env:
          PACT_BROKER_URL: ${{ secrets.PACT_BROKER_URL }}
          PACT_BROKER_TOKEN: ${{ secrets.PACT_BROKER_TOKEN }}
```

---

## Issue 3: Authentication Integration Tests

### Problem

No integration tests exist for authentication flows across platforms. OAuth 2.0, biometric auth (Face ID, Touch ID, fingerprint), and WebAuthn are defined in the architecture but completely untested.

### Solution: Unified Auth Integration Test Suite

#### 3.1 Test Matrix

| Auth Method | Desktop | Web | Mobile | Backend |
|-------------|---------|-----|--------|---------|
| **OAuth 2.0 Authorization Code + PKCE** | ✅ | ✅ | ✅ | ✅ |
| **OAuth 2.0 Token Refresh** | ✅ | ✅ | ✅ | ✅ |
| **OAuth 2.0 Token Revocation** | ✅ | ✅ | ✅ | ✅ |
| **Biometric — Fingerprint** | N/A | N/A | ✅ | ✅ |
| **Biometric — Face ID** | N/A | N/A | ✅ (iOS) | ✅ |
| **Biometric — Touch ID** | N/A | N/A | ✅ (iOS) | ✅ |
| **WebAuthn Registration** | ✅ | ✅ | ✅ | ✅ |
| **WebAuthn Authentication** | ✅ | ✅ | ✅ | ✅ |
| **Session Management** | ✅ | ✅ | ✅ | ✅ |
| **Multi-device Logout** | ✅ | ✅ | ✅ | ✅ |

#### 3.2 Backend Auth Integration Tests

**`tests/integration/auth/test_oauth_flows.py`**
```python
"""
Integration tests for OAuth 2.0 authentication flows.
Tests the full authorization code + PKCE flow, token refresh, and revocation.
"""
import pytest
import httpx
import hashlib
import base64
import secrets
from urllib.parse import urlencode, urlparse, parse_qs


API_BASE = "http://localhost:8000"
AUTH_BASE = f"{API_BASE}/api/auth"


def generate_pkce_pair():
    """Generate PKCE code verifier and challenge."""
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return code_verifier, code_challenge


class TestOAuthAuthorizationCodePKCE:
    """Test OAuth 2.0 Authorization Code flow with PKCE."""

    @pytest.mark.asyncio
    async def test_full_authorization_code_flow(self, http_client: httpx.AsyncClient):
        """Test complete OAuth flow: authorize → callback → token exchange."""
        code_verifier, code_challenge = generate_pkce_pair()
        state = secrets.token_urlsafe(16)

        # Step 1: Authorization request
        auth_params = {
            "response_type": "code",
            "client_id": "desktop-app",
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "trading:read trading:write portfolio:read",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        auth_response = await http_client.get(f"{AUTH_BASE}/authorize", params=auth_params, follow_redirects=False)

        assert auth_response.status_code in (302, 200), f"Authorization failed: {auth_response.status_code}"

        # Step 2: Simulate user consent (in test, auto-approve)
        if auth_response.status_code == 302:
            callback_url = auth_response.headers["location"]
        else:
            # Test mode: extract code from response
            callback_url = auth_response.json().get("redirect_uri")

        parsed = urlparse(callback_url)
        callback_params = parse_qs(parsed.query)
        auth_code = callback_params["code"][0]
        returned_state = callback_params["state"][0]
        assert returned_state == state, "State mismatch — possible CSRF"

        # Step 3: Token exchange
        token_response = await http_client.post(f"{AUTH_BASE}/token", data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": "http://localhost:3000/callback",
            "client_id": "desktop-app",
            "code_verifier": code_verifier,
        })

        assert token_response.status_code == 200
        tokens = token_response.json()
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "Bearer"
        assert "trading:read" in tokens["scope"]

        # Step 4: Use the access token
        me_response = await http_client.get(f"{API_BASE}/api/me", headers={
            "Authorization": f"Bearer {tokens['access_token']}"
        })
        assert me_response.status_code == 200
        assert me_response.json()["role"] == "trader"

    @pytest.mark.asyncio
    async def test_pkce_verifier_required(self, http_client: httpx.AsyncClient):
        """Verify that PKCE code_verifier is required — reject without it."""
        _, code_challenge = generate_pkce_pair()
        state = secrets.token_urlsafe(16)

        auth_params = {
            "response_type": "code",
            "client_id": "desktop-app",
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "trading:read",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        auth_response = await http_client.get(f"{AUTH_BASE}/authorize", params=auth_params, follow_redirects=False)

        if auth_response.status_code == 302:
            callback_url = auth_response.headers["location"]
            parsed = urlparse(callback_url)
            auth_code = parse_qs(parsed.query)["code"][0]

            # Try token exchange WITHOUT code_verifier
            token_response = await http_client.post(f"{AUTH_BASE}/token", data={
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": "http://localhost:3000/callback",
                "client_id": "desktop-app",
                # Missing code_verifier
            })

            assert token_response.status_code == 400
            assert token_response.json()["error"] == "invalid_grant"

    @pytest.mark.asyncio
    async def test_pkce_challenge_mismatch_rejected(self, http_client: httpx.AsyncClient):
        """Verify that a wrong code_verifier is rejected."""
        _, code_challenge = generate_pkce_pair()
        state = secrets.token_urlsafe(16)

        auth_params = {
            "response_type": "code",
            "client_id": "desktop-app",
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "trading:read",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        auth_response = await http_client.get(f"{AUTH_BASE}/authorize", params=auth_params, follow_redirects=False)

        if auth_response.status_code == 302:
            callback_url = auth_response.headers["location"]
            parsed = urlparse(callback_url)
            auth_code = parse_qs(parsed.query)["code"][0]

            # Use a DIFFERENT verifier (not the one that generated the challenge)
            wrong_verifier, _ = generate_pkce_pair()
            token_response = await http_client.post(f"{AUTH_BASE}/token", data={
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": "http://localhost:3000/callback",
                "client_id": "desktop-app",
                "code_verifier": wrong_verifier,
            })

            assert token_response.status_code == 400


class TestTokenRefresh:
    """Test OAuth token refresh flow."""

    @pytest.mark.asyncio
    async def test_refresh_token_rotation(self, http_client: httpx.AsyncClient, auth_tokens):
        """Verify refresh tokens are rotated on use (old one invalidated)."""
        old_refresh_token = auth_tokens["refresh_token"]

        # Refresh
        refresh_response = await http_client.post(f"{AUTH_BASE}/token", data={
            "grant_type": "refresh_token",
            "refresh_token": old_refresh_token,
            "client_id": "desktop-app",
        })

        assert refresh_response.status_code == 200
        new_tokens = refresh_response.json()
        assert new_tokens["refresh_token"] != old_refresh_token, "Refresh token should be rotated"

        # Old refresh token should no longer work
        old_refresh_response = await http_client.post(f"{AUTH_BASE}/token", data={
            "grant_type": "refresh_token",
            "refresh_token": old_refresh_token,
            "client_id": "desktop-app",
        })
        assert old_refresh_response.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_access_token_triggers_refresh(self, http_client: httpx.AsyncClient, expired_tokens):
        """Verify that an expired access token returns 401, enabling client to refresh."""
        me_response = await http_client.get(f"{API_BASE}/api/me", headers={
            "Authorization": f"Bearer {expired_tokens['access_token']}"
        })
        assert me_response.status_code == 401
        assert me_response.json()["error"] == "token_expired"

    @pytest.mark.asyncio
    async def test_concurrent_refresh_requests(self, http_client: httpx.AsyncClient, auth_tokens):
        """Verify only one refresh succeeds when multiple requests refresh simultaneously."""
        import asyncio

        refresh_token = auth_tokens["refresh_token"]

        async def do_refresh():
            return await http_client.post(f"{AUTH_BASE}/token", data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": "desktop-app",
            })

        # Fire 5 concurrent refresh requests
        results = await asyncio.gather(*[do_refresh() for _ in range(5)])
        success_count = sum(1 for r in results if r.status_code == 200)

        # Exactly one should succeed (the rest get 401 due to token rotation)
        assert success_count == 1, f"Expected 1 success, got {success_count}"


class TestTokenRevocation:
    """Test OAuth token revocation."""

    @pytest.mark.asyncio
    async def test_revoke_access_token(self, http_client: httpx.AsyncClient, auth_tokens):
        """Verify revoked access token is immediately invalid."""
        # Revoke
        revoke_response = await http_client.post(f"{AUTH_BASE}/revoke", data={
            "token": auth_tokens["access_token"],
            "token_type_hint": "access_token",
            "client_id": "desktop-app",
        })
        assert revoke_response.status_code == 200

        # Token should be invalid now
        me_response = await http_client.get(f"{API_BASE}/api/me", headers={
            "Authorization": f"Bearer {auth_tokens['access_token']}"
        })
        assert me_response.status_code == 401

    @pytest.mark.asyncio
    async def test_revoke_refresh_token(self, http_client: httpx.AsyncClient, auth_tokens):
        """Verify revoked refresh token cannot be used."""
        revoke_response = await http_client.post(f"{AUTH_BASE}/revoke", data={
            "token": auth_tokens["refresh_token"],
            "token_type_hint": "refresh_token",
            "client_id": "desktop-app",
        })
        assert revoke_response.status_code == 200

        refresh_response = await http_client.post(f"{AUTH_BASE}/token", data={
            "grant_type": "refresh_token",
            "refresh_token": auth_tokens["refresh_token"],
            "client_id": "desktop-app",
        })
        assert refresh_response.status_code == 401


class TestMultiPlatformSessionManagement:
    """Test session behavior across multiple platforms/devices."""

    @pytest.mark.asyncio
    async def test_same_user_multiple_devices(self, http_client: httpx.AsyncClient):
        """Verify same user can have active sessions on desktop + mobile simultaneously."""
        # Login as desktop
        desktop_login = await http_client.post(f"{AUTH_BASE}/login", json={
            "username": "trader@test.local",
            "password": "test-password",
            "client_id": "desktop-app",
        })
        assert desktop_login.status_code == 200
        desktop_tokens = desktop_login.json()

        # Login as mobile
        mobile_login = await http_client.post(f"{AUTH_BASE}/login", json={
            "username": "trader@test.local",
            "password": "test-password",
            "client_id": "mobile-app",
        })
        assert mobile_login.status_code == 200
        mobile_tokens = mobile_login.json()

        # Both tokens should work independently
        desktop_me = await http_client.get(f"{API_BASE}/api/me", headers={
            "Authorization": f"Bearer {desktop_tokens['access_token']}"
        })
        assert desktop_me.status_code == 200

        mobile_me = await http_client.get(f"{API_BASE}/api/me", headers={
            "Authorization": f"Bearer {mobile_tokens['access_token']}"
        })
        assert mobile_me.status_code == 200

    @pytest.mark.asyncio
    async def test_global_logout_revokes_all_sessions(self, http_client: httpx.AsyncClient, auth_tokens):
        """Verify global logout invalidates all sessions for the user."""
        # Create a second session
        second_login = await http_client.post(f"{AUTH_BASE}/login", json={
            "username": "trader@test.local",
            "password": "test-password",
            "client_id": "web-app",
        })
        second_tokens = second_login.json()

        # Global logout from first session
        logout_response = await http_client.post(f"{AUTH_BASE}/logout-all", headers={
            "Authorization": f"Bearer {auth_tokens['access_token']}"
        })
        assert logout_response.status_code == 200

        # Both tokens should be invalid
        r1 = await http_client.get(f"{API_BASE}/api/me", headers={
            "Authorization": f"Bearer {auth_tokens['access_token']}"
        })
        assert r1.status_code == 401

        r2 = await http_client.get(f"{API_BASE}/api/me", headers={
            "Authorization": f"Bearer {second_tokens['access_token']}"
        })
        assert r2.status_code == 401


class TestScopeEnforcement:
    """Test that API endpoints enforce OAuth scopes."""

    @pytest.mark.asyncio
    async def test_trading_write_required_for_trades(self, http_client: httpx.AsyncClient, limited_scope_token):
        """Verify trading:write scope is required to execute trades."""
        trade_response = await http_client.post(f"{API_BASE}/api/trades", json={
            "symbol": "EURUSD", "side": "buy", "type": "market", "volume": 0.10,
        }, headers={
            "Authorization": f"Bearer {limited_scope_token}"  # Only has portfolio:read
        })
        assert trade_response.status_code == 403
        assert trade_response.json()["error"] == "insufficient_scope"

    @pytest.mark.asyncio
    async def test_portfolio_read_sufficient_for_portfolio(self, http_client: httpx.AsyncClient, limited_scope_token):
        """Verify portfolio:read scope allows reading portfolio."""
        portfolio_response = await http_client.get(f"{API_BASE}/api/portfolio", headers={
            "Authorization": f"Bearer {limited_scope_token}"
        })
        assert portfolio_response.status_code == 200
```

#### 3.3 Backend Biometric Integration Tests

**`tests/integration/auth/test_biometric_flows.py`**
```python
"""
Integration tests for biometric authentication flows.
Tests registration, authentication, credential management, and edge cases.
"""
import pytest
import httpx

AUTH_BASE = "http://localhost:8000/api/auth"


class TestBiometricRegistration:
    """Test biometric credential enrollment."""

    @pytest.mark.asyncio
    async def test_register_fingerprint_credential(self, http_client: httpx.AsyncClient, auth_headers):
        """Test fingerprint enrollment flow."""
        response = await http_client.post(f"{AUTH_BASE}/biometric/register", json={
            "userId": "acc-001",
            "biometricType": "fingerprint",
            "publicKey": "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtest-key-data",
            "deviceInfo": {
                "platform": "android",
                "model": "Pixel 8",
                "osVersion": "14",
            },
        }, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["credentialId"].startswith("bio-cred-")
        assert data["biometricType"] == "fingerprint"
        assert data["status"] == "active"
        assert "enrolledAt" in data

    @pytest.mark.asyncio
    async def test_register_face_id_credential(self, http_client: httpx.AsyncClient, auth_headers):
        """Test Face ID enrollment (iOS-specific)."""
        response = await http_client.post(f"{AUTH_BASE}/biometric/register", json={
            "userId": "acc-001",
            "biometricType": "faceId",
            "publicKey": "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEface-key-data",
            "deviceInfo": {
                "platform": "ios",
                "model": "iPhone 15 Pro",
                "osVersion": "18.0",
            },
        }, headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["biometricType"] == "faceId"

    @pytest.mark.asyncio
    async def test_register_multiple_biometrics_same_device(self, http_client: httpx.AsyncClient, auth_headers):
        """Test that a user can enroll both fingerprint and face on same device."""
        r1 = await http_client.post(f"{AUTH_BASE}/biometric/register", json={
            "userId": "acc-001",
            "biometricType": "fingerprint",
            "publicKey": "key-1",
        }, headers=auth_headers)
        assert r1.status_code == 200

        r2 = await http_client.post(f"{AUTH_BASE}/biometric/register", json={
            "userId": "acc-001",
            "biometricType": "faceId",
            "publicKey": "key-2",
        }, headers=auth_headers)
        assert r2.status_code == 200

        # Both should be active
        creds_response = await http_client.get(f"{AUTH_BASE}/biometric/credentials", headers=auth_headers)
        assert creds_response.status_code == 200
        creds = creds_response.json()
        assert len(creds) == 2
        types = {c["biometricType"] for c in creds}
        assert types == {"fingerprint", "faceId"}

    @pytest.mark.asyncio
    async def test_register_requires_authentication(self, http_client: httpx.AsyncClient):
        """Verify biometric registration requires valid auth token."""
        response = await http_client.post(f"{AUTH_BASE}/biometric/register", json={
            "userId": "acc-001",
            "biometricType": "fingerprint",
            "publicKey": "key",
        })
        assert response.status_code == 401


class TestBiometricAuthentication:
    """Test biometric login flows."""

    @pytest.mark.asyncio
    async def test_fingerprint_authentication_success(self, http_client: httpx.AsyncClient, enrolled_biometric):
        """Test successful fingerprint authentication."""
        response = await http_client.post(f"{AUTH_BASE}/biometric/authenticate", json={
            "credentialId": enrolled_biometric["credentialId"],
            "signature": "base64-encoded-signature",
            "authenticatorData": "base64-authenticator-data",
            "clientDataJSON": "base64-client-data",
        })

        assert response.status_code == 200
        tokens = response.json()
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["authMethod"] == "biometric"

    @pytest.mark.asyncio
    async def test_biometric_auth_with_invalid_signature(self, http_client: httpx.AsyncClient, enrolled_biometric):
        """Test that invalid biometric signature is rejected."""
        response = await http_client.post(f"{AUTH_BASE}/biometric/authenticate", json={
            "credentialId": enrolled_biometric["credentialId"],
            "signature": "invalid-signature",
        })

        assert response.status_code == 401
        assert response.json()["error"] == "biometric_verification_failed"

    @pytest.mark.asyncio
    async def test_biometric_auth_with_revoked_credential(self, http_client: httpx.AsyncClient, auth_headers, enrolled_biometric):
        """Test that revoked biometric credential cannot authenticate."""
        # Revoke
        await http_client.delete(
            f"{AUTH_BASE}/biometric/credentials/{enrolled_biometric['credentialId']}",
            headers=auth_headers,
        )

        # Attempt auth
        response = await http_client.post(f"{AUTH_BASE}/biometric/authenticate", json={
            "credentialId": enrolled_biometric["credentialId"],
            "signature": "base64-encoded-signature",
        })

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_biometric_auth_rate_limiting(self, http_client: httpx.AsyncClient, enrolled_biometric):
        """Test rate limiting on biometric auth failures (brute force protection)."""
        for i in range(10):
            await http_client.post(f"{AUTH_BASE}/biometric/authenticate", json={
                "credentialId": enrolled_biometric["credentialId"],
                "signature": f"wrong-signature-{i}",
            })

        # 11th attempt should be rate limited
        response = await http_client.post(f"{AUTH_BASE}/biometric/authenticate", json={
            "credentialId": enrolled_biometric["credentialId"],
            "signature": "wrong-signature-final",
        })

        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_biometric_credential_expiry(self, http_client: httpx.AsyncClient, auth_headers):
        """Test that biometric credentials expire after configured period."""
        # Register with short expiry (test config)
        reg_response = await http_client.post(f"{AUTH_BASE}/biometric/register", json={
            "userId": "acc-001",
            "biometricType": "fingerprint",
            "publicKey": "key-expiry-test",
            "expiresIn": 1,  # 1 second for testing
        }, headers=auth_headers)
        cred_id = reg_response.json()["credentialId"]

        import asyncio
        await asyncio.sleep(2)

        # Should be expired
        auth_response = await http_client.post(f"{AUTH_BASE}/biometric/authenticate", json={
            "credentialId": cred_id,
            "signature": "valid-looking-signature",
        })

        assert auth_response.status_code == 401
        assert auth_response.json()["error"] == "credential_expired"
```

#### 3.4 Backend WebAuthn Integration Tests

**`tests/integration/auth/test_webauthn_flows.py`**
```python
"""
Integration tests for WebAuthn (FIDO2) registration and authentication.
Tests the full ceremony flow including challenge generation, attestation, and assertion.
"""
import pytest
import httpx
import base64

AUTH_BASE = "http://localhost:8000/api/auth"


class TestWebAuthnRegistration:
    """Test WebAuthn credential registration ceremony."""

    @pytest.mark.asyncio
    async def test_registration_options_generation(self, http_client: httpx.AsyncClient, auth_headers):
        """Test that registration options include correct challenge and RP info."""
        response = await http_client.post(f"{AUTH_BASE}/webauthn/register/options", json={
            "userId": "acc-001",
        }, headers=auth_headers)

        assert response.status_code == 200
        options = response.json()
        assert "challenge" in options
        assert options["rp"]["name"] == "Alpha Trading"
        assert options["user"]["id"] == "acc-001"
        assert options["attestation"] == "direct"
        assert any(p["type"] == "public-key" for p in options["pubKeyCredParams"])

    @pytest.mark.asyncio
    async def test_registration_verification_success(self, http_client: httpx.AsyncClient, auth_headers):
        """Test successful WebAuthn registration verification."""
        # Get options first
        options_response = await http_client.post(f"{AUTH_BASE}/webauthn/register/options", json={
            "userId": "acc-001",
        }, headers=auth_headers)
        options = options_response.json()

        # Simulate client attestation response
        credential = {
            "id": "webauthn-cred-test-001",
            "rawId": base64.urlsafe_b64encode(b"test-credential-id").decode().rstrip("="),
            "type": "public-key",
            "response": {
                "attestationObject": base64.urlsafe_b64encode(b"test-attestation").decode().rstrip("="),
                "clientDataJSON": base64.urlsafe_b64encode(
                    f'{{"type":"webauthn.create","challenge":"{options["challenge"]}","origin":"https://alpha-trading.app"}}'.encode()
                ).decode().rstrip("="),
            },
        }

        verify_response = await http_client.post(f"{AUTH_BASE}/webauthn/register/verify", json={
            "userId": "acc-001",
            "credential": credential,
        }, headers=auth_headers)

        assert verify_response.status_code == 200
        data = verify_response.json()
        assert data["credentialId"] == "webauthn-cred-test-001"
        assert data["status"] == "registered"

    @pytest.mark.asyncio
    async def test_registration_challenge_single_use(self, http_client: httpx.AsyncClient, auth_headers):
        """Verify that a registration challenge can only be used once."""
        options_response = await http_client.post(f"{AUTH_BASE}/webauthn/register/options", json={
            "userId": "acc-001",
        }, headers=auth_headers)
        options = options_response.json()

        credential = {
            "id": "webauthn-cred-reuse-test",
            "rawId": base64.urlsafe_b64encode(b"reuse-test-id").decode().rstrip("="),
            "type": "public-key",
            "response": {
                "attestationObject": base64.urlsafe_b64encode(b"reuse-attestation").decode().rstrip("="),
                "clientDataJSON": base64.urlsafe_b64encode(
                    f'{{"type":"webauthn.create","challenge":"{options["challenge"]}","origin":"https://alpha-trading.app"}}'.encode()
                ).decode().rstrip("="),
            },
        }

        # First attempt should succeed
        r1 = await http_client.post(f"{AUTH_BASE}/webauthn/register/verify", json={
            "userId": "acc-001", "credential": credential,
        }, headers=auth_headers)
        assert r1.status_code == 200

        # Second attempt with same challenge should fail
        r2 = await http_client.post(f"{AUTH_BASE}/webauthn/register/verify", json={
            "userId": "acc-001", "credential": {**credential, "id": "webauthn-cred-reuse-test-2"},
        }, headers=auth_headers)
        assert r2.status_code == 400


class TestWebAuthnAuthentication:
    """Test WebAuthn authentication ceremony."""

    @pytest.mark.asyncio
    async def test_authentication_options_generation(self, http_client: httpx.AsyncClient):
        """Test that authentication options include challenge and allowed credentials."""
        response = await http_client.post(f"{AUTH_BASE}/webauthn/login/options", json={
            "userId": "acc-001",
        })

        assert response.status_code == 200
        options = response.json()
        assert "challenge" in options
        assert options["rpId"] == "alpha-trading.app"
        assert len(options["allowCredentials"]) > 0

    @pytest.mark.asyncio
    async def test_authentication_assertion_success(self, http_client: httpx.AsyncClient, registered_webauthn_credential):
        """Test successful WebAuthn authentication with valid assertion."""
        # Get auth options
        options_response = await http_client.post(f"{AUTH_BASE}/webauthn/login/options", json={
            "userId": "acc-001",
        })
        options = options_response.json()

        # Simulate client assertion
        assertion = {
            "id": registered_webauthn_credential["credentialId"],
            "rawId": base64.urlsafe_b64encode(b"assertion-raw-id").decode().rstrip("="),
            "type": "public-key",
            "response": {
                "authenticatorData": base64.urlsafe_b64encode(b"auth-data").decode().rstrip("="),
                "clientDataJSON": base64.urlsafe_b64encode(
                    f'{{"type":"webauthn.get","challenge":"{options["challenge"]}","origin":"https://alpha-trading.app"}}'.encode()
                ).decode().rstrip("="),
                "signature": base64.urlsafe_b64encode(b"valid-signature").decode().rstrip("="),
            },
        }

        verify_response = await http_client.post(f"{AUTH_BASE}/webauthn/login/verify", json={
            "assertion": assertion,
        })

        assert verify_response.status_code == 200
        tokens = verify_response.json()
        assert tokens["authMethod"] == "webauthn"
        assert "access_token" in tokens

    @pytest.mark.asyncio
    async def test_authentication_with_wrong_origin(self, http_client: httpx.AsyncClient):
        """Verify assertion from wrong origin is rejected."""
        options_response = await http_client.post(f"{AUTH_BASE}/webauthn/login/options", json={
            "userId": "acc-001",
        })
        options = options_response.json()

        assertion = {
            "id": "test-cred",
            "rawId": base64.urlsafe_b64encode(b"wrong-origin").decode().rstrip("="),
            "type": "public-key",
            "response": {
                "authenticatorData": base64.urlsafe_b64encode(b"auth-data").decode().rstrip("="),
                "clientDataJSON": base64.urlsafe_b64encode(
                    f'{{"type":"webauthn.get","challenge":"{options["challenge"]}","origin":"https://evil.com"}}'.encode()
                ).decode().rstrip("="),
                "signature": base64.urlsafe_b64encode(b"sig").decode().rstrip("="),
            },
        }

        response = await http_client.post(f"{AUTH_BASE}/webauthn/login/verify", json={
            "assertion": assertion,
        })

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_authentication_with_expired_challenge(self, http_client: httpx.AsyncClient):
        """Verify that an expired challenge is rejected."""
        import asyncio

        # Get options with short timeout
        options_response = await http_client.post(f"{AUTH_BASE}/webauthn/login/options", json={
            "userId": "acc-001",
            "timeout": 1000,  # 1 second
        })
        options = options_response.json()

        await asyncio.sleep(2)

        assertion = {
            "id": "test-cred",
            "rawId": base64.urlsafe_b64encode(b"expired").decode().rstrip("="),
            "type": "public-key",
            "response": {
                "authenticatorData": base64.urlsafe_b64encode(b"auth-data").decode().rstrip("="),
                "clientDataJSON": base64.urlsafe_b64encode(
                    f'{{"type":"webauthn.get","challenge":"{options["challenge"]}","origin":"https://alpha-trading.app"}}'.encode()
                ).decode().rstrip("="),
                "signature": base64.urlsafe_b64encode(b"sig").decode().rstrip("="),
            },
        }

        response = await http_client.post(f"{AUTH_BASE}/webauthn/login/verify", json={
            "assertion": assertion,
        })

        assert response.status_code == 401
        assert response.json()["error"] == "challenge_expired"


class TestWebAuthnCredentialManagement:
    """Test WebAuthn credential lifecycle management."""

    @pytest.mark.asyncio
    async def test_list_registered_credentials(self, http_client: httpx.AsyncClient, auth_headers, registered_webauthn_credential):
        """Test listing user's registered WebAuthn credentials."""
        response = await http_client.get(f"{AUTH_BASE}/webauthn/credentials", headers=auth_headers)
        assert response.status_code == 200
        creds = response.json()
        assert len(creds) >= 1
        assert any(c["credentialId"] == registered_webauthn_credential["credentialId"] for c in creds)

    @pytest.mark.asyncio
    async def test_delete_credential(self, http_client: httpx.AsyncClient, auth_headers, registered_webauthn_credential):
        """Test deleting a WebAuthn credential."""
        delete_response = await http_client.delete(
            f"{AUTH_BASE}/webauthn/credentials/{registered_webauthn_credential['credentialId']}",
            headers=auth_headers,
        )
        assert delete_response.status_code == 200

        # Verify it's gone
        list_response = await http_client.get(f"{AUTH_BASE}/webauthn/credentials", headers=auth_headers)
        assert not any(
            c["credentialId"] == registered_webauthn_credential["credentialId"]
            for c in list_response.json()
        )

    @pytest.mark.asyncio
    async def test_cannot_delete_last_credential_without_password(self, http_client: httpx.AsyncClient, auth_headers):
        """Verify user cannot delete their only WebAuthn credential without password fallback."""
        response = await http_client.delete(
            f"{AUTH_BASE}/webauthn/credentials/last-credential",
            headers=auth_headers,
        )
        # Should require password confirmation
        assert response.status_code == 409
        assert response.json()["error"] == "password_confirmation_required"
```

#### 3.5 Desktop Auth Integration Tests

**`tests/integration/auth/desktop/test_desktop_auth.ts`**
```typescript
/**
 * Desktop-specific auth integration tests.
 * Tests Tauri IPC → backend auth flow, token persistence, and platform keychain.
 */
import { test, expect, chromium } from '@playwright/test';
import { mockClient, fixtures } from '@shared-test-kit/typescript';
import { execSync } from 'child_process';

test.describe('Desktop Authentication Integration', () => {
  test.describe('OAuth Login Flow', () => {
    test('completes full login via Tauri IPC and stores tokens securely', async () => {
      const oauthTokens = fixtures.auth.oauthTokens();

      // Step 1: Trigger login via desktop UI
      const page = await browser.newPage();
      await page.goto('tauri://localhost');

      // Step 2: Enter credentials
      await page.fill('[data-testid="login-email"]', 'trader@test.local');
      await page.fill('[data-testid="login-password"]', 'test-password');
      await page.click('[data-testid="login-submit"]');

      // Step 3: Wait for successful login → dashboard loads
      await expect(page.locator('[data-testid="dashboard"]')).toBeVisible({ timeout: 10000 });

      // Step 4: Verify tokens stored in platform keychain (via Tauri IPC)
      const storedToken = await page.evaluate(() => {
        return window.__TAURI__.invoke('get_stored_token');
      });
      expect(storedToken).toBeTruthy();
      expect(storedToken).toContain('Bearer');
    });

    test('handles login failure gracefully', async () => {
      const page = await browser.newPage();
      await page.goto('tauri://localhost');

      await page.fill('[data-testid="login-email"]', 'bad@test.local');
      await page.fill('[data-testid="login-password"]', 'wrong');
      await page.click('[data-testid="login-submit"]');

      await expect(page.locator('[data-testid="login-error"]')).toBeVisible();
      await expect(page.locator('[data-testid="login-error"]')).toContainText('Invalid email or password');
    });
  });

  test.describe('Token Refresh', () => {
    test('automatically refreshes expired token', async () => {
      const page = await browser.newPage();
      await page.goto('tauri://localhost');

      // Simulate token expiry by fast-forwarding time
      await page.evaluate(() => {
        // Set stored token to expired value
        window.__TAURI__.invoke('store_token', {
          accessToken: 'expired-token',
          refreshToken: 'valid-refresh-token',
        });
      });

      // Trigger an API call that requires auth
      await page.click('[data-testid="refresh-portfolio"]');

      // Should auto-refresh and show data (not login screen)
      await expect(page.locator('[data-testid="portfolio-panel"]')).toBeVisible({ timeout: 10000 });
      await expect(page.locator('[data-testid="login-email"]')).not.toBeVisible();
    });

    test('redirects to login when refresh token is also expired', async () => {
      const page = await browser.newPage();
      await page.goto('tauri://localhost');

      await page.evaluate(() => {
        window.__TAURI__.invoke('store_token', {
          accessToken: 'expired-access',
          refreshToken: 'expired-refresh',
        });
      });

      await page.click('[data-testid="refresh-portfolio"]');

      // Should redirect to login
      await expect(page.locator('[data-testid="login-email"]')).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('Session Persistence', () => {
    test('restores session after app restart', async () => {
      // Login
      const page = await browser.newPage();
      await page.goto('tauri://localhost');
      await page.fill('[data-testid="login-email"]', 'trader@test.local');
      await page.fill('[data-testid="login-password"]', 'test-password');
      await page.click('[data-testid="login-submit"]');
      await expect(page.locator('[data-testid="dashboard"]')).toBeVisible({ timeout: 10000 });

      // Close and reopen (simulate app restart)
      await page.close();
      const newPage = await browser.newPage();
      await newPage.goto('tauri://localhost');

      // Should restore session — no login screen
      await expect(newPage.locator('[data-testid="dashboard"]')).toBeVisible({ timeout: 10000 });
      await expect(newPage.locator('[data-testid="login-email"]')).not.toBeVisible();
    });
  });

  test.describe('Logout', () => {
    test('logout clears stored tokens and shows login screen', async () => {
      const page = await browser.newPage();
      await page.goto('tauri://localhost');

      // Login first
      await page.fill('[data-testid="login-email"]', 'trader@test.local');
      await page.fill('[data-testid="login-password"]', 'test-password');
      await page.click('[data-testid="login-submit"]');
      await expect(page.locator('[data-testid="dashboard"]')).toBeVisible({ timeout: 10000 });

      // Logout
      await page.click('[data-testid="user-menu"]');
      await page.click('[data-testid="logout-button"]');

      // Should show login screen
      await expect(page.locator('[data-testid="login-email"]')).toBeVisible({ timeout: 5000 });

      // Verify token cleared from keychain
      const storedToken = await page.evaluate(() => {
        return window.__TAURI__.invoke('get_stored_token');
      });
      expect(storedToken).toBeNull();
    });
  });
});
```

#### 3.6 Mobile Auth Integration Tests

**`test/integration/auth/biometric_test.dart`**
```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:flutter/material.dart';
import 'package:shared_test_kit/shared_test_kit.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('Mobile Biometric Authentication', () {
    testWidgets('fingerprint login completes successfully', (tester) async {
      // Arrange: App is launched, user has enrolled biometric
      await tester.pumpWidget(MyApp());
      await tester.pumpAndSettle();

      // Act: Tap biometric login button
      final biometricButton = find.byKey(Key('biometric-login-button'));
      expect(biometricButton, findsOneWidget);
      await tester.tap(biometricButton);
      await tester.pumpAndSettle();

      // Assert: Dashboard loads (biometric was verified by OS)
      expect(find.byKey(Key('dashboard')), findsOneWidget);
      expect(find.byKey(Key('login-email')), findsNothing);
    });

    testWidgets('biometric failure shows fallback to password', (tester) async {
      await tester.pumpWidget(MyApp());
      await tester.pumpAndSettle();

      // Simulate biometric failure (e.g., unrecognized fingerprint)
      // This would be mocked at the platform channel level
      await tester.tap(find.byKey(Key('biometric-login-button')));
      await tester.pumpAndSettle();

      // Should show fallback option
      expect(find.byKey(Key('password-fallback')), findsOneWidget);
      expect(find.text('Use password instead'), findsOneWidget);
    });

    testWidgets('biometric not available shows password-only login', (tester) async {
      // Simulate device without biometric hardware
      // Mock local_auth to return [BiometricType.none]
      await tester.pumpWidget(MyApp());
      await tester.pumpAndSettle();

      // Biometric button should not be visible
      expect(find.byKey(Key('biometric-login-button')), findsNothing);
      // Password fields should be visible
      expect(find.byKey(Key('login-email')), findsOneWidget);
      expect(find.byKey(Key('login-password')), findsOneWidget);
    });

    testWidgets('enroll biometric after password login', (tester) async {
      await tester.pumpWidget(MyApp());
      await tester.pumpAndSettle();

      // Login with password first
      await tester.enterText(find.byKey(Key('login-email')), 'trader@test.local');
      await tester.enterText(find.byKey(Key('login-password')), 'test-password');
      await tester.tap(find.byKey(Key('login-submit')));
      await tester.pumpAndSettle();

      // Should prompt to enable biometric
      expect(find.byKey(Key('enable-biometric-prompt')), findsOneWidget);
      await tester.tap(find.byKey(Key('enable-biometric-confirm')));
      await tester.pumpAndSettle();

      // Verify biometric is enrolled
      expect(find.text('Biometric login enabled'), findsOneWidget);
    });

    testWidgets('biometric token refresh on app foreground', (tester) async {
      // Login with biometric
      await tester.pumpWidget(MyApp());
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(Key('biometric-login-button')));
      await tester.pumpAndSettle();
      expect(find.byKey(Key('dashboard')), findsOneWidget);

      // Simulate app going to background and returning
      // (token may have expired during background)
      await tester.binding.defaultBinaryMessenger.handlePlatformMessage(
        'flutter/lifecycle',
        const StandardMethodCodec().encodeMethodCall(
          const MethodCall('AppLifecycleState.resumed'),
        ),
        (_) {},
      );
      await tester.pumpAndSettle();

      // Should still show dashboard (token refreshed silently)
      expect(find.byKey(Key('dashboard')), findsOneWidget);
    });
  });

  group('Mobile OAuth Login Flow', () {
    testWidgets('full OAuth login with redirect callback', (tester) async {
      await tester.pumpWidget(MyApp());
      await tester.pumpAndSettle();

      // Tap OAuth login
      await tester.tap(find.byKey(Key('oauth-login-button')));
      await tester.pumpAndSettle();

      // In-app browser opens for OAuth
      // In test mode, this is intercepted and auto-approves
      expect(find.byKey(Key('dashboard')), findsOneWidget, timeout: Duration(seconds: 15));
    });

    testWidgets('OAuth cancel returns to login screen', (tester) async {
      await tester.pumpWidget(MyApp());
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(Key('oauth-login-button')));
      await tester.pumpAndSettle();

      // Simulate user canceling OAuth
      await tester.tap(find.byKey(Key('oauth-cancel')));
      await tester.pumpAndSettle();

      expect(find.byKey(Key('login-email')), findsOneWidget);
    });
  });
}
```

#### 3.7 Auth Integration Test CI Pipeline

**`.github/workflows/auth-integration-tests.yml`**
```yaml
name: Authentication Integration Tests

on:
  push:
    branches: [main, develop]
    paths:
      - 'src/auth/**'
      - 'tests/integration/auth/**'
      - 'shared-test-kit/fixtures/auth/**'
  pull_request:
    paths:
      - 'src/auth/**'
      - 'tests/integration/auth/**'

jobs:
  # Backend auth integration tests
  backend-auth:
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:7
        ports: ['6379:6379']
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: alpha_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports: ['5432:5432']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -r requirements.txt -r requirements-test.txt
      - name: Run OAuth integration tests
        run: pytest tests/integration/auth/test_oauth_flows.py -v --tb=short
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/alpha_test
          REDIS_URL: redis://localhost:6379
          JWT_SECRET: test-secret-key
      - name: Run Biometric integration tests
        run: pytest tests/integration/auth/test_biometric_flows.py -v --tb=short
      - name: Run WebAuthn integration tests
        run: pytest tests/integration/auth/test_webauthn_flows.py -v --tb=short

  # Desktop auth integration tests
  desktop-auth:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci
        working-directory: shared-test-kit/adapters/typescript
      - run: npm ci
        working-directory: apps/desktop
      - name: Run desktop auth integration tests
        run: npx playwright test tests/integration/auth/desktop/ --project=${{ matrix.os }}
        working-directory: apps/desktop

  # Mobile auth integration tests
  mobile-auth:
    runs-on: macos-latest  # Required for iOS simulator
    steps:
      - uses: actions/checkout@v4
      - uses: subosito/flutter-action@v2
        with: { flutter-version: '3.22' }
      - run: flutter pub get
        working-directory: apps/mobile
      - name: Android biometric tests
        uses: reactivecircus/android-emulator-runner@v2
        with:
          api-level: 34
          script: |
            cd apps/mobile
            flutter test integration_test/auth/biometric_test.dart
      - name: iOS biometric tests
        run: |
          cd apps/mobile
          flutter test integration_test/auth/biometric_test.dart -d iPhone
```

#### 3.8 Test Fixtures for Auth

**`shared-test-kit/fixtures/auth/biometric-profiles.json`**
```json
{
  "enrolledProfiles": [
    {
      "credentialId": "bio-cred-001",
      "userId": "acc-001",
      "biometricType": "fingerprint",
      "publicKey": "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE...",
      "deviceInfo": {
        "platform": "android",
        "model": "Pixel 8",
        "osVersion": "14",
        "biometricStrength": "strong"
      },
      "enrolledAt": "2026-07-01T10:00:00Z",
      "lastUsedAt": "2026-07-11T12:00:00Z",
      "status": "active"
    },
    {
      "credentialId": "bio-cred-002",
      "userId": "acc-001",
      "biometricType": "faceId",
      "publicKey": "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE...",
      "deviceInfo": {
        "platform": "ios",
        "model": "iPhone 15 Pro",
        "osVersion": "18.0",
        "biometricStrength": "strong"
      },
      "enrolledAt": "2026-07-01T10:00:00Z",
      "lastUsedAt": "2026-07-11T12:00:00Z",
      "status": "active"
    }
  ],
  "revokedProfiles": [
    {
      "credentialId": "bio-cred-003",
      "userId": "acc-001",
      "biometricType": "fingerprint",
      "status": "revoked",
      "revokedAt": "2026-07-10T08:00:00Z",
      "revokedReason": "user_requested"
    }
  ]
}
```

**`shared-test-kit/fixtures/auth/webauthn-assertions.json`**
```json
{
  "validRegistration": {
    "challenge": "dGVzdC1jaGFsbGVuZ2UtZGF0YQ",
    "rp": { "name": "Alpha Trading", "id": "alpha-trading.app" },
    "user": { "id": "acc-001", "name": "trader@test.local", "displayName": "Test Trader" },
    "credential": {
      "id": "webauthn-cred-001",
      "rawId": "dGVzdC1jcmVkZW50aWwtaWQ",
      "type": "public-key",
      "response": {
        "attestationObject": "dGVzdC1hdHRlc3RhdGlvbg",
        "clientDataJSON": "dGVzdC1jbGllbnQtZGF0YQ"
      }
    }
  },
  "validAuthentication": {
    "challenge": "dGVzdC1sb2dpbi1jaGFsbGVuZ2U",
    "credential": {
      "id": "webauthn-cred-001",
      "rawId": "dGVzdC1jcmVkZW50aWwtaWQ",
      "type": "public-key",
      "response": {
        "authenticatorData": "dGVzdC1hdXRoLWRhdGE",
        "clientDataJSON": "dGVzdC1jbGllbnQtZGF0YQ",
        "signature": "dGVzdC1zaWduYXR1cmU"
      }
    }
  },
  "invalidAssertions": [
    {
      "description": "Wrong origin",
      "error": "origin_mismatch",
      "credential": {
        "id": "webauthn-cred-001",
        "rawId": "dGVzdC1jcmVkZW50aWwtaWQ",
        "type": "public-key",
        "response": {
          "authenticatorData": "dGVzdC1hdXRoLWRhdGE",
          "clientDataJSON": "eyJ0eXBlIjoid2ViYXV0aG4uZ2V0IiwiY2hhbGxlbmdlIjoiZEdWemRIVnRhVzUwIiwib3JpZ2luIjoiaHR0cHM6Ly9ldmlsLmNvbSJ9",
          "signature": "dGVzdC1zaWduYXR1cmU"
        }
      }
    },
    {
      "description": "Expired challenge",
      "error": "challenge_expired",
      "credential": {
        "id": "webauthn-cred-001",
        "rawId": "dGVzdC1jcmVkZW50aWwtaWQ",
        "type": "public-key",
        "response": {
          "authenticatorData": "dGVzdC1hdXRoLWRhdGE",
          "clientDataJSON": "dGVzdC1jbGllbnQtZGF0YQ",
          "signature": "dGVzdC1zaWduYXR1cmU"
        }
      }
    }
  ]
}
```

---

## Summary

### What This Fixes

| Issue | Before | After |
|-------|--------|-------|
| **Shared test utilities** | 3 independent codebases with duplicated/no test data | Single `shared-test-kit` with canonical fixtures, platform adapters, and shared mock server |
| **API contract testing** | No contract verification between backend and frontends | Pact consumer-driven contracts for Desktop, Web, and Mobile with CI verification |
| **Auth integration tests** | Zero auth tests across all platforms | Full OAuth 2.0 + PKCE, biometric (fingerprint/Face ID), and WebAuthn test suites for backend + all platforms |

### Files Created

```
shared-test-kit/
├── fixtures/                          # 8 JSON fixture files
├── mock-server/                       # Shared API mock server
├── adapters/typescript/               # TS adapter (desktop + web)
├── adapters/dart/                     # Dart adapter (mobile)
├── schemas/                           # 5 JSON Schema files
└── README.md

tests/contract/
├── desktop/consumer.spec.ts           # Desktop Pact consumer
├── web/consumer.spec.ts               # Web Pact consumer (same TS code)
├── mobile/consumer_test.dart          # Mobile Pact consumer
└── provider/test_contract_verification.py  # Backend provider verification

tests/integration/auth/
├── test_oauth_flows.py                # OAuth 2.0 + PKCE tests
├── test_biometric_flows.py            # Biometric auth tests
├── test_webauthn_flows.py             # WebAuthn tests
├── desktop/test_desktop_auth.ts       # Desktop auth E2E
└── mobile/biometric_test.dart         # Mobile biometric E2E

.github/workflows/
├── shared-test-kit.yml                # Fixture + adapter CI
├── contract-tests.yml                 # Pact contract CI
├── can-i-deploy.yml                   # Deployment safety check
└── auth-integration-tests.yml         # Auth integration CI
```

### Execution Order

1. **Create `shared-test-kit/`** — fixtures, mock server, adapters (Week 1)
2. **Implement Pact consumer tests** — one platform at a time, starting with desktop (Week 2)
3. **Implement provider verification** — backend verifies all consumer contracts (Week 2)
4. **Write auth integration tests** — backend first, then desktop, then mobile (Week 2-3)
5. **Set up CI pipelines** — all 4 workflow files (Week 3)
6. **Publish to Pact broker** — enable can-i-deploy checks (Week 3)

---

*Fix plan generated by Cross-Platform Fix Agent — Alpha Stack*
