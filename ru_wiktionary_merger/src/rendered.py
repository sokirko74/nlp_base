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
# variants in a cell: `то́чной<br/>то́чною`, `ненаси́льственен //<br/>ненаси́льствен`, `сильне́е, посильне́е`,
# `насо́лит / насоли́т`; only outside tags: `style="font-size:x-small; text-decoration: none;"`;
# parentheses separate variants in verbs only (`ту́хнул (ту́х)`), elsewhere they are prepositions (`(в) лесу́`)
VARIANT_SEPARATOR = re.compile(r"//|/|,|;")
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
COMPARATIVE_PLAIN = re.compile(r"Сравнительная степень(?:&nbsp;|&#160;|\s)*—(?:&nbsp;|&#160;|&#32;|\s)*"
                               r"((?:\[\[|&#42;|<span).*?)\.(?=\[\[Категория|<|\s|$)", re.S)
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


def without_stress(form: str) -> str:
    return normalize("NFC", re.sub("[\u0300\u0301]", "", normalize("NFD", form)))


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


# the words of analytic forms of pronouns: `о ко́м`, `ни о ко́м`, `(не) о чем`
ANALYTIC_WORDS = {"о", "об", "обо", "ни", "не", "в", "во", "на", "при", "кой", "кое", "у"}


def split_forms(cell_html: str, marks_per_variant: bool = False, split_spaces: bool = False,
                skip_analytic: bool = False) -> Tuple[List[Form], List[str]]:
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
        if skip_analytic and len(words) > 1 and \
                any(without_stress(word).lower() in ANALYTIC_WORDS or word.startswith("(") for word in words):
            problems.append("аналитическая форма: " + text)
            continue
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
    # adverbs and predicatives show it without italics: `Сравнительная степень — [[ближе]].`
    match = COMPARATIVE.search(expanded) or COMPARATIVE_PLAIN.search(expanded)
    if not match:
        return None, []
    value = re.sub(r"\([^()]*\)", "", match.group(1))
    # italic labels between the forms: `деше́вле ''и'' подеше́вле`
    value = re.sub(r"''[^']*''", ",", value)
    forms, problems = split_forms(value, marks_per_variant=True)
    return forms or None, problems


# the rows of the table of nouns (`сущ ru ...`, `сущ-ru`): the second genitive and prepositional of aot are
# `Разд.` (partitive, `ле́су`) and `М.` (locative, `(в) лесу́`); `Прит.`, `Сч.`, `Превр.` are not used
NOUN_CASES = {"Им.": "nom", "Р.": "gen", "Д.": "dat", "В.": "acc", "Тв.": "ins", "Пр.": "prp",
              "М.": "loc", "Разд.": "prt", "Зв.": "voc"}
NOUN_NUMBERS = ("sg", "pl")
# the cells of the locative and the partitive have prepositions and several variants: `(в) лесу́`,
# `в та́зе и в тазу́`, `(в) сло́е ''и'' (в) слою́`, `(в, на) элѐктрошкафу́`
SECOND_CASE_WORDS = {"в", "во", "на", "при", "о", "об", "у", "и", "или"}


def wiki_table_rows(text: str) -> List[List[Tuple[str, str]]]:
    """
    The rows of the first wiki table (`{| ... |}`): (tag, content) of the cells, `th` for `!`, `td` for `|`;
    the attributes of a cell are dropped (`class="grey" | ле́су`).
    """
    start = text.find("{|")
    end = text.find("|}", start)
    if start < 0 or end < 0:
        return []
    rows, row = [], None
    for line in text[start:end].split("\n")[1:]:
        line = line.strip()
        if line.startswith("|-"):
            row = []
            rows.append(row)
            continue
        if not line or line[0] not in "!|" or line.startswith("|+"):
            continue
        if row is None:
            row = []
            rows.append(row)
        tag = "th" if line[0] == "!" else "td"
        for cell in re.split(r"!!|\|\|", line[1:]):
            # `attributes | content`, a `|` of a link is not a separator
            match = re.match(r'^\s*(?:[\w-]+\s*=\s*"[^"]*"\s*)+\|(?!\|)', cell)
            row.append((tag, cell[match.end():] if match else cell))
    return [row for row in rows if row]


def noun_table(expanded: str) -> Tuple[Dict[str, List[Form]], List[str]]:
    """
    The forms of the table of a noun: `nom-sg`, ..., `prp-pl`, `loc-sg` (the locative, without the preposition),
    `prt-sg` (the partitive), `voc-sg`.
    """
    forms: Dict[str, List[Form]] = {}
    problems = []
    for row in wiki_table_rows(expanded):
        headers = [clean_text(content) for tag, content in row if tag == "th"]
        cells = [content for tag, content in row if tag == "td"]
        case = next((NOUN_CASES[h] for h in headers if h in NOUN_CASES), None)
        if not case or not cells:
            continue
        for number, cell in zip(NOUN_NUMBERS, cells):
            if case in ("loc", "prt"):
                cell = re.sub(r"\([^()]*\)|''", " ", cell)
                words = [w for w in re.split(r"[\s,;/]+|&nbsp;|&#160;", clean_text(cell))
                         if w and w.lower() not in SECOND_CASE_WORDS]
                cell = "<br>".join(words)
            cell_forms, cell_problems = split_forms(cell)
            name = f"{case}-{number}"
            problems += [f"{name}: {p}" for p in cell_problems]
            for form in cell_forms:
                if form not in forms.setdefault(name, []):
                    forms[name].append(form)
    return {name: values for name, values in forms.items() if values}, problems


# `мужской или средний род` (`евро`, `тирамису`): the first one, as the old generation took it
NOUN_GENDERS = (("общий род", "mas,fem"), ("мужской или средний род", "mas"), ("мужской род", "mas"),
                ("женский род", "fem"), ("средний род", "neu"))


def noun_grammems(expanded: str) -> Dict[str, object]:
    """
    The grammems of the line under the table: `Существительное, одушевлённое, общий род (...), 1-е склонение
    (тип склонения 3a ...)`, `...; формы ед. ч. не используются`. None if the line does not say it.
    """
    match = re.search(r"\[\[существительное\|Существительное\]\](.*?)(?:\[\[Категория|$)", expanded, re.S)
    line = clean_text(match.group(1)) if match else ""
    head = re.split(r"\(тип склонения", line)[0]
    animate = False if "неодушевлённое" in head else True if "одушевлённое" in head else None
    gender = next((value for text, value in NOUN_GENDERS if text in head), None)
    # without the line (`дупель`) the categories of the page are used
    categories = " ".join(re.findall(r"\[\[Категория:([^\]|]*)", expanded))
    if gender is None:
        gender = next((value for text, value in (("Мужской род/", "mas"), ("Женский род/", "fem"),
                                                 ("Средний род/", "neu")) if text in categories), None)
    if animate is None:
        animate = False if "Неодушевлённые/" in categories else True if "Одушевлённые/" in categories else None
    return {
        "gender": gender,
        "animate": animate,
        "plural_only": "формы ед. ч. не используются" in line,
        # the index with `−` (`1a−`): "формы мн. ч. предположительны или неупотребимы"
        "singular_only": "формы мн. ч. не используются" in line or "формы мн. ч. предположительны" in line,
        "indeclinable": "несклоняемое" in head,
    }


# the table of verbs (`Гл-блок`, `гл-ru`): the sections and their rows
VERB_SECTIONS = {"Настоящее время": "npst", "Будущее время": "npst", "Настоящее/будущее время": "npst",
                 "Прошедшее время": "pst", "Повелительное наклонение": "imp", "Причастия": "ptcp",
                 "Деепричастия": "ger"}
VERB_PERSONS = {"1-е лицо": "1", "2-е лицо": "2", "3-е лицо": "3"}
VERB_GENDERS = {"м. р.": "m", "ж. р.": "f", "с. р.": "n"}
VERB_PARTICIPLES = {"действ. наст.": "prs-act", "действ. прош.": "pst-act", "страд. наст.": "prs-pass",
                    "страд. прош.": "pst-pass"}
VERB_GERUNDS = {"наст. вр.": "prs", "прош. вр.": "pst"}


def verb_row_names(section: str, label: str, cells: int) -> List[Optional[str]]:
    """
    The form names of the data cells of a row: `1-е лицо` of the present -> [npst-sg-1, npst-pl-1].
    """
    if section in ("npst", "imp") and label in VERB_PERSONS:
        person = VERB_PERSONS[label]
        return [f"{section}-sg-{person}", f"{section}-pl-{person}"]
    if section == "pst" and label in VERB_GENDERS:
        return [f"pst-sg-{VERB_GENDERS[label]}", "pst-pl"]
    if section == "ptcp" and label in VERB_PARTICIPLES:
        return [f"ptcp-{VERB_PARTICIPLES[label]}"] * cells
    if section == "ger" and label in VERB_GERUNDS:
        return [f"ger-{VERB_GERUNDS[label]}"] * cells
    return []


def verb_table(expanded: str) -> Tuple[Dict[str, List[Form]], List[str]]:
    """
    The forms of the table of a verb: `npst-sg-1` ... `npst-pl-3` (the present or the future), `pst-sg-m`,
    `pst-sg-f`, `pst-sg-n`, `pst-pl`, `imp-sg-2`, `imp-pl-2`, `imp-pl-1`, `ptcp-prs-act` ... `ptcp-pst-pass`
    (the nominative masculine), `ger-prs`, `ger-pst`. The analytic future (`бу́ду/бу́дешь… бежа́ть`) is not used.
    The infinitive is not in the table, it is the title of the article.
    """
    match = re.search(r"<table.*?</table>", expanded, re.S)
    if not match:
        return {}, []
    forms: Dict[str, List[Form]] = {}
    problems = []
    section = None
    seen = set()
    for row in table_grid(match.group(0)):
        headers = [clean_text(inner) for tag, inner in row if tag == "th"]
        if row and all(tag == "th" for tag, _ in row):
            title = headers[0] if len(set(headers)) == 1 else None
            if title in VERB_SECTIONS:
                section = VERB_SECTIONS[title]
            continue
        cells = [inner for tag, inner in row if tag == "td"]
        if not headers:
            # the analytic future: one cell without a header
            continue
        names = verb_row_names(section, headers[0], len(cells))
        for name, cell in zip(names, cells):
            # a cell with `rowspan` (the past plural) is repeated in the grid
            if (name, cell) in seen:
                continue
            seen.add((name, cell))
            # a mark belongs to one variant: `расплетя́сь, *расплётшись`; `ту́хнул (ту́х)` are two variants
            cell_forms, cell_problems = split_forms(re.sub(r"[()]", ",", cell), marks_per_variant=True)
            problems += [f"{name}: {p}" for p in cell_problems]
            for form in cell_forms:
                if form not in forms.setdefault(name, []):
                    forms[name].append(form)
    return {name: values for name, values in forms.items() if values}, problems


# the table `morfotable` of `быть` (`гл ru ^a/c`): the columns are the tenses, the rows are the pronouns; the rows of
# the participles and gerunds are HTML rows inside the wiki table
MORFOTABLE_COLUMNS = {"наст.": "prs", "будущ.": "fut", "прош.": "pst", "повелит.": "imp"}
# `Они` before `Он` (`Он<br />Она<br />Оно`)
MORFOTABLE_PERSONS = (("Ты", "sg-2"), ("Они", "pl-3"), ("Он", "sg-3"), ("Мы", "pl-1"), ("Вы", "pl-2"), ("Я", "sg-1"))
MORFOTABLE_ROWS = {"Пр. действ. наст.": "ptcp-prs-act", "Пр. действ. прош.": "ptcp-pst-act",
                   "Пр. страд. наст.": "ptcp-prs-pass", "Пр. страд. прош.": "ptcp-pst-pass",
                   "Деепр. наст.": "ger-prs", "Деепр. прош.": "ger-pst"}
PAST_GENDERS = ("m", "f", "n")


def morfotable(expanded: str) -> Tuple[Dict[str, List[Form]], List[str]]:
    """
    The forms of the table `morfotable` (`быть`): `prs-sg-1` ... (the present), `fut-sg-1` ... (the future), `pst-sg-m`
    ..., `imp-sg-2`, `imp-pl-2`, the participles and gerunds as in `verb_table`. The variants with a footnote
    (`есмь`, `еси́`, `суть`, `бу́ди`, `су́щий`: obsolete) are not used.
    """
    if 'class="morfotable' not in expanded:
        return {}, []
    start = expanded.find("{|")
    end = expanded.find("\n|}", start)
    part = expanded[start:end + 3]
    forms: Dict[str, List[Form]] = {}
    problems = []

    def add(name: str, cell: str):
        for variant in re.split(r",|\(|\)", cell):
            if "<sup>" in variant:
                problems.append(f"{name}: a form with a footnote is not used: {clean_text(variant)}")
                continue
            cell_forms, cell_problems = split_forms(variant)
            problems.extend(f"{name}: {p}" for p in cell_problems)
            for form in cell_forms:
                if form not in forms.setdefault(name, []):
                    forms[name].append(form)

    wiki_html = wiki_table_html(part)
    rows = table_grid(wiki_html) if wiki_html else []
    columns = []
    for row in rows:
        headers = [clean_text(inner) for tag, inner in row if tag == "th"]
        cells = [inner for tag, inner in row if tag == "td"]
        if not cells:
            columns = [MORFOTABLE_COLUMNS.get(h) for h in headers[1:]]
            continue
        person = next((name for label, name in MORFOTABLE_PERSONS if headers and headers[0].startswith(label)), None)
        if not person:
            continue
        for column, cell in zip(columns, cells):
            if column in ("prs", "fut"):
                add(f"{column}-{person}", cell)
            elif column == "imp" and person in ("sg-2", "pl-2"):
                add(f"imp-{person}", cell)
            elif column == "pst":
                if person.startswith("pl"):
                    add("pst-pl", cell)
                else:
                    for gender, variant in zip(PAST_GENDERS, re.split(r"<br\s*/?>", cell)):
                        add(f"pst-sg-{gender}", variant)
    for row in re.findall(r"<tr>.*?</tr>", part, re.S):
        grid = table_grid(f"<table>{row}</table>")
        if not grid:
            continue
        headers = [clean_text(inner) for tag, inner in grid[0] if tag == "th"]
        cells = [inner for tag, inner in grid[0] if tag == "td"]
        name = MORFOTABLE_ROWS.get(headers[0]) if headers else None
        if name and cells:
            add(name, cells[0])
    # `[[был]]` of the row `Я` next to `бы́л` of the row `Он`: the form without the stress is a duplicate
    for name, values in forms.items():
        stressed = {without_stress(form) for form, _ in values if form != without_stress(form)}
        forms[name] = [(form, marks) for form, marks in values if form != without_stress(form) or form not in stressed]
    return {name: values for name, values in forms.items() if values}, problems


def verb_properties(expanded: str) -> Dict[str, object]:
    """
    The line under the table: `Глагол, совершенный вид, переходный, безличный, тип спряжения ...`.
    """
    tail = expanded[expanded.find("</table>"):] if "</table>" in expanded else expanded
    match = re.search(r"Глагол(.*?)тип спряжения", tail, re.S)
    line = clean_text(match.group(1)) if match else ""
    aspect = "both" if "двувидовой" in line else "impf" if "несовершенный вид" in line else \
        "pf" if "совершенный вид" in line else None
    transitive = False if "непереходный" in line else True if "переходный" in line else None
    return {"aspect": aspect, "transitive": transitive, "impersonal": "безличный" in line}


# the table of surnames (`Фам-блок`): the columns `м.`, `ж.`, `мн. ч.` or (`Фам-блок-мж`) the singular and the plural
# of each gender; the plural is common: `Ива́новы`
SURNAME_COLUMNS = {3: ("sg-m", "sg-f", "pl"), 4: ("sg-m", "pl", "sg-f", "pl")}


def surname_table(expanded: str) -> Tuple[Dict[str, List[Form]], List[str]]:
    """
    The forms of the table of a surname: `nom-sg-m`, `nom-sg-f`, `nom-pl`, ...
    """
    forms: Dict[str, List[Form]] = {}
    problems = []
    for row in wiki_table_rows(expanded):
        headers = [clean_text(content) for tag, content in row if tag == "th"]
        cells = [content for tag, content in row if tag == "td"]
        case = next((NOUN_CASES[h] for h in headers if h in NOUN_CASES), None)
        columns = SURNAME_COLUMNS.get(len(cells))
        if not case or case not in CASES_OF_TABLES or not columns:
            continue
        for column, cell in zip(columns, cells):
            name = f"{case}-{column}"
            cell_forms, cell_problems = split_forms(cell)
            problems += [f"{name}: {p}" for p in cell_problems]
            for form in cell_forms:
                if form not in forms.setdefault(name, []):
                    forms[name].append(form)
    return {name: values for name, values in forms.items() if values}, problems


CASES_OF_TABLES = ("nom", "gen", "dat", "acc", "ins", "prp")


# the attributes of a cell of a wiki table: `colspan=2 | Им.`, `style="..." | падеж`
WIKI_CELL_ATTRIBUTES = re.compile(r"""^\s*((?:[\w-]+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s|"']+)\s*)+)\|(?!\|)""")


def wiki_table_html(text: str) -> Optional[str]:
    """
    The first wiki table (`{| ... |}`) as an HTML table, the cells keep `rowspan` and `colspan`.
    """
    start = text.find("{|")
    end = text.find("\n|}", start)
    if start < 0 or end < 0:
        return None
    rows, row = [], None
    for line in text[start:end].split("\n")[1:]:
        line = line.strip()
        if line.startswith("|-"):
            row = []
            rows.append(row)
            continue
        if not line or line[0] not in "!|" or line.startswith("|+"):
            continue
        if row is None:
            row = []
            rows.append(row)
        tag = "th" if line[0] == "!" else "td"
        # `|| [[предложный|Пр.]] || ...`: the row starts with an empty separator
        content_line = line[2:] if line[:2] in ("||", "!!") else line[1:]
        for cell in re.split(r"!!|\|\|", content_line):
            match = WIKI_CELL_ATTRIBUTES.match(cell)
            attributes = " ".join(re.findall(r"(?:rowspan|colspan)\s*=\s*[\"']?\d+", match.group(1), re.I)) if match else ""
            attributes = re.sub(r"\s*=\s*[\"']?", '="', attributes)
            attributes = re.sub(r'="(\d+)', r'="\1"', attributes)
            content = cell[match.end():] if match else cell
            row.append(f"<{tag} {attributes.lower()}>{content}</{tag}>")
    body = "".join("<tr>" + "".join(cells) + "</tr>" for cells in rows if cells)
    return f"<table>{body}</table>" if body else None


CASE_LABELS = {"Им.": "nom", "Р.": "gen", "Род.": "gen", "Рд.": "gen", "Д.": "dat", "Дат.": "dat", "Дт.": "dat",
               "В.": "acc", "Вин.": "acc", "Вн.": "acc", "Тв.": "ins", "Твор.": "ins", "Пр.": "prp", "Предл.": "prp"}


def case_label(text: str) -> Optional[str]:
    """
    `case`, `anim`, `inan` or None: the labels of rows, also in cells `|` (`двое`, `полтора`);
    `acc-split`: `В. (одуш./неодуш.)` of `один`, a cell has the animate and the inanimate form (`одного́<br>оди́н`).
    """
    if re.match(r"В\.\s*\(\s*одуш\.\s*/\s*неодуш\.\s*\)", text):
        return "acc-split"
    if text in CASE_LABELS:
        return CASE_LABELS[text]
    if text.startswith("одуш"):
        return "anim"
    if text.startswith("неод"):
        return "inan"
    return None


def case_column_keys(header: str) -> List[str]:
    """
    The name parts of a column of a case table: `ед. ч.` -> sg, `мн. ч.` -> pl, `муж., ср.` -> m, n,
    `ед. ч. м.` -> sg-m, `форма`, `разговорная форма` -> "" (one column).
    """
    text = header.lower()
    number = "sg" if "ед" in text else "pl" if "мн" in text else None
    if number == "pl":
        return ["pl"]
    genders = [gender for gender, pattern in (("m", r"муж|(?<![а-яё])м\."), ("n", r"ср|(?<![а-яё])с\."),
                                                ("f", r"жен|(?<![а-яё])ж\.")) if re.search(pattern, text)]
    if genders:
        return [("sg-" if number else "") + gender for gender in genders]
    return ["sg"] if number else [""]


def case_table(expanded: str) -> Tuple[Dict[str, List[Form]], List[str]]:
    """
    The table of a pronoun or a numeral. An HTML table is the table `прил` (`этот`, `свой`, `Лизин`), the names are
    those of adjectives; a wiki table gives `nom` (`кто`), `acc-a`/`acc-n` (`три`), `nom-sg`/`nom-pl` (`тысяча`),
    `nom-m`/`nom-n`/`nom-f` (`два`), `nom-sg-m` (`один`), see `case_table_grammems` of `src/slf.py`.
    """
    if "<table" in expanded and expanded.find("<table") < (expanded.find("{|") + 1 or len(expanded)):
        return adjective_table(expanded)
    table = wiki_table_html(expanded)
    if not table:
        return {}, []
    grid = table_grid(table)
    # a label keeps its `<sup>`: `В.&nbsp;(<sup>одуш.</sup>/<sub>неодуш.</sub>)`
    def label_of(inner: str) -> Optional[str]:
        return case_label(clean_text(re.sub(r"</?su[pb]>", "", inner)))

    header_rows = [row for row in grid if not any(label_of(inner) for _, inner in row)]
    forms: Dict[str, List[Form]] = {}
    problems = []
    for row in grid:
        labels = [label_of(inner) for _, inner in row]
        case = next((label for label in labels if label and label not in ("anim", "inan")), None)
        if not case:
            continue
        split = case == "acc-split"
        case = "acc" if split else case
        animacy = "a" if "anim" in labels else "n" if "inan" in labels else None
        seen = set()
        for c, (tag, inner) in enumerate(row):
            if labels[c] or tag == "th":
                continue
            header = " ".join(clean_text(header_row[c][1]) for header_row in header_rows if c < len(header_row))
            keys = case_column_keys(header)
            if (inner, tuple(keys)) in seen:
                continue
            seen.add((inner, tuple(keys)))
            # `(н)его́` is `его́` and `него́`; `(не) о чем` is an analytic form
            inner = re.sub(r"\(([а-яё]+)\)([а-яё\u0301]+)", r"\2, \1\2", inner)
            cell_forms, cell_problems = split_forms(inner, split_spaces=True, skip_analytic=True)
            # `одного́<br>оди́н`: the animate and the inanimate form; one form is both (`одно́`, `одну́`)
            groups = [("a", cell_forms[:1]), ("n", cell_forms[1:])] if split and len(cell_forms) == 2 else \
                [(animacy if case == "acc" else None, cell_forms)]
            for key in keys:
                for group_animacy, group_forms in groups:
                    name = case + (f"-{key}" if key else "") + (f"-{group_animacy}" if group_animacy else "")
                    problems += [f"{name}: {p}" for p in cell_problems]
                    for form in group_forms:
                        if form not in forms.setdefault(name, []):
                            forms[name].append(form)
    return {name: values for name, values in forms.items() if values}, problems
