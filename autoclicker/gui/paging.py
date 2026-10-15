"""Bounded, stable pagination for large template lists."""

DEFAULT_PAGE_SIZE = 20


def select_template_page(order, query="", page=0, page_size=DEFAULT_PAGE_SIZE):
    """Return (filenames with original priority, page, number of pages, total)."""
    if page_size < 1:
        raise ValueError("page_size must be >= 1")
    needle = str(query).strip().casefold()
    matches = [
        (index, filename)
        for index, filename in enumerate(order)
        if not needle or needle in filename.casefold()
    ]
    total = len(matches)
    pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(int(page), pages - 1))
    start = page * page_size
    return matches[start:start + page_size], page, pages, total
