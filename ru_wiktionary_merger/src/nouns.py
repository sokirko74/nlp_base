"""
Nouns of the template `{{сущ-ru|кни́га|ж 3a}}`: the table is rendered by a Lua module and is not in the dump.
The Zaliznyak index is reduced to a template `сущ ru f ina 3a`, the stems of the template are derived from the lemma.
"""
import re
from typing import Dict, List, Optional, Tuple

from src.utils.etc import clean_string

VOWELS = "аеёиоуыэюя"
SIBILANTS = "жшчщц"
# the gender and the animacy of the index -> the words of a template name
GENDERS = {"м": "m ina", "мо": "m a", "ж": "f ina", "жо": "f a", "с": "n ina", "со": "n a"}
COMMON_GENDERS = ("мо-жо", "жо-мо")
GENDER_PATTERN = r"мо-жо|жо-мо|мо|жо|со|м|ж|с|[mfn] (?:a|ina)"
# `мн. <ж 3*a>`, `мн. одуш. <п 1a>`, `мн. неод. 0`
PLURAL_ONLY = re.compile(r"^мн\.\s*(одуш\.|неод\.)?\s*(.*)$")
CASE_FORM_NAME = re.compile(r"^(nom|gen|dat|acc|ins|prp)-(sg|pl)2?$")


class TNounIndex:
    """
    The parsed index of `сущ-ru`: the template name, the gender and the animacy of the word,
    `plural_only` (`мн.`) and `singular_only` (the mark `—` or `-` after the index: no plural).
    """
    def __init__(self, template: str, gender: str, animate: bool, index: str):
        self.template = template
        self.gender = gender
        self.animate = animate
        self.index = index
        self.plural_only = False
        self.singular_only = False
        # the animacy of the template, it may differ from the one of the word: there is no `сущ ru m a 3c`
        self.template_animate = animate


def index_variants(index: str) -> List[str]:
    """
    The index as written and reduced to existing templates: `1a①` -> `1a(1)`, `1a÷` -> `1a`, `1a[(2)]` -> `1a(2)`.
    """
    variants = [index]

    def add(value):
        value = value.strip()
        if value and value not in variants:
            variants.append(value)
    current = index
    for old, new in (("①", "(1)"), ("②", "(2)"), ("③", "(3)"), ("[", ""), ("]", ""), ("÷", ""), ("~", ""),
                     ("((", "("), ("))", ")")):
        current = current.replace(old, new)
        add(current)
    add(re.sub(r"\(\d\)", "", current))
    add(re.sub(r"\(\d\)|\^", "", current))
    return variants


def parse_noun_index(raw: str, lemma: str, templates: dict, redirects: dict, plural_only: bool = False) \
        -> Tuple[Optional[TNounIndex], str]:
    """
    `ж 3*a` -> `сущ ru f ina 3*a`; `мо <п 1a>` (declined as an adjective) -> `сущ ru m a (п 1a)`;
    `мо <жо 3*a>` (masculine, declined as feminine) -> `сущ ru f a 3*a` with the masculine gender;
    `мо-жо 1a` (the common gender) -> by the ending of the lemma.
    :return: the index or None and the reason
    """
    plural_param = plural_only
    index = re.sub(r"<!--.*?-->", "", raw).strip()
    # remarks: `м 1a, Р2`, `м 1a Р₂` (the second genitive is given by the parameter `Р`)
    index = re.sub(r",?\s*[РМП][2₂](\(.*?\))?$", "", index).strip()
    # `м 4b, ё`; `м, 1a`; `мн <с 7a>`; variants: `мо//м 1a`, `м 1c(1)//1a` (the first one is taken)
    index = re.sub(r",?\s+ё$", "", index)
    index = re.sub(r"^(мн)\.?,?\s*", r"\1. ", index) if index.startswith("мн") else index
    index = re.sub(r"^([а-я-]+)//[а-я-]+", r"\1", index)
    index = re.sub(r"^([а-я-]+(?:\.\s*[а-я]+\.)?)\s*,\s*", r"\1 ", index)
    index = re.sub(r"//\S+$", "", index).strip()
    index = re.sub(r"^мн\. (одуш\.|неод\.),", r"мн. \1", index)
    plural_only, plural_animacy = False, None
    m = PLURAL_ONLY.match(index)
    if m:
        plural_only, plural_animacy, index = True, m.group(1), m.group(2).strip()
        m = re.match(r"^<(.*)>$", index)
        if m:
            index = m.group(1).strip()
            # `мн. <п 1a>`: an adjective without a gender
            if index.startswith("п "):
                index = ("мо" if plural_animacy == "одуш." else "м") + " <" + index + ">"
        elif re.match(r"^\d", index):
            index = ("мо " if plural_animacy == "одуш." else "м ") + index
    singular_only = False
    if re.search(r"[—-]$", index) and not re.search(r"-[а-я]+$", index):
        singular_only, index = True, index[:-1].strip()
    m = re.match(rf"^({GENDER_PATTERN})\s*<(?:(п)\s+(.*)|({GENDER_PATTERN})\s+(.*))>$", index)
    if m:
        gender_mark = m.group(1)
        if m.group(2):
            declension_gender, declension = gender_mark, f"(п {m.group(3).strip()})"
        else:
            declension_gender, declension = m.group(4), m.group(5).strip()
    else:
        m = re.match(rf"^({GENDER_PATTERN})\s+(\S+)$", index)
        if not m:
            return None, f"Lua-модуль «сущ-ru»: не разобран индекс «{raw}»"
        gender_mark, declension = m.groups()
        declension_gender = gender_mark
    plain = clean_string(lemma)
    if gender_mark in COMMON_GENDERS:
        gender, animate = "mas,fem", True
    else:
        words = GENDERS.get(gender_mark, gender_mark).split()
        gender, animate = {"m": "mas", "f": "fem", "n": "neu"}[words[0]], words[1] == "a"
    if plural_animacy:
        animate = plural_animacy == "одуш."
    if declension_gender in COMMON_GENDERS:
        declension_gender = "жо" if plain.endswith(("а", "я")) else "мо"
    words = GENDERS.get(declension_gender, declension_gender).split()
    # the animacy of the declension is the animacy of the word: `мо <жо 3*a>`
    template_gender = words[0] + (" a" if animate else " ina")
    variants = index_variants(declension)
    # the type 8 after a sibilant has `-ам`, `-ами`, `-ах`: `брешь`, `ночь`
    if re.match(r"^8", declension) and re.search(r"[жшчщ]ь$", plain):
        variants = [v + "-ш" for v in variants] + variants
    for variant in variants:
        for animacy in (template_gender, words[0] + (" ina" if animate else " a")):
            name = f"сущ ru {animacy} {variant}"
            name = redirects.get(name, name)
            if name in templates:
                result = TNounIndex(name, gender, animate, declension)
                result.plural_only, result.singular_only = plural_only or plural_param, singular_only
                result.template_animate = animacy.endswith(" a")
                return result, ""
    return None, f"Lua-модуль «сущ-ru»: нет шаблона для индекса «{raw}»"


def resolve_noun_template(name: str, templates: dict, redirects: dict) -> Tuple[Optional[str], bool]:
    """
    A template name of an article that is not a template: `сущ ru m ina 1a((2))` -> `сущ ru m ina 1a(2)`,
    `сущ ru f ina 1b?` -> `сущ ru f ina 1b`, `сущ ru m ina 3*bX` -> `сущ ru m ina 3*b`;
    the index in brackets is a plurale tantum: `сущ ru f ina (3*a)` (`сутки`) -> `сущ ru f ina 3*a`.
    :return: the template name or None, plurale tantum
    """
    m = re.match(r"^(сущ ru (?:[mfn] )?(?:a|ina)) (.+)$", name)
    if not m:
        return None, False
    prefix, index = m.groups()
    plural_only = False
    pt = re.match(r"^\(([0-9][^()]*(?:\([^()]*\))?)\)$", index)
    if pt:
        plural_only, index = True, pt.group(1)
    variants = []
    for variant in index_variants(index):
        for v in (variant, variant.replace("?", ""), re.sub(r"X$", "", variant), re.sub(r"-$", "", variant)):
            if v not in variants:
                variants.append(v)
    for variant in variants:
        candidate = f"{prefix} {variant}"
        candidate = redirects.get(candidate, candidate)
        if candidate in templates:
            return candidate, plural_only
    return None, False


def drop_fleeting_vowel(stem: str) -> Optional[str]:
    """
    The stem of the oblique cases of masculine nouns with Zaliznyak's `*`: `кусок` -> `куск`, `боец` -> `бойц`,
    `палец` -> `пальц`, `лёд` -> `льд`, `соловей` -> `соловь`, `любовь` (the stem `любов`) -> `любв`.
    """
    if re.search(r"[её]й$", stem):
        return stem[:-2] + "ь"
    if len(stem) < 2 or stem[-1] in VOWELS or stem[-2] not in "оеё":
        return None
    before = stem[:-2]
    if stem[-2] in "её" and before and before[-1] in VOWELS:
        return before + "й" + stem[-1]
    if stem[-2] in "её" and before.endswith("л"):
        return before + "ь" + stem[-1]
    # `козырёк` -> `козырьк`, `огонёк` -> `огоньк`, but `кусочек` -> `кусочк`, `котёл` -> `котл`
    if stem[-2:] == "ёк" and before and before[-1] not in VOWELS + SIBILANTS:
        return before + "ьк"
    return before + stem[-1]


def insert_fleeting_vowel(stem: str, index: str) -> Optional[str]:
    """
    The stem of the genitive plural with Zaliznyak's `*`: `загадк` -> `загадок`, `ложк` -> `ложек`, `окн` -> `окон`,
    `чайк` -> `чаек`, `письм` -> `писем`, `сосн` -> `сосен`; the type 2 keeps the soft sign: `капл` -> `капель`;
    the type 6: `кель` -> `келий`, `стать` (6*b) -> `статей`.
    """
    stressed_ending = bool(re.search(r"\d\*?°?[bdf]", index))
    if stem.endswith("ь") and re.match(r"^6", index):
        return stem[:-1] + ("ей" if stressed_ending else "ий")
    if len(stem) < 2 or stem[-1] in VOWELS or stem[-2] in VOWELS:
        return None
    first, last = stem[-2], stem[-1]
    if first in "йь":
        result = stem[:-2] + "е" + last
    elif first in "кгх" or (last in "кгх" and first not in SIBILANTS):
        result = stem[:-1] + "о" + last
    else:
        result = stem[:-1] + "е" + last
    # but `башня` -> `башен` (`кухонь`, `деревень` are given in the articles)
    if re.match(r"^2", index) and last != "н":
        result += "ь"
    return result


def stem_forms(template: dict) -> Dict[str, set]:
    result = {}
    for form, stems in template.items():
        for name in stems:
            result.setdefault(name, set()).add(form)
    return result


def derive_noun_stems(lemma: str, template: dict, index: TNounIndex) -> Tuple[Optional[Dict[str, str]], str]:
    """
    The stems of the template from the lemma (as they would be written in an article, without stress marks).
    The stem of the lemma is the lemma without the ending of the template; the other stems are the same
    (they differ by the stress only) except for the fleeting vowel (`*`) and `°`: `крестьянин` -> `крестьян`,
    `котёнок` -> `котят`.
    """
    plain = clean_string(lemma)
    lemma_form = "nom-pl" if index.plural_only else "nom-sg"
    if lemma_form not in template:
        return None, f"в шаблоне «{index.template}» нет формы {lemma_form}"
    (lemma_stem_name, ending), = template[lemma_form].items()
    ending = ending.replace("|", "")
    if not plain.endswith(ending):
        return None, f"лемма «{plain}» не кончается на «{ending}» шаблона «{index.template}»"
    base = plain[:len(plain) - len(ending)] if ending else plain
    if not base:
        return None, "пустая основа"
    stems = {lemma_stem_name: base}
    lemma_forms = stem_forms(template)[lemma_stem_name]
    for name, forms in stem_forms(template).items():
        if name == lemma_stem_name:
            continue
        stem = base
        if "°" in index.index and "gen-pl" in forms and "nom-pl" in forms:
            if base.endswith("ин"):
                stem = base[:-2]
            elif re.search(r"[оё]нок$", base):
                stem = base[:-4] + ("ат" if base[-5:-4] in SIBILANTS else "ят")
            elif re.search(r"[оё]ночек$", base):
                stem = base[:-6] + ("атк" if base[-7:-6] in SIBILANTS else "ятк")
            else:
                return None, f"не выделена основа «{name}» (°) из «{plain}»"
        elif re.match(r"^6", index.index) and "*" not in index.index and forms <= {"gen-pl", "acc-pl"} \
                and base[-1] in VOWELS and not template["gen-pl"].get(name):
            # the type 6 without `*`: `шея` -> `шей`
            stem = base + "й"
        elif "*" in index.index or "°" in index.index:
            oblique_singular = forms & {"gen-sg", "dat-sg", "ins-sg", "prp-sg"}
            if oblique_singular and not lemma_forms & {"gen-sg", "dat-sg", "ins-sg", "prp-sg"}:
                stem = drop_fleeting_vowel(base)
            elif "gen-pl" in forms and not forms & {"nom-pl", "dat-pl"}:
                stem = insert_fleeting_vowel(base, index.index)
            if stem is None:
                return None, f"не выделена основа «{name}» (беглая гласная) из «{plain}»"
        stems[name] = stem
    return stems, ""


def fix_accusative(forms: Dict[str, str], index: TNounIndex) -> None:
    """
    The animate accusative is the genitive, the inanimate one is the nominative; in the singular only for
    the masculine declension (`друг`, but not `сирота`). It is needed for a template of the other animacy (there is
    no `сущ ru m a 3c`) and for wrong templates (`сущ ru f ina 6a` has `acc-pl` = `gen-pl`: `идей`).
    """
    source = "gen" if index.animate else "nom"
    if f"{source}-pl" in forms:
        forms["acc-pl"] = forms[f"{source}-pl"]
    lemma = clean_string(forms.get("nom-sg", "")) if isinstance(forms.get("nom-sg"), str) else ""
    if index.template.split()[2] == "m" and f"{source}-sg" in forms and not lemma.endswith(("а", "я")):
        forms["acc-sg"] = forms[f"{source}-sg"]


def explicit_forms(info: dict) -> Dict[str, List[str]]:
    """
    Forms given in the article: `gen-pl=друзе́й`, `ins-sg=ло́сем //\\nлосём`; `—` and `-` mean the form is absent.
    """
    result = {}
    for name, value in info.items():
        if not CASE_FORM_NAME.match(name) or not value.strip():
            continue
        value = re.sub(r"<!--.*?-->|<[^<>]*>|\{\{.*?\}\}|\[\[(?:[^|\]]*\|)?|\]\]", " ", value)
        variants = [clean_string(v) for v in re.split(r"//|,|;|\n", value)]
        result[name] = [v for v in variants if v]
    return result
