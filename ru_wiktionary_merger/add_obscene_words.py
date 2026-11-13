"""
Writes the paradigms of the obscene words of Wiktionary that are not in aot.ru to an slf file, to be added to aot by
`slf_convert --to-mrd` (it adds the paradigms of the slf file to the dictionary).
A word is obscene if all meanings of its article have the mark `{{обсц.|ru}}` (`пиздец`, `ебать`, `долбоёб`), see
`is_obscene` in `src/utils/wiki.py`; an article with an obscene meaning among others (`банан`, `палка`) is an ordinary
word. A paradigm is taken from the export of Wiktionary (`result/wiktionary.slf`) if aot has no lemma with its part of
speech.
"""
import argparse
import json
import re

from src.utils.wiki import is_obscene


def norm(s: str) -> str:
    return s.upper().replace("Ё", "Е")


def drop_yo_variants(paradigms: list) -> list:
    """
    Articles that differ by `ё` only (`ёбаный` and `ебаный`, `уёбан` and `уебан`) are one lemma in aot, where `ё` is
    optional: a paradigm that is a part of another one if `ё` is `е` is dropped (of equal ones the one with `ё` is kept).
    """
    def key_and_lines(block):
        lines = block.strip("\n").split("\n")
        type_grammems = "\n".join(x for x in lines if x.startswith("$"))
        forms = [x.replace("ё", "е") for x in lines[1:] if x and not x.startswith("$")]
        return (forms[0].split()[0], forms[0].split()[1], type_grammems), frozenset(forms)
    parsed = [key_and_lines(block) for block in paradigms]

    def has_yo(block):
        return "ё" in next(x for x in block.strip("\n").split("\n")[1:] if x and not x.startswith("$"))
    result = []
    for i, block in enumerate(paradigms):
        key, lines = parsed[i]
        dropped = False
        for j, (other_key, other_lines) in enumerate(parsed):
            if j == i or other_key != key or not lines <= other_lines:
                continue
            if lines != other_lines or (has_yo(paradigms[j]) and not has_yo(block)) or \
                    (has_yo(paradigms[j]) == has_yo(block) and j < i):
                dropped = True
                break
        if not dropped:
            result.append(block)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", default="tmp/cache/pages.jsonl")
    parser.add_argument("--wiki-slf", default="result/wiktionary.slf")
    parser.add_argument("--aot", default="../data/Russian/morphs.json")
    parser.add_argument("--gramtab", default="../data/Russian/gramtab.json")
    parser.add_argument("--output", default="result/obscene.slf")
    args = parser.parse_args()
    titles = set()
    for line in open(args.pages):
        page = json.loads(line)
        if page.get("type") == "article" and is_obscene(page.get("text", "")):
            titles.add(page["title"])
    aot = json.load(open(args.aot))
    pos = {code: value["p"] for code, value in json.load(open(args.gramtab))["gramcodes"].items()}
    # a lemma and its part of speech: the interjection `ебать` is not the verb
    aot_lemmas = {(norm(lemma["l"]), pos[aot["flexia_models"][lemma["f"]]["endings"][0]["gramcode"][:2]])
                  for lemma in aot["lemmas"]}
    paradigms, found, in_aot = [], set(), 0
    for block in open(args.wiki_slf).read().split("=====\n"):
        lines = block.split("\n")
        # `// nouns пиздец 1 {{сущ ru m ina 5b}}`
        m = re.match(r"^// \S+ (.+?)(?: \d+| [IVX]+)? \{\{.*\}\}$", lines[0])
        if not m or m.group(1) not in titles:
            continue
        forms = [x for x in lines[1:] if x and not x.startswith("$")]
        if (norm(forms[0].split()[0]), forms[0].split()[1]) in aot_lemmas:
            in_aot += 1
            continue
        paradigms.append(block if block.endswith("\n") else block + "\n")
        found.add(m.group(1))
    paradigms = drop_yo_variants(paradigms)
    with open(args.output, "w") as outp:
        for paradigm in paradigms:
            outp.write(paradigm + "=====\n")
    print(f"obscene articles: {len(titles)}, paradigms written: {len(paradigms)}, lemmas of aot: {in_aot}, "
          f"articles without a paradigm: {len(titles - found)}")


if __name__ == "__main__":
    main()
