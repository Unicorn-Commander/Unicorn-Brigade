"""Tests for the Gemma/Harmony channel-artifact sanitizer.

Lives in app/tests/ because pytest.ini sets `testpaths = tests app/tests` — these
14 tests were never collected by CI while the file sat in app/llm/.

Run with:
    python3 -m pytest app/tests/test_gemma_sanitize.py -v
"""

from app.llm.gemma_sanitize import strip_channel_artifacts

# --- Required cases ---------------------------------------------------------

def test_bare_channel_tag_is_cleaned():
    """A stray ``<channel|>`` token is removed and surrounding text kept."""
    out = strip_channel_artifacts("Hello there<channel|> world")
    assert "channel" not in out
    assert "<" not in out and "|>" not in out
    assert out == "Hello there world"


def test_pipe_first_channel_tag_is_cleaned():
    """The ``<|channel|>`` delimiter shape is also removed."""
    out = strip_channel_artifacts("Answer:<|channel|> 42")
    assert "channel" not in out
    assert out == "Answer: 42"


def test_analysis_then_final_keeps_only_final_content():
    """Harmony analysis+final transcript collapses to just the final answer."""
    raw = (
        "<|channel|>analysis<|message|>The user greets me, so I should greet "
        "back and be friendly.<|channel|>final<|message|>Hello! How can I help "
        "you today?"
    )
    out = strip_channel_artifacts(raw)
    assert out == "Hello! How can I help you today?"
    # The analysis/scratch content must not leak through.
    assert "analysis" not in out.lower()
    assert "greets me" not in out
    assert "channel" not in out.lower()
    assert "message" not in out.lower()


def test_plain_text_is_byte_identical():
    """Text with no artifacts is returned exactly as given."""
    plain = "Here is a normal answer.\nIt spans two lines, with  no  tags."
    assert strip_channel_artifacts(plain) is plain or \
        strip_channel_artifacts(plain) == plain
    # Strong form: identical content, including the double spaces.
    assert strip_channel_artifacts(plain) == plain


def test_code_block_with_pipe_is_not_mangled():
    """A fenced code block containing pipes must pass through untouched."""
    code = (
        "Here is some code:\n"
        "```python\n"
        "result = a | b  # bitwise or\n"
        "df = df[df.col | other.col]\n"
        "flags = READ | WRITE | EXECUTE\n"
        "```\n"
        "And a shell pipe: `cat file | grep foo | wc -l`\n"
        "Type union: def f(x: int | str) -> bool | None: ...\n"
    )
    assert strip_channel_artifacts(code) == code


# --- Extra conservative-behaviour cases -------------------------------------

def test_channel_with_role_inside_tag_is_cleaned():
    """The ``<channel|final|>`` shape (role inside the delimiters)."""
    out = strip_channel_artifacts("<channel|final|>The deploy is green.")
    assert out == "The deploy is green."
    assert "channel" not in out.lower()


def test_only_analysis_channel_drops_leading_role_token():
    """With no final tag, a leading bare role token left behind is removed."""
    raw = "<|channel|>analysis<|message|>Some user-facing sentence."
    out = strip_channel_artifacts(raw)
    assert out == "Some user-facing sentence."
    assert not out.lower().startswith("analysis")


def test_word_final_in_normal_prose_is_preserved():
    """A legitimate sentence beginning with 'Final' must not be stripped."""
    prose = "Final answer: the build passes all 226 tests."
    assert strip_channel_artifacts(prose) == prose


def test_word_analysis_in_normal_prose_is_preserved():
    """'analysis' as ordinary content (no channel tag) is untouched."""
    prose = "analysis of the logs shows a 524 timeout pattern."
    assert strip_channel_artifacts(prose) == prose


def test_empty_string_returns_empty():
    assert strip_channel_artifacts("") == ""


def test_non_string_passthrough():
    assert strip_channel_artifacts(None) is None


def test_multiple_channel_tags_all_removed():
    raw = "<|channel|>analysis<|message|>thinking<|channel|>final<|message|>Done."
    out = strip_channel_artifacts(raw)
    assert out == "Done."


def test_final_content_preserves_internal_structure():
    """Newlines/markdown inside the final channel survive intact."""
    raw = (
        "<|channel|>analysis<|message|>plan it<|channel|>final<|message|>"
        "Step 1: do this\nStep 2: do that\n\n- bullet a\n- bullet b"
    )
    out = strip_channel_artifacts(raw)
    assert out == "Step 1: do this\nStep 2: do that\n\n- bullet a\n- bullet b"


def test_uppercase_channel_token_is_cleaned():
    """Match is case-insensitive for the control word."""
    out = strip_channel_artifacts("<|CHANNEL|>final<|MESSAGE|>Ready.")
    assert out == "Ready."
