#!/usr/bin/env python3

import os
import sys
import ROOT
import queue_system
from ROOT import TChain


print("DEBUG CHECKER: started")


# ------------------------------------------------------------
# Get information from queue_system
# ------------------------------------------------------------

print("DEBUG CHECKER: before decompress arguments")

job_log_string = queue_system.decompress_string(sys.argv[1])
job_argument_string = queue_system.decompress_string(sys.argv[2])

print("DEBUG CHECKER: after decompress arguments")
print("DEBUG CHECKER: job_log_string length =", len(job_log_string))
print("DEBUG CHECKER: job_argument_string =", repr(job_argument_string))

print(job_argument_string)


# ------------------------------------------------------------
# Golden JSON
#
# The JSON parsing remains in Python because it runs only once.
# The event-by-event Golden JSON decision is moved to C++ and
# executed inside ROOT::RDataFrame.
# ------------------------------------------------------------

class GoldenJson:

  # key   : run number
  # value : [(start_lumi, end_lumi), ...]
  good_lumi_blocks = {}

  def __init__(self):

    print("DEBUG CHECKER: GoldenJson init started")

    # Avoid keeping data from a previous instance if this module
    # is ever reused in the same Python process.
    self.good_lumi_blocks = {}

    for json_filename in os.listdir('txt/json/'):

      json_file = open('txt/json/' + json_filename, 'r')
      json_file_text = json_file.read().split('\n')
      json_file.close()

      for run_line in json_file_text:

        if len(run_line.split('"')) < 2:
          continue

        run_number = int(run_line.split('"')[1])

        lumi_blocks_string = run_line[
          run_line.find('['):run_line.rfind(']')
        ]

        lumi_blocks_list = (
          lumi_blocks_string
          .replace('[', '')
          .replace(']', '')
          .replace(' ', '')
          .split(',')
        )

        int_lumi_blocks_list = []

        # Python 3: use // instead of /
        for index in range(len(lumi_blocks_list) // 2):

          int_lumi_blocks_list.append(
            (
              int(lumi_blocks_list[2 * index]),
              int(lumi_blocks_list[2 * index + 1])
            )
          )

        self.good_lumi_blocks[run_number] = int_lumi_blocks_list

    print("DEBUG CHECKER: GoldenJson init finished")
    print(
      "DEBUG CHECKER: number of runs in GoldenJson =",
      len(self.good_lumi_blocks)
    )


  def declare_cpp_filter(self):

    print("DEBUG CHECKER: declaring Golden JSON C++ filter")

    # Build a C++ map once. The per-event lookup then happens entirely
    # in C++, rather than calling a Python function for every event.
    run_entries = []

    for run_number in sorted(self.good_lumi_blocks):

      lumi_entries = []

      for start_lumi, end_lumi in self.good_lumi_blocks[run_number]:

        lumi_entries.append(
          "{{{}u, {}u}}".format(start_lumi, end_lumi)
        )

      run_entries.append(
        "{{{}u, {{{}}}}}".format(
          run_number,
          ", ".join(lumi_entries)
        )
      )

    cpp_code = r"""
#include <unordered_map>
#include <vector>
#include <utility>

namespace checker_rdf {

using LumiRange = std::pair<unsigned int, unsigned int>;

static const std::unordered_map<
  unsigned int,
  std::vector<LumiRange>
> good_lumi_blocks = {
%s
};

bool PassGoldenJson(
    unsigned int run,
    unsigned int lumi_block) {

  const auto run_it = good_lumi_blocks.find(run);

  if (run_it == good_lumi_blocks.end()) {
    return false;
  }

  for (const auto &lumi_range : run_it->second) {

    if (
      lumi_block >= lumi_range.first
      && lumi_block <= lumi_range.second
    ) {
      return true;
    }
  }

  return false;
}

} // namespace checker_rdf
""" % ",\n".join(run_entries)

    ROOT.gInterpreter.Declare(cpp_code)

    print("DEBUG CHECKER: Golden JSON C++ filter declared")


print("DEBUG CHECKER: before GoldenJson()")
golden_json = GoldenJson()
print("DEBUG CHECKER: after GoldenJson()")


# ------------------------------------------------------------
# Trigger helper for RDataFrame
# ------------------------------------------------------------

def MakeTriggerExpression(available_columns, trigger_list):

  available_triggers = [
    trigger_name
    for trigger_name in trigger_list
    if trigger_name in available_columns
  ]

  if len(available_triggers) == 0:
    return "false", []

  return (
    "(" + " || ".join(available_triggers) + ")",
    available_triggers
  )


# ------------------------------------------------------------
# Trigger lists
#
# Keep the same trigger lists as the original checker.
# ------------------------------------------------------------

met_triggers = [
  'HLT_PFMET90_PFMHT90_IDTight',
  'HLT_PFMETNoMu90_PFMHTNoMu90_IDTight',
  'HLT_PFMET100_PFMHT100_IDTight',
  'HLT_PFMETNoMu100_PFMHTNoMu100_IDTight',
  'HLT_PFMET110_PFMHT110_IDTight',
  'HLT_PFMETNoMu110_PFMHTNoMu110_IDTight',
  'HLT_PFMET120_PFMHT120_IDTight',
  'HLT_PFMETNoMu120_PFMHTNoMu120_IDTight',
  'HLT_PFMET130_PFMHT130_IDTight',
  'HLT_PFMETNoMu130_PFMHTNoMu130_IDTight',
  'HLT_PFMET140_PFMHT140_IDTight',
  'HLT_PFMETNoMu140_PFMHTNoMu140_IDTight',
  'HLT_PFMET100_PFMHT100_IDTight_PFHT60',
  'HLT_PFMETNoMu100_PFMHTNoMu100_IDTight_PFHT60',
  'HLT_PFMET110_PFMHT110_IDTight_PFHT60',
  'HLT_PFMETNoMu110_PFMHTNoMu110_IDTight_PFHT60',
  'HLT_PFMET120_PFMHT120_IDTight_PFHT60',
  'HLT_PFMETNoMu120_PFMHTNoMu120_IDTight_PFHT60',
  'HLT_PFMET130_PFMHT130_IDTight_PFHT60',
  'HLT_PFMETNoMu130_PFMHTNoMu130_IDTight_PFHT60',
  'HLT_PFMET140_PFMHT140_IDTight_PFHT60',
  'HLT_PFMETNoMu140_PFMHTNoMu140_IDTight_PFHT60',
  'HLT_PFMET120_PFMHT120_IDTight',
  'HLT_PFMETNoMu120_PFMHTNoMu120_IDTight_HFCleaned',
  'HLT_PFMET120_PFMHT120_IDTight_PFHT60_HFCleaned',
  'HLT_PFMET100_PFMHT100_IDTight_CaloBTagCSV_3p1',
  'HLT_PFMET110_PFMHT110_IDTight_CaloBTagCSV_3p1',
  'HLT_PFMET110_PFMHT110_IDTight_CaloBTagDeepCSV_3p1',
]

egamma_triggers = [
  'HLT_Ele25_WPTight_Gsf',
  'HLT_Ele27_WPTight_Gsf',
  'HLT_Ele28_WPTight_Gsf',
  'HLT_Ele30_WPTight_Gsf', # In EventTools::SaveTriggerDecisions
  'HLT_Ele32_WPTight_Gsf',
  'HLT_Ele32_WPTight_Gsf_L1DoubleEG',
  'HLT_Ele35_WPTight_Gsf',
  'HLT_Ele20_WPLoose_Gsf',
  'HLT_Ele45_WPLoose_Gsf',
  'HLT_Ele105_CaloIdVT_GsfTrkIdT',
  'HLT_Ele115_CaloIdVT_GsfTrkIdT',
  'HLT_Ele135_CaloIdVT_GsfTrkIdT',
  'HLT_Ele145_CaloIdVT_GsfTrkIdT',
  'HLT_Ele25_eta2p1_WPTight_Gsf',
  'HLT_Ele27_eta2p1_WPTight_Gsf',
  'HLT_Ele20_eta2p1_WPLoose_Gsf', # In EventTools::SaveTriggerDecisions
  'HLT_Ele25_eta2p1_WPLoose_Gsf', # In EventTools::SaveTriggerDecisions
  'HLT_Ele27_eta2p1_WPLoose_Gsf', # In EventTools::SaveTriggerDecisions
  'HLT_Ele20_eta2p1_WPTight_Gsf',
  'HLT_Ele15_IsoVVVL_PFHT350',
  'HLT_Ele15_IsoVVVL_PFHT400',
  'HLT_Ele15_IsoVVVL_PFHT450',
  'HLT_Ele15_IsoVVVL_PFHT600',
  'HLT_Ele50_IsoVVVL_PFHT450',
]

doubleeg_triggers = [
  'HLT_Ele23_Ele12_CaloIdL_TrackIdL_IsoVL_DZ',
  'HLT_Ele23_Ele12_CaloIdL_TrackIdL_IsoVL',
  'HLT_DoubleEle25_CaloIdL_MW',
  'HLT_DoublePhoton70',
  'HLT_Diphoton30_18_R9IdL_AND_HE_AND_IsoCaloId',
  'HLT_Diphoton30_18_R9IdL_AND_HE_AND_IsoCaloId_Mass55',
  'HLT_Diphoton30_22_R9Id_OR_IsoCaloId_AND_HE_R9Id_Mass90',
  'HLT_Diphoton30_22_R9Id_OR_IsoCaloId_AND_HE_R9Id_Mass95',
]

muon_triggers = [
  'HLT_IsoMu20',
  'HLT_IsoMu22',
  'HLT_IsoMu24',
  'HLT_IsoMu27',
  'HLT_IsoTkMu20',
  'HLT_IsoTkMu22',
  'HLT_IsoTkMu24',
  'HLT_Mu50',
  'HLT_Mu55',
  'HLT_TkMu50',
  'HLT_IsoMu22_eta2p1',
  'HLT_IsoMu24_eta2p1',
  'HLT_Mu45_eta2p1',
  'HLT_Mu15_IsoVVVL_PFHT350',
  'HLT_Mu15_IsoVVVL_PFHT400',
  'HLT_Mu15_IsoVVVL_PFHT450',
  'HLT_Mu15_IsoVVVL_PFHT600',
  'HLT_Mu50_IsoVVVL_PFHT400',
  'HLT_Mu50_IsoVVVL_PFHT450',
]

jetht_triggers = [
  'HLT_PFJet500',
  'HLT_PFHT125',
  'HLT_PFHT200',
  'HLT_PFHT300',
  'HLT_PFHT400',
  'HLT_PFHT475',
  'HLT_PFHT600',
  'HLT_PFHT650',
  'HLT_PFHT800',
  'HLT_PFHT900',
  'HLT_PFHT180',
  'HLT_PFHT370',
  'HLT_PFHT430',
  'HLT_PFHT510',
  'HLT_PFHT590',
  'HLT_PFHT680',
  'HLT_PFHT780',
  'HLT_PFHT890',
  'HLT_PFHT1050',
  'HLT_PFHT250',
  'HLT_PFHT350',
]


# ------------------------------------------------------------
# Parse original process_nano command
# ------------------------------------------------------------

print("DEBUG CHECKER: before parsing process_nano command")

command = job_argument_string.split('--command="')[1].split('"')[0]

command_args = command.split()


input_file = command_args[
  command_args.index("-f") + 1
]

input_dir = command_args[
  command_args.index("-i") + 1
]

print("DEBUG CHECKER: command =", repr(command))
print("DEBUG CHECKER: input_file =", repr(input_file))
print("DEBUG CHECKER: input_dir =", repr(input_dir))


# ------------------------------------------------------------
# Build remote input path
#
# Writer gives:
#
# -f UUID.root
# -i /store/data/Run2023D/.../
#
# Checker reads the NanoAOD again through global XRootD.
# ------------------------------------------------------------

input_redirector = "root://cms-xrd-global.cern.ch/"

infile_path = (
  input_redirector
  + input_dir
  + input_file
)

print("DEBUG CHECKER: infile_path =", repr(infile_path))


# ------------------------------------------------------------
# Build remote output path
#
# connect_condor_queue.py already transferred the pico to:
#
# /store/user/sucho/out_zgamma/raw_pico/
# ------------------------------------------------------------

output_redirector = "root://cluster142.knu.ac.kr:1094/"

outfile_path = (
  output_redirector
  + "/store/user/sucho/out_zgamma/raw_pico/"
  + "raw_pico_"
  + input_file
)

print("DEBUG CHECKER: outfile_path =", repr(outfile_path))


# ------------------------------------------------------------
# Read --nent if specified
# ------------------------------------------------------------

nent = None

if "--nent" in command_args:

  nent = int(
    command_args[
      command_args.index("--nent") + 1
    ]
  )


print("DEBUG: input  = {}".format(infile_path))
print("DEBUG: output = {}".format(outfile_path))
print("DEBUG: nent   = {}".format(nent))


# ------------------------------------------------------------
# Open NanoAOD
#
# Keep TChain for the same file/branch validation and GetEntries()
# behavior as the original checker.
# ------------------------------------------------------------

print("DEBUG CHECKER: before TChain(Events)")
infile = TChain("Events")
print("DEBUG CHECKER: after TChain(Events)")

print("DEBUG CHECKER: before infile.Add")
infile.Add(infile_path)
print("DEBUG CHECKER: after infile.Add")


# Check that input ROOT file was opened correctly.
print("DEBUG CHECKER: before infile.GetNbranches")
if infile.GetNbranches() == 0:

  print(
    '[For queue_system] fail: '
    'input ({}) has no branches.'
    .format(infile_path)
  )

  sys.exit(0)

print("DEBUG CHECKER: after infile.GetNbranches")


print("DEBUG CHECKER: before infile.GetEntries")
total_input_entries = infile.GetEntries()
print("DEBUG CHECKER: after infile.GetEntries")
print("DEBUG CHECKER: total_input_entries =", total_input_entries)


# process_nano with --nent only processes the first N events.
if nent is None:

  entries_to_check = total_input_entries

else:

  entries_to_check = min(
    nent,
    total_input_entries
  )


print(
  "DEBUG: total input entries = {}".format(
    total_input_entries
  )
)

print(
  "DEBUG: entries to check    = {}".format(
    entries_to_check
  )
)


# ------------------------------------------------------------
# Determine whether this is data
# ------------------------------------------------------------

is_data = "/store/data/" in input_dir

print("DEBUG CHECKER: is_data =", is_data)


# ------------------------------------------------------------
# Count expected pico entries
#
# DATA:
#   Use ROOT::RDataFrame so that the event loop, trigger decisions,
#   overlap removal, and Golden JSON check run in C++.
#
# MC:
#   Same behavior as the original checker: no Golden JSON filtering.
# ------------------------------------------------------------

in_nent = 0


if is_data:

  print("DEBUG CHECKER: preparing RDataFrame")

  # Build the dataframe from the already-created TChain.
  # infile must stay alive until Count() finishes.
  df = ROOT.RDataFrame(infile)

  # IMPORTANT:
  # Range must be applied BEFORE any physics filters.
  #
  # This reproduces the original:
  #
  #   for i in range(entries_to_check):
  #
  # and therefore --nent means "inspect the first N input events",
  # not "keep the first N events that pass the filters".
  if entries_to_check < total_input_entries:

    print(
      "DEBUG CHECKER: applying RDataFrame Range({})"
      .format(entries_to_check)
    )

    df = df.Range(entries_to_check)


  print("DEBUG CHECKER: getting available columns")

  available_columns = {
    str(column_name)
    for column_name in df.GetColumnNames()
  }

  print(
    "DEBUG CHECKER: number of RDataFrame columns =",
    len(available_columns)
  )


  # ----------------------------------------------------------
  # Build trigger OR expressions using only branches that
  # actually exist in this NanoAOD.
  #
  # This reproduces the original hasattr(chain, trigger_name)
  # behavior.
  # ----------------------------------------------------------

  met_expr, available_met_triggers = MakeTriggerExpression(
    available_columns,
    met_triggers
  )

  egamma_expr, available_egamma_triggers = MakeTriggerExpression(
    available_columns,
    egamma_triggers
  )

  doubleeg_expr, available_doubleeg_triggers = MakeTriggerExpression(
    available_columns,
    doubleeg_triggers
  )

  muon_expr, available_muon_triggers = MakeTriggerExpression(
    available_columns,
    muon_triggers
  )

  jetht_expr, available_jetht_triggers = MakeTriggerExpression(
    available_columns,
    jetht_triggers
  )


  print(
    "DEBUG CHECKER: available MET triggers =",
    available_met_triggers
  )

  print(
    "DEBUG CHECKER: available EGamma triggers =",
    available_egamma_triggers
  )

  print(
    "DEBUG CHECKER: available DoubleEG triggers =",
    available_doubleeg_triggers
  )

  print(
    "DEBUG CHECKER: available Muon triggers =",
    available_muon_triggers
  )

  print(
    "DEBUG CHECKER: available JetHT triggers =",
    available_jetht_triggers
  )


  # Define one boolean per trigger group.
  #
  # The strings are valid C++ expressions and are JIT-compiled by ROOT.
  df = (
    df
    .Define("checker_pass_met_trigger", met_expr)
    .Define("checker_pass_egamma_trigger", egamma_expr)
    .Define("checker_pass_doubleeg_trigger", doubleeg_expr)
    .Define("checker_pass_muon_trigger", muon_expr)
    .Define("checker_pass_jetht_trigger", jetht_expr)
  )


  # ----------------------------------------------------------
  # Trigger overlap removal
  #
  # Keep exactly the same logic as the original Python loop.
  # ----------------------------------------------------------

  if "MET" in infile_path:

    print("DEBUG CHECKER: applying MET trigger selection")

    df = df.Filter(
      "checker_pass_met_trigger",
      "MET dataset trigger selection"
    )


  if (
    "SingleElectron" in infile_path
    or "EGamma" in infile_path
  ):

    print("DEBUG CHECKER: applying EGamma trigger overlap removal")

    df = df.Filter(
      "("
      "checker_pass_egamma_trigger"
      " || checker_pass_doubleeg_trigger"
      ")"
      " && !checker_pass_muon_trigger",
      "EGamma dataset trigger overlap removal"
    )

    # NOTE:
    # The original checker intentionally has:
    #
    #   # or pass_met_trigger
    #
    # commented out. Keep the same behavior here.


  if "SingleMuon" in infile_path:

    print("DEBUG CHECKER: applying SingleMuon trigger overlap removal")

    df = df.Filter(
      "checker_pass_muon_trigger"
      " && !checker_pass_egamma_trigger"
      " && !checker_pass_met_trigger",
      "SingleMuon dataset trigger overlap removal"
    )


  if "JetHT" in infile_path:

    print("DEBUG CHECKER: applying JetHT trigger overlap removal")

    df = df.Filter(
      "checker_pass_jetht_trigger"
      " && !checker_pass_muon_trigger"
      " && !checker_pass_egamma_trigger"
      " && !checker_pass_met_trigger",
      "JetHT dataset trigger overlap removal"
    )


  # ----------------------------------------------------------
  # Golden JSON
  #
  # Parsing was done once in Python. The actual per-event
  # PassGoldenJson(run, luminosityBlock) call executes in C++.
  # ----------------------------------------------------------

  if (
    "run" not in available_columns
    or "luminosityBlock" not in available_columns
  ):

    print(
      '[For queue_system] fail: '
      'input ({}) is missing run and/or luminosityBlock.'
      .format(infile_path)
    )

    sys.exit(0)


  golden_json.declare_cpp_filter()

  print("DEBUG CHECKER: applying Golden JSON filter")

  df = df.Filter(
    "checker_rdf::PassGoldenJson(run, luminosityBlock)",
    "Golden JSON"
  )


  # ----------------------------------------------------------
  # Trigger the single RDataFrame event loop.
  #
  # Transformations above are lazy. Count().GetValue() actually
  # starts the event loop.
  # ----------------------------------------------------------

  print("DEBUG CHECKER: starting RDataFrame event loop")

  count_result = df.Count()
  in_nent = int(count_result.GetValue())

  print("DEBUG CHECKER: finished RDataFrame event loop")
  print("DEBUG CHECKER: in_nent after RDataFrame =", in_nent)


else:

  # MC has no Golden JSON filtering here.
  in_nent = entries_to_check

  print("DEBUG CHECKER: MC input, in_nent =", in_nent)


# ------------------------------------------------------------
# Open processed pico from KNU storage
# ------------------------------------------------------------

print("DEBUG CHECKER: before TChain(tree)")
outfile = TChain("tree")
print("DEBUG CHECKER: after TChain(tree)")

print("DEBUG CHECKER: before outfile.Add")
outfile.Add(outfile_path)
print("DEBUG CHECKER: after outfile.Add")


print("DEBUG CHECKER: before outfile.GetNbranches")
if outfile.GetNbranches() == 0:

  print(
    '[For queue_system] fail: '
    'output ({}) has no branches.'
    .format(outfile_path)
  )

  sys.exit(0)

print("DEBUG CHECKER: after outfile.GetNbranches")


print("DEBUG CHECKER: before outfile.GetEntries")
out_nent = outfile.GetEntries()
print("DEBUG CHECKER: after outfile.GetEntries")
print("DEBUG CHECKER: out_nent =", out_nent)


# ------------------------------------------------------------
# Print validation result
# ------------------------------------------------------------

print(
  "DEBUG: expected input entries = {}".format(
    in_nent
  )
)

print(
  "DEBUG: output pico entries    = {}".format(
    out_nent
  )
)


# ------------------------------------------------------------
# Final result for queue_system
# ------------------------------------------------------------

print("DEBUG CHECKER: before final success/fail decision")

if in_nent == out_nent:

  print('[For queue_system] success')


else:

  print(
    '[For queue_system] fail: '
    'Input ({}) has {} expected entries, '
    'while output ({}) has {} entries.'
    .format(
      infile_path,
      in_nent,
      outfile_path,
      out_nent
    )
  )

print("DEBUG CHECKER: finished")

