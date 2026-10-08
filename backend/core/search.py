"""Reusable, typo-tolerant text/location search helpers.

The hotel catalogue accepts free-text searches such as ``banglore`` and must
still resolve them to the admin-managed destination "Bangalore". Rather than
special-casing any city, these helpers normalise both the query and the data
that is already in the database and match them tolerant of case, whitespace,
punctuation and small spelling mistakes.

Nothing here knows about a particular place: the candidate values always come
from the caller (i.e. rows the administrator created).
"""

import re
from difflib import SequenceMatcher

#: Collapse runs of whitespace into a single space.
_WHITESPACE_RE = re.compile(r'\s+')
#: Keep letters/digits/spaces only — drops punctuation so "St. John's" and
#: "st johns" compare equal.
_NON_WORD_RE = re.compile(r'[^0-9a-z\s]+')

#: Similarity at/above which two words are treated as the same (typo tolerance).
FUZZY_THRESHOLD = 0.8
#: Only words this long are compared fuzzily; short words must match outright.
MIN_FUZZY_LENGTH = 4
#: Minimum length before substring containment counts, to avoid noise.
MIN_SUBSTRING_LENGTH = 3


def normalize_text(value):
    """Trim, lowercase, strip punctuation and collapse repeated spaces."""
    if value is None:
        return ''
    text = str(value).strip().lower()
    text = _NON_WORD_RE.sub(' ', text)
    return _WHITESPACE_RE.sub(' ', text).strip()


def tokens(value):
    """Normalised, non-empty words of ``value``."""
    normalized = normalize_text(value)
    return normalized.split(' ') if normalized else []


def similarity(a, b):
    """Ratio between two normalised strings, in the 0..1 range."""
    a, b = normalize_text(a), normalize_text(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def words_match(query_word, candidate_word):
    """True when a single query word matches a single candidate word.

    Exact equality, substring containment (either direction) and, for words of
    a reasonable length, fuzzy similarity (``banglore`` → ``bangalore``).
    """
    if not query_word or not candidate_word:
        return False
    if query_word == candidate_word:
        return True
    if len(query_word) >= MIN_SUBSTRING_LENGTH and len(candidate_word) >= MIN_SUBSTRING_LENGTH:
        if query_word in candidate_word or candidate_word in query_word:
            return True
    if len(query_word) >= MIN_FUZZY_LENGTH and len(candidate_word) >= MIN_FUZZY_LENGTH:
        return similarity(query_word, candidate_word) >= FUZZY_THRESHOLD
    return False


def term_matches(query, candidate):
    """True when ``candidate`` (a city, country, name...) satisfies ``query``.

    A multi-word query must have *every* word satisfied by some word of the
    candidate, so "bangalore india" matches "Bangalore, India" but "bali" does
    not match "Bangladesh".
    """
    query, candidate = normalize_text(query), normalize_text(candidate)
    if not query or not candidate:
        return False
    if query == candidate or query in candidate or candidate in query:
        return True
    candidate_words = tokens(candidate)
    return bool(candidate_words) and all(
        any(words_match(word, candidate_word) for candidate_word in candidate_words)
        for word in tokens(query)
    )


def _field(source, name):
    if isinstance(source, dict):
        return source.get(name) or ''
    return getattr(source, name, '') or ''


#: Fields searched tolerantly (place names + hotel name).
LOCATION_FIELDS = ('name', 'city', 'state', 'country', 'address')
#: Free-text fields searched by plain normalised substring only.
DESCRIPTION_FIELDS = ('short_description', 'description')


def hotel_matches_search(hotel, query):
    """True when ``hotel`` should be returned for the free-text ``query``.

    ``hotel`` may be a model instance or a ``values()`` dict. Matching covers
    city, state, country and hotel name (with typo tolerance) plus the descriptions
    (plainly), never an exact-string requirement on any single field.

    Multi-word queries match across fields as well as within one: "Bangalore
    India" is satisfied by a hotel whose city is Bangalore *and* country India.
    """
    normalized = normalize_text(query)
    if not normalized:
        return True

    # Every word of the query must be satisfied by some word across the location
    # fields. This is what lets "banglore" find "Bangalore" and lets a multi-word
    # query span city + country without a hard-coded place list.
    combined = ' '.join(_field(hotel, field) for field in LOCATION_FIELDS)
    candidate_words = tokens(combined)
    if candidate_words and all(
        any(words_match(word, candidate_word) for candidate_word in candidate_words)
        for word in tokens(query)
    ):
        return True

    # Phrase containment inside a single field (e.g. "city central").
    if any(term_matches(query, _field(hotel, field)) for field in LOCATION_FIELDS):
        return True

    return any(normalized in normalize_text(_field(hotel, field)) for field in DESCRIPTION_FIELDS)
