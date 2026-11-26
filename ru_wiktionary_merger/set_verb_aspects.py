"""
Changes the aspect of the verbs whose aspect in aot is not confirmed by Wiktionary and the Flibusta corpus.

The decisions are in `verb_aspects.tsv` (659 verbs whose aspect differs in aot and Wiktionary). The voices: Wiktionary
(the aspect of the template; its errors are frequent: `вводиться` has `гл ru 4c-т-сяСВ`), aot, the Flibusta corpus
with two tests checked by contexts: the imperfective frame (`будет / начал / стал / перестал / продолжал` + the
infinitive: `будет дуться пару дней`; the modal `надо / можно будет` takes perfectives too and is not counted) and the
past gerund (`отказался, мотивировав это тем`, `купившись на уговоры`), and Claude (a perfective pair: `подрубать` -
`подрубить`). Changed: 60 verbs (20 imperf, 30 imperf,perf, 10 perf); kept: 599 (Flibusta agrees with aot, no corpus
evidence, or the contexts show the aspect of aot: `родить` - `земля перестала родить`, `родив двойню`).

The paradigm follows the aspect, as in aot: the personal forms are `pres` for imperf, `fut` for perf, both for
imperf,perf; perfective verbs have no present participles and no present gerund. A missing personal form is a copy of
the form of the other tense; the present participles and the gerund of a verb that was perfective are built from the
3rd person plural (`клонируют` -> `клонирующий`, `клонируя`) and the 1st person plural (`клонируем` -> `клонируемый`)
with the endings and gramcodes of МОБИЛИЗОВАТЬ / МОБИЛИЗОВАТЬСЯ, only if Wiktionary gives them (not `перелазимый`);
the stress is that of the Wiktionary form (`нано́сятся`, but `нанося́щийся`).

The result should be saved by `slf_convert --to-mrd` with an empty slf file.
"""
import argparse
import json
import unicodedata
from collections import Counter
from typing import List, Optional, Tuple

UNKNOWN_ACCENT = 255
VOWELS = "АЕЁИОУЫЭЮЯ"
PRESENT_FORMS = ("PARTICIPLE", "PARTICIPLE_SHORT", "ADV_PARTICIPLE")
HUSHING = "ЖШЧЩ"


def vowel_positions(word: str) -> List[int]:
    return [i for i, c in enumerate(word) if c in VOWELS]


def stressed_char(word: str, accent: int) -> Optional[int]:
    """the position from the start of the vowel number `accent` from the end"""
    vowels = vowel_positions(word)
    if accent == UNKNOWN_ACCENT or accent >= len(vowels):
        return None
    return vowels[len(vowels) - 1 - accent]


def accent_of(word: str, char: Optional[int]) -> int:
    vowels = vowel_positions(word)
    if char is None or char not in vowels:
        return UNKNOWN_ACCENT
    return len(vowels) - 1 - vowels.index(char)


def main():
    with open(args.input) as inp:
        data = json.load(inp)
    codes = json.load(open(args.gramtab))["gramcodes"]
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

    def split(gramcode: str) -> List[str]:
        return [gramcode[i:i + 2] for i in range(0, len(gramcode), 2)]

    code_by_grammems = {}
    for code, value in codes.items():
        code_by_grammems.setdefault((value["p"], frozenset(value["g"])), code)

    def other_tense(code: str, tense: str) -> str:
        value = codes[code]
        grammems = (set(value["g"]) - {"pres", "fut"}) | {tense}
        return code_by_grammems[(value["p"], frozenset(grammems))]

    def is_verb(lemma) -> bool:
        return codes[flexia[lemma["f"]]["endings"][0]["gramcode"][:2]]["p"] in ("INFINITIVE", "V")

    def find(word: str):
        found = [lemma for lemma in data["lemmas"] if lemma["l"] == word and "n" not in lemma and is_verb(lemma)]
        if len(found) != 1:
            raise ValueError(f"{len(found)} verbs {word}")
        return found[0]

    def forms(lemma) -> Tuple[str, List[Tuple[str, str, int]]]:
        endings = flexia[lemma["f"]]["endings"]
        if any("prefix" in e for e in endings):
            raise ValueError("a prefix in " + lemma["l"])
        base = lemma["l"][:len(lemma["l"]) - len(endings[0]["flexia"])]
        return base, [(base + e["flexia"], e["gramcode"], a) for e, a in zip(endings, accents[lemma["a"]])]

    def present_model(word: str, kind: str):
        """the endings of the present participles of the model after the stem `-ющ` (kind Щ, from the 3rd person
        plural) or the 1st person plural `-ем` (kind М)"""
        _, model_forms = forms(find(word))
        refl = word.endswith("СЯ")
        person = {"Щ": {"3p", "pl"}, "М": {"1p", "pl"}}[kind]
        finite = next(f for f, c, _ in model_forms if codes[c[:2]]["p"] == "V" and person <= set(codes[c[:2]]["g"]))
        finite = finite[:-2] if refl else finite
        stem = finite[:-1] + "Щ" if kind == "Щ" else finite
        result = []
        for form, gramcode, _ in model_forms:
            value = codes[gramcode[:2]]
            if value["p"] in ("PARTICIPLE", "PARTICIPLE_SHORT") and "pres" in value["g"] and \
                    ("act" in value["g"]) == (kind == "Щ"):
                if not form.startswith(stem):
                    raise ValueError(f"{form} does not continue {stem}")
                result.append((form[len(stem):], gramcode))
        return result

    models = {(refl, kind): present_model("МОБИЛИЗОВАТЬСЯ" if refl else "МОБИЛИЗОВАТЬ", kind)
              for refl in (False, True) for kind in ("Щ", "М") if not (refl and kind == "М")}
    for (refl, kind), endings in models.items():
        if not endings:
            raise ValueError(f"no model endings {refl} {kind}")

    wiki = {}
    for line in open(args.wiki):
        article = json.loads(line)
        wiki.setdefault(article["title"].upper().replace("Ё", "Е"), {}).update(article["generated_forms"])

    def wiki_form(word: str, name: str) -> Optional[str]:
        values = wiki.get(word, {}).get(name)
        if not values:
            return None
        return unicodedata.normalize("NFC", "".join(
            c for c in unicodedata.normalize("NFD", values[0]) if c not in "\u0301\u0300")).upper().replace("|", "")

    def wiki_stress(word: str, name: str) -> Optional[int]:
        """the position of the stressed vowel in the Wiktionary form `name`"""
        value = unicodedata.normalize("NFD", wiki[word][name][0].replace("|", ""))
        position = None
        plain = 0
        for c in value:
            if c == "\u0301":
                if position is not None:
                    return None
                position = plain - 1
            elif not unicodedata.combining(c):
                plain += 1
        return position

    decisions = []
    for line in open(args.decisions):
        parts = line.rstrip("\n").split("\t")
        if line.startswith(("#", "lemma\t")) or parts[6] == "keep":
            continue
        decisions.append((parts[0], parts[6]))
    counts = Counter()
    report = []
    for word, new_aspect in decisions:
        lemma = find(word)
        type_value = codes[lemma["t"]]
        old_aspect = ",".join(sorted(set(type_value["g"]) & {"perf", "imperf"}))
        new = set(new_aspect.split(","))
        base, old_forms = forms(lemma)
        refl = word.endswith(("СЯ", "СЬ"))
        transitive = "trans" in type_value["g"]
        personal = [(f, c, a) for f, c, a in old_forms if codes[c[:2]]["p"] == "V"
                    and codes[c[:2]]["g"] and ({"pres", "fut"} & set(codes[c[:2]]["g"]))]
        rest = [x for x in old_forms if x not in personal]
        by_tense = {t: [(f, c, a) for f, c, a in personal if t in codes[c[:2]]["g"]] for t in ("pres", "fut")}
        source = by_tense["pres"] or by_tense["fut"]
        new_forms = []
        for tense in ("pres", "fut"):
            if (tense == "pres" and "imperf" in new) or (tense == "fut" and "perf" in new):
                if by_tense[tense]:
                    new_forms += by_tense[tense]
                else:
                    new_forms += [(f, "".join(other_tense(x, tense) for x in split(c)), a) for f, c, a in source]
        present = [(f, c, a) for f, c, a in rest if codes[c[:2]]["p"] in PRESENT_FORMS and "pres" in codes[c[:2]]["g"]]
        rest = [x for x in rest if x not in present]
        added_present = []
        if "imperf" in new:
            if present:
                rest += present
            else:
                third = [(f, a) for f, c, a in source if {"3p", "pl"} <= set(codes[c[:2]]["g"])]
                first = [(f, a) for f, c, a in source if {"1p", "pl"} <= set(codes[c[:2]]["g"])]
                if not third:
                    raise ValueError("no 3pl of " + word)
                form3 = third[0][0]
                plain3 = form3[:-2] if refl else form3
                stem = plain3[:-1]
                group = [(stem + "Щ" + ending, gramcode) for ending, gramcode in models[(refl, "Щ")]]
                if wiki_form(word, "ptcp-prs-act-nom-sg-m"):
                    if wiki_form(word, "ptcp-prs-act-nom-sg-m") != group[0][0]:
                        raise ValueError(f"{group[0][0]} is not {wiki_form(word, 'ptcp-prs-act-nom-sg-m')}")
                    stress = wiki_stress(word, "ptcp-prs-act-nom-sg-m")
                    added_present += [(f, c, accent_of(f, stress)) for f, c in group]
                gerund = plain3[:-2] + ("А" if plain3[-3] in HUSHING else "Я") + ("СЬ" if refl else "")
                gerund_code = code_by_grammems[("ADV_PARTICIPLE", frozenset({"act", "pres"}))]
                if wiki_form(word, "ger-prs"):
                    if wiki_form(word, "ger-prs") != gerund:
                        raise ValueError(f"{gerund} is not {wiki_form(word, 'ger-prs')}")
                    added_present.append((gerund, gerund_code, accent_of(gerund, wiki_stress(word, "ger-prs"))))
                if transitive and not refl and first and wiki_form(word, "ptcp-prs-pass-nom-sg-m"):
                    form1 = first[0][0]
                    group = [(form1 + ending, gramcode) for ending, gramcode in models[(False, "М")]]
                    if wiki_form(word, "ptcp-prs-pass-nom-sg-m") != group[0][0]:
                        raise ValueError(f"{group[0][0]} is not {wiki_form(word, 'ptcp-prs-pass-nom-sg-m')}")
                    stress = wiki_stress(word, "ptcp-prs-pass-nom-sg-m")
                    added_present += [(f, c, accent_of(f, stress)) for f, c in group]
                rest += added_present
        all_forms = [x for x in old_forms if x in rest or x in new_forms]
        all_forms += [x for x in new_forms + added_present if x not in all_forms]
        new_base = base
        for form, _, _ in all_forms:
            while not form.startswith(new_base):
                new_base = new_base[:-1]
        endings = [{"flexia": f[len(new_base):], "gramcode": c} for f, c, _ in all_forms]
        lemma["f"] = flexia_no({"endings": endings})
        lemma["a"] = accent_no([a for _, _, a in all_forms])
        new_type = (set(type_value["g"]) - {"perf", "imperf"}) | new
        lemma["t"] = code_by_grammems[("", frozenset(new_type))]
        old_set = {(f, c) for f, c, _ in old_forms}
        new_set = {(f, c) for f, c, _ in all_forms}
        counts[f"{old_aspect} -> {new_aspect}"] += 1
        counts["forms added"] += len(new_set - old_set)
        counts["forms removed"] += len(old_set - new_set)
        report.append((word, old_aspect, new_aspect, str(len(new_set - old_set)), str(len(old_set - new_set)),
                       " ".join(sorted({f for f, c, _ in added_present}))))
    with open(args.output, "w") as outp:
        json.dump(data, outp, ensure_ascii=False)
    with open(args.report, "w") as outp:
        outp.write("lemma\told aspect\tnew aspect\tforms added\tforms removed\tnew present participles, gerund\n")
        for row in report:
            outp.write("\t".join(row) + "\n")
    print(dict(counts))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--gramtab", default="../data/Russian/gramtab.json")
    parser.add_argument("--wiki", default="result/verbs.jsonl")
    parser.add_argument("--decisions", default="verb_aspects.tsv")
    parser.add_argument("--report", default="result/verb_aspects_changed.tsv")
    args = parser.parse_args()
    main()
