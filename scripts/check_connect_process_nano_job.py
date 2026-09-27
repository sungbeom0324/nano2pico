#!/usr/bin/env python3

import os
import sys
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
# ------------------------------------------------------------

class GoldenJson:

  # key   : run number
  # value : [(start_lumi, end_lumi), ...]
  good_lumi_blocks = {}

  def __init__(self):

    print("DEBUG CHECKER: GoldenJson init started")

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
    print("DEBUG CHECKER: number of runs in GoldenJson =", len(self.good_lumi_blocks))


  def check(self, run, lumi_block):

    if run in self.good_lumi_blocks:

      for lumi_range in self.good_lumi_blocks[run]:

        if (
          lumi_block >= lumi_range[0]
          and lumi_block <= lumi_range[1]
        ):
          return True

    return False


# ------------------------------------------------------------
# Trigger helper
# ------------------------------------------------------------

def CheckPassTriggers(chain, trigger_list):

  r_check_pass_triggers = False

  for trigger_name in trigger_list:

    if hasattr(chain, trigger_name):

      r_check_pass_triggers = (
        r_check_pass_triggers
        or getattr(chain, trigger_name)
      )

  return r_check_pass_triggers


print("DEBUG CHECKER: before GoldenJson()")
golden_json = GoldenJson()
print("DEBUG CHECKER: after GoldenJson()")


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
  #'HLT_Ele20_eta2p1_WPTight_Gsf',
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

doublemuon_triggers = [
  'HLT_Mu17_TrkIsoVVL_Mu8_TrkIsoVVL',
  'HLT_Mu17_TrkIsoVVL_TkMu8_TrkIsoVVL',
  'HLT_Mu17_TrkIsoVVL_Mu8_TrkIsoVVL_DZ',
  'HLT_Mu17_TrkIsoVVL_TkMu8_TrkIsoVVL_DZ',
  'HLT_Mu17_TrkIsoVVL_Mu8_TrkIsoVVL_DZ_Mass3p8',
  'HLT_Mu17_TrkIsoVVL_Mu8_TrkIsoVVL_DZ_Mass8',
  'HLT_Mu37_TkMu27',
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
# ------------------------------------------------------------

in_nent = 0


if is_data:

  print("DEBUG CHECKER: starting input event loop")

  for i in range(entries_to_check):

    if i % 1000 == 0:
      print("DEBUG CHECKER: checking input event", i)

    infile.GetEntry(i)

    # Trigger decisions
    pass_met_trigger = CheckPassTriggers(infile, met_triggers)
    pass_egamma_trigger = CheckPassTriggers(infile, egamma_triggers)
    pass_doubleeg_trigger = CheckPassTriggers(infile, doubleeg_triggers)
    pass_muon_trigger = CheckPassTriggers(infile, muon_triggers)
    pass_doublemuon_trigger = CheckPassTriggers(infile, doublemuon_triggers)
    pass_jetht_trigger = CheckPassTriggers(infile, jetht_triggers)

    # --------------------------------------------------------
    # Trigger overlap removal
    # --------------------------------------------------------

    if (
      "MET" in infile_path
      and not pass_met_trigger
    ):
      continue


    if (
      (
        "SingleElectron" in infile_path
        or "EGamma" in infile_path
      )
      and (
        not (pass_egamma_trigger or pass_doubleeg_trigger)
        or (pass_muon_trigger or doublemuon_triggers)
        # or pass_met_trigger
      )
    ):
      continue


    if (
      "SingleMuon" in infile_path
      and (
        not pass_muon_trigger
        or pass_egamma_trigger
        or pass_met_trigger
      )
    ):
      continue


    if (
      "JetHT" in infile_path
      and (
        not pass_jetht_trigger
        or pass_muon_trigger
        or pass_egamma_trigger
        or pass_met_trigger
      )
    ):
      continue


    # --------------------------------------------------------
    # Golden JSON
    # --------------------------------------------------------

    if golden_json.check(
      infile.run,
      infile.luminosityBlock
    ):
      in_nent += 1

  print("DEBUG CHECKER: finished input event loop")
  print("DEBUG CHECKER: in_nent after event loop =", in_nent)


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
