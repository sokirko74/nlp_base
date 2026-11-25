"""
Adds the composite form (`A compos`, композ) to the paradigms of adjectives: the first part of a compound adjective,
written with the hyphen at the end: `ракетно-` (ракетно-космический), `русско-` (русско-японский), `сине-`
(сине-бело-красный), `химико-` (химико-биологический), `англо-` (англо-американский).

The model is very productive, so every adjective in -ый, -ой, -ий gets the form by the rule:
- the stem + `о`: `ракетный` -> `ракетно-`, `золотой` -> `золото-`, `русский` -> `русско-`, `широкий` -> `широко-`;
- after a soft consonant or a sibilant the stem + `е`: `синий` -> `сине-`, `рабочий` -> `рабоче-`, `свежий` -> `свеже-`;
- `-ический` -> `-ико-`: `химический` -> `химико-`, `исторический` -> `историко-`.
Irregular forms with a truncated stem are added too (`IRREGULAR`, frequent first parts of the Flibusta corpus):
`английский` -> `англо-` (and `английско-`), `французский` -> `франко-`, `южный` -> `юго-`.
The form is written with the hyphen, so a word of a text never equals it; the lemmatizer looks for it only for the
first part of a hyphenated word (`predict_hyphen_word`): the lemma of `ракетно-космической` is РАКЕТНО-КОСМИЧЕСКИЙ.
Before, the neuter short form served the same purpose (`ракетно`), but it does not exist for most relative adjectives
(`русско-японский`), and the lemma of the first part replaced the part (РАКЕТНЫЙ-КОСМИЧЕСКИЙ).

If the form does not continue the stem of the paradigm (`англо-` of `английск|ий`), the stem of the flexia model is
shortened to the common beginning of all forms. The gramcode `A compos` is added to gramtab.json if it is missing.

The result should be saved by `slf_convert --to-mrd` with an empty slf file.
"""
import argparse
import itertools
import json
import string
from collections import Counter
from typing import Dict, List, Optional

COMPOSITE = "compos"
UNKNOWN_ACCENT = 255

IRREGULAR: Dict[str, str] = {
    "АНГЛИЙСКИЙ": "АНГЛО", "АВСТРИЙСКИЙ": "АВСТРО", "ФРАНЦУЗСКИЙ": "ФРАНКО", "ГЕРМАНСКИЙ": "ГЕРМАНО",
    "ГРЕЧЕСКИЙ": "ГРЕКО", "ИТАЛЬЯНСКИЙ": "ИТАЛО", "ИСПАНСКИЙ": "ИСПАНО", "ЯПОНСКИЙ": "ЯПОНО", "ФИНСКИЙ": "ФИННО",
    "СЛАВЯНСКИЙ": "СЛАВЯНО", "МОНГОЛЬСКИЙ": "МОНГОЛО", "ТАТАРСКИЙ": "ТАТАРО", "АРАБСКИЙ": "АРАБО",
    "ИНДИЙСКИЙ": "ИНДО", "ИРАНСКИЙ": "ИРАНО", "АФРИКАНСКИЙ": "АФРО", "УГОРСКИЙ": "УГРО", "ЕВРОПЕЙСКИЙ": "ЕВРО",
    "ВОЛЖСКИЙ": "ВОЛГО", "АМЕРИКАНСКИЙ": "АМЕРИКАНО", "ЧЕЧЕНСКИЙ": "ЧЕЧЕНО", "КАРЕЛЬСКИЙ": "КАРЕЛО",
    "РОМАНСКИЙ": "РОМАНО", "МЕДИЦИНСКИЙ": "МЕДИКО", "ЮЖНЫЙ": "ЮГО", "СЕВЕРНЫЙ": "СЕВЕРО",
}


def norm(s: str) -> str:
    return s.upper().replace("Ё", "Е")


def regular_composite(lemma: str) -> Optional[str]:
    if lemma.endswith(("ЫЙ", "ОЙ")):
        return lemma[:-2] + "О"
    if lemma.endswith("ИЙ"):
        stem = lemma[:-2]
        if stem.endswith("ИЧЕСК"):
            return stem[:-5] + "ИКО"
        if stem[-1:] in "КГХ":
            return stem + "О"
        return stem + "Е"
    return None


def common_prefix(words: List[str]) -> str:
    result = words[0]
    for word in words[1:]:
        while not word.startswith(result):
            result = result[:-1]
    return result


def main():
    with open(args.input) as inp:
        data = json.load(inp)
    gramtab = json.load(open(args.gramtab))
    codes = gramtab["gramcodes"]
    flexia, accents = data["flexia_models"], data["accent_models"]
    code = next((c for c, v in codes.items() if v["p"] == "A" and v["g"] == [COMPOSITE]), None)
    counts = Counter()
    if code is None:
        code = next(a + b for a, b in itertools.product(string.ascii_uppercase + string.ascii_lowercase, repeat=2)
                    if a + b not in codes)
        codes[code] = {"p": "A", "g": [COMPOSITE], "f": 0}
        counts["new gramcode " + code] += 1
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

    def pos(gramcode: str) -> str:
        return codes[gramcode[:2]]["p"]

    for lemma in data["lemmas"]:
        endings = flexia[lemma["f"]]["endings"]
        if pos(endings[0]["gramcode"]) != "A" or "n" in lemma:
            continue
        if any(code in e["gramcode"][i:i + 2] for e in endings for i in range(0, len(e["gramcode"]), 2)):
            counts["already has the form"] += 1
            continue
        word = norm(lemma["l"])
        composites = [c for c in (regular_composite(word), IRREGULAR.get(word)) if c]
        if not composites:
            counts["no rule"] += 1
            continue
        base = lemma["l"][:len(lemma["l"]) - len(endings[0]["flexia"])]
        forms = [base + e["flexia"] for e in endings]
        new_base = common_prefix(forms + [c + "-" for c in composites])
        new_endings = [dict(e, flexia=(base + e["flexia"])[len(new_base):]) for e in endings]
        for composite in composites:
            new_endings.append({"flexia": (composite + "-")[len(new_base):], "gramcode": code})
        lemma["f"] = flexia_no({"endings": new_endings})
        lemma["a"] = accent_no(accents[lemma["a"]] + [UNKNOWN_ACCENT] * len(composites))
        counts["adjectives"] += 1
        counts["forms"] += len(composites)
        if len(new_base) < len(base):
            counts["shortened stem"] += 1
    with open(args.output, "w") as outp:
        json.dump(data, outp, ensure_ascii=False)
    with open(args.gramtab, "w") as outp:
        json.dump(gramtab, outp, ensure_ascii=False, indent=4)
    print(dict(counts))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--gramtab", default="../data/Russian/gramtab.json")
    args = parser.parse_args()
    main()
