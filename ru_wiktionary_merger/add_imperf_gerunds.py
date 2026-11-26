"""
Adds the past gerund in -в to imperfective verbs in -овать that have only the gerund in -вши in aot
(`мотивировав` next to `мотивировавши`, `игнорировав`, `делегировав`, `не участвовав`).

781 imperfective verbs in -овать/-евать and ФАВОРИЗИРОВАТЬ had no gerund in -в in their whole paradigm, the decisions
are in `imperf_gerunds.tsv`. The voices: Wiktionary (gives -овав for 764), aot (only -овавши, 10 uses in Flibusta),
the Flibusta frequency of the form in -в and its contexts. The past gerund of an imperfective verb is rare
(`читав` 33 against `прочитав` 15040); most uses are of verbs that are biaspectual in Wiktionary (`мотивировав` 442).
- add (45): Wiktionary and at least two different gerund contexts (`отказался, мотивировав это тем`,
  `ни разу не пробовав`, `игнорировав вопрос`, `не мудрствовав лукаво`, `крест целовав`);
- skip: no form in Flibusta (664: one voice of Wiktionary, `агитировав`), one gerund context (43: `дважды
  варьировав мотив`), other words (30: broken perfectives `по газовав`, typos `он чувствовав голод`, broken participles
  `существовав ших`, Ukrainian text).
The new form takes the gramcode of the form in -вши, the stress is the same vowel (one vowel less from the end).

The result should be saved by `slf_convert --to-mrd` with an empty slf file.
"""
import argparse
import json
from collections import Counter

UNKNOWN_ACCENT = 255


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

    def grammems(gramcode):
        return [codes[gramcode[i:i + 2]] for i in range(0, len(gramcode), 2)]

    added = set()
    for line in open(args.decisions):
        parts = line.rstrip("\n").split("\t")
        if not line.startswith(("#", "lemma\t")) and parts[4] == "add":
            added.add(parts[0])
    counts = Counter()
    report = []
    for lemma in data["lemmas"]:
        word = lemma["l"]
        if word not in added or "n" in lemma:
            continue
        aspect = set(codes[lemma["t"]]["g"]) if lemma.get("t") else set()
        if "imperf" not in aspect:
            continue
        endings = flexia[lemma["f"]]["endings"]
        base = word[:len(word) - len(endings[0]["flexia"])]
        past = [(k, e) for k, e in enumerate(endings) if any(
            c["p"] == "ADV_PARTICIPLE" and "past" in c["g"] for c in grammems(e["gramcode"]))]
        if not past or any((base + e["flexia"]).endswith("В") for _, e in past):
            continue
        vshi = [(k, e) for k, e in past if (base + e["flexia"]).endswith("ВШИ")]
        if len(vshi) != 1:
            counts["no single form in -вши"] += 1
            continue
        k, e = vshi[0]
        form = base + e["flexia"][:-2]
        stress = accents[lemma["a"]][k]
        new_stress = UNKNOWN_ACCENT if stress == UNKNOWN_ACCENT or stress == 0 else stress - 1
        lemma["f"] = flexia_no({"endings": endings + [{"flexia": e["flexia"][:-2], "gramcode": e["gramcode"]}]})
        lemma["a"] = accent_no(accents[lemma["a"]] + [new_stress])
        counts["forms added"] += 1
        counts["unknown stress"] += new_stress == UNKNOWN_ACCENT
        report.append((word, form))
    counts["decisions not applied"] = len(added - {r[0] for r in report})
    with open(args.output, "w") as outp:
        json.dump(data, outp, ensure_ascii=False)
    with open(args.report, "w") as outp:
        outp.write("lemma\tadded form\n")
        for row in report:
            outp.write("\t".join(row) + "\n")
    print(dict(counts))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--gramtab", default="../data/Russian/gramtab.json")
    parser.add_argument("--decisions", default="imperf_gerunds.tsv")
    parser.add_argument("--report", default="result/imperf_gerunds_added.tsv")
    args = parser.parse_args()
    main()
