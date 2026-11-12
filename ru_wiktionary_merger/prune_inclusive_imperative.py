"""
Removes the inclusive imperative (сделаем, сделаемте: the gramcodes Ft and Mt) of the verbs of aot.ru listed with the
decision `drop` in `inclusive_imperative_reviewed.tsv`: Wiktionary does not give it (the table of a biaspectual verb
`гл ru 2a` has no cell for it), Flibusta has no form in -те, and the contexts with "!" do not show the imperative
(1329 verbs). The forms without -те stay in the paradigm as the future. The verbs with the decision `keep` (атакуем,
ползем, выбегаем: 52 verbs) and all the others are not changed.
The result should be saved by `slf_convert --to-mrd` with an empty slf file.
"""
import argparse
import csv
import json
from collections import Counter
from typing import List

INCLUSIVE_IMPERATIVE = ("Ft", "Mt")


def add_item(items: List, item) -> int:
    if item in items:
        return items.index(item)
    items.append(item)
    return len(items) - 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--decisions", default="inclusive_imperative_reviewed.tsv")
    args = parser.parse_args()
    with open(args.decisions) as inp:
        rows = csv.DictReader((line for line in inp if not line.startswith("#")), delimiter="\t")
        drop = {row["lemma"] for row in rows if row["decision"].startswith("drop")}
    data = json.load(open(args.input))
    flexia, accents = data["flexia_models"], data["accent_models"]
    counts = Counter()
    for lemma in data["lemmas"]:
        if lemma["l"] not in drop:
            continue
        endings = flexia[lemma["f"]]["endings"]
        keep = [i for i, e in enumerate(endings) if e["gramcode"] not in INCLUSIVE_IMPERATIVE]
        if len(keep) == len(endings):
            continue
        counts["forms"] += len(endings) - len(keep)
        counts["lemmas"] += 1
        lemma["f"] = add_item(flexia, {"endings": [endings[i] for i in keep]})
        lemma["a"] = add_item(accents, [accents[lemma["a"]][i] for i in keep])
    with open(args.output, "w") as outp:
        json.dump(data, outp, ensure_ascii=False)
    print(dict(counts), "verbs to drop:", len(drop))


if __name__ == "__main__":
    main()
