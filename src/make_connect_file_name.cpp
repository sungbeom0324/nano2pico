#include "make_connect_file_name.hpp"

#include <iostream>
#include <regex>
#include <cstdlib>

using namespace std;

string MakeConnectFileName(const string &in_dir, const string &in_file) {
  smatch matches;

  regex data_regex(
    ".*/store/data/(Run20[^/]+)/([^/]+)/NANOAOD/([^/]+)/.*$"
  );

  if (!regex_match(in_dir, matches, data_regex)) {
    cout << "ERROR: Could not parse CMSConnect input directory: "
         << in_dir << endl;
    exit(1);
  }

  string run = matches[1];
  string dataset = matches[2];
  string condition = matches[3];

  string file_name =
    dataset + "__" +
    run + "__" +
    condition + "__" +
    in_file;

  return file_name;
}
