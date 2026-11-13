# ru_wiktionary_merger

Generates Russian paradigms from a dump of ru.wiktionary, exports them to the slf format of MorphWizard and compares
them with the Russian dictionary of aot.ru (`../data/Russian`), to merge them into it.

It is based on [RuWiktionaryParser](https://github.com/slowwavesleep/RuWiktionaryParser) by Aleksei Dorkin
(MIT license, see [LICENSE](LICENSE)), the history of that repository is kept. The original project generated nouns,
adjectives, verbs, other parts of speech, surnames, the evaluation of wiki templates, the slf export and the comparison
were added here.

Use a virtual environment: `python -m venv venv; venv/bin/pip install -r requirements.txt` (on Debian/Ubuntu `venv`
needs the package `python3-venv`). Checked with Python 3.14.

## Data extraction
The first step of the process is the extraction of the data from the downloaded Wiktionary dump.
The most recent version can be found [here](https://dumps.wikimedia.org/backup-index.html). You'll want
the pages-articles version of the dump which hash the following name format: 
__ruwiktionary-{date}-pages-articles.xml.bz2__. You don't need to unpack it. Just put it in a desired
directory, then specify the path in the [config.yml](config.yml) file.

### Cache the dump
```
python cache_dump.py
```
Reads the dump once (about 5 minutes, `lbzip2` is used if installed) and stores the Russian
pages in `tmp/cache/pages.jsonl`: the Russian section of each article, Russian templates and
template redirects, and a few templates they call (`EXTRA_TEMPLATES`, e.g. the verb table `Гл-блок`). The XML namespace version of the dump does not matter.

### Extract data from the dump
```
python extract_from_dump.py                # articles and templates, about 3 minutes
python extract_from_dump.py --templates    # templates only, seconds
python extract_from_dump.py --articles     # articles only
```
Works with the cache (builds it first if it is missing, `--rebuild-cache` reads the dump again).
Three files will be generated in the `tmp` folder: `articles.jsonl`, `templates.jsonl`,
and `template_redirects.jsonl`. Homonyms (several morphological sections on one page) give
separate articles with a `homonym` label taken from the section header (`I`, `II`, ...).

### Some examples of the format

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

#### A template

```
{
  "template": {
    "case": "{{{case|}}}",
    "form": "{{{form|}}}",
    "nom-sg": "{{{основа}}}я",
    "nom-pl": "{{{основа}}}и",
    "gen-sg": "{{{основа}}}и",
    "gen-pl": "{{{основа1}}}ь",
    "dat-sg": "{{{основа}}}е",
    "dat-pl": "{{{основа}}}ям",
    "acc-sg": "{{{основа}}}ю",
    "acc-pl": "{{{основа}}}и",
    "ins-sg": "{{{основа}}}ей",
    "ins-sg2": "{{{основа}}}ею",
    "ins-pl": "{{{основа}}}ями",
    "prp-sg": "{{{основа}}}е",
    "prp-pl": "{{{основа}}}ях",
    "loc-sg": "{{{М|}}}",
    "voc-sg": "{{{З|}}}",
    "prt-sg": "{{{Р|}}}",
    "П": "{{{П|}}}",
    "hide-text": "{{{hide-text|}}}",
    "слоги": "{{{слоги|}}}",
    "дореф": "{{{дореф|}}}",
    "Сч": "{{{Сч|}}}",
    "st": "{{{st|}}}",
    "pt": "{{{pt|}}}",
    "затрудн": "{{{затрудн|}}}",
    "коммент": "{{{коммент|}}}",
    "зачин": "{{{зачин|}}}",
    "клитика": "{{{клитика|}}}",
    "кат": "неодуш",
    "род": "{{{род|жен}}}",
    "скл": "1",
    "зализняк": "2*a^",
    "чередование": "1"
  },
  "id": 15763,
  "title": "сущ ru f ina 2*a^",
  "type": "template"
}
```
#### A template redirect
```
{
  "id": 836905,
  "title": "сущ ru f ina 2*a-ня(2)",
  "redirect_title": "сущ ru f ina 2*a(2)-ня",
  "type": "template_redirect"
}
```

Suppose that the extracted data in this form may have its uses. Do note, however, that homonymous
lemmas _are currently not accounted for_. This means that if a certain page has articles for several
word senses, then only the first one will be saved.

## Generating Word Forms
The main purpose of this project is to generate word forms with morpheme boundaries marked using the provided
wiki-templates and segmented lemmas. To do this, some preliminary steps are required.

*Note:* only nouns are supported at the moment.

### Process the templates
This will filter and reformat `templates.jsonl`.
```
python process_templates.py
```

### Process the articles
This will clean up and enrich `articles.json`. 
```
python process_articles.py
```

The results of the last two steps will be saved in `tmp/processed/` folder by default.

#### Generate the segmented noun word forms
This will use the processed files to generate word forms (where possible). Obscene words
and proper names are not used by this original script, `generate_wordforms.py` generates them.
```
python generate_nouns.py
```
The output is saved to `result/processed_articles.jsonl` by default. The file should
contain approximately 500 thousand noun word forms.

## Adjectives
```
python process_templates.py
python process_articles.py
python generate_wordforms.py --pos adj --output-articles result/adjectives.jsonl --failures result/adj_failures.tsv
```
Adjective templates contain no endings, they call each other (`прил ru 1*a` -> `прил ru 1a`) and end
with the table template `прил`; `process_templates.py` resolves these chains. Each form is a list
of variants (`твёрдой`, `твёрдою`), `comp` contains the comparative. Adjectives whose forms could
not be built are listed in the failures file with the reason and a link to the article.

Indeclinable adjectives (`прил ru 0`) get the lemma in all full forms and `"indeclinable": true`.
Articles with `{{прил-ru|безымя́нный|1*a}}` are rendered by a Lua module, so their tables are not in the
dump. For them the template `прил ru <index>` is used (`src/adjectives.py`): the index is reduced to an
existing template (`1b(X)` -> `1bX`), the stems are derived from the lemma, including the short form stem
with Zaliznyak's fleeting vowel (`безымянн` -> `безымянен`, `связанн` (1) -> `связан`). The template used
is stored in `morpho.lua_template`.

## Verbs
```
python generate_wordforms.py --pos verb --output-articles result/verbs.jsonl --failures result/verb_failures.tsv
```
Verb templates (`гл ru 1a`, `гл ru 1aСВ`) pass all cells to the table template `Гл-блок`; the cells are
evaluated for each article and shown the way `Гл-блок` and `спряжения` show them: perfective verbs use the
cells `Прич`, `Деепр`, `Мы (повел.)`, and their `ПричСтрад` is the past passive participle; passive
participles are shown only for transitive verbs (`НП` is empty), impersonal verbs (`безличный`) have only the
3rd person, frequentative ones (`многократный`) have no present forms. The infinitive of perfective verbs is
the title of the article.

Form names: `inf`, `npst-sg-1` ... `npst-pl-3` (the present for imperfective verbs, the future for perfective
ones), `pst-sg-m`, `pst-sg-f`, `pst-sg-n`, `pst-pl`, `imp-sg-2`, `imp-pl-2`, `imp-pl-1`, `ger-prs`, `ger-pst`.
Participles are declined in `src/verbs.py`, since the table gives only their initial forms:
`ptcp-prs-act-`, `ptcp-pst-act-`, `ptcp-prs-pass-`, `ptcp-pst-pass-` followed by an adjective form name
(`nom-sg-m`, ..., `srt-sg-f` for the short forms of passive participles). Variants are separated in the cells
by `<br>`, commas, `/`, `//` and parentheses (`до́хнул (дох)`). The article gets `aspect` (`impf`, `pf`, `both`),
`transitive`, `impersonal`, `frequentative`, and `difficult`: the forms marked as difficult (`ПовелЗатрудн`,
`{{difficult|...}}`). Errors of the articles found on the way (a wrong template: `ощети́нйся`, a wrong stem:
`пережида́йнный`) are listed in the failures file as warnings, the forms are kept as Wiktionary shows them.

Participles with an article of their own (`агитированный`, `{{прич ru -нн|основа=агити́рова}}`, 64607 articles) are
linked to the verb by the definition `{{прич.|агитировать}}`: `extract_from_dump.py` stores it in `morpho.participle_of`
(the definition is looked for in the whole text, the morphological section does not contain it). A participle that is in
the table of some verb (62686 articles, the table links to them: `засыпанный` of the perfective `засыпать`) is skipped.
The others are added to the verb (`participle_articles`, 1060 participles) if it is the only verb with this title:
the table of an imperfective verb `гл ru 2a` has the past passive participle only with the parameter `ПричСтрадПрош`.
The failures file lists the rest (778): the verb is not found or has homonyms, a passive participle of an intransitive
verb, a present participle of a perfective or frequentative one, the first two letters differ from the verb
(`неимеющийся` of `иметься`).

## Other parts of speech
```
python generate_wordforms.py --pos other --output-articles result/other.jsonl --failures result/other_failures.tsv
```
Each article gets `pos`: `adv`, `pred`, `particle`, `prep`, `conj`, `intrj`, `par` (parenthetical words), `ono`
(onomatopoeia) by the header templates `adv ru`, `predic ru`, ... (`INVARIABLE_TEMPLATES`), their only form is
`inv`; adverbs may have `comp` (the parameter `степень`); `also` keeps another part of speech of the word
(`{{adv ru|или=частица}}`).

Pronouns (`pron`), numerals (`num`) and possessive adjectives with the pronominal declension (`padj`, `мамин`)
have templates `мест ru ...`, `числ ...`, `Мс-...`: they end with the adjective table `прил` (the forms are named
as for adjectives) or with a case table (`CASE_TABLES`): `падежи ru 1` (`nom`, `gen`, ...), `падежи` (`nom-sg`,
...), `падежи ru m n f pl` (`nom-sg-m`, ...). The table may be given in the article itself
(`{{падежи ru 1|nom=он|gen=его́, него́|...}}`), then the part of speech is taken from the next header template
(`section_templates`). Forms with stylistic labels (`{{устар.|-}}&nbsp;ея́`) and analytic forms (`ни о ком`) are
dropped. Templates written in the wiki table markup (`числ ru 2`, `числ-собир1b`) are parsed by `src/wikitable.py`:
the case of a row and the gender of a column are recognized by their labels (`Им.`, `Вн.` + `одуш.`, `м./ср. р.`).
Pronouns with a header and no table: `который-то` is declined as `который` with the particle, `такой-сякой` as
both words; the others get the only form `inv` and `no_table`.

Abbreviations (`{{abbrev|роль=существительного мужского рода единственного числа}}`) are `abbr` with the only
form `inv`; `abbr_pos`, `gender`, `number` are taken from `роль`.

## Surnames
```
python generate_wordforms.py --pos surname --output-articles result/surnames.jsonl --failures result/surname_failures.tsv
```
Surname templates (`Фам ru ин ов`, `Фам ru m 1a`, ...) call the table `Фам-блок` (`им-м`, `им-ж`, `им-мн`, the forms
are named `nom-sg-m`, `nom-sg-f`, `nom-pl`) or `Фам-блок-мж` (the plural of each gender). A surname with the header `{{Фам ru|основа=Хво́рост}}` and no
table gets the template by its ending (`src/surnames.py`: `-ов`, `-ин` like `Иванов`, a consonant like `Хворост`,
`-о`, `-их` indeclinable, ...), both parts of a double surname are declined; the template is stored in
`morpho.guessed_template`.

## Export to slf and the comparison with aot.ru
```
python generate_wordforms.py --pos noun --output-articles result/nouns.jsonl --failures result/noun_failures.tsv
python export_slf.py
mkdir -p result/mrd
cp ../data/Russian/gramtab.json result/mrd/
echo '{"MRD_FILE": "morphs.json", "LANG": "RUSSIAN", "USERS": ["wiktionary"]}' > result/mrd/project.mwz
echo '{"flexia_models": [], "accent_models": [], "sessions": [], "prefix_sets": [], "lemmas": []}' > result/mrd/morphs.json
slf_convert --to-mrd --slf result/wiktionary.slf --mwz result/mrd/project.mwz --user wiktionary
python compare_with_aot.py
```
Nouns with `{{сущ-ru|кни́га|ж 3a}}` (46243 articles, mostly the new ones: `книга`, `автор`, `оптогенетика`) are
rendered by a Lua module, so their tables are not in the dump. For them the template `сущ ru <gender> <index>` is used
(`src/nouns.py`): `ж 3a` -> `сущ ru f ina 3a`, `мо <п 1a>` (declined as an adjective) -> `сущ ru m a (п 1a)`,
`мо <жо 3*a>` (masculine, declined as feminine) -> `сущ ru f a 3*a` with the masculine gender, `мо-жо 1a` is of the
common gender, `мн. <ж 3a>` and `pt=1` are pluralia tantum (the lemma is the nominative plural), a trailing `—` means
no plural, the type 8 after a sibilant uses `8a-ш` (`брешам`). The stem of the lemma is the lemma without the ending
of the template, the other stems are the same (they differ by the stress only) except for Zaliznyak's fleeting vowel:
it is dropped in the oblique cases of masculine nouns (`кусок` -> `куска`, `боец` -> `бойца`, `палец` -> `пальца`,
`огонёк` -> `огонька`) and inserted in the genitive plural of feminine and neuter ones (`загадка` -> `загадок`,
`ложка` -> `ложек`, `чайка` -> `чаек`, `капля` -> `капель`, `башня` -> `башен`, `статья` -> `статей`); `°` gives
`крестьянин` -> `крестьяне`, `котёнок` -> `котята`. The accusative follows the animacy (some templates are wrong:
`сущ ru f ina 6a` has `идей`), the forms given in the article (`gen-pl=друзе́й`) replace the generated ones. The
template used is stored in `morpho.lua_template`, the grammems in `morpho.noun_index`. 96% of the generated forms of
the words known to aot are in aot, the rest are mostly the plural of `sing_tant` words (`фторирование`). The failures
(896) are listed in `result/noun_failures.tsv`: compound words (`м, 1a + 1a`), errors of the articles (`вилы` with
`ж 1a`).

Articles without `морфо-ru` (25.5 thousand: `завод`, `сердце`, `искусство`) have no morpheme segmentation, their stems
are taken as is. Template names that are not templates are reduced (`src/nouns.py`): `1a((2))` -> `1a(2)`, `1b?` ->
`1b`, `3*bX` -> `3*b`, an index in brackets is a plurale tantum: `сущ ru f ina (3*a)` (`сутки`), the template used
is stored in `morpho.resolved_template`. Proper names and obscene words are generated too. Not generated: articles without an index (10.6
thousand, `сущ ru m ina`: the table shows nothing, 9.7 thousand of them are not in aot), compound words
(`сущ ru 2`, `ковёр-самолёт`) and `сущ ru пол1` (`полчаса`).

`export_slf.py` writes all paradigms of `result/*.jsonl` to `result/wiktionary.slf`, the slf format of MorphWizard
(`src/slf.py`), a homonym whose paradigm is a part of the paradigm of another homonym (`снос 1`, `снос 2` with the
second genitive `сносу`) is not written, aot has one lemma for them; a paradigm is a list of lines `form POS grammems` with the Latin names of the Russian gramtab of aot.ru
(`N mas,sg,nom`, `PARTICIPLE pres,act,mas,sg,acc,anim`), the lemma first, the animacy of nouns and the aspect and
transitivity of verbs are in `$type_grm`. The forms are named as in aot: the non-past of a perfective verb is the
future, a biaspectual verb has both, a surname is one paradigm of both genders (`N mas,fem,pl,nom` for the plural),
an indeclinable word is one form (`N mas,0`, `A 0,anim,inanim`), a pronoun-adjective is `PA`, an ordinal numeral is
`ORD_NUM`. The comparatives of adverbs are not exported, in aot they are forms of adjectives. Stress marks are lost.

The slf file is loaded into a dictionary of MorphWizard (`result/mrd/`: `project.mwz`, `gramtab.json` of aot.ru,
`morphs.json`) by the C++ utility `slf_convert` of nlp_base (`--to-slf` writes a dictionary back to slf). The dictionary
is created by the commands above, an empty one each time, since `--to-mrd` adds paradigms to it. `slf_convert` is
built with nlp_base (`build/Source/nlp_base/slf_convert/slf_convert`).

The full run on the dump of 2026-11-01: `extract_from_dump.py` takes about 5 minutes, `generate_wordforms.py` a minute
for each part of speech, `slf_convert --to-mrd` 2 minutes (233285 paradigms), `compare_with_aot.py` 40 seconds.

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
as in `pairs.tsv`). A decision holds for these exact differences, if they change, the pair comes up again.
The grammem `arch` is removed before the comparison, so a form added to aot as obsolete is not a difference.
Reasons:
- `template_plural`: the plural is shown by the Wiktionary template by default, aot has `sing_tant` and is kept;
- `wiki_no_form`: aot has the second genitive, the optional parameter `Р` of the article is empty, aot is kept;
- `wiki_error`: the form of Wiktionary is wrong for this category (`блинов` in the parameter `Р`), it is not added;
- `wiki_doubtful`: the form is doubtful, it is not added until it is checked in a corpus.

## The plural of toponyms
```
python add_toponym_plurals.py --input ../data/Russian/morphs.json --output ../data/Russian/morphs.json
slf_convert --to-mrd --slf empty.slf --mwz ../data/Russian/project.mwz --user guest
```
In aot.ru `sing_tant` (дфст, de facto singularia tantum) means that the plural exists but is rarely used: the rule
`Rule_DeadPlurals` of MAPost removes the plural readings of such a word if the context is not plural (`из Москвы` is
genitive singular only). So a paradigm with `sing_tant` should have the plural, as `АБАДАН` has, but 2220 toponyms
(`loc,sing_tant`: `МОСКВА`, `ИТАЛИЯ`) had no plural forms. The plural of toponyms is used in Flibusta: `по Парижам`,
`в разных Италиях`, `по всевозможным Турциям`, `двух павших Римов`, `обоих Египтов`. The script takes the plural from
the Wiktionary dictionary (`result/mrd`): a paradigm with the same lemma and the same singular forms (one of them may
have more: the second prepositional of aot, `Италиею` of Wiktionary); the stem is shortened if the plural has a
fleeting vowel (`Авдеевка` -> `Авдеевок`), the stress of the new forms is unknown, `sing_tant` is kept. The plural was
added to 658 toponyms, the list of the added forms is `result/toponym_plurals.tsv`; 1516 toponyms have no such paradigm
in Wiktionary (1409 have no article), 46 have several different ones.

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
articles whose lemma is not a lemma of aot.ru, `slf_convert --to-mrd` adds them to aot: 686 paradigms (313 nouns, 240
verbs, 64 adjectives, 69 other words), 5 lemmas were in aot (`хуй`, `пизда`), 47 articles have no paradigm (forms with
an article of their own: `спизженный`, `проебав`; failures: `еть`, `выёбистый`). The stress of the added words is
unknown (the slf export loses it).

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
