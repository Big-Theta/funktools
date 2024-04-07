cmake_minimum_required(VERSION 3.14)

include(cmake/prelude.cmake)

project(
    templates
    VERSION 0.1.0
    DESCRIPTION "An example of using pybind11 bindings for templated functions with the funktools.template decorator."
    HOMEPAGE_URL "https://github.com/Big-Theta/funktools"
    LANGUAGES CXX
)

include(cmake/project-is-top-level.cmake)
include(cmake/variables.cmake)

# ---- Declare library ----

include(FetchContent)
FetchContent_Populate(
    pybind11
    GIT_REPOSITORY https://github.com/pybind/pybind11.git
    GIT_TAG        8a099e4  # v2.11.1
)
add_subdirectory(${pybind11_SOURCE_DIR})

#find_package(PkgConfig)
#pkg_check_modules(PYBIND11 REQUIRED pybind11)

pybind11_add_module(example src/example.cpp)
get_filename_component(funktools_path ${CMAKE_SOURCE_DIR}/../.. ABSOLUTE)
target_compile_definitions(example PUBLIC FUNKTOOLS_PATH=${funktools_path})
set_target_properties(example PROPERTIES SUFFIX ".so")

configure_file(${CMAKE_SOURCE_DIR}/test_example.py.in ${CMAKE_BINARY_DIR}/test_example.py COPYONLY)
add_custom_command(
  OUTPUT pytest_executed
  COMMAND pytest test_example.py
  DEPENDS example ${CMAKE_BINARY_DIR}/test_example.py
  WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
)
add_custom_target(test-example DEPENDS pytest_executed)

