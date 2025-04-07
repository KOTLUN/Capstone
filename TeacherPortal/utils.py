from datetime import datetime

def get_current_quarter():
    """
    Determine the current quarter based on the date.
    
    The academic year is divided into four quarters:
    - First Quarter: June to August
    - Second Quarter: September to November
    - Third Quarter: December to February
    - Fourth Quarter: March to May
    
    Returns:
        str: Quarter number ('1', '2', '3', or '4')
    """
    now = datetime.now()
    month = now.month
    
    if month in [6, 7, 8]:
        return '1'
    elif month in [9, 10, 11]:
        return '2'
    elif month in [12, 1, 2]:
        return '3'
    else:  # month in [3, 4, 5]:
        return '4' 