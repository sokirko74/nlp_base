"""
Adds the plural to the toponyms of aot.ru (`loc,sing_tant` without plural forms: `МОСКВА`) from Wiktionary.
In aot `sing_tant` (дфст, de facto singularia tantum) means that the plural exists but is rarely used: the rule
`Rule_DeadPlurals` of MAPost removes the plural readings of such words if the context is not plural. So a paradigm
with `sing_tant` should have the plural, as `АБАДАН` has. The plural of toponyms is used in Flibusta: `по Парижам`,
`в разных Италиях`, `по всевозможным Турциям`, `двух павших Римов`.
The plural is taken from the Wiktionary dictionary (`--wiki`, the export loaded by slf_convert): a paradigm with the
same lemma and the same singular forms. The stress of the new forms is unknown, `sing_tant` is kept.
The result should be saved by `slf_convert --to-mrd` with an empty slf file.
"""
import argparse
import json
from collections import Counter, defaultdict
from typing import List

UNKNOWN_ACCENT = 255
CASES = ("nom", "gen", "dat", "acc", "ins", "prp")
GENDERS = ("mas", "fem", "neu")


def norm(s: str) -> str:
    return s.upper().replace("Ё", "Е")


def add_item(items: List, item) -> int:
    if item in items:
        return items.index(item)
    items.append(item)
    return len(items) - 1


def paradigm(lemma, flexia, codes):
    endings = flexia[lemma["f"]]["endings"]
    first = endings[0]["flexia"]
    base = lemma["l"][:len(lemma["l"]) - len(first)] if first else lemma["l"]
    return base, [(base + e["flexia"], codes[e["gramcode"][:2]]) for e in endings]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--gramtab", default="../data/Russian/gramtab.json")
    parser.add_argument("--wiki", default="result/mrd", help="the Wiktionary dictionary (morphs.json, gramtab.json)")
    parser.add_argument("--added", default="result/toponym_plurals.tsv", help="the list of the added forms")
    args = parser.parse_args()
    data = json.load(open(args.input))
    codes = json.load(open(args.gramtab))["gramcodes"]
    flexia = data["flexia_models"]
    # the gramcode of a plural noun form: `N fem,pl,nom`
    plural_code = {}
    for code, value in codes.items():
        g = set(value["g"])
        if value["p"] == "N" and "pl" in g and len(g) == 3:
            gender = g & set(GENDERS)
            case = g & set(CASES)
            if gender and case:
                plural_code.setdefault((gender.pop(), case.pop()), code)

    wiki = json.load(open(args.wiki + "/morphs.json"))
    wiki_codes = json.load(open(args.wiki + "/gramtab.json"))["gramcodes"]
    wiki_by_lemma = defaultdict(list)
    for lemma in wiki["lemmas"]:
        _, forms = paradigm(lemma, wiki["flexia_models"], wiki_codes)
        if forms[0][1]["p"] == "N":
            wiki_by_lemma[norm(lemma["l"])].append(forms)

    counts, added = Counter(), []
    accents = data["accent_models"]
    for lemma in data["lemmas"]:
        type_grammems = codes.get(lemma.get("t", ""), {}).get("g", [])
        if "loc" not in type_grammems or "sing_tant" not in type_grammems:
            continue
        base, forms = paradigm(lemma, flexia, codes)
        if forms[0][1]["p"] != "N" or any("pl" in c["g"] for _, c in forms) or any("0" in c["g"] for _, c in forms):
            continue
        counts["aot toponyms without plural"] += 1
        singular = {(norm(f), tuple(sorted(c["g"]))) for f, c in forms}
        candidates = []
        for wiki_forms in wiki_by_lemma.get(norm(lemma["l"]), []):
            wiki_singular = {(norm(f), tuple(sorted(c["g"]))) for f, c in wiki_forms if "sg" in c["g"]}
            plural = [(f, c) for f, c in wiki_forms if "pl" in c["g"]]
            # the same word: the singular of one dictionary is a part of the other one (aot may have the second
            # prepositional `в Крыму`, Wiktionary a variant `Италиею`)
            if plural and wiki_singular and (wiki_singular <= singular or singular <= wiki_singular):
                candidates.append(plural)
        if not candidates:
            counts["no Wiktionary paradigm with the same singular"] += 1
            continue
        if len(candidates) > 1 and any(c != candidates[0] for c in candidates):
            counts["several Wiktionary paradigms"] += 1
            continue
        if "p" in lemma:
            counts["has a prefix set"] += 1
            continue
        new = []
        for form, code in candidates[0]:
            gender = next((g for g in GENDERS if g in code["g"]), None)
            case = next((c for c in CASES if c in code["g"]), None)
            if not gender or not case or (gender, case) not in plural_code:
                new = None
                break
            # the spelling of aot: `Ё` only if the lemma has it
            form = form.upper() if "Ё" in lemma["l"] else norm(form)
            new.append((form, plural_code[(gender, case)]))
        if not new:
            counts["no gramcode for the plural"] += 1
            continue
        # the stem is the common beginning of all forms: `АВДЕЕВКА` + `АВДЕЕВОК` -> `АВДЕЕВ`
        old_endings = flexia[lemma["f"]]["endings"]
        all_forms = [base + e["flexia"] for e in old_endings] + [f for f, _ in new]
        stem = all_forms[0]
        for form in all_forms[1:]:
            while not form.startswith(stem):
                stem = stem[:-1]
        endings = [{"flexia": f[len(stem):], "gramcode": e["gramcode"]}
                   for f, e in zip(all_forms, old_endings)]
        endings += [{"flexia": f[len(stem):], "gramcode": code} for f, code in new]
        accent = list(accents[lemma["a"]]) + [UNKNOWN_ACCENT] * len(new)
        for form, code in new:
            added.append((lemma["l"], form, code))
        lemma["f"] = add_item(flexia, {"endings": endings})
        lemma["a"] = add_item(accents, accent)
        counts["plural added"] += 1
    with open(args.output, "w") as outp:
        json.dump(data, outp, ensure_ascii=False)
    with open(args.added, "w") as outp:
        for row in added:
            outp.write("\t".join(row) + "\n")
    print(dict(counts))


if __name__ == "__main__":
    main()
