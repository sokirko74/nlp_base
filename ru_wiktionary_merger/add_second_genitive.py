"""
Adds the second genitive to nouns that have it in the parameter `Р` of Wiktionary, but not in aot.ru.
The reviewed list is below. The form repeats the ending of the dative and takes the stress of the genitive.
The result should be saved by `slf_convert --to-mrd` with an empty slf file.
"""
import argparse
import json
from collections import Counter
from typing import List

SECOND_GENITIVE = "AC"
GENITIVE, DATIVE = "AB", "AD"
LEMMAS = ["БРОД", "СПОР", "СПРОС", "ОТДЫХ", "ИЗНОС", "СПАС", "РОЗДЫХ", "ИСПУГ", "ШАШЛЫК", "ОГОНЕК", "КЕТЧУП", "БРЕЗЕНТ",
          "НАЖДАК", "ЧИФИР", "АНАНАС", "ПРОФИТ", "АКСАМИТ", "ГИПЮР", "ДЕМИКОТОН", "МИТКАЛЬ", "ОБРОК", "ПАРДОН"]
# lemmas with an animate homonym, it has no second genitive
INANIMATE = "MM"


def add_item(items: List, item) -> int:
    if item in items:
        return items.index(item)
    items.append(item)
    return len(items) - 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    with open(args.input) as inp:
        data = json.load(inp)
    counts, changed = Counter(), set()
    for lemma in data["lemmas"]:
        key = lemma["l"].replace("Ё", "Е")
        if key not in LEMMAS or lemma.get("n") or lemma.get("t") not in (INANIMATE, "MK"):
            continue
        endings = data["flexia_models"][lemma["f"]]["endings"]
        codes = [e["gramcode"] for e in endings]
        if GENITIVE not in codes or DATIVE not in codes or SECOND_GENITIVE in codes:
            continue
        position = codes.index(GENITIVE) + 1
        new_ending = {"flexia": endings[codes.index(DATIVE)]["flexia"], "gramcode": SECOND_GENITIVE}
        new_endings = endings[:position] + [new_ending] + endings[position:]
        lemma["f"] = add_item(data["flexia_models"], {"endings": new_endings})
        accents = data["accent_models"][lemma["a"]]
        lemma["a"] = add_item(data["accent_models"], accents[:position] + [accents[position - 1]] + accents[position:])
        changed.add(key)
        counts["changed"] += 1
    with open(args.output, "w") as outp:
        json.dump(data, outp, ensure_ascii=False)
    print(counts, "not found", sorted(set(LEMMAS) - changed))


if __name__ == "__main__":
    main()
