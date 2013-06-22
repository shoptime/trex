
def iso_minute(dt):
    """
    Simple ISO to the minute, useful for log lines, created timestamps etc for non-auto processes
    """
    return dt.strftime('%Y-%m-%d %H:%M')
