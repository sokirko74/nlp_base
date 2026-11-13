"""
Writes the paradigms of the obscene words of Wiktionary that are not in aot.ru to an slf file, to be added to aot by
`slf_convert --to-mrd` (it adds the paradigms of the slf file to the dictionary).
A word is obscene if all meanings of its article have the mark `{{обсц.|ru}}` (`пиздец`, `ебать`, `долбоёб`), see
`is_obscene` in `src/utils/wiki.py`; an article with an obscene meaning among others (`банан`, `палка`) is an ordinary
word. A paradigm is taken from the export of Wiktionary (`result/wiktionary.slf`) if its lemma is not a lemma of aot.
"""
import argparse
import json
import re

from src.utils.wiki import is_obscene


def norm(s: str) -> str:
    return s.upper().replace("Ё", "Е")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", default="tmp/cache/pages.jsonl")
    parser.add_argument("--wiki-slf", default="result/wiktionary.slf")
    parser.add_argument("--aot", default="../data/Russian/morphs.json")
    parser.add_argument("--output", default="result/obscene.slf")
    args = parser.parse_args()
    titles = set()
    for line in open(args.pages):
        page = json.loads(line)
        if page.get("type") == "article" and is_obscene(page.get("text", "")):
            titles.add(page["title"])
    aot_lemmas = {norm(lemma["l"]) for lemma in json.load(open(args.aot))["lemmas"]}
    paradigms, found, in_aot = [], set(), 0
    for block in open(args.wiki_slf).read().split("=====\n"):
        lines = block.split("\n")
        # `// nouns пиздец 1 {{сущ ru m ina 5b}}`
        m = re.match(r"^// \S+ (.+?)(?: \d+| [IVX]+)? \{\{.*\}\}$", lines[0])
        if not m or m.group(1) not in titles:
            continue
        forms = [x for x in lines[1:] if x and not x.startswith("$")]
        if norm(forms[0].split()[0]) in aot_lemmas:
            in_aot += 1
            continue
        paradigms.append(block if block.endswith("\n") else block + "\n")
        found.add(m.group(1))
    with open(args.output, "w") as outp:
        for paradigm in paradigms:
            outp.write(paradigm + "=====\n")
    print(f"obscene articles: {len(titles)}, paradigms written: {len(paradigms)}, lemmas of aot: {in_aot}, "
          f"articles without a paradigm: {len(titles - found)}")


if __name__ == "__main__":
    main()
