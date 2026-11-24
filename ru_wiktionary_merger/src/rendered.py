"""
Word forms from the inflection tables rendered by `expand_morpho.py` (the wiki text the templates and Lua modules
expand to). The tables are HTML (`<table class="morfotable ru">`) with `rowspan` and `colspan`.

The marks of the templates are kept for each form:
`assumed` — `*` "данная форма предположительна или малоупотребима" (`краткая=−`, `{{incorrect}}`),
`difficult` — `*` "образование данной формы затруднительно" (`краткая=✕`),
`irregular` — `△` "нерегулярная форма" (`{{особ.ф.}}`),
`label:<title>` — a label before the form: `label:разговорное` for `разг. ловче́й`.
"""
import html
import re
from typing import Dict, List, Optional, Tuple

from unicodedata import normalize

from lxml import etree, html as lxml_html

from src.utils.etc import LATIN_HOMOGLYPHS

MARKS = {
    "предположительна": "assumed",
    "затруднительно": "difficult",
    "нерегулярная форма": "irregular",
}
WIKI_LINK = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]|]*)\]\]")
TAG = re.compile(r"<[^<>]*>")
# variants in a cell: `то́чной<br/>то́чною`, `ненаси́льственен //<br/>ненаси́льствен`, `сильне́е, посильне́е`;
# only outside tags: `style="font-size:x-small; text-decoration: none;"`
VARIANT_SEPARATOR = re.compile(r"//|,|;")
BR = re.compile(r"<br\s*/?>")
SPLIT = "\x00"


def split_variants(cell_html: str) -> List[str]:
    parts = []
    for part in re.split(r"(<[^<>]*>)", cell_html):
        if part.startswith("<"):
            parts.append(SPLIT if BR.fullmatch(part) else part)
        else:
            parts.append(VARIANT_SEPARATOR.sub(SPLIT, part))
    return "".join(parts).split(SPLIT)
ABSENT_VALUES = {"", "—", "-", "−", "–"}
# the value may have italics of its own: `''[[дешевле]] ''и'' [[подешевле]] ''(в значении цены)''''.`,
# `''[[мерзее]] (встречается также более редкий вариант ''[[мерзче]]'')''.`; it ends with `''.`
COMPARATIVE = re.compile(r"Сравнительная степень(?:&nbsp;|&#160;|\s)*—(?:&nbsp;|&#160;|&#32;|\s)*''(.*?)''\.", re.S)
NO_COMPARATIVE = "Сравнительная степень не образуется"

Form = Tuple[str, List[str]]


CYRILLIC = re.compile(r"[а-яёА-ЯЁ]")


def fix_homoglyphs(word: str) -> str:
    """
    Stressed vowels are sometimes typed with Latin letters: `пальмитáтный` with `á` (U+00E1).
    """
    if not CYRILLIC.search(word):
        return word
    return normalize("NFC", normalize("NFD", word).translate(LATIN_HOMOGLYPHS))


# a label before a form: `[[Викисловарь:Условные сокращения|<span class="label mark" title="разговорное">разг.</span>]]`
LABEL = re.compile(r'<span class="label[^"]*"[^>]*>.*?</span>', re.S)
TITLE = re.compile(r'title="([^"]*)"')


def cell_marks(cell_html: str) -> List[str]:
    marks = {mark for text, mark in MARKS.items() if text in cell_html}
    marks |= {"label:" + title.group(1) for label in LABEL.findall(cell_html) for title in [TITLE.search(label)] if title}
    return sorted(marks)


def clean_text(text: str) -> str:
    text = re.sub(r"<sup>.*?</sup>", "", text, flags=re.S)
    text = LABEL.sub("", text)
    text = WIKI_LINK.sub(r"\1", text)
    text = TAG.sub("", text)
    text = html.unescape(text).replace("''", "")
    # `устар.: здоро́вее` without the label
    return text.replace("*", "").replace("△", "").replace("\xa0", " ").strip().lstrip(":").strip()


def split_forms(cell_html: str, marks_per_variant: bool = False, split_spaces: bool = False) \
        -> Tuple[List[Form], List[str]]:
    """
    The forms of a cell and the problems: unexpanded parameters (`{{{основа1}}}`), several words.
    The marks of the cell apply to all its variants (a mark may span several of them), unless `marks_per_variant`.
    `split_spaces`: a space separates variants too (`сту́женой сту́женою`), tables of adjectives have no analytic forms.
    """
    forms, problems = [], []
    marks = cell_marks(cell_html)
    for variant in split_variants(cell_html):
        text = clean_text(variant)
        if text in ABSENT_VALUES:
            continue
        if "{{" in text or "}}" in text:
            problems.append("не раскрылось: " + text)
            continue
        if text.isdigit():
            problems.append("в статье номер вместо формы: " + text)
            continue
        if " " in text and not split_spaces:
            problems.append("несколько слов: " + text)
            continue
        words = text.split() if split_spaces else [text]
        for word in words:
            if word not in ABSENT_VALUES:
                forms.append((fix_homoglyphs(word), cell_marks(variant) if marks_per_variant else marks))
    return forms, problems


def table_grid(table_html: str) -> List[List[Tuple[str, str]]]:
    """
    The cells of a table as a grid, the cells with `rowspan` and `colspan` are repeated: rows of (tag, inner html).
    """
    table = lxml_html.fragment_fromstring(table_html)
    grid: Dict[Tuple[int, int], Tuple[str, str]] = {}
    rows = table.xpath(".//tr")
    for r, row in enumerate(rows):
        c = 0
        for cell in row:
            if cell.tag not in ("th", "td"):
                continue
            while (r, c) in grid:
                c += 1
            inner = (cell.text or "") + "".join(etree.tostring(child, encoding="unicode") for child in cell)
            rowspan, colspan = int(cell.get("rowspan", 1) or 1), int(cell.get("colspan", 1) or 1)
            for dr in range(rowspan):
                for dc in range(colspan):
                    grid[(r + dr, c + dc)] = (cell.tag, inner)
            c += colspan
    height = max((r for r, _ in grid), default=-1) + 1
    width = max((c for _, c in grid), default=-1) + 1
    return [[grid.get((r, c), ("td", "")) for c in range(width)] for r in range(height)]


ADJ_CASES = {"Им.": "nom", "Р.": "gen", "Д.": "dat", "В.": "acc", "Тв.": "ins", "Пр.": "prp"}
ADJ_COLUMNS = (("муж", "sg-m"), ("ср", "sg-n"), ("жен", "sg-f"), ("мн", "pl"))


def adjective_form_name(case: str, animacy: Optional[str], column: str) -> str:
    if case == "srt":
        return f"srt-{column}"
    if case == "acc" and column in ("sg-m", "pl"):
        return f"acc-{column}-{animacy}"
    return f"{case}-{column}"


def adjective_table(expanded: str) -> Tuple[Dict[str, List[Form]], List[str]]:
    """
    The forms of the table `прил`: `nom-sg-m`, ..., `acc-sg-m-a`, `acc-sg-m-n`, `srt-sg-f`.
    """
    match = re.search(r"<table.*?</table>", expanded, re.S)
    if not match:
        return {}, []
    grid = table_grid(match.group(0))
    columns: Dict[int, str] = {}
    for c in range(len(grid[0]) if grid else 0):
        header = " ".join(clean_text(row[c][1]) for row in grid if all(tag == "th" for tag, _ in row))
        for key, name in ADJ_COLUMNS:
            if key in header:
                columns[c] = name
                break
    forms: Dict[str, List[Form]] = {}
    problems = []
    for row in grid:
        if all(tag == "th" for tag, _ in row):
            continue
        headers = [clean_text(inner) for tag, inner in row if tag == "th"]
        case = next((ADJ_CASES[h] for h in headers if h in ADJ_CASES), None)
        if any(h.startswith("Кратк") for h in headers):
            case = "srt"
        if not case:
            problems.append("строка таблицы не распознана: " + " ".join(headers))
            continue
        animacy = "a" if "одуш." in headers else "n" if "неод." in headers else None
        for c, (tag, inner) in enumerate(row):
            if tag != "td" or c not in columns:
                continue
            name = adjective_form_name(case, animacy, columns[c])
            cell_forms, cell_problems = split_forms(inner, split_spaces=True)
            problems += [f"{name}: {p}" for p in cell_problems]
            for form in cell_forms:
                if form not in forms.setdefault(name, []):
                    forms[name].append(form)
    forms = {name: values for name, values in forms.items() if values}
    fix_adjective_accusative(forms)
    fix_plural_only_table(forms)
    return forms, problems


def fix_adjective_accusative(forms: Dict[str, List[Form]]) -> None:
    """
    A table of a substantivized adjective with `anim` has one row `В.`: `блаже́нненького` is animate,
    the form is the genitive or the nominative.
    """
    for column in ("sg-m", "pl"):
        values = forms.pop(f"acc-{column}-None", None)
        if not values:
            continue
        accusative = {form for form, _ in values}
        animacy = "a" if accusative & {form for form, _ in forms.get(f"gen-{column}", [])} else "n"
        forms[f"acc-{column}-{animacy}"] = values


def fix_plural_only_table(forms: Dict[str, List[Form]]) -> None:
    """
    A broken table of a plural only adjective puts the forms in the column `жен. р.`
    (`хлора́нтовые`, `хлора́нтовых`); they are moved to the plural.
    """
    columns = {re.sub(r"-(a|n|None)$", "", name.split("-", 1)[1]) for name in forms if not name.startswith("srt-")}
    if len(columns) != 1 or "pl" in columns:
        return
    column = columns.pop()
    nominative = [form for form, _ in forms.get(f"nom-{column}", [])]
    if not nominative or not all(clean_text(form).replace("́", "").endswith(("ые", "ие")) for form in nominative):
        return
    for name in [name for name in forms if not name.startswith("srt-")]:
        case = name.split("-")[0]
        forms["acc-pl-n" if case == "acc" else f"{case}-pl"] = forms.pop(name)
    # the animate accusative is the genitive, the table has one row `В.`
    if "gen-pl" in forms:
        forms["acc-pl-a"] = forms["gen-pl"]


def comparative(expanded: str) -> Tuple[Optional[List[Form]], List[str]]:
    """
    The line `Сравнительная степень — точне́е, точне́й.` under the table; None if there is no line or
    `Сравнительная степень не образуется.` A comment in parentheses is dropped: `(образуются супплетивно)`.
    """
    if NO_COMPARATIVE in expanded:
        return None, []
    match = COMPARATIVE.search(expanded)
    if not match:
        return None, []
    value = re.sub(r"\([^()]*\)", "", match.group(1))
    # italic labels between the forms: `деше́вле ''и'' подеше́вле`
    value = re.sub(r"''[^']*''", ",", value)
    forms, problems = split_forms(value, marks_per_variant=True)
    return forms or None, problems
