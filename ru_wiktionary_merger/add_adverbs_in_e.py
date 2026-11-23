"""
Adverbs in -е (`умоляюще`, `негодующе`) of adjectives that lost their fictitious short forms.

prune_own_homonym_comparatives.py removed the short forms of 484 adjectives (`умоляющий`: `умоляющ`, `умоляюща`,
`умоляюще`, `умоляющи`), but the neuter form in -е is mostly an adverb in the corpus (`умоляюще` 11831 in Flibusta
against `умоляющ` 1), and aot.ru had no such adverb. The adverbs of `adverbs_in_e.tsv` are added as lemmas (ADV,
`непригоже` also PRED as in Wiktionary); the voices of each one: `wiki+flibusta` (an adverb article of Wiktionary and
the corpus), `wiki` (Wiktionary only, no evidence in the corpus: the long tail), `flibusta+claude` (the contexts of the
corpus show the adverb). The stress is taken from the Wiktionary article (`{{по-слогам|у|.|мо|ля́|ю|ще}}`) or from the
adjective: -ий and -е have one vowel each, so the stressed vowel has the same number from the end of the word.

The result should be saved by `slf_convert --to-mrd` with an empty slf file.
"""
import argparse
import json
import time
from collections import Counter
from typing import Dict, List, Optional

from add_po_ski_adverbs import stress_of_wiki_text

ADV_GRAMCODE = "LQ"
PRED_GRAMCODE = "LU"
UNKNOWN_ACCENT = 255


def add_item(items: List, item) -> int:
    if item in items:
        return items.index(item)
    items.append(item)
    return len(items) - 1


def norm(s: str) -> str:
    return s.upper().replace("Ё", "Е")


def read_decisions(path: str) -> List[List[str]]:
    return [line.rstrip("\n").split("\t") for line in open(path)
            if not line.startswith("#") and not line.startswith("adverb\t")]


def wiki_articles(path: str, words) -> Dict[str, Dict]:
    """adverb -> {"stress": the vowel from the end or None, "pos": {"adv", "pred"}}"""
    result = {}
    for line in open(path):
        article = json.loads(line)
        word = norm(article["title"])
        if word not in words or article.get("pos") not in ("adv", "pred"):
            continue
        item = result.setdefault(word, {"stress": None, "pos": set()})
        item["pos"].add(article["pos"])
        for text in article["morpho"].get("info", {}).values():
            stress = stress_of_wiki_text(text) if "по-слогам" in text else None
            if stress is not None and item["stress"] is None:
                item["stress"] = stress
    return result


def main():
    with open(args.input) as inp:
        data = json.load(inp)
    codes = json.load(open(args.gramtab))["gramcodes"]
    flexia, accents = data["flexia_models"], data["accent_models"]
    decisions = read_decisions(args.decisions)
    words = {norm(row[0]) for row in decisions}
    wiki = wiki_articles(args.wiki_other, words)
    existing_adverbs = set()
    adjective_stress: Dict[str, int] = {}
    for lemma in data["lemmas"]:
        pos = codes[flexia[lemma["f"]]["endings"][0]["gramcode"][:2]]["p"]
        if pos in ("ADV", "PRED"):
            existing_adverbs.add((norm(lemma["l"]), pos))
        elif pos == "A" and accents[lemma["a"]][0] != UNKNOWN_ACCENT:
            adjective_stress.setdefault(norm(lemma["l"]), accents[lemma["a"]][0])
    now = time.strftime("%H:%M, %d %B %Y")
    data["sessions"].append({"user": args.user, "start": now, "last_save": now})
    session = len(data["sessions"]) - 1
    counts = Counter()
    report = []
    for adverb, adjective, _, voices, _ in decisions:
        article = wiki.get(norm(adverb), {"stress": None, "pos": set()})
        stress: Optional[int] = article["stress"]
        source = "wiktionary"
        if stress is None:
            stress = adjective_stress.get(norm(adjective))
            source = "adjective" if stress is not None else "unknown"
        counts[f"stress: {source}"] += 1
        parts = [("ADV", ADV_GRAMCODE)] + ([("PRED", PRED_GRAMCODE)] if "pred" in article["pos"] else [])
        for pos, gramcode in parts:
            if (norm(adverb), pos) in existing_adverbs:
                counts[f"{pos} exists"] += 1
                continue
            model = add_item(flexia, {"endings": [{"flexia": "", "gramcode": gramcode}]})
            accent = add_item(accents, [UNKNOWN_ACCENT if stress is None else stress])
            data["lemmas"].append({"l": adverb, "f": model, "a": accent, "s": session})
            counts[f"{pos} added, {voices}"] += 1
            report.append((adverb, pos, voices, "" if stress is None else str(stress), source))
    with open(args.output, "w") as outp:
        json.dump(data, outp, ensure_ascii=False)
    with open(args.report, "w") as outp:
        outp.write("adverb\tpos\tvoices\tstressed vowel from the end\tstress source\n")
        for row in report:
            outp.write("\t".join(row) + "\n")
    print(dict(counts))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--gramtab", default="../data/Russian/gramtab.json")
    parser.add_argument("--wiki-other", default="result/other.jsonl")
    parser.add_argument("--decisions", default="adverbs_in_e.tsv")
    parser.add_argument("--user", default="wiktionary")
    parser.add_argument("--report", default="result/adverbs_in_e_added.tsv")
    args = parser.parse_args()
    main()
