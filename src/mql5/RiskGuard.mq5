//+------------------------------------------------------------------+
//|                                                  RiskGuard.mq5    |
//|                 AlphaStack Risk Guard EA                          |
//|          Monitors positions, enforces risk limits, emergency close|
//|                              Magic Number: 20260713               |
//+------------------------------------------------------------------+
#property copyright "AlphaStack"
#property link      "https://github.com/alphastack"
#property version   "1.00"
#property description "AlphaStack Risk Guard - Position Monitor & Risk Enforcer"
#property strict

#include "Include/AlphaStack.mqh"
#include "Include/ZmqBridge.mqh"

//--- Input parameters
input string   ZMQ_PUB_ENDPOINT    = "tcp://127.0.0.1:5558";  // Risk metrics publish endpoint
input int      MONITOR_INTERVAL_MS = 500;                      // Monitoring interval (ms)
input double   MAX_DRAWDOWN_PCT    = 10.0;                     // Max drawdown % (emergency close)
input double   MAX_DAILY_LOSS_PCT  = 5.0;                      // Max daily loss % (emergency close)
input double   MAX_POSITION_LOTS   = 10.0;                     // Max lot size per position
input int      MAX_OPEN_POSITIONS  = 10;                       // Max simultaneous positions
input double   MAX_RISK_PER_TRADE  = 2.0;                      // Max risk per trade %
input bool     ENABLE_EMERGENCY    = true;                     // Enable emergency close
input bool     MONITOR_ALL_MAGIC   = false;                    // Monitor all magic numbers
input int      RISK_REPORT_SEC     = 5;                        // Risk report interval (seconds)
input bool     CLOSE_ON_DRAWDOWN   = true;                     // Close on max drawdown breach
input bool     CLOSE_ON_DAILY_LOSS = true;                     // Close on max daily loss breach
input bool     CLOSE_ON_MAX_POSITIONS = false;                  // Close oldest when max positions exceeded

//--- Global objects
CZmqBridge    *g_bridge     = NULL;
CTrade        *g_trade      = NULL;
CAccountInfo  *g_account    = NULL;

//--- Risk tracking
SRiskParams    g_risk_params;
SRiskMetrics   g_risk_metrics;
double         g_day_start_balance = 0;
datetime       g_day_start_time    = 0;
double         g_peak_equity       = 0;
bool           g_emergency_active  = false;
datetime       g_last_report       = 0;
int            g_emergency_count   = 0;

//--- Alert flags (prevent spam)
bool           g_alert_drawdown    = false;
bool           g_alert_daily_loss  = false;
bool           g_alert_max_pos     = false;

//+------------------------------------------------------------------+
//| OnInit                                                             |
//+------------------------------------------------------------------+
int OnInit()
  {
   Print(AS_PREFIX, " RiskGuard v", AS_VERSION, " starting...");
   Print(AS_PREFIX, " Max Drawdown: ", DoubleToString(MAX_DRAWDOWN_PCT, 1), "%");
   Print(AS_PREFIX, " Max Daily Loss: ", DoubleToString(MAX_DAILY_LOSS_PCT, 1), "%");
   Print(AS_PREFIX, " Max Positions: ", MAX_OPEN_POSITIONS);
   Print(AS_PREFIX, " Max Lot Size: ", DoubleToString(MAX_POSITION_LOTS, 2));

   // Create objects
   g_bridge  = new CZmqBridge();
   g_trade   = new CTrade();
   g_account = new CAccountInfo();

   if(g_bridge == NULL || g_trade == NULL || g_account == NULL)
      return INIT_FAILED;

   // Configure trade
   g_trade.SetExpertMagicNumber(AS_MAGIC);

   // Initialize risk parameters
   g_risk_params.Reset();
   g_risk_params.max_drawdown_pct   = MAX_DRAWDOWN_PCT;
   g_risk_params.max_daily_loss_pct = MAX_DAILY_LOSS_PCT;
   g_risk_params.max_position_lots  = MAX_POSITION_LOTS;
   g_risk_params.max_open_positions = MAX_OPEN_POSITIONS;
   g_risk_params.max_risk_per_trade = MAX_RISK_PER_TRADE;

   // Initialize tracking
   g_day_start_balance = g_account.Balance();
   g_peak_equity       = g_account.Equity();
   g_day_start_time    = StringToTime(TimeToString(TimeCurrent(), TIME_DATE));

   // Connect ZMQ (publish only)
   g_bridge.Connect("", ZMQ_PUB_ENDPOINT);

   // Set timer
   EventSetMillisecondTimer(MONITOR_INTERVAL_MS);

   Print(AS_PREFIX, " RiskGuard active. Monitoring ", PositionsTotal(), " positions");
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//| OnDeinit                                                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   Print(AS_PREFIX, " RiskGuard stopping. Emergencies: ", g_emergency_count);

   EventKillTimer();

   if(g_bridge != NULL)
     {
      SendFinalReport();
      g_bridge.Disconnect();
      delete g_bridge;
     }
   if(g_trade != NULL)   delete g_trade;
   if(g_account != NULL) delete g_account;
  }

//+------------------------------------------------------------------+
//| OnTimer - main monitoring loop                                     |
//+------------------------------------------------------------------+
void OnTimer()
  {
   // Update account info
   g_account.Refresh();

   // Check for new day (reset daily tracking)
   CheckDayReset();

   // Update risk metrics
   UpdateRiskMetrics();

   // Enforce risk limits
   EnforceRiskLimits();

   // Send periodic risk report
   datetime now = TimeCurrent();
   if(now - g_last_report >= RISK_REPORT_SEC)
     {
      SendRiskReport();
      g_last_report = now;
     }
  }

//+------------------------------------------------------------------+
//| Check if day has reset                                             |
//+------------------------------------------------------------------+
void CheckDayReset()
  {
   datetime today = StringToTime(TimeToString(TimeCurrent(), TIME_DATE));
   if(today > g_day_start_time)
     {
      g_day_start_time    = today;
      g_day_start_balance = g_account.Balance();
      g_alert_daily_loss  = false;
      Print(AS_PREFIX, " New day. Balance: ", DoubleToString(g_day_start_balance, 2));
     }
  }

//+------------------------------------------------------------------+
//| Update risk metrics                                                |
//+------------------------------------------------------------------+
void UpdateRiskMetrics()
  {
   double equity  = g_account.Equity();
   double balance = g_account.Balance();

   // Track peak equity
   if(equity > g_peak_equity)
      g_peak_equity = equity;

   // Calculate drawdown
   double drawdown_pct = 0;
   if(g_peak_equity > 0)
      drawdown_pct = (g_peak_equity - equity) / g_peak_equity * 100.0;

   // Calculate daily P&L
   double daily_pnl = equity - g_day_start_balance;
   double daily_pnl_pct = 0;
   if(g_day_start_balance > 0)
      daily_pnl_pct = daily_pnl / g_day_start_balance * 100.0;

   // Count positions and exposure
   int    open_positions = 0;
   double total_exposure = 0;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;

      if(!MONITOR_ALL_MAGIC)
        {
         if(PositionGetInteger(POSITION_MAGIC) != AS_MAGIC)
            continue;
        }

      open_positions++;
      total_exposure += PositionGetDouble(POSITION_VOLUME);
     }

   // Determine risk level
   ENUM_RISK_LEVEL level = RISK_OK;

   if(drawdown_pct >= MAX_DRAWDOWN_PCT || daily_pnl_pct <= -MAX_DAILY_LOSS_PCT)
      level = RISK_EMERGENCY;
   else if(drawdown_pct >= MAX_DRAWDOWN_PCT * 0.8 || daily_pnl_pct <= -MAX_DAILY_LOSS_PCT * 0.8)
      level = RISK_CRITICAL;
   else if(drawdown_pct >= MAX_DRAWDOWN_PCT * 0.6 || daily_pnl_pct <= -MAX_DAILY_LOSS_PCT * 0.6)
      level = RISK_WARNING;

   // Update metrics
   g_risk_metrics.equity          = equity;
   g_risk_metrics.balance         = balance;
   g_risk_metrics.drawdown_pct    = drawdown_pct;
   g_risk_metrics.daily_pnl       = daily_pnl;
   g_risk_metrics.daily_pnl_pct   = daily_pnl_pct;
   g_risk_metrics.open_positions  = open_positions;
   g_risk_metrics.total_exposure  = total_exposure;
   g_risk_metrics.risk_level      = level;
   g_risk_metrics.timestamp       = TimeCurrent();
  }

//+------------------------------------------------------------------+
//| Enforce risk limits                                                |
//+------------------------------------------------------------------+
void EnforceRiskLimits()
  {
   // Check drawdown
   if(CLOSE_ON_DRAWDOWN && g_risk_metrics.drawdown_pct >= MAX_DRAWDOWN_PCT)
     {
      if(!g_alert_drawdown)
        {
         Print(AS_PREFIX, " *** EMERGENCY: Max drawdown breached! ***");
         Print(AS_PREFIX, " Drawdown: ", DoubleToString(g_risk_metrics.drawdown_pct, 2), "%");
         Alert(AS_PREFIX, " MAX DRAWDOWN BREACH: ", DoubleToString(g_risk_metrics.drawdown_pct, 2), "%");
         g_alert_drawdown = true;
        }

      if(ENABLE_EMERGENCY && !g_emergency_active)
         EmergencyCloseAll("MAX_DRAWDOWN");
     }

   // Check daily loss
   if(CLOSE_ON_DAILY_LOSS && g_risk_metrics.daily_pnl_pct <= -MAX_DAILY_LOSS_PCT)
     {
      if(!g_alert_daily_loss)
        {
         Print(AS_PREFIX, " *** EMERGENCY: Max daily loss breached! ***");
         Print(AS_PREFIX, " Daily Loss: ", DoubleToString(g_risk_metrics.daily_pnl_pct, 2), "%");
         Alert(AS_PREFIX, " MAX DAILY LOSS BREACH: ", DoubleToString(g_risk_metrics.daily_pnl_pct, 2), "%");
         g_alert_daily_loss = true;
        }

      if(ENABLE_EMERGENCY && !g_emergency_active)
         EmergencyCloseAll("MAX_DAILY_LOSS");
     }

   // Check max positions
   if(g_risk_metrics.open_positions > MAX_OPEN_POSITIONS)
     {
      if(!g_alert_max_pos)
        {
         Print(AS_PREFIX, " WARNING: Max positions exceeded! ",
               g_risk_metrics.open_positions, "/", MAX_OPEN_POSITIONS);
         g_alert_max_pos = true;
        }

      if(CLOSE_ON_MAX_POSITIONS)
         CloseOldestPositions();
     }
   else
     {
      g_alert_max_pos = false;
     }

   // Check individual position lot sizes
   EnforceLotLimits();
  }

//+------------------------------------------------------------------+
//| Emergency close all positions                                      |
//+------------------------------------------------------------------+
void EmergencyCloseAll(const string reason)
  {
   g_emergency_active = true;
   g_emergency_count++;

   Print(AS_PREFIX, " *** EMERGENCY CLOSE ALL *** Reason: ", reason);
   Alert(AS_PREFIX, " EMERGENCY CLOSE: ", reason);

   int closed = 0;
   int failed = 0;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;

      if(!MONITOR_ALL_MAGIC && PositionGetInteger(POSITION_MAGIC) != AS_MAGIC)
         continue;

      if(g_trade.PositionClose(ticket))
        {
         closed++;
         Print(AS_PREFIX, " Closed position: ", ticket);
        }
      else
        {
         failed++;
         Print(AS_PREFIX, " Failed to close: ", ticket, " - ", g_trade.ResultComment());
        }
     }

   Print(AS_PREFIX, " Emergency close complete. Closed: ", closed, " Failed: ", failed);

   // Send emergency notification
   CJsonBuilder jb;
   jb.BeginObject();
   jb.AddString("event", "EMERGENCY_CLOSE");
   jb.AddString("reason", reason);
   jb.AddInteger("closed", closed);
   jb.AddInteger("failed", failed);
   jb.AddDouble("equity_after", g_account.Equity(), 2);
   jb.AddInteger("timestamp", (long)TimeCurrent());
   jb.EndObject();

   g_bridge.SendStatus(jb.Build());

   // Reset emergency flag after a delay
   g_risk_params.emergency_close = true;
  }

//+------------------------------------------------------------------+
//| Close oldest positions to reduce count                             |
//+------------------------------------------------------------------+
void CloseOldestPositions()
  {
   // Find and close the oldest position
   datetime oldest_time = TimeCurrent();
   ulong    oldest_ticket = 0;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;

      if(!MONITOR_ALL_MAGIC && PositionGetInteger(POSITION_MAGIC) != AS_MAGIC)
         continue;

      datetime open_time = (datetime)PositionGetInteger(POSITION_TIME);
      if(open_time < oldest_time)
        {
         oldest_time  = open_time;
         oldest_ticket = ticket;
        }
     }

   if(oldest_ticket > 0)
     {
      if(g_trade.PositionClose(oldest_ticket))
        {
         Print(AS_PREFIX, " Closed oldest position: ", oldest_ticket);
        }
     }
  }

//+------------------------------------------------------------------+
//| Enforce lot size limits                                            |
//+------------------------------------------------------------------+
void EnforceLotLimits()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;

      if(!MONITOR_ALL_MAGIC && PositionGetInteger(POSITION_MAGIC) != AS_MAGIC)
         continue;

      double volume = PositionGetDouble(POSITION_VOLUME);
      if(volume > MAX_POSITION_LOTS)
        {
         // Reduce to max allowed
         double reduce_by = volume - MAX_POSITION_LOTS;
         ulong pos_ticket = PositionGetInteger(POSITION_TICKET);

         // Partial close
         string symbol = PositionGetString(POSITION_SYMBOL);
         long   type   = PositionGetInteger(POSITION_TYPE);

         CTrade trade;
         trade.SetExpertMagicNumber(AS_MAGIC);

         if(type == POSITION_TYPE_BUY)
            trade.Sell(reduce_by, symbol, 0, 0, 0, "RiskGuard:lot_limit");
         else
            trade.Buy(reduce_by, symbol, 0, 0, 0, "RiskGuard:lot_limit");

         Print(AS_PREFIX, " Reduced position ", ticket, " by ",
               DoubleToString(reduce_by, 2), " lots");
        }
     }
  }

//+------------------------------------------------------------------+
//| Send risk report                                                   |
//+------------------------------------------------------------------+
void SendRiskReport()
  {
   if(g_bridge == NULL) return;

   g_bridge.SendRiskMetrics(g_risk_metrics);

   if(g_risk_metrics.risk_level >= RISK_WARNING)
     {
      Print(AS_PREFIX, " Risk: ", RiskLevelToString(g_risk_metrics.risk_level),
            " | DD: ", DoubleToString(g_risk_metrics.drawdown_pct, 2), "%",
            " | Daily: ", DoubleToString(g_risk_metrics.daily_pnl_pct, 2), "%",
            " | Pos: ", g_risk_metrics.open_positions);
     }
  }

//+------------------------------------------------------------------+
//| Send final report on shutdown                                      |
//+------------------------------------------------------------------+
void SendFinalReport()
  {
   CJsonBuilder jb;
   jb.BeginObject();
   jb.AddString("event", "RISKGUARD_SHUTDOWN");
   jb.AddDouble("final_equity", g_account.Equity(), 2);
   jb.AddDouble("peak_equity", g_peak_equity, 2);
   jb.AddDouble("drawdown_pct", g_risk_metrics.drawdown_pct, 2);
   jb.AddDouble("daily_pnl", g_risk_metrics.daily_pnl, 2);
   jb.AddInteger("emergency_count", g_emergency_count);
   jb.AddInteger("timestamp", (long)TimeCurrent());
   jb.EndObject();

   g_bridge.SendStatus(jb.Build());
  }
//+------------------------------------------------------------------+
