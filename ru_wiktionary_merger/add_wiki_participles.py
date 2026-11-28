"""
Adds the past passive participles that Wiktionary gives and aot has in no lemma (`отпразднованный`, `покаранный`,
`обмакнутый`, `пнутый`, `стрельнутый`).

The candidates are the verbs whose Wiktionary paradigm has the past passive participle and whose aot paradigm has
none, and the nominative of the participle is not a form of aot at all (`пройденный` of the table of `проходить` is
the participle of `пройти` in aot). The decisions are in `participles_only_wiki.tsv`. The voices: Wiktionary, the
frequency of the participle forms without homographs in Flibusta + Wikipedia (the ddc server), the contexts.
- add (78): the contexts show the participle (`с блеском отпраздновано`, `обидчик покаран`, `пнутый скоморох`,
  `закурил стрельнутую сигарету`, `был зашикан`, `по сусекам скребён`);
- skip: no form in the corpus (302: one voice of Wiktionary, `шевельнутый`), one use (42), other words in the contexts
  or fewer than two participle uses (42: `вран`, `каран-дашик`, `снована` for `основана`), forms that are forms of
  other words (22: `бешен` of `бешеный`, `ждан`, `минут`; the user's condition: no new homonymy with other words),
  the participle of another verb in the table (7: `сверженный` of `свергнуть` for `сверзить`), adjectives
  (`шибанутый`, `долбанутый`, `гребанутый`: `crazy`).
The short form in -нут of a verb in -нуть is also its 3rd person plural future (`толкнут`), as in 454 of the 455 aot
verbs in -нуть with the participle: a homonymy within the paradigm is kept.
The forms and their gramcodes are taken from the Wiktionary dictionary `result/mrd` (its gramtab is the aot one without
the codes added later), the stress from `result/verbs.jsonl` (the slf of Wiktionary has no stress marks).

The result should be saved by `slf_convert --to-mrd` with an empty slf file.
"""
import argparse
import json
import unicodedata
from collections import Counter

UNKNOWN_ACCENT = 255
VOWELS = "АЕЁИОУЫЭЮЯ"


def plain_and_accent(value: str):
    """`пну́т|ый` -> ("ПНУТЫЙ", the stressed vowel from the end or 255); the slf of Wiktionary has no stress marks"""
    letters, position = [], None
    for c in unicodedata.normalize("NFD", value.replace("|", "")):
        if c == "\u0301":
            position = len(letters) - 1
        elif c != "\u0300":
            letters.append(c)
    if position is None:
        word = unicodedata.normalize("NFC", "".join(letters)).upper()
        # `напылённ|ый`: ё is stressed without a mark
        if word.count("Ё") == 1:
            vowels = [i for i, c in enumerate(word) if c in VOWELS]
            return word, len(vowels) - 1 - vowels.index(word.index("Ё"))
        return word, UNKNOWN_ACCENT
    marked = unicodedata.normalize("NFC", "".join(letters[:position + 1]) + "\u0001" + "".join(letters[position + 1:]))
    position = marked.index("\u0001") - 1
    word = marked.replace("\u0001", "").upper()
    vowels = [i for i, c in enumerate(word) if c in VOWELS]
    return word, len(vowels) - 1 - vowels.index(position) if position in vowels else UNKNOWN_ACCENT


def main():
    with open(args.input) as inp:
        data = json.load(inp)
    wiki = json.load(open(args.wiki))
    codes = json.load(open(args.gramtab))["gramcodes"]
    added = set()
    for line in open(args.decisions):
        parts = line.rstrip("\n").split("\t")
        if not line.startswith(("#", "lemma\t")) and parts[4] == "add":
            added.add(parts[0])

    def is_participle(gramcode: str) -> bool:
        value = codes[gramcode[:2]]
        return value["p"] in ("PARTICIPLE", "PARTICIPLE_SHORT") and "pass" in value["g"] and "past" in value["g"]

    def is_verb(model) -> bool:
        return codes[model["endings"][0]["gramcode"][:2]]["p"] in ("INFINITIVE", "V")

    def forms(dictionary, lemma):
        endings = dictionary["flexia_models"][lemma["f"]]["endings"]
        base = lemma["l"][:len(lemma["l"]) - len(endings[0]["flexia"])]
        return [(base + e["flexia"], e["gramcode"], a)
                for e, a in zip(endings, dictionary["accent_models"][lemma["a"]])]

    stress = {}
    for line in open(args.verbs):
        article = json.loads(line)
        word = article["title"].upper().replace("Ё", "Е")
        if word in added:
            for name, values in article["generated_forms"].items():
                if name.startswith("ptcp-pst-pass"):
                    for value in values:
                        form, accent = plain_and_accent(value)
                        if accent != UNKNOWN_ACCENT:
                            stress.setdefault(word, {})[form.replace("Ё", "Е")] = accent
    wiki_participles = {}
    for lemma in wiki["lemmas"]:
        if lemma["l"] in added and is_verb(wiki["flexia_models"][lemma["f"]]):
            participle = [(f, c, stress.get(lemma["l"], {}).get(f.replace("Ё", "Е"), a))
                          for f, c, a in forms(wiki, lemma) if is_participle(c)]
            if participle:
                wiki_participles.setdefault(lemma["l"], []).append(participle)
    counts = Counter()
    report = []
    flexia, accents = data["flexia_models"], data["accent_models"]
    for word in sorted(added):
        variants = wiki_participles.get(word, [])
        if len(variants) != 1:
            counts[f"{len(variants)} Wiktionary paradigms with the participle"] += 1
            continue
        targets = [lemma for lemma in data["lemmas"] if lemma["l"] == word and "n" not in lemma
                   and is_verb(flexia[lemma["f"]]) and not any(is_participle(c) for _, c, _ in forms(data, lemma))]
        if len(targets) != 1:
            counts[f"{len(targets)} aot verbs without the participle"] += 1
            continue
        lemma = targets[0]
        all_forms = forms(data, lemma) + variants[0]
        base = lemma["l"]
        for form, _, _ in all_forms:
            while not form.startswith(base):
                base = base[:-1]
        model = {"endings": [{"flexia": f[len(base):], "gramcode": c} for f, c, _ in all_forms]}
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
        counts["forms"] += len(variants[0])
        counts["unknown stress"] += sum(1 for _, _, a in variants[0] if a == UNKNOWN_ACCENT)
        report.append((word, " ".join(sorted({f for f, _, _ in variants[0]}))))
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
    parser.add_argument("--wiki", default="result/mrd/morphs.json")
    parser.add_argument("--verbs", default="result/verbs.jsonl")
    parser.add_argument("--gramtab", default="../data/Russian/gramtab.json")
    parser.add_argument("--decisions", default="participles_only_wiki.tsv")
    parser.add_argument("--report", default="result/wiki_participles_added.tsv")
    args = parser.parse_args()
    main()
