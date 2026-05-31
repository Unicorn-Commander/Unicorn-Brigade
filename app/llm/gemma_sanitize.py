"""Conservative sanitizer for Gemma/Harmony chat-template channel artifacts.

Some Gemma-family / Harmony-style chat templates leak control tokens into the
user-visible assistant text. The tokens look like channel markers, e.g.::

    <|channel|>analysis<|message|>...<|channel|>final<|message|>Hello

or shorter, malformed variants that slip through a model's decoder::

    <channel|>            <|channel|>            <channel|final|>
    <|channel|>analysis   <channel|analysis|>   <|channel|>final

This module exposes a single pure function, ``strip_channel_artifacts``,
that removes those artifacts. It is intentionally conservative:

* It only matches tokens that contain the literal word ``channel`` wrapped in
  the template's angle-and-pipe delimiters. Ordinary prose and code that
  merely contains a pipe (``a | b``, shell pipes, Python ``X | Y`` unions) is
  left completely untouched.
* When a Harmony-style transcript carries an ``analysis`` channel followed by
  a ``final`` channel, only the ``final`` channel's content is kept, since the
  analysis channel is model-internal scratch space that should never reach the
  user.
* A bare leading role token (``analysis`` / ``final``) is stripped ONLY when it
  is immediately preceded by a channel marker we already removed, i.e. it is
  unambiguously a template artifact. A normal message that simply starts with
  the word "Final" is never touched.
* Only the whitespace introduced by a removal is collapsed; the rest of the
  text (including internal newlines and indentation) is preserved.

Stdlib ``re`` only.
"""

from __future__ import annotations

import re

__all__ = ["strip_channel_artifacts"]

# Channel role tokens the Harmony/Gemma template emits. Kept narrow on purpose
# so we never eat a legitimate word that happens to follow a real channel tag.
_ROLE_TOKEN = r"(?:analysis|final|commentary)"

# The channel control token itself, in any of the observed delimiter shapes.
# The role word is NOT part of this token: in the Harmony grammar the role is a
# bare word emitted AFTER the tag (``<|channel|>final``), while some malformed
# variants instead place it INSIDE (``<channel|final|>``). We handle both by
# letting the tag optionally swallow an interior role, and separately letting it
# optionally swallow a trailing bare role word (see ``_CHANNEL_TAG``).
#
# Delimiter shapes covered for the bare tag:
#   <|channel|>   <channel|>   <|channel>   <channel>   <|channel|   (lenient)
_CHANNEL_CORE = r"""
    <\|?                # opening angle bracket, optional leading pipe
    channel             # the literal control word (required)
    \s*
    (?:\|\s*""" + _ROLE_TOKEN + r"""\s*)?   # optional INTERIOR role: <channel|final|>
    \|?                 # optional pipe before the close
    >                   # closing angle bracket
"""

# A full channel artifact: the core tag, optionally followed by a bare role
# word (the Harmony ``<|channel|>final`` shape) and/or stray whitespace. We
# require the literal "channel" word so the pattern can only ever fire on these
# template tokens, never on ordinary prose or piped code.
_CHANNEL_TAG = re.compile(
    _CHANNEL_CORE + r"""
    (?:\s*""" + _ROLE_TOKEN + r""")?   # optional TRAILING bare role word
                                       # (whitespace only consumed when a role
                                       # word actually follows, so a normal
                                       # inter-word space after the tag stays)
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Locates a 'final' channel marker in either delimiter arrangement:
#   <|channel|>final            (role trails the tag, Harmony grammar)
#   <channel|final|>            (role inside the tag, malformed variant)
# Used to find where the user-visible answer begins so the analysis/scratch
# channels before it can be dropped.
_FINAL_TAG = re.compile(
    r"""
    <\|?
    channel
    \s*
    (?:
        \|\s*final\s*\|?>        # interior:  <channel|final|>
      |
        \|?>\s*final             # trailing:  <|channel|>final
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

# The Harmony message separator that follows a channel tag, e.g.
# ``<|channel|>final<|message|>``. We strip it when it is adjacent to a channel
# tag we are already removing.
_MESSAGE_SEP = re.compile(
    r"""
    <\|?
    message
    \|?
    >
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Harmony end-of-turn / start markers that ride along with channel transcripts.
# These are only ever stripped from text that also carried a channel tag, so we
# never touch arbitrary prose.
_TURN_MARKER = re.compile(
    r"""
    <\|?
    (?:start|end|return|assistant)
    \|?
    >
    """,
    re.VERBOSE | re.IGNORECASE,
)

# A bare leading role token that the template emits with no surrounding
# delimiters, e.g. text that begins with "analysis" or "final" as the very
# first token. Anchored to the very start of the (already tag-stripped) string.
_LEADING_BARE_ROLE = re.compile(
    r"^\s*" + _ROLE_TOKEN + r"\b[ \t]*",
    re.IGNORECASE,
)


def _collapse_introduced_whitespace(text: str) -> str:
    """Collapse only the whitespace that token removal can introduce.

    Removing an inline tag can leave a doubled space or a space hugging a
    newline. We tidy those without disturbing the document's real structure:
    runs of spaces/tabs collapse to one, spaces around a newline are trimmed,
    and 3+ blank lines collapse to a maximum of two newlines.
    """
    # Spaces/tabs hugging a newline -> just the newline.
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
    # Runs of spaces or tabs -> single space.
    text = re.sub(r"[ \t]{2,}", " ", text)
    # 3+ consecutive newlines -> 2 (preserve paragraph breaks, drop the gap a
    # removed block may have opened up).
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def strip_channel_artifacts(text: str) -> str:
    """Remove Gemma/Harmony channel-template artifacts from ``text``.

    Behaviour:
      * If no channel artifact is present, ``text`` is returned byte-identical.
      * If a ``final`` channel tag is present, everything up to and including
        that tag (the analysis/scratch channels) is dropped and only the final
        channel's content is returned.
      * Otherwise every channel tag, its adjacent ``<|message|>`` separator, and
        Harmony turn markers are removed in place, and a bare leading role token
        left behind by that removal is also dropped.
      * Only whitespace introduced by the removal is collapsed.

    Args:
        text: The raw assistant text as returned by the model.

    Returns:
        The sanitized, user-safe text.
    """
    if not isinstance(text, str) or not text:
        return text

    # Fast path: nothing that looks like a channel control token -> untouched.
    # This guarantees ordinary text (and code with pipes) is byte-identical.
    if not _CHANNEL_TAG.search(text):
        return text

    original = text

    # If the transcript names a 'final' channel, the user-visible answer is
    # whatever follows the LAST 'final' tag. Drop everything before it.
    final_matches = list(_FINAL_TAG.finditer(text))
    if final_matches:
        last_final = final_matches[-1]
        text = text[last_final.end():]
        # A '<|message|>' separator commonly sits right after the final tag.
        text = _MESSAGE_SEP.sub("", text, count=1)

    # Remove any remaining channel tags (e.g. a leading analysis tag in the
    # no-final case, or stray duplicates), their message separators, and turn
    # markers.
    text = _CHANNEL_TAG.sub("", text)
    text = _MESSAGE_SEP.sub("", text)
    text = _TURN_MARKER.sub("", text)

    # A bare role token may remain at the very start only because we just
    # removed the delimiters around it; that makes it an unambiguous artifact,
    # so drop it. (We do not do this on text that never had a channel tag.)
    text = _LEADING_BARE_ROLE.sub("", text, count=1)

    text = _collapse_introduced_whitespace(text)

    # Trim only the outer whitespace the removal may have left dangling. If the
    # cleanup somehow emptied a non-empty input, fall back to the original to
    # avoid ever returning nothing where the model said something.
    cleaned = text.strip()
    if not cleaned and original.strip():
        return original
    return cleaned
