import time
import math

def calculate_metrics(views, likes, comments, shares, saves, create_time):
    current_time = int(time.time())
    age_hours = max((current_time - create_time) / 3600, 0.1) if create_time > 0 else 0.1
    views_per_hour = round(views / age_hours, 2)

    engagement_points = likes + (comments * 2) + (saves * 3) + (shares * 4)
    engagement_rate = (engagement_points / views) * 100 if views > 0 else 0
    
    viral_velocity = round((views_per_hour * engagement_rate) / math.log10(age_hours + 10), 2)
    
    return views_per_hour, round(engagement_rate, 2), viral_velocity