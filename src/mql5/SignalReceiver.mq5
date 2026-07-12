//+------------------------------------------------------------------+
//|                                              SignalReceiver.mq5   |
//|              AlphaStack Signal Receiver - Standalone EA           |
//|          Focused ZeroMQ signal receiver and trade executor         |
//|                              Magic Number: 20260713               |
//+------------------------------------------------------------------+
#property copyright "AlphaStack"
#property link      "https://github.com/alphastack"
#property version   "1.00"
#property description "AlphaStack Signal Receiver - ZeroMQ Trade Executor"
#property strict

#include "Include/AlphaStack.mqh"
#include "Include/ZmqBridge.mqh"

//--- Input parameters
input string   ZMQ_SUB_ENDPOINT  = "tcp://127.0.0.1:5555";  // Signal subscribe endpoint
input string   ZMQ_PUB_ENDPOINT  = "tcp://127.0.0.1:5556";  // Result publish endpoint
input int      POLL_INTERVAL_MS  = 50;                       // Polling interval (ms)
input double   MAX_SLIPPAGE      = 3.0;                      // Max slippage (points)
input double   MAX_LOT_SIZE      = 10.0;                     // Max lot size per trade
input int      MAX_POSITIONS     = 10;                       // Max open positions
input bool     ENABLE_TRAILING   = true;                     // Enable trailing stop
input int      TRAILING_START    = 50;                       // Trailing start (points in profit)
input int      TRAILING_STEP     = 20;                       // Trailing step (points)
input bool     ENABLE_BREAK_EVEN = true;                     // Enable break-even
input int      BREAK_EVEN_START  = 30;                       // Break-even start (points in profit)
input int      BREAK_EVEN_OFFSET = 5;                        // Break-even offset (points)
input bool     VERBOSE_LOGGING   = true;                     // Verbose logging

//--- Global objects
CZmqBridge    *g_bridge     = NULL;
CTrade        *g_trade      = NULL;
CPositionInfo *g_pos_info   = NULL;
CAccountInfo  *g_account    = NULL;

//--- Statistics
int            g_total_signals    = 0;
int            g_executed_signals = 0;
int            g_failed_signals   = 0;
double         g_total_pnl        = 0;
double         g_total_commission  = 0;

//+------------------------------------------------------------------+
//| OnInit                                                             |
//+------------------------------------------------------------------+
int OnInit()
  {
   Print(AS_PREFIX, " SignalReceiver v", AS_VERSION, " starting...");

   // Create objects
   g_bridge   = new CZmqBridge();
   g_trade    = new CTrade();
   g_pos_info = new CPositionInfo();
   g_account  = new CAccountInfo();

   if(g_bridge == NULL || g_trade == NULL)
      return INIT_FAILED;

   // Configure trade
   g_trade.SetExpertMagicNumber(AS_MAGIC);
   g_trade.SetDeviationInPoints((ulong)MAX_SLIPPAGE);
   g_trade.SetTypeFilling(ORDER_FILLING_IOC);

   // Connect ZMQ
   if(!g_bridge.Connect(ZMQ_SUB_ENDPOINT, ZMQ_PUB_ENDPOINT))
     {
      Print(AS_PREFIX, " WARNING: ZMQ connect failed, will retry...");
     }

   // Set timer
   EventSetMillisecondTimer(POLL_INTERVAL_MS);

   Print(AS_PREFIX, " SignalReceiver ready. Listening on: ", ZMQ_SUB_ENDPOINT);
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//| OnDeinit                                                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   Print(AS_PREFIX, " SignalReceiver stopping. Signals: ",
         g_executed_signals, "/", g_total_signals, " executed. PnL: ", g_total_pnl);

   EventKillTimer();

   if(g_bridge != NULL)
     {
      g_bridge.Disconnect();
      delete g_bridge;
     }
   if(g_trade != NULL)    delete g_trade;
   if(g_pos_info != NULL) delete g_pos_info;
   if(g_account != NULL)  delete g_account;
  }

//+------------------------------------------------------------------+
//| OnTimer - main loop                                                |
//+------------------------------------------------------------------+
void OnTimer()
  {
   // Handle reconnection
   if(!g_bridge.IsConnected())
     {
      g_bridge.Reconnect();
      return;
     }

   // Update heartbeat
   g_bridge.UpdateHeartbeat();

   // Process signals
   ProcessSignals();

   // Manage trailing stops and break-even
   if(ENABLE_TRAILING || ENABLE_BREAK_EVEN)
      ManagePositions();
  }

//+------------------------------------------------------------------+
//| OnTick - low-latency signal check                                  |
//+------------------------------------------------------------------+
void OnTick()
  {
   if(g_bridge != NULL && g_bridge.IsConnected())
      ProcessSignals();
  }

//+------------------------------------------------------------------+
//| Process incoming signals                                           |
//+------------------------------------------------------------------+
void ProcessSignals()
  {
   string json;
   int max_per_tick = 10;  // Process up to 10 signals per tick

   for(int i = 0; i < max_per_tick; i++)
     {
      json = g_bridge.ReceiveSignal();
      if(json == "") break;

      g_total_signals++;
      ProcessOneSignal(json);
     }
  }

//+------------------------------------------------------------------+
//| Process a single signal                                            |
//+------------------------------------------------------------------+
void ProcessOneSignal(const string json)
  {
   // Parse signal
   SAlphaSignal signal;
   if(!ParseSignalJson(json, signal))
     {
      Print(AS_PREFIX, " ERROR: Invalid signal JSON");
      g_bridge.SendNack("", "Invalid JSON");
      g_failed_signals++;
      return;
     }

   // ACK immediately
   g_bridge.SendAck(signal.signal_id);

   // Check position limits
   if(signal.type == SIGNAL_BUY || signal.type == SIGNAL_SELL ||
      signal.type == SIGNAL_BUY_LIMIT || signal.type == SIGNAL_SELL_LIMIT ||
      signal.type == SIGNAL_BUY_STOP || signal.type == SIGNAL_SELL_STOP)
     {
      if(PositionsTotal() >= MAX_POSITIONS)
        {
         STradeResult result;
         result.signal_id = signal.signal_id;
         result.status    = STATUS_FAILED;
         result.error     = "Max positions reached: " + IntegerToString(MAX_POSITIONS);
         result.timestamp = TimeCurrent();
         g_bridge.SendResult(signal.signal_id, result);
         g_failed_signals++;
         return;
        }

      // Check lot size
      if(signal.volume > MAX_LOT_SIZE)
         signal.volume = MAX_LOT_SIZE;
     }

   // Execute
   STradeResult result;
   result.Reset();
   result.signal_id = signal.signal_id;
   result.timestamp = TimeCurrent();

   bool success = ExecuteSignal(signal, result);

   result.status = success ? STATUS_EXECUTED : STATUS_FAILED;

   // Send result
   g_bridge.SendResult(signal.signal_id, result);

   if(success)
     {
      g_executed_signals++;
      if(VERBOSE_LOGGING)
         Print(AS_PREFIX, " [OK] ", signal.signal_id, " ", SignalTypeToString(signal.type),
               " ", signal.symbol, " vol=", DoubleToString(signal.volume, 2),
               " ticket=", result.ticket);
     }
   else
     {
      g_failed_signals++;
      Print(AS_PREFIX, " [FAIL] ", signal.signal_id, " ", result.error);
     }
  }

//+------------------------------------------------------------------+
//| Parse signal JSON                                                  |
//+------------------------------------------------------------------+
bool ParseSignalJson(const string json, SAlphaSignal &signal)
  {
   signal.Reset();

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
   signal.timestamp   = TimeCurrent();

   if(signal.magic == 0)
      signal.magic = AS_MAGIC;

   if(signal.symbol == "")
      return false;

   return true;
  }

//+------------------------------------------------------------------+
//| Execute signal                                                     |
//+------------------------------------------------------------------+
bool ExecuteSignal(const SAlphaSignal &signal, STradeResult &result)
  {
   CSymbolInfo sym;
   if(!sym.Name(signal.symbol))
     {
      result.error = "Symbol not found: " + signal.symbol;
      return false;
     }
   sym.Refresh();

   switch(signal.type)
     {
      case SIGNAL_BUY:
        {
         double price = sym.Ask();
         double sl = signal.stop_loss > 0 ? NormalizeDouble(signal.stop_loss, sym.Digits()) : 0;
         double tp = signal.take_profit > 0 ? NormalizeDouble(signal.take_profit, sym.Digits()) : 0;
         double vol = NormalizeVolume(signal.symbol, signal.volume);

         if(g_trade.Buy(vol, signal.symbol, price, sl, tp, signal.comment))
           {
            result.ticket      = g_trade.ResultOrder();
            result.fill_price  = g_trade.ResultPrice();
            result.fill_volume = g_trade.ResultVolume();
            result.slippage    = MathAbs(result.fill_price - price);
            return true;
           }
         result.error = g_trade.ResultComment();
         return false;
        }

      case SIGNAL_SELL:
        {
         double price = sym.Bid();
         double sl = signal.stop_loss > 0 ? NormalizeDouble(signal.stop_loss, sym.Digits()) : 0;
         double tp = signal.take_profit > 0 ? NormalizeDouble(signal.take_profit, sym.Digits()) : 0;
         double vol = NormalizeVolume(signal.symbol, signal.volume);

         if(g_trade.Sell(vol, signal.symbol, price, sl, tp, signal.comment))
           {
            result.ticket      = g_trade.ResultOrder();
            result.fill_price  = g_trade.ResultPrice();
            result.fill_volume = g_trade.ResultVolume();
            result.slippage    = MathAbs(result.fill_price - price);
            return true;
           }
         result.error = g_trade.ResultComment();
         return false;
        }

      case SIGNAL_BUY_LIMIT:
        {
         double price = NormalizeDouble(signal.price, sym.Digits());
         double sl = signal.stop_loss > 0 ? NormalizeDouble(signal.stop_loss, sym.Digits()) : 0;
         double tp = signal.take_profit > 0 ? NormalizeDouble(signal.take_profit, sym.Digits()) : 0;
         double vol = NormalizeVolume(signal.symbol, signal.volume);

         if(g_trade.BuyLimit(vol, price, signal.symbol, sl, tp, ORDER_TIME_GTC, 0, signal.comment))
           {
            result.ticket = g_trade.ResultOrder();
            return true;
           }
         result.error = g_trade.ResultComment();
         return false;
        }

      case SIGNAL_SELL_LIMIT:
        {
         double price = NormalizeDouble(signal.price, sym.Digits());
         double sl = signal.stop_loss > 0 ? NormalizeDouble(signal.stop_loss, sym.Digits()) : 0;
         double tp = signal.take_profit > 0 ? NormalizeDouble(signal.take_profit, sym.Digits()) : 0;
         double vol = NormalizeVolume(signal.symbol, signal.volume);

         if(g_trade.SellLimit(vol, price, signal.symbol, sl, tp, ORDER_TIME_GTC, 0, signal.comment))
           {
            result.ticket = g_trade.ResultOrder();
            return true;
           }
         result.error = g_trade.ResultComment();
         return false;
        }

      case SIGNAL_BUY_STOP:
        {
         double price = NormalizeDouble(signal.price, sym.Digits());
         double sl = signal.stop_loss > 0 ? NormalizeDouble(signal.stop_loss, sym.Digits()) : 0;
         double tp = signal.take_profit > 0 ? NormalizeDouble(signal.take_profit, sym.Digits()) : 0;
         double vol = NormalizeVolume(signal.symbol, signal.volume);

         if(g_trade.BuyStop(vol, price, signal.symbol, sl, tp, ORDER_TIME_GTC, 0, signal.comment))
           {
            result.ticket = g_trade.ResultOrder();
            return true;
           }
         result.error = g_trade.ResultComment();
         return false;
        }

      case SIGNAL_SELL_STOP:
        {
         double price = NormalizeDouble(signal.price, sym.Digits());
         double sl = signal.stop_loss > 0 ? NormalizeDouble(signal.stop_loss, sym.Digits()) : 0;
         double tp = signal.take_profit > 0 ? NormalizeDouble(signal.take_profit, sym.Digits()) : 0;
         double vol = NormalizeVolume(signal.symbol, signal.volume);

         if(g_trade.SellStop(vol, price, signal.symbol, sl, tp, ORDER_TIME_GTC, 0, signal.comment))
           {
            result.ticket = g_trade.ResultOrder();
            return true;
           }
         result.error = g_trade.ResultComment();
         return false;
        }

      case SIGNAL_CLOSE:
        {
         ulong ticket = (ulong)signal.price;
         if(ticket > 0 && PositionSelectByTicket(ticket))
           {
            if(g_trade.PositionClose(ticket))
              {
               result.ticket = ticket;
               return true;
              }
           }
         // Try by symbol
         if(PositionSelect(signal.symbol))
           {
            ticket = PositionGetInteger(POSITION_TICKET);
            if(g_trade.PositionClose(ticket))
              {
               result.ticket = ticket;
               return true;
              }
           }
         result.error = "Position not found";
         return false;
        }

      case SIGNAL_MODIFY:
        {
         ulong ticket = (ulong)signal.price;
         if(!PositionSelectByTicket(ticket) && !PositionSelect(signal.symbol))
           {
            result.error = "Position not found for modify";
            return false;
           }
         ticket = PositionGetInteger(POSITION_TICKET);
         double sl = signal.stop_loss > 0 ? NormalizeDouble(signal.stop_loss, sym.Digits())
                    : PositionGetDouble(POSITION_SL);
         double tp = signal.take_profit > 0 ? NormalizeDouble(signal.take_profit, sym.Digits())
                    : PositionGetDouble(POSITION_TP);

         if(g_trade.PositionModify(ticket, sl, tp))
           {
            result.ticket = ticket;
            return true;
           }
         result.error = g_trade.ResultComment();
         return false;
        }

      case SIGNAL_CLOSE_ALL:
        {
         int closed = CloseAllPositions();
         result.fill_volume = closed;
         return (closed > 0);
        }

      default:
         result.error = "Unknown signal type";
         return false;
     }
  }

//+------------------------------------------------------------------+
//| Normalize volume to broker constraints                             |
//+------------------------------------------------------------------+
double NormalizeVolume(const string symbol, double volume)
  {
   double min_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double step    = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);

   if(volume < min_lot) volume = min_lot;
   if(volume > max_lot) volume = max_lot;
   if(volume > MAX_LOT_SIZE) volume = MAX_LOT_SIZE;

   // Round to step
   if(step > 0)
      volume = MathFloor(volume / step) * step;

   return NormalizeDouble(volume, 2);
  }

//+------------------------------------------------------------------+
//| Close all positions with our magic                                 |
//+------------------------------------------------------------------+
int CloseAllPositions()
  {
   int closed = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != AS_MAGIC) continue;

      if(g_trade.PositionClose(ticket))
         closed++;
     }
   return closed;
  }

//+------------------------------------------------------------------+
//| Manage trailing stops and break-even                               |
//+------------------------------------------------------------------+
void ManagePositions()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != AS_MAGIC) continue;

      if(!PositionSelectByTicket(ticket)) continue;

      long   pos_type    = PositionGetInteger(POSITION_TYPE);
      double open_price  = PositionGetDouble(POSITION_PRICE_OPEN);
      double current_sl  = PositionGetDouble(POSITION_SL);
      double current_tp  = PositionGetDouble(POSITION_TP);
      double bid         = SymbolInfoDouble(PositionGetString(POSITION_SYMBOL), SYMBOL_BID);
      double ask         = SymbolInfoDouble(PositionGetString(POSITION_SYMBOL), SYMBOL_ASK);
      long   digits      = SymbolInfoInteger(PositionGetString(POSITION_SYMBOL), SYMBOL_DIGITS);
      double point       = SymbolInfoDouble(PositionGetString(POSITION_SYMBOL), SYMBOL_POINT);

      if(point <= 0) continue;

      double profit_points = 0;
      double new_sl = 0;

      if(pos_type == POSITION_TYPE_BUY)
        {
         profit_points = (bid - open_price) / point;

         // Break-even
         if(ENABLE_BREAK_EVEN && profit_points >= BREAK_EVEN_START)
           {
            double be_price = NormalizeDouble(open_price + BREAK_EVEN_OFFSET * point, (int)digits);
            if(current_sl < be_price || current_sl == 0)
              {
               g_trade.PositionModify(ticket, be_price, current_tp);
              }
           }

         // Trailing stop
         if(ENABLE_TRAILING && profit_points >= TRAILING_START)
           {
            new_sl = NormalizeDouble(bid - TRAILING_STEP * point, (int)digits);
            if(new_sl > current_sl || current_sl == 0)
              {
               g_trade.PositionModify(ticket, new_sl, current_tp);
              }
           }
        }
      else if(pos_type == POSITION_TYPE_SELL)
        {
         profit_points = (open_price - ask) / point;

         // Break-even
         if(ENABLE_BREAK_EVEN && profit_points >= BREAK_EVEN_START)
           {
            double be_price = NormalizeDouble(open_price - BREAK_EVEN_OFFSET * point, (int)digits);
            if(current_sl > be_price || current_sl == 0)
              {
               g_trade.PositionModify(ticket, be_price, current_tp);
              }
           }

         // Trailing stop
         if(ENABLE_TRAILING && profit_points >= TRAILING_START)
           {
            new_sl = NormalizeDouble(ask + TRAILING_STEP * point, (int)digits);
            if(new_sl < current_sl || current_sl == 0)
              {
               g_trade.PositionModify(ticket, new_sl, current_tp);
              }
           }
        }
     }
  }
//+------------------------------------------------------------------+
