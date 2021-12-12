# Multilingual IPA and romanization data
The data is presented as tab-delimited text files (separately for IPA transcriptions, romanizations, and ASCII romanizations). Multiple transcriptions and/or romanizations for the same word are given as separate entries of the word. Fully duplicate entries are removed.

File names are [Wiktionary language codes](https://en.wiktionary.org/wiki/Wiktionary:List_of_languages).

Wiktionary data is collected partly using a [Wiktextract](https://github.com/tatuylonen/wiktextract) dump of the [English Wiktionary](https://en.wiktionary.org) and partly with a custom tool by [Tamila Krashtan](https://github.com/tamila-krashtan). Clipped transcriptions (such as `/-səɹi/` in `/ˈdʒænəˌzeɹi/, /-səɹi/`) are skipped. The data is provided in a [canonically decomposed form](https://unicode.org/reports/tr15/#Norm_Forms).

ASCII romanizations are identical to the romanizations found in Wiktionary, except for being additionally normalized (using [AnyAscii](https://github.com/anyascii/anyascii)) to only contain lowercase Latin letters (a-z) and spaces.

Both ASCII and non-ASCII romanizations are currently filtered to be at most 20 (non-combining) characters long, which helps make the data much cleaner. This constraint applies to the words being romanized as well.

[CMU Dictionary](https://github.com/Alexir/CMUdict) transcriptions were converted into IPA with a straightforward[^1] algorithm: see [conversion chart](cmudict/collection/data/phonemes). Note that `AH` in unstressed syllables is represented as `ə`, and `ER` as `ɚ`. These are the only instances of vowel reduction applied.

[^1]: That is, apart from the syllabification bit.