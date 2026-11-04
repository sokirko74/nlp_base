#include "../morph_wizard/wizard.h"

#include "nlp_base/common/argparse.h"


void initArgParser(int argc, const char** argv, ArgumentParser& parser) {
    parser.AddOption("--help");
    parser.AddArgument("--input", "input file");
    parser.Parse(argc, argv);
}


int main(int argc, const char* argv[])
{
    ArgumentParser args;
    initArgParser(argc, argv, args);
    MorphoWizard wizard;
	wizard.load_wizard(args.Retrieve("input"), "guest", false, true, true);
    //for (lemma_iterator_t it = wizard.m_LemmaToParadigm.begin(); it != wizard.m_LemmaToParadigm.end(); it++) {
    for (const auto& [lemma, lemm_info] : wizard.m_LemmaToParadigm) {
        auto s = convert_to_utf8(lemma, wizard.m_Language);
        const CFlexiaModel& P = wizard.m_FlexiaModels[lemm_info.m_FlexiaModelNo];
        std::string common_grammems = wizard.get_grammem_string(lemm_info.GetCommonAncodeCopy());
        std::string gramcode = P.m_Flexia[0].m_Gramcode.substr(0, 2);
        std::string grammems = wizard.get_pos_string_and_grammems(gramcode);
        std::cout << s << "\t" << common_grammems << "\t" << grammems << std::endl;
    }

    return 0;
}


