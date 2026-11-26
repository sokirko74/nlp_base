"""
Words and forms added to aot by hand, after a look at the Flibusta corpus.

- `NEW_LEMMAS`: a new lemma with the flexia, accent and type models of another lemma of the same declension:
  the substantive `бывший` (ex-partner, `мой бывший опять звонил`, `моя бывшая`; after a possessive pronoun 10-20% of
  `бывший`/`бывшая` are substantives, about two thousand uses), as `знакомый`/`знакомая`, declined as `ведущий`/`ведущая`.
  Wiktionary gives it as a meaning `{{субст.}}` of the participle `бывший`. The note ДО (N neu,0 inanim, as РЕ):
  aot had all the notes but `до`, the homonym of the preposition; the Mapost rule `Rule_DO` removes it before a
  genitive or a number (`до 5 часов`, `до вечера`), it stays in `ноту до`, `до мажор`; `StatData.txt` gives the
  preposition the weight 10000 and the note 1.
  The childish noun КАКА (`ка́ка`, as БЯКА inanim; aot had only the indeclinable name Кака): its genitive plural `как`
  is a homonym of the most frequent `как`, the Mapost rule `Rule_KAK` removes it unless a number or a word of quantity
  (`много`, `несколько`) is before it.
- `NEW_FORMS`: a new form with the gramcode of an existing form of the lemma: `всяк` (вся́к) of the substantive pronoun
  ВСЯКИЙ (`всяк норовит`, `всяк сюда входящий`: 87% of 200 contexts) and of the pronoun-adjective ВСЯКИЙ (`всяк
  человек`, `всяк сверчок знай свой шесток`: 13%). `всяка`, `всяки` of Wiktionary are not added: in the corpus they are
  folk full forms (`всяка тварь`, `всяки травки`).

The result should be saved by `slf_convert --to-mrd` with an empty slf file.
"""
import argparse
import json
import time
from collections import Counter

# (new lemma, the model lemma, the part of speech of the model, the type grammems of the model or None)
NEW_LEMMAS = [("БЫВШИЙ", "ВЕДУЩИЙ", "N", None), ("БЫВШАЯ", "ВЕДУЩАЯ", "N", None), ("ДО", "РЕ", "N", None),
              ("КАКА", "БЯКА", "N", {"inanim"})]
# (lemma, its part of speech, the new form, the existing form whose gramcode is taken, the stressed vowel from the end)
NEW_FORMS = [("ВСЯКИЙ", "PRON", "ВСЯК", "ВСЯКИЙ", 0), ("ВСЯКИЙ", "PA", "ВСЯК", "ВСЯКИЙ", 0)]


def main():
    with open(args.input) as inp:
        data = json.load(inp)
    codes = json.load(open(args.gramtab))["gramcodes"]
    flexia, accents = data["flexia_models"], data["accent_models"]

    def pos(lemma) -> str:
        return codes[flexia[lemma["f"]]["endings"][0]["gramcode"][:2]]["p"]

    def find(word: str, part_of_speech: str, type_grammems=None):
        found = [lemma for lemma in data["lemmas"] if lemma["l"] == word and pos(lemma) == part_of_speech
                 and "n" not in lemma and (type_grammems is None or
                                           set(codes[lemma["t"]]["g"] if lemma.get("t") else []) == type_grammems)]
        return found[0] if len(found) == 1 else None

    now = time.strftime("%H:%M, %d %B %Y")
    data["sessions"].append({"user": args.user, "start": now, "last_save": now})
    session = len(data["sessions"]) - 1
    counts = Counter()
    for word, model_word, part_of_speech, type_grammems in NEW_LEMMAS:
        model = find(model_word, part_of_speech, type_grammems)
        if model is None:
            raise ValueError(f"no single model {model_word} {part_of_speech} {type_grammems}")
        # a lemma with the same paradigm exists (КАКА, the indeclinable name, is another word)
        if any(lemma["l"] == word and lemma["f"] == model["f"] and "n" not in lemma for lemma in data["lemmas"]):
            counts["lemma exists: " + word] += 1
            continue
        lemma = {"l": word, "f": model["f"], "a": model["a"], "s": session}
        if model.get("t"):
            lemma["t"] = model["t"]
        data["lemmas"].append(lemma)
        counts["lemmas added"] += 1
    for word, part_of_speech, form, model_form, stress in NEW_FORMS:
        lemma = find(word, part_of_speech)
        if lemma is None:
            raise ValueError(f"no single lemma {word} {part_of_speech}")
        endings = flexia[lemma["f"]]["endings"]
        base = lemma["l"][:len(lemma["l"]) - len(endings[0]["flexia"])]
        if any(base + e["flexia"] == form for e in endings):
            counts["form exists: " + form + " " + part_of_speech] += 1
            continue
        if not form.startswith(base):
            raise ValueError(f"{form} does not continue the stem {base}")
        gramcode = next(e["gramcode"] for e in endings if base + e["flexia"] == model_form)
        new_endings = endings + [{"flexia": form[len(base):], "gramcode": gramcode}]
        new_model = {"endings": new_endings}
        if new_model in flexia:
            lemma["f"] = flexia.index(new_model)
        else:
            lemma["f"] = len(flexia)
            flexia.append(new_model)
        new_accent = accents[lemma["a"]] + [stress]
        if new_accent in accents:
            lemma["a"] = accents.index(new_accent)
        else:
            lemma["a"] = len(accents)
            accents.append(new_accent)
        counts["forms added"] += 1
    with open(args.output, "w") as outp:
        json.dump(data, outp, ensure_ascii=False)
    print(dict(counts))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--gramtab", default="../data/Russian/gramtab.json")
    parser.add_argument("--user", default="wiktionary")
    args = parser.parse_args()
    main()
