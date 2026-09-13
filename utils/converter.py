# -*- coding: utf-8 -*-
# Helper to auto-convert Zawgyi text to Unicode Myanmar using the vendored Rabbit converter.

import re

from utils.rabbit import Rabbit

# Code points that only ever appear in Zawgyi encoded text (real Unicode text
# rarely uses this block). Presence of any of these is a strong Zawgyi signal.
# Code points 0x1060-0x109F only ever appear in Zawgyi encoded text
# (Zawgyi maps normal Unicode letters onto these block codepoints).
_ZAWGYI_ONLY_RX = re.compile(r"[\u1060-\u109F]")

# Zawgyi ya-pin (ျ) is stored as U+103A immediately before the base consonant
# (e.g. "ျမန္မာ"), and is NOT preceded by a base consonant itself. In Unicode
# the equivalent codepoint is the asat (်) and is always typed AFTER a vowel
# or medial that follows a base consonant, so a genuine asat is preceded by a
# consonant character.
_ZAWGYI_YAPIN_RX = re.compile(r"(?<![\u1000-\u1021])[\u103A][\u1000-\u1021]")

# Zawgyi asat (်) is stored as U+1039 (virama). In genuine Unicode a virama
# is only used for stacking/kinzi and is ALWAYS followed by a base consonant,
# so any U+1039 not followed by one is a Zawgyi signature.
_ZAWGYI_ASAT_RX = re.compile(r"[\u1000-\u1021]\u1039(?![\u1000-\u1021])")

# Zawgyi writes the pre-base vowel U+1031 at the START of the consonant
# cluster in typed order (e.g. "ေ" + consonant). In Unicode the U+1031 is
# stored AFTER the base consonant and any medials, so a U+1031 that begins a
# cluster (not preceded by a base consonant or medial) is a Zawgyi signature.
_ZAWGYI_PRE_VOWEL_RX = re.compile(r"(?<![\u1000-\u1021\u103B-\u103E])\u1031(?:[\u103B-\u103E]*)[\u1000-\u1021]")

# Unicode signals.
_UNICODE_ASAT_END_RX = re.compile(r"[\u1000-\u1021]\u103A(?![\u1000-\u1021])")
_UNICODE_KINZI_RX = re.compile(r"\u1004\u103A\u1039")


def is_zawgyi(text):
    """Return True if text is probably encoded in Zawgyi."""
    if not text:
        return False
    if _ZAWGYI_ONLY_RX.search(text):
        return True
    zaw = 0
    uni = 0
    if _ZAWGYI_YAPIN_RX.search(text):
        zaw += 2
    if _ZAWGYI_ASAT_RX.search(text):
        zaw += 2
    if _ZAWGYI_PRE_VOWEL_RX.search(text):
        zaw += 2
    if _UNICODE_ASAT_END_RX.search(text):
        uni += 2
    if _UNICODE_KINZI_RX.search(text):
        uni += 2
    return zaw > uni


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