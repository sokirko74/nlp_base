"""
Marks the obscene words of aot.ru by the type grammem `obsc` (обсц): the lemmas equal to the titles of the obscene
articles of Wiktionary (all meanings have the mark `{{обсц.|ru}}`, see `is_obscene` in `src/utils/wiki.py`).
The type grammems of a lemma are a gramcode of the gramtab without a part of speech (`MH`: `inanim`), a code for the
type grammems with `obsc` is added to the gramtab if there is none (`inanim,obsc`).
The result should be saved by `slf_convert --to-mrd` with an empty slf file.
"""
import argparse
import itertools
import json
import string
from collections import Counter

from src.utils.wiki import is_obscene

OBSCENE = "obsc"


def norm(s: str) -> str:
    return s.upper().replace("Ё", "Е")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="../data/Russian/morphs.json")
    parser.add_argument("--output", default="../data/Russian/morphs.json")
    parser.add_argument("--gramtab", default="../data/Russian/gramtab.json")
    parser.add_argument("--pages", default="tmp/cache/pages.jsonl")
    args = parser.parse_args()
    titles = set()
    for line in open(args.pages):
        page = json.loads(line)
        if page.get("type") == "article" and is_obscene(page.get("text", "")):
            titles.add(norm(page["title"]))
    gramtab = json.load(open(args.gramtab))
    codes = gramtab["gramcodes"]
    type_codes = {frozenset(v["g"]): code for code, v in codes.items() if v["p"] == ""}
    free_codes = (a + b for a, b in itertools.product(string.ascii_uppercase + string.ascii_lowercase, repeat=2)
                  if a + b not in codes)
    data = json.load(open(args.input))
    counts = Counter()
    for lemma in data["lemmas"]:
        if norm(lemma["l"]) not in titles:
            continue
        grammems = set(codes[lemma["t"]]["g"]) if lemma.get("t") else set()
        if OBSCENE in grammems:
            continue
        grammems.add(OBSCENE)
        key = frozenset(grammems)
        if key not in type_codes:
            code = next(free_codes)
            codes[code] = {"p": "", "g": sorted(grammems, key=lambda g: (g == OBSCENE, g)), "f": 0}
            type_codes[key] = code
            counts["new gramcodes"] += 1
        lemma["t"] = type_codes[key]
        counts["marked lemmas"] += 1
    counts["obscene articles"] = len(titles)
    counts["articles without a lemma"] = len(titles - {norm(lemma["l"]) for lemma in data["lemmas"]})
    with open(args.output, "w") as outp:
        json.dump(data, outp, ensure_ascii=False)
    with open(args.gramtab, "w") as outp:
        json.dump(gramtab, outp, ensure_ascii=False, indent=4)
    print(dict(counts))


if __name__ == "__main__":
    main()
