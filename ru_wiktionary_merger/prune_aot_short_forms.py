"""
Removes the short forms of aot that neither Wiktionary nor the Flibusta corpus confirm (`абиетинов`, `ранговы`).

The candidates are the adjectives whose short forms are in aot only (the Wiktionary paradigm has no short form,
2164 adjectives); the decisions are in `short_only_aot.tsv` (`keep` / `remove` and the reason). The voices: aot,
Wiktionary (`marked`: the short forms are marked `*` as assumed or difficult; `absent:кач`, `absent:отн`, `absent:-`:
the table has no short forms, the type of the adjective), the Flibusta frequency of the short forms m, f, pl in
lowercase (the ddc server, case sensitive: `Малахитова` is a surname; the neuter is mostly an adverb; a form of
another word does not count), the contexts of these forms (a predicative: `был молчалив`, `ночь была черна и
безлунна`), Claude (the meaning of the qualitative adjectives without corpus evidence).
- keep: the short forms are forms of a verb too (207: `загорел`, `утомлена`, `устал`; the corpus does not tell them
  apart); the contexts show short forms (320: `гиблы`, `узкогруд`, `половозрел`, `термостоек`); a qualitative adjective
  without corpus evidence (4: `бестолков`, `брав`);
- remove: Flibusta 0, Wiktionary no or silent (1452); a relative adjective typed as qualitative in Wiktionary (34:
  `асбестов`, `таможен`); the contexts show other words (147: surnames, nouns `круторог`, `мохноног`, the genitive
  plural `берцов`, `квинтов`, folk forms `шкатулка малахитова`, Ukrainian text).
All short forms of such an adjective are removed. The neuter form that is an adverb in the corpus is added back as
an adverb by `add_adverbs_in_e.py --decisions adverbs_in_o.tsv` (`небывало`, `образцово`, `упреждающе`).

The result should be saved by `slf_convert --to-mrd` with an empty slf file.
"""
import argparse
import json
from collections import Counter
from typing import List


def add_item(items: List, item) -> int:
    if item in items:
        return items.index(item)
    items.append(item)
    return len(items) - 1


def norm(s: str) -> str:
    return s.upper().replace("Ё", "Е")


def read_removed(path: str) -> set:
    result = set()
    for line in open(path):
        if line.startswith("#") or line.startswith("lemma\t"):
            continue
        lemma, _, _, _, decision, _ = line.rstrip("\n").split("\t")
        if decision == "remove":
            result.add(norm(lemma))
    return result


def main():
    with open(args.input) as inp:
        data = json.load(inp)
    codes = json.load(open(args.gramtab))["gramcodes"]
    flexia, accents = data["flexia_models"], data["accent_models"]
    removed_lemmas = read_removed(args.decisions)

    def is_short(code: str) -> bool:
        return codes[code]["p"] == "ADJ_SHORT"

    counts = Counter()
    found = set()
    report = []
    for lemma in data["lemmas"]:
        if norm(lemma["l"]) not in removed_lemmas:
            continue
        endings = flexia[lemma["f"]]["endings"]
        if codes[endings[0]["gramcode"][:2]]["p"] != "A":
            continue
        if "n" in lemma:
            counts["skipped: a lemma with parts"] += 1
            continue
        base = lemma["l"][:len(lemma["l"]) - len(endings[0]["flexia"])]
        new_endings, keep, removed = [], [], []
        for i, ending in enumerate(endings):
            gramcodes = [ending["gramcode"][j:j + 2] for j in range(0, len(ending["gramcode"]), 2)]
            rest = [c for c in gramcodes if not is_short(c)]
            if len(rest) == len(gramcodes):
                new_endings.append(ending)
                keep.append(i)
                continue
            removed.append(ending.get("prefix", "") + base + ending["flexia"])
            if rest:
                # the form has other readings: only the codes of the short form are removed
                new_endings.append(dict(ending, gramcode="".join(rest)))
                keep.append(i)
        if not removed:
            continue
        found.add(norm(lemma["l"]))
        lemma["f"] = add_item(flexia, {"endings": new_endings})
        lemma["a"] = add_item(accents, [accents[lemma["a"]][i] for i in keep])
        counts["adjectives"] += 1
        counts["removed forms"] += len(removed)
        report.append((lemma["l"], " ".join(removed)))
    counts["decisions without an adjective with short forms"] = len(removed_lemmas - found)
    with open(args.output, "w") as outp:
        json.dump(data, outp, ensure_ascii=False)
    with open(args.report, "w") as outp:
        outp.write("lemma\tremoved forms\n")
        for row in report:
            outp.write("\t".join(row) + "\n")
    print(dict(counts))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--gramtab", default="../data/Russian/gramtab.json")
    parser.add_argument("--decisions", default="short_only_aot.tsv")
    parser.add_argument("--report", default="result/aot_short_forms_removed.tsv")
    args = parser.parse_args()
    main()
