"""
The participles of verbs are declined here, since the table of a verb gives only their initial forms.
"""
import re
from typing import Dict, List, Optional

from constants import SEGMENT_SEPARATOR

# full forms: the names are the same as for adjectives, see ADJ_FULL_FORMS
HARD_ENDINGS: Dict[str, List[str]] = {
    "nom-sg-m": ["ый"], "gen-sg-m": ["ого"], "dat-sg-m": ["ому"], "ins-sg-m": ["ым"], "prp-sg-m": ["ом"],
    "nom-sg-n": ["ое"], "gen-sg-n": ["ого"], "dat-sg-n": ["ому"], "ins-sg-n": ["ым"], "prp-sg-n": ["ом"],
    "nom-sg-f": ["ая"], "gen-sg-f": ["ой"], "dat-sg-f": ["ой"], "ins-sg-f": ["ой", "ою"], "prp-sg-f": ["ой"],
    "nom-pl": ["ые"], "gen-pl": ["ых"], "dat-pl": ["ым"], "ins-pl": ["ыми"], "prp-pl": ["ых"],
    "acc-sg-m-a": ["ого"], "acc-sg-m-n": ["ый"], "acc-sg-n": ["ое"], "acc-sg-f": ["ую"],
    "acc-pl-a": ["ых"], "acc-pl-n": ["ые"],
}
# after a sibilant: `-щий`, `-вший`
SOFT_ENDINGS: Dict[str, List[str]] = {
    "nom-sg-m": ["ий"], "gen-sg-m": ["его"], "dat-sg-m": ["ему"], "ins-sg-m": ["им"], "prp-sg-m": ["ем"],
    "nom-sg-n": ["ее"], "gen-sg-n": ["его"], "dat-sg-n": ["ему"], "ins-sg-n": ["им"], "prp-sg-n": ["ем"],
    "nom-sg-f": ["ая"], "gen-sg-f": ["ей"], "dat-sg-f": ["ей"], "ins-sg-f": ["ей", "ею"], "prp-sg-f": ["ей"],
    "nom-pl": ["ие"], "gen-pl": ["их"], "dat-pl": ["им"], "ins-pl": ["ими"], "prp-pl": ["их"],
    "acc-sg-m-a": ["его"], "acc-sg-m-n": ["ий"], "acc-sg-n": ["ее"], "acc-sg-f": ["ую"],
    "acc-pl-a": ["их"], "acc-pl-n": ["ие"],
}
SHORT_ENDINGS: Dict[str, str] = {"srt-sg-m": "", "srt-sg-f": "а", "srt-sg-n": "о", "srt-pl": "ы"}


def participle_form_name(form: str) -> Optional[str]:
    """
    The kind of a participle by its suffix, for the cell `Прич` of old articles.
    """
    plain = form.replace(SEGMENT_SEPARATOR, "")
    if plain.endswith("ся"):
        plain = plain[:-2]
    if re.search(r"[щ]ий$", plain):
        return "ptcp-prs-act"
    if re.search(r"ший$", plain):
        return "ptcp-pst-act"
    if re.search(r"мый$", plain):
        return "ptcp-prs-pass"
    if re.search(r"(нный|тый)$", plain):
        return "ptcp-pst-pass"
    return None


# the suffixes of participles, a form of another shape is probably an error in the article: `пережида́йнный`
PARTICIPLE_SHAPES: Dict[str, re.Pattern] = {
    "ptcp-prs-act": re.compile(r"[уюая]щий(ся)?$"),
    "ptcp-pst-act": re.compile(r"ший(ся)?$"),
    "ptcp-prs-pass": re.compile(r"[еоиё]мый$"),
    "ptcp-pst-pass": re.compile(r"([аяеёиоуыю]нн|т)ый$"),
}


def is_participle_shape(form: str, name: str) -> bool:
    return bool(PARTICIPLE_SHAPES[name].search(form.replace(SEGMENT_SEPARATOR, "")))


def decline_participle(form: str, passive: bool) -> Optional[Dict[str, List[str]]]:
    """
    Declines a participle given in the nominative masculine: `прочи́танный`, `пры́гающий`, `умыва́ющийся`.
    Passive participles get short forms: `прочитан`, `прочтён`, `прочтена`.
    :return: forms by name (the names of ADJ_FULL_FORMS and ADJ_SHORT_FORMS) or None if it is not a participle
    """
    reflexive = form.endswith("ся")
    base = form[:-2] if reflexive else form
    plain = base.replace(SEGMENT_SEPARATOR, "")
    if plain.endswith("ый"):
        endings = HARD_ENDINGS
    elif plain.endswith("ий") and plain[-3:-2] in ("ш", "щ"):
        endings = SOFT_ENDINGS
    else:
        return None
    stem = base[:-2]
    if not stem.endswith(SEGMENT_SEPARATOR):
        stem += SEGMENT_SEPARATOR
    suffix = "ся" if reflexive else ""
    result = {name: [stem + ending + suffix for ending in variants] for name, variants in endings.items()}
    if passive and not reflexive:
        short = stem.rstrip(SEGMENT_SEPARATOR)
        # `прочитанн` -> `прочитан`
        if short.replace(SEGMENT_SEPARATOR, "").endswith("нн"):
            short = short[:-1]
        # the stressed suffix `-ённ` keeps `ё` only in the masculine form: `прочтён`, `прочтена́`
        others = re.sub(r"ё(\|?н)$", r"е\1", short)
        for name, ending in SHORT_ENDINGS.items():
            result[name] = [(others if ending else short) + ending]
    return result
