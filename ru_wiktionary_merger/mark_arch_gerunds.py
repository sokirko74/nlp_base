"""
Marks as obsolete (`arch`) the gerunds of perfective verbs in -я/-ясь/-а/-ась (вдохновя, вооружась, вспомня)
that have the gerund in -в/-вшись (вдохновив, вооружившись). Wiktionary gives only the forms in -в/-вшись,
the forms in -я are rare in the Flibusta corpus (вооружась 87 / вооружившись 5369, вспомня 17 / вспомнив 58836).
The verbs without a gerund in -в (придя, принеся) are not changed: their gerund in -я is the normal one.
The forms that Wiktionary gives (`--wiki`, the dictionary loaded from the slf export) are not changed either
(возвратясь 303 / возвратившись 1127).
The forms that are frequent in Flibusta (`--flibusta`: the share of the form among the gerunds of the verb is
>= 20% and the frequency >= 5) are not changed: idioms (скрепя сердце, очертя голову, куда ни попадя, не спросясь)
and forms like воротясь (206 / воротившись 88).
The new gramcode is `Fs` (ADV_PARTICIPLE act,past,arch), also for the forms which were marked as present
(вспомня: a perfective verb has no present gerund).
The result should be saved by `slf_convert --to-mrd` with an empty slf file.
"""
import argparse
import json
from collections import Counter
from typing import List

ARCH_GERUND = "Fs"
OLD_SUFFIXES = ("Я", "ЯСЬ", "А", "АСЬ")
NEW_SUFFIXES = ("В", "ВШИСЬ")


def add_item(items: List, item) -> int:
    if item in items:
        return items.index(item)
    items.append(item)
    return len(items) - 1


def norm(s: str) -> str:
    return s.upper().replace("Ё", "Е")


def lemma_forms(lemma, flexia, codes, pos: str):
    endings = flexia[lemma["f"]]["endings"]
    first = endings[0]["flexia"]
    base = lemma["l"][:len(lemma["l"]) - len(first)] if first else lemma["l"]
    return [(i, base + e["flexia"]) for i, e in enumerate(endings) if codes[e["gramcode"][:2]]["p"] == pos]


def read_wiki_gerunds(folder: str):
    data = json.load(open(folder + "/morphs.json"))
    codes = json.load(open(folder + "/gramtab.json"))["gramcodes"]
    result = {}
    for lemma in data["lemmas"]:
        forms = lemma_forms(lemma, data["flexia_models"], codes, "ADV_PARTICIPLE")
        result.setdefault(norm(lemma["l"]), set()).update(norm(f) for _, f in forms)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--gramtab", default="../data/Russian/gramtab.json")
    parser.add_argument("--wiki", default="result/mrd", help="the Wiktionary dictionary (morphs.json, gramtab.json)")
    parser.add_argument("--flibusta", default="arch_gerunds_flibusta.tsv")
    parser.add_argument("--min-share", type=float, default=0.2)
    parser.add_argument("--min-freq", type=int, default=5)
    parser.add_argument("--changed", default="result/arch_gerunds.tsv", help="the list of the changed forms")
    args = parser.parse_args()
    with open(args.input) as inp:
        data = json.load(inp)
    codes = json.load(open(args.gramtab))["gramcodes"]
    flexia = data["flexia_models"]
    wiki = read_wiki_gerunds(args.wiki)
    frequent = set()
    for line in open(args.flibusta):
        if line.startswith("#"):
            continue
        lemma, form, count, count_new = line.rstrip("\n").split("\t")
        count, count_new = int(count), int(count_new)
        if count >= args.min_freq and count >= args.min_share * (count + count_new):
            frequent.add((lemma, form))
    counts, changed = Counter(), []
    for lemma in data["lemmas"]:
        grammems = codes.get(lemma.get("t", ""), {}).get("g", [])
        if "perf" not in grammems or "imperf" in grammems:
            continue
        endings = flexia[lemma["f"]]["endings"]
        forms = dict(lemma_forms(lemma, flexia, codes, "ADV_PARTICIPLE"))
        if not any(f.endswith(NEW_SUFFIXES) for f in forms.values()):
            continue
        old = [i for i, f in forms.items() if f.endswith(OLD_SUFFIXES) and endings[i]["gramcode"] != ARCH_GERUND]
        in_wiki = [i for i in old if norm(forms[i]) in wiki.get(norm(lemma["l"]), set())]
        counts["kept, Wiktionary has it"] += len(in_wiki)
        old = [i for i in old if i not in in_wiki]
        in_corpus = [i for i in old if (lemma["l"], forms[i]) in frequent]
        counts["kept, frequent in Flibusta"] += len(in_corpus)
        old = [i for i in old if i not in in_corpus]
        if not old:
            continue
        new_endings = [dict(e) for e in endings]
        for i in old:
            counts[endings[i]["gramcode"]] += 1
            new_endings[i]["gramcode"] = ARCH_GERUND
            changed.append((lemma["l"], forms[i], endings[i]["gramcode"]))
        lemma["f"] = add_item(flexia, {"endings": new_endings})
        counts["lemmas"] += 1
    with open(args.output, "w") as outp:
        json.dump(data, outp, ensure_ascii=False)
    with open(args.changed, "w") as outp:
        for row in sorted(changed):
            outp.write("\t".join(row) + "\n")
    print(dict(counts))


if __name__ == "__main__":
    main()
