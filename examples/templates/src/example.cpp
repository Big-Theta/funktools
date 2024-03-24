#include <pybind11/pybind11.h>

#define STRINGIZE_(x) #x
#define STRINGIZE(x) STRINGIZE_(x)

template <typename T>
std::string get();

template <>
std::string get<int>() {
  return "get<int>";
}

template <>
std::string get<double>() {
  return "get<double>";
}

class Foo {};
template <>
std::string get<Foo>() {
  return "get<Foo>";
}

template <typename T>
std::string get_from_arg(T);

template <>
std::string get_from_arg(int) {
  return "get_from_arg<int>";
}

template <>
std::string get_from_arg(double) {
  return "get_from_arg<double>";
}

template <>
std::string get_from_arg(Foo) {
  return "get_from_arg<Foo>";
}

PYBIND11_MODULE(example, m) {
  m.doc() = "pybind11 example plugin";

  const auto& sys = pybind11::module_::import("sys");
  sys.attr("path").attr("append")(STRINGIZE(FUNKTOOLS_PATH));

  pybind11::class_<Foo>(m, "Foo").def(pybind11::init<>());

  m.def("_get_int", &get<int>);
  m.def("_get_double", &get<double>);
  m.def("_get_Foo", &get<Foo>);

  auto getFunc = pybind11::module_::import("funktools")
                     .attr("template")
                     .attr("make")("get");

  m.attr("get") = getFunc;

  // Due to https://github.com/pybind/pybind11/issues/2486, basic types aren't
  // automatically converted with `pybind11::type::of`.
  getFunc[pybind11::type::of(pybind11::int_())] = m.attr("_get_int");
  getFunc[pybind11::type::of(pybind11::float_())] = m.attr("_get_double");
  getFunc[pybind11::type::of<Foo>()] = m.attr("_get_Foo");

  m.def("_get_from_arg_int", &get_from_arg<int>);
  m.def("_get_from_arg_double", &get_from_arg<double>);
  m.def("_get_from_arg_Foo", &get_from_arg<Foo>);

  auto getFromArgFunc = pybind11::module_::import("funktools")
                            .attr("template")
                            .attr("make")("get_from_arg");

  m.attr("get_from_arg") = getFromArgFunc;

  getFromArgFunc[pybind11::type::of(pybind11::int_())] = m.attr("_get_from_arg_int");
  getFromArgFunc[pybind11::type::of(pybind11::float_())] = m.attr("_get_from_arg_double");
  getFromArgFunc[pybind11::type::of<Foo>()] = m.attr("_get_from_arg_Foo");
}
