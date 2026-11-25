"""
Generates the word forms of Russian Wiktionary articles from the inflection tables rendered by `expand_morpho.py`
(`src/rendered.py`): `--pos noun`, `adj`, `verb`, `other`, `surname`.
"""
import argparse
import json
import re
from typing import List, Dict, Optional, Tuple

from constants import WRITE_PATHS, ADJ_FULL_FORMS, ADJ_COMPARATIVE, VERB_TABLE_TEMPLATE, INVARIABLE_TEMPLATES, \
    PRONOUN_NUMERAL_PREFIXES, SURNAME_PREFIXES, PARTICLES, ABBREVIATION_ROLES
from src.rendered import case_table, surname_table, adjective_table, comparative, noun_table, noun_grammems, \
    verb_table, verb_properties, without_stress
from src.surnames import guess_surname_template
from src.utils.etc import determine_pos, basic_json_read, read_redirects, replace_redirect, clean_string, \
    remove_comments, clean_stem_markup
from src.verbs import decline_participle, is_participle_shape, participle_form_name

PAGE_NAME = re.compile(r"\{\{\s*(?:subst:)?PAGENAME\s*\}\}")
# the forms of the rendered tables with these marks are not generated, see `generate_adjective_forms`
DROPPED_MARKS = {"assumed", "difficult"}


def normalize_word(word: str) -> str:
    return clean_string(word).replace("ё", "е").lower()


class TWiktionary:
    def __init__(self, args):
        self.args = args
        self.articles = None
        self.redirects = None
        self.articles_by_title = None
        self.failures = []
        self.verbs = []
        self.wtp = None

    def read_db(self):
        articles = basic_json_read(self.args.input_articles)
        self.redirects = read_redirects(WRITE_PATHS["template_redirect"])
        self.articles = [replace_redirect(self.normalize_article(article), self.redirects) for article in articles]
        # participles with an article of their own: `агитированный` (`{{прич.|агитировать}}`)
        self.participle_articles = [article for article in self.articles if article["morpho"].get("participle_of")]
        self.expanded = self.read_expanded()

    def read_expanded(self) -> Dict[Tuple[int, Optional[str]], dict]:
        """
        The inflection templates expanded by `expand_morpho.py`, by the article id and the homonym label.
        """
        # only the articles of this part of speech: the whole file does not fit in memory well;
        # the template name may differ, a redirect is resolved in the articles (`прил ru (мс 6*a)` -> `Мс-п6*a`)
        keys = {(article["id"], article.get("homonym")) for article in self.articles
                if determine_pos(article) == self.args.pos or
                self.args.pos == "verb" and article["morpho"].get("template") == VERB_TABLE_TEMPLATE or
                self.args.pos == "surname" and (article["morpho"].get("template") or "").startswith(SURNAME_PREFIXES) or
                # the comparative of adverbs, the tables of pronouns and numerals, the bases of `который-то`
                self.args.pos == "other" and (determine_pos(article) == "adj" or
                                              remove_comments(article["morpho"].get("template") or "").strip()
                                              in INVARIABLE_TEMPLATES or
                                              (article["morpho"].get("template") or "").startswith(PRONOUN_NUMERAL_PREFIXES))}
        result = {}
        with open(self.args.expanded) as inp:
            for line in inp:
                record = json.loads(line)
                key = (record["id"], record.get("homonym"))
                if key in keys:
                    result[key] = record
        return result

    def generate_noun_forms(self, article) -> Tuple[Optional[dict], Optional[str], List[str]]:
        """
        The forms of the table rendered by MediaWiki templates and Lua modules (`expand_morpho.py`): the cases,
        `loc-sg` (the locative `М.`, the second prepositional of aot), `prt-sg` (the partitive `Разд.`, the second
        genitive of aot), `voc-sg`. The grammems of the line under the table (gender, animacy, `формы ед. ч. не
        используются`, `несклоняемое`) are stored in `morpho.rendered_grammems`. The forms marked with `*` are
        dropped, as for adjectives; the marks are kept in `form_marks`.
        """
        record = self.expanded.get((article["id"], article.get("homonym")))
        if not record:
            return None, "шаблон не раскрыт (нет в expanded.jsonl)", []
        if "error" in record:
            return None, "ошибка раскрытия шаблона: " + record["error"], []
        table, warnings = noun_table(record["expanded"])
        if not table:
            return None, "в раскрытом шаблоне нет таблицы: " + re.sub(r"\s+", " ", record["expanded"]).strip()[:80], []
        generated_forms, marks = {}, {}
        for name, forms in table.items():
            kept = [form for form, form_marks in forms if not DROPPED_MARKS & set(form_marks)]
            if kept:
                generated_forms[name] = kept
            for form, form_marks in forms:
                if form_marks:
                    marks.setdefault(name, {})[form] = form_marks
        if marks:
            article["form_marks"] = marks
        article["morpho"]["rendered_grammems"] = noun_grammems(record["expanded"])
        lemmas = generated_forms.get("nom-sg", []) + generated_forms.get("nom-pl", [])
        if normalize_word(article["title"]) not in map(normalize_word, lemmas):
            return None, f"начальная форма таблицы «{lemmas[0] if lemmas else ''}» ≠ заголовку", []
        return generated_forms, None, warnings

    def process_noun(self, article, outp):
        generated_forms, problem, warnings = self.generate_noun_forms(article)
        if problem:
            self.add_failure(article, problem)
            return
        for warning in warnings:
            self.add_failure(article, "предупреждение: " + warning)
        article["generated_forms"] = generated_forms
        outp.write(json.dumps(article, ensure_ascii=False) + "\n")

    @staticmethod
    def normalize_article(article: dict) -> dict:
        """
        `основа={{PAGENAME}}` is the title of the article, `основа={{{основа|Брессон}}}` is `Брессон`,
        the template name may have a comment: `Фам ru иностр-м<!-- 1a ~ 0-->`.
        """
        morpho = article["morpho"]
        if morpho.get("template"):
            morpho["template"] = remove_comments(morpho["template"]).strip()
        for group in ("stems", "info"):
            for name, value in morpho.get(group, {}).items():
                if "PAGENAME" in value:
                    morpho[group][name] = PAGE_NAME.sub(article["title"], value)
        for name, value in morpho.get("stems", {}).items():
            if "{{{" in value:
                morpho["stems"][name] = clean_stem_markup(value)
        return article

    def add_failure(self, article, reason):
        title = article["title"]
        if "homonym" in article:
            title += f" ({article['homonym']})"
        self.failures.append((title, article["morpho"]["template"], reason))

    def indeclinable_adjective_forms(self, article) -> dict:
        """
        `прил ru 0`: all full forms are the lemma, there are no short forms.
        """
        return {name: [clean_string(article["title"])] for name in ADJ_FULL_FORMS}

    def generate_adjective_forms(self, article) -> Tuple[Optional[dict], Optional[str], List[str]]:
        """
        The forms of the table rendered by MediaWiki templates and Lua modules (`expand_morpho.py`), with the
        comparative of the line `Сравнительная степень — точне́е, точне́й`. The forms marked with `*` are dropped,
        as the old generation did it: `assumed` ("данная форма предположительна или малоупотребима": the short forms
        of the indices with ✕, ⊠, −, `{{incorrect|е́дче}}`) and `difficult` ("образование данной формы
        затруднительно"); all marks, also `irregular` (△), are kept in `form_marks`.
        """
        article_template = remove_comments(article["morpho"]["template"]).strip()
        if article_template == "прил ru":
            return None, "не указан тип по Зализняку (шаблон «прил ru» без параметров)", []
        if article_template == "прил ru 0":
            article["indeclinable"] = True
            return self.indeclinable_adjective_forms(article), None, []
        if article_template == "прил ru сравн":
            return None, "сравнительная степень («прил ru сравн»), не склоняется", []
        record = self.expanded.get((article["id"], article.get("homonym")))
        if not record:
            return None, "шаблон не раскрыт (нет в expanded.jsonl)", []
        if "error" in record:
            return None, "ошибка раскрытия шаблона: " + record["error"], []
        table, warnings = adjective_table(record["expanded"])
        if not table:
            return None, "в раскрытом шаблоне нет таблицы: " + re.sub(r"\s+", " ", record["expanded"]).strip()[:80], []
        comparatives, problems = comparative(record["expanded"])
        warnings += ["сравнительная степень, " + problem for problem in problems]
        if comparatives:
            table["comp"] = comparatives
        if article_template == "прил-ru":
            self.mark_module_forms(article["morpho"]["info"], table)
        generated_forms, marks = {}, {}
        for name, forms in table.items():
            kept = [(form, form_marks) for form, form_marks in forms if not DROPPED_MARKS & set(form_marks)]
            if kept:
                generated_forms[name] = [form for form, _ in kept]
            for form, form_marks in forms:
                if form_marks:
                    marks.setdefault(name, {})[form] = form_marks
        if marks:
            article["form_marks"] = marks
        lemmas = [form for name in ("nom-sg-m", "nom-sg-f", "nom-sg-n", "nom-pl", "srt-sg-m")
                  for form in generated_forms.get(name, [])]
        if normalize_word(article["title"]) not in map(normalize_word, lemmas):
            return None, f"начальная форма таблицы «{lemmas[0] if lemmas else ''}» ≠ заголовку", []
        return generated_forms, None, warnings

    @staticmethod
    def mark_module_forms(info: dict, table: dict) -> None:
        """
        The Lua module of `прил-ru` builds the comparative and the short forms of every adjective without `~` or ✕
        in the index, also of relative ones (`гиперзвукове́е`, `кружко́вы`): such a form gets the mark `module`, it is
        not a decision of the editor. Not marked: the forms given in the article (`степень=`, `srt-sg-m=`).
        """
        for name, forms in table.items():
            if name == "comp":
                given = info.get(ADJ_COMPARATIVE, "").strip()
            elif name.startswith("srt-"):
                given = info.get(name, "").strip()
            else:
                continue
            if not given:
                table[name] = [(form, sorted(set(form_marks) | {"module"})) for form, form_marks in forms]

    def process_adjective(self, article, outp):
        generated_forms, problem, warnings = self.generate_adjective_forms(article)
        if problem:
            self.add_failure(article, problem)
        else:
            for warning in warnings:
                self.add_failure(article, "предупреждение: " + warning)
            article["generated_forms"] = generated_forms
            outp.write(json.dumps(article, ensure_ascii=False) + "\n")

    @staticmethod
    def participle_problem(title: str, verb: dict) -> Optional[str]:
        name = participle_form_name(title)
        if not name or not is_participle_shape(title, name):
            return "не похоже на причастие"
        # two letters: the root may alternate (блещущий of блистать), a wrong link (неизменяемый of изменять) differs
        if normalize_word(title)[:2] != normalize_word(verb["title"])[:2]:
            return f"начало не совпадает с глаголом «{verb['title']}»"
        if name.endswith("pass") and not verb.get("transitive"):
            return f"страдательное причастие непереходного глагола «{verb['title']}»"
        if "-prs-" in name and verb.get("aspect") == "pf":
            return f"причастие настоящего времени глагола совершенного вида «{verb['title']}»"
        if "-prs-" in name and verb.get("frequentative"):
            return f"причастие настоящего времени многократного глагола «{verb['title']}»"
        return None

    def add_participle_articles(self):
        """
        A participle with an article of its own (`{{прич.|агитировать}}`) is added to its verb if no table of a verb
        has it: the table of an imperfective verb `гл ru 2a` has the past passive participle only with the parameter
        `ПричСтрадПрош`. A participle in a table (`засыпанный` of the perfective `засыпать`, the table links to the
        article) is already there. The verb must be the only one with this title, the other cases are failures.
        """
        table_participles, verbs = set(), {}
        for verb in self.verbs:
            verbs.setdefault(normalize_word(verb["title"]), []).append(verb)
            for name, values in verb["generated_forms"].items():
                if name.startswith("ptcp-") and name.endswith("-nom-sg-m"):
                    table_participles.update(normalize_word(v) for v in values)
        for participle in self.participle_articles:
            title = participle["title"]
            if normalize_word(title) in table_participles:
                continue
            verb_title = participle["morpho"]["participle_of"]
            candidates = verbs.get(normalize_word(verb_title), [])
            if len(candidates) != 1:
                self.add_failure(participle, f"причастие: глагол «{verb_title}» не найден" if not candidates else
                                 f"причастие: у глагола «{verb_title}» {len(candidates)} омонима")
                continue
            verb = candidates[0]
            problem = self.participle_problem(title, verb)
            if problem:
                self.add_failure(participle, "причастие: " + problem)
                continue
            name = participle_form_name(title)
            declined = decline_participle(title, name.endswith("pass"))
            if declined is None:
                self.add_failure(participle, "причастие: не склоняется")
                continue
            for case, forms in declined.items():
                verb["generated_forms"].setdefault(f"{name}-{case}", []).extend(forms)
            verb.setdefault("participle_articles", []).append(title)

    def generate_verb_forms(self, article) -> Tuple[Optional[dict], Optional[str], List[str]]:
        """
        The forms of the table rendered by MediaWiki templates and Lua modules (`expand_morpho.py`); the infinitive
        is the title, the participles of the table are declined by `decline_participle`. The aspect, the
        transitivity and `безличный` are taken from the line under the table. As the old generation did, the
        forms marked as `assumed` (`*` "данная форма предположительна", `бежи́мый`) are not generated, the forms
        marked as `difficult` (`моги́`) are generated and listed in `difficult`; the marks are kept in `form_marks`.
        """
        article_template = remove_comments(article["morpho"]["template"]).strip()
        if article_template == "гл ru":
            return None, "не указан тип по Зализняку (шаблон «гл ru» без параметров)", []
        record = self.expanded.get((article["id"], article.get("homonym")))
        if not record:
            return None, "шаблон не раскрыт (нет в expanded.jsonl)", []
        if "error" in record:
            return None, "ошибка раскрытия шаблона: " + record["error"], []
        table, warnings = verb_table(record["expanded"])
        if not table:
            return None, "в раскрытом шаблоне нет таблицы: " + re.sub(r"\s+", " ", record["expanded"]).strip()[:80], []
        properties = verb_properties(record["expanded"])
        generated_forms, marks, difficult = {"inf": [article["title"]]}, {}, set()

        def add(name, forms):
            for form in forms:
                if form not in generated_forms.setdefault(name, []):
                    generated_forms[name].append(form)

        for name, forms in table.items():
            for form, form_marks in forms:
                if form_marks:
                    marks.setdefault(name, {})[form] = form_marks
                if "assumed" in form_marks:
                    continue
                form_name = name
                if form_name.startswith("ptcp"):
                    plain = without_stress(form)
                    # a template without the stem gives `нный`, `а́нный` (`запутешествовать`, `2aСВ`); the root
                    # may alternate, so the beginning is not compared with the verb (`шлющийся` of `слаться`)
                    if re.fullmatch(r"[аяеёиоуыю]?нн(ый|ий)(ся)?", normalize_word(plain)):
                        warnings.append(f"причастие «{form}» без основы")
                        continue
                    if not is_participle_shape(plain, form_name):
                        # `тя́нутый` in the cell of the present passive participle
                        other = form_name.replace("prs", "pst") if "prs" in form_name else None
                        if other and is_participle_shape(plain, other):
                            warnings.append(f"«{form}» — причастие прошедшего времени")
                            form_name = other
                        else:
                            warnings.append(f"подозрительная форма причастия «{form}»")
                    declined = decline_participle(form, form_name.endswith("pass"))
                    if declined is None:
                        warnings.append(f"«{form}» не склоняется как причастие")
                        continue
                    for case, case_forms in declined.items():
                        add(f"{form_name}-{case}", case_forms)
                else:
                    add(form_name, [form])
                if "difficult" in form_marks:
                    difficult.add(form_name)
        if marks:
            article["form_marks"] = marks
        article["aspect"] = properties["aspect"]
        article["transitive"] = bool(properties["transitive"])
        if properties["impersonal"]:
            article["impersonal"] = True
        # verbs of repeated action (`хаживать`) have no present forms in the table
        if properties["aspect"] == "impf" and not properties["impersonal"] and \
                not any(name.startswith("npst-") for name in generated_forms):
            article["frequentative"] = True
        if difficult:
            article["difficult"] = sorted(difficult)
        return generated_forms, None, warnings

    def process_verb(self, article, outp):
        """
        The verbs are written by `write_verbs`, after all tables are built.
        """
        generated_forms, problem, warnings = self.generate_verb_forms(article)
        if problem:
            self.add_failure(article, problem)
        else:
            for warning in warnings:
                self.add_failure(article, "предупреждение: " + warning)
            article["generated_forms"] = generated_forms
            self.verbs.append(article)

    def write_verbs(self, outp):
        self.add_participle_articles()
        for verb in self.verbs:
            outp.write(json.dumps(verb, ensure_ascii=False) + "\n")

    @staticmethod
    def pronoun_numeral_pos(article) -> Optional[str]:
        """
        The part of speech by the template or by the header after a table given in the article.
        """
        names = [article["morpho"]["template"]] + article["morpho"].get("section_templates", [])
        if any(name.startswith("числ") for name in names):
            return "num"
        if any(name.startswith(("мест", "Мс")) for name in names):
            # `мест ru 1a-н`: possessive adjectives with the pronominal declension, `мамин`
            kind = article["morpho"]["info"].get("часть речи", "")
            if kind.startswith("Прилагательное") or article["morpho"]["template"] in ("мест ru 1a-н", "мест ru 1a-в"):
                return "padj"
            return "pron"
        return None

    def find_paradigm(self, title: str) -> Optional[dict]:
        """
        The forms of another word, a pronoun or an adjective: the base of `который-то`.
        """
        if self.articles_by_title is None:
            self.articles_by_title = {}
            for article in self.articles:
                self.articles_by_title.setdefault(article["title"], []).append(article)
        for article in self.articles_by_title.get(title, []):
            article_template = remove_comments(article["morpho"].get("template") or "").strip()
            copy = json.loads(json.dumps(article))
            if determine_pos(article) == "adj":
                forms, problem, _ = self.generate_adjective_forms(copy)
            elif article_template.startswith(PRONOUN_NUMERAL_PREFIXES):
                forms, problem, _ = self.generate_pronoun_numeral_forms(copy)
            else:
                continue
            # an indeclinable word without a table is not a base
            if forms and "inv" not in forms:
                return forms
        return None

    def generate_untabled_forms(self, article) -> Tuple[Optional[dict], Optional[str], List[str]]:
        """
        A pronoun or a numeral with a header but without a table: `который-то` is declined as `который`,
        `какой-никакой` as `какой` twice; other words are taken as indeclinable, with `no_table`.
        """
        parts = article["title"].split("-")
        if len(parts) == 2:
            first = self.find_paradigm(parts[0])
            if first and parts[1] in PARTICLES:
                forms = {name: [form + "-" + parts[1] for form in variants]
                         for name, variants in first.items() if name != "comp"}
                return forms, None, [f"формы построены по слову «{parts[0]}» с частицей"]
            second = self.find_paradigm(parts[1])
            if first and second:
                forms = {name: [first[name][0] + "-" + second[name][0]]
                         for name in first if name in second and name != "comp"}
                return forms, None, [f"формы построены по словам «{parts[0]}» и «{parts[1]}»"]
        article["no_table"] = True
        return {"inv": [clean_string(article["title"])]}, None, ["нет таблицы склонения, взята одна форма"]

    @staticmethod
    def abbreviation_role(article) -> dict:
        """
        `{{abbrev|роль=существительного мужского рода единственного числа}}`: what the abbreviation is used as.
        """
        role = article["morpho"]["info"].get("роль", "").strip()
        result = {"role": role} if role else {}
        for pattern, key, value in ABBREVIATION_ROLES:
            if pattern in role:
                result.setdefault(key, value)
        return result

    def rendered_record(self, article) -> Tuple[Optional[dict], Optional[str]]:
        record = self.expanded.get((article["id"], article.get("homonym")))
        if not record:
            return None, "шаблон не раскрыт (нет в expanded.jsonl)"
        if "error" in record:
            return None, "ошибка раскрытия шаблона: " + record["error"]
        return record, None

    def generate_invariable_forms(self, article) -> Tuple[Optional[dict], Optional[str], List[str]]:
        """
        Adverbs, particles, prepositions etc.: the only form is the title; the comparative is the line
        `Сравнительная степень — [[ближе]].` of the rendered page (adverbs, predicatives).
        """
        info = article["morpho"]["info"]
        generated_forms = {"inv": [clean_string(article["title"])]}
        warnings = []
        record, _ = self.rendered_record(article)
        if record:
            comparatives, problems = comparative(record["expanded"])
            if comparatives:
                # as the old generation did, a difficult comparative is kept (`зя́бче`), an assumed one is not
                generated_forms["comp"] = [form for form, marks in comparatives if "assumed" not in marks]
            warnings += ["сравнительная степень, " + problem for problem in problems]
        # `{{adv ru|или=частица}}`: the word is also another part of speech
        also = [info[name].strip() for name in ("или", "или1", "или2") if info.get(name, "").strip()]
        if also:
            article["also"] = also
        return generated_forms, None, warnings

    def generate_pronoun_numeral_forms(self, article) -> Tuple[Optional[dict], Optional[str], List[str]]:
        """
        Pronouns and numerals: the rendered table (`src/rendered.py`, `case_table`), an HTML table `прил`
        (`этот`, `Лизин`) or a wiki table of cases (`кто`, `два`, `один`); without a table the forms are built
        by the base words (`который-то`) or the word is indeclinable, see `generate_untabled_forms`.
        """
        record, problem = self.rendered_record(article)
        if problem:
            return None, problem, []
        table, warnings = case_table(record["expanded"])
        if not table:
            return self.generate_untabled_forms(article)
        generated_forms, marks = {}, {}
        for name, forms in table.items():
            kept = [form for form, form_marks in forms if not DROPPED_MARKS & set(form_marks)]
            if kept:
                generated_forms[name] = kept
            for form, form_marks in forms:
                if form_marks:
                    marks.setdefault(name, {})[form] = form_marks
        if marks:
            article["form_marks"] = marks
        lemmas = [form for name in ("nom", "nom-sg", "nom-sg-m", "nom-m", "nom-pl") for form in generated_forms.get(name, [])]
        if lemmas and normalize_word(article["title"]) not in map(normalize_word, lemmas):
            return None, f"начальная форма таблицы «{lemmas[0]}» ≠ заголовку", []
        return generated_forms, None, warnings

    def process_other(self, article, outp):
        article_template = remove_comments(article["morpho"]["template"]).strip()
        if article_template in INVARIABLE_TEMPLATES:
            pos = INVARIABLE_TEMPLATES[article_template]
            generated_forms, problem, warnings = self.generate_invariable_forms(article)
        elif article_template == "abbrev":
            pos = "abbr"
            article.update(self.abbreviation_role(article))
            generated_forms, problem, warnings = {"inv": [clean_string(article["title"])]}, None, []
        elif article_template.startswith(PRONOUN_NUMERAL_PREFIXES):
            pos = self.pronoun_numeral_pos(article)
            if pos is None:
                return
            generated_forms, problem, warnings = self.generate_pronoun_numeral_forms(article)
        else:
            return
        if problem:
            self.add_failure(article, problem)
            return
        for warning in warnings:
            self.add_failure(article, "предупреждение: " + warning)
        article["pos"] = pos
        article["generated_forms"] = generated_forms
        outp.write(json.dumps(article, ensure_ascii=False) + "\n")

    def expand_template(self, call: str, title: str) -> str:
        """
        Expands a template call with `wikitextprocessor` (the database of `expand_morpho.py`).
        """
        if self.wtp is None:
            from wikitextprocessor import Wtp
            from expand_morpho import DB_PATH
            self.wtp = Wtp(db_path=DB_PATH, lang_code="ru", project="wiktionary")
        self.wtp.start_page(title)
        return self.wtp.expand(call, timeout=60)

    def generate_surname_forms(self, article) -> Tuple[Optional[dict], Optional[str], List[str]]:
        """
        The forms of the table `Фам-блок` rendered by `expand_morpho.py`. A surname with the header
        `{{Фам ru|основа=Хво́рост}}` has no table on the page: the template is chosen by the ending
        (`src/surnames.py`) and its call `{{Фам ru m 1a|основа=Хво́рост}}` is expanded the same way; both parts of
        a double surname are declined (`Гапонов-Грехов`, `Гапонова-Грехова`).
        """
        article_template = remove_comments(article["morpho"]["template"]).strip()
        if article_template in ("Фам ru", "Фам"):
            # the stem in the article is the whole surname with the stress (`Хво́рост`) or already a stem (`Капи́ц`)
            surname = clean_stem_markup(article["morpho"]["stems"].get("основа", ""))
            if normalize_word(surname) != normalize_word(article["title"]):
                surname = article["title"]
            parts_forms, guessed = [], []
            for part in surname.split("-"):
                template_and_stem = guess_surname_template(part)
                if not template_and_stem:
                    return None, f"нет таблицы склонения, тип не подобран по окончанию «{part}»", []
                template, stem = template_and_stem
                table, _ = surname_table(self.expand_template(f"{{{{{template}|основа={stem}}}}}", article["title"]))
                if not table:
                    return None, f"нет таблицы склонения, шаблон «{template}» не дал таблицы", []
                parts_forms.append({name: [form for form, _ in forms] for name, forms in table.items()})
                guessed.append(template)
            generated_forms = parts_forms[0] if len(parts_forms) == 1 else \
                {name: ["-".join(forms[name][0] for forms in parts_forms)]
                 for name in parts_forms[0] if all(forms.get(name) for forms in parts_forms)}
            if normalize_word(article["title"]) not in map(normalize_word, generated_forms.get("nom-sg-m", [])):
                return None, f"построенная начальная форма «{(generated_forms.get('nom-sg-m') or [''])[0]}» ≠ заголовку", []
            article["morpho"]["guessed_template"] = " + ".join(guessed)
            return generated_forms, None, [f"нет таблицы склонения, шаблон «{' + '.join(guessed)}» подобран по окончанию"]
        record = self.expanded.get((article["id"], article.get("homonym")))
        if not record:
            return None, "шаблон не раскрыт (нет в expanded.jsonl)", []
        if "error" in record:
            return None, "ошибка раскрытия шаблона: " + record["error"], []
        table, warnings = surname_table(record["expanded"])
        if not table:
            return None, "в раскрытом шаблоне нет таблицы: " + re.sub(r"\s+", " ", record["expanded"]).strip()[:80], []
        generated_forms, marks = {}, {}
        for name, forms in table.items():
            kept = [form for form, form_marks in forms if not DROPPED_MARKS & set(form_marks)]
            if kept:
                generated_forms[name] = kept
            for form, form_marks in forms:
                if form_marks:
                    marks.setdefault(name, {})[form] = form_marks
        if marks:
            article["form_marks"] = marks
        return generated_forms, None, warnings

    def process_surname(self, article, outp):
        generated_forms, problem, warnings = self.generate_surname_forms(article)
        if problem:
            self.add_failure(article, problem)
            return
        for warning in warnings:
            self.add_failure(article, "предупреждение: " + warning)
        article["pos"] = "surname"
        article["generated_forms"] = generated_forms
        outp.write(json.dumps(article, ensure_ascii=False) + "\n")

    def write_failures(self):
        with open(self.args.failures, "w") as outp:
            outp.write("title\ttemplate\treason\turl\n")
            for title, template, reason in sorted(self.failures, key=lambda f: (f[2], f[0])):
                url = "https://ru.wiktionary.org/wiki/" + title.split(" (")[0]
                outp.write(f"{title}\t{template}\t{reason}\t{url}\n")

    def generate_word_forms(self):
        with open(self.args.output_articles, "w") as outp:
            for article in self.articles:
                # proper names and obscene words are generated too: a morphological dictionary needs them,
                # and an article is marked as obscene if one of its meanings is (`агрегат`, `банан`)
                if self.args.pos == "surname":
                    template = article["morpho"].get("template") or ""
                    if template.startswith(SURNAME_PREFIXES):
                        self.process_surname(article, outp)
                    continue
                pos = determine_pos(article)
                if pos == "noun" and self.args.pos == "noun":
                    self.process_noun(article, outp)
                elif pos == "adj" and self.args.pos == "adj":
                    self.process_adjective(article, outp)
                elif self.args.pos == "verb" and (pos == "verb" or
                                                  article["morpho"].get("template") == VERB_TABLE_TEMPLATE):
                    self.process_verb(article, outp)
                elif self.args.pos == "other":
                    self.process_other(article, outp)
            if self.args.pos == "verb":
                self.write_verbs(outp)
        if self.args.failures:
            self.write_failures()


def parse_args():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('--output-articles', type=str, dest="output_articles", required=True)
    arg_parser.add_argument('--input-articles', type=str, dest="input_articles", default=WRITE_PATHS["article"],
                            help="the articles of `extract_from_dump.py`")
    arg_parser.add_argument('--expanded', type=str, default="tmp/expanded.jsonl",
                            help="the inflection templates expanded by `expand_morpho.py`")
    arg_parser.add_argument('--pos', type=str, choices=["noun", "adj", "verb", "other", "surname"], default="noun")
    arg_parser.add_argument('--failures', type=str, help="the words whose forms could not be built, the warnings")
    return arg_parser.parse_args()


if __name__ == '__main__':
    wkt = TWiktionary(parse_args())
    wkt.read_db()
    wkt.generate_word_forms()
