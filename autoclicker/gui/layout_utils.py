"""Small display-only helpers to prevent unbounded label geometry."""

def shorten_middle(value, limit=36):
    value = str(value)
    if limit < 5:
        raise ValueError("limit must be >= 5")
    if len(value) <= limit:
        return value
    side = (limit - 1) // 2
    return value[:side] + "…" + value[-(limit - side - 1):]
