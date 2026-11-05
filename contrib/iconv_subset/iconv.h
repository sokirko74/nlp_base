#include <string>
#include <vector>
#include <utility>

struct convert_exception : std::exception {
	std::string m_what;
	convert_exception(const char* what) : m_what(what) {

	}
	const char* what() const noexcept { return m_what.c_str(); }
};

extern std::string convert_cp1251_to_utf8(const std::string&);
extern std::string convert_cp1252_to_utf8(const std::string&);

extern std::string convert_utf8_to_cp1251(const char* s);
extern std::string convert_utf8_to_cp1252(const char* s);

// characters that do not exist in the encoding are replaced by placeholder;
// unknown gets (offset in the result, original utf8 bytes) for each of them
extern std::string convert_utf8_to_cp1251(const char* s, char placeholder, std::vector<std::pair<size_t, std::string>>& unknown);
extern std::string convert_utf8_to_cp1252(const char* s, char placeholder, std::vector<std::pair<size_t, std::string>>& unknown);
