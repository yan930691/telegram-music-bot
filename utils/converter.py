# -*- coding: utf-8 -*-
# Helper to auto-convert Zawgyi text to Unicode Myanmar using the vendored Rabbit converter.

import re

from utils.rabbit import Rabbit

# Code points that only ever appear in Zawgyi encoded text (real Unicode text
# rarely uses this block). Presence of any of these is a strong Zawgyi signal.
# Code points 0x1060-0x109F only ever appear in Zawgyi encoded text
# (Zawgyi maps normal Unicode letters onto these block codepoints).
_ZAWGYI_ONLY_RX = re.compile(r"[\u1060-\u109F]")

# Zawgyi places the pre-base vowel U+1031 before the consonant cluster
# in the order it is typed; Unicode keeps it after the base consonant.
_ZAWGYI_PRE_VOWEL_RX = re.compile(r"[\u1031][\u1000-\u1021]")


def is_zawgyi(text):
    """Return True if text is probably encoded in Zawgyi."""
    if not text:
        return False
    if _ZAWGYI_ONLY_RX.search(text):
        return True
    if re.search(r"[\u1000-\u1021]\u1039", text):
        return False
    if _ZAWGYI_PRE_VOWEL_RX.search(text):
        return True
    return False


def zawgyi_to_unicode(text):
    """Convert Zawgyi text to Unicode. A no-op for non-Zawgyi input."""
    if not text:
        return text
    if not is_zawgyi(text):
        return text
    return Rabbit.zg2uni(text)


def unicode_to_zawgyi(text):
    """Convert Unicode text to Zawgyi (rarely needed; kept for completeness)."""
    if not text:
        return text
    return Rabbit.uni2zg(text)


def normalize_myanmar(text):
    """Best-effort normalize: ensure stored text is Unicode, not Zawgyi."""
    return zawgyi_to_unicode(text)