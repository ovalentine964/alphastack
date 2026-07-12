//+------------------------------------------------------------------+
//|                                                   AlphaStack.mqh |
//|                          AlphaStack Shared Include File           |
//|                              Magic Number: 20260713               |
//+------------------------------------------------------------------+
#ifndef ALPHASTACK_MQH
#define ALPHASTACK_MQH

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\OrderInfo.mqh>
#include <Trade\AccountInfo.mqh>
#include <Trade\SymbolInfo.mqh>

//--- Magic number
#define AS_MAGIC        20260713
#define AS_VERSION      "1.0.0"
#define AS_PREFIX       "[AlphaStack]"

//--- Signal types
enum ENUM_SIGNAL_TYPE
  {
   SIGNAL_BUY        = 1,    // Buy market
   SIGNAL_SELL       = 2,    // Sell market
   SIGNAL_BUY_LIMIT  = 3,    // Buy limit
   SIGNAL_SELL_LIMIT = 4,    // Sell limit
   SIGNAL_BUY_STOP   = 5,    // Buy stop
   SIGNAL_SELL_STOP  = 6,    // Sell stop
   SIGNAL_CLOSE      = 7,    // Close position
   SIGNAL_MODIFY     = 8,    // Modify position
   SIGNAL_CLOSE_ALL  = 9,    // Close all positions
   SIGNAL_NONE       = 0     // No signal
  };

//--- Signal status
enum ENUM_SIGNAL_STATUS
  {
   STATUS_PENDING    = 0,    // Awaiting execution
   STATUS_EXECUTED   = 1,    // Successfully executed
   STATUS_FAILED     = 2,    // Execution failed
   STATUS_CANCELLED  = 3,    // Cancelled
   STATUS_EXPIRED    = 4     // Expired
  };

//--- Connection state
enum ENUM_CONNECTION_STATE
  {
   CONN_DISCONNECTED = 0,
   CONN_CONNECTING   = 1,
   CONN_CONNECTED    = 2,
   CONN_RECONNECTING = 3,
   CONN_ERROR        = 4
  };

//--- Risk alert levels
enum ENUM_RISK_LEVEL
  {
   RISK_OK           = 0,
   RISK_WARNING      = 1,
   RISK_CRITICAL     = 2,
   RISK_EMERGENCY    = 3
  };

//--- Timeframe mapping
struct STFMap
  {
   string            name;
   ENUM_TIMEFRAMES   tf;
  };

//+------------------------------------------------------------------+
//| Signal structure                                                   |
//+------------------------------------------------------------------+
struct SAlphaSignal
  {
   string            signal_id;        // Unique signal ID
   ENUM_SIGNAL_TYPE  type;             // Signal type
   string            symbol;           // Trading symbol
   double            volume;           // Lot size
   double            price;            // Entry price (limit/stop)
   double            stop_loss;        // Stop loss price
   double            take_profit;      // Take profit price
   double            trailing_stop;    // Trailing stop in points
   string            comment;          // Signal comment
   long              magic;            // Magic number
   datetime          expiry;           // Signal expiry time
   datetime          timestamp;        // Creation timestamp
   ENUM_SIGNAL_STATUS status;          // Current status
   ulong             ticket;           // Resulting order/position ticket
   string            error;            // Error message if failed

   void              Reset()
     {
      signal_id       = "";
      type            = SIGNAL_NONE;
      symbol          = "";
      volume          = 0.0;
      price           = 0.0;
      stop_loss       = 0.0;
      take_profit     = 0.0;
      trailing_stop   = 0.0;
      comment         = "";
      magic           = AS_MAGIC;
      expiry          = 0;
      timestamp       = 0;
      status          = STATUS_PENDING;
      ticket          = 0;
      error           = "";
     }
  };

//+------------------------------------------------------------------+
//| Trade result structure                                             |
//+------------------------------------------------------------------+
struct STradeResult
  {
   string            signal_id;        // Original signal ID
   ulong             ticket;           // Order/position ticket
   ENUM_SIGNAL_STATUS status;          // Execution status
   double            fill_price;       // Actual fill price
   double            fill_volume;      // Actual filled volume
   double            commission;       // Commission paid
   double            slippage;         // Price slippage
   string            error;            // Error message
   datetime          timestamp;        // Execution timestamp

   void              Reset()
     {
      signal_id       = "";
      ticket          = 0;
      status          = STATUS_PENDING;
      fill_price      = 0.0;
      fill_volume     = 0.0;
      commission      = 0.0;
      slippage        = 0.0;
      error           = "";
      timestamp       = 0;
     }
  };

//+------------------------------------------------------------------+
//| Risk parameters structure                                          |
//+------------------------------------------------------------------+
struct SRiskParams
  {
   double            max_drawdown_pct;     // Max drawdown % (e.g. 10.0)
   double            max_daily_loss_pct;   // Max daily loss % (e.g. 5.0)
   double            max_position_lots;    // Max lot size per position
   int               max_open_positions;   // Max simultaneous positions
   double            max_risk_per_trade;   // Max risk per trade %
   bool              emergency_close;      // Emergency close flag

   void              Reset()
     {
      max_drawdown_pct    = 10.0;
      max_daily_loss_pct  = 5.0;
      max_position_lots   = 10.0;
      max_open_positions  = 10;
      max_risk_per_trade  = 2.0;
      emergency_close     = false;
     }
  };

//+------------------------------------------------------------------+
//| Risk metrics structure                                             |
//+------------------------------------------------------------------+
struct SRiskMetrics
  {
   double            equity;               // Current equity
   double            balance;              // Account balance
   double            drawdown_pct;         // Current drawdown %
   double            daily_pnl;            // Today's P&L
   double            daily_pnl_pct;        // Today's P&L %
   int               open_positions;       // Number of open positions
   double            total_exposure;       // Total lot exposure
   ENUM_RISK_LEVEL   risk_level;           // Current risk level
   datetime          timestamp;            // Last update time

   void              Reset()
     {
      equity            = 0.0;
      balance           = 0.0;
      drawdown_pct      = 0.0;
      daily_pnl         = 0.0;
      daily_pnl_pct     = 0.0;
      open_positions    = 0;
      total_exposure    = 0.0;
      risk_level        = RISK_OK;
      timestamp         = 0;
     }
  };

//+------------------------------------------------------------------+
//| Heartbeat structure                                                |
//+------------------------------------------------------------------+
struct SHeartbeat
  {
   datetime          last_sent;            // Last heartbeat sent
   datetime          last_received;        // Last heartbeat received
   int               missed_beats;         // Consecutive missed beats
   int               timeout_seconds;      // Heartbeat timeout

   void              Reset()
     {
      last_sent         = 0;
      last_received     = 0;
      missed_beats      = 0;
      timeout_seconds   = 30;
     }

   bool              IsAlive()
     {
      return (missed_beats < 3);
     }
  };

//+------------------------------------------------------------------+
//| Order type string helper                                           |
//+------------------------------------------------------------------+
string SignalTypeToString(ENUM_SIGNAL_TYPE type)
  {
   switch(type)
     {
      case SIGNAL_BUY:        return "BUY";
      case SIGNAL_SELL:       return "SELL";
      case SIGNAL_BUY_LIMIT:  return "BUY_LIMIT";
      case SIGNAL_SELL_LIMIT: return "SELL_LIMIT";
      case SIGNAL_BUY_STOP:   return "BUY_STOP";
      case SIGNAL_SELL_STOP:  return "SELL_STOP";
      case SIGNAL_CLOSE:      return "CLOSE";
      case SIGNAL_MODIFY:     return "MODIFY";
      case SIGNAL_CLOSE_ALL:  return "CLOSE_ALL";
      default:                return "NONE";
     }
  }

//+------------------------------------------------------------------+
//| Status string helper                                               |
//+------------------------------------------------------------------+
string SignalStatusToString(ENUM_SIGNAL_STATUS status)
  {
   switch(status)
     {
      case STATUS_PENDING:   return "PENDING";
      case STATUS_EXECUTED:  return "EXECUTED";
      case STATUS_FAILED:    return "FAILED";
      case STATUS_CANCELLED: return "CANCELLED";
      case STATUS_EXPIRED:   return "EXPIRED";
      default:               return "UNKNOWN";
     }
  }

//+------------------------------------------------------------------+
//| Risk level string helper                                           |
//+------------------------------------------------------------------+
string RiskLevelToString(ENUM_RISK_LEVEL level)
  {
   switch(level)
     {
      case RISK_OK:        return "OK";
      case RISK_WARNING:   return "WARNING";
      case RISK_CRITICAL:  return "CRITICAL";
      case RISK_EMERGENCY: return "EMERGENCY";
      default:             return "UNKNOWN";
     }
  }

#endif // ALPHASTACK_MQH
//+------------------------------------------------------------------+
