"""
Marks as obsolete (`arch`) the inclusive imperative in -мте/-мтесь (напишемте, вернемтесь) that does not occur in
the Flibusta corpus (`inclusive_imperative_flibusta.tsv`, the ddc query `count(/мте(сь)?$/i) #by[$w]`): 14710 of 14836
forms of aot.ru (15112 of 15239 with homonyms); пойдемте (33464), идемте (18989), споемте, выпьемте are kept.
The forms are regular, so they are not removed: a text of the 19th century has напишемте. The forms without -те (сделаем) coincide with the future and are
not changed.
The gramtab gets the gramcode `Mt` (V act,imp,1p,pl,arch), it had `arch` only for the 2nd person (GA, GB).
The result should be saved by `slf_convert --to-mrd` with an empty slf file.
"""
import argparse
import json
from collections import Counter
from typing import List

IMPERATIVE_1P = "Ft"
ARCH_IMPERATIVE_1P = "Mt"
ARCH_IMPERATIVE_1P_LINE = {"p": "V", "g": ["act", "imp", "1p", "pl", "arch"], "f": 0, "l": "НАПИШЕМТЕ"}


def norm(s: str) -> str:
    return s.upper().replace("Ё", "Е")


def add_item(items: List, item) -> int:
    if item in items:
        return items.index(item)
    items.append(item)
    return len(items) - 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--gramtab", default="../data/Russian/gramtab.json")
    parser.add_argument("--flibusta", default="inclusive_imperative_flibusta.tsv")
    parser.add_argument("--changed", default="result/arch_inclusive_imperative.tsv")
    args = parser.parse_args()

    gramtab = json.load(open(args.gramtab))
    if ARCH_IMPERATIVE_1P not in gramtab["gramcodes"]:
        gramtab["gramcodes"][ARCH_IMPERATIVE_1P] = ARCH_IMPERATIVE_1P_LINE
        with open(args.gramtab, "w") as outp:
            json.dump(gramtab, outp, ensure_ascii=False, indent=4)
    corpus = set()
    for line in open(args.flibusta):
        if not line.startswith("#"):
            corpus.add(norm(line.split("\t")[0]))

    data = json.load(open(args.input))
    flexia = data["flexia_models"]
    counts, changed = Counter(), []
    for lemma in data["lemmas"]:
        endings = flexia[lemma["f"]]["endings"]
        first = endings[0]["flexia"]
        base = lemma["l"][:len(lemma["l"]) - len(first)] if first else lemma["l"]
        old = []
        for i, e in enumerate(endings):
            form = base + e["flexia"]
            if e["gramcode"] == IMPERATIVE_1P and form.endswith(("МТЕ", "МТЕСЬ")):
                if norm(form) in corpus:
                    counts["kept, in Flibusta"] += 1
                else:
                    old.append(i)
                    changed.append((lemma["l"], form))
        if not old:
            continue
        new_endings = [dict(e) for e in endings]
        for i in old:
            new_endings[i]["gramcode"] = ARCH_IMPERATIVE_1P
        lemma["f"] = add_item(flexia, {"endings": new_endings})
        counts["arch"] += len(old)
    with open(args.output, "w") as outp:
        json.dump(data, outp, ensure_ascii=False)
    with open(args.changed, "w") as outp:
        for row in sorted(changed):
            outp.write("\t".join(row) + "\n")
    print(dict(counts))


if __name__ == "__main__":
    main()
