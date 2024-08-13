from datetime import datetime


def current_timestamp_with_iso_week_local():
    now = datetime.now().astimezone()
    iso_timestamp = now.replace(second=0, microsecond=0).isoformat()
    day_of_week = now.strftime("%A")
    # ISO week number
    week_number = now.strftime("%V")
    formatted_string = f"{iso_timestamp} [{day_of_week}, Week {week_number}]"
    return formatted_string
