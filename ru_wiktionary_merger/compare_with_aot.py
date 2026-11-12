"""
Compares two dictionaries of MorphWizard (morphs.json with the same gramtab): the Wiktionary dictionary,
loaded from the slf file by `slf_convert --to-mrd`, and the dictionary of aot.ru.

A paradigm is the set of pairs (form, POS and grammems), `ё` is compared as `е`, since aot writes `ё`
only in a few words. Paradigms are matched by the lemma and the group of the POS of the lemma (an adjective
of Wiktionary is matched with an ordinal numeral or a pronoun-adjective of aot); of several homonyms the most
similar paradigm is taken. The differences of a pair are written as endings relative to the common stem of
both paradigms, pairs with the same differences make a group: e.g. aot has the second genitive `-у`.
Lemmas with no pair are linked with the paradigms of the other dictionary by their forms: `лемма -> лемма2`.
Each part of a word (key `n` of a lemma) is compared as a separate paradigm, since a part corresponds to an article
of Wiktionary: воскресенье is the second part of воскресение in aot.
The grammem `arch` is removed before the comparison: Wiktionary has no such mark, and a form accepted into aot
as obsolete (`Абрамскою`) must not come up as a difference again. An obsolete form of aot that Wiktionary does not
give (`вспомня`, see mark_arch_gerunds.py) is not a difference either.
The file compare_decisions.tsv keeps the differences that were reviewed and accepted: such a pair goes to accepted.tsv,
not to the groups. A decision holds for the exact differences only, so a pair that changes comes up again.
"""
import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

AOT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "Russian")

# the POS of the lemma (the first form) -> the group used to match paradigms
POS_GROUPS: Dict[str, str] = {
    "N": "N",
    "A": "A", "ADJ_SHORT": "A", "PA": "A", "ORD_NUM": "A",
    "INFINITIVE": "V", "V": "V", "PARTICIPLE": "V", "PARTICIPLE_SHORT": "V", "ADV_PARTICIPLE": "V",
    "PRON": "PRON", "P_PRED": "PRON",
    "NUM": "NUM",
}

Line = Tuple[str, str]  # (form, "POS grammems") with sorted grammems


class TDictionary:
    def __init__(self, folder: str, gramtab: Dict[str, Tuple[str, str]]):
        with open(os.path.join(folder, "morphs.json")) as inp:
            data = json.load(inp)
        self.flexia_models = data["flexia_models"]
        self.lemmas = []
        for lemma in data["lemmas"]:
            self.lemmas.append(lemma)
            base = lemma["l"][:len(lemma["l"]) - len(self.flexia_models[lemma["f"]]["endings"][0]["flexia"])]
            for flexia_no, _ in lemma.get("n", []):
                part_lemma = base + self.flexia_models[flexia_no]["endings"][0]["flexia"]
                self.lemmas.append({"l": part_lemma, "f": flexia_no, "t": lemma.get("t")})
        self.gramtab = gramtab
        self.by_key: Dict[Tuple[str, str], List[int]] = defaultdict(list)
        for index, lemma in enumerate(self.lemmas):
            self.by_key[(normalize(lemma["l"]), self.group(index))].append(index)

    def first_gramcode(self, index: int) -> str:
        return self.flexia_models[self.lemmas[index]["f"]]["endings"][0]["gramcode"][:2]

    def group(self, index: int) -> str:
        pos = self.gramtab[self.first_gramcode(index)][0]
        return POS_GROUPS.get(pos, pos)

    def type_grammems(self, index: int) -> str:
        code = self.lemmas[index].get("t")
        return self.gramtab[code][1] if code else ""

    def lines(self, index: int, arch_only: bool = False) -> Set[Line]:
        """
        the forms with grammems, without `arch`; `arch_only`: only the forms marked as `arch`
        """
        lemma = self.lemmas[index]
        endings = self.flexia_models[lemma["f"]]["endings"]
        base = lemma["l"][:len(lemma["l"]) - len(endings[0]["flexia"])]
        result = set()
        for ending in endings:
            form = normalize(ending.get("prefix", "") + base + ending["flexia"])
            codes = ending["gramcode"]
            for i in range(0, len(codes), 2):
                pos, grammems = self.gramtab[codes[i:i + 2]]
                if arch_only and "arch" not in grammems.split(","):
                    continue
                grammems = ",".join(g for g in grammems.split(",") if g != "arch")
                result.add((form, f"{pos} {grammems}".strip()))
        return result


def normalize(form: str) -> str:
    return form.replace("Ё", "Е").replace("ё", "е")


def read_gramtab(folder: str) -> Dict[str, Tuple[str, str]]:
    with open(os.path.join(folder, "gramtab.json")) as inp:
        codes = json.load(inp)["gramcodes"]
    return {code: (v["p"], ",".join(sorted(v["g"]))) for code, v in codes.items()}


def common_prefix(words: List[str]) -> str:
    first, last = min(words), max(words)
    size = 0
    while size < min(len(first), len(last)) and first[size] == last[size]:
        size += 1
    return first[:size]


def similarity(a: Set[Line], b: Set[Line]) -> float:
    return len(a & b) / len(a | b)


def difference_signature(wiki: Set[Line], aot: Set[Line]) -> Tuple[str, ...]:
    """
    The differences as endings: `gen,mas,sg: wiki - ; aot -У`, the endings are cut off the common stem
    of all forms of both paradigms, so that different lemmas of the same inflection have the same signature.
    """
    stem = len(common_prefix([form for form, _ in wiki | aot]))
    by_grammems: Dict[str, Tuple[Set[str], Set[str]]] = defaultdict(lambda: (set(), set()))
    for form, grammems in wiki - aot:
        by_grammems[grammems][0].add("-" + form[stem:])
    for form, grammems in aot - wiki:
        by_grammems[grammems][1].add("-" + form[stem:])
    return tuple(f"{grammems}: {' '.join(sorted(w)) or '0'} / {' '.join(sorted(a)) or '0'}"
                 for grammems, (w, a) in sorted(by_grammems.items()))


# the grammems that name a kind of forms in the overview of differences, the case, gender and number do not
CATEGORY_GRAMMEMS = {"compar", "2", "voc", "0", "imp", "pass", "act", "past", "pres", "fut", "conv", "arch", "abbr",
                     "name", "patr", "superl"}


def difference_categories(wiki: Set[Line], aot: Set[Line]) -> Set[str]:
    """
    Kinds of differing forms: `ADJ_SHORT: only aot`, `N 2: only aot` (the second genitive or prepositional),
    `ADV_PARTICIPLE past: different`.
    """
    by_kind: Dict[str, List[Set[str]]] = defaultdict(lambda: [set(), set()])
    for form, grammems in wiki:
        pos, _, rest = grammems.partition(" ")
        by_kind[" ".join([pos] + [g for g in rest.split(",") if g in CATEGORY_GRAMMEMS])][0].add((form, grammems))
    for form, grammems in aot:
        pos, _, rest = grammems.partition(" ")
        by_kind[" ".join([pos] + [g for g in rest.split(",") if g in CATEGORY_GRAMMEMS])][1].add((form, grammems))
    result = set()
    for kind, (w, a) in by_kind.items():
        if w == a:
            continue
        result.add(f"{kind}: " + ("only aot" if not w else "only wiki" if not a else "different"))
    return result


def wiki_templates(folder: str) -> Dict[str, List[str]]:
    """
    The Wiktionary templates of lemmas, to show them in the groups.
    """
    result = defaultdict(list)
    for name in ("nouns", "adjectives", "verbs", "other", "surnames"):
        path = os.path.join(folder, name + ".jsonl")
        if not os.path.exists(path):
            continue
        for line in open(path):
            article = json.loads(line)
            template = article["morpho"].get("template", "")
            key = normalize(article["title"].upper())
            if template not in result[key]:
                result[key].append(template)
    return result


def best_pairs(wiki: TDictionary, aot: TDictionary, wiki_indices: List[int], aot_indices: List[int]) \
        -> List[Tuple[int, int, Set[Line], Set[Line]]]:
    """
    Pairs of homonyms with the same lemma and POS group, the most similar first.
    """
    wiki_lines = {i: wiki.lines(i) for i in wiki_indices}
    aot_lines = {i: aot.lines(i) for i in aot_indices}
    candidates = sorted(((similarity(wiki_lines[w], aot_lines[a]), w, a) for w in wiki_indices for a in aot_indices),
                        reverse=True)
    used_wiki, used_aot, result = set(), set(), []
    for _, w, a in candidates:
        if w not in used_wiki and a not in used_aot:
            used_wiki.add(w)
            used_aot.add(a)
            result.append((w, a, wiki_lines[w], aot_lines[a]))
    return result


def read_decisions(path: str) -> Dict[Tuple[str, str, str], str]:
    """
    :return: (lemma, POS group, differences) -> the reason of the decision
    """
    with open(path) as inp:
        rows = csv.DictReader(inp, delimiter="\t", quoting=csv.QUOTE_NONE)
        return {(row["lemma"], row["pos"], row["differences"]): row["reason"] for row in rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wiki-folder", default="result/mrd")
    parser.add_argument("--aot-folder", default=AOT_FOLDER)
    parser.add_argument("--jsonl-folder", default="result", help="the generated paradigms, for the templates")
    parser.add_argument("--output-folder", default="result/compare")
    parser.add_argument("--examples", type=int, default=10)
    parser.add_argument("--decisions", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                            "compare_decisions.tsv"))
    args = parser.parse_args()
    os.makedirs(args.output_folder, exist_ok=True)

    gramtab = read_gramtab(args.aot_folder)
    wiki = TDictionary(args.wiki_folder, gramtab)
    aot = TDictionary(args.aot_folder, gramtab)
    templates = wiki_templates(args.jsonl_folder)
    decisions = read_decisions(args.decisions)
    used_decisions = set()

    stats = Counter()
    groups: Dict[Tuple[str, Tuple[str, ...]], List[str]] = defaultdict(list)
    group_templates: Dict[Tuple[str, Tuple[str, ...]], Counter] = defaultdict(Counter)
    type_diffs = Counter()
    categories = Counter()
    unmatched_wiki: List[int] = []
    matched_aot: Set[int] = set()
    with open(os.path.join(args.output_folder, "pairs.tsv"), "w") as pairs_out, \
            open(os.path.join(args.output_folder, "accepted.tsv"), "w") as accepted_out:
        pairs_out.write("lemma\tpos\twiki template\taot flexia model\tdifferences\n")
        accepted_out.write("lemma\tpos\treason\tdifferences\n")
        for key, wiki_indices in sorted(wiki.by_key.items()):
            lemma, group = key
            aot_indices = aot.by_key.get(key, [])
            pairs = best_pairs(wiki, aot, wiki_indices, aot_indices) if aot_indices else []
            paired = {w for w, _, _, _ in pairs}
            unmatched_wiki.extend(i for i in wiki_indices if i not in paired)
            for w, a, wiki_lines, aot_lines in pairs:
                # an obsolete form of aot that Wiktionary does not give is not a difference (вспомня)
                aot_lines = aot_lines - (aot.lines(a, arch_only=True) - wiki_lines)
                matched_aot.add(a)
                stats[(group, "pairs")] += 1
                wiki_type, aot_type = wiki.type_grammems(w), aot.type_grammems(a)
                if wiki_type != aot_type:
                    type_diffs[(group, wiki_type, aot_type)] += 1
                if wiki_lines == aot_lines:
                    stats[(group, "equal")] += 1
                    continue
                signature = difference_signature(wiki_lines, aot_lines)
                decision_key = (lemma, group, " | ".join(signature))
                if decision_key in decisions:
                    used_decisions.add(decision_key)
                    stats[(group, "accepted")] += 1
                    accepted_out.write(f"{lemma}\t{group}\t{decisions[decision_key]}\t{decision_key[2]}\n")
                    continue
                for category in difference_categories(wiki_lines, aot_lines):
                    categories[(group, category)] += 1
                groups[(group, signature)].append(lemma)
                template = " ".join(templates.get(lemma, []))
                group_templates[(group, signature)][template] += 1
                pairs_out.write(f"{lemma}\t{group}\t{template}\t{aot.lemmas[a]['f']}\t{' | '.join(signature)}\n")

    # forms of the unmatched paradigms: is a lemma of one dictionary a form of a lemma of the other?
    aot_forms: Dict[Line, Set[int]] = defaultdict(set)
    unmatched_aot = [i for i in range(len(aot.lemmas)) if i not in matched_aot]
    for i in unmatched_aot:
        for line in aot.lines(i):
            aot_forms[line].add(i)
    with open(os.path.join(args.output_folder, "only_wiki.tsv"), "w") as outp:
        outp.write("lemma\tpos\twiki template\tshared forms with aot lemmas\n")
        for i in unmatched_wiki:
            group = wiki.group(i)
            stats[(group, "only wiki")] += 1
            shared = Counter()
            for line in wiki.lines(i):
                for a in aot_forms.get(line, ()):
                    shared[aot.lemmas[a]["l"] + " " + aot.group(a)] += 1
            if shared:
                stats[(group, "only wiki, shares forms")] += 1
            lemma = normalize(wiki.lemmas[i]["l"])
            outp.write(f"{lemma}\t{group}\t{' '.join(templates.get(lemma, []))}\t"
                       f"{', '.join(f'{l} ({n})' for l, n in shared.most_common(3))}\n")
    with open(os.path.join(args.output_folder, "only_aot.tsv"), "w") as outp:
        outp.write("lemma\tpos\ttype grammems\n")
        for i in unmatched_aot:
            group = aot.group(i)
            stats[(group, "only aot")] += 1
            outp.write(f"{aot.lemmas[i]['l']}\t{group}\t{aot.type_grammems(i)}\n")

    with open(os.path.join(args.output_folder, "groups.tsv"), "w") as outp:
        outp.write("count\tpos\tdifferences (grammems: wiki endings / aot endings)\twiki templates\texamples\n")
        for (group, signature), lemmas in sorted(groups.items(), key=lambda g: -len(g[1])):
            top_templates = ", ".join(f"{t} ({n})" for t, n in group_templates[(group, signature)].most_common(3))
            outp.write(f"{len(lemmas)}\t{group}\t{' | '.join(signature)}\t{top_templates}\t"
                       f"{', '.join(lemmas[:args.examples])}\n")
    with open(os.path.join(args.output_folder, "type_grammems.tsv"), "w") as outp:
        outp.write("count\tpos\twiki\taot\n")
        for (group, wiki_type, aot_type), count in type_diffs.most_common():
            outp.write(f"{count}\t{group}\t{wiki_type}\t{aot_type}\n")

    with open(os.path.join(args.output_folder, "categories.tsv"), "w") as outp:
        outp.write("pairs\tpos\tkind of forms: where they are\n")
        for (group, category), count in sorted(categories.items(), key=lambda c: (c[0][0], -c[1])):
            outp.write(f"{count}\t{group}\t{category}\n")

    pos_list = sorted({group for group, _ in stats})
    columns = ["pairs", "equal", "accepted", "only wiki", "only wiki, shares forms", "only aot"]
    with open(os.path.join(args.output_folder, "summary.tsv"), "w") as outp:
        outp.write("pos\t" + "\t".join(columns) + "\n")
        for group in pos_list:
            outp.write(group + "\t" + "\t".join(str(stats[(group, c)]) for c in columns) + "\n")
    print(open(os.path.join(args.output_folder, "summary.tsv")).read())
    print(f"groups of differences: {len(groups)}")
    for lemma, group, _ in sorted(set(decisions) - used_decisions):
        print(f"a decision does not match any pair: {lemma} {group}")


if __name__ == "__main__":
    main()
