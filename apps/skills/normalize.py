"""Text normalisation shared by aliases and the skill matcher (single definition, used everywhere)."""
import re

_KEEP = re.compile(r"[^a-z0-9+#.\s]")
_SPACES = re.compile(r"\s+")


def normalize_term(text: str) -> str:
    """Lower-case, drop punctuation except + # . (so c++, c#, node.js survive), collapse whitespace."""
    t = _KEEP.sub(" ", text.lower().replace("/", " ").replace("-", " "))
    return _SPACES.sub(" ", t).strip(" .")
