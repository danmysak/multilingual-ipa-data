# Multilingual IPA and romanization data
The data is presented as tab-delimited text files (separately for IPA transcriptions and romanizations). Multiple transcriptions and/or romanizations for the same word are given as separate entries of the word. Fully duplicate entries are removed.

File names are [Wiktionary language codes](https://en.wiktionary.org/wiki/Wiktionary:List_of_languages).

Wiktionary data is collected partly using a [Wiktextract](https://github.com/tatuylonen/wiktextract) dump of the [English Wiktionary](https://en.wiktionary.org) and partly with a custom tool by [Tamila Krashtan](https://github.com/tamila-krashtan).

Wiktionary IPA transcriptions are provided exactly as found in the source.

[CMU Dictionary](https://github.com/Alexir/CMUdict) transcriptions were automatically converted into IPA (see [phoneme correspondences](cmudict/collection/data/phonemes)). Note that `AH` in unstressed syllables is represented as `ə`, and `ER` as `ɚ`. These are the only instances of vowel reduction applied.

All romanizations are normalized (using [AnyAscii](https://github.com/anyascii/anyascii)) to only contain lowercase Latin letters (a-z) and spaces.
