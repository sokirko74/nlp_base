"""
Expands the inflection template of every Russian article (`{{прил-ru|то́чный|1*a/c'}}`, `{{сущ ru m a 1a|...}}`)
with `wikitextprocessor`, which runs the Lua modules and the parser functions the way MediaWiki does it.
The result is the wiki text of the rendered table, e.g. with the line `Сравнительная степень — точне́е, точне́й`
that the dump does not have.

The templates and modules are loaded from the dump into a SQLite database once (`--load`, about a minute):
    python expand_morpho.py --load
    python expand_morpho.py --processes 8
The full run takes about an hour; it can be started apart from the terminal and continued if interrupted:
    setsid nohup python expand_morpho.py --processes 8 --resume >> tmp/expand_morpho.log 2>&1 < /dev/null &
The articles are read from the cache of `cache_dump.py`; the inflection template is chosen the same way as in
`extract_from_dump.py`, homonyms get the same labels.
"""
import argparse
import json
import pathlib
import re
from multiprocessing import Pool
from timeit import default_timer as timer

import wikitextparser

from config import DUMP_PATH
from constants import BROKEN_ARTICLES, CACHE_PATH
from extract_from_dump import keep_morpho_sections
from src.utils.wiki import find_ru_section, main_morpho_template, homonym_label, clean_template_name

DB_PATH = "tmp/wtp_ru.db"
OUTPUT_PATH = "tmp/expanded.jsonl"
MORPHO_SECTION = "Морфологические и синтаксические свойства"
TEMPLATE_NAMESPACE, MODULE_NAMESPACE = 10, 828

wtp = None


def load_db():
    from wikitextprocessor import Wtp
    from wikitextprocessor.dumpparser import process_dump
    pathlib.Path(DB_PATH).unlink(missing_ok=True)
    ctx = Wtp(db_path=DB_PATH, lang_code="ru", project="wiktionary")
    process_dump(ctx, DUMP_PATH, {TEMPLATE_NAMESPACE, MODULE_NAMESPACE})
    ctx.db_conn.commit()


def init_worker():
    global wtp
    from wikitextprocessor import Wtp
    wtp = Wtp(db_path=DB_PATH, lang_code="ru", project="wiktionary")


def morpho_calls(page: dict):
    """
    The inflection templates of an article: (homonym label or None, the template call as it is written).
    """
    section = find_ru_section(wikitextparser.parse(keep_morpho_sections(page["text"])))
    if not section:
        return []
    homonyms = section.get_sections(level=2)
    morpho_sections = [sec for sec in section.get_sections() if MORPHO_SECTION in str(sec.title)]
    result = []
    for index, morpho_section in enumerate(morpho_sections, start=1):
        main = main_morpho_template(morpho_section)
        if not main:
            continue
        homonym = None
        if len(morpho_sections) > 1:
            owners = [sec for sec in homonyms if sec.span[0] <= morpho_section.span[0] < sec.span[1]]
            homonym = homonym_label(owners[0], index) if owners else str(index)
        result.append((homonym, main))
    return result


def expand_page(page: dict):
    result = []
    for homonym, template in morpho_calls(page):
        # MediaWiki joins spaces and underscores in titles and drops the direction marks, `wikitextprocessor` does
        # not: `{{прил ru  1*a|...}}`
        # invisible marks of the text direction: `{{мест ru 1a-в\u200e|...}}`
        template.name = re.sub(r"[ _]+", " ", template.name).replace("\u200e", "").replace("\u200f", "")
        wtp.start_page(page["title"])
        record = {"id": page["id"], "title": page["title"], "template": clean_template_name(template.name)}
        if homonym:
            record["homonym"] = homonym
        try:
            record["expanded"] = wtp.expand(template.string, timeout=60)
        except Exception as e:
            record["error"] = f"{type(e).__name__}: {e}"[:500]
        if wtp.errors:
            record["wtp_errors"] = [str(err.get("msg", err))[:300] for err in wtp.errors[:3]]
        result.append(record)
    return result


def read_pages(titles, done_ids):
    with open(CACHE_PATH) as inp:
        for line in inp:
            page = json.loads(line)
            if page["type"] != "article" or page["title"] in BROKEN_ARTICLES or page["id"] in done_ids:
                continue
            if titles and page["title"] not in titles:
                continue
            yield page


def prepare_resume(path: str) -> set:
    """
    Keeps the complete records of an interrupted run and returns the ids of their articles; the records of the
    last article are dropped, they may be incomplete (homonyms are several records).
    """
    records = []
    with open(path) as inp:
        for line in inp:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                break
    if records:
        last_id = records[-1]["id"]
        records = [record for record in records if record["id"] != last_id]
    with open(path, "w") as out:
        for record in records:
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {record["id"] for record in records}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--load", action="store_true", help="load the templates and modules of the dump")
    parser.add_argument("--processes", type=int, default=8)
    parser.add_argument("--titles", help="only these articles, separated by commas")
    parser.add_argument("--output", default=OUTPUT_PATH)
    parser.add_argument("--resume", action="store_true", help="continue an interrupted run, append to the output")
    args = parser.parse_args()
    if args.load:
        load_db()
        return
    titles = set(args.titles.split(",")) if args.titles else None
    done_ids = prepare_resume(args.output) if args.resume and pathlib.Path(args.output).exists() else set()
    print(f"{len(done_ids)} articles are already expanded", flush=True)
    start = timer()
    count = errors = 0
    with Pool(args.processes, initializer=init_worker) as pool, open(args.output, "a" if done_ids else "w") as out:
        for records in pool.imap(expand_page, read_pages(titles, done_ids), chunksize=20):
            for record in records:
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1
                errors += "error" in record
            if count and count % 20000 < len(records):
                print(f"{count} templates, {errors} errors, {timer() - start:.0f}s", flush=True)
    print(f"{count} templates, {errors} errors, {timer() - start:.0f}s")


if __name__ == "__main__":
    main()
