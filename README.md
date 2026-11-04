# nlp_base

Base NLP libraries and dictionaries of [aot.ru](http://aot.ru) (formerly `morph_dict`), shared by
[RML](https://github.com/sokirko74/aot) and [DDC](https://github.com/sokirko74/ddc3):

- `common/` — common utilities (`utilit.h`, single-byte encodings, utf8, ...);
- morphology: `agramtab/`, `morph_wizard/`, `lemmatizer_base_lib/`, `morph_gen/`, ...
  and the morphological dictionaries in `data/{Russian,English,German}`;
- graphematics: `graphan/` (`GraphanLib`, `GraphmatThick`) with the dictionaries
  `data/GraphAn`, `data/Obor`, `data/GerObor`, `data/EngObor`;
- structural dictionaries (Ross): `dicts/StructDictLib`, `dicts/StructDictLoader`.

The library is used as a git submodule named `nlp_base` (includes are written as
`#include "nlp_base/common/utilit.h"`, so the parent of the submodule must be in the include path).
The code must stay compilable under Windows (RML) and Linux.

This repository contains sources of Aot.ru morphological dictionaries (Russian, English and German) and
C++ sources for manipulating these dictionaries (editing, creating binary versions). Russian morphological dictionary is based on  
[Zaliznyak's grammar dictionary](https://ru.wikipedia.org/wiki/%D0%93%D1%80%D0%B0%D0%BC%D0%BC%D0%B0%D1%82%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%B8%D0%B9_%D1%81%D0%BB%D0%BE%D0%B2%D0%B0%D1%80%D1%8C_%D1%80%D1%83%D1%81%D1%81%D0%BA%D0%BE%D0%B3%D0%BE_%D1%8F%D0%B7%D1%8B%D0%BA%D0%B0_%D0%90._%D0%90._%D0%97%D0%B0%D0%BB%D0%B8%D0%B7%D0%BD%D1%8F%D0%BA%D0%B0)
