"""Unit tests for tools.lib.release.extract_whats_new."""

import pytest

from tools.lib.release import extract_whats_new


def test_extracts_section_between_headers():
    body = (
        "## Summary\n\nsome stuff\n\n"
        "## What's new\n\n"
        "Updated INSP sitrep through report 011.\n\n"
        "## Contributor checklist\n\n- [x] foo\n"
    )
    assert extract_whats_new(body) == "Updated INSP sitrep through report 011."


def test_extracts_when_section_is_last():
    body = "## Foo\n\nbar\n\n## What's new\n\nThe new stuff.\n"
    assert extract_whats_new(body) == "The new stuff."


def test_strips_html_comments_from_template():
    body = (
        "## What's new\n\n"
        "<!-- This section becomes the GitHub Release description. -->\n"
        "<!-- Write 1–3 sentences. -->\n"
        "Refreshed cross-border data.\n\n"
        "## Next\n"
    )
    assert extract_whats_new(body) == "Refreshed cross-border data."


def test_handles_crlf_line_endings():
    body = "## What's new\r\n\r\nLine one.\r\n\r\n## End\r\n"
    assert extract_whats_new(body) == "Line one."


def test_raises_when_section_missing():
    with pytest.raises(ValueError, match="What's new"):
        extract_whats_new("## Summary\n\nno relevant section\n")


def test_raises_when_section_empty():
    body = "## What's new\n\n<!-- only a comment -->\n\n## End\n"
    with pytest.raises(ValueError, match="empty"):
        extract_whats_new(body)


def test_preserves_multiline_content():
    body = (
        "## What's new\n\n"
        "Line one.\n\n"
        "Line two with **bold** and a [link](https://example.com).\n\n"
        "## Next\n"
    )
    expected = (
        "Line one.\n\n"
        "Line two with **bold** and a [link](https://example.com)."
    )
    assert extract_whats_new(body) == expected
