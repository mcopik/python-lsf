#!/usr/bin/env python
from __future__ import print_function, division

from utility import color, format_duration, format_mem

import os
import sys
import re
from time import time
from subprocess import check_output
from collections import defaultdict


def findstringpattern(strings):
    if not len(strings):
        return ""
    if all(strings[0] == s for s in strings[1:]):
        return strings[0]
    prefix = ""
    while strings[0] and all(strings[0][0] == s[0] for s in strings[1:] if s):
        prefix += strings[0][0]
        strings = [s[1:] for s in strings]
    suffix = ""
    while strings[0] and all(strings[0][-1] == s[-1]
                             for s in strings[1:] if s):
        suffix = strings[0][-1] + suffix
        strings = [s[:-1] for s in strings]
    return prefix + "*" + suffix


def printjobssum(jobs, long=False, wide=False, title=None, header=True,
                 file=sys.stdout):
    """list the jobs"""
    if len(jobs) == 0:
        return
    # begin output
    whoami = os.getenv("USER")
    lens = {
        "name": 20,
        "stat": 12,
        "user": 10,
        "time": 12,
        "title": 10
    }
    if wide:
        lens["name"] = 32
        lens["queue"] = 8
        lens["project"] = 8
    if header and printjobssum.header:
        h = ""
        if title:
            h += "group".ljust(lens["title"])
        h += "".join(n.ljust(lens[n]) for n in ("name", "stat", "user"))
        if wide:
            h += "".join(n.ljust(lens[n]) for n in ("queue", "project"))
        h += "wait/runtime".rjust(lens["time"]) + "  resources"
        h = h.upper()
        print(h, file=file)
        printjobssum.header = False
    sumjob = {}
    for key in jobs[0]:
        if key in ("job_name", "job_description", "user", "queue", "project",
                   "input_file", "output_file", "error_file", "output_dir",
                   "sub_cwd", "exec_home", "exec_cwd", "exit_reson",
                   "application", "command", "pre_exec_command",
                   "post_exec_command", "resize_notification_command",
                   "effective_resreq"):
            # find string pattern
            sumjob[key] = findstringpattern([job[key] for job in jobs if
                                             job[key]])
        elif key in ("runlimit", "swaplimit", "stacklimi", "memlimit",
                     "filelimit", "processlimit", "corelimit", "run_time",
                     "swap", "slots", "mem", "max_mem", "avg_mem",
                     "nexec_host"):
            # sum
            sumjob[key] = sum(job[key] for job in jobs if job[key])
        elif key in ("%complete", "job_priority", "idle_factor"):
            # compute average
            pcomp = [job[key] for job in jobs if job[key]]
            if pcomp:
                sumjob[key] = sum(pcomp) / len(pcomp)
            else:
                sumjob[key] = None
        elif key == "stat":
            # compute statistics
            sumjob[key] = defaultdict(int)
            for job in jobs:
                sumjob[key][job["stat"]] += 1
        elif key == "exec_host":
            # collect host counts
            sumjob[key] = defaultdict(int)
            for job in jobs:
                if job[key]:
                    for host, count in job[key].iteritems():
                        sumjob[key][host] += count
        elif key == "pids":
            # collect
            sumjob[key] = sum((job[key] for job in jobs if job[key]), [])
        else:
            # collect
            sumjob[key] = [job[key] for job in jobs if job[key]]
    # begin output
    # title
    l = ""
    if title:
        l += color(title.ljust(lens["title"]), "b")
    # Job Name
    jobname = sumjob["job_name"]
    if not wide:
        if len(jobname) >= lens["name"]:
            jobname = jobname[:lens["name"] - 2] + "*"
    l += jobname.ljust(lens["name"])
    # Status
    l += color("%3d " % sumjob["stat"]["PEND"], "r")
    l += color("%3d " % sumjob["stat"]["RUN"], "g")
    done = sumjob["stat"]["EXIT"] + sumjob["stat"]["DONE"]
    if done:
        l += color("%3d " % done, "y")
    else:
        l += "    "
    # User
    c = "g" if sumjob["user"] == whoami else 0
    l += color((sumjob["user"] + " ").ljust(lens["user"]), c)
    # Project
    if wide:
        l += sumjob["queue"].ljust(lens["queue"])
        l += sumjob["project"].ljust(lens["project"])
    # Wait/Runtime
    l += format_duration(sumjob["run_time"]).rjust(lens["time"])
    # Resources
    # Time
    if sumjob["runlimit"]:
        l += "  " + format_duration(sumjob["runlimit"]).rjust(lens["time"])
    if sumjob["%complete"]:
        ptime = int(sumjob["%complete"])
        c = "r" if ptime > 90 else "y" if ptime > 75 else 0
        l += " " + color("%3d" % ptime, c) + "%t"
    # Memory
    if sumjob["memlimit"] and sumjob["mem"] and sumjob["slots"]:
        memlimit = sumjob["memlimit"] * sumjob["slots"]
        pmem = int(100 * sumjob["mem"] / memlimit)
        c = "r" if pmem > 90 else "y" if pmem > 75 else 0
        l += " " + color("%3d" % pmem, c) + "%m"
    if sumjob["mem"]:
        l += " " + format_mem(sumjob["mem"]).rjust(9)
    else:
        l += "          "
    # Hosts
    if sumjob["exec_host"]:
        if wide or len(sumjob["exec_host"]) == 1:
            d = sumjob["exec_host"]
        else:
            d = defaultdict(int)
            for key, val in sumjob["exec_host"].iteritems():
                d[re.match("(.*?)\d+", key).groups()[0]] += val
        for key, val in d.iteritems():
            c = "r" if val >= 100 else "y" if val >= 20 else 0
            l += color(" %3d" % val, c) + "*%s" % key
    print(l, file=file)
    file.flush()

printjobssum.header = True