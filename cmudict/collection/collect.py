import argparse
from functools import partial
from itertools import product
from pathlib import Path
import re
from typing import Iterator, Pattern, Optional, Union

CMUDICT_COMMENT = ';;;'
CMUDICT_TAB = re.compile(r' {2,}')  # https://github.com/Alexir/CMUdict/pull/3
CMUDICT_PHONEME_DELIMITER = ' '
CMUDICT_IGNORE_UTF8_ERRORS = True  # https://github.com/Alexir/CMUdict/issues/5

PRIMARY_STRESS = 1
SECONDARY_STRESS = 2
NO_STRESS = 0

TAB = '\t'
COMMENT = '#'

DATA_DIRECTORY = 'data'
DATA_PHONEMES = 'phonemes'
DATA_ONSETS = 'onsets'
DATA_COMPOUNDS = 'compounds'

IPA_BRACKETS = '/', '/'
IPA_PRIMARY_STRESS = 'ˈ'
IPA_SECONDARY_STRESS = 'ˌ'

WORD_LABEL_PATTERN = re.compile(r'\(\d+\)$')

COMPOUND_PARTS_GUARANTEED_LENGTH = 5  # If both potential parts are at least this long, they deem to form a compound
COMPOUND_CONNECTOR = re.compile(r'^[^\w]*$')  # E.g., an empty string or a hyphen

Phonemes = dict[str, str]
Onsets = set[str]
Compounds = set[tuple[str, str]]
IPAWithStress = tuple[str, Optional[int]]
MaskedPhoneme = Union[str, bool]  # Either a consonant or (any) vowel with the given simplified stress value
WordData = tuple[str, list[IPAWithStress]]
WordDataIndex = dict[tuple[MaskedPhoneme, ...], list[str]]


def split_pair(delimiter: Union[str, Pattern], text: str) -> tuple[str, str]:
    sections = re.split(delimiter, text) if isinstance(delimiter, Pattern) else text.split(delimiter)
    if len(sections) != 2:
        raise ValueError(f'Expected "{text}" to be two values separated with "{delimiter}"')
    return sections[0], sections[1]


def get_lines(file: Path, *, comment_prefix: Optional[str] = None, ignore_errors: bool = False) -> Iterator[str]:
    with open(file, 'r', errors='ignore' if ignore_errors else 'strict') as lines:
        for unstripped in lines:
            if (line := unstripped.strip()) \
                    and (comment_prefix is None or not line.startswith(comment_prefix)):
                yield line


def get_data_path(file: str) -> Path:
    return Path(__file__).parent / DATA_DIRECTORY / file


def load_phonemes() -> Phonemes:
    return dict(map(partial(split_pair, TAB), get_lines(get_data_path(DATA_PHONEMES))))


def load_onsets() -> Onsets:
    return {line for line in get_lines(get_data_path(DATA_ONSETS), comment_prefix=COMMENT)}


def load_compounds() -> Compounds:
    return set(map(partial(split_pair, TAB), get_lines(get_data_path(DATA_COMPOUNDS), comment_prefix=COMMENT)))


def normalize_word(word: str) -> str:
    return re.sub(WORD_LABEL_PATTERN, '', word)


def cmu_phoneme_to_ipa_and_stress(cmu_phoneme: str, phonemes: Phonemes) -> IPAWithStress:
    suffix = cmu_phoneme[-1] if cmu_phoneme else ''
    cmu_core, stress = \
        (cmu_phoneme.removesuffix(suffix), int(suffix)) \
        if suffix.isdecimal() \
        else (cmu_phoneme, None)

    def look_up_ipa() -> str:
        if cmu_phoneme in phonemes:
            return phonemes[cmu_phoneme]
        elif cmu_core in phonemes:
            return phonemes[cmu_core]
        else:
            raise ValueError(f'Invalid CMUdict phoneme: "{cmu_phoneme}"')

    return look_up_ipa(), stress


def cmu_to_ipa_with_stress(cmu: str, phonemes: Phonemes) -> list[IPAWithStress]:
    return [cmu_phoneme_to_ipa_and_stress(cmu_phoneme, phonemes)
            for cmu_phoneme in cmu.split(CMUDICT_PHONEME_DELIMITER)]


def has_stress(stress: Optional[int]) -> bool:
    return stress in [PRIMARY_STRESS, SECONDARY_STRESS]


def mask_phoneme(phoneme: IPAWithStress) -> MaskedPhoneme:
    ipa, stress = phoneme
    return ipa if stress is None else has_stress(stress)


def build_word_data_index(data: list[WordData]) -> WordDataIndex:
    index: WordDataIndex = {}
    for word_data in data:
        word, ipa_with_stress = word_data
        key = tuple(map(mask_phoneme, ipa_with_stress))
        if key not in index:
            index[key] = []
        index[key].append(word)
    return index


def shift_values(values: list[int], shift: int) -> list[int]:
    return [value + shift for value in values]


def is_compound_of(word: str, left: str, right: str, compounds: Compounds) -> bool:
    if word.startswith(left) and word.endswith(right) and len(word) >= len(left) + len(right):
        connector = word.removeprefix(left).removesuffix(right)
        return (bool(re.fullmatch(COMPOUND_CONNECTOR, connector))
                and (connector  # E.g., all-out = all + out
                     or (left, right) in compounds
                     or min(len(left), len(right)) >= COMPOUND_PARTS_GUARANTEED_LENGTH))
    else:
        return False


# blacklist -> black_list
# homeownership -> home_owner_ship
# cat -> cat
def find_split_indices(ipa_with_stress: list[IPAWithStress], word: str,
                       word_data_index: WordDataIndex, compounds: Compounds) -> list[int]:
    stressed_indices = [index for index, (_, stress) in enumerate(ipa_with_stress) if has_stress(stress)]
    if len(stressed_indices) < 2:
        return []  # To eliminate cases like caseworker = casework + er
    masked = tuple(map(mask_phoneme, ipa_with_stress))
    indices_with_words: list[tuple[int, tuple[str, str]]] = []
    for index in range(stressed_indices[0] + 1, stressed_indices[-1] + 1):
        for left, right in product(word_data_index.get(masked[:index], []),
                                   word_data_index.get(masked[index:], [])):
            if is_compound_of(word, left, right, compounds):
                indices_with_words.append((index, (left, right)))
                break
    indices = [index for index, _ in indices_with_words]
    return (indices
            if all((metaindex == 0
                   or (find_split_indices(ipa_with_stress[:index], left, word_data_index, compounds)
                       == indices[:metaindex]))
                   and
                   (metaindex == len(indices) - 1
                    or (find_split_indices(ipa_with_stress[index:], right, word_data_index, compounds)
                        == shift_values(indices[metaindex + 1:], -index)))
                   for metaindex, (index, (left, right)) in enumerate(indices_with_words))
            else [])  # There are multiple ways to split the word into parts; it's safer not to assume anything


def stress_to_ipa(stress: int) -> str:
    if stress == PRIMARY_STRESS:
        return IPA_PRIMARY_STRESS
    elif stress == SECONDARY_STRESS:
        return IPA_SECONDARY_STRESS
    elif stress == NO_STRESS:
        return ''
    else:
        raise ValueError(f'Unexpected value for stress: {stress}')


def construct_ipa(ipa_with_stress: list[IPAWithStress], word: str,
                  onsets: Onsets, word_data_index: WordDataIndex, compounds: Compounds) -> str:
    vowel_count = sum(1 for ipa, stress in ipa_with_stress if stress is not None)
    stress_by_position = [NO_STRESS for _ in range(len(ipa_with_stress))]
    if vowel_count > 1:
        break_indices = [0] + find_split_indices(ipa_with_stress, word, word_data_index, compounds)
        for index, (_, stress) in enumerate(ipa_with_stress):
            if has_stress(stress):
                stress_position = index
                while stress_position not in break_indices \
                        and ''.join(ipa for ipa, _ in ipa_with_stress[stress_position - 1:index]) in onsets:
                    stress_position -= 1
                for start_index in break_indices:
                    if start_index >= stress_position:
                        break
                    if all(stress is None for _, stress in ipa_with_stress[start_index:stress_position]):
                        stress_position = start_index
                        break
                stress_by_position[stress_position] = stress
    left_bracket, right_bracket = IPA_BRACKETS
    return left_bracket \
        + ''.join(stress_to_ipa(stress) + ipa for stress, (ipa, _) in zip(stress_by_position, ipa_with_stress)) \
        + right_bracket


def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=Path, help='Path to the CMU Dictionary file')
    parser.add_argument('output', type=Path, help='Path to the output file')
    arguments = parser.parse_args()

    phonemes = load_phonemes()
    onsets = load_onsets()
    compounds = load_compounds()

    data: list[WordData] = []
    for line in get_lines(arguments.input, comment_prefix=CMUDICT_COMMENT, ignore_errors=CMUDICT_IGNORE_UTF8_ERRORS):
        word, transcription = split_pair(CMUDICT_TAB, line)
        data.append((normalize_word(word), cmu_to_ipa_with_stress(transcription, phonemes)))

    # The following is to detect compound words, which allows for better splitting into syllables
    word_data_index = build_word_data_index(data)

    entry_index: set[str] = set()
    with open(arguments.output, 'w') as output_data:
        for word, ipa_with_stress in data:
            entry = f'{word}{TAB}{construct_ipa(ipa_with_stress, word, onsets, word_data_index, compounds)}\n'
            if entry not in entry_index:
                entry_index.add(entry)
                output_data.write(entry)


run()
