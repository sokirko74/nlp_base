"""
The text and the word frequencies of the Russian Wikipedia from its CirrusSearch dump
(`ruwiki-<date>-cirrussearch-content.json.gz`, https://dumps.wikimedia.org/other/cirrussearch/).

The dump has two lines per article: `{"index": ...}` and the document, whose field `text` is the rendered plain text.
Writes:
- `--text`: the plain text, one article per line (`title<TAB>text`), for indexing and contexts;
- `--freq`: the lowercase frequencies of the Cyrillic words (`word<TAB>count`, sorted by the count), the format of
  `~/data/flibusta/wordfreq.tsv`; a word may have inner hyphens (`по-русски`), ё is kept.

The Flibusta corpus is mostly fiction; Wikipedia adds the vocabulary of science and technology (`агломерировать`).

    python ruwiki_corpus.py --dump ~/data/ruwiki/ruwiki-20251229-cirrussearch-content.json.gz \
        --text ~/data/ruwiki/ruwiki_text.txt --freq ~/data/ruwiki/wordfreq.tsv
"""
import argparse
import json
import re
import subprocess
import sys
import time
from collections import Counter
from multiprocessing import Pool
from typing import List, Tuple

WORD = re.compile(r"[а-яёА-ЯЁ]+(?:-[а-яёА-ЯЁ]+)*")
BATCH = 200


def process(lines: List[str]) -> Tuple[List[str], Counter]:
    texts = []
    counts = Counter()
    for line in lines:
        document = json.loads(line)
        text = document.get("text") or ""
        title = (document.get("title") or "").replace("\t", " ")
        texts.append(title + "\t" + text.replace("\n", " ").replace("\t", " "))
        counts.update(word.lower() for word in WORD.findall(text))
    return texts, counts


def batches(stream):
    batch = []
    for line in stream:
        # the lines `{"index": ...}` are not documents
        if line.startswith('{"index"'):
            continue
        batch.append(line)
        if len(batch) == BATCH:
            yield batch
            batch = []
    if batch:
        yield batch


def main():
    zcat = subprocess.Popen(["zcat", args.dump], stdout=subprocess.PIPE, text=True, encoding="utf-8",
                            bufsize=1 << 24)
    total = Counter()
    articles = 0
    start = time.time()
    with open(args.text, "w", encoding="utf-8") as text_out, Pool(args.processes) as pool:
        for texts, counts in pool.imap(process, batches(zcat.stdout), chunksize=1):
            for text in texts:
                text_out.write(text + "\n")
            total.update(counts)
            articles += len(texts)
            if articles % 50000 < BATCH:
                print(f"{articles} articles, {len(total)} words, {round(time.time() - start)} s",
                      file=sys.stderr, flush=True)
    if zcat.wait() != 0:
        raise RuntimeError("zcat failed")
    with open(args.freq, "w", encoding="utf-8") as freq_out:
        for word, count in total.most_common():
            freq_out.write(f"{word}\t{count}\n")
    print(f"done: {articles} articles, {len(total)} words, {sum(total.values())} tokens, "
          f"{round(time.time() - start)} s", file=sys.stderr, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--freq", required=True)
    parser.add_argument("--processes", type=int, default=6)
    args = parser.parse_args()
    main()
