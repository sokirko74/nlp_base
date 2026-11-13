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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-folder", default="result")
    parser.add_argument("--output", default="result/wiktionary.slf")
    parser.add_argument("--failures", default="result/slf_failures.tsv")
    args = parser.parse_args()
    counts = Counter()
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
                for i, (lines, header, paradigm) in enumerate(items):
                    # a homonym whose paradigm is a part of another one is the same word for aot:
                    # `снос 1` and `снос 2` (with the second genitive `сносу`)
                    if any(j != i and other.type_grammems == paradigm.type_grammems and lines <= other_lines
                           and (lines != other_lines or j < i)
                           for j, (other_lines, _, other) in enumerate(items)):
                        counts[source + " merged homonyms"] += 1
                        continue
                    outp.write(paradigm.to_slf(header))
                    counts[source] += 1
    for name, count in counts.items():
        print(f"{name}: {count}")


if __name__ == "__main__":
    main()
