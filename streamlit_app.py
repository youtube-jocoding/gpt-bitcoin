import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import pyupbit

def load_data():
    db_path = 'trading_decisions.sqlite'
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp, decision, percentage, reason, btc_balance, krw_balance, btc_avg_buy_price, btc_krw_price FROM decisions ORDER BY timestamp")
        decisions = cursor.fetchall()
        df = pd.DataFrame(decisions, columns=['timestamp', 'decision', 'percentage', 'reason', 'btc_balance', 'krw_balance', 'btc_avg_buy_price', 'btc_krw_price'])
        return df

def main():
    st.set_page_config(layout="wide")
    st.title("실시간 비트코인 GPT 자동매매 기록")
    st.write("by 유튜버 [조코딩](https://youtu.be/MgatVqXXoeA) - [Github](https://github.com/youtube-jocoding/gpt-bitcoin)")
    st.write("---")
    df = load_data()
    if not df.empty:
        start_value = 2000000
        current_price = pyupbit.get_orderbook(ticker="KRW-BTC")['orderbook_units'][0]["ask_price"]
        latest_row = df.iloc[-1]
        btc_balance = latest_row['btc_balance']
        krw_balance = latest_row['krw_balance']
        btc_avg_buy_price = latest_row['btc_avg_buy_price']
        current_value = int(btc_balance * current_price + krw_balance)

        time_diff = datetime.now() - pd.to_datetime(df.iloc[0]['timestamp'])
        days = time_diff.days
        hours = time_diff.seconds // 3600
        minutes = (time_diff.seconds % 3600) // 60

        st.header("수익률:"+str(round((current_value-start_value)/start_value*100, 2))+"%")
        st.write("현재 시각:"+str(datetime.now()))
        st.write("투자기간:", days, "일", hours, "시간", minutes, "분")
        st.write("시작 원금", start_value, "원")
        st.write("현재 비트코인 가격:", current_price, "원")
        st.write("현재 보유 현금:", krw_balance, "원")
        st.write("현재 보유 비트코인:", btc_balance, "BTC")
        st.write("BTC 매수 평균가격:", btc_avg_buy_price, "원")
        st.write("현재 원화 가치 평가:", current_value, "원")

        st.dataframe(df, use_container_width=True)

if __name__ == '__main__':
    main()