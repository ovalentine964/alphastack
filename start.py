"""AlphaStack Full System Launcher.

Wires together all components and starts the API server:
- Event Bus (Redis Streams)
- Broker Registry (CCXT, MT5, OANDA)
- Data Pipeline (LiveMarketFeed → MarketDataStore)
- Risk Governor
- Agent Orchestrator (LangGraph multi-agent pipeline)
- FastAPI REST + WebSocket server
"""

from __future__ import annotations

import asyncio
import os
import sys
import traceback
from contextlib import asynccontextmanager

from alphastack.utils.logger import setup_logging, get_logger

# Setup logging first
setup_logging(level="INFO", json_output=True)
logger = get_logger(__name__)


async def build_system():
    """Build and wire all system components. Returns (app, cleanup_fn)."""
    from alphastack.core.config import get_settings
    settings = get_settings()

    # ------------------------------------------------------------------
    # 1. Event Bus (Redis Streams)
    # ------------------------------------------------------------------
    event_bus = None
    try:
        from alphastack.core.events import EventBus
        event_bus = EventBus(redis_url=settings.redis.url)
        await event_bus.connect()
        logger.info("system.event_bus_connected")
    except Exception as exc:
        logger.info("system.event_bus_skipped", reason=str(exc))

    # ------------------------------------------------------------------
    # 2. Broker Registry
    # ------------------------------------------------------------------
    registry = None
    try:
        from alphastack.brokers.registry import BrokerRegistry
        registry = BrokerRegistry()

        # Auto-register from env
        ccxt_key = settings.ccxt.api_key.get_secret_value()
        if ccxt_key:
            from alphastack.brokers.ccxt_connector import CCXTConnector
            connector = CCXTConnector(
                exchange_id=settings.ccxt.exchange,
                api_key=ccxt_key,
                secret=settings.ccxt.secret.get_secret_value(),
                sandbox=settings.ccxt.sandbox,
            )
            registry.register("ccxt", connector, default=True)
            try:
                await connector.connect()
                logger.info("system.ccxt_connected", exchange=settings.ccxt.exchange)
            except Exception as exc:
                logger.warning("system.ccxt_connect_failed", error=str(exc))

        # MT5
        mt5_login = settings.mt5.login
        if mt5_login:
            try:
                from alphastack.brokers.mt5_connector import MT5Connector
                mt5_conn = MT5Connector()
                registry.register("mt5", mt5_conn)
                logger.info("system.mt5_registered", login=mt5_login)
            except Exception as exc:
                logger.warning("system.mt5_register_failed", error=str(exc))

        logger.info("system.broker_registry_ready", brokers=registry.names)
    except Exception as exc:
        logger.info("system.broker_registry_skipped", reason=str(exc))

    # ------------------------------------------------------------------
    # 3. Risk Governor
    # ------------------------------------------------------------------
    risk_governor = None
    try:
        from alphastack.risk.governor import RiskGovernor
        risk_governor = RiskGovernor(
            account_balance=10000.0,  # Default, updated from broker
        )
        logger.info("system.risk_governor_created")
    except Exception as exc:
        logger.info("system.risk_governor_skipped", reason=str(exc))

    # ------------------------------------------------------------------
    # 4. Data Pipeline (optional — needs live feeds)
    # ------------------------------------------------------------------
    data_pipeline = None
    try:
        from alphastack.data.pipeline import DataPipeline
        from alphastack.data.feed import LiveMarketFeed
        from alphastack.data.store import MarketDataStore

        # Only create if we have a connected broker
        if registry and registry.connected_brokers():
            store = MarketDataStore(
                enable_cache=True,
                enable_timescale=False,  # Disable TimescaleDB for startup simplicity
            )

            feeds = []
            # Create feeds from connected brokers
            for name in registry.connected_brokers():
                connector = registry.get(name)
                if connector is None:
                    continue
                if name.startswith("ccxt"):
                    feed = LiveMarketFeed(
                        connector=connector,
                        event_bus=event_bus,
                        market_type="crypto",
                    )
                    feeds.append(feed)

            if feeds:
                data_pipeline = DataPipeline(
                    feeds=feeds,
                    store=store,
                    event_bus=event_bus,
                )
                logger.info("system.data_pipeline_created", feeds=len(feeds))
    except Exception as exc:
        logger.info("system.data_pipeline_skipped", reason=str(exc))

    # ------------------------------------------------------------------
    # 5. Orchestrator (LangGraph multi-agent pipeline)
    # ------------------------------------------------------------------
    orchestrator = None
    try:
        from alphastack.agents.orchestrator.graph import AlphaStackOrchestrator
        orchestrator = AlphaStackOrchestrator(
            event_bus=event_bus,
            human_in_the_loop=False,  # Auto-approve for API mode
            broker_registry=registry,
            data_pipeline=data_pipeline,
        )

        # Wire RiskGovernor into the risk agent
        if risk_governor is not None:
            orchestrator.risk_agent.set_risk_governor(risk_governor)

        logger.info("system.orchestrator_created")
    except Exception as exc:
        logger.error("system.orchestrator_failed", error=str(exc), exc_info=True)

    # ------------------------------------------------------------------
    # 6. Build FastAPI app with injected dependencies
    # ------------------------------------------------------------------
    from alphastack.api.rest import deps
    if event_bus:
        deps.set_event_bus(event_bus)
    if registry:
        deps.set_broker_registry(registry)
    if orchestrator:
        deps.set_orchestrator(orchestrator)
    if data_pipeline:
        deps.set_data_pipeline(data_pipeline)

    from alphastack.api.rest.app import create_app
    app = create_app()

    # Store references for cleanup
    app.state.event_bus = event_bus
    app.state.registry = registry
    app.state.orchestrator = orchestrator
    app.state.data_pipeline = data_pipeline
    app.state.risk_governor = risk_governor

    logger.info(
        "system.built",
        event_bus=event_bus is not None,
        registry=registry is not None and bool(registry.names),
        orchestrator=orchestrator is not None,
        data_pipeline=data_pipeline is not None,
        risk_governor=risk_governor is not None,
    )

    return app


async def shutdown_system(app):
    """Gracefully shutdown all system components."""
    logger.info("system.shutting_down")

    # Stop data pipeline
    if hasattr(app.state, "data_pipeline") and app.state.data_pipeline:
        try:
            await app.state.data_pipeline.stop()
        except Exception:
            pass

    # Disconnect brokers
    if hasattr(app.state, "registry") and app.state.registry:
        try:
            await app.state.registry.disconnect_all()
        except Exception:
            pass

    # Close event bus
    if hasattr(app.state, "event_bus") and app.state.event_bus:
        try:
            await app.state.event_bus.close()
        except Exception:
            pass

    logger.info("system.shutdown_complete")


def main():
    """Entry point — build system and start uvicorn."""
    import uvicorn

    print(f"Python: {sys.version}")
    print(f"PORT: {os.environ.get('PORT', 'not set')}")

    try:
        logger.info("system.building")
        app = asyncio.run(build_system())
        logger.info("system.starting_server")
    except Exception as exc:
        logger.error("system.build_failed", error=str(exc), exc_info=True)
        traceback.print_exc()
        sys.exit(1)

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
