//+------------------------------------------------------------------+
//|                                            AlphaStackBridge.mq5   |
//|                   AlphaStack Expert Advisor - Main Bridge         |
//|                      Receives signals via ZeroMQ, executes trades |
//|                              Magic Number: 20260713               |
//+------------------------------------------------------------------+
#property copyright "AlphaStack"
#property link      "https://github.com/alphastack"
#property version   "1.00"
#property description "AlphaStack MT5 Bridge - ZeroMQ Signal Receiver"
#property strict

#include "Include/AlphaStack.mqh"
#include "Include/ZmqBridge.mqh"

//--- Input parameters
input string   ZMQ_SUB_ENDPOINT  = "tcp://127.0.0.1:5555";  // Signal subscribe endpoint
input string   ZMQ_PUB_ENDPOINT  = "tcp://127.0.0.1:5556";  // Result publish endpoint
input string   ZMQ_PUSH_ENDPOINT = "tcp://127.0.0.1:5557";  // Heartbeat push endpoint
input int      SIGNAL_POLL_MS    = 100;                      // Signal polling interval (ms)
input int      HEARTBEAT_SEC     = 10;                       // Heartbeat interval (seconds)
input int      RECONNECT_SEC     = 5;                        // Reconnect delay (seconds)
input int      MAX_RECONNECTS    = 50;                       // Max reconnect attempts
input double   MAX_SLIPPAGE      = 3.0;                      // Max slippage (points)
input bool     ENABLE_LOGGING    = true;                     // Enable detailed logging

//--- Global objects
CZmqBridge    *g_bridge     = NULL;
CTrade        *g_trade      = NULL;
CPositionInfo *g_pos_info   = NULL;
CAccountInfo  *g_account    = NULL;
CSymbolInfo   *g_symbol     = NULL;

//--- State
datetime       g_last_heartbeat  = 0;
datetime       g_last_status     = 0;
int            g_signals_total   = 0;
int            g_signals_ok      = 0;
int            g_signals_fail    = 0;
bool           g_initialized     = false;

//+------------------------------------------------------------------+
//| Expert initialization function                                     |
//+------------------------------------------------------------------+
int OnInit()
  {
   // Validate magic number
   if(AS_MAGIC != 20260713)
     {
      Print(AS_PREFIX, " ERROR: Magic number mismatch!");
      return INIT_FAILED;
     }

   Print(AS_PREFIX, " v", AS_VERSION, " initializing...");
   Print(AS_PREFIX, " Magic: ", AS_MAGIC);

   // Create objects
   g_bridge   = new CZmqBridge();
   g_trade    = new CTrade();
   g_pos_info = new CPositionInfo();
   g_account  = new CAccountInfo();
   g_symbol   = new CSymbolInfo();

   if(g_bridge == NULL || g_trade == NULL)
     {
      Print(AS_PREFIX, " ERROR: Failed to create objects");
      return INIT_FAILED;
     }

   // Configure trade object
   g_trade.SetExpertMagicNumber(AS_MAGIC);
   g_trade.SetDeviationInPoints((ulong)MAX_SLIPPAGE);
   g_trade.SetTypeFilling(ORDER_FILLING_IOC);

   // Connect to ZMQ
   if(!g_bridge.Connect(ZMQ_SUB_ENDPOINT, ZMQ_PUB_ENDPOINT, ZMQ_PUSH_ENDPOINT))
     {
      Print(AS_PREFIX, " WARNING: Initial ZMQ connection failed, will retry...");
      // Non-fatal: continue and retry in OnTimer()
     }

   // Set timer for heartbeat and reconnection
   EventSetMillisecondTimer(SIGNAL_POLL_MS);

   g_initialized = true;
   Print(AS_PREFIX, " Initialized successfully");

   // Send initial status
   SendBridgeStatus("ONLINE");

   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//| Expert deinitialization function                                   |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   Print(AS_PREFIX, " Deinitializing, reason: ", reason);

   // Send offline status
   if(g_bridge != NULL && g_bridge.IsConnected())
     {
      SendBridgeStatus("OFFLINE");
      g_bridge.Disconnect();
     }

   // Cleanup
   EventKillTimer();

   if(g_bridge != NULL)   { delete g_bridge;   g_bridge   = NULL; }
   if(g_trade != NULL)    { delete g_trade;     g_trade    = NULL; }
   if(g_pos_info != NULL) { delete g_pos_info;  g_pos_info = NULL; }
   if(g_account != NULL)  { delete g_account;   g_account  = NULL; }
   if(g_symbol != NULL)   { delete g_symbol;    g_symbol   = NULL; }

   Print(AS_PREFIX, " Deinitialized");
  }

//+------------------------------------------------------------------+
//| Timer function - handles heartbeats, reconnection, signal polling |
//+------------------------------------------------------------------+
void OnTimer()
  {
   if(g_bridge == NULL) return;

   datetime now = TimeCurrent();

   // Handle reconnection if disconnected
   if(!g_bridge.IsConnected())
     {
      if(g_bridge.Reconnect())
        {
         Print(AS_PREFIX, " Reconnected to ZMQ");
         SendBridgeStatus("ONLINE");
        }
      return;
     }

   // Update heartbeat
   g_bridge.UpdateHeartbeat();

   // Check if bridge is alive
   if(!g_bridge.IsAlive())
     {
      Print(AS_PREFIX, " WARNING: Bridge heartbeat lost, reconnecting...");
      g_bridge.Reconnect();
      return;
     }

   // Poll for signals
   PollSignals();

   // Send periodic status (every 30 seconds)
   if(now - g_last_status >= 30)
     {
      SendBridgeStatus("ACTIVE");
      g_last_status = now;
     }
  }

//+------------------------------------------------------------------+
//| Tick function - optional signal check on every tick                |
//+------------------------------------------------------------------+
void OnTick()
  {
   // Signal polling is handled by timer, but we can also check here
   // for lower latency on active trading
   if(g_bridge != NULL && g_bridge.IsConnected())
     {
      PollSignals();
     }
  }

//+------------------------------------------------------------------+
//| Poll for incoming signals and execute                              |
//+------------------------------------------------------------------+
void PollSignals()
  {
   if(g_bridge == NULL || !g_bridge.IsConnected())
      return;

   string json = g_bridge.ReceiveSignal();
   if(json == "") return;

   // Parse signal
   SAlphaSignal signal;
   if(!ParseSignal(json, signal))
     {
      Print(AS_PREFIX, " ERROR: Failed to parse signal JSON");
      return;
     }

   g_signals_total++;

   // ACK the signal
   g_bridge.SendAck(signal.signal_id);

   // Execute signal
   STradeResult result;
   result.signal_id = signal.signal_id;
   result.timestamp = TimeCurrent();

   bool success = ExecuteSignal(signal, result);

   if(success)
     {
      g_signals_ok++;
      result.status = STATUS_EXECUTED;
     }
   else
     {
      g_signals_fail++;
      result.status = STATUS_FAILED;
     }

   // Send result back
   g_bridge.SendResult(signal.signal_id, result);

   if(ENABLE_LOGGING)
     {
      Print(AS_PREFIX, " Signal ", signal.signal_id,
            " | Type: ", SignalTypeToString(signal.type),
            " | ", signal.symbol,
            " | Status: ", SignalStatusToString(result.status),
            " | Ticket: ", result.ticket);
     }
  }

//+------------------------------------------------------------------+
//| Parse JSON into signal structure                                   |
//+------------------------------------------------------------------+
bool ParseSignal(const string json, SAlphaSignal &signal)
  {
   signal.Reset();

   // Extract fields
   signal.signal_id   = CJsonParser::GetString(json, "signal_id");
   signal.type        = (ENUM_SIGNAL_TYPE)(int)CJsonParser::GetInteger(json, "type");
   signal.symbol      = CJsonParser::GetString(json, "symbol");
   signal.volume      = CJsonParser::GetDouble(json, "volume");
   signal.price       = CJsonParser::GetDouble(json, "price");
   signal.stop_loss   = CJsonParser::GetDouble(json, "stop_loss");
   signal.take_profit = CJsonParser::GetDouble(json, "take_profit");
   signal.trailing_stop = CJsonParser::GetDouble(json, "trailing_stop");
   signal.comment     = CJsonParser::GetString(json, "comment");
   signal.magic       = (long)CJsonParser::GetInteger(json, "magic");
   signal.expiry      = (datetime)CJsonParser::GetInteger(json, "expiry");
   signal.timestamp   = TimeCurrent();

   // Validate
   if(signal.symbol == "" || signal.type == SIGNAL_NONE)
     {
      signal.error = "Invalid signal: missing symbol or type";
      return false;
     }

   // Set default magic if not specified
   if(signal.magic == 0)
      signal.magic = AS_MAGIC;

   return true;
  }

//+------------------------------------------------------------------+
//| Execute a parsed signal                                            |
//+------------------------------------------------------------------+
bool ExecuteSignal(const SAlphaSignal &signal, STradeResult &result)
  {
   // Prepare symbol info
   if(!g_symbol.Name(signal.symbol))
     {
      result.error = "Symbol not found: " + signal.symbol;
      Print(AS_PREFIX, " ERROR: ", result.error);
      return false;
     }

   g_symbol.Refresh();

   switch(signal.type)
     {
      case SIGNAL_BUY:
      case SIGNAL_SELL:
         return ExecuteMarket(signal, result);

      case SIGNAL_BUY_LIMIT:
      case SIGNAL_SELL_LIMIT:
         return ExecuteLimit(signal, result);

      case SIGNAL_BUY_STOP:
      case SIGNAL_SELL_STOP:
         return ExecuteStop(signal, result);

      case SIGNAL_CLOSE:
         return ExecuteClose(signal, result);

      case SIGNAL_MODIFY:
         return ExecuteModify(signal, result);

      case SIGNAL_CLOSE_ALL:
         return ExecuteCloseAll(signal, result);

      default:
         result.error = "Unknown signal type: " + IntegerToString(signal.type);
         return false;
     }
  }

//+------------------------------------------------------------------+
//| Execute market order                                               |
//+------------------------------------------------------------------+
bool ExecuteMarket(const SAlphaSignal &signal, STradeResult &result)
  {
   bool is_buy = (signal.type == SIGNAL_BUY);
   double price = is_buy ? g_symbol.Ask() : g_symbol.Bid();

   // Normalize volume
   double volume = g_symbol.LotsMin();
   if(signal.volume > 0)
      volume = signal.volume;
   volume = MathMax(volume, g_symbol.LotsMin());
   volume = MathMin(volume, g_symbol.LotsMax());

   // Normalize prices
   double sl = signal.stop_loss > 0 ? NormalizeDouble(signal.stop_loss, g_symbol.Digits()) : 0;
   double tp = signal.take_profit > 0 ? NormalizeDouble(signal.take_profit, g_symbol.Digits()) : 0;

   // Execute
   bool success;
   if(is_buy)
      success = g_trade.Buy(volume, signal.symbol, price, sl, tp, signal.comment);
   else
      success = g_trade.Sell(volume, signal.symbol, price, sl, tp, signal.comment);

   if(success)
     {
      result.ticket     = g_trade.ResultOrder();
      result.fill_price = g_trade.ResultPrice();
      result.fill_volume = g_trade.ResultVolume();
      result.slippage   = MathAbs(result.fill_price - price);
      return true;
     }
   else
     {
      result.error = "Trade failed: " + g_trade.ResultComment();
      Print(AS_PREFIX, " ERROR: ", result.error);
      return false;
     }
  }

//+------------------------------------------------------------------+
//| Execute limit order                                                |
//+------------------------------------------------------------------+
bool ExecuteLimit(const SAlphaSignal &signal, STradeResult &result)
  {
   bool is_buy = (signal.type == SIGNAL_BUY_LIMIT);
   double price = NormalizeDouble(signal.price, g_symbol.Digits());
   double sl = signal.stop_loss > 0 ? NormalizeDouble(signal.stop_loss, g_symbol.Digits()) : 0;
   double tp = signal.take_profit > 0 ? NormalizeDouble(signal.take_profit, g_symbol.Digits()) : 0;
   double volume = MathMax(signal.volume, g_symbol.LotsMin());

   bool success;
   if(is_buy)
      success = g_trade.BuyLimit(volume, price, signal.symbol, sl, tp, ORDER_TIME_GTC, 0, signal.comment);
   else
      success = g_trade.SellLimit(volume, price, signal.symbol, sl, tp, ORDER_TIME_GTC, 0, signal.comment);

   if(success)
     {
      result.ticket     = g_trade.ResultOrder();
      result.fill_price = price;
      result.fill_volume = volume;
      return true;
     }
   else
     {
      result.error = "Limit order failed: " + g_trade.ResultComment();
      return false;
     }
  }

//+------------------------------------------------------------------+
//| Execute stop order                                                 |
//+------------------------------------------------------------------+
bool ExecuteStop(const SAlphaSignal &signal, STradeResult &result)
  {
   bool is_buy = (signal.type == SIGNAL_BUY_STOP);
   double price = NormalizeDouble(signal.price, g_symbol.Digits());
   double sl = signal.stop_loss > 0 ? NormalizeDouble(signal.stop_loss, g_symbol.Digits()) : 0;
   double tp = signal.take_profit > 0 ? NormalizeDouble(signal.take_profit, g_symbol.Digits()) : 0;
   double volume = MathMax(signal.volume, g_symbol.LotsMin());

   bool success;
   if(is_buy)
      success = g_trade.BuyStop(volume, price, signal.symbol, sl, tp, ORDER_TIME_GTC, 0, signal.comment);
   else
      success = g_trade.SellStop(volume, price, signal.symbol, sl, tp, ORDER_TIME_GTC, 0, signal.comment);

   if(success)
     {
      result.ticket     = g_trade.ResultOrder();
      result.fill_price = price;
      result.fill_volume = volume;
      return true;
     }
   else
     {
      result.error = "Stop order failed: " + g_trade.ResultComment();
      return false;
     }
  }

//+------------------------------------------------------------------+
//| Close a specific position by ticket                                |
//+------------------------------------------------------------------+
bool ExecuteClose(const SAlphaSignal &signal, STradeResult &result)
  {
   ulong ticket = (ulong)signal.price;  // Ticket passed in price field

   if(!PositionSelectByTicket(ticket))
     {
      // Try by symbol
      if(!PositionSelect(signal.symbol))
        {
         result.error = "Position not found: " + signal.symbol + " / ticket " + IntegerToString(ticket);
         return false;
        }
      ticket = PositionGetInteger(POSITION_TICKET);
     }

   bool success = g_trade.PositionClose(ticket);

   if(success)
     {
      result.ticket     = ticket;
      result.fill_price = PositionGetDouble(POSITION_PRICE_CURRENT);
      result.fill_volume = PositionGetDouble(POSITION_VOLUME);
      return true;
     }
   else
     {
      result.error = "Close failed: " + g_trade.ResultComment();
      return false;
     }
  }

//+------------------------------------------------------------------+
//| Modify a position's SL/TP                                          |
//+------------------------------------------------------------------+
bool ExecuteModify(const SAlphaSignal &signal, STradeResult &result)
  {
   ulong ticket = (ulong)signal.price;  // Ticket in price field

   if(!PositionSelectByTicket(ticket) && !PositionSelect(signal.symbol))
     {
      result.error = "Position not found for modify";
      return false;
     }

   ticket = PositionGetInteger(POSITION_TICKET);
   double sl = signal.stop_loss > 0 ? NormalizeDouble(signal.stop_loss, g_symbol.Digits())
              : PositionGetDouble(POSITION_SL);
   double tp = signal.take_profit > 0 ? NormalizeDouble(signal.take_profit, g_symbol.Digits())
              : PositionGetDouble(POSITION_TP);

   bool success = g_trade.PositionModify(ticket, sl, tp);

   if(success)
     {
      result.ticket = ticket;
      return true;
     }
   else
     {
      result.error = "Modify failed: " + g_trade.ResultComment();
      return false;
     }
  }

//+------------------------------------------------------------------+
//| Close all positions with our magic number                          |
//+------------------------------------------------------------------+
bool ExecuteCloseAll(const SAlphaSignal &signal, STradeResult &result)
  {
   int closed = 0;
   int total  = PositionsTotal();

   for(int i = total - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;

      if(PositionGetInteger(POSITION_MAGIC) == AS_MAGIC)
        {
         if(g_trade.PositionClose(ticket))
            closed++;
        }
     }

   result.ticket     = 0;
   result.fill_volume = closed;
   result.error      = (closed > 0) ? "" : "No positions found with magic " + IntegerToString(AS_MAGIC);

   Print(AS_PREFIX, " CloseAll: closed ", closed, " positions");
   return (closed > 0);
  }

//+------------------------------------------------------------------+
//| Send bridge status message                                         |
//+------------------------------------------------------------------+
void SendBridgeStatus(const string status)
  {
   if(g_bridge == NULL || !g_bridge.IsConnected())
      return;

   CJsonBuilder jb;
   jb.BeginObject();
   jb.AddString("bridge", "AlphaStackBridge");
   jb.AddString("version", AS_VERSION);
   jb.AddString("status", status);
   jb.AddInteger("magic", AS_MAGIC);
   jb.AddInteger("signals_total", g_signals_total);
   jb.AddInteger("signals_ok", g_signals_ok);
   jb.AddInteger("signals_fail", g_signals_fail);
   jb.AddInteger("positions", PositionsTotal());
   jb.AddInteger("timestamp", (long)TimeCurrent());

   // Account info
   if(g_account != NULL)
     {
      jb.AddDouble("balance", g_account.Balance(), 2);
      jb.AddDouble("equity", g_account.Equity(), 2);
      jb.AddDouble("margin_free", g_account.FreeMargin(), 2);
     }

   jb.EndObject();

   g_bridge.SendStatus(jb.Build());
  }
//+------------------------------------------------------------------+
