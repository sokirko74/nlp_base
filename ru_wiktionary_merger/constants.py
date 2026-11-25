from typing import Dict, List

# TODO Move to config yaml
WRITE_PATHS: Dict[str, str] = {
    "article": "tmp/articles.jsonl",
    "template_redirect": "tmp/template_redirects.jsonl"
}

# Russian pages from the dump, see cache_dump.py
CACHE_PATH = "tmp/cache/pages.jsonl"

SEGMENT_SEPARATOR: str = "|"

BROKEN_ARTICLES: List[str] = [
    "ханьжа"
]

INVARIABLE_POS: List[str] = [
    "adv",
    "ger"
]

POS_MAP: Dict[str, str] = {
    "сущ": "noun",
    # "падежи": "noun",
    "прил": "adj",
    "гл": "verb",
    "прич": "participle",
    "деепр": "ger",
    "adv": "adv",
    "interj": "intrj",
    "part": "particle",
    "мест": "padj",  # possessive
    "predic": "pred",
    "conj": "conj",
    "числ": "num",
    "prep": "prep",
    # not really parts of speech, it's just for consistency's sake
    "Фам": "fam",
    "собств.": "prop",  # proper name
    "abbrev": "abbr",
    "onomatop": "ono",
    "intro": "par",  # parenthesis
    "не так": "broken",  # ungrammatical, ignore this
}

CASE_MAP: Dict[str, str] = {
    "Им.": "nom",
    "Р.": "gen",
    "Д.": "dat",
    "В.": "acc",
    "Тв.": "ins",
    "Пр.": "prp"
}

CASE_PRONOUN_MAP: Dict[str, str] = {
    "Кто/что? (ед)": "nom-sg",
    "Кто/что? (мн)": "nom-pl",
    "Нет кого/чего? (ед)": "gen-sg",
    "Нет кого/чего? (мн)": "gen-pl",
    "Кому/чему? (ед)": "dat-sg",
    "Кому/чему? (мн)": "gat-pl",
    "Кого/что? (ед)": "acc-sg",
    "Кого/что? (мн)": "acc-pl",
    "Кем/чем? (ед)": "ins-sg",
    "Кем/чем? (мн)": "ins-pl",
    "О ком/чём? (ед)": "prp-sg",
    "О ком/чём? (мн)": "prp-pl"
}

NUMBER_MAP: Dict[str, str] = {
    "ед. ч.": "sg",
    "мн. ч.": "pl"
}

# full forms of adjectives as named in the table template `прил`
ADJ_FULL_FORMS: List[str] = [
    f"{case}-{number}" for case in ("nom", "gen", "dat", "ins", "prp")
    for number in ("sg-m", "sg-n", "sg-f", "pl")
] + ["acc-sg-m-a", "acc-sg-m-n", "acc-sg-n", "acc-sg-f", "acc-pl-a", "acc-pl-n"]

ADJ_SHORT_FORMS: List[str] = ["srt-sg-m", "srt-sg-n", "srt-sg-f", "srt-pl"]

# the parameter of the header template `прил ru` with the comparative forms
ADJ_COMPARATIVE: str = "степень"

# the table template all verb inflection templates resolve to
VERB_TABLE_TEMPLATE: str = "Гл-блок"

# header templates of the parts of speech without inflection
INVARIABLE_TEMPLATES: Dict[str, str] = {
    "adv ru": "adv",
    "predic ru": "pred",
    "part ru": "particle",
    "prep ru": "prep",
    "conj ru": "conj",
    "interj ru": "intrj",
    "interj-ru": "intrj",
    "intro ru": "par",
    "onomatop ru": "ono",
}

# inflection templates of pronouns and numerals end with the adjective table `прил` or with a case table
PRONOUN_NUMERAL_PREFIXES = ("мест", "числ", "Мс", "падежи")
SURNAME_PREFIXES = ("Фам", "фам")
# particles of indefinite pronouns: `который-то`, `какой-нибудь`
PARTICLES = ("то", "либо", "нибудь", "нито", "таки")

# the role of an abbreviation (`роль=существительного мужского рода единственного числа`): key, value
ABBREVIATION_ROLES = [
    ("существительн", "abbr_pos", "noun"), ("прилагательн", "abbr_pos", "adj"), ("наречи", "abbr_pos", "adv"),
    ("глагол", "abbr_pos", "verb"), ("предлог", "abbr_pos", "prep"), ("союз", "abbr_pos", "conj"),
    ("частиц", "abbr_pos", "particle"), ("междомет", "abbr_pos", "intrj"), ("вводн", "abbr_pos", "par"),
    ("мужского", "gender", "m"), ("женского", "gender", "f"), ("среднего", "gender", "n"),
    ("единственного", "number", "sg"), ("множественного", "number", "pl"),
]
CASES: List[str] = ["nom", "gen", "dat", "acc", "ins", "prp"]

ARTICLE_NAMESPACE: str = "0"
TEMPLATE_NAMESPACE: str = "10"

USER_AGENT: Dict[str, str] = {
    'User-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/74.0.3729.169 Safari/537.36'}
