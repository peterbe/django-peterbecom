import re


def html_highlight(text, term):
    """
    Highlight the term in the text with HTML <mark> tags.

    Args:
        text (str): The text to search in.
        term (str): The term to highlight.

    Returns:
        str: The text with the term highlighted.
    """
    regex = re.compile(rf"\b{re.escape(term)}\w*\b", re.IGNORECASE)
    return regex.sub(lambda m: f"<mark>{m.group(0)}</mark>", text)
