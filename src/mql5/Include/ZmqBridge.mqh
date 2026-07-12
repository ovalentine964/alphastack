//+------------------------------------------------------------------+
//|                                                   ZmqBridge.mqh  |
//|                      ZeroMQ Bridge for AlphaStack                 |
//|                    Socket management / JSON / Heartbeat           |
//+------------------------------------------------------------------+
#ifndef ZMQ_BRIDGE_MQH
#define ZMQ_BRIDGE_MQH

#include "AlphaStack.mqh"

//--- Import ZeroMQ DLL (libzmq / libsodium required in MT5 MQL5/Libraries)
#import "libsodium.dll"
   int  sodium_init(void);
#import

#import "libzmq.dll"
   // Context
   int  zmq_ctx_new(void);
   int  zmq_ctx_term(int context);
   int  zmq_ctx_set(int context, int option, int optval);

   // Socket
   int  zmq_socket(int context, int type);
   int  zmq_close(int socket);
   int  zmq_bind(int socket, const char &endpoint[]);
   int  zmq_connect(int socket, const char &endpoint[]);
   int  zmq_setsockopt(int socket, int option, const void &optval, int optvallen);
   int  zmq_getsockopt(int socket, int option, void &optval, int &optvallen);

   // Messaging
   int  zmq_send(int socket, const void &buf, int len, int flags);
   int  zmq_recv(int socket, void &buf, int len, int flags);
   int  zmq_msg_init(int &msg[]);
   int  zmq_msg_init_size(int &msg[], int size);
   int  zmq_msg_close(int &msg[]);
   int  zmq_msg_size(int &msg[]);
   int  zmq_msg_data(int &msg[], void &data[]);
   int  zmq_msg_send(int &msg[], int socket, int flags);
   int  zmq_msg_recv(int &msg[], int socket, int flags);

   // Polling
   int  zmq_poll(int items[], int nitems, long timeout);
#import

//--- ZeroMQ socket types
#define ZMQ_PAIR    0
#define ZMQ_PUB     1
#define ZMQ_SUB     2
#define ZMQ_REQ     3
#define ZMQ_REP     4
#define ZMQ_DEALER  5
#define ZMQ_ROUTER  6
#define ZMQ_PULL    7
#define ZMQ_PUSH    8

//--- ZeroMQ socket options
#define ZMQ_SUBSCRIBE     6
#define ZMQ_UNSUBSCRIBE   7
#define ZMQ_RCVTIMEO      27
#define ZMQ_SNDTIMEO      28
#define ZMQ_LINGER        17
#define ZMQ_RECONNECT_IVL 18
#define ZMQ_RECONNECT_IVL_MAX 21
#define ZMQ_SNDHWM        23
#define ZMQ_RCVHWM        24

//--- ZeroMQ poll events
#define ZMQ_POLLIN   1
#define ZMQ_POLLOUT  2
#define ZMQ_POLLERR  4

//--- ZeroMQ flags
#define ZMQ_DONTWAIT 1

//--- Message framing
#define AS_FRAME_DELIMITER  "|"
#define AS_MSG_HEARTBEAT    "HB"
#define AS_MSG_SIGNAL       "SIG"
#define AS_MSG_RESULT       "RES"
#define AS_MSG_RISK         "RISK"
#define AS_MSG_STATUS       "STATUS"
#define AS_MSG_ACK          "ACK"
#define AS_MSG_NACK         "NACK"

//--- Buffer size
#define ZMQ_BUFFER_SIZE  65536

//+------------------------------------------------------------------+
//| Simple JSON builder (no external lib needed)                       |
//+------------------------------------------------------------------+
class CJsonBuilder
  {
private:
   string            m_json;
   bool              m_first;

public:
                     CJsonBuilder() : m_json(""), m_first(true) {}

   void              BeginObject()       { m_json = "{"; m_first = true; }
   void              EndObject()         { m_json += "}"; }

   void              AddString(const string key, const string value)
     {
      if(!m_first) m_json += ",";
      m_json += "\"" + key + "\":\"" + value + "\"";
      m_first = false;
     }

   void              AddInteger(const string key, const long value)
     {
      if(!m_first) m_json += ",";
      m_json += "\"" + key + "\":" + IntegerToString(value);
      m_first = false;
     }

   void              AddDouble(const string key, const double value, int digits = 8)
     {
      if(!m_first) m_json += ",";
      m_json += "\"" + key + "\":" + DoubleToString(value, digits);
      m_first = false;
     }

   void              AddBool(const string key, const bool value)
     {
      if(!m_first) m_json += ",";
      m_json += "\"" + key + "\":" + (value ? "true" : "false");
      m_first = false;
     }

   string            Build()             { return m_json; }
  };

//+------------------------------------------------------------------+
//| Simple JSON parser (extracts values by key)                        |
//+------------------------------------------------------------------+
class CJsonParser
  {
public:
                     CJsonParser() {}

   //--- Extract string value for key: "key":"value"
   static string     GetString(const string json, const string key)
     {
      string search = "\"" + key + "\":\"";
      int pos = StringFind(json, search);
      if(pos < 0) return "";
      int start = pos + StringLen(search);
      int end = StringFind(json, "\"", start);
      if(end < 0) return "";
      return StringSubstr(json, start, end - start);
     }

   //--- Extract numeric value for key: "key":123 or "key":1.5
   static double     GetDouble(const string json, const string key)
     {
      string search = "\"" + key + "\":";
      int pos = StringFind(json, search);
      if(pos < 0) return 0.0;
      int start = pos + StringLen(search);
      // Find end of value (comma, closing brace, or space)
      int end = start;
      int len = StringLen(json);
      while(end < len)
        {
         ushort ch = StringGetCharacter(json, end);
         if(ch == ',' || ch == '}' || ch == ' ' || ch == '\n') break;
         end++;
        }
      string val = StringSubstr(json, start, end - start);
      return StringToDouble(val);
     }

   //--- Extract integer value
   static long       GetInteger(const string json, const string key)
     {
      return (long)GetDouble(json, key);
     }

   //--- Extract boolean value
   static bool       GetBool(const string json, const string key)
     {
      string search = "\"" + key + "\":";
      int pos = StringFind(json, search);
      if(pos < 0) return false;
      int start = pos + StringLen(search);
      string sub = StringSubstr(json, start, 4);
      return (sub == "true");
     }
  };

//+------------------------------------------------------------------+
//| ZeroMQ Bridge Class                                                |
//+------------------------------------------------------------------+
class CZmqBridge
  {
private:
   int               m_context;           // ZMQ context
   int               m_socket_sub;        // Subscriber (receive signals)
   int               m_socket_pub;        // Publisher (send results)
   int               m_socket_push;       // Push (send heartbeats)
   string            m_endpoint_sub;      // Subscribe endpoint
   string            m_endpoint_pub;      // Publish endpoint
   string            m_endpoint_push;     // Push endpoint
   bool              m_connected;         // Connection state
   ENUM_connection_state m_state;         // Detailed state
   SHeartbeat        m_heartbeat;         // Heartbeat tracker
   datetime          m_last_reconnect;    // Last reconnect attempt
   int               m_reconnect_delay;   // Reconnect delay (seconds)
   int               m_max_reconnects;    // Max reconnect attempts
   int               m_reconnect_count;   // Current reconnect count

   //--- Receive buffer
   uchar             m_buffer[ZMQ_BUFFER_SIZE];

   //--- Internal methods
   bool              CreateSockets();
   void              CloseSockets();
   bool              SetupSocket(int socket, int type, const string &endpoint);

public:
                     CZmqBridge();
                    ~CZmqBridge();

   //--- Lifecycle
   bool              Connect(const string &sub_endpoint,
                             const string &pub_endpoint,
                             const string &push_endpoint = "");
   void              Disconnect();
   bool              Reconnect();

   //--- Messaging
   bool              SendResult(const string &signal_id, const STradeResult &result);
   bool              SendRiskMetrics(const SRiskMetrics &metrics);
   bool              SendStatus(const string &status_json);
   bool              SendHeartbeat();
   bool              SendAck(const string &signal_id);
   bool              SendNack(const string &signal_id, const string &error);

   //--- Receiving
   string            ReceiveSignal();
   string            ReceiveRaw(int timeout_ms = 100);
   bool              HasData(int timeout_ms = 0);

   //--- State
   bool              IsConnected()        { return m_connected; }
   ENUM_connection_state GetState()       { return m_state; }
   bool              IsAlive()            { return m_heartbeat.IsAlive(); }
   int               MissedBeats()        { return m_heartbeat.missed_beats; }
   void              UpdateHeartbeat();

   //--- Utility
   string            SignalToJson(const SAlphaSignal &signal);
   STradeResult      JsonToResult(const string &json);
   SRiskMetrics      JsonToRiskMetrics(const string &json);
   string            ResultToJson(const STradeResult &result);
   string            RiskMetricsToJson(const SRiskMetrics &metrics);
  };

//+------------------------------------------------------------------+
//| Constructor                                                        |
//+------------------------------------------------------------------+
CZmqBridge::CZmqBridge()
  {
   m_context         = 0;
   m_socket_sub      = -1;
   m_socket_pub      = -1;
   m_socket_push     = -1;
   m_connected       = false;
   m_state           = CONN_DISCONNECTED;
   m_last_reconnect  = 0;
   m_reconnect_delay = 5;
   m_max_reconnects  = 50;
   m_reconnect_count = 0;
   m_heartbeat.Reset();
   m_heartbeat.timeout_seconds = 30;
  }

//+------------------------------------------------------------------+
//| Destructor                                                         |
//+------------------------------------------------------------------+
CZmqBridge::~CZmqBridge()
  {
   Disconnect();
  }

//+------------------------------------------------------------------+
//| Create ZMQ context and sockets                                     |
//+------------------------------------------------------------------+
bool CZmqBridge::CreateSockets()
  {
   // Create context
   m_context = zmq_ctx_new();
   if(m_context == 0)
     {
      Print(AS_PREFIX, " ERROR: Failed to create ZMQ context");
      return false;
     }

   // Set context options
   zmq_ctx_set(m_context, 1, 1);  // ZMQ_IO_THREADS = 1

   // Create subscriber socket
   m_socket_sub = zmq_socket(m_context, ZMQ_SUB);
   if(m_socket_sub == 0)
     {
      Print(AS_PREFIX, " ERROR: Failed to create SUB socket");
      return false;
     }

   // Create publisher socket
   m_socket_pub = zmq_socket(m_context, ZMQ_PUB);
   if(m_socket_pub == 0)
     {
      Print(AS_PREFIX, " ERROR: Failed to create PUB socket");
      zmq_close(m_socket_sub);
      return false;
     }

   // Create push socket (for heartbeats)
   m_socket_push = zmq_socket(m_context, ZMQ_PUSH);
   if(m_socket_push == 0)
     {
      Print(AS_PREFIX, " ERROR: Failed to create PUSH socket");
      zmq_close(m_socket_sub);
      zmq_close(m_socket_pub);
      return false;
     }

   // Set socket options
   int linger = 0;
   zmq_setsockopt(m_socket_sub, ZMQ_LINGER, linger, sizeof(int));
   zmq_setsockopt(m_socket_pub, ZMQ_LINGER, linger, sizeof(int));
   zmq_setsockopt(m_socket_push, ZMQ_LINGER, linger, sizeof(int));

   // Set receive timeout
   int rcvtimeo = 100;  // 100ms
   zmq_setsockopt(m_socket_sub, ZMQ_RCVTIMEO, rcvtimeo, sizeof(int));

   // Set send timeout
   int sndtimeo = 1000;  // 1 second
   zmq_setsockopt(m_socket_pub, ZMQ_SNDTIMEO, sndtimeo, sizeof(int));

   return true;
  }

//+------------------------------------------------------------------+
//| Close all sockets                                                  |
//+------------------------------------------------------------------+
void CZmqBridge::CloseSockets()
  {
   if(m_socket_sub > 0)
     {
      zmq_close(m_socket_sub);
      m_socket_sub = -1;
     }
   if(m_socket_pub > 0)
     {
      zmq_close(m_socket_pub);
      m_socket_pub = -1;
     }
   if(m_socket_push > 0)
     {
      zmq_close(m_socket_push);
      m_socket_push = -1;
     }
   if(m_context > 0)
     {
      zmq_ctx_term(m_context);
      m_context = 0;
     }
  }

//+------------------------------------------------------------------+
//| Connect to ZMQ endpoints                                           |
//+------------------------------------------------------------------+
bool CZmqBridge::Connect(const string &sub_endpoint,
                          const string &pub_endpoint,
                          const string &push_endpoint)
  {
   m_endpoint_sub  = sub_endpoint;
   m_endpoint_pub  = pub_endpoint;
   m_endpoint_push = push_endpoint;

   if(m_connected)
     {
      Print(AS_PREFIX, " Already connected, disconnecting first");
      Disconnect();
     }

   m_state = CONN_CONNECTING;
   Print(AS_PREFIX, " Connecting to ZMQ endpoints...");
   Print(AS_PREFIX, "   SUB:  ", sub_endpoint);
   Print(AS_PREFIX, "   PUB:  ", pub_endpoint);
   if(push_endpoint != "")
      Print(AS_PREFIX, "   PUSH: ", push_endpoint);

   // Create sockets
   if(!CreateSockets())
     {
      m_state = CONN_ERROR;
      return false;
     }

   // Subscribe to all signals (empty filter = all messages)
   uchar empty = 0;
   zmq_setsockopt(m_socket_sub, ZMQ_SUBSCRIBE, empty, 0);

   // Connect subscriber
   if(zmq_connect(m_socket_sub, sub_endpoint) != 0)
     {
      Print(AS_PREFIX, " ERROR: Failed to connect SUB to ", sub_endpoint);
      CloseSockets();
      m_state = CONN_ERROR;
      return false;
     }

   // Bind publisher
   if(zmq_bind(m_socket_pub, pub_endpoint) != 0)
     {
      Print(AS_PREFIX, " ERROR: Failed to bind PUB to ", pub_endpoint);
      CloseSockets();
      m_state = CONN_ERROR;
      return false;
     }

   // Connect push (optional)
   if(push_endpoint != "")
     {
      if(zmq_connect(m_socket_push, push_endpoint) != 0)
        {
         Print(AS_PREFIX, " WARNING: Failed to connect PUSH to ", push_endpoint);
         // Non-fatal: continue without push socket
        }
     }

   m_connected       = true;
   m_state           = CONN_CONNECTED;
   m_reconnect_count = 0;
   m_heartbeat.Reset();

   Print(AS_PREFIX, " Connected to ZMQ successfully");
   return true;
  }

//+------------------------------------------------------------------+
//| Disconnect from ZMQ                                                |
//+------------------------------------------------------------------+
void CZmqBridge::Disconnect()
  {
   if(m_connected)
     {
      Print(AS_PREFIX, " Disconnecting from ZMQ...");
      // Send final heartbeat
      SendHeartbeat();
     }
   CloseSockets();
   m_connected = false;
   m_state     = CONN_DISCONNECTED;
  }

//+------------------------------------------------------------------+
//| Reconnect to ZMQ                                                   |
//+------------------------------------------------------------------+
bool CZmqBridge::Reconnect()
  {
   if(m_reconnect_count >= m_max_reconnects)
     {
      Print(AS_PREFIX, " ERROR: Max reconnect attempts (", m_max_reconnects, ") reached");
      m_state = CONN_ERROR;
      return false;
     }

   datetime now = TimeCurrent();
   if(now - m_last_reconnect < m_reconnect_delay)
      return false;  // Too soon

   m_last_reconnect = now;
   m_reconnect_count++;
   m_state = CONN_RECONNECTING;

   Print(AS_PREFIX, " Reconnecting... attempt ", m_reconnect_count, "/", m_max_reconnects);

   Disconnect();

   // Exponential backoff (capped at 60s)
   m_reconnect_delay = MathMin(m_reconnect_delay * 2, 60);

   if(Connect(m_endpoint_sub, m_endpoint_pub, m_endpoint_push))
     {
      m_reconnect_delay = 5;  // Reset on success
      return true;
     }

   return false;
  }

//+------------------------------------------------------------------+
//| Send trade result                                                  |
//+------------------------------------------------------------------+
bool CZmqBridge::SendResult(const string &signal_id, const STradeResult &result)
  {
   if(!m_connected) return false;

   string json = ResultToJson(result);

   // Frame: TYPE|PAYLOAD
   string msg = AS_MSG_RESULT + AS_FRAME_DELIMITER + json;

   uchar data[];
   StringToCharArray(msg, data, 0, WHOLE_ARRAY, CP_UTF8);
   int sent = zmq_send(m_socket_pub, data, ArraySize(data) - 1, 0);

   if(sent > 0)
     {
      Print(AS_PREFIX, " Sent result for signal: ", signal_id);
      return true;
     }

   Print(AS_PREFIX, " WARNING: Failed to send result");
   return false;
  }

//+------------------------------------------------------------------+
//| Send risk metrics                                                  |
//+------------------------------------------------------------------+
bool CZmqBridge::SendRiskMetrics(const SRiskMetrics &metrics)
  {
   if(!m_connected) return false;

   string json = RiskMetricsToJson(metrics);
   string msg  = AS_MSG_RISK + AS_FRAME_DELIMITER + json;

   uchar data[];
   StringToCharArray(msg, data, 0, WHOLE_ARRAY, CP_UTF8);
   int sent = zmq_send(m_socket_pub, data, ArraySize(data) - 1, 0);

   return (sent > 0);
  }

//+------------------------------------------------------------------+
//| Send status                                                        |
//+------------------------------------------------------------------+
bool CZmqBridge::SendStatus(const string &status_json)
  {
   if(!m_connected) return false;

   string msg = AS_MSG_STATUS + AS_FRAME_DELIMITER + status_json;

   uchar data[];
   StringToCharArray(msg, data, 0, WHOLE_ARRAY, CP_UTF8);
   int sent = zmq_send(m_socket_pub, data, ArraySize(data) - 1, 0);

   return (sent > 0);
  }

//+------------------------------------------------------------------+
//| Send heartbeat                                                     |
//+------------------------------------------------------------------+
bool CZmqBridge::SendHeartbeat()
  {
   if(!m_connected) return false;

   CJsonBuilder jb;
   jb.BeginObject();
   jb.AddString("type", AS_MSG_HEARTBEAT);
   jb.AddInteger("timestamp", (long)TimeCurrent());
   jb.AddInteger("missed", m_heartbeat.missed_beats);
   jb.EndObject();

   string msg = AS_MSG_HEARTBEAT + AS_FRAME_DELIMITER + jb.Build();

   uchar data[];
   StringToCharArray(msg, data, 0, WHOLE_ARRAY, CP_UTF8);
   int sent = zmq_send(m_socket_push, data, ArraySize(data) - 1, 0);

   if(sent > 0)
     {
      m_heartbeat.last_sent = TimeCurrent();
      return true;
     }

   return false;
  }

//+------------------------------------------------------------------+
//| Send ACK                                                           |
//+------------------------------------------------------------------+
bool CZmqBridge::SendAck(const string &signal_id)
  {
   if(!m_connected) return false;

   CJsonBuilder jb;
   jb.BeginObject();
   jb.AddString("signal_id", signal_id);
   jb.AddString("status", "ACK");
   jb.AddInteger("timestamp", (long)TimeCurrent());
   jb.EndObject();

   string msg = AS_MSG_ACK + AS_FRAME_DELIMITER + jb.Build();

   uchar data[];
   StringToCharArray(msg, data, 0, WHOLE_ARRAY, CP_UTF8);
   int sent = zmq_send(m_socket_pub, data, ArraySize(data) - 1, 0);

   return (sent > 0);
  }

//+------------------------------------------------------------------+
//| Send NACK                                                          |
//+------------------------------------------------------------------+
bool CZmqBridge::SendNack(const string &signal_id, const string &error)
  {
   if(!m_connected) return false;

   CJsonBuilder jb;
   jb.BeginObject();
   jb.AddString("signal_id", signal_id);
   jb.AddString("status", "NACK");
   jb.AddString("error", error);
   jb.AddInteger("timestamp", (long)TimeCurrent());
   jb.EndObject();

   string msg = AS_MSG_NACK + AS_FRAME_DELIMITER + jb.Build();

   uchar data[];
   StringToCharArray(msg, data, 0, WHOLE_ARRAY, CP_UTF8);
   int sent = zmq_send(m_socket_pub, data, ArraySize(data) - 1, 0);

   return (sent > 0);
  }

//+------------------------------------------------------------------+
//| Receive signal (returns JSON string or "" if none)                 |
//+------------------------------------------------------------------+
string CZmqBridge::ReceiveSignal()
  {
   if(!m_connected) return "";

   string raw = ReceiveRaw(100);
   if(raw == "") return "";

   // Parse frame: TYPE|PAYLOAD
   int delim_pos = StringFind(raw, AS_FRAME_DELIMITER);
   if(delim_pos < 0) return "";

   string msg_type = StringSubstr(raw, 0, delim_pos);
   string payload  = StringSubstr(raw, delim_pos + 1);

   if(msg_type == AS_MSG_SIGNAL)
     {
      return payload;  // Return JSON payload
     }
   else if(msg_type == AS_MSG_HEARTBEAT)
     {
      m_heartbeat.last_received = TimeCurrent();
      m_heartbeat.missed_beats  = 0;
      return "";
     }
   else if(msg_type == AS_MSG_STATUS)
     {
      Print(AS_PREFIX, " Status: ", payload);
      return "";
     }

   return "";
  }

//+------------------------------------------------------------------+
//| Receive raw message                                                |
//+------------------------------------------------------------------+
string CZmqBridge::ReceiveRaw(int timeout_ms)
  {
   if(!m_connected) return "";

   // Set timeout
   zmq_setsockopt(m_socket_sub, ZMQ_RCVTIMEO, timeout_ms, sizeof(int));

   // Receive
   int received = zmq_recv(m_socket_sub, m_buffer, ZMQ_BUFFER_SIZE, 0);

   if(received <= 0)
      return "";

   // Convert to string
   string result = CharArrayToString(m_buffer, 0, received, CP_UTF8);

   return result;
  }

//+------------------------------------------------------------------+
//| Check if data is available                                         |
//+------------------------------------------------------------------+
bool CZmqBridge::HasData(int timeout_ms)
  {
   if(!m_connected) return false;

   zmq_setsockopt(m_socket_sub, ZMQ_RCVTIMEO, timeout_ms, sizeof(int));

   int received = zmq_recv(m_socket_sub, m_buffer, ZMQ_BUFFER_SIZE, ZMQ_DONTWAIT);
   return (received > 0);
  }

//+------------------------------------------------------------------+
//| Update heartbeat                                                   |
//+------------------------------------------------------------------+
void CZmqBridge::UpdateHeartbeat()
  {
   datetime now = TimeCurrent();

   // Check if we missed a heartbeat
   if(now - m_heartbeat.last_received > m_heartbeat.timeout_seconds)
     {
      m_heartbeat.missed_beats++;
      Print(AS_PREFIX, " WARNING: Missed heartbeat #", m_heartbeat.missed_beats);
     }

   // Send our heartbeat periodically
   if(now - m_heartbeat.last_sent >= 10)  // Every 10 seconds
     {
      SendHeartbeat();
     }
  }

//+------------------------------------------------------------------+
//| Convert signal to JSON                                             |
//+------------------------------------------------------------------+
string CZmqBridge::SignalToJson(const SAlphaSignal &signal)
  {
   CJsonBuilder jb;
   jb.BeginObject();
   jb.AddString("signal_id", signal.signal_id);
   jb.AddInteger("type", (int)signal.type);
   jb.AddString("symbol", signal.symbol);
   jb.AddDouble("volume", signal.volume);
   jb.AddDouble("price", signal.price, 5);
   jb.AddDouble("stop_loss", signal.stop_loss, 5);
   jb.AddDouble("take_profit", signal.take_profit, 5);
   jb.AddDouble("trailing_stop", signal.trailing_stop, 1);
   jb.AddString("comment", signal.comment);
   jb.AddInteger("magic", signal.magic);
   jb.AddInteger("expiry", (long)signal.expiry);
   jb.AddInteger("timestamp", (long)signal.timestamp);
   jb.AddInteger("status", (int)signal.status);
   jb.AddInteger("ticket", (long)signal.ticket);
   jb.AddString("error", signal.error);
   jb.EndObject();
   return jb.Build();
  }

//+------------------------------------------------------------------+
//| Convert trade result to JSON                                       |
//+------------------------------------------------------------------+
string CZmqBridge::ResultToJson(const STradeResult &result)
  {
   CJsonBuilder jb;
   jb.BeginObject();
   jb.AddString("signal_id", result.signal_id);
   jb.AddInteger("ticket", (long)result.ticket);
   jb.AddInteger("status", (int)result.status);
   jb.AddDouble("fill_price", result.fill_price, 5);
   jb.AddDouble("fill_volume", result.fill_volume);
   jb.AddDouble("commission", result.commission, 2);
   jb.AddDouble("slippage", result.slippage, 5);
   jb.AddString("error", result.error);
   jb.AddInteger("timestamp", (long)result.timestamp);
   jb.EndObject();
   return jb.Build();
  }

//+------------------------------------------------------------------+
//| Convert risk metrics to JSON                                       |
//+------------------------------------------------------------------+
string CZmqBridge::RiskMetricsToJson(const SRiskMetrics &metrics)
  {
   CJsonBuilder jb;
   jb.BeginObject();
   jb.AddDouble("equity", metrics.equity, 2);
   jb.AddDouble("balance", metrics.balance, 2);
   jb.AddDouble("drawdown_pct", metrics.drawdown_pct, 2);
   jb.AddDouble("daily_pnl", metrics.daily_pnl, 2);
   jb.AddDouble("daily_pnl_pct", metrics.daily_pnl_pct, 2);
   jb.AddInteger("open_positions", metrics.open_positions);
   jb.AddDouble("total_exposure", metrics.total_exposure);
   jb.AddInteger("risk_level", (int)metrics.risk_level);
   jb.AddInteger("timestamp", (long)metrics.timestamp);
   jb.EndObject();
   return jb.Build();
  }

#endif // ZMQ_BRIDGE_MQH
//+------------------------------------------------------------------+
