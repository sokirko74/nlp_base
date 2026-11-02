"""
Adds the second prepositional to nouns that have it in the parameter `М` of Wiktionary, but not in aot.ru.
The reviewed list is below. The form repeats the ending of the dative, the stress is on the ending (`в песку́`).
Feminine nouns: the form is spelled as the usual prepositional. REMOVE lists the lemmas of aot that got the form with
a flexia model, not on purpose: `в логину`. Repeated runs change nothing.
The result should be saved by `slf_convert --to-mrd` with an empty slf file.
"""
import argparse
import json
from collections import Counter

from add_second_genitive import DATIVE, add_item

SECOND_PREPOSITIONAL = "AH"
PREPOSITIONAL = "AG"
UNKNOWN_ACCENT_MODEL = 0xffff - 1
UNKNOWN_ACCENT = 255
FEMININE_SECOND_PREPOSITIONAL = "BR"
FEMININE_PREPOSITIONAL = "BQ"
INANIMATE = "MM"
LEMMAS = ["ПЕСОК", "ПУШОК", "СКАК", "ХВОСТ", "КУСТ", "МИРОК", "РАНТ", "ПАЙ", "НАСТ", "МЫСОК", "ЗООСАД", "АВИАПОЛК",
          "АВАНПОРТ", "АВАНПОСТ", "ФОРПОСТ", "ТЕРЕМ", "КУТ", "КУТОК"]
FEMININE = ["МАЗЬ", "ЧЕСТЬ", "ШЕРСТЬ", "АГРОСЕТЬ", "КИНОСЕТЬ", "ПОДСЕТЬ", "РАДИОСЕТЬ", "СОЦСЕТЬ", "ТЕЛЕСЕТЬ",
            "ТЕПЛОСЕТЬ", "ЭЛЕКТРОСЕТЬ", "ЭНЕРГОСЕТЬ"]
REMOVE = ["ЛОГИН", "АВИАКЕРОСИН"]


def insert_ending(data: dict, lemma: dict, position: int, ending: dict, accent: int) -> None:
    endings = data["flexia_models"][lemma["f"]]["endings"]
    lemma["f"] = add_item(data["flexia_models"], {"endings": endings[:position] + [ending] + endings[position:]})
    if lemma["a"] != UNKNOWN_ACCENT_MODEL:
        accents = data["accent_models"][lemma["a"]]
        if all(a == UNKNOWN_ACCENT for a in accents):
            accent = UNKNOWN_ACCENT
        lemma["a"] = add_item(data["accent_models"], accents[:position] + [accent] + accents[position:])


def remove_ending(data: dict, lemma: dict, position: int) -> None:
    endings = data["flexia_models"][lemma["f"]]["endings"]
    lemma["f"] = add_item(data["flexia_models"], {"endings": endings[:position] + endings[position + 1:]})
    if lemma["a"] != UNKNOWN_ACCENT_MODEL:
        accents = data["accent_models"][lemma["a"]]
        lemma["a"] = add_item(data["accent_models"], accents[:position] + accents[position + 1:])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    with open(args.input) as inp:
        data = json.load(inp)
    counts, changed, skipped = Counter(), set(), []
    for lemma in data["lemmas"]:
        key = lemma["l"].replace("Ё", "Е")
        endings = data["flexia_models"][lemma["f"]]["endings"]
        codes = [e["gramcode"] for e in endings]
        if key in REMOVE and SECOND_PREPOSITIONAL in codes:
            remove_ending(data, lemma, codes.index(SECOND_PREPOSITIONAL))
            counts["removed"] += 1
        if key in FEMININE and FEMININE_PREPOSITIONAL in codes and FEMININE_SECOND_PREPOSITIONAL not in codes:
            position = codes.index(FEMININE_PREPOSITIONAL)
            new_ending = {"flexia": endings[position]["flexia"], "gramcode": FEMININE_SECOND_PREPOSITIONAL}
            insert_ending(data, lemma, position + 1, new_ending, 0)
            counts["feminine"] += 1
            changed.add(key)
        if key not in LEMMAS:
            continue
        if lemma.get("n") or lemma.get("t") != INANIMATE or PREPOSITIONAL not in codes or DATIVE not in codes \
                or SECOND_PREPOSITIONAL in codes:
            skipped.append(f"{key} {lemma.get('t')} {lemma['f']}")
            continue
        position = codes.index(PREPOSITIONAL) + 1
        new_ending = {"flexia": endings[codes.index(DATIVE)]["flexia"], "gramcode": SECOND_PREPOSITIONAL}
        insert_ending(data, lemma, position, new_ending, 0)
        changed.add(key)
        counts["changed"] += 1
    with open(args.output, "w") as outp:
        json.dump(data, outp, ensure_ascii=False)
    print(counts, "not found", sorted(set(LEMMAS + FEMININE) - changed), "skipped", skipped)


if __name__ == "__main__":
    main()
