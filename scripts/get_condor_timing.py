#!/usr/bin/env python3

import argparse
import csv
import json
import re
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path


# ============================================================
# Regular expressions / markers
# ============================================================

TIMING_RE = re.compile(
    r"\[Timing\]\s+([A-Za-z0-9_]+)=([0-9]+(?:\.[0-9]+)?)"
)

START_CMD_RE = re.compile(
    r"Start divided_command\[(\d+)\]"
)

END_CMD_RE = re.compile(
    r"End divided_command(?:\[(\d+)\])?"
)

EVENT_RE = re.compile(
    r"^\s*(\d{3})\s+\((\d+)\.(\d+)\.\d+\)\s+"
    r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})"
)

RETURN_RE = re.compile(
    r"Normal termination \(return value\s+(-?\d+)\)"
)

DOWNLOAD_DONE_MARKER = "[Info] Copy done from Rucio."
TRANSFER_DONE_MARKER = "[Info] command_divider : Transfer done"


# ============================================================
# Arguments
# ============================================================

def parse_args():

    parser = argparse.ArgumentParser(
        description="Summarize Nano2Pico/HTCondor timing and final-trial logs."
    )

    parser.add_argument(
        "job_id",
        nargs="?",
        default=None,
        help=(
            "Cluster ID or CLUSTER.PROC. "
            "Example: 1416567 or 1416567.318. "
            "Not needed with --jobs-json."
        ),
    )

    parser.add_argument(
        "--jobs-json",
        default=None,
        help=(
            "Nano2Pico auto_process_nano_cmds.json. "
            "Analyze the final job_identifier of each logical job."
        ),
    )

    parser.add_argument(
        "--dir",
        default=".",
        help="Directory containing Condor logs.",
    )

    parser.add_argument(
        "--csv",
        default=None,
        help="Optional output CSV filename.",
    )

    parser.add_argument(
        "--plot",
        action="store_true",
        help="Save timing distribution histograms.",
    )

    parser.add_argument(
        "--plot-dir",
        default=None,
        help="Directory for timing plots.",
    )

    parser.add_argument(
        "--no-table",
        action="store_true",
        help="Do not print the per-job table.",
    )

    parser.add_argument(
        "--failed-log-list",
        default="failed_nano_logs.txt",
        help=(
            "Output text file containing final stdout logs for "
            "Nano2Pico jobs whose job_status is fail."
        ),
    )

    args = parser.parse_args()

    if args.jobs_json is None and args.job_id is None:
        parser.error("Provide either job_id or --jobs-json.")

    if args.jobs_json is not None and args.job_id is not None:
        parser.error("Use either job_id or --jobs-json, not both.")

    return args


# ============================================================
# Job ID parsing
# ============================================================

def split_job_id(text):

    m = re.fullmatch(r"(\d+)(?:\.(\d+))?", text)

    if not m:
        raise ValueError(f"Invalid Condor job ID: {text}")

    cluster = m.group(1)
    proc = int(m.group(2)) if m.group(2) is not None else None

    return cluster, proc


def parse_nano_identifier(identifier):
    """
    Example:
        1421483.1407_0

    -> cluster = 1421483
    -> proc    = 1407
    -> suffix  = 0
    """

    if not identifier:
        return None

    m = re.fullmatch(
        r"(\d+)\.(\d+)(?:_(\d+))?",
        str(identifier),
    )

    if not m:
        return None

    return {
        "cluster": m.group(1),
        "proc": int(m.group(2)),
        "suffix": int(m.group(3)) if m.group(3) is not None else None,
    }


# ============================================================
# Log indexing
# ============================================================

def filename_job_id(path):
    """
    Examples:
        out.1416567.318.log
        log.1416567.318.log
    """

    m = re.match(
        r"^(?:out|log)\.(\d+)\.(\d+)(?:\..*)?$",
        path.name,
    )

    if not m:
        return None

    return m.group(1), int(m.group(2))


def build_log_index(base):
    """
    Recursively scan everything below --dir.

    key:
        (cluster, proc)

    value:
        list of matching out/log files
    """

    index = {}

    for path in base.rglob("*"):

        if not path.is_file():
            continue

        job_id = filename_job_id(path)

        if job_id is None:
            continue

        index.setdefault(job_id, []).append(path)

    for key in index:
        index[key] = sorted(index[key])

    return index


def candidate_files_cluster(log_index, cluster, requested_proc=None):

    result = {}

    for (c, proc), paths in log_index.items():

        if c != cluster:
            continue

        if requested_proc is not None and proc != requested_proc:
            continue

        result[proc] = paths

    return result


# ============================================================
# Nano2Pico JSON
# ============================================================

def load_nano_jobs(json_path):

    with open(json_path) as f:
        raw_jobs = json.load(f)

    logical_jobs = []
    missing_identifier = []

    for index, job in enumerate(raw_jobs):

        # Skip empty placeholder such as jobs[0] == {}
        if not job:
            continue

        identifier = job.get("job_identifier")
        parsed_id = parse_nano_identifier(identifier)

        if parsed_id is None:

            missing_identifier.append(
                {
                    "index": index,
                    "status": job.get("job_status"),
                    "identifier": identifier,
                }
            )

            continue

        logical_jobs.append(
            {
                "logical_index": index,
                "command": job.get("command", ""),
                "job_status": job.get("job_status"),
                "job_identifier": identifier,
                "job_trials": job.get("job_trials", []),
                "cluster": parsed_id["cluster"],
                "proc": parsed_id["proc"],
                "suffix": parsed_id["suffix"],
            }
        )

    return {
        "logical_jobs": logical_jobs,
        "missing_identifier": missing_identifier,
    }


# ============================================================
# Parse log
# ============================================================

def parse_file(path, cluster, proc):

    timings = {}

    start_commands = set()
    end_commands = set()

    download_done = False
    any_end_command = False
    transfer_done = False

    submit_times = []
    execute_times = []
    terminate_times = []

    return_value = None

    try:

        with path.open("r", errors="replace") as f:

            for line in f:

                # Wrapper timing
                mt = TIMING_RE.search(line)

                if mt:

                    key = mt.group(1)
                    value = float(mt.group(2))

                    timings.setdefault(key, []).append(value)

                # Rucio download completed
                if DOWNLOAD_DONE_MARKER in line:
                    download_done = True

                # divided_command start
                ms = START_CMD_RE.search(line)

                if ms:
                    start_commands.add(int(ms.group(1)))

                # divided_command end
                me_cmd = END_CMD_RE.search(line)

                if me_cmd:

                    any_end_command = True

                    if me_cmd.group(1) is not None:
                        end_commands.add(int(me_cmd.group(1)))

                # Workflow output transfer completed
                if TRANSFER_DONE_MARKER in line:
                    transfer_done = True

                # HTCondor events
                me = EVENT_RE.match(line)

                if me:

                    code = me.group(1)
                    line_cluster = me.group(2)
                    line_proc = int(me.group(3))

                    if line_cluster != cluster or line_proc != proc:
                        continue

                    dt = datetime.strptime(
                        f"{me.group(4)} {me.group(5)}",
                        "%Y-%m-%d %H:%M:%S",
                    )

                    if code == "000":
                        submit_times.append(dt)

                    elif code == "001":
                        execute_times.append(dt)

                    elif code == "005":
                        terminate_times.append(dt)

                # Condor return value
                mr = RETURN_RE.search(line)

                if mr:
                    return_value = int(mr.group(1))

    except OSError as exc:

        print(f"[WARN] Could not read {path}: {exc}")

    return {
        "timings": timings,

        "start_commands": start_commands,
        "end_commands": end_commands,

        "download_done": download_done,
        "any_end_command": any_end_command,
        "transfer_done": transfer_done,

        "submit_times": submit_times,
        "execute_times": execute_times,
        "terminate_times": terminate_times,

        "return_value": return_value,
    }


# ============================================================
# Merge out/log files
# ============================================================

def merge_parsed(items):

    merged = {
        "timings": {},

        "start_commands": set(),
        "end_commands": set(),

        "download_done": False,
        "any_end_command": False,
        "transfer_done": False,

        "submit_times": [],
        "execute_times": [],
        "terminate_times": [],

        "return_value": None,
    }

    for item in items:

        for key, vals in item["timings"].items():
            merged["timings"].setdefault(key, []).extend(vals)

        merged["start_commands"].update(item["start_commands"])
        merged["end_commands"].update(item["end_commands"])

        merged["download_done"] |= item["download_done"]
        merged["any_end_command"] |= item["any_end_command"]
        merged["transfer_done"] |= item["transfer_done"]

        merged["submit_times"].extend(item["submit_times"])
        merged["execute_times"].extend(item["execute_times"])
        merged["terminate_times"].extend(item["terminate_times"])

        if item["return_value"] is not None:
            merged["return_value"] = item["return_value"]

    for key in (
        "submit_times",
        "execute_times",
        "terminate_times",
    ):
        merged[key] = sorted(set(merged[key]))

    # out/log may contain duplicate timing lines.
    for key, vals in merged["timings"].items():

        if vals and len(set(vals)) == 1:
            merged["timings"][key] = [vals[0]]

    return merged


# ============================================================
# Utilities
# ============================================================

def first(vals):
    return min(vals) if vals else None


def last(vals):
    return max(vals) if vals else None


def timing_sum(timings, key):

    vals = timings.get(key, [])
    return sum(vals) if vals else None


def timing_first(timings, key):

    vals = timings.get(key, [])
    return vals[0] if vals else None


def timing_last(timings, key):

    vals = timings.get(key, [])
    return vals[-1] if vals else None


def seconds_between(a, b):

    if a is None or b is None:
        return None

    return (b - a).total_seconds()


def fmt_seconds(sec):

    if sec is None:
        return "N/A"

    sec = int(round(sec))

    sign = "-" if sec < 0 else ""
    sec = abs(sec)

    days, rem = divmod(sec, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)

    if days:
        return (
            f"{sign}{days}d "
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{seconds:02d}"
        )

    return (
        f"{sign}"
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{seconds:02d}"
    )


def fmt_datetime(dt):

    if dt is None:
        return "N/A"

    return dt.strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
# Final-trial log status
# ============================================================

def determine_log_status(
    terminate,
    return_value,
    download_done,
    process_finished,
    transfer_done,
):
    """
    This is only a log-level check.

    LOG_COMPLETE does NOT mean that the output ROOT file passed
    the Nano2Pico checker.
    """

    if terminate is None:
        return "NO_TERMINATION"

    if not download_done:
        return "DOWNLOAD_FAILED"

    if not process_finished:
        return "PROCESS_INCOMPLETE"

    if not transfer_done:
        return "TRANSFER_INCOMPLETE"

    if return_value is None:
        return "NO_RETURN_VALUE"

    if return_value != 0:
        return "NONZERO_RETURN"

    return "LOG_COMPLETE"


# ============================================================
# Build one job record
# ============================================================

def make_job_record(
    cluster,
    proc,
    parsed,
    paths,
    logical_job=None,
):

    timings = parsed["timings"]

    submit = first(parsed["submit_times"])
    execute = first(parsed["execute_times"])
    terminate = last(parsed["terminate_times"])

    job_start_epoch = timing_first(
        timings,
        "job_start_time",
    )

    job_end_epoch = timing_last(
        timings,
        "job_end_time",
    )

    wrapper_total = timing_last(
        timings,
        "job_total_sec",
    )

    if (
        wrapper_total is None
        and job_start_epoch is not None
        and job_end_epoch is not None
    ):
        wrapper_total = job_end_epoch - job_start_epoch

    download = timing_sum(
        timings,
        "download_sec",
    )

    process_nano = timing_sum(
        timings,
        "process_nano_sec",
    )

    transfer = timing_sum(
        timings,
        "transfer_sec",
    )

    divided_total = timing_sum(
        timings,
        "total_sec",
    )

    idle = seconds_between(
        submit,
        execute,
    )

    condor_run = seconds_between(
        execute,
        terminate,
    )

    submit_to_end = seconds_between(
        submit,
        terminate,
    )

    download_done = parsed["download_done"]
    process_finished = parsed["any_end_command"]
    transfer_done = parsed["transfer_done"]

    log_status = determine_log_status(
        terminate,
        parsed["return_value"],
        download_done,
        process_finished,
        transfer_done,
    )

    record = {
        "job": f"{cluster}.{proc}",

        "cluster": cluster,
        "proc": proc,

        "log_status": log_status,
        "return_value": parsed["return_value"],

        "download_done": download_done,
        "process_finished": process_finished,
        "transfer_done": transfer_done,

        "ncmd": (
            len(parsed["start_commands"])
            if parsed["start_commands"]
            else None
        ),

        "submit": submit,
        "execute": execute,
        "terminate": terminate,

        "idle": idle,
        "download": download,
        "process": process_nano,
        "transfer": transfer,

        "divided_total": divided_total,
        "wrapper_total": wrapper_total,

        "condor_run": condor_run,
        "submit_to_end": submit_to_end,

        "files": [str(p) for p in paths],

        # Nano2Pico JSON information
        "logical_index": None,
        "nano_status": None,
        "job_identifier": None,
        "n_trials": None,
        "command": None,
    }

    if logical_job is not None:

        record["logical_index"] = logical_job["logical_index"]
        record["nano_status"] = logical_job["job_status"]
        record["job_identifier"] = logical_job["job_identifier"]
        record["n_trials"] = len(logical_job["job_trials"])
        record["command"] = logical_job["command"]

    return record


# ============================================================
# Per-job table
# ============================================================

def print_table(records, json_mode=False):

    headers = []

    if json_mode:
        headers.extend(
            [
                ("Idx", 7),
                ("Trials", 6),
            ]
        )

    headers.extend(
        [
            ("Job", 16),
            ("LogStatus", 20),
            ("Ret", 5),
            ("Down", 5),
            ("Proc", 5),
            ("Tran", 5),
            ("Idle", 10),
            ("Download", 10),
            ("Process", 10),
            ("Transfer", 10),
            ("Wrapper", 10),
            ("Condor", 10),
        ]
    )

    header = " ".join(
        f"{name:<{width}}"
        for name, width in headers
    )

    print(header)
    print("-" * len(header))

    for r in records:

        values = []

        if json_mode:

            values.extend(
                [
                    (
                        str(r["logical_index"])
                        if r["logical_index"] is not None
                        else "N/A"
                    ),
                    (
                        str(r["n_trials"])
                        if r["n_trials"] is not None
                        else "N/A"
                    ),
                ]
            )

        values.extend(
            [
                r["job"],
                r["log_status"],

                (
                    str(r["return_value"])
                    if r["return_value"] is not None
                    else "N/A"
                ),

                "YES" if r["download_done"] else "NO",
                "YES" if r["process_finished"] else "NO",
                "YES" if r["transfer_done"] else "NO",

                fmt_seconds(r["idle"]),
                fmt_seconds(r["download"]),
                fmt_seconds(r["process"]),
                fmt_seconds(r["transfer"]),
                fmt_seconds(r["wrapper_total"]),
                fmt_seconds(r["condor_run"]),
            ]
        )

        print(
            " ".join(
                f"{value:<{width}}"
                for value, (_, width)
                in zip(values, headers)
            )
        )


# ============================================================
# Timing statistics
# ============================================================

def valid_values(records, key):

    return [
        r[key]
        for r in records
        if r[key] is not None
    ]


def print_stats(records, key, label):

    vals = valid_values(records, key)

    if not vals:
        print(f"{label:<18}: N/A")
        return

    print(
        f"{label:<18}: "
        f"mean {fmt_seconds(statistics.mean(vals))}"
        f" | median {fmt_seconds(statistics.median(vals))}"
        f" | min {fmt_seconds(min(vals))}"
        f" | max {fmt_seconds(max(vals))}"
    )


# ============================================================
# Log-status summary
# ============================================================

def print_log_status_summary(records):

    status_order = [
        ("LOG_COMPLETE", "Log complete"),
        ("DOWNLOAD_FAILED", "Download failed"),
        ("PROCESS_INCOMPLETE", "Process incomplete"),
        ("TRANSFER_INCOMPLETE", "Transfer incomplete"),
        ("NONZERO_RETURN", "Non-zero return"),
        ("NO_RETURN_VALUE", "No return value"),
        ("NO_TERMINATION", "No Condor termination"),
    ]

    counts = Counter(
        r["log_status"]
        for r in records
    )

    for key, label in status_order:

        print(
            f"{label:<22}: "
            f"{counts.get(key, 0)}"
        )


# ============================================================
# Timing summary
# ============================================================

def print_timing_summary(records):

    submits = [
        r["submit"]
        for r in records
        if r["submit"] is not None
    ]

    ends = [
        r["terminate"]
        for r in records
        if r["terminate"] is not None
    ]

    first_submit = min(submits) if submits else None
    last_end = max(ends) if ends else None

    print()
    print("Timing summary")
    print()

    print(
        f"First final submit  : "
        f"{fmt_datetime(first_submit)}"
    )

    print(
        f"Last termination    : "
        f"{fmt_datetime(last_end)}"
    )

    print(
        f"Final-job wall time : "
        f"{fmt_seconds(seconds_between(first_submit, last_end))}"
    )

    print()

    print_stats(records, "idle", "Idle")
    print_stats(records, "download", "Download")
    print_stats(records, "process", "process_nano")
    print_stats(records, "transfer", "Transfer")
    print_stats(records, "wrapper_total", "Wrapper total")
    print_stats(records, "condor_run", "Condor execute")
    print_stats(records, "submit_to_end", "Submit -> end")


# ============================================================
# Cluster-mode summary
# ============================================================

def print_cluster_summary(cluster, records):

    print()
    print(f"Cluster: {cluster}")
    print()

    print(
        f"Jobs found          : "
        f"{len(records)}"
    )

    print()
    print("Final-trial log check")
    print()

    print_log_status_summary(records)

    print_timing_summary(records)


# ============================================================
# Failed Nano2Pico log list
# ============================================================

def write_failed_nano_logs(
    records,
    output_file="failed_nano_logs.txt",
):

    failed_records = [
        r for r in records
        if r["nano_status"] == "fail"
    ]

    with open(output_file, "w") as f:

        for r in failed_records:

            # Prefer stdout log: out.<cluster>.<proc>.log
            out_files = [
                path
                for path in r["files"]
                if Path(path).name.startswith("out.")
            ]

            if out_files:

                for path in out_files:
                    f.write(f"{path}\n")

            else:

                # Fallback if stdout log is not available.
                for path in r["files"]:
                    f.write(f"{path}\n")

    print()
    print(
        f"Failed Nano2Pico jobs : "
        f"{len(failed_records)}"
    )

    print(
        f"Failed log list       : "
        f"{output_file}"
    )


# ============================================================
# JSON-mode summary
# ============================================================

def print_json_summary(
    nano_info,
    records,
    missing_logs,
    failed_log_list,
):

    logical_jobs = nano_info["logical_jobs"]

    # --------------------------------------------------------
    # Logical jobs / final logs
    # --------------------------------------------------------

    print()
    print("Nano2Pico logical jobs")
    print()

    print(
        f"Logical jobs        : "
        f"{len(logical_jobs)}"
    )

    print(
        f"Final logs found    : "
        f"{len(records)}/{len(logical_jobs)}"
    )

    print(
        f"Final logs missing  : "
        f"{len(missing_logs)}"
    )

    print(
        f"Missing identifier  : "
        f"{len(nano_info['missing_identifier'])}"
    )

    # --------------------------------------------------------
    # Trial history
    # --------------------------------------------------------

    trial_counts = Counter(
        len(j["job_trials"])
        for j in logical_jobs
    )

    total_trials = sum(
        len(j["job_trials"])
        for j in logical_jobs
    )

    retried_jobs = sum(
        len(j["job_trials"]) > 1
        for j in logical_jobs
    )

    print()
    print("Condor trial history")
    print()

    print(
        f"Total trials        : "
        f"{total_trials}"
    )

    print(
        f"Retried jobs        : "
        f"{retried_jobs}"
    )

    if logical_jobs:

        print(
            f"Mean trials/job     : "
            f"{total_trials / len(logical_jobs):.2f}"
        )

    print(
        f"Max trials/job      : "
        f"{max(trial_counts) if trial_counts else 0}"
    )

    print()
    print("Number of trials per logical job")

    for n in sorted(trial_counts):

        print(
            f"  {n:2d} trial(s)       : "
            f"{trial_counts[n]}"
        )

    # --------------------------------------------------------
    # Final Condor/log state
    # --------------------------------------------------------

    print()
    print("Final-trial log check")
    print()

    print_log_status_summary(records)

    # --------------------------------------------------------
    # Nano2Pico state recorded in JSON
    # --------------------------------------------------------

    nano_status = Counter(
        j["job_status"]
        for j in logical_jobs
    )

    print()
    print("Nano2Pico recorded state")
    print()

    for status, count in sorted(
        nano_status.items(),
        key=lambda x: str(x[0]),
    ):

        print(
            f"  {str(status):<18}: "
            f"{count}"
        )

    # --------------------------------------------------------
    # Timing
    # --------------------------------------------------------

    print_timing_summary(records)

    # --------------------------------------------------------
    # Missing final logs
    # --------------------------------------------------------

    if missing_logs:

        print()
        print("Missing final logs:")

        for job in missing_logs[:50]:

            print(
                f"  index={job['logical_index']:<6} "
                f"id={job['job_identifier']} "
                f"nano_status={job['job_status']}"
            )

        if len(missing_logs) > 50:

            print(
                f"  ... and "
                f"{len(missing_logs) - 50} more"
            )

    # --------------------------------------------------------
    # Invalid identifiers
    # --------------------------------------------------------

    if nano_info["missing_identifier"]:

        print()
        print("Missing/invalid job_identifier:")

        for item in nano_info["missing_identifier"][:50]:

            print(
                f"  index={item['index']} "
                f"status={item['status']} "
                f"id={item['identifier']}"
            )

    # --------------------------------------------------------
    # Save failed job logs to a separate text file
    # --------------------------------------------------------

    write_failed_nano_logs(
        records,
        failed_log_list,
    )


# ============================================================
# CSV
# ============================================================

def write_csv(path, records):

    fields = [
        "logical_index",
        "job",
        "cluster",
        "proc",

        "nano_status",
        "job_identifier",
        "n_trials",

        "log_status",
        "return_value",

        "download_done",
        "process_finished",
        "transfer_done",

        "ncmd",

        "submit",
        "execute",
        "terminate",

        "idle_sec",
        "download_sec",
        "process_nano_sec",
        "transfer_sec",

        "divided_total_sec",
        "wrapper_total_sec",

        "condor_run_sec",
        "submit_to_end_sec",

        "command",
        "files",
    ]

    with open(path, "w", newline="") as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields,
        )

        writer.writeheader()

        for r in records:

            writer.writerow(
                {
                    "logical_index":
                        r["logical_index"],

                    "job":
                        r["job"],

                    "cluster":
                        r["cluster"],

                    "proc":
                        r["proc"],

                    "nano_status":
                        r["nano_status"],

                    "job_identifier":
                        r["job_identifier"],

                    "n_trials":
                        r["n_trials"],

                    "log_status":
                        r["log_status"],

                    "return_value":
                        r["return_value"],

                    "download_done":
                        r["download_done"],

                    "process_finished":
                        r["process_finished"],

                    "transfer_done":
                        r["transfer_done"],

                    "ncmd":
                        r["ncmd"],

                    "submit":
                        (
                            fmt_datetime(r["submit"])
                            if r["submit"]
                            else ""
                        ),

                    "execute":
                        (
                            fmt_datetime(r["execute"])
                            if r["execute"]
                            else ""
                        ),

                    "terminate":
                        (
                            fmt_datetime(r["terminate"])
                            if r["terminate"]
                            else ""
                        ),

                    "idle_sec":
                        r["idle"],

                    "download_sec":
                        r["download"],

                    "process_nano_sec":
                        r["process"],

                    "transfer_sec":
                        r["transfer"],

                    "divided_total_sec":
                        r["divided_total"],

                    "wrapper_total_sec":
                        r["wrapper_total"],

                    "condor_run_sec":
                        r["condor_run"],

                    "submit_to_end_sec":
                        r["submit_to_end"],

                    "command":
                        r["command"],

                    "files":
                        ";".join(r["files"]),
                }
            )


# ============================================================
# Plots
# ============================================================

def save_timing_plots(
    records,
    label,
    output_dir,
):

    try:
        import matplotlib.pyplot as plt

    except ImportError:

        raise SystemExit(
            "Plotting requires matplotlib."
        )

    output_dir = Path(output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    plot_specs = [
        ("idle", "Idle", "idle.png"),
        ("download", "Download", "download.png"),
        ("process", "process_nano", "process_nano.png"),
        ("transfer", "Transfer", "transfer.png"),
        ("wrapper_total", "Wrapper total", "wrapper_total.png"),
        ("condor_run", "Condor execute", "condor_execute.png"),
        ("submit_to_end", "Submit -> end", "submit_to_end.png"),
    ]

    for key, title, filename in plot_specs:

        vals_sec = valid_values(
            records,
            key,
        )

        if not vals_sec:
            continue

        vals_min = [
            v / 60.0
            for v in vals_sec
        ]

        mean_min = statistics.mean(vals_min)
        median_min = statistics.median(vals_min)

        fig, ax = plt.subplots(
            figsize=(8, 5)
        )

        ax.hist(
            vals_min,
            bins="auto",
            alpha=0.8,
            edgecolor="black",
        )

        ax.axvline(
            mean_min,
            linestyle="--",
            linewidth=2,
            label=f"Mean = {mean_min:.1f} min",
        )

        ax.axvline(
            median_min,
            linestyle=":",
            linewidth=2,
            label=f"Median = {median_min:.1f} min",
        )

        ax.set_title(
            f"{label}: {title}"
        )

        ax.set_xlabel(
            "Time [min]"
        )

        ax.set_ylabel(
            "Number of jobs"
        )

        ax.legend()

        fig.tight_layout()

        fig.savefig(
            output_dir / filename,
            dpi=150,
        )

        plt.close(fig)

    print(
        f"Plots written to: "
        f"{output_dir}"
    )


# ============================================================
# Cluster mode
# ============================================================

def run_cluster_mode(
    args,
    log_index,
):

    try:

        cluster, requested_proc = split_job_id(
            args.job_id
        )

    except ValueError as exc:

        raise SystemExit(str(exc))

    grouped = candidate_files_cluster(
        log_index,
        cluster,
        requested_proc,
    )

    if not grouped:

        raise SystemExit(
            f"No logs found for {args.job_id}"
        )

    records = []

    for proc in sorted(grouped):

        paths = grouped[proc]

        parsed_items = [
            parse_file(
                path,
                cluster,
                proc,
            )
            for path in paths
        ]

        merged = merge_parsed(
            parsed_items
        )

        records.append(
            make_job_record(
                cluster,
                proc,
                merged,
                paths,
            )
        )

    if not args.no_table:

        print_table(
            records,
            json_mode=False,
        )

    print_cluster_summary(
        cluster,
        records,
    )

    return records, f"Cluster {cluster}"


# ============================================================
# JSON mode
# ============================================================

def run_json_mode(
    args,
    log_index,
):

    nano_info = load_nano_jobs(
        args.jobs_json
    )

    records = []
    missing_logs = []

    for logical_job in nano_info["logical_jobs"]:

        cluster = logical_job["cluster"]
        proc = logical_job["proc"]

        paths = log_index.get(
            (cluster, proc),
            [],
        )

        if not paths:

            missing_logs.append(
                logical_job
            )

            continue

        parsed_items = [
            parse_file(
                path,
                cluster,
                proc,
            )
            for path in paths
        ]

        merged = merge_parsed(
            parsed_items
        )

        records.append(
            make_job_record(
                cluster,
                proc,
                merged,
                paths,
                logical_job=logical_job,
            )
        )

    if not args.no_table:

        print_table(
            records,
            json_mode=True,
        )

    print_json_summary(
        nano_info,
        records,
        missing_logs,
        args.failed_log_list,
    )

    return records, "Nano2Pico final trials"


# ============================================================
# Main
# ============================================================

def main():

    args = parse_args()

    base = Path(
        args.dir
    ).expanduser().resolve()

    if not base.is_dir():

        raise SystemExit(
            f"Log directory does not exist: {base}"
        )

    print(
        f"[Info] Building log index from {base} ..."
    )

    log_index = build_log_index(
        base
    )

    print(
        f"[Info] Indexed "
        f"{len(log_index)} Condor job IDs."
    )

    if args.jobs_json:

        records, plot_label = run_json_mode(
            args,
            log_index,
        )

    else:

        records, plot_label = run_cluster_mode(
            args,
            log_index,
        )

    if args.csv:

        write_csv(
            args.csv,
            records,
        )

        print()
        print(
            f"CSV written to: {args.csv}"
        )

    if args.plot:

        if args.plot_dir:

            plot_dir = args.plot_dir

        elif args.jobs_json:

            plot_dir = "timing_plots_final_jobs"

        else:

            cluster, _ = split_job_id(
                args.job_id
            )

            plot_dir = (
                f"timing_plots_{cluster}"
            )

        print()

        save_timing_plots(
            records,
            plot_label,
            plot_dir,
        )


if __name__ == "__main__":
    main()
