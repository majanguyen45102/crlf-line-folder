"""Fold header lines per RFC 5322 section 2.2.3.

RFC 5322 mandates that each logical line of a header field be wrapped to at
most 78 characters (998 is the hard limit). Wrapping is achieved by inserting
CRLF followed by at least one space or tab; the whitespace both separates the
lines and signals continuation to the parser.

Design decisions
----------------

1. Only ASCII is supported. RFC 5322 headers are ASCII; MIME-encoded words
   (RFC 2047) carry non-ASCII payloads as ASCII. Handling raw UTF-8 would
   conflate transport encoding with header folding, so we refuse it.

2. We fold at existing whitespace boundaries when possible. If a single token
   exceeds the limit we break it (there is no other option) and insert a
   continuation after each chunk. We never split a token mid-byte because the
   input is ASCII.

3. The line is measured *including* any trailing CRLF-free content but the
   78-char budget applies to each physical line. A folded line is
   ``<line1>\r\n <line2>\r\n <line3>`` — the leading space on continuation
   lines counts toward their 78-char budget.
"""

from __future__ import annotations

__all__ = ["fold_line", "fold_header"]

MAX_LINE_LEN = 78
CRLF = "\r\n"


class FoldError(ValueError):
    """Raised when a header line cannot be folded within the rules."""


def _is_ascii(text: str) -> bool:
    try:
        text.encode("ascii")
    except UnicodeEncodeError:
        return False
    return True


def fold_line(line: str, max_len: int = MAX_LINE_LEN) -> str:
    """Fold a single header *line* to at most ``max_len`` characters per physical line.

    The input must not contain ``\r`` or ``\n``; pass one logical header line
    at a time. The returned string uses ``\r\n`` followed by a single space as
    the fold separator, per RFC 5322 §2.2.3.

    Parameters
    ----------
    line:
        One logical header line (e.g. ``"Subject: Hello, world"``).
    max_len:
        Maximum number of characters on any single physical line, including
        the leading continuation whitespace. Defaults to 78 per RFC 5322.

    Returns
    -------
    str
        The folded line with ``\r\n`` separators. No trailing ``\r\n`` is
        appended.

    Raises
    ------
    FoldError
        If *line* contains ``\r`` or ``\n``, or contains non-ASCII
        characters, or *max_len* is too small to hold a continuation.
    """
    if not isinstance(line, str):
        raise TypeError("line must be str")
    if not isinstance(max_len, int):
        raise TypeError("max_len must be int")
    if max_len < 3:
        # A continuation line needs at least one leading space plus one
        # character of content plus... actually one char of content is enough
        # for the line itself, but we need room for the leading space and at
        # least one payload character.
        raise FoldError("max_len must be at least 3")
    if "\r" in line or "\n" in line:
        raise FoldError("line must not contain CR or LF; pass one logical line")
    if not _is_ascii(line):
        raise FoldError("line contains non-ASCII characters; encode with RFC 2047 first")

    if len(line) <= max_len:
        return line

    return _fold(line, max_len)


def _fold(line: str, max_len: int) -> str:
    """Core folding routine. Precondition: *line* is ASCII, no CR/LF, len > max_len."""
    out: list[str] = []
    pos = 0
    n = len(line)

    while pos < n:
        remaining = n - pos
        if remaining <= max_len:
            out.append(line[pos:])
            break

        # We need to wrap. Find the rightmost whitespace within the budget.
        # On the first chunk the budget is max_len; on continuation chunks we
        # must reserve one leading space.
        budget = max_len if not out else max_len - 1

        if budget < 1:
            raise FoldError("max_len too small for continuation")

        chunk_end = pos + budget
        if chunk_end > n:
            chunk_end = n

        # Search backwards for whitespace in [pos, chunk_end).
        wrap_at = -1
        for i in range(chunk_end - 1, pos, -1):
            if line[i] == " " or line[i] == "\t":
                wrap_at = i
                break

        if wrap_at == -1:
            # No whitespace in the budget: we must hard-break the token.
            # Emit a full chunk and continue on the next line.
            out.append(line[pos:chunk_end])
            pos = chunk_end
        else:
            # Emit up to (but not including) the whitespace, then skip past
            # exactly one whitespace character — the fold's own space replaces
            # it on the continuation line.
            out.append(line[pos:wrap_at])
            pos = wrap_at + 1

    return (CRLF + " ").join(out)


def fold_header(name: str, value: str, max_len: int = MAX_LINE_LEN) -> str:
    """Fold a ``Name: value`` header line.

    Equivalent to ``fold_line(f"{name}: {value}", max_len)`` but with the
    name and value provided separately, which is the more common call site.

    Raises
    ------
    FoldError
        If *name* is empty, or either *name* or *value* contains CR/LF or
        non-ASCII characters.
    """
    if not name:
        raise FoldError("header name must be non-empty")
    if ":" in name:
        raise FoldError("header name must not contain ':'")
    combined = f"{name}: {value}"
    return fold_line(combined, max_len=max_len)
