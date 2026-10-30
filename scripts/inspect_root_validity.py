#!/usr/bin/env python3
"""Read pico ROOT files and log abnormalities, without modifying input files.

Usage: python inspect_root_validity.py DIRECTORY [Run2024 | '*Run2024*']
Requires PyROOT (source set_env.sh first). Exit codes: 0 clean, 1 abnormal,
2 setup error, 130 interrupted. Empty trees are reported as abnormal.
Levels: 1 metadata only, 2 first entry (default), 3 all entries.
"""

import argparse
import fnmatch
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def inspect(path, tree_name, level=2):
    import ROOT

    ROOT.gROOT.SetBatch(True)
    handle = ROOT.TFile.Open(str(path), "READ")
    if not handle or handle.IsZombie():
        raise RuntimeError("Cannot open file, or file is a zombie")
    try:
        if handle.TestBit(ROOT.TFile.kRecovered):
            raise RuntimeError("ROOT recovered the file; it was not closed cleanly")
        tree = handle.Get(tree_name)
        if not tree or not tree.InheritsFrom("TTree"):
            raise RuntimeError("Missing TTree: " + tree_name)
        if tree.GetListOfBranches().GetEntries() == 0:
            raise RuntimeError("Tree has no branches")
        entries = int(tree.GetEntries())
        if entries <= 0:
            raise RuntimeError("Tree has no entries")
        if level == 1:
            return
        ROOT.gInterpreter.Declare(r'''
            Long64_t inspect_root_read(TTree *tree, bool full) {
                tree->SetBranchStatus("*", 1);
                const Long64_t entries = tree->GetEntries();
                const Long64_t count = full ? entries : 1;
                for (Long64_t i = 0; i < count; ++i) {
                    if (tree->GetEntry(i) <= 0) return i;
                }
                return -1;
            }
        ''')
        bad_entry = int(ROOT.inspect_root_read(tree, level == 3))
        if bad_entry >= 0:
            raise RuntimeError("Failed to read entry {} of {}".format(bad_entry, entries))
    finally:
        handle.Close()


def positive_timeout(value):
    value = float(value)
    if value <= 0:
        raise argparse.ArgumentTypeError("timeout must be positive")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("directory", type=Path)
    parser.add_argument("patterns", nargs="*", help="Filename substrings or quoted glob patterns (OR)")
    parser.add_argument("--log", type=Path, help="Abnormal-only JSON-lines log (default: timestamped log in cwd)")
    parser.add_argument("--tree", default="tree", help="Expected TTree name (default: tree)")
    parser.add_argument("--level", "-level", type=int, choices=(1, 2, 3), default=2,
                        help="1: metadata only; 2: first entry (default); 3: all entries")
    parser.add_argument("--timeout", type=positive_timeout, default=3600,
                        help="Seconds allowed per file (default: 3600)")
    parser.add_argument("--recursive", action="store_true")
    args = parser.parse_args()
    directory = args.directory.expanduser().resolve()
    if not directory.is_dir():
        parser.error("Not a directory: " + str(directory))
    patterns = [p if any(c in p for c in "*?[") else "*" + p + "*"
                for p in args.patterns]
    try:
        files = sorted(p for p in (directory.rglob("*.root") if args.recursive
                                  else directory.glob("*.root"))
                       if p.is_file() and (not patterns or
                          any(fnmatch.fnmatchcase(p.name, pat) for pat in patterns)))
    except OSError as exc:
        parser.error(str(exc))
    if not files:
        parser.error("No matching .root files")
    # Check the environment once, before potentially thousands of workers.
    probe = subprocess.run([sys.executable, "-c", "import ROOT"],
                           capture_output=True, text=True)
    if probe.returncode:
        parser.error("PyROOT is unavailable. Source your ROOT/CMSSW environment first.\n" + probe.stderr)
    log_path = (args.log or Path("abnormal_root_" + time.strftime("%Y%m%d_%H%M%S") + ".jsonl")).resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    abnormal = 0
    checked = 0
    started = time.monotonic()
    scan = {1: "metadata only", 2: "first entry only",
            3: "full entry scan"}[args.level]
    print("Checking {} files; tree={}; level={}; {}".format(
        len(files), args.tree, args.level, scan), flush=True)
    print("Abnormal log: " + str(log_path), flush=True)
    try:
        # Exclusive creation protects results from previous runs.
        with log_path.open("x", buffering=1) as log:
            for path in files:
                reason = None
                try:
                    before = path.stat()
                except OSError as exc:
                    checked += 1
                    abnormal += 1
                    log.write(json.dumps({"file": str(path), "reason": str(exc),
                                          "diagnostics": ""}) + "\n")
                    log.flush()
                    print("ABNORMAL: {}: {}".format(path, exc), flush=True)
                    continue
                with tempfile.TemporaryFile(mode="w+") as diagnostics:
                    try:
                        result = subprocess.run(
                            [sys.executable, str(Path(__file__).resolve()), "--worker", str(path),
                             args.tree, str(args.level)],
                            stdout=diagnostics, stderr=subprocess.STDOUT, timeout=args.timeout)
                        if result.returncode:
                            reason = "Worker exited with code {}".format(result.returncode)
                    except subprocess.TimeoutExpired:
                        reason = "Timed out after {} seconds".format(args.timeout)
                    diagnostics.seek(0)
                    output = diagnostics.read()
                # ROOT can report damaged baskets without a Python exception.
                if reason is None and any(token in output for token in
                                          ("Error in <", "Fatal in <", "SysError in <")):
                    reason = "ROOT reported an error while reading"
                try:
                    after = path.stat()
                    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                        reason = "File changed during inspection; rerun when writing has finished"
                except OSError as exc:
                    reason = "File disappeared or became inaccessible: " + str(exc)
                checked += 1
                if reason:
                    abnormal += 1
                    log.write(json.dumps({"file": str(path), "reason": reason,
                                          "diagnostics": output}, ensure_ascii=True) + "\n")
                    log.flush()
                    print("ABNORMAL: {}: {}".format(path, reason), flush=True)
                if checked % 10 == 0 or checked == len(files):
                    print("Progress {}/{}; abnormal={}; elapsed={:.0f}s".format(
                        checked, len(files), abnormal, time.monotonic() - started), flush=True)
    except KeyboardInterrupt:
        print("Interrupted after {} files; {} abnormal. Log saved: {}".format(
            checked, abnormal, log_path), flush=True)
        return 130
    except OSError as exc:
        print("Scan failed: " + str(exc), file=sys.stderr)
        return 2
    print("Finished: {} checked, {} abnormal. Log: {}".format(checked, abnormal, log_path), flush=True)
    return 1 if abnormal else 0


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--worker":
        try:
            inspect(Path(sys.argv[2]), sys.argv[3], int(sys.argv[4]))
        except Exception as exc:
            print("{}: {}".format(type(exc).__name__, exc), file=sys.stderr)
            sys.exit(1)
    else:
        sys.exit(main())
