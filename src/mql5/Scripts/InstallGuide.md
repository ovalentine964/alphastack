# AlphaStack MQL5 Installation Guide

## Prerequisites

- MetaTrader 5 (FXPesa or any MT5 broker)
- Windows 10/11 (or Windows VPS for 24/7 operation)
- ZeroMQ DLL files

## Step 1: Install ZeroMQ for MT5

1. Download ZeroMQ DLL for MT5:
   - `libsodium.dll`
   - `libzmq.dll`

2. Copy DLLs to MT5:
   ```
   C:\Users\[YourName]\AppData\Roaming\MetaQuotes\Terminal\[ID]\MQL5\Libraries\
   ```

3. Restart MT5

## Step 2: Install AlphaStack EA

1. Copy the EA files to MT5:
   ```
   MQL5/Experts/AlphaStack/AlphaStackBridge.mq5
   MQL5/Experts/AlphaStack/SignalReceiver.mq5
   MQL5/Experts/AlphaStack/RiskGuard.mq5
   MQL5/Include/AlphaStack.mqh
   MQL5/Include/ZmqBridge.mqh
   ```

2. In MT5, open MetaEditor (F4)

3. Compile each .mq5 file (F7)

4. The EAs will appear in the Navigator panel

## Step 3: Configure EA

1. Drag `AlphaStackBridge` to a chart

2. In the EA settings:
   ```
   ZMQ_Address = tcp://localhost:5555
   Magic_Number = 20260713
   Max_Lots = 0.01
   Risk_Percent = 2.0
   ```

3. Enable "Allow Algo Trading" in MT5

## Step 4: Start Python Backend

```bash
cd alphastack
python -m alphastack.main
```

The Python backend will start a ZeroMQ server on port 5555.

## Step 5: Verify Connection

1. Check MT5 Experts tab for connection messages
2. Check Python logs for "MT5 EA connected"
3. Send a test signal

## Troubleshooting

| Issue | Solution |
|-------|----------|
| EA won't compile | Ensure ZeroMQ DLLs are in Libraries folder |
| No connection | Check firewall allows port 5555 |
| DLL not found | Restart MT5 after copying DLLs |
| Trade context busy | Wait for current trade to finish |
| Requote | Increase slippage in EA settings |

## Architecture

```
┌─────────────────┐     ZeroMQ      ┌─────────────────┐
│   MT5 Terminal   │ ◄────────────► │  Python Backend  │
│  (AlphaStack EA) │   tcp://5555   │  (Trading Engine)│
└─────────────────┘                 └─────────────────┘
```

## Signal Format (JSON)

```json
{
  "action": "buy",
  "symbol": "EURUSD",
  "lots": 0.01,
  "sl": 1.0850,
  "tp": 1.0950,
  "magic": 20260713,
  "comment": "AlphaStack S10"
}
```

## Risk Guard

The RiskGuard EA monitors all positions and enforces:
- Max daily loss: 5%
- Max drawdown: 10%
- Emergency close all if limits exceeded

Install it on any chart — it works independently of the main EA.
