"""
Removes the past passive participles of aot that neither Wiktionary nor the corpus supports
(`понабреханный`, `прилганный`, `превалированный`, `отчаленный`).

The candidates are the verbs whose aot paradigm has the past passive participle and whose Wiktionary paradigm has
none (368); the decisions are in `participles_only_aot.tsv`. The voices: aot, Wiktionary, the frequency of the
participle forms without homographs in Flibusta + Wikipedia (the ddc server on migalka), the contexts, Claude.
The silence of Wiktionary is a voice only if the verb is intransitive there: the table of an imperfective verb
`гл ru 2a` has no past passive participle without the parameter `ПричСтрадПрош`.
- remove (36): Wiktionary gives the verb as intransitive, the corpus has no form (29) or only other words (7:
  `отчаленный крик` for `отчаянный`, `повранном поясе` for `повреждённом`, `удружена левица` in Serbian), and the
  verb has no transitive use (Claude): `понабрехать`, `превалировать`, `диффундировать`, `сигналить`, `съязвить`;
- keep: Wiktionary has the form in another article (26: `концентрированный`, `провоженный` of `проводить`), the table
  hides it (185), the corpus has the participle (54: `отёсанный`, `нафаршированный`; 26 with one or two uses:
  `болтанные яичницы`, `был матерно отлаян`), a transitive use (27: `отбурить скважину`, `щепать лучину`), doubtful
  (14: `воскликнуть`, `рапортовать`).
All the full and short forms of the past passive participle of the lemma are removed.

The result should be saved by `slf_convert --to-mrd` with an empty slf file.
"""
import argparse
import json
from collections import Counter


def main():
    with open(args.input) as inp:
        data = json.load(inp)
    codes = json.load(open(args.gramtab))["gramcodes"]
    removed = set()
    for line in open(args.decisions):
        parts = line.rstrip("\n").split("\t")
        if not line.startswith(("#", "lemma\t")) and parts[4] == "remove":
            removed.add(parts[0])
    flexia, accents = data["flexia_models"], data["accent_models"]

    def is_participle(gramcode: str) -> bool:
        value = codes[gramcode[:2]]
        return value["p"] in ("PARTICIPLE", "PARTICIPLE_SHORT") and "pass" in value["g"] and "past" in value["g"]

    counts = Counter()
    report = []
    for lemma in data["lemmas"]:
        if lemma["l"] not in removed or "n" in lemma:
            continue
        endings = flexia[lemma["f"]]["endings"]
        if codes[endings[0]["gramcode"][:2]]["p"] not in ("INFINITIVE", "V"):
            continue
        pairs = list(zip(endings, accents[lemma["a"]]))
        kept = [(e, a) for e, a in pairs if not is_participle(e["gramcode"])]
        if len(kept) == len(pairs):
            continue
        base = lemma["l"][:len(lemma["l"]) - len(endings[0]["flexia"])]
        model = {"endings": [e for e, _ in kept]}
        if model in flexia:
            lemma["f"] = flexia.index(model)
        else:
            lemma["f"] = len(flexia)
            flexia.append(model)
        accent_model = [a for _, a in kept]
        if accent_model in accents:
            lemma["a"] = accents.index(accent_model)
        else:
            lemma["a"] = len(accents)
            accents.append(accent_model)
        counts["verbs"] += 1
        counts["forms"] += len(pairs) - len(kept)
        report.append((lemma["l"], " ".join(sorted({base + e["flexia"] for e, _ in pairs
                                                    if is_participle(e["gramcode"])}))))
    counts["decisions not applied"] = len(removed - {r[0] for r in report})
    with open(args.output, "w") as outp:
        json.dump(data, outp, ensure_ascii=False)
    with open(args.report, "w") as outp:
        outp.write("lemma\tremoved forms\n")
        for row in report:
            outp.write("\t".join(row) + "\n")
    print(dict(counts))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--gramtab", default="../data/Russian/gramtab.json")
    parser.add_argument("--decisions", default="participles_only_aot.tsv")
    parser.add_argument("--report", default="result/aot_participles_removed.tsv")
    args = parser.parse_args()
    main()
