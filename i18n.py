"""Local UI translations. User text and form values are never translated.

This module provides single-pass phrase translation and streaming HTML localization
from the base Traditional Chinese (``zh-Hant``) interface into Simplified Chinese
(``zh-Hans``) or English (``en``), while preserving user-entered text and form inputs.
"""
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import json
import re

# Load translation dictionary and compile longest-first alternation regex for single-pass matching
CATALOG = json.loads(Path(__file__).with_name('translations.json').read_text(encoding='utf-8'))
PATTERN = re.compile('|'.join(re.escape(key) for key in sorted(CATALOG, key=len, reverse=True)))


def translate(text, language):
    """Translate known UI phrases in a plain text string into the target language.

    Performs a single-pass regular expression substitution sorted by descending
    phrase length so longer phrases match first and replaced segments are never
    double-translated.

    Args:
        text (str): Source text in Traditional Chinese (``zh-Hant``).
        language (str): Target locale code (``'zh-Hant'``, ``'zh-Hans'``, or ``'en'``).

    Returns:
        str: Translated text in the requested language, or the original ``text``
        unchanged when ``language == 'zh-Hant'``.
    """
    if language == 'zh-Hant':
        return text
    index = 0 if language == 'zh-Hans' else 1
    # One pass avoids translating a replacement a second time.
    return PATTERN.sub(lambda m: CATALOG[m.group()][index], text)


class Localizer(HTMLParser):
    """Streaming HTML parser that translates static UI text nodes and accessibility attributes.

    Skips translating contents inside ``<script>``, ``<style>``, ``<textarea>``, and
    any element marked with the ``data-user`` attribute to protect user-generated data.

    Attributes:
        language (str): Target locale code (``'zh-Hans'`` or ``'en'``).
        output (list[str]): Accumulated HTML fragments produced during parsing.
        stack (list[tuple[str, bool]]): Active element stack tracking ``(tag_name, skip_flag)``.
    """

    def __init__(self, language):
        """Initialize the HTML localizer for a target language.

        Args:
            language (str): Target locale code (e.g., ``'zh-Hans'`` or ``'en'``).
        """
        super().__init__(convert_charrefs=False)
        self.language = language
        self.output = []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        """Process an opening HTML tag, updating skip state and translatable attributes.

        Translates ``aria-label`` and ``placeholder`` attribute values unless inside a
        skipped subtree, and updates the ``lang`` attribute on the root ``<html>`` tag.

        Args:
            tag (str): Lowercase HTML tag name.
            attrs (list[tuple[str, str | None]]): Sequence of ``(attribute, value)`` pairs.
        """
        # Inherit skip state from ancestor tags or activate it on code/textarea/data-user elements
        skip = any(v for _, v in self.stack) or tag in ('script', 'style', 'textarea') or any(k == 'data-user' for k, v in attrs)
        # Void HTML elements have no closing tag, so only push container elements onto the stack
        if tag not in ('input', 'meta', 'link', 'br', 'hr', 'img'):
            self.stack.append((tag, skip))
        result = []
        for key, value in attrs:
            if tag == 'html' and key == 'lang':
                value = self.language
            # Translate user-facing accessibility/placeholder attributes outside protected subtrees
            if value is not None and key in ('aria-label', 'placeholder') and not skip:
                value = translate(value, self.language)
            result.append(key if value is None else key + '="' + escape(value, quote=True) + '"')
        self.output.append('<' + tag + (' ' + ' '.join(result) if result else '') + '>')

    def handle_startendtag(self, tag, attrs):
        """Process a self-closing XHTML-style tag (e.g., ``<br/>`` or ``<input/>``).

        Args:
            tag (str): Lowercase HTML tag name.
            attrs (list[tuple[str, str | None]]): Sequence of ``(attribute, value)`` pairs.
        """
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()
        self.output[-1] = self.output[-1][:-1] + '/>'

    def handle_endtag(self, tag):
        """Process a closing HTML tag and unwind the active element stack.

        Args:
            tag (str): Lowercase HTML tag name being closed.
        """
        # Unwind back to the matching opening tag (tolerates unclosed inner HTML tags)
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break
        self.output.append('</' + tag + '>')

    def handle_data(self, text):
        """Translate character data outside protected user-content or code tags.

        Also reformats Chinese year/month/day strings into slash-delimited numeric
        dates when localizing into English.

        Args:
            text (str): Raw text content encountered between HTML tags.
        """
        if not any(v for _, v in self.stack):
            text = translate(text, self.language)
            # Reformat Chinese date headings (e.g. "2026 年 11 月") into numeric slash notation for English
            if self.language == 'en':
                text = re.sub(r'(\d+) 年 (\d+) 月', r'\1 / \2', text)
                text = re.sub(r'(\d+) 月 (\d+) 日，', r'\1 / \2, ', text)
        self.output.append(text)

    def handle_entityref(self, name):
        """Preserve named HTML character entities (e.g., ``&nbsp;``) verbatim.

        Args:
            name (str): Entity reference name without leading ``&`` or trailing ``;``.
        """
        self.output.append('&' + name + ';')

    def handle_charref(self, name):
        """Preserve numeric HTML character references (e.g., ``&#39;``) verbatim.

        Args:
            name (str): Numeric or hexadecimal character reference body.
        """
        self.output.append('&#' + name + ';')

    def handle_decl(self, decl):
        """Preserve HTML declarations (e.g., ``<!DOCTYPE html>``) verbatim.

        Args:
            decl (str): Declaration content inside ``<!...>``.
        """
        self.output.append('<!' + decl + '>')


def localize_html(html, language):
    """Translate a complete HTML document string into the specified target language.

    Args:
        html (str): Rendered HTML page content in Traditional Chinese (``zh-Hant``).
        language (str): Target locale code (``'zh-Hant'``, ``'zh-Hans'``, or ``'en'``).

    Returns:
        str: Localized HTML output with static UI text and labels translated while
        leaving user-provided content intact.
    """
    if language == 'zh-Hant':
        return html
    parser = Localizer(language)
    parser.feed(html)
    return ''.join(parser.output)


def client_messages(language):
    """Build a dictionary mapping all catalog keys to their translated strings.

    Used to expose localized UI strings to client-side JavaScript scripts.

    Args:
        language (str): Target locale code (``'zh-Hant'``, ``'zh-Hans'``, or ``'en'``).

    Returns:
        dict[str, str]: Mapping from source Traditional Chinese phrase keys to
        localized strings in ``language``.
    """
    return {key: translate(key, language) for key in CATALOG}