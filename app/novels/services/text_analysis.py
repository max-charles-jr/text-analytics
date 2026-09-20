"""
NLTK-based tokenization and named-entity extraction for a novel's text.

Two outputs are produced, both required by the assignment:
  * token counts  -- how many times each token appears in the novel
  * entity counts -- how many times each named entity (person, place,
    organization, etc.) appears, using NLTK's built-in maxent chunker
"""
import logging
from collections import Counter

import nltk

logger = logging.getLogger(__name__)

# NLTK's data.find() resolves a bare package path (e.g. "tokenizers/punkt_tab")
# by pattern-matching against zip files it already knows about, which in
# NLTK 3.8.x can mis-resolve punkt_tab against an already-extracted punkt/
# directory. Checking for a concrete file inside each package sidesteps
# that ambiguity entirely.
_REQUIRED_NLTK_PACKAGES = [
    'punkt',
    'punkt_tab',
    'averaged_perceptron_tagger',
    'averaged_perceptron_tagger_eng',
    'maxent_ne_chunker',
    'maxent_ne_chunker_tab',
    'words',
]


def ensure_nltk_resources():
    """Make sure the NLTK corpora/models this module needs are available.

    The Dockerfile pre-downloads all of these at image-build time (see
    Dockerfile comments), so in the deployed container this is a fast
    no-op. It's kept here as a defensive fallback for local/dev runs where
    the image wasn't used. nltk.download() is idempotent -- it checks its
    own data directory and skips anything already present -- so calling it
    unconditionally on every request-free startup path is cheap and avoids
    relying on nltk.data.find()'s package-name pattern matching, which in
    NLTK 3.8.x can mis-resolve a package like "punkt_tab" against a
    similarly-named sibling package ("punkt") that was downloaded first.
    """
    for package in _REQUIRED_NLTK_PACKAGES:
        try:
            nltk.download(package, quiet=True)
        except Exception:
            logger.exception("Failed to ensure NLTK resource: %s", package)
            raise


def tokenize_with_counts(text):
    """Return a Counter of token -> occurrence count for the novel text.

    Tokens are lower-cased word tokens only (punctuation tokens are
    dropped) so that "The" and "the" are counted together, matching the
    conventional definition of word frequency used in text analytics.
    """
    tokens = nltk.word_tokenize(text)
    words = [t.lower() for t in tokens if any(ch.isalnum() for ch in t)]
    return Counter(words)


def _extract_entities_from_chunk(tree):
    entities = []
    for subtree in tree:
        if hasattr(subtree, 'label'):
            entity_text = ' '.join(leaf[0] for leaf in subtree.leaves())
            entities.append((entity_text, subtree.label()))
    return entities


def named_entities_with_counts(text, max_sentences=None):
    """Return a Counter of "Entity Text (LABEL)" -> occurrence count.

    NLTK's ne_chunk operates sentence-by-sentence on POS-tagged tokens.
    `max_sentences` can cap analysis for very long novels if runtime needs
    to be bounded; by default the whole novel is analyzed.
    """
    sentences = nltk.sent_tokenize(text)
    if max_sentences:
        sentences = sentences[:max_sentences]

    counts = Counter()
    for sentence in sentences:
        tokens = nltk.word_tokenize(sentence)
        tagged = nltk.pos_tag(tokens)
        tree = nltk.ne_chunk(tagged)
        for entity_text, label in _extract_entities_from_chunk(tree):
            counts[f"{entity_text} ({label})"] += 1
    return counts
