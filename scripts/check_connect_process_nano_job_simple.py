#!/usr/bin/env python3

import sys
import ROOT
import queue_system


print("DEBUG SIMPLE CHECKER: started")


# ------------------------------------------------------------
# Get information from queue_system
# ------------------------------------------------------------

job_log_string = queue_system.decompress_string(sys.argv[1])
job_argument_string = queue_system.decompress_string(sys.argv[2])

print(
  "DEBUG SIMPLE CHECKER: job_log_string length =",
  len(job_log_string)
)

print(
  "DEBUG SIMPLE CHECKER: job_argument_string =",
  repr(job_argument_string)
)


# ------------------------------------------------------------
# Parse original process_nano command
# ------------------------------------------------------------

try:

  command = (
    job_argument_string
    .split('--command="')[1]
    .split('"')[0]
  )

except IndexError:

  print(
    '[For queue_system] fail: '
    'could not parse process_nano command.'
  )

  sys.exit(0)


command_args = command.split()


try:

  input_file = command_args[
    command_args.index("-f") + 1
  ]

  input_dir = command_args[
    command_args.index("-i") + 1
  ]

except (ValueError, IndexError):

  print(
    '[For queue_system] fail: '
    'could not find -f or -i in process_nano command.'
  )

  sys.exit(0)


print("DEBUG SIMPLE CHECKER: command    =", repr(command))
print("DEBUG SIMPLE CHECKER: input_file =", repr(input_file))
print("DEBUG SIMPLE CHECKER: input_dir  =", repr(input_dir))


# ------------------------------------------------------------
# Check that process_nano finished
# ------------------------------------------------------------

if "[Info] command_divider : End divided_command" not in job_log_string:

  print(
    '[For queue_system] fail: '
    'process_nano did not finish normally.'
  )

  sys.exit(0)


print(
  "DEBUG SIMPLE CHECKER: "
  "process_nano finished"
)


# ------------------------------------------------------------
# Check that output transfer finished
# ------------------------------------------------------------

if (
  "[Info] command_divider : Transfer done"
  not in job_log_string
):

  print(
    '[For queue_system] fail: '
    'processed pico transfer did not finish.'
  )

  sys.exit(0)


print(
  "DEBUG SIMPLE CHECKER: "
  "output transfer finished"
)


# ------------------------------------------------------------
# Parse CMS data path
#
# Example:
#
# /store/data/Run2018C/DoubleMuon/NANOAOD/
#   UL2018_MiniAODv2_NanoAODv9-v1/130000/
#
# or
#
# ./store/data/Run2024C/EGamma0/NANOAOD/
#   PromptReco-v1/000/379/454/00000/
#
# process_nano --connect output:
#
# raw_pico_<dataset>__<era>__<campaign>__<input_file>
# ------------------------------------------------------------

normalized_input_dir = input_dir

if normalized_input_dir.startswith("./"):
  normalized_input_dir = normalized_input_dir[2:]


path_parts = (
  normalized_input_dir
  .strip("/")
  .split("/")
)


try:

  store_index = path_parts.index("store")

  if path_parts[store_index + 1] != "data":
    raise ValueError

  era = path_parts[store_index + 2]
  dataset = path_parts[store_index + 3]

  if path_parts[store_index + 4] != "NANOAOD":
    raise ValueError

  campaign = path_parts[store_index + 5]


except (ValueError, IndexError):

  print(
    '[For queue_system] fail: '
    'unexpected CMSConnect input path: {}'
    .format(input_dir)
  )

  sys.exit(0)


print("DEBUG SIMPLE CHECKER: era      =", era)
print("DEBUG SIMPLE CHECKER: dataset  =", dataset)
print("DEBUG SIMPLE CHECKER: campaign =", campaign)


# ------------------------------------------------------------
# Build output filename
# ------------------------------------------------------------

connect_output_file = (
  dataset
  + "__"
  + era
  + "__"
  + campaign
  + "__"
  + input_file
)


output_redirector = (
  "root://cluster142.knu.ac.kr:1094/"
)

output_directory = (
  "/store/user/sucho/out_zgamma/raw_pico/"
)


outfile_path = (
  output_redirector
  + output_directory
  + "raw_pico_"
  + connect_output_file
)


print(
  "DEBUG SIMPLE CHECKER: outfile_path =",
  repr(outfile_path)
)


# ------------------------------------------------------------
# Open remote ROOT file
# ------------------------------------------------------------

print(
  "DEBUG SIMPLE CHECKER: opening output ROOT file"
)

outfile = ROOT.TFile.Open(outfile_path)


if not outfile:

  print(
    '[For queue_system] fail: '
    'could not open output ROOT file ({}).'
    .format(outfile_path)
  )

  sys.exit(0)


if outfile.IsZombie():

  print(
    '[For queue_system] fail: '
    'output ROOT file ({}) is a zombie.'
    .format(outfile_path)
  )

  outfile.Close()

  sys.exit(0)


print(
  "DEBUG SIMPLE CHECKER: "
  "ROOT file opened successfully"
)


# ------------------------------------------------------------
# Check tree
# ------------------------------------------------------------

tree = outfile.Get("tree")


if not tree:

  print(
    '[For queue_system] fail: '
    'output ({}) does not contain tree.'
    .format(outfile_path)
  )

  outfile.Close()

  sys.exit(0)


if not tree.InheritsFrom("TTree"):

  print(
    '[For queue_system] fail: '
    'object named tree in output ({}) is not a TTree.'
    .format(outfile_path)
  )

  outfile.Close()

  sys.exit(0)


print(
  "DEBUG SIMPLE CHECKER: "
  "tree found"
)


# ------------------------------------------------------------
# Check branches
# ------------------------------------------------------------

nbranches = tree.GetNbranches()


print(
  "DEBUG SIMPLE CHECKER: "
  "number of branches =",
  nbranches
)


if nbranches == 0:

  print(
    '[For queue_system] fail: '
    'tree in output ({}) has no branches.'
    .format(outfile_path)
  )

  outfile.Close()

  sys.exit(0)


# ------------------------------------------------------------
# Print number of entries
#
# NOTE:
# Zero entries are allowed in the simple checker.
# We only verify that a valid pico tree was produced.
# ------------------------------------------------------------

nent = tree.GetEntries()

print(
  "DEBUG SIMPLE CHECKER: "
  "number of entries =",
  nent
)


outfile.Close()


# ------------------------------------------------------------
# Success
# ------------------------------------------------------------

print('[For queue_system] success')

print("DEBUG SIMPLE CHECKER: finished")
