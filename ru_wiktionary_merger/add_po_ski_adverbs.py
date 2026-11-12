"""
Adverbs по-...ски (`по-абакански`) instead of the fictitious short form of adjectives.

1. Adjectives in -ский/-цкий had the only short form `ADJ_SHORT pl` in -и (`абакански`), so that the lemmatizer
   predicted an unknown `по-абакански` by the known part after the hyphen. These adjectives have no short forms
   (Wiktionary: `3aX~`), and the form made a word of `абакански`. The form is removed from the paradigms where it is
   the only short form; the other adjectives (`крутобокий`: `крутобоки`) keep it.
2. The adverbs are added as lemmas: the adverbs of Wiktionary (`result/other.jsonl`) and the words of the Flibusta
   corpus (`po_ski_flibusta.tsv`, the query `count(/^по-.+[сц]ки$/i) #by[$w]`) with the frequency >= `--threshold`.
   An adverb is added only if its adjective (`по-абакански` -> `абаканский`, `по-морски` -> `морской`) is in aot.ru or
   in Wiktionary, so that frequent misspellings (`по-джентельменски`) are not added.
   The stress of the adverb is the stress of the adjective (the vowel number from the end of the word is the same),
   or the stress of the Wiktionary article (`{{по-слогам|по|-|анг|ли́й|ски}}`), otherwise it is unknown.

The result should be saved by `slf_convert --to-mrd` with an empty slf file.
"""
import argparse
import json
import re
import time
from collections import Counter
from typing import Dict, List, Optional

ADV_GRAMCODE = "LQ"
UNKNOWN_ACCENT = 255
VOWELS = "АЕЁИОУЫЭЮЯ"
ACUTE = "́"
ADVERB = re.compile(r"^ПО-[А-ЯЁ]+[СЦ]КИ$")


def norm(s: str) -> str:
    return s.upper().replace("Ё", "Е")


def add_item(items: List, item) -> int:
    if item in items:
        return items.index(item)
    items.append(item)
    return len(items) - 1


def vowel_from_end(word: str, position: int) -> int:
    """the number of the vowel at `position` counted from the end of the word (0 is the last vowel)"""
    return sum(1 for c in word[position + 1:].upper() if c in VOWELS)


def stress_of_wiki_text(text: str) -> Optional[int]:
    """`{{по-слогам|по|-|анг|ли́й|ски}}` or `англи́йский` -> the stressed vowel from the end"""
    m = re.search(r"\{\{по-слогам\|([^}]*)}}", text)
    word = "".join(m.group(1).split("|")) if m else text
    word = word.replace("̀", "")
    if word.count(ACUTE) != 1:
        return None
    position = word.index(ACUTE) - 1
    if position < 0 or word[position].upper() not in VOWELS:
        return None
    return vowel_from_end(word.replace(ACUTE, ""), position)


def adjectives_of(adverb: str) -> List[str]:
    stem = adverb[len("ПО-"):-1]
    return [stem + "ИЙ", stem + "ОЙ"]


class Dictionary:
    def __init__(self, data):
        self.data = data
        codes = json.load(open(args.gramtab))["gramcodes"]
        self.pos = {code: v["p"] for code, v in codes.items()}
        self.flexia = data["flexia_models"]

    def lemma_pos(self, lemma) -> str:
        return self.pos[self.flexia[lemma["f"]]["endings"][0]["gramcode"][:2]]

    def remove_short_plural(self, counts: Counter):
        accents = self.data["accent_models"]
        for lemma in self.data["lemmas"]:
            if not norm(lemma["l"]).endswith(("СКИЙ", "ЦКИЙ")) or self.lemma_pos(lemma) != "A":
                continue
            endings = self.flexia[lemma["f"]]["endings"]
            short = [i for i, e in enumerate(endings) if self.pos[e["gramcode"][:2]] == "ADJ_SHORT"]
            if not short or any(endings[i]["flexia"] != "И" for i in short):
                continue
            keep = [i for i in range(len(endings)) if i not in short]
            lemma["f"] = add_item(self.flexia, {"endings": [endings[i] for i in keep]})
            lemma["a"] = add_item(accents, [accents[lemma["a"]][i] for i in keep])
            counts["short plural removed"] += 1

    def adjective_stress(self) -> Dict[str, int]:
        result = {}
        for lemma in self.data["lemmas"]:
            if self.lemma_pos(lemma) == "A":
                accent = self.data["accent_models"][lemma["a"]][0]
                if accent != UNKNOWN_ACCENT:
                    result.setdefault(norm(lemma["l"]), accent)
        return result

    def add_adverbs(self, adverbs: Dict[str, Optional[int]], user: str):
        now = time.strftime("%H:%M, %d %B %Y")
        self.data["sessions"].append({"user": user, "start": now, "last_save": now})
        session = len(self.data["sessions"]) - 1
        model = add_item(self.flexia, {"endings": [{"flexia": "", "gramcode": ADV_GRAMCODE}]})
        for word, stress in sorted(adverbs.items()):
            accent = add_item(self.data["accent_models"], [UNKNOWN_ACCENT if stress is None else stress])
            self.data["lemmas"].append({"l": word, "f": model, "a": accent, "s": session})


def read_wiktionary():
    adjectives, adverbs, titles = {}, {}, set()
    for line in open(args.wiki_articles):
        article = json.loads(line)
        titles.add(norm(article["title"]))
    for line in open(args.wiki_adjectives):
        article = json.loads(line)
        stems = article["morpho"].get("stems", {})
        info = article["morpho"].get("info", {})
        stress = stress_of_wiki_text(info.get("слоги", ""))
        if stress is None and stems.get("основа"):
            stem = stems["основа"]
            # the stress on the stem, the ending -ий has one vowel
            stress = stress_of_wiki_text(stem)
            stress = None if stress is None else stress + 1
        adjectives[norm(article["title"])] = stress
    for line in open(args.wiki_other):
        article = json.loads(line)
        word = article["title"].upper()
        if article.get("pos") == "adv" and ADVERB.match(word):
            adverbs[word] = stress_of_wiki_text(article["morpho"].get("info", {}).get("слоги", ""))
    return adjectives, adverbs, titles


def read_flibusta() -> Counter:
    freq, spelling = Counter(), {}
    for line in open(args.flibusta):
        if line.startswith("#"):
            continue
        word, count = line.rstrip("\n").split("\t")
        word = word.upper()
        freq[norm(word)] += int(count)
        if "Ё" in word or norm(word) not in spelling:
            spelling[norm(word)] = word
    return Counter({spelling[w]: c for w, c in freq.items()})


def main():
    with open(args.input) as inp:
        data = json.load(inp)
    dictionary = Dictionary(data)
    counts = Counter()
    existing = {norm(lemma["l"]) for lemma in data["lemmas"]}
    aot_stress = dictionary.adjective_stress()
    aot_adjectives = {norm(lemma["l"]) for lemma in data["lemmas"] if dictionary.lemma_pos(lemma) == "A"}
    wiki_adjectives, wiki_adverbs, wiki_titles = read_wiktionary()

    def adjective_stress(word: str) -> Optional[int]:
        for adj in adjectives_of(norm(word)):
            if adj in aot_stress:
                return aot_stress[adj]
        for adj in adjectives_of(norm(word)):
            if wiki_adjectives.get(adj) is not None:
                return wiki_adjectives[adj]
        return None

    adverbs = {}
    for word, stress in wiki_adverbs.items():
        if norm(word) in existing:
            continue
        adverbs[word] = stress if stress is not None else adjective_stress(word)
        counts["wiktionary"] += 1
    for word, freq in read_flibusta().items():
        if not ADVERB.match(word) or norm(word) in existing or word in adverbs:
            continue
        if freq < args.threshold:
            counts["flibusta: below the threshold"] += 1
            continue
        if not any(adj in aot_adjectives or adj in wiki_titles for adj in adjectives_of(norm(word))):
            counts["flibusta: no adjective"] += 1
            continue
        adverbs[word] = adjective_stress(word)
        counts["flibusta"] += 1
    counts["without stress"] = sum(1 for s in adverbs.values() if s is None)
    dictionary.remove_short_plural(counts)
    dictionary.add_adverbs(adverbs, args.user)
    with open(args.output, "w") as outp:
        json.dump(data, outp, ensure_ascii=False)
    with open(args.added, "w") as outp:
        for word in sorted(adverbs):
            outp.write(f"{word}\t{'' if adverbs[word] is None else adverbs[word]}\n")
    print(dict(counts))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--gramtab", default="../data/Russian/gramtab.json")
    parser.add_argument("--wiki-articles", default="tmp/articles.jsonl")
    parser.add_argument("--wiki-adjectives", default="result/adjectives.jsonl")
    parser.add_argument("--wiki-other", default="result/other.jsonl")
    parser.add_argument("--flibusta", default="po_ski_flibusta.tsv")
    parser.add_argument("--threshold", type=int, default=3)
    parser.add_argument("--user", default="wiktionary")
    parser.add_argument("--added", default="result/po_ski_added.tsv", help="the list of the added adverbs")
    args = parser.parse_args()
    main()
