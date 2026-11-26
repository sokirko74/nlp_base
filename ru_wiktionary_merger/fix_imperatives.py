"""
Takes the imperative (2nd person) of Wiktionary where the Flibusta corpus supports it against aot.

The decisions are in `imperatives.tsv`: 397 verbs whose imperative of the 2nd person singular differs in aot and
Wiktionary (mostly -и / -ь: `всунь` / `всуни`). The voices: aot, Wiktionary, the lowercase Flibusta frequency of the
singular and plural forms without homographs (`голуби` is a noun, `выволочь` an infinitive, `вывесите` the future).
- wiki (10): the forms of Wiktionary replace those of aot (`приструни` 85 against `приструнь` 1, `лыбься` 115,
  `скинься` 23, `пригуби` 29, `вытянись` 17);
- add (1): both are used, the form of Wiktionary is added (`пополощи` next to `пополоскай`);
- keep: Flibusta prefers aot (60: `всунь` 69 against `всуни` 0, `восполни`, `высиди`), no clear majority (56), no form
  in Flibusta (244), homographs only (3), errors of Wiktionary (23: `вклинй`, `впялйся` with й after a consonant,
  `вороши` for `наворошить`, `раскрутись` for `раскутиться`).
The new forms take the gramcodes of the imperative of aot and the stress of Wiktionary.

The result should be saved by `slf_convert --to-mrd` with an empty slf file.
"""
import argparse
import json
import unicodedata
from collections import Counter
from typing import Optional, Tuple

UNKNOWN_ACCENT = 255
VOWELS = "АЕЁИОУЫЭЮЯ"


def plain_and_stress(value: str) -> Tuple[str, Optional[int]]:
    """`при́струни` -> ("ПРИСТРУНИ", the vowel number from the end)"""
    text = unicodedata.normalize("NFD", value)
    letters = []
    position = None
    for c in text:
        if c == "́":
            position = len(letters) - 1
        elif c != "\u0300":
            letters.append(c)
    if position is None:
        return unicodedata.normalize("NFC", "".join(letters)).upper(), None
    marked = unicodedata.normalize("NFC", "".join(letters[:position + 1]) + "\u0001" + "".join(letters[position + 1:]))
    position = marked.index("\u0001") - 1
    word = marked.replace("\u0001", "").upper()
    vowels = [i for i, c in enumerate(word) if c in VOWELS]
    return word, len(vowels) - 1 - vowels.index(position) if position in vowels else None


def main():
    with open(args.input) as inp:
        data = json.load(inp)
    codes = json.load(open(args.gramtab))["gramcodes"]
    flexia, accents = data["flexia_models"], data["accent_models"]
    decisions = {}
    for line in open(args.decisions):
        parts = line.rstrip("\n").split("\t")
        if not line.startswith(("#", "lemma\t")) and parts[5] in ("wiki", "add"):
            decisions[parts[0]] = parts[5]
    wiki = {}
    for line in open(args.wiki):
        article = json.loads(line)
        key = article["title"].upper().replace("Ё", "Е")
        if key in decisions:
            wiki[key] = {n: article["generated_forms"].get(n, []) for n in ("imp-sg-2", "imp-pl-2")}
    counts = Counter()
    report = []
    for lemma in data["lemmas"]:
        word = lemma["l"]
        if word not in decisions or "n" in lemma:
            continue
        endings = flexia[lemma["f"]]["endings"]
        if codes[endings[0]["gramcode"][:2]]["p"] not in ("INFINITIVE", "V"):
            continue
        base = word[:len(word) - len(endings[0]["flexia"])]
        old_accents = accents[lemma["a"]]

        def number(gramcode: str) -> Optional[str]:
            value = codes[gramcode[:2]]
            if value["p"] == "V" and "imp" in value["g"] and "2p" in value["g"]:
                return "imp-sg-2" if "sg" in value["g"] else "imp-pl-2"
            return None

        code_of = {number(e["gramcode"]): e["gramcode"] for e in endings if number(e["gramcode"])}
        kept = [(base + e["flexia"], e["gramcode"], a) for e, a in zip(endings, old_accents)
                if decisions[word] == "add" or not number(e["gramcode"])]
        removed = [base + e["flexia"] for e in endings if decisions[word] == "wiki" and number(e["gramcode"])]
        added = []
        for name, values in wiki[word].items():
            for value in values:
                form, stress = plain_and_stress(value)
                item = (form, code_of[name], UNKNOWN_ACCENT if stress is None else stress)
                if not any(f == form and c == code_of[name] for f, c, _ in kept):
                    added.append(item)
        all_forms = kept + added
        new_base = base
        for form, _, _ in all_forms:
            while not form.startswith(new_base):
                new_base = new_base[:-1]
        model = {"endings": [{"flexia": f[len(new_base):], "gramcode": c} for f, c, _ in all_forms]}
        if model in flexia:
            lemma["f"] = flexia.index(model)
        else:
            lemma["f"] = len(flexia)
            flexia.append(model)
        accent_model = [a for _, _, a in all_forms]
        if accent_model in accents:
            lemma["a"] = accents.index(accent_model)
        else:
            lemma["a"] = len(accents)
            accents.append(accent_model)
        counts["verbs"] += 1
        removed_forms = sorted(set(removed) - {f for f, _, _ in added})
        report.append((word, " ".join(removed_forms), " ".join(f for f, _, _ in added)))
    counts["decisions not applied"] = len(set(decisions) - {r[0] for r in report})
    with open(args.output, "w") as outp:
        json.dump(data, outp, ensure_ascii=False)
    with open(args.report, "w") as outp:
        outp.write("lemma\tremoved\tadded\n")
        for row in report:
            outp.write("\t".join(row) + "\n")
    print(dict(counts))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--gramtab", default="../data/Russian/gramtab.json")
    parser.add_argument("--wiki", default="result/verbs.jsonl")
    parser.add_argument("--decisions", default="imperatives.tsv")
    parser.add_argument("--report", default="result/imperatives_changed.tsv")
    args = parser.parse_args()
    main()
