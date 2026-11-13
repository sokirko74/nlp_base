"""
Writes the generated paradigms (result/*.jsonl) as one slf file of MorphWizard, see src/slf.py.
A homonym whose paradigm is a part of the paradigm of another one (`снос 1`, `снос 2` with `сносу`) is not written.
The slf file is loaded into a dictionary of aot.ru with `slf_to_mrd` (nlp_base).
"""
import argparse
import json
import os
from collections import Counter

from src.slf import TParadigm, adjective_paradigm, noun_paradigm, other_paradigms, surname_paradigm, \
    verb_paradigm

SOURCES = ["nouns", "adjectives", "verbs", "other", "surnames"]


def article_paradigms(source: str, article: dict):
    if source == "nouns":
        paradigm, reason = noun_paradigm(article)
        return [paradigm] if paradigm else [], reason
    if source == "adjectives":
        return [adjective_paradigm(article)], ""
    if source == "verbs":
        paradigm, reason = verb_paradigm(article)
        return [paradigm] if paradigm else [], reason
    if source == "surnames":
        return [surname_paradigm(article)], ""
    return other_paradigms(article)


def merge_participle_homonyms(items: list, counts: Counter, source: str) -> None:
    """
    Homonyms of a verb that differ by participles only are one paradigm with the participles of both: `ебать 1` has
    `ебаный` (`ебомый` is `{{incorrect}}` for this meaning), `ебать 2` has `ебомый`; the second one gets all lines
    and the first one becomes its part, so it is not written.
    """
    for i, (lines, _, paradigm) in enumerate(items):
        for other_lines, _, other in items[i + 1:]:
            difference = lines ^ other_lines
            if other.type_grammems == paradigm.type_grammems and difference and \
                    all(annotation.startswith("PARTICIPLE") for _, annotation in difference):
                for line in paradigm.lines:
                    if line not in other_lines:
                        other.lines.append(line)
                        other_lines.add(line)
                counts[source + " homonyms merged by participles"] += 1
                break


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-folder", default="result")
    parser.add_argument("--output", default="result/wiktionary.slf")
    parser.add_argument("--failures", default="result/slf_failures.tsv")
    args = parser.parse_args()
    counts = Counter()
    # equal paradigms of different articles are written once: `хуяка 1` with a masculine template gives `хуяк`
    written = set()
    with open(args.output, "w") as outp, open(args.failures, "w") as failures:
        failures.write("source\ttitle\ttemplate\treason\n")
        for source in SOURCES:
            path = os.path.join(args.input_folder, source + ".jsonl")
            if not os.path.exists(path):
                print(f"no file {path}")
                continue
            # the paradigms of a title: (line set, type grammems, header, paradigm)
            by_title = {}
            for line in open(path):
                article = json.loads(line)
                template = article["morpho"].get("template", "")
                paradigms, reason = article_paradigms(source, article)
                for paradigm in paradigms:
                    paradigm: TParadigm
                    if paradigm.skipped:
                        failures.write(f"{source}\t{article['title']}\t{template}\t"
                                       f"пропущены формы {', '.join(paradigm.skipped)}\n")
                    if not paradigm.lines:
                        reason = "нет форм"
                        continue
                    homonym = f" {article['homonym']}" if article.get("homonym") else ""
                    header = f"{source} {article['title']}{homonym} {{{{{template}}}}}"
                    by_title.setdefault(article["title"], []).append((set(paradigm.lines), header, paradigm))
                if reason:
                    failures.write(f"{source}\t{article['title']}\t{template}\t{reason}\n")
                    counts[source + " failures"] += 1
            for items in by_title.values():
                merge_participle_homonyms(items, counts, source)
                for i, (lines, header, paradigm) in enumerate(items):
                    # a homonym whose paradigm is a part of another one is the same word for aot:
                    # `снос 1` and `снос 2` (with the second genitive `сносу`)
                    if any(j != i and other.type_grammems == paradigm.type_grammems and lines <= other_lines
                           and (lines != other_lines or j < i)
                           for j, (other_lines, _, other) in enumerate(items)):
                        counts[source + " merged homonyms"] += 1
                        continue
                    key = (paradigm.type_grammems, frozenset(lines))
                    if key in written:
                        counts[source + " duplicates"] += 1
                        continue
                    written.add(key)
                    outp.write(paradigm.to_slf(header))
                    counts[source] += 1
    for name, count in counts.items():
        print(f"{name}: {count}")


if __name__ == "__main__":
    main()
