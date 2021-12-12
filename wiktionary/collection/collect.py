import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import sys
from typing import Any
import unicodedata
from warnings import warn

try:
    import anyascii
except ModuleNotFoundError:
    sys.exit('Please install AnyAscii ("pip install anyascii") to run the script')


MAX_NON_COMBINING_LENGTH = 20

LOGGING_PERIOD = 10000

IPA = 'ipa'
ROMANIZATION = 'roman'
ASCII = 'ascii'

LATIN_DATA = 'data/latin'

TAB = '\t'

NORMALIZATION_FORM = 'NFD'
NORMALIZATION_REPLACEMENTS: list[tuple[re.Pattern, str]] = [
    # left-to-right and right-to-left marks when not in the middle of the word:
    (re.compile(r'^[\u200e\u200f]+'), ''),
    (re.compile(r'[\u200e\u200f]+$'), ''),

    (re.compile(r'\s+'), ' '),
]

LATIN_PATTERN = re.compile(r'[a-z -]', flags=re.IGNORECASE)
NON_ASCII_PATTERN = re.compile(r'[^a-z ]', flags=re.IGNORECASE)
CLIPPEDLIKE_IPA_PATTERN = re.compile(r'^[/[]-|-[]/]$')

EXTRA_WORD_NORMALIZATION_RULES: dict[str, list[tuple[re.Pattern, str]]] = {
    'ja': [
        (re.compile(r' ?\([^)]*\)'), ''),
    ],
}

SEARCH_PATTERN_DELIMITER = '/'

Entry = tuple[str, str, str]  # language, word, IPA/romanization
Storage = dict[str, defaultdict[str, set[tuple[str, str]]]]  # category -> language -> word + IPA/romanization
LanguageSet = set[str]

SearchPattern = str
SearchPatterns = tuple[
    SearchPattern,  # language
    SearchPattern,  # word
    SearchPattern,  # IPA/romanization
    list[tuple[SearchPattern, str]],  # equality conditions
]

Bindings = dict[str, int]

SearchResults = list[tuple[str, Bindings]]
ConsolidatedResult = tuple[str, ...]
ConsolidatedResults = list[ConsolidatedResult]

IPA_PATTERNS: list[SearchPatterns] = [
    ('lang_code', 'word', 'sounds/N/ipa', []),
    ('lang_code', 'forms/N/form', 'forms/N/ipa', []),
]

ROMANIZATION_PATTERNS: list[SearchPatterns] = [
    ('lang_code', 'forms/N/form', 'forms/N/roman', []),
    ('lang_code', 'form_of/N/word', 'form_of/N/roman', []),
    ('lang_code', 'abbreviations/N/word', 'abbreviations/N/roman', []),
    ('lang_code', 'synonyms/N/word', 'synonyms/N/roman', []),
    ('lang_code', 'antonyms/N/word', 'antonyms/N/roman', []),
    ('lang_code', 'hyponyms/N/word', 'hyponyms/N/roman', []),
    ('lang_code', 'hypernyms/N/word', 'hypernyms/N/roman', []),
    ('lang_code', 'coordinate_terms/N/word', 'coordinate_terms/N/roman', []),
    ('lang_code', 'meronyms/N/word', 'meronyms/N/roman', []),
    ('lang_code', 'holonyms/N/word', 'holonyms/N/roman', []),
    ('lang_code', 'troponyms/N/word', 'troponyms/N/roman', []),
    ('lang_code', 'derived/N/word', 'derived/N/roman', []),
    ('lang_code', 'related/N/word', 'related/N/roman', []),
    ('lang_code', 'proverbs/N/word', 'proverbs/N/roman', []),
    ('lang_code', 'senses/N/examples/M/text', 'senses/N/examples/M/roman', []),
    ('lang_code', 'senses/N/alt_of/M/word', 'word', [('senses/N/tags/T', 'romanization')]),
    ('lang_code', 'word', 'forms/N/form', [('forms/N/tags/T', 'romanization')]),
    ('lang_code', 'forms/A/form', 'forms/B/form', [('forms/A/tags/C', 'canonical'),
                                                   ('forms/B/tags/D', 'romanization')]),
    ('translations/N/code', 'translations/N/word', 'translations/N/roman', []),
]


def is_variable_name(text: str) -> bool:
    return len(text) == 1 and text.isupper()


def search_values(pattern: SearchPattern, data: Any, *, silently_ignore_none: bool = False) -> SearchResults:
    def search_recursively(path: list[str], node: Any, bindings: Bindings) -> SearchResults:
        if path:
            key, path_tail = path[0], path[1:]
            if is_variable_name(key):
                assert key not in bindings
                if isinstance(node, list):
                    return [result
                            for index, item in enumerate(node)
                            for result in search_recursively(path_tail, item, {**bindings, key: index})]
                else:
                    return []
            else:
                if isinstance(node, dict) and key in node:
                    return search_recursively(path_tail, node[key], bindings)
                else:
                    return []
        else:
            if not isinstance(node, str):
                if not (silently_ignore_none and node is None):
                    warn(f'Ignoring value which is not a string: {node}')
                return []
            return [(node, bindings)]

    return search_recursively(pattern.split(SEARCH_PATTERN_DELIMITER), data, {})


def consolidate_results(*results: SearchResults) -> ConsolidatedResults:
    if not all(results):
        return []
    ordered_variables_t = list[str]
    ordered_values_t = tuple[int, ...]
    index_t = defaultdict[ordered_values_t, SearchResults]

    def extract_values(bindings: Bindings, variables: ordered_variables_t) -> ordered_values_t:
        return tuple(bindings[variable] for variable in variables)

    indices: list[index_t] = []
    intersections: list[ordered_variables_t] = []
    cumulative: set[str] = set()
    for position_results, position_variables in zip(results, (set(bindings.keys()) for (_, bindings), *_ in results)):
        intersecting_variables = sorted(cumulative.intersection(position_variables))
        cumulative.update(position_variables)
        index: index_t = defaultdict(list)
        for result in position_results:
            _, bindings = result
            values = extract_values(bindings, intersecting_variables)
            index[values].append(result)
        indices.append(index)
        intersections.append(intersecting_variables)

    consolidated: ConsolidatedResults = []

    def consolidate_recursively(position: int, current: ConsolidatedResult, bindings: Bindings) -> None:
        if position == len(results):
            consolidated.append(current)
        else:
            for item, position_bindings in indices[position][extract_values(bindings, intersections[position])]:
                consolidate_recursively(position + 1, current + (item,), {**bindings, **position_bindings})

    consolidate_recursively(0, (), {})
    return consolidated


def normalize(text: str) -> str:
    text = unicodedata.normalize(NORMALIZATION_FORM, text)
    for pattern, replacement in NORMALIZATION_REPLACEMENTS:
        text = re.sub(pattern, replacement, text)
    return text.strip()


def extra_normalize_word(word: str, language: str) -> str:
    for pattern, replacement in EXTRA_WORD_NORMALIZATION_RULES.get(language, []):
        word = re.sub(pattern, replacement, word)
    return word


def count_non_combining_characters(text: str) -> int:
    return sum(1 for character in text if not unicodedata.combining(character))


def is_valid_entry(entry: Entry, is_ipa: bool) -> bool:
    language, word, romanization = entry
    return bool(language and word and romanization) and (is_ipa or (
        all(count_non_combining_characters(text) <= MAX_NON_COMBINING_LENGTH for text in [word, romanization])
        and not all(unicodedata.combining(character) or re.fullmatch(LATIN_PATTERN, character) for character in word)
    ))


def search_triples(patterns: SearchPatterns, data: Any, is_ipa: bool) -> list[Entry]:
    language_pattern, word_pattern, romanization_pattern, conditions = patterns
    condition_results = [[(value, bindings) for value, bindings in search_values(pattern, data) if value == required]
                         for pattern, required in conditions]
    return [entry
            for *_, language, word, romanization in consolidate_results(
                *condition_results,
                search_values(language_pattern, data,      # Language code is None when data is given
                              silently_ignore_none=True),  # for a group of languages (e.g., "Mayan")
                search_values(word_pattern, data),
                search_values(romanization_pattern, data),
            )
            if is_valid_entry(
                entry := (language, extra_normalize_word(normalize(word), language), normalize(romanization)),
                is_ipa,
            )]


def is_clippedlike_ipa(text: str) -> bool:
    return bool(re.search(CLIPPEDLIKE_IPA_PATTERN, text))


def romanization_to_ascii(romanization: str) -> str:
    return re.sub(NON_ASCII_PATTERN, '', anyascii.anyascii(romanization).lower())


def add_entry(storage: Storage, category: str, entry: Entry) -> None:
    language, word, romanization = entry
    language_storage = storage[category][language]
    language_entry = (word, romanization)
    if language_entry not in language_storage:
        language_storage.add(language_entry)


def log(lines_processed: int) -> None:
    if lines_processed % LOGGING_PERIOD == 0:
        print(f'Processed {format(lines_processed, ",d")} lines')


def load_latin() -> LanguageSet:
    with open(Path(__file__).parent / LATIN_DATA, 'r') as latin:
        return set(line for unstripped in latin if (line := unstripped.rstrip('\n')))


def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=Path, help='Path to a Wiktextract dump')
    parser.add_argument('output', type=Path, help='Path to the output directory')
    arguments = parser.parse_args()

    output_directory: Path = arguments.output
    storage: Storage = {}

    categories = IPA, ROMANIZATION, ASCII

    for category in categories:
        directory = output_directory / category
        if not directory.exists():
            directory.mkdir()
        storage[category] = defaultdict(set)

    latin = load_latin()

    with open(arguments.input, 'r') as lines:
        for line_index, unstripped in enumerate(lines):
            data = json.loads(unstripped.rstrip('\n'))
            for patterns in IPA_PATTERNS:
                for index, (language, word, ipa) in enumerate(search_triples(patterns, data, True)):
                    if not (index > 0 and is_clippedlike_ipa(ipa)):
                        add_entry(storage, IPA, (language, word, ipa))
            for patterns in ROMANIZATION_PATTERNS:
                for index, (language, word, romanization) in enumerate(search_triples(patterns, data, False)):
                    if language not in latin:  # This is to prevent junk from being collected for such languages
                        add_entry(storage, ROMANIZATION, (language, word, romanization))
                        add_entry(storage, ASCII, (language, word, romanization_to_ascii(romanization)))
            log(line_index + 1)

    for category in categories:
        for language, entries in storage[category].items():
            print(f'Dumping {category}/{language}...')
            with open(output_directory / category / language, 'w') as output_data:
                for word, romanization in sorted(entries):
                    output_data.write(f'{word}{TAB}{romanization}\n')

    print('Done')


run()
