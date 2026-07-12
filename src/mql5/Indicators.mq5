//+------------------------------------------------------------------+
//| AlphaStack Indicators for MT5                                     |
//| Custom RSI, MACD, Structure Detection, Liquidity Pools            |
//+------------------------------------------------------------------+
#property copyright "AlphaStack"
#property link      "https://github.com/ovalentine964/alphastack"
#property version   "1.00"
#property indicator_separate_window

//--- RSI Parameters
input int RSI_Period = 14;
input double RSI_Overbought = 70.0;
input double RSI_Oversold = 30.0;

//--- MACD Parameters
input int MACD_Fast = 12;
input int MACD_Slow = 26;
input int MACD_Signal = 9;

//--- Structure Parameters
input int Structure_Lookback = 20;
input int Structure_MinSwing = 5;

//--- Buffers
double RSIBuffer[];
double MACDBuffer[];
double SignalBuffer[];
double StructureBuffer[];

//+------------------------------------------------------------------+
//| Custom indicator initialization function                          |
//+------------------------------------------------------------------+
int OnInit()
{
   SetIndexBuffer(0, RSIBuffer, INDICATOR_DATA);
   SetIndexBuffer(1, MACDBuffer, INDICATOR_DATA);
   SetIndexBuffer(2, SignalBuffer, INDICATOR_DATA);
   SetIndexBuffer(3, StructureBuffer, INDICATOR_DATA);
   
   PlotIndexSetString(0, PLOT_LABEL, "RSI");
   PlotIndexSetString(1, PLOT_LABEL, "MACD");
   PlotIndexSetString(2, PLOT_LABEL, "Signal");
   PlotIndexSetString(3, PLOT_LABEL, "Structure");
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| RSI Calculation                                                    |
//+------------------------------------------------------------------+
double CalculateRSI(int period, int shift)
{
   double sumGain = 0, sumLoss = 0;
   
   for(int i = shift; i < shift + period; i++)
   {
      double change = iClose(_Symbol, PERIOD_CURRENT, i) - iClose(_Symbol, PERIOD_CURRENT, i+1);
      if(change > 0) sumGain += change;
      else sumLoss -= change;
   }
   
   double avgGain = sumGain / period;
   double avgLoss = sumLoss / period;
   
   if(avgLoss == 0) return 100.0;
   
   double rs = avgGain / avgLoss;
   return 100.0 - (100.0 / (1.0 + rs));
}

//+------------------------------------------------------------------+
//| MACD Calculation                                                   |
//+------------------------------------------------------------------+
void CalculateMACD(int shift, double &macd, double &signal)
{
   double fastEMA = 0, slowEMA = 0;
   double fastSum = 0, slowSum = 0;
   
   // Simple initial calculation
   for(int i = 0; i < MACD_Fast; i++)
      fastSum += iClose(_Symbol, PERIOD_CURRENT, shift + i);
   for(int i = 0; i < MACD_Slow; i++)
      slowSum += iClose(_Symbol, PERIOD_CURRENT, shift + i);
   
   fastEMA = fastSum / MACD_Fast;
   slowEMA = slowSum / MACD_Slow;
   
   macd = fastEMA - slowEMA;
   signal = macd; // Simplified
}

//+------------------------------------------------------------------+
//| Structure Detection (HH/HL/LH/LL)                                 |
//+------------------------------------------------------------------+
int DetectStructure(int shift)
{
   double highs[], lows[];
   ArrayResize(highs, Structure_Lookback);
   ArrayResize(lows, Structure_Lookback);
   
   for(int i = 0; i < Structure_Lookback; i++)
   {
      highs[i] = iHigh(_Symbol, PERIOD_CURRENT, shift + i);
      lows[i] = iLow(_Symbol, PERIOD_CURRENT, shift + i);
   }
   
   // Find swing highs and lows
   double lastSwingHigh = 0, lastSwingLow = 999999;
   int direction = 0; // 1 = bullish, -1 = bearish, 0 = neutral
   
   for(int i = Structure_MinSwing; i < Structure_Lookback - Structure_MinSwing; i++)
   {
      bool isSwingHigh = true, isSwingLow = true;
      
      for(int j = 1; j <= Structure_MinSwing; j++)
      {
         if(highs[i] <= highs[i-j] || highs[i] <= highs[i+j]) isSwingHigh = false;
         if(lows[i] >= lows[i-j] || lows[i] >= lows[i+j]) isSwingLow = false;
      }
      
      if(isSwingHigh && highs[i] > lastSwingHigh)
      {
         lastSwingHigh = highs[i];
         if(lastSwingHigh > highs[0]) direction = -1; // LH = bearish
      }
      
      if(isSwingLow && lows[i] < lastSwingLow)
      {
         lastSwingLow = lows[i];
         if(lastSwingLow < lows[0]) direction = 1; // HL = bullish
      }
   }
   
   return direction;
}

//+------------------------------------------------------------------+
//| Liquidity Pool Detection                                           |
//+------------------------------------------------------------------+
void DetectLiquidityPools(int shift, double &supportLevel, double &resistanceLevel)
{
   double levels[];
   int touches[];
   ArrayResize(levels, 50);
   ArrayResize(touches, 50);
   int levelCount = 0;
   
   // Find equal highs/lows (liquidity pools)
   for(int i = shift; i < shift + 100; i++)
   {
      double high = iHigh(_Symbol, PERIOD_CURRENT, i);
      double low = iLow(_Symbol, PERIOD_CURRENT, i);
      
      bool found = false;
      for(int j = 0; j < levelCount; j++)
      {
         if(MathAbs(high - levels[j]) < _Point * 10)
         {
            touches[j]++;
            found = true;
            break;
         }
      }
      
      if(!found && levelCount < 50)
      {
         levels[levelCount] = high;
         touches[levelCount] = 1;
         levelCount++;
      }
   }
   
   // Find levels with most touches (strongest liquidity)
   int maxTouches = 0;
   supportLevel = 0;
   resistanceLevel = 999999;
   
   for(int i = 0; i < levelCount; i++)
   {
      if(touches[i] >= 3) // Minimum 3 touches = liquidity pool
      {
         if(levels[i] < iClose(_Symbol, PERIOD_CURRENT, shift))
            supportLevel = MathMax(supportLevel, levels[i]);
         else
            resistanceLevel = MathMin(resistanceLevel, levels[i]);
      }
   }
}

//+------------------------------------------------------------------+
//| Main calculation function                                          |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
{
   if(rates_total < RSI_Period + 1) return(0);
   
   int limit = rates_total - prev_calculated;
   if(limit > rates_total - RSI_Period - 1) limit = rates_total - RSI_Period - 1;
   
   for(int i = limit; i >= 0; i--)
   {
      // RSI
      RSIBuffer[i] = CalculateRSI(RSI_Period, i);
      
      // MACD
      double macd, signal;
      CalculateMACD(i, macd, signal);
      MACDBuffer[i] = macd;
      SignalBuffer[i] = signal;
      
      // Structure
      StructureBuffer[i] = DetectStructure(i);
   }
   
   return(rates_total);
}
//+------------------------------------------------------------------+
