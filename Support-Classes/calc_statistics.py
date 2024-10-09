# Calculating Result statistics

import pandas as pd
import numpy as np

def calculate_nakamoto_coefficient(holder):
    # Sort entities by power descending
    sorted_holder = sorted(holder, key=lambda x: x[1], reverse=True)
    
    # Calculate the total power
    total_power = sum(power for _, power in sorted_holder)
    
    # Find the minimum number of entities needed for a 51% majority
    
    cumulative_power = 0
    nakamoto_coefficient = 0
    
    for _, power in sorted_holder:
        cumulative_power += power
        nakamoto_coefficient += 1
        # Check if the cumulative power is at least 51% of the total
        if cumulative_power >= total_power * 0.51:
            break

    return nakamoto_coefficient


def calculate_hhi(holder):
    # Calculate the total power
    total_power = sum(power for _, power in holder)
    
    # Calculate each holder's market share squared and sum them
    hhi = sum(((power / total_power) * 100)  ** 2 for _, power in holder)
    
    return hhi

# Define the Garman-Klass volatility calculation function
def garman_klass_volatility(prices_df):
    """
    Calculate the Garman-Klass volatility from a DataFrame with 'epoch' and 'ticket_price'.
    
    Parameters:
    prices_df (DataFrame): DataFrame with columns 'epoch' and 'ticket_price'

    Returns:
    float: Estimated Garman-Klass volatility
    """
    # Group by 'epoch' to calculate Open, High, Low, and Close
    ohlcv = prices_df.groupby('epoch')['ticket_price'].agg(
        Open=lambda x: x.iloc[0],
        High='max',
        Low='min',
        Close=lambda x: x.iloc[-1]
    ).reset_index()

    # Squared Logarithm of the ratio of high to low prices
    log_hl = np.log(ohlcv['High'] / ohlcv['Low'])**2
    
    # Squared Logarithm of the ratio of closing to opening prices
    log_co = np.log(ohlcv['Close'] / ohlcv['Open'])**2
    
    # Garman-Klass volatility formula
    variance = 0.5 * log_hl - (2*np.log(2) - 1) * log_co
    volatility = np.sqrt(variance.mean())
    
    return volatility

def calc_variance_of_deltas(prices_df):
    
    deltas = np.diff(prices_df['ticket_price'])
    variance = np.var(deltas)

    return variance

