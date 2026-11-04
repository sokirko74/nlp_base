declare_cmake_min_version()

project(GraphanLib)

add_library(GraphanLib
        C_desc.cpp
        Consent.cpp
        Cs_hiera.cpp
        GraphanDicts.cpp
        GraphmatFile.cpp
        HtmlConv.cpp
        Oborots.cpp
        Sentences.cpp
        StdAfx.cpp
        UnitHolder.cpp
        Writegra.cpp
        abbrev.cpp
        graline.cpp
        abbrev.h
        Consent.h
        graline.h
        GraphanDicts.h
        GraphmatFile.h
        HTMLConv.h
        StdGraph.h
        UnitHolder.h

)

target_link_libraries(GraphanLib
    morphology_common
    StructDictLib
)


if (BUILD_DICTS)
    add_dependencies (GraphanLib GraphanDicts)
endif()
add_subdirectory (tests)
