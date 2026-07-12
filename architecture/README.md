# Alpha Stack — Architecture Index

> **Generated:** 2026-07-13 · **Total Documents:** 34 · **Total Size:** ~3.2 GB
>
> Every architecture document traces back to its source research. See the **Source Research** column for provenance.

---

## Core Platform Architecture

| # | Architecture Document | Research Source(s) | Size |
|---|---|---|---|
| 1 | [System Architecture](architecture_system.md) | [Tech Stack](../research/research_02_tech_stack_architecture.md), [Trading Bot Landscape](../research/research_01_crypto_forex_trading_bot_landscape.md) | 97K |
| 2 | [Trading Engine](architecture_trading_engine.md) | [Strategy Steps 1–16](../research/strategy/) | 111K |
| 3 | [Risk Management](architecture_risk.md) | [Financial Crises](../research/research_financial_crises.md), [Market Microstructure](../research/research_market_microstructure.md) | 124K |
| 4 | [Broker Abstraction Layer](architecture_broker.md) | [Broker Connection](../research/research_broker_connection.md), [Hybrid Broker](../research/research_hybrid_broker_architecture.md), [Multi-Broker](../research/research_multi_broker_integration.md) | 112K |
| 5 | [Broker Routing](architecture_broker_routing.md) | [Hybrid Broker Routing](../research/research_hybrid_broker_routing.md) | 61K |
| 6 | [Data Storage](architecture_data_storage.md) | [Data Sources](../research/research_data_sources.md), [Tech Data Sources](../research/tech/research_data_sources.md) | 86K |
| 7 | [Data Pipeline](architecture_data.md) | [Data Sources](../research/research_data_sources.md) | 49K |
| 8 | [Database](architecture_database.md) | [Data Sources](../research/research_data_sources.md), [Tech Stack](../research/research_02_tech_stack_architecture.md) | 96K |
| 9 | [Security](architecture_security.md) | [Regulatory](../research/security/research_regulatory.md), [Quantum Unresolved](../research/security/research_quantum_unsolved.md) | 75K |
| 10 | [Deployment](architecture_deployment.md) | [Scalability](../research/research_scalability.md) | 115K |

## Trading Strategy & Markets

| # | Architecture Document | Research Source(s) | Size |
|---|---|---|---|
| 11 | [Backtesting](architecture_backtesting.md) | [Strategy Steps 1–16](../research/strategy/) | 130K |
| 12 | [Crypto-Specific Trading](architecture_crypto.md) | [Trading Pairs](../research/market/research_07_trading_pairs.md), [Market Microstructure](../research/market/research_market_microstructure.md) | 90K |
| 13 | [Pair-Specific Strategy](architecture_pair_strategy.md) | [Trading Pairs](../research/market/research_07_trading_pairs.md) (partial) | 79K |
| 14 | [Strategy Flow](architecture_strategy_flow.md) | [Strategy Steps 1–16](../research/strategy/) | 82K |
| 15 | [Trade Monitoring](architecture_trade_monitoring.md) | Cross-cutting — risk and strategy research | 167K |

## AI / ML Systems

| # | Architecture Document | Research Source(s) | Size |
|---|---|---|---|
| 16 | [AI/ML Models](architecture_ai_models.md) | [ML/AI Curriculum](../research/curriculum/research_curriculum_ml_ai.md) | 102K |
| 17 | [ML Pipeline](architecture_ml_pipeline.md) | [ML/AI Curriculum](../research/curriculum/research_curriculum_ml_ai.md) | 132K |
| 18 | [Model Selection & Access](architecture_model_selection.md) | None — Architectural decision by design team | 39K |
| 19 | [Multi-Agent System](architecture_multi_agent.md) | [Multi-Agent Systems](../research/research_03_loop_multiagent_systems.md) | 82K |
| 20 | [Agent Communication](architecture_agent_communication.md) | [Multi-Agent Systems](../research/research_03_loop_multiagent_systems.md) | 100K |
| 21 | [Memory System](architecture_memory.md) | [Multi-Agent Systems](../research/research_03_loop_multiagent_systems.md) (partial) | 118K |

## User Interface

| # | Architecture Document | Research Source(s) | Size |
|---|---|---|---|
| 22 | [Desktop App UI](architecture_ui_desktop.md) | [Desktop App Architecture](../research/platform/research_12_desktop_app_architecture.md) | 108K |
| 23 | [Web App UI](architecture_ui_web.md) | [Web App](../research/platform/research_web_app.md) | 134K |
| 24 | [Mobile App UI](architecture_ui_mobile.md) | [Mobile App](../research/platform/research_mobile_app.md) | 166K |

## Curriculum & Education

| # | Architecture Document | Research Source(s) | Size |
|---|---|---|---|
| 25 | [CS/IT Curriculum](architecture_curriculum_cs.md) | [ML/AI Curriculum](../research/curriculum/research_curriculum_ml_ai.md) | 97K |
| 26 | [Economics Curriculum](architecture_curriculum_economics.md) | [ML/AI Curriculum](../research/curriculum/research_curriculum_ml_ai.md) | 82K |
| 27 | [Curriculum Integration](architecture_curriculum_integration.md) | [ML/AI Curriculum](../research/curriculum/research_curriculum_ml_ai.md) | 54K |
| 28 | [Mathematics Curriculum](architecture_curriculum_math.md) | [ML/AI Curriculum](../research/curriculum/research_curriculum_ml_ai.md) | 53K |
| 29 | [Statistics Curriculum](architecture_curriculum_statistics.md) | [ML/AI Curriculum](../research/curriculum/research_curriculum_ml_ai.md) | 60K |

## Operations & Cross-Cutting

| # | Architecture Document | Research Source(s) | Size |
|---|---|---|---|
| 30 | [Integration Testing](architecture_testing.md) | Cross-cutting — all research | 117K |
| 31 | [Monitoring](architecture_monitoring.md) | Cross-cutting — deployment and risk research | 88K |
| 32 | [Performance Optimization](architecture_performance.md) | [Scalability](../research/research_scalability.md) | 87K |
| 33 | [Channel & Notification](architecture_channels.md) | None — Architectural decision by design team | 36K |
| 34 | [Documentation](architecture_documentation.md) | None — Architectural decision by design team | 63K |

---

## Traceability Legend

- **Direct mapping** — Architecture document directly implements research findings
- **Partial** — Research informed the architecture but significant architect innovation was added
- **Cross-cutting** — Architecture draws from multiple research sources across domains
- **None** — Pure architectural design decision with no dedicated research source

## Related Directories

- [`../research/`](../research/) — Source research documents (54+ files)
- [`../reviews/`](../reviews/) — Architecture review reports (47+ files)
- [`../fixes/`](../fixes/) — Fix reports addressing review findings (32+ files)
