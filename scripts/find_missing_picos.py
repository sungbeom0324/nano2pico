#!/usr/bin/env python3
"""Find input ROOT files whose UUIDs are absent from a pico file listing."""

import argparse
from collections import Counter
from pathlib import Path
import re
import subprocess


UUID = re.compile(
    r"(?<![0-9a-f])[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}(?=\.root\b)",
    re.IGNORECASE,
)


def parse_entries(lines, source):
    """Read all entries, failing on malformed lines rather than skipping them."""
    entries = []
    for number, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        matches = UUID.findall(line)
        if len(matches) != 1:
            raise ValueError("{}:{}: expected one ROOT-file UUID".format(source, number))
        entries.append((line, matches[0].lower()))
    return entries


def read_entries(path):
    with path.open() as listing:
        return parse_entries(listing, path)


def read_remote_entries(server, directory, recursive):
    command = ["xrdfs", server, "ls"]
    if recursive:
        command.append("-R")
    command.append(directory)
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True)
    if result.returncode:
        raise ValueError("xrdfs listing failed (exit {}): {}".format(
            result.returncode, result.stderr.strip() or "no error details"))
    roots = [line.strip() for line in result.stdout.splitlines()
             if line.strip().endswith(".root")]
    return parse_entries(roots, "{} {}".format(server, directory))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--filelist", type=Path, default=Path("filelist_2024.txt"))
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--picolist", type=Path,
                        help="Local pico listing (default: picolist.txt)")
    source.add_argument("--server", help="XRootD server, including port (e.g. host:1094)")
    parser.add_argument("--directory", help="Remote pico directory; requires --server")
    parser.add_argument("--recursive", action="store_true",
                        help="Include remote subdirectories; requires --server")
    parser.add_argument("--output", type=Path, default=Path("missing_Run2024.txt"))
    args = parser.parse_args()
    if args.server and not args.directory:
        parser.error("--server requires --directory")
    if not args.server and (args.directory or args.recursive):
        parser.error("--directory and --recursive require --server")
    picolist = args.picolist or Path("picolist.txt")
    try:
        inputs = read_entries(args.filelist)
        picos = (read_remote_entries(args.server, args.directory, args.recursive)
                 if args.server else read_entries(picolist))
        if not inputs:
            raise ValueError("no input entries in {}".format(args.filelist))
        input_paths = [args.filelist.resolve()]
        if not args.server:
            input_paths.append(picolist.resolve())
        if args.output.resolve() in input_paths:
            raise ValueError("output must differ from the input listings")
        output_ids = {uuid for _, uuid in picos}
        missing = [line for line, uuid in inputs if uuid not in output_ids]
        args.output.write_text("".join(line + "\n" for line in missing))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    input_ids = {uuid for _, uuid in inputs}
    print("Input entries: {} ({} unique UUIDs)".format(len(inputs), len(input_ids)))
    print("Pico entries: {} ({} unique UUIDs)".format(len(picos), len(output_ids)))
    print("Matched input UUIDs: {}".format(len(input_ids & output_ids)))
    print("Missing input files: {} -> {}".format(len(missing), args.output))
    counts = Counter(re.search(r"/store/data/([^/]+)/([^/]+)/", line).groups()
                     if re.search(r"/store/data/([^/]+)/([^/]+)/", line)
                     else ("other", "other") for line in missing)
    for (run, dataset), count in sorted(counts.items()):
        print("  {}/{}: {}".format(run, dataset, count))


if __name__ == "__main__":
    main()
