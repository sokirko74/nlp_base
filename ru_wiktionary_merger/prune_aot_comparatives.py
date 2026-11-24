"""
Removes the comparatives of aot that neither Wiktionary nor the Flibusta corpus confirm (`абажурнее`, `черешковее`).

The candidates are the adjectives whose comparative is in aot only (`A compar: only aot` of compare_with_aot.py,
8121 adjectives); the decisions are in `compar_only_aot.tsv` (`keep` / `remove` and the reason). The voices:
aot, Wiktionary (`no`: `~` in the index or "Сравнительная степень не образуется"; `hidden`: `степень=` is given, but
the template does not show it; `silent:кач`, `silent:отн`, `silent:-`: no comparative, the type of the adjective),
the Flibusta frequency of the comparatives without `по-` (a form of another word does not count: `клубней` of
`клубень`; a comparative of another word does: `подробнее`, `меньше` of МАЛО), Claude (the contexts, the meaning).
- keep: Flibusta >= 5 (923); Flibusta 1-4 and Wiktionary `hidden` or `качественное` (150); Flibusta 1-4 and the
  contexts show a comparative (664: `бывалее меня`, `захолустнее которой`, `желторотее не бывает`); Flibusta 0,
  a hidden Wiktionary yes and the adjective is qualitative (47: `постыднее`, `эгоцентричнее`); the Wiktionary page
  gives the comparative (37: `лимоннее`; aot has `-ней` too, so the pair differed);
- remove: Flibusta 0 and Wiktionary no or silent (5915); Flibusta 0, a hidden Wiktionary yes and the adjective is
  relative (272: `золотовалютнее`, `тоннельнее`); Flibusta 1-4 and the contexts show another word (113: typos
  `безлопастнее`, nouns `кандальней`, `сводней`).
All comparative forms of such an adjective are removed: `A compar` and `A compar,2` with `по-`.

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

    def is_comparative(code: str) -> bool:
        return codes[code]["p"] == "A" and "compar" in codes[code]["g"]

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
            rest = [c for c in gramcodes if not is_comparative(c)]
            if len(rest) == len(gramcodes):
                new_endings.append(ending)
                keep.append(i)
                continue
            removed.append(ending.get("prefix", "") + base + ending["flexia"])
            if rest:
                # the form has other readings: only the codes of the comparative are removed
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
    counts["decisions without an adjective with a comparative"] = len(removed_lemmas - found)
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
    parser.add_argument("--decisions", default="compar_only_aot.tsv")
    parser.add_argument("--report", default="result/aot_comparatives_removed.tsv")
    args = parser.parse_args()
    main()
