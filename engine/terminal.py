"""Terminal utilities for the Infinite RPG UI V2.1.

Provides ANSI color support, screen size detection, and display-width-aware
string operations that correctly handle ANSI escape sequences.
"""

import os
import re
import shutil
import sys
from typing import List

# ---------------------------------------------------------------------------
# ANSI color support
# ---------------------------------------------------------------------------

_COLORS_ENABLED = False

if sys.stdout.isatty():
    _COLORS_ENABLED = True
    if os.name == "nt":
        try:
            import colorama
            colorama.just_fix_windows_console()
        except ImportError:
            pass


def colors_enabled() -> bool:
    return _COLORS_ENABLED


def enable_colors(enabled: bool = True):
    global _COLORS_ENABLED
    _COLORS_ENABLED = enabled


class FG:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


def colorize(text: str, *codes: str) -> str:
    if not _COLORS_ENABLED or not codes:
        return text
    return "".join(codes) + text + FG.RESET


# ---------------------------------------------------------------------------
# ANSI-aware display width
# ---------------------------------------------------------------------------

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return _ANSI_RE.sub("", text)


def visible_width(text: str) -> int:
    """Calculate the visible display width of text, ignoring ANSI codes.

    Accounts for CJK characters (width 2) and fullwidth forms.
    """
    clean = strip_ansi(text)
    width = 0
    for ch in clean:
        cp = ord(ch)
        if (
            0x4E00 <= cp <= 0x9FFF
            or 0x3400 <= cp <= 0x4DBF
            or 0xFF01 <= cp <= 0xFF60
            or 0xFFE0 <= cp <= 0xFFE6
            or 0x2E80 <= cp <= 0x2FDF
            or 0x3000 <= cp <= 0x303F
            or 0xFE30 <= cp <= 0xFE4F
            or 0x1F300 <= cp <= 0x1F9FF
            or 0x1100 <= cp <= 0x115F
        ):
            width += 2
        elif cp < 0x20 or cp == 0x7F:
            width += 0
        else:
            width += 1
    return width


# Keep legacy alias
display_width = visible_width


def pad_to_width(text: str, target_width: int, fill: str = " ") -> str:
    """Pad text so its visible width equals target_width.

    Correctly handles ANSI escape sequences by placing fill characters
    after the last ANSI code so padding is not colored.
    """
    current = visible_width(text)
    if current >= target_width:
        return text
    needed = target_width - current
    # Find the last ANSI escape code to place padding after it
    matches = list(_ANSI_RE.finditer(text))
    if matches and text.endswith(FG.RESET):
        last_end = matches[-1].end()
        return text[:last_end] + fill * needed + text[last_end:]
    return text + fill * needed


def truncate_to_width(text: str, max_width: int, suffix: str = "...") -> str:
    """Truncate text to fit within max_width visible characters."""
    if visible_width(text) <= max_width:
        return text
    suffix_width = visible_width(suffix)
    target = max_width - suffix_width
    if target <= 0:
        return suffix[:max_width]
    clean = strip_ansi(text)
    result = []
    current = 0
    for ch in clean:
        cw = 1 if ord(ch) < 0x2000 else visible_width(ch)
        if current + cw > target:
            break
        result.append(ch)
        current += cw
    truncated = "".join(result)
    # Preserve any ANSI prefix from the original text
    prefix = text[: len(text) - len(clean)] if clean != text else ""
    return prefix + truncated + suffix


# ---------------------------------------------------------------------------
# Terminal size detection
# ---------------------------------------------------------------------------

class TerminalSize:
    def __init__(self, width: int = 80, height: int = 24):
        self.width = width
        self.height = height

    @classmethod
    def detect(cls) -> "TerminalSize":
        size = shutil.get_terminal_size(fallback=(80, 24))
        return cls(width=size.columns, height=size.lines)

    def __repr__(self) -> str:
        return f"TerminalSize({self.width}x{self.height})"


# ---------------------------------------------------------------------------
# Text wrapping (ANSI-aware)
# ---------------------------------------------------------------------------

def wrap_text(text: str, width: int) -> List[str]:
    """Wrap text to fit within the given visible width.

    Respects word boundaries. ANSI codes are preserved on each output line.
    """
    if width <= 0:
        return [text] if text else [""]

    # Strip ANSI for word splitting, but preserve prefix for reapplication
    prefix = ""
    clean = text
    matches = list(_ANSI_RE.finditer(text))
    if matches:
        first_match = matches[0]
        if first_match.start() == 0:
            prefix = first_match.group()
            clean = text[first_match.end():]

    words = clean.split()
    if not words:
        return [""] if not text else [text]

    lines = []
    current_line = []
    current_width = 0

    for word in words:
        word_w = visible_width(word)
        space_w = 1 if current_line else 0
        needed = current_width + space_w + word_w

        if needed <= width:
            current_line.append(word)
            current_width = needed
        else:
            if current_line:
                lines.append(prefix + " ".join(current_line))
            current_line = [word]
            current_width = word_w

    if current_line:
        lines.append(prefix + " ".join(current_line))

    return lines if lines else [""]


# ---------------------------------------------------------------------------
# Screen buffer
# ---------------------------------------------------------------------------

class ScreenBuffer:
    """Accumulates lines and outputs them as a single screen."""

    def __init__(self):
        self._lines: List[str] = []

    def add(self, line: str = ""):
        self._lines.append(line)

    def flush(self, clear: bool = True):
        if clear:
            os.system("cls" if os.name == "nt" else "clear")
        sys.stdout.write("\n".join(self._lines))
        sys.stdout.write("\n")
        sys.stdout.flush()

    def get_output(self) -> str:
        return "\n".join(self._lines)

    def line_count(self) -> int:
        return len(self._lines)

    def clear(self):
        self._lines.clear()
