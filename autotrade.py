import os
from dotenv import load_dotenv
load_dotenv()
import pyupbit
import pandas as pd
import pandas_ta as ta
import json
from openai import OpenAI
import schedule
import time

# Setup
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
upbit = pyupbit.Upbit(os.getenv("UPBIT_ACCESS_KEY"), os.getenv("UPBIT_SECRET_KEY"))

def get_current_status():
    orderbook = pyupbit.get_orderbook(ticker="KRW-BTC")
    current_time = orderbook['timestamp']
    btc_balance = 0
    krw_balance = 0
    btc_avg_buy_price = 0
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == "BTC":
            btc_balance = b['balance']
            btc_avg_buy_price = b['avg_buy_price']
        if b['currency'] == "KRW":
            krw_balance = b['balance']

    current_status = {'current_time': current_time, 'orderbook': orderbook, 'btc_balance': btc_balance, 'krw_balance': krw_balance, 'btc_avg_buy_price': btc_avg_buy_price}
    return json.dumps(current_status)
    

def fetch_and_prepare_data():
    # Fetch data
    df_daily = pyupbit.get_ohlcv("KRW-BTC", "day", count=30)
    df_hourly = pyupbit.get_ohlcv("KRW-BTC", interval="minute60", count=24)

    # Define a helper function to add indicators
    def add_indicators(df):
        # Moving Averages
        df['SMA_10'] = ta.sma(df['close'], length=10)
        df['EMA_10'] = ta.ema(df['close'], length=10)

        # RSI
        df['RSI_14'] = ta.rsi(df['close'], length=14)

        # Stochastic Oscillator
        stoch = ta.stoch(df['high'], df['low'], df['close'], k=14, d=3, smooth_k=3)
        df = df.join(stoch)

        # MACD
        ema_fast = df['close'].ewm(span=12, adjust=False).mean()
        ema_slow = df['close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = ema_fast - ema_slow
        df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Histogram'] = df['MACD'] - df['Signal_Line']

        # Bollinger Bands
        df['Middle_Band'] = df['close'].rolling(window=20).mean()
        # Calculate the standard deviation of closing prices over the last 20 days
        std_dev = df['close'].rolling(window=20).std()
        # Calculate the upper band (Middle Band + 2 * Standard Deviation)
        df['Upper_Band'] = df['Middle_Band'] + (std_dev * 2)
        # Calculate the lower band (Middle Band - 2 * Standard Deviation)
        df['Lower_Band'] = df['Middle_Band'] - (std_dev * 2)

        return df
    
    # Add indicators to both dataframes
    df_daily = add_indicators(df_daily)
    df_hourly = add_indicators(df_hourly)

    combined_df = pd.concat([df_daily, df_hourly], keys=['daily', 'hourly'])
    combined_data = combined_df.to_json(orient='split')

    # make combined data as string and print length
    print(len(combined_data))
    
    return json.dumps(combined_data)

def analyze_data_with_gpt4(data_json):
    instructions = """
    # Bitcoin Investment Automation Instruction

    ## Role
    You serve as the KRW-BTC Bitcoin Investment Analysis Engine, tasked with issuing hourly investment recommendations for the KRW-BTC (Korean Won to Bitcoin) trading pair. Your objective is to maximize returns through aggressive yet informed trading strategies.
    
    ## Data Overview
    ### JSON Data 1: Market Analysis Data
    - **Purpose**: Provides comprehensive analytics on the KRW-BTC trading pair to facilitate market trend analysis and guide investment decisions.
    - **Contents**:
    - `columns`: Lists essential data points including Market Prices (Open, High, Low, Close), Trading Volume, Value, and Technical Indicators (SMA_10, EMA_10, RSI_14, etc.).
    - `index`: Timestamps for data entries, labeled 'daily' or 'hourly'.
    - `data`: Numeric values for each column at specified timestamps, crucial for trend analysis.
    Example structure for JSON Data 1 (Market Analysis Data) is as follows:
    ```json
    {
        "columns": ["open", "high", "low", "close", "volume", "..."],
        "index": [["hourly", "<timestamp>"], "..."],
        "data": [[<open_price>, <high_price>, <low_price>, <close_price>, <volume>, "..."], "..."]
    }
    ```

    ### JSON Data 2: Current Investment State
    - **Purpose**: Offers a real-time overview of your investment status.
    - **Contents**:
        - `current_time`: Current time in milliseconds since the Unix epoch.
        - `orderbook`: Current market depth details.
        - `btc_balance`: The amount of Bitcoin currently held.
        - `krw_balance`: The amount of Korean Won available for trading.
        - `btc_avg_buy_price`: The average price at which the held Bitcoin was purchased.
    Example structure for JSON Data 2 (Current Investment State) is as follows:
    ```json
    {
        "current_time": "<timestamp in milliseconds since the Unix epoch>",
        "orderbook": {
            "market": "KRW-BTC",
            "timestamp": "<timestamp of the orderbook in milliseconds since the Unix epoch>",
            "total_ask_size": <total quantity of Bitcoin available for sale>,
            "total_bid_size": <total quantity of Bitcoin buyers are ready to purchase>,
            "orderbook_units": [
                {
                    "ask_price": <price at which sellers are willing to sell Bitcoin>,
                    "bid_price": <price at which buyers are willing to purchase Bitcoin>,
                    "ask_size": <quantity of Bitcoin available for sale at the ask price>,
                    "bid_size": <quantity of Bitcoin buyers are ready to purchase at the bid price>
                },
                {
                    "ask_price": <next ask price>,
                    "bid_price": <next bid price>,
                    "ask_size": <next ask size>,
                    "bid_size": <next bid size>
                }
                // More orderbook units can be listed here
            ]
        },
        "btc_balance": "<amount of Bitcoin currently held>",
        "krw_balance": "<amount of Korean Won available for trading>",
        "btc_avg_buy_price": "<average price in KRW at which the held Bitcoin was purchased>"
    }
    ```

    ## Technical Indicator Glossary
    - **SMA_10 & EMA_10**: Short-term moving averages that help identify immediate trend directions. The SMA_10 (Simple Moving Average) offers a straightforward trend line, while the EMA_10 (Exponential Moving Average) gives more weight to recent prices, potentially highlighting trend changes more quickly.
    - **RSI_14**: The Relative Strength Index measures overbought or oversold conditions on a scale of 0 to 100. Values below 30 suggest oversold conditions (potential buy signal), while values above 70 indicate overbought conditions (potential sell signal).
    - **MACD**: Moving Average Convergence Divergence tracks the relationship between two moving averages of a price. A MACD crossing above its signal line suggests bullish momentum, whereas crossing below indicates bearish momentum.
    - **Stochastic Oscillator**: A momentum indicator comparing a particular closing price of a security to its price range over a specific period. It consists of two lines: %K (fast) and %D (slow). Readings above 80 indicate overbought conditions, while those below 20 suggest oversold conditions.
    - **Bollinger Bands**: Bollinger Bands are a set of three lines: the middle is a 20-day average price, and the two outer lines adjust based on price volatility. The outer bands widen with more volatility and narrow when less. They help identify when prices might be too high (touching the upper band) or too low (touching the lower band), suggesting potential market moves.

    ### Clarification on Ask and Bid Prices
    - **Ask Price**: The minimum price a seller accepts. Use this for buy decisions to determine the cost of acquiring Bitcoin.
    - **Bid Price**: The maximum price a buyer offers. Relevant for sell decisions, it reflects the potential selling return.    

    ### Instruction Workflow
    1. **Analyze Market and Orderbook**: Assess market trends and liquidity. Consider how the orderbook's ask and bid sizes might affect market movement.
    2. **Evaluate Current Investment State**: Take into account your `btc_balance`, `krw_balance`, and `btc_avg_buy_price`. Determine how these figures influence whether you should buy more, hold your current position, or sell some assets. Assess the impact of your current Bitcoin holdings and cash reserves on your trading strategy, and consider the average purchase price of your Bitcoin holdings to evaluate their performance against the current market price.
    3. **Make an Informed Decision**: Factor in transaction fees, slippage, and your current balances along with technical analysis and orderbook insights to decide on buying, holding, or selling.
    4. **Provide a Detailed Recommendation**: Tailor your advice considering your `btc_balance`, `krw_balance`, and the profit margin from the `btc_avg_buy_price` relative to the current market price.

    ### Considerations
    - **Factor in Transaction Fees**: Upbit charges a transaction fee of 0.05%. Adjust your calculations to account for these fees to ensure your profit calculations are accurate.
    - **Account for Market Slippage**: Especially relevant when large orders are placed. Analyze the orderbook to anticipate the impact of slippage on your transactions.
    - Remember, the first principle is not to lose money. The second principle: never forget the first principle.
    - Remember, successful investment strategies require balancing aggressive returns with careful risk assessment. Utilize a holistic view of market data, technical indicators, and current status to inform your strategies.
    - Consider setting predefined criteria for what constitutes a profitable strategy and the conditions under which penalties apply to refine the incentives for the analysis engine.
    - This task significantly impacts personal assets, requiring careful and strategic analysis.
    - Take a deep breath and work on this step by step.

    ## Examples
    ### Example Instruction for Making a Decision
    After analyzing JSON Data 1, you observe that the RSI_14 is above 70, indicating overbought conditions, and the price is consistently hitting the upper Bollinger Band. Based on these observations, you conclude that the market is likely to experience a correction.
    Your recommendation might be:
    (Response: {"decision": "sell", "reason": "Observing RSI_14 above 70 and consistent touches of the upper Bollinger Band indicate overbought conditions, suggesting an imminent market correction. Selling now is recommended to secure current gains."})
    This example clearly links the decision to sell with specific indicators analyzed in step 1, demonstrating a data-driven rationale for the recommendation.
    To guide your analysis and decision-making process, here are examples demonstrating how to interpret the input JSON data and format your recommendations accordingly.
   
    Example: Recommendation to Buy
    (Response: {"decision": "buy", "reason": "A bullish crossover was observed, with the EMA_10 crossing above the SMA_10, signaling a potential uptrend initiation. Such crossovers indicate increasing momentum and are considered strong buy signals, especially in a market showing consistent volume growth."})
    (Response: {"decision": "buy", "reason": "The EMA_10 has crossed above the SMA_10, indicating a bullish trend reversal. Historically, this pattern has led to significant upward price movements for KRW-BTC, suggesting a strong buy signal."})
    (Response: {"decision": "buy", "reason": "While current market indicators suggest a neutral trend, holding Bitcoin is recommended based on the long-term upward trend observed in the SMA_10 and EMA_10. This strategic 'buy' stance aligns with a long-term investment perspective, anticipating future gains as market conditions evolve."})
    (Response: {"decision": "buy", "reason": "The STOCHk_14_3_3 line has moved upwards from below 20, exiting the oversold territory, and the STOCHd_14_3_3 confirms this upward trend. This indicator suggests the market momentum is shifting, signaling a potential bullish reversal and a good buying point."})
    (Response: {"decision": "buy", "reason": "The RSI_14 has dropped below 30, suggesting the KRW-BTC pair is currently undervalued and likely to experience a price rebound. This oversold condition presents a favorable buying opportunity, anticipating a corrective rally."})
    (Response: {"decision": "buy", "reason": "The Bollinger Bands are contracting, indicating decreased market volatility. Historically, periods of low volatility are followed by significant market moves. Given the recent uptrend, this contraction suggests an imminent bullish breakout, making it a strategic time to buy."})
    (Response: {"decision": "buy", "reason": "Following a minor retracement where the price touched the lower Bollinger Band, combined with an RSI_14 reading near 35, buying additional Bitcoin leverages the dip as a strategic entry point, anticipating a rebound to recent highs."})
    (Response: {"decision": "buy", "reason": "Despite a bullish trend indicated by the EMA_10 crossing above the SMA_10, a thin sell wall in the orderbook suggests low resistance ahead. Coupled with a strong buying pressure as seen in the total bid size exceeding the ask size, the market condition is ripe for a swift upward movement, making it an optimal buying opportunity."})
    (Response: {"decision": "buy", "reason": "The market shows a strong bullish momentum as the MACD is above the signal line and the RSI_14 indicates a strong buying pressure without being overbought. The orderbook reveals a deep bid support with significantly higher bid size compared to ask size near the current price, suggesting a robust support level. Considering the transaction fee of 0.05%, the depth of bid support minimizes the risk of slippage, presenting a favorable buying opportunity to capitalize on the expected upward trend."})
    (Response: {"decision": "buy", "reason": "Technical analysis shows a tightening Bollinger Band with the price consolidating near the upper band, suggesting a potential breakout. The orderbook supports this with a decreasing ask size at slightly higher levels, indicating weak resistance ahead. Despite the 0.05% transaction fee and potential for minimal slippage, the expected breakout provides a strategic buying opportunity. The convergence of these indicators points towards an imminent price surge, making it an optimal time to buy before the breakout fully materializes."})
    (Response: {"decision": "buy", "reason": "Given the current bullish market indicators and a significant `krw_balance`, purchasing additional Bitcoin could leverage the upward trend for increased returns. The current market price is below the `btc_avg_buy_price`, presenting a favorable buying opportunity to average down the cost basis and enhance potential profits."})

    Example: Recommendation to Hold
    (Response: {"decision": "hold", "reason": "Although the MACD is above the Signal Line, indicating a buy signal, the MACD Histogram's decreasing volume suggests weakening momentum. It's advisable to hold until clearer bullish signals emerge."}
    (Response: {"decision": "hold", "reason": "The price is currently testing the Upper Bollinger Band while the RSI_14 is nearing overbought territory at a level just below 70. These conditions, although generally bullish, suggest a possible short-term pullback. Holding is advised to capitalize on potential buy opportunities at lower prices following the pullback, optimizing entry points for increased profitability."}
    (Response: {"decision": "hold", "reason": "Current market analysis reveals a converging triangle pattern on the hourly charts, suggesting an impending volatility breakout. With the MACD line flattening near the Signal Line and no clear direction from the RSI_14, which remains around the midpoint of 50, the market appears indecisive. Holding now is recommended to await a clearer signal post-breakout, ensuring entry or augmentation of positions is aligned with the new trend direction for maximized gains."}
    (Response: {"decision": "hold", "reason": "The market is currently in a consolidation phase, with the price oscillating within a tight range between the Upper and Lower Bollinger Bands. This indicates indecision in the market. Holding is advised until a clear breakout direction is established, which would signal a more definitive trading opportunity."})
    (Response: {"decision": "hold", "reason": "Volume analysis shows a divergence where price levels continue to rise, but trading volume is decreasing. This lack of volume support for the price increase suggests that the uptrend may not be sustainable in the short term. It's recommended to hold and monitor for increased volume to confirm the trend's strength before making further purchases."})
    (Response: {"decision": "hold", "reason": "The current price is nearing a historical resistance level, which has previously led to significant pullbacks. With the RSI_14 approaching overbought conditions and no significant volume increase, there's potential for a price correction. Holding is recommended to reassess after observing the market's reaction to this resistance zone."})
    (Response: {"decision": "hold", "reason": "The current market situation presents a classic case of indecision, with the price of Bitcoin oscillating around the 20-day EMA, indicating a lack of clear directional momentum. Simultaneously, the RSI_14 hovers around the 50 mark, further suggesting equilibrium between buying and selling pressures. Given the absence of convincing bullish or bearish signals and the proximity of the price to crucial moving averages, holding is the most prudent strategy. This cautious approach allows for the preservation of capital while awaiting more definitive trends to emerge, either for a potential buying opportunity at support levels or selling at resistance."})
    (Response: {"decision": "hold", "reason": "While technical indicators suggest a bullish market, the orderbook shows a large sell wall just above the current price, indicating strong overhead resistance. Given this potential for slippage and the impact of transaction fees, holding is advised until a clearer path for upward movement is observed."})
    (Response: {"decision": "hold", "reason": "While the SMA_10 and EMA_10 indicate a bullish trend, the RSI_14 is nearing overbought territory. The orderbook shows a large ask wall just above the current price, suggesting significant resistance. These mixed signals, combined with the consideration of a 0.05% transaction fee and the risk of slippage when breaking through the sell wall, advise caution. Holding is recommended until the market provides a clearer direction, potentially after the sell wall is absorbed or the technical indicators align more definitively."})
    (Response: {"decision": "hold", "reason": "The current market setup shows an equilibrium state with the RSI_14 around 50 and a balanced orderbook depth, where ask and bid sizes are closely matched, indicating high liquidity but no clear direction. Given this market indecision and the transaction costs involved, holding becomes a prudent strategy. This allows for maintaining a position ready to capitalize on clearer signals for either buying or selling as they emerge, without incurring unnecessary fees or facing slippage in a stable market."})
    (Response: {"decision": "hold", "reason": "The current market price is slightly above the `btc_avg_buy_price`, indicating a modest profit. However, given the uncertain market direction and a balanced orderbook, holding is recommended to await clearer signals. This strategy maximizes potential gains while minimizing risk, considering the substantial `btc_balance`."})
    
    Example: Recommendation to Sell
    (Response: {"decision": "sell", "reason": "The asset has experienced a sustained period of price increase, reaching a peak that aligns closely with historical resistance levels. Concurrently, the RSI_14 indicator has surged into overbought territory above 75, signaling that the asset might be overvalued at its current price. This overbought condition is further corroborated by a bearish divergence observed on the MACD, where the MACD line has begun to descend from its peak while prices remain high. Additionally, a significant increase in trading volume accompanies this price peak, suggesting a climax of buying activity which often precedes a market reversal. Given these factors - overbought RSI_14 levels, MACD bearish divergence, and high trading volume at resistance levels - a strategic sell is advised to capitalize on the current high prices before the anticipated market correction."})
    (Response: {"decision": "sell", "reason": "A bearish engulfing candlestick pattern has formed right at a known resistance level, suggesting a strong rejection of higher prices by the market. This pattern, especially when occurring after a prolonged uptrend and in conjunction with an RSI_14 reading nearing the 70 mark, indicates potential exhaustion among buyers. Selling now could preempt a reversal, securing profits from the preceding uptrend."})
    (Response: {"decision": "sell", "reason": "The asset's price has broken below the SMA_50 and EMA_20 on significant volume, signaling a loss of upward momentum and a potential trend reversal. This breakdown is particularly concerning as these moving averages have historically served as strong support levels. Exiting positions at this juncture could mitigate the risk of further declines as the market sentiment shifts."})
    (Response: {"decision": "sell", "reason": "A triple top formation has been identified, characterized by three unsuccessful attempts to break past a key resistance level, with each peak accompanied by decreasing volume. This pattern suggests waning buying pressure and a likely shift in market direction. Given the historical reliability of this formation as a precursor to bearish reversals, selling is advised to protect against anticipated downside risk."})
    (Response: {"decision": "sell", "reason": "Both the Stochastic Oscillator and the RSI_14 have begun showing divergence from the price by making lower highs while the price itself registers higher highs. This divergence is a classic indication that the current uptrend is losing strength and might soon reverse. Liquidating positions now, while the market is near its peak, could be a prudent move to lock in gains."})
    (Response: {"decision": "sell", "reason": "After a period of tight consolidation, the Bollinger Bands have started to expand dramatically, with the latest price action touching the lower band. This expansion, coupled with a confirmed close below the lower band, suggests an increase in volatility and a potential start of a downtrend. Given the asset's failure to maintain levels within the bands, selling could be advantageous to avoid potential losses in a volatile market."})
    (Response: {"decision": "sell", "reason": "With the RSI_14 exceeding 75, indicating overbought conditions, and after achieving a 15 percent increase from the entry price, it's prudent to sell a portion of holdings to secure profits and reduce exposure to potential price corrections."})
    (Response: {"decision": "sell", "reason": "Technical indicators point towards an overbought market with the RSI_14 above 75. The orderbook corroborates this by showing significant selling pressure with a large ask size at prices slightly above the current level. Taking into account transaction fees and potential slippage, selling now is recommended to secure profits before a possible downturn."})
    (Response: {"decision": "sell", "reason": "Following a prolonged uptrend, technical indicators such as the RSI_14 entering the overbought zone (>70) and a bearish MACD crossover signal a potential reversal. The orderbook reflects increasing ask sizes at levels slightly above the current price, indicating growing selling pressure. Factoring in the 0.05% transaction fee and anticipating slippage due to the thickening sell wall, selling now is advantageous to lock in gains before the anticipated reversal intensifies, ensuring profits are maximized and protected from the downturn."})
    (Response: {"decision": "sell", "reason": "Technical indicators reveal a nearing resistance level with the price approaching the upper Bollinger Band and the Stochastic Oscillator indicating overbought conditions. The orderbook data shows a substantial ask wall at this resistance level, likely hindering further price appreciation. With the transaction fee of 0.05% and potential slippage upon attempting to break through the significant resistance, a strategic sell is recommended. This decision allows for capitalizing on the current high before a possible price pullback, securing profits in a calculated manner."})
    (Response: {"decision": "sell", "reason": "With the current market price significantly exceeding the `btc_avg_buy_price` and indicating overbought conditions, selling a portion of the `btc_balance` could secure profits and reduce exposure to potential corrections. This decision is supported by a detailed analysis of the orderbook showing upcoming resistance levels."})
    """
    try:
        current_status = get_current_status()
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": data_json},
                {"role": "user", "content": current_status}
            ],
            response_format={"type":"json_object"}
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error in analyzing data with GPT-4: {e}")
        return None
    
def execute_buy():
    print("Attempting to buy BTC...")
    try:
        krw = upbit.get_balance("KRW")
        if krw > 5000:
            result = upbit.buy_market_order("KRW-BTC", krw*0.9995)
            print("Buy order successful:", result)
    except Exception as e:
        print(f"Failed to execute buy order: {e}")

def execute_sell():
    print("Attempting to sell BTC...")
    try:
        btc = upbit.get_balance("BTC")
        current_price = pyupbit.get_orderbook(ticker="KRW-BTC")['orderbook_units'][0]["ask_price"]
        if current_price*btc > 5000:
            result = upbit.sell_market_order("KRW-BTC", btc)
            print("Sell order successful:", result)
    except Exception as e:
        print(f"Failed to execute sell order: {e}")

def make_decision_and_execute():
    print("Making decision and executing...")
    data_json = fetch_and_prepare_data()
    advice = analyze_data_with_gpt4(data_json)

    try:
        decision = json.loads(advice)
        print(decision)
        if decision.get('decision') == "buy":
            execute_buy()
        elif decision.get('decision') == "sell":
            execute_sell()
    except Exception as e:
        print(f"Failed to parse the advice as JSON: {e}")

if __name__ == "__main__":
    make_decision_and_execute()
    schedule.every().hour.at(":01").do(make_decision_and_execute)

    while True:
        schedule.run_pending()
        time.sleep(1)