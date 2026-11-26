# ru_wiktionary_merger

Generates Russian paradigms from a dump of ru.wiktionary, exports them to the slf format of MorphWizard and compares
them with the Russian dictionary of aot.ru (`../data/Russian`), to merge them into it.

It is based on [RuWiktionaryParser](https://github.com/slowwavesleep/RuWiktionaryParser) by Aleksei Dorkin
(MIT license, see [LICENSE](LICENSE)), the history of that repository is kept. The original project parsed the
articles and generated nouns by its own evaluation of the inflection templates; here the templates and Lua modules are
expanded by `wikitextprocessor` the way MediaWiki renders the page, all parts of speech are taken from the rendered
tables, and the slf export and the comparison with aot.ru were added.

Use a virtual environment: `python -m venv venv; venv/bin/pip install -r requirements.txt` (on Debian/Ubuntu `venv`
needs the package `python3-venv`). Checked with Python 3.14.

## Data extraction
The input is the pages-articles dump of ru.wiktionary (`ruwiktionary-{date}-pages-articles.xml.bz2`, see
[the dumps](https://dumps.wikimedia.org/backup-index.html)), it is not unpacked; its path is set in
[config.yml](config.yml).

### Cache the dump
```
python cache_dump.py
```
Reads the dump once (about 5 minutes, `lbzip2` is used if installed) and stores the Russian
pages in `tmp/cache/pages.jsonl`: the Russian section of each article, Russian templates and
template redirects, and a few templates they call (`EXTRA_TEMPLATES`). The XML namespace version of the dump does not
matter.

### Extract the articles
```
python extract_from_dump.py                # articles and template redirects, about 3 minutes
python extract_from_dump.py --templates    # template redirects only, seconds
python extract_from_dump.py --articles     # articles only
```
Works with the cache (builds it first if it is missing, `--rebuild-cache` reads the dump again). Writes
`tmp/articles.jsonl`: the inflection template of the morphological section of each article with its parameters
(`morpho`), the morpheme segmentation (`segments`), proper names and obscene words are marked; homonyms (several
morphological sections on one page) give separate articles with a `homonym` label taken from the section header
(`I`, `II`, ...). `tmp/template_redirects.jsonl` gives the template a redirect points to: the part of speech of an
article is found by the name of its template.

#### An article
```
{
  "morpho": {
    "template": "сущ ru m ina 1a",
    "stems": {
      "основа": "перево́д"
    },
    "alternate": {},
    "forms": {},
    "info": {
      "слоги": "{{по-слогам|пе|ре|во́д}}"
    }
  },
  "segments": {
    "1": "пере-",
    "2": "вод",
    "и": "т"
  },
  "id": 3941,
  "title": "перевод",
  "type": "article",
  "is_proper": false,
  "is_obscene": false,
  "has_homonyms": false
}
```

## Expanded templates
```
python expand_morpho.py --load
python expand_morpho.py --processes 8
```
The inflection template of every article (`{{прил-ru|то́чный|1*a/c'}}`, `{{сущ ru m a 1a|...}}`) is expanded with
`wikitextprocessor` the way MediaWiki renders the page: it runs the Lua modules (`Модуль:inflection/ru/...`) and the
parser functions of the templates of the dump, so the result is the table of the page and the line
`Сравнительная степень — точне́е, точне́й`, that the dump does not have. `--load` puts the templates and modules of
the dump into `tmp/wtp_ru.db` (a minute), the second command writes `tmp/expanded.jsonl` (`id`, `title`, `homonym`,
`template`, `expanded`; 460 thousand templates, about 45 minutes in 8 processes). The template is chosen as in
`extract_from_dump.py`. MediaWiki joins the spaces of a template name (`{{прил ru  1*a|...}}`), `wikitextprocessor`
does not, the name is normalized before the expansion (also the invisible marks of the text direction of
`{{мест ru 1a-в\u200e|...}}`). An interrupted run is continued by `--resume`, a run apart
from the terminal: `setsid nohup python expand_morpho.py --processes 8 --resume >> tmp/expand_morpho.log 2>&1 &`.

## Generating word forms
```
python generate_wordforms.py --pos noun --output-articles result/nouns.jsonl --failures result/noun_failures.tsv
python generate_wordforms.py --pos adj --output-articles result/adjectives.jsonl --failures result/adj_failures.tsv
python generate_wordforms.py --pos verb --output-articles result/verbs.jsonl --failures result/verb_failures.tsv
python generate_wordforms.py --pos other --output-articles result/other.jsonl --failures result/other_failures.tsv
python generate_wordforms.py --pos surname --output-articles result/surnames.jsonl --failures result/surname_failures.tsv
```
The forms are taken from the templates expanded by `expand_morpho.py` (`--expanded`, `tmp/expanded.jsonl`), the
tables are parsed by `src/rendered.py`. Each form is a list of variants (`то́чной`, `то́чною`, separated by `<br>`,
commas, `/`, `//`); the stress marks are kept, the export drops them. Latin letters with a stress mark
(`пальмитáтный`) are replaced by Cyrillic ones. The marks of the templates are kept in `form_marks` (form name ->
form -> marks): `assumed` (`*` "данная форма предположительна или малоупотребима": the short forms of the indices
with ✕, ⊠, −, `{{incorrect|е́дче}}`), `difficult` (`*` "образование данной формы затруднительно"), `irregular`
(△, `{{особ.ф.|бли́же}}`), `label:<title>` (`разг. ловче́й`: `label:разговорное`), `module` (adjectives, see below).
The failures file lists the articles whose forms could not be built, with the reason and a link, and the warnings.
Errors of the articles are kept as the page shows them.

### Nouns
The wiki table of the cases (`nom-sg` ... `prp-pl`) and the grey rows `Разд.` (the partitive, the second genitive of
aot: `ле́су`), `М.` (the locative, the second prepositional of aot: `(в) лесу́`, `в та́зе и в тазу́` without the
prepositions and the usual form) and `Зв.` (the vocative: `дру́же`, `Тань`) as `prt-sg`, `loc-sg`, `voc-sg`; `Прит.`,
`Сч.`, `Превр.` are not used. The grammems are taken from the line under the table (`morpho.rendered_grammems`): the
animacy, the gender (`общий род` is `mas,fem`, `мужской или средний род` of `евро` is `mas`; without the line the
categories of the page), `формы ед. ч. не используются` (plurale tantum, also the parameter `pt=1`), `формы мн. ч. не
используются` or `предположительны` (sing_tant, also `st=1`), `несклоняемое`. The forms marked as `assumed` or
`difficult` are not generated. Not generated: articles without an index (51 thousand, `сущ ru m ina`: the page shows no
table). Compound words (`автомобиль-цементовоз`) and `полчаса` have forms, but no gender for the export.

### Adjectives
The HTML table `прил` with `rowspan`/`colspan` and the line `Сравнительная степень — ...` under it (`comp`). The forms
marked as `assumed` or `difficult` are not generated. A table of a substantivized adjective with one row `В.` gets
the animacy from the genitive (`блаже́нненького`), a broken table of a plural only adjective (`хлора́нтовые` in the
column `жен. р.`) is moved to the plural. A comparative in parentheses is dropped (`(образуются супплетивно)`), italic
labels between the forms are separators (`деше́вле ''и'' подеше́вле`). Indeclinable adjectives (`прил ru 0`) get the
lemma in all full forms and `"indeclinable": true`; `прил ru` without an index and comparatives with an article of
their own (`прил ru сравн`) are failures.

The Lua module of `прил-ru` (4253 articles) builds the comparative and the short forms of every adjective without
`~` or ✕ in the index, also of relative ones (`гиперзвукове́е`, `кружко́вы`); unless the article gives them
(`степень=`, `srt-sg-m=`) they get the mark `module`, and `compare_with_aot.py` does not count them as a difference if
aot does not have them. Errors of the articles: `степень=1` in `прил-ru` is shown as `1` (`взаимозависимый`, a
warning, no comparative), `{{{основа1}}}` instead of the short masculine form (107 articles, a warning), `степень` of
`хороший` gives the forms of `лучший` (see `compare_decisions.tsv`).

### Verbs
The sections of the table: `Настоящее время`, `Будущее время`, `Настоящее/будущее время` (`npst-sg-1` ...
`npst-pl-3`: the present for imperfective verbs, the future for perfective ones), `Прошедшее время` (`pst-sg-m`,
`pst-sg-f`, `pst-sg-n`, `pst-pl`: the rows `м. р.`, `ж. р.`, `с. р.`, the plural cell with `rowspan`),
`Повелительное наклонение` (`imp-sg-2`, `imp-pl-2`, `imp-pl-1`), `Причастия`, `Деепричастия` (`ger-prs`, `ger-pst`);
the analytic future (`бу́ду/бу́дешь… бежа́ть`) is not used, the infinitive `inf` is the title. Parentheses separate
variants too (`ту́хнул (ту́х)`), a mark belongs to its variant (`расплетя́сь, *расплётшись`). The aspect (`aspect`:
`pf`, `impf`, `both`), the transitivity (`transitive`) and `impersonal` are taken from the line under the table; an
imperfective verb without the present forms is `frequentative` (`хаживать`). The forms marked as `assumed`
(`бежи́мый`) are not generated, the forms marked as `difficult` (`моги́`) are generated and listed in `difficult`.
The table of `быть` (`гл ru ^a/c`, `morfotable`) has the tenses as columns and the pronouns as rows (`morfotable` of
`src/rendered.py`): `prs-sg-1` ... and `fut-sg-1` ... (`есть`, `бу́ду`), the past by the genders of the cell, the
participles and gerunds in HTML rows; the variants with a footnote (`есмь`, `еси́`, `суть`, `бу́ди`, `су́щий`) are not
used.

The participles of the table are declined by `decline_participle` (`src/verbs.py`), since the table gives only their
initial forms: `ptcp-prs-act-`, `ptcp-pst-act-`, `ptcp-prs-pass-`, `ptcp-pst-pass-` followed by an adjective form
name (`nom-sg-m`, ..., `srt-sg-f` for the short forms of passive participles). The shape is checked without the stress
marks (`тя́нутый` in the cell of the present passive participle is a past one), a participle without the stem of a
template without parameters (`нный` of `запутешествовать`) is dropped.

Participles with an article of their own (`агитированный`, `{{прич ru -нн|основа=агити́рова}}`, 64607 articles) are
linked to the verb by the definition `{{прич.|агитировать}}`: `extract_from_dump.py` stores it in `morpho.participle_of`
(the definition is looked for in the whole text, the morphological section does not contain it). A participle that is in
the table of some verb (the table links to them: `засыпанный` of the perfective `засыпать`) is skipped. The others are
added to the verb (`participle_articles`) if it is the only verb with this title: the table of an imperfective verb
`гл ru 2a` has the past passive participle only with the parameter `ПричСтрадПрош`. The failures file lists the rest:
the verb is not found or has homonyms, a passive participle of an intransitive verb, a present participle of a
perfective or frequentative one, the first two letters differ from the verb (`неимеющийся` of `иметься`).

### Other parts of speech
Each article gets `pos`: `adv`, `pred`, `particle`, `prep`, `conj`, `intrj`, `par` (parenthetical words), `ono`
(onomatopoeia) by the header templates `adv ru`, `predic ru`, ... (`INVARIABLE_TEMPLATES`), their only form is
`inv`; adverbs and predicatives may have `comp`, the line of the page (`Сравнительная степень — [[ближе]].`, a
difficult one is kept: `зя́бче`); `also` keeps another part of speech of the word (`{{adv ru|или=частица}}`).

Pronouns (`pron`), numerals (`num`) and possessive adjectives with the pronominal declension (`padj`, `мамин`)
have templates `мест ru ...`, `числ ...`, `Мс-...` or a table in the article itself (`{{падежи ru 1|nom=он|...}}`,
then the part of speech is taken from the next header template, `section_templates`; `падежи ru 1` is a pronoun:
`себя`, which is `PRON` with the case only, as in aot). An article without a part of speech goes to the failures file;
an article whose table is the table of another word (`оне` with the table of `он`) is a failure too. The table (`case_table`): an
HTML table `прил` gives the names of adjectives (`этот`, `Лизин`), a wiki table is converted to HTML (`rowspan`,
`colspan`), the rows are found by their labels (`Им.`, `Род.`, `Вн.`, `одуш.`, `неод.`, also in cells `|`: `двое`;
`В. (одуш./неодуш.)` of `один` has both forms in a cell), the columns by their headers (`ед. ч.` -> `nom-sg`, `муж.,
ср.` -> `nom-m`, `nom-n`, `ед. ч. м.` -> `nom-sg-m`, `форма` -> `nom`); `(н)его́` is `его́` and `него́`, analytic
forms are dropped (`о ко́м`, `ко̀й (предлог) ко́м`). Pronouns with a header and no table: `который-то` is declined as
`который` with the particle, `такой-сякой` as both words; the others get the only form `inv` and `no_table`. The page
of `чей-то` has the error `чье́й чье́ю-то`.

Abbreviations (`{{abbrev|роль=существительного мужского рода единственного числа}}`) are `abbr` with the only
form `inv`; `abbr_pos`, `gender`, `number` are taken from `роль`.

### Surnames
The table `Фам-блок`: the columns `м.`, `ж.`, `мн. ч.` (`nom-sg-m`, `nom-sg-f`, `nom-pl`) or the singular and the plural
of each gender. A surname with the header `{{Фам ru|основа=Хво́рост}}` has no table on the page: the template is chosen
by its ending (`src/surnames.py`: `-ов`, `-ин` like `Иванов`, a consonant like `Хворост`, `-о`, `-их` indeclinable,
...), its call `{{Фам ru m 1a|основа=Хво́рост}}` is expanded by `wikitextprocessor` (the database of `expand_morpho.py`),
both parts of a double surname are declined; the template is stored in `morpho.guessed_template`.

## Export to slf and the comparison with aot.ru
```
python export_slf.py
mkdir -p result/mrd
cp ../data/Russian/gramtab.json result/mrd/
echo '{"MRD_FILE": "morphs.json", "LANG": "RUSSIAN", "USERS": ["wiktionary"]}' > result/mrd/project.mwz
echo '{"flexia_models": [], "accent_models": [], "sessions": [], "prefix_sets": [], "lemmas": []}' > result/mrd/morphs.json
slf_convert --to-mrd --slf result/wiktionary.slf --mwz result/mrd/project.mwz --user wiktionary
python compare_with_aot.py
```
`export_slf.py` writes all paradigms of `result/*.jsonl` to `result/wiktionary.slf`, the slf format of MorphWizard
(`src/slf.py`), a homonym whose paradigm is a part of the paradigm of another homonym (`снос 1`, `снос 2` with the
second genitive `сносу`) is not written, aot has one lemma for them; homonyms of a verb that differ by participles
only are one paradigm with the participles of both (`ебать 1` with `ебаный`, `ебать 2` with `ебомый`, 41 cases); an
equal paradigm of another article is written once (`хуяка 1` with a masculine template gives `хуяк`); a paradigm is a list of lines `form POS grammems` with the Latin names of the Russian gramtab of aot.ru
(`N mas,sg,nom`, `PARTICIPLE pres,act,mas,sg,acc,anim`), the lemma first, the animacy of nouns and the aspect and
transitivity of verbs are in `$type_grm`. The forms are named as in aot: the non-past of a perfective verb is the
future, a biaspectual verb has both, a surname is one paradigm of both genders (`N mas,fem,pl,nom` for the plural),
an indeclinable word is one form (`N mas,0`, `A 0,anim,inanim`), a pronoun-adjective is `PA`, an ordinal numeral is
`ORD_NUM`. The comparatives of adverbs are not exported, in aot they are forms of adjectives. Stress marks are lost.

The slf file is loaded into a dictionary of MorphWizard (`result/mrd/`: `project.mwz`, `gramtab.json` of aot.ru,
`morphs.json`) by the C++ utility `slf_convert` of nlp_base (`--to-slf` writes a dictionary back to slf). The dictionary
is created by the commands above, an empty one each time, since `--to-mrd` adds paradigms to it. `slf_convert` is
built with nlp_base (`build/Source/nlp_base/slf_convert/slf_convert`).

The full run on the dump of 2026-11-01: `cache_dump.py` takes about 5 minutes, `extract_from_dump.py` 3 minutes,
`expand_morpho.py` about 45 minutes in 8 processes, `generate_wordforms.py` under a minute for each part of speech, `slf_convert --to-mrd` 2 minutes (245915 paradigms), `compare_with_aot.py` 40 seconds.

`compare_with_aot.py` compares `result/mrd/morphs.json` with `nlp_base/data/Russian/morphs.json`, `ё` is compared
as `е`. Paradigms are matched by the lemma and the POS of the lemma (homonyms by the number of shared forms), the
results are in `result/compare/`:
- `summary.tsv`: pairs, equal pairs, lemmas of one dictionary only, by POS;
- `categories.tsv`: kinds of differing forms, e.g. `ADJ_SHORT: only aot`, `N 2: only aot` (the second genitive);
- `groups.tsv`: pairs with the same differences, written as endings after the common stem, with the Wiktionary
  templates and examples;
- `pairs.tsv`: the differences of each pair;
- `only_wiki.tsv`, `only_aot.tsv`: unmatched lemmas, for a Wiktionary lemma the aot lemmas sharing its forms;
- `type_grammems.tsv`: differences of `$type_grm`;
- `accepted.tsv`: the pairs with a decision in `compare_decisions.tsv`, they are not in the groups.

`compare_decisions.tsv` is the list of reviewed differences (tab separated: `lemma`, `pos`, `reason`, `differences`
as in `pairs.tsv`, an optional `comment` on what exactly is wrong). A decision holds for these exact differences, if they change, the pair comes up again.
The grammem `arch` is removed before the comparison, so a form added to aot as obsolete is not a difference.
The comparatives with `по-` of aot (`покраснее`, `A compar,2`) are not a difference if the Wiktionary article gives none
of them: only 306 of 2843 adjectives with a comparative have them, the other articles do not mention them; the form is
normative (a softened comparative, it is formed of any synthetic one), aot is kept.
Reasons:
- `wiki_no_form`: aot has the second genitive, the optional parameter `Р` of the article is empty, aot is kept;
- `wiki_error`: the form of Wiktionary is wrong for this category (`блинов` in the parameter `Р`), it is not added;
- `wiki_doubtful`: the form is doubtful, it is not added until it is checked in a corpus.

## The plural of nouns with sing_tant
```
python add_sing_tant_plurals.py --input ../data/Russian/morphs.json --output ../data/Russian/morphs.json
slf_convert --to-mrd --slf empty.slf --mwz ../data/Russian/project.mwz --user guest
```
In aot.ru `sing_tant` (дфст, de facto singularia tantum) means that the plural exists but is rarely used: the rule
`Rule_DeadPlurals` of MAPost removes the plural readings of such a word if the context is not plural (`из Москвы` is
genitive singular only). So a paradigm with `sing_tant` should have the plural, as `АБАДАН` has, but 8206 nouns had
`sing_tant` and no plural forms: 2220 toponyms (`МОСКВА`, `ИТАЛИЯ`) and 5986 other nouns (`ФТОРИРОВАНИЕ`,
`АГРОПРОМЫШЛЕННОСТЬ`). The plural is used in Flibusta: `по Парижам`, `в разных Италиях`, `двух павших Римов`,
`с повизгиваниями`, `в сингулярностях`. The script takes the plural from the Wiktionary dictionary (`result/mrd`): a
paradigm with the same lemma and the same singular forms (one of them may have more: the second prepositional of aot,
`Италиею` of Wiktionary); the stem is shortened if the plural has a fleeting vowel (`Авдеевка` -> `Авдеевок`), the
stress of the new forms is unknown, `sing_tant` is kept. The first run (`--toponyms-only`) added the plural to 658
toponyms, the second one to 2363 other nouns. `sing_tant` is removed if the plural is frequent in Flibusta
(`sing_tant_plurals_flibusta.tsv`: the dative, instrumental and prepositional plural that are not forms of other words
of aot, the sum >= 20; 17 nouns: `объятье` with `в объятьях` 5572, `пицца`, `мехмастерская`, `целеуказание`). `ЛЕТО`
is excluded: `лета`, `лет` are the plural of `ГОД` in aot, the plural of `ЛЕТО` would double `двадцать лет`. The list of
the added forms is `result/sing_tant_plurals.tsv`; 5128 nouns have no such paradigm in Wiktionary, 51 have several
different ones.

## Obscene words
```
python add_obscene_words.py
slf_convert --to-mrd --slf result/obscene.slf --mwz ../data/Russian/project.mwz --user guest
```
A word is obscene if all meanings of its article have the mark `{{обсц.|ru}}` (`is_obscene` of `src/utils/wiki.py`,
683 articles: `пиздец`, `ебать`, `долбоёб`); an article with an obscene meaning among others (`банан`, `палка`) is an
ordinary word, its obscene meaning is not a morphological difference. The flag `is_obscene` of the cache was computed
by the marks `{off}` and `{offensive}` before (`агрегат`, `банан`), `cache_dump.py` computes it this way now; it is
not used to filter articles. The script writes the paradigms of the export (`result/wiktionary.slf`) of these
articles whose lemma with its part of speech is not in aot.ru (the interjection `ебать` is not the verb), `slf_convert
--to-mrd` adds them to aot: 680 paradigms, 2 lemmas were in aot (`хуй`, `пизда`), 46 articles have no paradigm (forms
with an article of their own: `спизженный`, `проебав`; failures: `еть`, `выёбистый`). Articles that differ by `ё` only
(`ёбаный` and `ебаный`) are one lemma: a paradigm that is a part of another one if `ё` is `е` is dropped. The stress of the added words is
unknown (the slf export loses it).

```
python mark_obscene.py
slf_convert --to-mrd --slf empty.slf --mwz ../data/Russian/project.mwz --user guest
```
The obscene words are marked by the type grammem `obsc` (обсц, `rObscene` of `agramtab/RusGramTab.h`): the script
adds it to the type grammems of the lemmas of aot.ru equal to the titles of the obscene articles (682 lemmas, also
`хуй`, `пизда` that were in aot), the codes of the new combinations of type grammems (`inanim,obsc`, ...) are added to
`gramtab.json`. The lemmatizer shows `ПИЗДЕЦ С обсц,но`.

## Adverbs по-...ски
```
python add_po_ski_adverbs.py --input ../data/Russian/morphs.json --output ../data/Russian/morphs.json --user guest
slf_convert --to-mrd --slf empty.slf --mwz ../data/Russian/project.mwz --user guest
```
Adjectives in -ский/-цкий had in aot.ru the fictitious short form `ADJ_SHORT pl` in -и (`абакански`): the lemmatizer
found it after the hyphen of an unknown `по-абакански`, so the word was predicted as a short adjective. The script removes
this form where it is the only short form (11244 adjectives, `крутобоки` is kept) and adds the adverbs as lemmas: 524
adverbs of Wiktionary and 702 words of the Flibusta corpus (`po_ski_flibusta.tsv`, the ddc query
`count(/^по-.+[сц]ки$/i) #by[$w]`) with the frequency >= 3 whose adjective (`абаканский`, `морской`) is in aot.ru or in
Wiktionary; a frequent misspelling without such an adjective (`по-джентельменски`, 210) is not added. The stress is taken
from the adjective or from the Wiktionary article. The list of the added adverbs is `result/po_ski_added.tsv`.

An unknown `по-...ски` is predicted as an adverb by the prediction base: the lemmatizer (`Lemmatizers.cpp`) does not
predict a hyphenated word by a known suffix inside its last part (`по-абакански` -> `кански` of `Канск`).
After the change of the dictionary the dependent dictionaries are rebuilt: `cmake --build . --target morph_gen_on_Russian BinDicts`.

## Obsolete gerunds
```
python mark_arch_gerunds.py --input ../data/Russian/morphs.json --output ../data/Russian/morphs.json
slf_convert --to-mrd --slf empty.slf --mwz ../data/Russian/project.mwz --user guest
```
The gerunds of perfective verbs in -я/-ясь/-а/-ась (`вдохновя`, `вооружась`, `вспомня`) next to the gerunds in
-в/-вшись get the gramcode `Fs` (ADV_PARTICIPLE act,past,arch), 2728 forms; `вспомня` was marked as present. Wiktionary
gives only `вдохновив`, in the Flibusta corpus the forms in -я are 4.3% of the gerunds of these verbs, 2153 of them do not
occur at all (`arch_gerunds_flibusta.tsv`). Not changed: the verbs without a gerund in -в (`придя`), 531 forms that
Wiktionary gives (`возвратясь`) and 37 forms frequent in Flibusta (the share >= 20%, the frequency >= 5: `скрепя`,
`очертя`, `воротясь`). The list of the changed forms is `result/arch_gerunds.tsv`.
`compare_with_aot.py` does not count an obsolete form of aot that Wiktionary does not give as a difference.

## Obsolete inclusive imperative
```
python mark_arch_inclusive_imperative.py --input ../data/Russian/morphs.json --output ../data/Russian/morphs.json
slf_convert --to-mrd --slf empty.slf --mwz ../data/Russian/project.mwz --user guest
```
The inclusive imperative in -мте/-мтесь (`напишемте`) that does not occur in the Flibusta corpus
(`inclusive_imperative_flibusta.tsv`, the ddc query `count(/мте(сь)?$/i) #by[$w]`, 320 words) gets the new gramcode `Mt`
(V act,imp,1p,pl,arch) of `gramtab.json`: 14710 of 14836 forms. The forms of the corpus are kept: `пойдемте` (33464),
`идемте` (18989), `пройдемте`, `споемте`, `выпьемте`, 126 forms. The forms are regular and are not removed. The forms
without -те (`сделаем`) coincide with the future and are not changed. The list of the changed forms is
`result/arch_inclusive_imperative.tsv`.

The inclusive imperative that neither Wiktionary gives nor Flibusta has as a form in -те is removed
(`prune_inclusive_imperative.py`, run after `mark_arch_inclusive_imperative.py`): 1329 verbs, mostly biaspectual ones
(`организуем`), whose Wiktionary table `гл ru 2a` has no cell for it. Before that the contexts with "!" were looked for
in Flibusta (the form before "!" without "мы"), the 149 verbs that have them were reviewed by hand: 52 verbs keep the
imperative (`– Атакуем ! – отрепетовал Левшин`, `Ребята , все выбегаем !`), the others are promises (`Сейчас
организуем !`), performatives (`Обещаем !`), `давай` + the form or other words. The decisions are in
`inclusive_imperative_reviewed.tsv`. The forms without -те stay in the paradigm as the future.

## Comparatives equal to the forms of the adjective
```
python prune_own_homonym_comparatives.py --input ../data/Russian/morphs.json --output ../data/Russian/morphs.json
slf_convert --to-mrd --slf empty.slf --mwz ../data/Russian/project.mwz --user guest
```
aot.ru gave a comparative to adjectives with a soft stem or a stem in a sibilant or ц, and the comparative forms were
the neuter and the feminine forms of the adjective itself: `последний` had `последнее`, `последней` (`A compar`) and
`попоследнее`, `попоследней` (`A compar,2`), so did `будущий`, `ведущий`, `верхний` (658 adjectives, -щий 346, -ний
123, -чий 69, -жий 49, -ший 39, -цый 23). Their frequency in a corpus is meaningless, the forms are the forms of the
adjective. The comparatives are removed (615 adjectives), unless the Wiktionary paradigm has a comparative (43:
`свежий`, `горячий`, `древний`, to be reviewed). `поздний` with `позже` is not touched.

The short forms of these adjectives were mostly fictitious too (`будущ`, `последня`, `ведущ`; Wiktionary builds them
by the template as well). The short forms m+f+pl were counted in lowercase in the Flibusta corpus (the neuter in -е is
mostly an adverb: `умоляюще` 12024 against `умоляющ` 1); the short forms are kept if they are >= 1% of the nominative
and >= 10 and their contexts (5 per form) show short forms: `похож`, `схож`, `вхож`, `свеж`, `могуч`, `всемогущ`; 10
adjectives above the threshold are noise (`кари` = карри, `сидячи` is a gerund, `будня` of `будень`), 14 below the
threshold were checked and kept (`рыж`, `общи`, `подходяща`, `погож`). The decisions are in
`own_homonym_short_forms.tsv`, 114 adjectives keep the short forms, 484 lose them, 4284 forms are removed in all
(`result/own_homonym_comparatives.tsv`). The lines of `../data/Russian/StatData.txt` with the removed readings
(`вещей`, `вещи` of `вещий`, `будни` of `будний`) are deleted, otherwise `StatDatBin` fails. The comparison: equal
adjective pairs 8146 -> 8404, `A compar: only aot` 9295 -> 8885.

The frequency list of the Flibusta word forms (`ddc_stats ... Token dump-freq` of the 4 parts, lowercase, without the
words with a stress mark or U+2011) is `~/data/flibusta/wordfreq.tsv`; it has no case, so the counts of rare forms were
taken from the ddc server (`@form`, case sensitive).

## Adverbs in -е
```
python add_adverbs_in_e.py --input ../data/Russian/morphs.json --output ../data/Russian/morphs.json
slf_convert --to-mrd --slf empty.slf --mwz ../data/Russian/project.mwz --user guest
```
The short forms removed above included the neuter in -е (`умоляюще`), which is mostly an adverb in the corpus, and aot
had no such adverb. Of the 478 forms in -е, 82 are added as adverbs (`adverbs_in_e.tsv`, the voices of each one):
42 have an adverb article of Wiktionary and occur in Flibusta (`умоляюще` 11831, `негодующе`, `скучающе`, `ликующе`,
`невидяще`, `подобающе`), 4 have only the Wiktionary article (`горне`, `веще`, `настояще`, `предвесенне`: the long tail,
the corpus has other words or nothing), 36 have no article, but their contexts in Flibusta (lowercase, frequency >= 5)
show the adverb (`шипяще процедила`, `тянуще завыла сирена`, `было очень как-то домашне`). `непригоже` is also PRED, as
in Wiktionary. Not added: forms whose contexts show other words (`суще` of `суще­ство`, `колюще` of `колюще-режущий`,
`последне`, `следующе` are misprints) and forms with the frequency < 5 and no Wiktionary article (363). The stress is
taken from the Wiktionary article or from the adjective (the same vowel from the end of the word); the list of the
added lemmas is `result/adverbs_in_e_added.tsv`.

## Comparatives of aot only
```
python prune_aot_comparatives.py --input ../data/Russian/morphs.json --output ../data/Russian/morphs.json
slf_convert --to-mrd --slf empty.slf --mwz ../data/Russian/project.mwz --user guest
```
After the comparatives of Wiktionary were taken from the rendered pages, 8121 adjectives had a comparative in aot only
(`A compar: only aot`); most of them are relative adjectives that aot gave a comparative by the template
(`абажурнее`, `черешковее`, `выхухольнее`). The voices, in `compar_only_aot.tsv`:
- Wiktionary: an explicit no (`~` in the index, "Сравнительная степень не образуется", 64), a hidden yes (`степень=` is
  given, but `прил ru 1*a` with an empty `тип` does not show it, 409: often a copied default, `золотовалютнее`),
  silence (the parameter is empty) with the type `качественное`, `относительное` or none; the type is a weak voice
  (`ответственнее` 443 is `относительное`);
- Flibusta: the frequency of the comparatives without `по-` in `~/data/flibusta/wordfreq.tsv`; a form of another word is
  not counted (`клубней` of `клубень`, `колоколен`), a comparative of another word is (`подробнее`, `меньше` of МАЛО);
- Claude: 5 Flibusta contexts of each form with the frequency 1-4 (the comparative cues `чем`, `ещё`, `гораздо`,
  `некуда`, `кто из них`, a neighbouring comparative were found automatically, the 213 lemmas without a cue were read,
  40 with a cue were checked: 2 errors); the meaning of the adjectives with the frequency 0 and a Wiktionary yes.

Kept (1821): Flibusta >= 5 (923; `пологий` has `положе` 135 against the explicit no), Flibusta 1-4 and Wiktionary
yes (150), the contexts show a comparative (664: `бывалее меня`, `захолустнее которой`, `желторотее не бывает`),
Flibusta 0, a hidden Wiktionary yes and a qualitative adjective (47: `постыднее`, `эгоцентричнее`), Wiktionary gives
the comparative on the page (37: `лимоннее`, `коммунальнее`; aot has `-ней` too, so the pair differed). Removed (6300):
Flibusta 0 and Wiktionary no or silent (5915), Flibusta 0, a hidden Wiktionary yes and a relative adjective (272:
`золотовалютнее`, `тоннельнее`), the contexts show other words (113: misprints `безлопастнее`, nouns `кандальней`,
`сводней`, `гарней` is Ukrainian). All comparative forms of such an adjective are removed, also those with `по-`:
25281 forms of 6301 paradigms (`result/aot_comparatives_removed.tsv`). The comparison: equal adjective pairs
9738 -> 14450, `A compar: only aot` 7922 -> 1622.

## Short forms of aot only
```
python prune_aot_short_forms.py --input ../data/Russian/morphs.json --output ../data/Russian/morphs.json
python add_adverbs_in_e.py --input ../data/Russian/morphs.json --output ../data/Russian/morphs.json \
    --decisions adverbs_in_o.tsv --report result/adverbs_in_o_added.tsv
slf_convert --to-mrd --slf empty.slf --mwz ../data/Russian/project.mwz --user guest
```
2164 adjectives had short forms in aot, and their Wiktionary paradigm had none of the differing ones (`ADJ_SHORT:
only aot`); most of them are relative adjectives that aot gave short forms by the template (`абиетинов`, `ранговы`).
The voices, in `short_only_aot.tsv`:
- Wiktionary: the table has short forms (`1*a` shows them by default), they are marked `*` (assumed or difficult), or
  the table has none; the type `качественное` or `относительное`;
- Flibusta: the frequency of the short forms m, f, pl in lowercase from the ddc server (case sensitive: `Малахитова`,
  `Туева` are surnames; the neuter is mostly an adverb and is not counted; a form of another word is not counted);
- Claude: 5 contexts of each form (the predicative cues `был`, `стал`, `очень`, `слишком`, a pronoun before the form
  and a punctuation mark after it were found automatically; the 204 lemmas without a cue and the 125 with a weak one
  were read, 40 with a strong one were checked); the meaning of the qualitative adjectives without corpus evidence.

Kept (782): the Wiktionary table gives short forms (251: `авизна`, its masculine is missing: the difference is a
`different` one), the short forms are forms of a verb too (207: `загорел`, `утомлена`, `устал`: the corpus does not tell
them apart), the contexts show short forms (320: `гиблы`, `узкогруд`, `половозрел`, `термостоек`, `ночь была черна и
безлунна`), a qualitative adjective (4: `бестолков`, `брав`). Removed (1382): Flibusta 0, Wiktionary has no short
forms (1224), a relative adjective typed as qualitative (29: `асбестов`, `таможен`), the contexts show other words
(129: surnames, nouns `круторог`, `мохноног`, the genitive plural `берцов`, `квинтов`, folk forms `шкатулка
малахитова`, Ukrainian text). All short forms of such an adjective are removed: 5059 forms
(`result/aot_short_forms_removed.tsv`).

The neuter short form is often an adverb that aot has nowhere else: 91 of them are added as adverbs
(`adverbs_in_o.tsv`, the voices of each one, `result/adverbs_in_o_added.tsv`): 34 have an adverb article of
Wiktionary and occur in Flibusta (`небывало` 1552, `образцово`, `спокойненько`, `внепланово`, `фиолетово` is also PRED),
4 have only the article (the long tail), 53 occur >= 5 times and their contexts show the adverb (`упреждающе
зарычал`, `пробно крутанула`, `широченно улыбнулся`, `тысячеголосо разнеслось`, `средневеково выглядит`). Not added:
the first parts of compounds split by the tokenizer (`ремонтно – восстановительные`, `торгово – промышленной`), folk
forms (`чрево китово`), nouns (`палево`), misprints. The lines of `StatData.txt` with the removed readings (`дюймов`,
`прессов`, `споров` as short forms) are deleted. The comparison: equal adjective pairs 14450 -> 15777,
`ADJ_SHORT: only aot` 1765 -> 383.

## Composite forms of adjectives
```
python add_composite_forms.py --input ../data/Russian/morphs.json --output ../data/Russian/morphs.json
slf_convert --to-mrd --slf empty.slf --mwz ../data/Russian/project.mwz --user guest
```
The first part of a compound adjective (`ракетно-космический`, `русско-японский`, `сине-бело-красный`) is a very
productive form of the adjective. It is a form of the paradigm with the new grammem `compos` (композ, `rComposite` of
`agramtab/RusGramTab.h`), written with the hyphen at the end: `ракетно- A compos`. `add_composite_forms.py` gives it to
all 41726 adjectives in -ый, -ой, -ий by the rule (the stem + `о`; after a soft consonant or a sibilant + `е`:
`сине-`, `рабоче-`; `-ический` -> `-ико-`: `химико-`) and adds irregular forms with a truncated stem frequent in
Flibusta (`англо-` and `английско-`, `франко-`, `австро-`, `греко-`, `финно-`, `медико-`, `юго-`, `северо-`).

The lemmatizer (`predict_hyphen_word` of `lemmatizer_base_lib/Lemmatizers.cpp`) looks for `first_part + "-"`; if it is
found, the analyses of the second part get the first part as written: the lemma of `ракетно-космической` is
РАКЕТНО-КОСМИЧЕСКИЙ (before: РАКЕТНЫЙ-КОСМИЧЕСКИЙ, the lemma of the neuter short form `ракетно` replaced the part), a
word of three parts is analysed recursively (`сине-бело-красный`, before also СИН-БЕЛО-КРАСНЫЙ). The form never equals
a word of a text without the hyphen, so it does not add homonyms; a word with a suspended hyphen (`ракетно- и
космической`) is analysed as the composite form. The neuter short forms are no longer needed for compounds: 1382
relative adjectives lost them (see "Short forms of aot only"), 39 thousand words of Flibusta (`русско-японской`,
`немецко-фашистских`) never had them. `compare_with_aot.py` skips the composite forms, Wiktionary does not give them.
The expected lemmas of `PredictTestRussian` (`ЗАПАДНО-СИБИРСКИЙ`, `ФИНАНСОВО-ЭКОНОМИЧЕСКИЙ`) and of the syntax test
(`МОГУЧЕ-ДЕЙСТВЕННЫЙ`) are changed accordingly.

## Short forms of Wiktionary only
```
python add_wiki_short_forms.py --input ../data/Russian/morphs.json --output ../data/Russian/morphs.json
slf_convert --to-mrd --slf empty.slf --mwz ../data/Russian/project.mwz --user guest
```
1755 adjectives had no short form in aot, while their Wiktionary paradigm had short forms not marked as assumed or
difficult (`ADJ_SHORT: only wiki`). The voices, in `short_only_wiki.tsv`: Wiktionary (`editor`: the article gives
`краткая=` or the forms, 412; `template`: the template shows them by default, `прил ru 1*a`, 1342; `module`: the Lua
module of `прил-ru`, 1), the lowercase Flibusta frequency of the forms m, f, pl from the ddc server, the contexts
(read as for "Short forms of aot only"). Added (255; `всякий` is PA in aot and is not changed): the contexts show
short forms (`непредсказуем` 5991, `низковат`, `традиционен`, `боеготов`, `пафосен`, `неподъемен`, `вариативен`,
`коррупционен`, `многофакторна`, `полумертв`, `политкорректен`). Not added: no corpus evidence (1386: one voice of
Wiktionary, mostly the default of the template, `резервуарен`, `газокислороден`), the contexts show other words (80:
folk full forms of soft stems `дальня родственница`, `прежни годы`, `с рання`, Ukrainian text, broken words
`сенти­ментален`, `недолжен` for `не должен`), the forms are forms of a verb too (33: `организован`). The forms and
their stress are taken from the Wiktionary paradigm, 1020 forms (`result/wiki_short_forms_added.tsv`; the stress is
unknown for 52 forms with two stress marks, `то́чны́`). The comparison: equal adjective pairs 15777 -> 15999,
`ADJ_SHORT: only wiki` 1755 -> 1500.

## Words added by hand
```
python add_manual_words.py --input ../data/Russian/morphs.json --output ../data/Russian/morphs.json
slf_convert --to-mrd --slf empty.slf --mwz ../data/Russian/project.mwz --user guest
```
The substantives БЫВШИЙ, БЫВШАЯ (N anim, declined as ВЕДУЩИЙ, ВЕДУЩАЯ; `мой бывший опять звонил`: 10-20% of
`бывший`/`бывшая` after a possessive pronoun in Flibusta, Wiktionary has the meaning `{{субст.}}`), the form ВСЯК of
the substantive pronoun and of the pronoun-adjective ВСЯКИЙ (`всяк норовит` 87%, `всяк человек` 13% of 200 contexts).
The note ДО (N neu,0, as РЕ: aot had `ре`, `ми`, `фа`, `соль`, `ля`, `си`, but not the homonym of the preposition); the
Mapost rule `Rule_DO` (`Source/synan/MAPostLib`, the test `TestMapost/test/Russian/do.txt`) removes the note before a
genitive or a number (`до 5 часов`, `до вечера`), it stays in `ноту до`, `до мажор`, `в до миноре`; `StatData.txt`
gives the preposition the weight 10000 and the note 1.
The childish noun КАКА (`ка́ка`, as БЯКА inanim; aot had only the indeclinable name `Кака`): its forms `как` and `какой`
are homonyms of the most frequent words, the Mapost rule `Rule_KAK` (the test `TestMapost/test/Russian/kak.txt`)
removes the noun from `какой` always and from `как` unless a number or a word of quantity is before it (`много как`,
`несколько как`); `каку`, `каки`, `каке` keep it.

## Past gerunds of imperfective verbs in -овать
```
python add_imperf_gerunds.py --input ../data/Russian/morphs.json --output ../data/Russian/morphs.json
slf_convert --to-mrd --slf empty.slf --mwz ../data/Russian/project.mwz --user guest
```
781 imperfective verbs in -овать/-евать and ФАВОРИЗИРОВАТЬ had only the gerund in -вши in aot (`мотивировавши`), and
Wiktionary gives -овав for 764 of them (`ADV_PARTICIPLE act past: different`). The past gerund of an imperfective verb
is rare in Flibusta (`читав` 33 against `прочитав` 15040, `агитировав` 0); the forms in -овав of these verbs occur 1080
times, mostly of verbs that are biaspectual in Wiktionary (`мотивировав` 442). The decisions are in
`imperf_gerunds.tsv`: added (45) the forms with at least two different gerund contexts (`отказался, мотивировав это
тем`, `ни разу не пробовав`, `игнорировав вопрос`, `не мудрствовав лукаво`); not added: no form in Flibusta (664,
one voice of Wiktionary), one gerund context (43), other words (30: broken perfectives `по газовав`, typos `он
чувствовав голод`, broken participles `существовав ших`). The new form takes the gramcode and the stress of the form in
-вши (`result/imperf_gerunds_added.tsv`).

## Aspect of verbs
```
python set_verb_aspects.py --input ../data/Russian/morphs.json --output ../data/Russian/morphs.json
slf_convert --to-mrd --slf empty.slf --mwz ../data/Russian/project.mwz --user guest
```
The aspect of 659 verbs differs in aot and Wiktionary (`verb_aspects.tsv`). Wiktionary takes the aspect from the
template and the template is often wrong (`вводиться` has `гл ru 4c-т-сяСВ`, `возмечтать` has `гл ru 1a` without
`СВ`). Two Flibusta tests, calibrated on 112 verbs where aot and Wiktionary agree: the imperfective frame `будет /
начал / стал / перестал / продолжал` + the infinitive (imperfective verbs: the median 9.5% of the infinitive,
perfective: 0.2%) and the past gerund in -в/-вшись (imperfective: 0, perfective: 21%, biaspectual: 3.1% and 2.8%).
The contexts of the 92 verbs where Flibusta differs from aot were read: the modal `надо / можно будет` takes
perfectives (`надо будет поспрашивать`) and rare imperfective uses of biaspectual verbs are real (`земля перестала
родить`). Changed 60 verbs (`result/verb_aspects_changed.tsv`): imperfective 20 (`афишировать`, `дегустировать`,
`лоббировать`, `дуться`, `продюсировать`), biaspectual 30 (`анонсировать`, `мотивировать`, `делегировать`,
`клонировать`, `разминировать`), perfective 10 (`купиться`, `повскакивать`, `воспрепятствовать`, `подкорректировать`).
Kept 599: Flibusta agrees with aot (116, errors of Wiktionary), no evidence (451), the contexts show the aspect of aot
(32: `рапортовав, что сбил`, `родить`, `реорганизовать`). The paradigm follows the aspect (pres/fut personal forms,
the present participles and gerund); the new present participles and gerunds are those Wiktionary gives, with its
stress (`нанося́щийся`). The comparison: equal verb pairs 26279 -> 26318.

## Imperative in -и / -ь
```
python fix_imperatives.py --input ../data/Russian/morphs.json --output ../data/Russian/morphs.json
slf_convert --to-mrd --slf empty.slf --mwz ../data/Russian/project.mwz --user guest
```
The imperative of the 2nd person singular differs in aot and Wiktionary for 397 verbs (`imperatives.tsv`), mostly -и
/ -ь (`всунь` / `всуни`). The voices are the lowercase Flibusta frequencies of the singular and plural forms without
homographs (`голуби` is a noun, `выволочь` an infinitive, `вывесите` the future). Changed 11 verbs
(`result/imperatives_changed.tsv`): the form of Wiktionary replaces that of aot (`приструни` 85 against `приструнь` 1,
`лыбься` 115, `скинься` 23, `пригуби` 29, `вытянись` 17, `стопори`, `угоразди`) or is added (`пополощи` next to
`пополоскай`). Kept: Flibusta prefers aot (60: `всунь` 69 against `всуни` 0, `восполни`, `высиди`), errors of
Wiktionary (23: `вклинй`, `впялйся` with й after a consonant, `вороши` for `наворошить`, `раскрутись` for
`раскутиться`), no clear majority (56), no form in Flibusta (244), homographs only (3). The kept pairs whose only
difference is the imperative are in `compare_decisions.tsv` (54 wiki_error, 169 wiki_doubtful). The comparison:
`V act imp: different` 1243 -> 1010.
