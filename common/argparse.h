#pragma once

#include <string>
#include <vector>
#include <typeinfo>
#include <stdexcept>
#include <sstream>
#include <iostream>
#include <cassert>
#include <algorithm>
#include <unordered_map>
#include <fstream>
#include <plog/Log.h>

// Command line parser.
//   parser.AddArgument("--name", help, optional) : an option with a value: "--name VALUE" or "--name=VALUE"
//   parser.AddOption("--name", help)             : a flag without a value
//   parser.AddPositional("name", help, optional) : a positional argument (in the order of declaration)
//   parser.AddPositionalList("name", help, optional) : all remaining positional arguments (must be the last one)
// An option name can have a short synonym: "-o, --output". Options declared with repeatable=true
// may occur several times (see RetrieveList). "--" ends the options. "-h"/"--help" prints Usage()
// and exits, unless the program declares "--help" itself. SetVersion(text) adds "-V, --version",
// which prints the text and exits (before the required arguments are checked).
// The values of the arguments named "language", "log-level", "input" and "output" are checked/opened
// in Parse() (see GetLanguage, GetLogLevel, GetInputStream, GetOutputStream); opening the input/output
// files can be switched off with SetOpenStreams(false).
class ArgumentParser {
private:
    typedef std::string String;

    struct Argument {
        String Name;          // without the leading "--"
        String ShortName;     // e.g. "-o", may be empty
        bool Optional = true;
        bool MustHaveValue = false;
        bool Positional = false;
        bool List = false;    // positional: takes all the remaining positional arguments; option: repeatable
        String Help;

        String ValueName() const { return upper(Name); }

        String Synopsis() const {
            if (Positional) {
                String s = ValueName();
                if (List) s += "...";
                return Optional ? "[" + s + "]" : s;
            }
            String s;
            if (!ShortName.empty()) s += ShortName + ", ";
            s += "--" + Name;
            if (MustHaveValue) s += " " + ValueName();
            return s;
        }
    };

    String AppName;
    String Description;
    String Epilog;
    String Version;
    std::vector<Argument> Arguments;
    bool OpenStreams = true;

    std::unordered_map<String, std::vector<String> > ArgumentValues;
    MorphLanguageEnum  Language = morphUnknown;
    plog::Severity LogLevel = plog::Severity::info;
    std::istream* InputStream = nullptr;
    std::ifstream  InputStreamFile;
    std::ostream* OutputStream = nullptr;
    std::ofstream  OutputStreamFile;

    static String trim_copy(const String& s) {
        size_t b = s.find_first_not_of(" \t");
        size_t e = s.find_last_not_of(" \t");
        return (b == String::npos) ? String() : s.substr(b, e - b + 1);
    }

    static String upper(const String& in) {
        String out(in);
        std::transform(out.begin(), out.end(), out.begin(), ::toupper);
        return out;
    }

    static String escape(const String& in) {
        String out(in);
        if (in.find(' ') != std::string::npos) out = String("\"").append(out).append("\"");
        return out;
    }

    // "--name" or "-n, --name" (in any order)
    static Argument MakeOption(const String& names, bool optional, bool hasValue, const String& help, bool repeatable) {
        Argument a;
        std::stringstream ss(names);
        String item;
        while (std::getline(ss, item, ',')) {
            item = trim_copy(item);
            if (item.size() > 2 && item.substr(0, 2) == "--") {
                a.Name = item.substr(2);
            }
            else if (item.size() == 2 && item[0] == '-') {
                a.ShortName = item;
            }
            else {
                throw std::logic_error("ArgumentParser: bad option name \"" + names + "\"");
            }
        }
        if (a.Name.empty()) throw std::logic_error("ArgumentParser: no long option name in \"" + names + "\"");
        a.Optional = optional;
        a.MustHaveValue = hasValue;
        a.List = repeatable;
        a.Help = help;
        return a;
    }

    void ArgumentError(const std::string& msg, bool show_usage = true) const {
        std::cerr << "ArgumentParser error: " << msg << std::endl;
        if (show_usage) std::cerr << Usage() << std::endl;
        exit(-5);
    }

    const Argument* FindArgument(const String& name) const {
        for (auto& a : Arguments) {
            if (a.Name == name) return &a;
        }
        return nullptr;
    }

    const Argument* FindOption(const String& s) const {
        for (auto &a: Arguments) {
            if (a.Positional) continue;
            if (s == "--" + a.Name) return &a;
            if (!a.ShortName.empty() && s == a.ShortName) return &a;
        }
        return nullptr;
    }

    void CheckValidAndInitCommon()  {
        for (auto& a : Arguments) {
            if (!a.Optional && !Exists(a.Name)) {
                ArgumentError(String("argument is missing: ") + a.Name);
            }
            if (Exists(a.Name) && a.MustHaveValue && Retrieve(a.Name).empty()) {
                ArgumentError(String("argument value is missing: ") + a.Name);
            }
            if (a.Name == "language") {
                if (!GetLanguageByString(Retrieve("language"), Language)) {
                    ArgumentError( "bad language " + Retrieve("language") );
                }

            }
            if (a.Name == "log-level") {
                auto log_level_str = Retrieve("log-level");
                if (!log_level_str.empty()) {
                    LogLevel = plog::severityFromString(Retrieve("log-level").c_str());
                    if (LogLevel == plog::Severity::none) {
                        ArgumentError("bad log-level " + Retrieve("log-level"));
                    }
                }
            }

            if (a.Name == "input" && OpenStreams) {
                if (Retrieve("input") != "-") {
                    auto path = Retrieve("input");
                    std::cerr << "read " << path << "\n";
                    InputStreamFile.open(path);
                    if (!InputStreamFile.is_open()) {
                        ArgumentError("cannot open file " + path);
                    }
                    InputStream = &InputStreamFile;
                } else {
                    InputStream = &std::cin;
                }
            }
            if (a.Name == "output" && OpenStreams) {
                if (Retrieve("output") != "-") {
					// to write unix eoln under windows open files in binary mode
                    OutputStreamFile.open(Retrieve("output"), std::ifstream::out| std::ifstream::binary);
                    if (!OutputStreamFile.is_open()) {
                        ArgumentError("cannot open file " + Retrieve("output"));
                    }
                    OutputStream = &OutputStreamFile;
                } else {
                    OutputStream = &std::cout;
                }
            }
        }
    }


public:
    ArgumentParser()  {}

    // an option with a value; repeatable: the option may be given several times (see RetrieveList)
    void AddArgument(const String& name, String help = "", bool _optional = false, bool repeatable = false) {
        Arguments.push_back(MakeOption(name, _optional, true, help, repeatable));
    }

    // a flag without a value
    void AddOption(const String& name, String help = "") {
        Arguments.push_back(MakeOption(name, true, false, help, false));
    }

    void AddPositional(const String& name, String help = "", bool _optional = false) {
        Argument a;
        a.Name = name;
        a.Positional = true;
        a.Optional = _optional;
        a.MustHaveValue = true;
        a.Help = help;
        Arguments.push_back(a);
    }

    // all remaining positional arguments, must be declared after all the other positional arguments
    void AddPositionalList(const String& name, String help = "", bool _optional = false) {
        AddPositional(name, help, _optional);
        Arguments.back().List = true;
    }

    // a text printed by Usage() after the synopsis line
    void SetDescription(const String& s) { Description = s; }

    // a text printed by Usage() at the end (notes, examples)
    void SetEpilog(const String& s) { Epilog = s; }

    // adds the option "-V, --version" that prints this text and exits
    void SetVersion(const String& s) {
        Version = s;
        if (!FindArgument("version")) AddOption("-V, --version", "print the program version and exit");
    }

    // open the files of the arguments "input" and "output" in Parse() (default: true)
    void SetOpenStreams(bool v) { OpenStreams = v; }

    void Parse(size_t argc, const char** argv) {
        const Argument* active = nullptr; // an option waiting for its value
        bool optionsDone = false;
        size_t posNo = 0;
        for (size_t argNo = 0; argNo < argc; ++argNo) {
            String argStr = argv[argNo];
            if (argNo == 0) {
                AppName = argStr;
                continue;
            }
            if (active) {
                ArgumentValues[active->Name].back() = argStr;
                active = nullptr;
                continue;
            }
            if (!optionsDone && argStr == "--") {
                optionsDone = true;
                continue;
            }
            if (!optionsDone && argStr.size() > 1 && argStr[0] == '-') {
                String name = argStr, value;
                bool hasValue = false;
                size_t eq = argStr.find('=');
                if (argStr.substr(0, 2) == "--" && eq != String::npos) {
                    name = argStr.substr(0, eq);
                    value = argStr.substr(eq + 1);
                    hasValue = true;
                }
                const Argument* a = FindOption(name);
                if (!a) {
                    if (name == "--help" || name == "-h") {
                        std::cout << Usage() << std::endl;
                        exit(0);
                    }
                    ArgumentError(String("unknown option ") + argStr);
                }
                auto& values = ArgumentValues[a->Name];
                if (!a->List) values.clear();
                if (a->MustHaveValue) {
                    values.push_back(value);
                    if (!hasValue) active = a;
                }
                else {
                    if (hasValue) ArgumentError(String("option ") + name + " takes no value");
                    values.push_back("");
                }
                continue;
            }
            // a positional argument
            for (; posNo < Arguments.size(); ++posNo) {
                if (Arguments[posNo].Positional) break;
            }
            if (posNo == Arguments.size()) {
                ArgumentError(String("bad argument ") + argStr);
            }
            ArgumentValues[Arguments[posNo].Name].push_back(argStr);
            if (!Arguments[posNo].List) ++posNo;
        }
        if (!Version.empty() && Exists("version")) {
            std::cout << Version << std::endl;
            exit(0);
        }
        CheckValidAndInitCommon();
    }

    // the (last) value of an argument, "" if it is not given
    String Retrieve(const String& name) const {
        auto it = ArgumentValues.find(name);
        return (it == ArgumentValues.end() || it->second.empty()) ? "" : it->second.back();
    }

    int Retrieve(const String& name, int default_value) const {
        auto it = ArgumentValues.find(name);
        return (it == ArgumentValues.end() || it->second.empty()) ? default_value : atoi(it->second.back().c_str());
    }

    // all values of a positional list or of a repeatable option
    std::vector<String> RetrieveList(const String& name) const {
        auto it = ArgumentValues.find(name);
        return (it == ArgumentValues.end()) ? std::vector<String>() : it->second;
    }

    bool Exists(const String& name) const {
        return ArgumentValues.find(name) != ArgumentValues.end();
    }

    MorphLanguageEnum GetLanguage() const {
        return Language;
    }

    plog::Severity GetLogLevel() const {
        return LogLevel;
    }

    std::ostream& GetOutputStream() const {
        return *OutputStream;
    }

    String CloseOutputStreamAndGetName() {
        if (OutputStreamFile.is_open()) {
            OutputStreamFile.close();
        };
        OutputStream  = 0;
        return Retrieve("output");
    }

    std::istream& GetInputStream() const {
        return *InputStream;
    }

    String Usage() const {
        std::stringstream help;
        help << "Usage: " << escape(AppName);
        bool hasOptions = FindArgument("help") == nullptr; // the automatic --help
        for (auto& a : Arguments) {
            if (!a.Positional) {
                if (a.Optional) hasOptions = true;
                else help << " " << a.Synopsis();
            }
        }
        if (hasOptions) help << " [OPTIONS]";
        for (auto& a : Arguments) {
            if (a.Positional) help << " " << a.Synopsis();
        }
        help << "\n";
        if (!Description.empty()) {
            help << Description << "\n";
        }

        // the left column
        size_t width = 0;
        for (auto& a : Arguments) width = std::max(width, a.Synopsis().size());
        width = std::max(width, String("-h, --help").size());
        auto line = [&](const String& left, const String& text) {
            help << "  " << left;
            if (!text.empty()) help << String(width - left.size() + 2, ' ') << text;
            help << "\n";
        };

        bool hasPositional = false;
        for (auto& a : Arguments) hasPositional = hasPositional || (a.Positional && !a.Help.empty());
        if (hasPositional) {
            help << "\nArguments:\n";
            for (auto& a : Arguments) {
                if (a.Positional) line(a.Synopsis(), a.Help);
            }
        }

        help << "\nOptions:\n";
        for (auto& a : Arguments) {
            if (!a.Positional) {
                String text = a.Help;
                if (!a.Optional) text += " (required)";
                if (a.List) text += " (repeatable)";
                line(a.Synopsis(), text);
            }
        }
        if (FindArgument("help") == nullptr) {
            line("-h, --help", "this help message");
        }
        if (!Epilog.empty()) {
            help << "\n" << Epilog << "\n";
        }
        return help.str();
    }

    StringVector GetInputFiles() const {
        std::vector<std::string> files;
        if (Exists("input-is-list-file")) {
            std::string s;
            while (getline(GetInputStream(), s)) {
                Trim(s);
                if (!FileExists(s.c_str())) {
                    std::cerr << "Cannot open " << s << "\n";
                    exit(1);
                };
                files.push_back(s);
            }
        } else
            files.push_back(Retrieve("input"));
        return files;
    }
};
