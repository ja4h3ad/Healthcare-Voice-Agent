from datetime import datetime


def format_datetime_for_tts(dt: datetime) -> str:
    # Format the date
    date_str = dt.strftime("%B %d, %Y")

    # Add the ordinal indicator to the day
    day = dt.day
    if 4 <= day <= 20 or 24 <= day <= 30:
        suffix = "th"
    else:
        suffix = ["st", "nd", "rd"][day % 10 - 1]
    date_str = date_str.replace(f" {day},", f" {day}{suffix},")

    # Format the time
    time_str = dt.strftime("%I:%M %p").lstrip("0")

    return f"{date_str} at {time_str}"