# Quantum Unsolved Problems in Finance & Trading — Alpha Stack Research

**Date:** 2026-07-11  
**Status:** Research Complete — Actionable Intelligence

---

## Executive Summary

Quantum computing in finance is transitioning from theoretical promise to **early-stage production reality**. The key insight: quantum isn't replacing classical computing — it's solving specific **NP-hard sub-problems** that classical systems approximate poorly. For Alpha Stack, the actionable window is NOW for architecture decisions, and 12-24 months for direct quantum integration.

---

## 1. What Classical AI CANNOT Solve (Mathematical Limits)

### 1.1 Combinatorial Explosion in Portfolio Optimization

**The Problem:** Selecting K assets from N candidates creates a search space of C(N,K). For a real portfolio:
- 50 stocks from S&P 500 = C(500,50) ≈ 10⁵⁰ combinations
- With constraints (sector limits, ESG, tax lots) → NP-hard

**Why classical fails:** Markowitz Mean-Variance Optimization gives closed-form solutions for *unconstrained* portfolios. Adding cardinality constraints ("pick exactly K from N") makes it **non-convex and NP-hard**. Classical heuristics (genetic algorithms, simulated annealing) find *local* optima, not *global*.

**Current classical workarounds and their limits:**
- Branch-and-bound: O(2^N) worst case
- Simulated annealing: no optimality guarantee
- HRP (Hierarchical Risk Parity): avoids covariance inversion but doesn't optimize returns
- All degrade rapidly beyond ~200 assets with complex constraints

### 1.2 Real-Time Optimization Across Thousands of Assets

**The Problem:** Simultaneously optimizing portfolio weights, hedging ratios, and execution schedules across 1,000+ instruments with real-time market data.

**Why classical fails:** Covariance matrix estimation for N assets requires O(N²) parameters. For 5,000 assets = 12.5M parameters. Matrix inversion is O(N³). With market regimes changing in milliseconds, this is intractable for true real-time optimization.

### 1.3 High-Dimensional Partial Differential Equations

**The Problem:** Pricing derivatives on multiple underlyings (basket options, rainbow options) requires solving the multi-dimensional Black-Scholes PDE.

**Why classical fails:**
- 1 underlying: solvable analytically (Black-Scholes formula)
- 3-5 underlyings: Monte Carlo with 10⁶-10⁸ paths (minutes)
- 50+ underlyings: Monte Carlo variance explodes, needs 10¹²+ paths
- Curse of dimensionality: computation scales exponentially with dimensions

**Quantum advantage:** Quantum Monte Carlo (amplitude estimation) provides **quadratic speedup**: O(1/ε) → O(1/√ε) for error ε. This turns hours into minutes for high-dimensional pricing.

### 1.4 True Random Number Generation

**The Problem:** All classical "random" number generators are deterministic (PRNGs). For Monte Carlo simulations and cryptographic applications, true randomness matters.

**Why classical fails fundamentally:** Von Neumann proved classical systems cannot generate true randomness. PRNGs are periodic and predictable given enough output.

**Quantum advantage:** Quantum measurement produces **certified true randomness**. Companies like Quantis and ID Quantique already sell quantum RNG devices. This is the **most immediately deployable** quantum advantage.

### 1.5 Simulating Complex Market Microstructures

**The Problem:** Modeling order book dynamics, market maker behavior, and liquidity cascades requires simulating many interacting agents with quantum-like correlations.

**Why classical fails:** The number of possible order book states grows exponentially with the number of price levels and participants. Agent-based models with >100 agents become intractable.

### 1.6 Breaking Cryptographic Primitives

**The Problem:** RSA-2048 and ECC-256 (used in crypto wallets, API authentication, blockchain) can be broken by Shor's algorithm on a sufficiently powerful quantum computer.

**Why this is mathematically impossible classically:** Integer factorization is believed to be in BQP (solvable by quantum polynomial time) but not in P (classical polynomial time). The best classical algorithm (general number field sieve) is sub-exponential: O(exp(c·(ln n)^(1/3)·(ln ln n)^(2/3))).

---

## 2. What Quantum CAN Solve — Algorithms & Mechanisms

### 2.1 Quantum Annealing (D-Wave Approach)

**Mechanism:** Encodes optimization problems as energy minimization. The system starts in a superposition of all states and quantum tunneling finds the global minimum.

**Finance application:** Portfolio selection, trade scheduling, index tracking

**Current status:**
- D-Wave Advantage: 5,000+ qubits, available via AWS Braket
- **Production-ready for QUBO (Quadratic Unconstrained Binary Optimization) problems**
- 2026 paper (SquareOne Capital): QAOA achieved **Sharpe Ratio 1.81** vs Simulated Annealing's 1.31 and HRP's 0.98 on 10-stock direct indexing
- Limitation: High turnover (76.8%) — optimization needs transaction cost constraints

### 2.2 Quantum Approximate Optimization Algorithm (QAOA)

**Mechanism:** Hybrid quantum-classical variational algorithm. Quantum processor evaluates cost function in superposition; classical optimizer tunes parameters.

**Finance application:** Cardinality-constrained portfolio optimization, direct indexing, ESG-constrained mandates

**Key innovation (2026):** XY-Mixer Hamiltonian with Dicke state initialization ensures **only valid portfolios** are explored — no penalty terms needed. Trotterized initialization mitigates barren plateau problem.

**Current state:**
- Demonstrated on 10-asset problems with real market data (2025 backtest)
- Scaling to 50-100 assets requires ~100-500 logical qubits
- Current hardware: ~1,000 noisy qubits → limited to ~20-30 asset problems with error mitigation

### 2.3 Quantum Monte Carlo / Amplitude Estimation

**Mechanism:** Quantum amplitude estimation provides quadratic speedup over classical Monte Carlo for estimating expected values.

**Finance application:** Options pricing, VaR calculation, credit risk modeling

**Speedup:**
- Classical Monte Carlo: O(1/ε²) samples for error ε
- Quantum Monte Carlo: O(1/ε) quantum operations
- For ε = 0.001: **1,000x fewer operations**

**Current state:**
- Theoretically proven since 2020 (Stamatopoulos et al., Quantum journal)
- Requires fault-tolerant quantum computers (estimated 10,000+ logical qubits)
- Timeline: **5-10 years** for practical advantage
- Near-term: quantum-inspired classical algorithms (Tensor Networks) provide partial speedup NOW

### 2.4 Grover's Algorithm for Search

**Mechanism:** Quadratic speedup for searching unsorted databases. O(N) → O(√N).

**Finance application:**
- Pattern matching in historical market data
- Anomaly detection in trade surveillance
- Searching optimal parameters in strategy backtesting

**Current state:** Requires fault-tolerant quantum computers. Not practical on NISQ hardware for financial applications.

### 2.5 Quantum Machine Learning (QML)

**Mechanism:** Quantum kernels, variational quantum circuits, quantum neural networks for pattern recognition in high-dimensional feature spaces.

**Finance application:** Market regime detection, alpha signal generation, credit scoring

**Current state:**
- Quantum kernel methods: theoretically promising for specific data structures
- Quantum neural networks: no proven advantage over classical deep learning yet
- Aioi Insurance: testing quantum neural networks for risk classification on Amazon Braket
- **Verdict: Experimental. No production advantage demonstrated yet.**

### 2.6 Variational Quantum Eigensolver (VQE) for Optimization

**Mechanism:** Finds ground state of a Hamiltonian using variational ansatz. Can be adapted for optimization by encoding cost functions as Hamiltonians.

**Finance application:** General optimization problems, risk parity, factor model calibration

**Current state:** Works on NISQ hardware but limited by barren plateaus. Useful for small problems (<30 variables).

---

## 3. Current State of Quantum Finance (2026)

### 3.1 What's Working in Production vs Experimental

| Application | Status | Who | Notes |
|---|---|---|---|
| **Quantum RNG** | ✅ PRODUCTION | Quantis, ID Quantique, Cloudflare | Commercially available, plug-and-play |
| **Portfolio optimization (small)** | 🔬 PILOT | JPMorgan, Goldman Sachs, SquareOne Capital | 10-30 assets, research-grade |
| **Options pricing (Monte Carlo)** | 🔬 RESEARCH | Goldman Sachs, IBM | Awaiting fault-tolerant hardware |
| **Fraud detection** | 🔬 PILOT | HSBC, Barclays | Quantum-enhanced anomaly detection |
| **Risk modeling** | 🔬 RESEARCH | JPMorgan (Onyx), Citi | Quantum Monte Carlo for VaR |
| **Quantum-inspired classical** | ✅ PRODUCTION | Multiple | Tensor networks, simulated annealing |
| **Post-quantum crypto** | ✅ DEPLOYING | NIST, Google, Cloudflare | NIST PQC standards finalized 2024 |

### 3.2 Financial Institutions Active in Quantum

**Tier 1 — Production/Pilot:**
- **JPMorgan Chase:** Quantum research lab since 2017. Focus: portfolio optimization, derivatives pricing. Partnership with IBM. Published QAOA portfolio papers.
- **Goldman Sachs:** Quantum Monte Carlo research for options pricing. Partnership with AWS Braket and QC Ware.
- **HSBC:** Partnered with IBM for quantum-secured communications. Quantum risk modeling pilots.

**Tier 2 — Research:**
- **Citi:** Quantum optimization for settlement and clearing
- **Barclays:** Quantum machine learning for fraud detection
- **BNP Paribas:** Quantum Monte Carlo for credit risk
- **Standard Chartered:** Quantum random number generation

**Tier 3 — Exploring:**
- **Morgan Stanley, Deutsche Bank, UBS** — quantum working groups, no public pilots yet

### 3.3 Quantum Computing as a Service (QCaaS)

| Platform | Hardware Access | Pricing (approx.) | Best For |
|---|---|---|---|
| **IBM Quantum** | 127-1,121 qubit superconducting | Free tier (limited); ~$1.60/sec for premium | Qiskit Finance SDK, portfolio optimization |
| **Amazon Braket** | IonQ (trapped ion), Rigetti (superconducting), QuEra (neutral atom), D-Wave (annealing) | $0.30/task + $0.01/gate-second | Multi-hardware comparison, hybrid algorithms |
| **Google Cirq** | Sycamore-class processors | Research access only (as of 2026) | Algorithm development, quantum ML |
| **Microsoft Azure Quantum** | IonQ, Quantinuum, others | Pay-per-use via Azure credits | Enterprise integration, Q# development |
| **D-Wave Leap** | 5,000+ qubit annealer | Free 1 min/month; ~$0.00019/qpu-second | QUBO problems, portfolio selection |

**Cost reality check:** For a typical portfolio optimization run:
- D-Wave: ~$0.01-0.10 per problem instance
- Gate-based (IBM/Braket): ~$1-10 per run with error mitigation
- Classical equivalent: ~$0.001 on commodity hardware
- **Quantum is 10-1000x more expensive per run** — justified only where classical CANNOT find good solutions

### 3.4 Timeline for Practical Quantum Advantage in Trading

| Milestone | Estimated Timeline | Confidence |
|---|---|---|
| Quantum RNG in trading systems | **NOW** | High |
| Quantum-inspired algorithms on classical hardware | **NOW** | High |
| Post-quantum cryptography deployment | **2024-2027** (in progress) | High |
| Quantum advantage for portfolio optimization (50+ assets) | **2028-2030** | Medium |
| Quantum Monte Carlo for options pricing | **2030-2035** | Medium |
| Quantum ML for alpha generation | **2030-2035** | Low |
| Fault-tolerant quantum computing | **2030-2035** | Medium |
| Quantum advantage for real-time trading | **2035+** | Low |

---

## 4. Hybrid Classical-Quantum Approaches

### 4.1 The Hybrid Architecture Pattern

The proven pattern (2026) is **quantum as co-processor**, not quantum as computer:

```
┌─────────────────────────────────────────────┐
│              Classical System                │
│  ┌─────────┐  ┌──────────┐  ┌───────────┐  │
│  │ Data    │→ │ Problem  │→ │ Classical │  │
│  │ Pipeline│  │ Encoding │  │ Post-     │  │
│  │         │  │ (QUBO)   │  │ Processing│  │
│  └─────────┘  └────┬─────┘  └───────────┘  │
│                    │                        │
│              ┌─────▼─────┐                  │
│              │  Quantum   │                  │
│              │  Co-proc   │                  │
│              │ (D-Wave/   │                  │
│              │  IBM/IonQ) │                  │
│              └───────────┘                  │
└─────────────────────────────────────────────┘
```

### 4.2 Quantum-Inspired Algorithms on Classical Hardware

**Available NOW, no quantum hardware needed:**

1. **Tensor Network Methods:** Classical algorithms inspired by quantum entanglement structure. Microsoft's Quantum-Inspired Optimization (QIO) on Azure.
   - Speedup: 10-100x over standard simulated annealing for combinatorial problems
   - Works on: portfolio selection, scheduling, vehicle routing

2. **Simulated Quantum Annealing:** Classical simulation of quantum tunneling dynamics.
   - Better escape from local minima than classical simulated annealing
   - D-Wave's problem structure can be classically simulated for moderate sizes

3. **Quantum Monte Carlo (classical):** Path-integral Monte Carlo methods that borrow quantum statistical mechanics concepts.
   - Already used in physics; applicable to financial Monte Carlo

### 4.3 When to Use Quantum vs Classical for Alpha Stack

| Sub-Problem | Classical | Quantum | Hybrid | Timeline |
|---|---|---|---|---|
| **Signal generation (alpha)** | ✅ Best | ❌ No advantage | — | Now |
| **Feature engineering** | ✅ Best | ❌ No advantage | — | Now |
| **Risk factor models** | ✅ Best | ❌ No advantage | — | Now |
| **Small portfolio opt (<30 assets)** | ✅ Fine | 🔬 Comparable | — | Now |
| **Large portfolio opt (50+ assets, constraints)** | ⚠️ Approximate | ✅ Potentially better | ✅ Best | 2028+ |
| **Options pricing (low-dim)** | ✅ Best | ❌ Overhead not worth it | — | Now |
| **Options pricing (high-dim, 10+ underlyings)** | ⚠️ Slow | ✅ Quadratic speedup | ✅ Best | 2030+ |
| **Random number generation** | ⚠️ Pseudo | ✅ True random | ✅ Best | Now |
| **Encryption/crypto security** | ✅ Current | ⚠️ Threat | ✅ PQC migration | Now (prep) |
| **Real-time order routing** | ✅ Best | ❌ Too slow (latency) | — | Now |
| **Backtesting** | ✅ Best | ❌ No advantage | — | Now |
| **Market microstructure simulation** | ⚠️ Limited | 🔬 Promising | 🔬 Research | 2030+ |

---

## 5. Quantum Threats to Trading Systems

### 5.1 Shor's Algorithm and RSA/ECC

**The threat:** Shor's algorithm factors integers and computes discrete logarithms in polynomial time on a quantum computer. This breaks:
- **RSA-2048/4096:** Used for API authentication, TLS, document signing
- **ECC (secp256k1):** Used in Ethereum, Bitcoin, and most blockchain systems
- **ECDSA signatures:** Used for transaction authentication

**Timeline to threat:**
- Current largest factored number by quantum: ~1,000,000 (trivial)
- RSA-2048 requires: ~4,000 logical qubits = ~20 million physical qubits (with error correction)
- Current hardware: ~1,000-1,121 noisy physical qubits
- **Estimate: 10-20 years** for cryptographically relevant quantum computer
- **"Harvest now, decrypt later" threat is REAL TODAY** — adversaries can store encrypted data now and decrypt it later

**Federal Reserve perspective (Sep 2025):** Published paper on "Harvest Now Decrypt Later" risks to financial infrastructure. Recommends immediate migration planning.

### 5.2 Quantum Attacks on Blockchain

**Bitcoin/Ethereum vulnerability:**
- Bitcoin uses ECDSA (secp256k1) for transaction signing — **broken by Shor's algorithm**
- Ethereum uses the same curve
- Grover's algorithm provides quadratic speedup for mining (but this is less threatening)
- **Reused addresses are most vulnerable** (public key is exposed after first transaction)

**Mitigation:**
- Bitcoin: P2PKH addresses hide public key until spend → quantum must crack before confirmation
- Ethereum: Account abstraction could enable post-quantum signature schemes
- Timeline: Quantum threat to blockchain estimated 2035-2040

### 5.3 Post-Quantum Cryptography (PQC) for Trading Systems

**NIST Standards (finalized 2024):**
| Algorithm | Type | Use Case | Status |
|---|---|---|---|
| **ML-KEM (CRYSTALS-Kyber)** | Lattice-based KEM | Key exchange | NIST standard |
| **ML-DSA (CRYSTALS-Dilithium)** | Lattice-based signature | Digital signatures | NIST standard |
| **SLH-DSA (SPHINCS+)** | Hash-based signature | Backup signatures | NIST standard |
| **FN-DSA (FALCON)** | Lattice-based signature | Compact signatures | NIST standard |

**Migration timeline:**
- 2024-2026: Standards finalized, libraries available
- 2025-2027: Early adopters (Google Chrome, Cloudflare already support ML-KEM)
- 2027-2030: Regulatory mandates expected (NSA, NIST guidelines)
- 2030-2035: Full migration expected across financial systems

---

## 6. Actionable Steps for Alpha Stack

### 6.1 What to Integrate TODAY (Zero Quantum Hardware Required)

#### Priority 1: Post-Quantum Cryptography Migration
```bash
# Immediate: Audit current cryptographic dependencies
# - TLS certificates: Plan migration to hybrid (classical + PQC)
# - API authentication: Plan for PQC-compatible schemes
# - Wallet security: Monitor Bitcoin/Ethereum PQC upgrade proposals
```
**Action:** Begin cryptographic inventory. Identify all RSA/ECC dependencies. Test ML-KEM/ML-DSA in staging.  
**Cost:** Engineering time only (~2-4 weeks for audit)  
**Risk if skipped:** "Harvest now, decrypt later" attacks on stored financial data

#### Priority 2: Quantum-Inspired Optimization (Classical Hardware)
```python
# Use quantum-inspired solvers for portfolio optimization NOW
# Microsoft QIO, D-Wave's classical solvers, or open-source alternatives

# Example: Quantum-inspired simulated annealing for portfolio selection
from dwave.samplers import SimulatedAnnealingSampler  # Works on classical hardware
sampler = SimulatedAnnealingSampler()
response = sampler.sample_qubo(Q, num_reads=1000)
```
**Action:** Replace standard simulated annealing with quantum-inspired solvers in portfolio module.  
**Cost:** Free (open-source libraries)  
**Expected improvement:** 10-30% better solution quality for combinatorial problems

#### Priority 3: Quantum Random Number Generation
```python
# Option A: Hardware QRNG device (~$1,500-5,000)
# Option B: Cloud-based QRNG (e.g., Quantis QRNG API)
# Option C: Use quantum-certified randomness from IBM Quantum (free tier)
```
**Action:** Replace PRNG with QRNG for Monte Carlo simulations and cryptographic nonces.  
**Cost:** $0 (cloud) to $5,000 (hardware)  
**Expected improvement:** Eliminates PRNG periodicity bias in simulations

### 6.2 Architecture Decisions That Enable Quantum Later

#### Design Pattern: Problem Abstraction Layer
```python
# Design portfolio optimization as a QUBO problem from the start
# This enables drop-in quantum solvers when available

class PortfolioOptimizer:
    def __init__(self, solver="classical"):
        self.solver = solver  # "classical", "quantum_annealing", "qaoa"
    
    def optimize(self, returns, constraints):
        # Build QUBO matrix (works for both classical and quantum)
        Q = self._build_qubo(returns, constraints)
        
        if self.solver == "classical":
            return self._classical_solve(Q)
        elif self.solver == "quantum_annealing":
            return self._dwave_solve(Q)
        elif self.solver == "qaoa":
            return self._qaoa_solve(Q)
    
    def _build_qubo(self, returns, constraints):
        """Encode portfolio optimization as QUBO — universal formulation"""
        # This is the key abstraction: same problem, different solver
        ...
```

**Action:** Refactor optimization modules to use QUBO/Ising formulations.  
**Cost:** 1-2 weeks engineering  
**Benefit:** Instant quantum plug-and-play when hardware matures

#### Infrastructure Decisions
1. **Use containerized microservices** — quantum calls are API-based, fit naturally
2. **Implement solver abstraction layers** — swap classical ↔ quantum without code changes
3. **Design for hybrid workflows** — quantum for sub-problems, classical for orchestration
4. **Monitor quantum hardware roadmaps** — IBM (100K qubits by 2033), Google (1M qubits by 2029)

### 6.3 Quantum-Resistant Security Implementation

**Immediate actions:**
1. Enable TLS 1.3 with hybrid key exchange (X25519 + ML-KEM-768) where supported
2. Use hybrid signatures for document signing (ECDSA + ML-DSA)
3. Implement crypto-agility: design systems to swap algorithms without code rewrites
4. Monitor NIST PQC implementation guides

**Code-level:**
```python
# Example: Hybrid TLS configuration (conceptual)
# liboqs-python for post-quantum support
from oqs import KeyEncapsulation, Signature

# Hybrid key exchange
kem = KeyEncapsulation("Kyber768")
public_key = kem.generate_keypair()

# Hybrid signature
sig = Signature("Dilithium3")
sig_public_key = sig.generate_keypair()
```

### 6.4 Cost-Benefit Analysis

| Investment | Cost | Benefit | ROI Timeline |
|---|---|---|---|
| PQC migration audit | $0 (internal) | Risk mitigation for future threats | Immediate (risk avoidance) |
| Quantum-inspired solvers | $0 (open-source) | 10-30% better optimization | 1-3 months |
| QRNG integration | $0-5K | True randomness, better simulations | 1 month |
| QUBO architecture refactor | 2 weeks eng | Future quantum readiness | 6-12 months |
| AWS Braket experimentation | $100-500/month | Hands-on quantum experience | 3-6 months |
| Quantum computing team hire | $150-250K/year | Strategic capability | 12-24 months |
| Full quantum integration | $50-200K/year | Portfolio optimization edge | 2028-2030 |

### 6.5 Recommended Alpha Stack Quantum Roadmap

```
Q3 2026: FOUNDATION
├── Complete cryptographic audit
├── Deploy quantum-inspired solvers (classical)
├── Experiment with D-Wave/IBM via cloud (proof of concept)
└── Refactor portfolio optimizer to QUBO formulation

Q4 2026: PILOT
├── Integrate QRNG into Monte Carlo module
├── Test QAOA on small portfolio (10-20 assets) via IBM/AWS
├── Begin PQC hybrid deployment for internal APIs
└── Establish quantum vendor relationships

2027: SCALE
├── Deploy PQC hybrid for production APIs
├── Quantum annealing for portfolio rebalancing (weekly/monthly)
├── Quantum-inspired optimization for real-time risk
└── Quantum ML experiments for regime detection

2028-2030: ADVANTAGE
├── Quantum portfolio optimization in production (if hardware scales)
├── Quantum Monte Carlo for complex derivatives
├── Full PQC migration
└── Quantum-enhanced alpha signals (if QML proves viable)
```

---

## 7. Key Takeaways for Alpha Stack

1. **Don't wait for quantum hardware** — quantum-inspired algorithms and PQC are actionable NOW
2. **Portfolio optimization is the #1 near-term opportunity** — QAOA already outperforms classical on small problems
3. **The hybrid model wins** — quantum for specific sub-problems, classical for everything else
4. **PQC migration is urgent** — "harvest now, decrypt later" makes this a today problem
5. **Architecture matters more than hardware** — design QUBO-compatible systems now, plug in quantum later
6. **Cost is low to experiment** — AWS Braket, IBM Quantum free tiers enable hands-on learning for <$100/month
7. **The 2028-2030 window** is when quantum advantage for finance becomes real — be ready before competitors

---

## Sources & References

- SquareOne Capital (2026): "QAOA with XY-Mixers for Direct Indexing" — Sharpe 1.81 vs 1.31 SA
- Federal Reserve (Sep 2025): "Harvest Now Decrypt Later" PQC risk paper
- IBM Quantum / Qiskit Finance SDK documentation
- Amazon Braket pricing and hardware specifications
- NIST Post-Quantum Cryptography Standards (2024): ML-KEM, ML-DSA, SLH-DSA
- Stamatopoulos et al. (2020): "Option Pricing using Quantum Computers" — Quantum journal
- The Quantum Insider (Mar 2026): "15+ Global Banks Probing Quantum Technologies"
- CFA Institute (Apr 2026): "Quantum Computing vs AI" analysis
- Arxiv: Multiple 2025-2026 papers on QAOA portfolio optimization, quantum Monte Carlo
