#pragma once
#include  "base_types.h"
#include "../contrib/iconv_subset/iconv.h"
#include "vector"

// single byte chars for Graphan
const BYTE GraphematicalTAB    = (BYTE) 16;
const BYTE cParagraph    = (BYTE) 21;
const BYTE Apostrophe    = (BYTE) 39;
const BYTE cHyphenChar   = (BYTE) 45;

// important char of windows-1252
const BYTE Nu = 181;
const BYTE szlig = 223;

// windows-1251
const BYTE cEllipseChar  = (BYTE) 133;
const BYTE GraphematicalSPACE = (BYTE)160;
const BYTE OpenQuoteMark1251  = (BYTE) 171;
const BYTE cCompanyChar  = (BYTE) 176;
const BYTE cPiChar       = (BYTE) 182;
const BYTE GraphematicalEOLN = (BYTE)182;
const BYTE cIonChar      = (BYTE) 183;
const BYTE cNumberChar   = (BYTE) 185;
const BYTE CloseQuoteMark1251  = (BYTE) 187;



extern  bool is_english_upper(BYTE x);
extern  bool is_english_lower(BYTE x);
extern  bool is_german_upper(BYTE x);
extern  bool is_german_lower(BYTE x);
extern  bool is_russian_upper(BYTE x);
extern  bool is_russian_lower(BYTE x);

extern  bool is_upper_consonant(BYTE x, MorphLanguageEnum Langua);
extern  bool is_upper_vowel(BYTE x, MorphLanguageEnum Langua);

extern  bool is_english_alpha(BYTE x);
extern  bool is_russian_alpha(BYTE x);
extern  bool is_german_alpha(BYTE x);

extern  bool is_alpha(BYTE x);
extern  bool is_generic_alpha(BYTE x);   // english letter or any byte >= 128
extern  bool is_generic_lower(BYTE x);
extern  bool is_generic_upper(BYTE x);
extern  bool is_URL_alpha(BYTE x);
extern  bool is_lower_alpha(BYTE x, MorphLanguageEnum langua);
extern  bool is_upper_alpha(BYTE x, MorphLanguageEnum langua);

extern  BYTE ReverseChar(BYTE ch, MorphLanguageEnum langua);
extern std::string& RmlMakeUpper(std::string& word, MorphLanguageEnum langua);
extern std::string& RmlMakeLower(std::string& word, MorphLanguageEnum langua);
extern std::string& EngMakeUpper(std::string& word);   // ASCII letters only
extern std::string& EngMakeLower(std::string& word);   // ASCII letters only
extern bool is_alpha(BYTE x, MorphLanguageEnum langua);
// single-byte (cp1251/cp1252) check that all chars of word are letters of langua (or '-');
// cf. CheckLanguage(std::string), which expects utf8
extern bool CheckLanguageSingleByte(const char* word, MorphLanguageEnum langua);
extern bool IsRussian(const char* word);                // CheckLanguageSingleByte(word, morphRussian)

// morphGeneric/morphURL texts are kept as raw utf8 bytes (no single-byte conversion, every byte >= 128 is a letter)
inline bool is_raw_utf8_language(MorphLanguageEnum langua) { return langua == morphGeneric || langua == morphURL; }
std::string convert_from_utf8(const char* utf8str, const MorphLanguageEnum langua);
// placeholder for characters that do not exist in the single-byte encoding of langua
// (0x98 is unused in cp1251, 0x81 is unused in cp1252)
inline BYTE unknown_char_placeholder(MorphLanguageEnum langua) {
	return (langua == morphRussian || langua == morphFioDisclosures) ? 0x98 : 0x81;
}
// like convert_from_utf8, but characters that do not exist in the encoding become
// unknown_char_placeholder(langua); unknown gets (offset in the result, original utf8) for each of them
std::string convert_from_utf8_keep_unknown(const char* utf8str, const MorphLanguageEnum langua, std::vector<std::pair<size_t, std::string>>& unknown);
std::string convert_to_utf8(const std::string& str, const MorphLanguageEnum langua);


extern void ConvertJO2Je(std::string& src);
extern void ConvertJO2Je(char* src, size_t Length);
extern std::string ConvertASCIIToHtmlSymbols(const std::string& txt);


inline std::string _R(const char* buffer) {
	return convert_from_utf8(buffer, morphRussian);
}

inline std::string _R(const std::string& s) {
	return _R(s.c_str());
}

extern bool		IsSuperEqualChar(BYTE ch1, BYTE ch2, MorphLanguageEnum langua);
extern BYTE		force_rus_char(BYTE ch);
extern BYTE convert_html_entity_to_char(const std::string& entity);
