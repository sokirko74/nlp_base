"""
The fictitious comparatives and short forms of adjectives whose comparative equals their own forms.

aot.ru gave a comparative to adjectives with a soft stem or a stem in a sibilant or ц (`последний`: `последнее`,
`последней`, `попоследнее`; `будущий`, `ведущий`, `верхний`), the comparative forms were the neuter and the feminine
forms of the adjective itself. Such an adjective is found by its comparative forms (`A compar`) that are all forms of
the same paradigm; `поздний` with `позже` is not one of them.

1. The comparatives (`A compar` and `A compar,2` with по-) are removed, unless the Wiktionary paradigm of the lemma
   (`result/mrd`) has a comparative (`свежий`: `свежее`, `горячий`, `древний`): such adjectives are listed for review.
2. The short forms of these adjectives are mostly fictitious too (`будущ`, `последня`). They are kept for the
   adjectives with the decision `keep` in `own_homonym_short_forms.tsv`: the short forms m+f+pl (the neuter in -е is
   mostly an adverb: `умоляюще`) in lowercase in the Flibusta corpus are >= 1% of the nominative and >= 10, and their
   contexts show short forms (`похож`, `схож`, `вхож`, `свеж`, `могуч`, `всемогущ`); the decision `noise` means that
   the contexts show other words (`кари` = карри, `сидячи` = a gerund, `будня` of `будень`).
   The other adjectives lose their short forms.

The result should be saved by `slf_convert --to-mrd` with an empty slf file.
"""
import argparse
import json
from collections import Counter
from typing import Dict, List, Set

from compare_with_aot import TDictionary, read_gramtab


def add_item(items: List, item) -> int:
    if item in items:
        return items.index(item)
    items.append(item)
    return len(items) - 1


def norm(s: str) -> str:
    return s.upper().replace("Ё", "Е")


def wiki_comparatives(folder: str) -> Set[str]:
    """the lemmas of the Wiktionary dictionary with a comparative"""
    wiki = TDictionary(folder, read_gramtab(folder))
    result = set()
    for index, lemma in enumerate(wiki.lemmas):
        if wiki.group(index) == "A" and any(a.startswith("A ") and "compar" in a.split(" ", 1)[1].split(",")
                                            for _, a in wiki.lines(index)):
            result.add(norm(lemma["l"]))
    return result


def read_decisions(path: str) -> Dict[str, str]:
    result = {}
    for line in open(path):
        if line.startswith("#") or line.startswith("lemma\t"):
            continue
        lemma, _, _, decision, _ = line.rstrip("\n").split("\t")
        result[lemma] = decision
    return result


def main():
    with open(args.input) as inp:
        data = json.load(inp)
    codes = json.load(open(args.gramtab))["gramcodes"]
    flexia, accents = data["flexia_models"], data["accent_models"]

    def pos(code: str) -> str:
        return codes[code]["p"]

    def is_comparative(code: str) -> bool:
        return pos(code) == "A" and "compar" in codes[code]["g"]

    with_wiki_comparative = wiki_comparatives(args.wiki_folder)
    decisions = read_decisions(args.decisions)
    counts = Counter()
    report = []
    for lemma in data["lemmas"]:
        endings = flexia[lemma["f"]]["endings"]
        if "n" in lemma or pos(endings[0]["gramcode"][:2]) != "A":
            continue
        base = lemma["l"][:len(lemma["l"]) - len(endings[0]["flexia"])]

        def form(e) -> str:
            return e.get("prefix", "") + base + e["flexia"]

        def codes_of(e) -> List[str]:
            return [e["gramcode"][i:i + 2] for i in range(0, len(e["gramcode"]), 2)]

        comparatives = {form(e) for e in endings if any(is_comparative(c) and "2" not in codes[c]["g"]
                                                       for c in codes_of(e))}
        others = {form(e) for e in endings if not any(is_comparative(c) for c in codes_of(e))}
        if not comparatives or not comparatives <= others:
            continue
        counts["adjectives"] += 1
        remove_comparative = norm(lemma["l"]) not in with_wiki_comparative
        remove_short = decisions.get(lemma["l"]) != "keep"
        removed = [i for i, e in enumerate(endings)
                   if (remove_comparative and any(is_comparative(c) for c in codes_of(e))) or
                   (remove_short and any(pos(c) == "ADJ_SHORT" for c in codes_of(e)))]
        if not remove_comparative:
            counts["comparative kept, Wiktionary has it"] += 1
        else:
            counts["comparative removed"] += 1
        has_short = any(pos(c) == "ADJ_SHORT" for e in endings for c in codes_of(e))
        if has_short:
            counts["short forms removed" if remove_short else "short forms kept"] += 1
        if removed:
            keep = [i for i in range(len(endings)) if i not in removed]
            lemma["f"] = add_item(flexia, {"endings": [endings[i] for i in keep]})
            lemma["a"] = add_item(accents, [accents[lemma["a"]][i] for i in keep])
            counts["removed forms"] += len(removed)
        report.append((lemma["l"], "kept" if not remove_comparative else "removed",
                       "kept" if not remove_short else ("removed" if has_short else "none"),
                       " ".join(form(endings[i]) for i in removed)))
    with open(args.output, "w") as outp:
        json.dump(data, outp, ensure_ascii=False)
    with open(args.report, "w") as outp:
        outp.write("lemma\tcomparative\tshort forms\tremoved forms\n")
        for row in report:
            outp.write("\t".join(row) + "\n")
    print(dict(counts))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--gramtab", default="../data/Russian/gramtab.json")
    parser.add_argument("--wiki-folder", default="result/mrd")
    parser.add_argument("--decisions", default="own_homonym_short_forms.tsv")
    parser.add_argument("--report", default="result/own_homonym_comparatives.tsv")
    args = parser.parse_args()
    main()
