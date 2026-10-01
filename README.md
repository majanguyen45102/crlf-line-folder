# crlf-line-folder

Folds long RFC 5322 header lines to 78 characters per physical line using CRLF + space as the continuation marker.

## Usage

```python
from crlf_line_folder import fold_line, fold_header

# Fold a pre-formed logical line.
folded = fold_line("Subject: " + "x" * 100)
# 'Subject: ' + 69 x's + '\r\n ' + remaining x's ...

# Or pass name and value separately.
folded = fold_header("Subject", "A very long subject line " * 10)
```

The exported names are `fold_line` and `fold_header`. Both accept an optional `max_len` integer (default 78). The return value uses `\r\n` (CRLF) as the line separator and never ends with a trailing `\r\n`.

## Why

RFC 5322 §2.2.3 requires header lines to be wrapped at 78 characters (998 hard limit). Doing this naively — splitting at 78 and inserting `\r\n ` — corrupts tokens and can leave the continuation line over budget because the leading space on each wrapped line counts toward its own 78-character limit.

This library folds at existing whitespace where possible, and when a single token exceeds the budget it hard-breaks the token across lines (there is no alternative within ASCII). The leading continuation space is reserved from the budget on every wrapped line.

## Edge cases you will hit

- **Non-ASCII is rejected.** RFC 5322 headers are ASCII. Encode non-ASCII payloads with RFC 2047 encoded words before folding. Mixing UTF-8 into folding would conflate transport encoding with line wrapping.
- **Input must not contain `\r` or `\n`.** Pass one logical line at a time. The library does not parse a full header block.
- **Hard breaks inside long tokens.** A 200-character word with no spaces will be split at the 78-character boundary. There is no way to avoid this while staying within the limit.
- **`max_len` must be at least 3.** Smaller values cannot hold a continuation line (one leading space plus at least one payload character plus the fold marker context).

## Performance

The window keeps a bounded buffer, so `push` is constant time and memory does not
grow with the length of the stream. `peak` and `trough` are linear in the window
size, which is the trade that keeps `push` cheap.

