"""
Adds the short forms that Wiktionary gives and aot does not (`непредсказуем`, `низковат`, `традиционен`, `боеготов`).

The candidates are the adjectives without any short form in aot whose Wiktionary paradigm has short forms not marked
as assumed or difficult (1755); the decisions are in `short_only_wiki.tsv`. The voices: Wiktionary (`editor`: the
article gives `краткая=` or the forms; `template`: the template shows them by default, `прил ru 1*a`; `module`: the
Lua module of `прил-ру`), the Flibusta frequency of the short forms m, f, pl in lowercase (the ddc server; the
neuter is mostly an adverb), the contexts of the forms (a predicative: `был непредсказуем`, `армия не боеготова`).
- add (256): Wiktionary and the contexts of the corpus (`вариативен`, `коррупционен`, `многофакторна`,
  `полумертв`, `политкорректен`);
- skip: no corpus evidence (1386: one voice of Wiktionary, often the default of the template: `резервуарен`), the
  contexts show other words (80: folk full forms of soft stems `дальня родственница`, `прежни годы`, Ukrainian
  text, broken words), the forms are forms of a verb too (33: `организован`, the corpus does not tell them apart).
The forms and their stress are taken from the Wiktionary paradigm (`result/adjectives.jsonl`): `srt-sg-m`, `srt-sg-f`,
`srt-sg-n`, `srt-pl` with all variants; the stress is the vowel from the end, unknown if the form has two stress marks
(`то́чны́`). If a form does not continue the stem of the flexia model (`традиционен` of `традиционн|ый`), the stem is
shortened to the common beginning of all forms.

The result should be saved by `slf_convert --to-mrd` with an empty slf file.
"""
import argparse
import json
import unicodedata
from collections import Counter
from typing import List, Optional

from add_po_ski_adverbs import stress_of_wiki_text

UNKNOWN_ACCENT = 255
SHORT_GRAMMEMS = {"srt-sg-m": ["mas", "sg"], "srt-sg-f": ["fem", "sg"], "srt-sg-n": ["neu", "sg"], "srt-pl": ["pl"]}


def norm(s: str) -> str:
    return s.upper().replace("Ё", "Е")


def plain(form: str) -> str:
    """without the stress marks, in upper case: `ве́ска́` -> `ВЕСКА`"""
    return unicodedata.normalize("NFC", "".join(c for c in unicodedata.normalize("NFD", form)
                                                if c not in "́̀")).upper()


def common_prefix(words: List[str]) -> str:
    result = words[0]
    for word in words[1:]:
        while not word.startswith(result):
            result = result[:-1]
    return result


def read_added(path: str) -> set:
    result = set()
    for line in open(path):
        if line.startswith("#") or line.startswith("lemma\t"):
            continue
        parts = line.rstrip("\n").split("\t")
        if parts[5] == "add":
            result.add(norm(parts[0]))
    return result


def main():
    with open(args.input) as inp:
        data = json.load(inp)
    codes = json.load(open(args.gramtab))["gramcodes"]
    short_code = {name: next(c for c, v in codes.items() if v["p"] == "ADJ_SHORT" and
                             set(v["g"]) == set(grammems) | {"anim", "inanim"})
                  for name, grammems in SHORT_GRAMMEMS.items()}
    added = read_added(args.decisions)
    wiki = {}
    for line in open(args.wiki):
        article = json.loads(line)
        key = norm(article["title"])
        if key in added and key not in wiki:
            forms = {name: values for name, values in article["generated_forms"].items() if name in SHORT_GRAMMEMS}
            if forms:
                wiki[key] = forms
    flexia, accents = data["flexia_models"], data["accent_models"]
    flexia_index = {json.dumps(m, sort_keys=True, ensure_ascii=False): i for i, m in enumerate(flexia)}
    accent_index = {tuple(a): i for i, a in enumerate(accents)}

    def flexia_no(model) -> int:
        key = json.dumps(model, sort_keys=True, ensure_ascii=False)
        if key not in flexia_index:
            flexia_index[key] = len(flexia)
            flexia.append(model)
        return flexia_index[key]

    def accent_no(model) -> int:
        key = tuple(model)
        if key not in accent_index:
            accent_index[key] = len(accents)
            accents.append(list(model))
        return accent_index[key]

    counts = Counter()
    report = []
    for lemma in data["lemmas"]:
        key = norm(lemma["l"])
        endings = flexia[lemma["f"]]["endings"]
        if key not in wiki or "n" in lemma or codes[endings[0]["gramcode"][:2]]["p"] != "A":
            continue
        if any(codes[e["gramcode"][i:i + 2]]["p"] == "ADJ_SHORT" for e in endings
               for i in range(0, len(e["gramcode"]), 2)):
            counts["already has short forms"] += 1
            continue
        new_forms = []
        for name, values in wiki[key].items():
            for value in values:
                form = plain(value)
                stress: Optional[int] = stress_of_wiki_text(value)
                new_forms.append((form, short_code[name], UNKNOWN_ACCENT if stress is None else stress))
        base = lemma["l"][:len(lemma["l"]) - len(endings[0]["flexia"])]
        old = [base + e["flexia"] for e in endings]
        new_base = common_prefix(old + [f for f, _, _ in new_forms])
        new_endings = [dict(e, flexia=(base + e["flexia"])[len(new_base):]) for e in endings]
        new_endings += [{"flexia": f[len(new_base):], "gramcode": c} for f, c, _ in new_forms]
        lemma["f"] = flexia_no({"endings": new_endings})
        lemma["a"] = accent_no(accents[lemma["a"]] + [a for _, _, a in new_forms])
        counts["adjectives"] += 1
        counts["forms"] += len(new_forms)
        counts["unknown stress"] += sum(1 for _, _, a in new_forms if a == UNKNOWN_ACCENT)
        report.append((lemma["l"], " ".join(f for f, _, _ in new_forms)))
    counts["decisions without an adjective"] = len(added - {norm(r[0]) for r in report})
    with open(args.output, "w") as outp:
        json.dump(data, outp, ensure_ascii=False)
    with open(args.report, "w") as outp:
        outp.write("lemma\tadded forms\n")
        for row in report:
            outp.write("\t".join(row) + "\n")
    print(dict(counts))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--gramtab", default="../data/Russian/gramtab.json")
    parser.add_argument("--wiki", default="result/adjectives.jsonl")
    parser.add_argument("--decisions", default="short_only_wiki.tsv")
    parser.add_argument("--report", default="result/wiki_short_forms_added.tsv")
    args = parser.parse_args()
    main()
