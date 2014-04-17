#!/usr/bin/env python
from __future__ import print_function, division

from utility import color, format_duration, format_mem
import job as modulejob

import sys
import os
import re
from time import strptime, sleep
from subprocess import Popen, check_output, PIPE

import threading


class Joblist(list):
    """List of LSF jobs"""
    alljobs = dict()

    def __init__(self, args=None, jobs=None):
        """Read joblist from bjobs or form another list"""
        list.__init__(self)
        if jobs:
            self += jobs
        if args is None:
            return
        if type(args) is str:
            args = [args]
        self.readjobs(args)

    def __setitem__(self, key, value):
        """Access jobs"""
        if not isinstance(value, modulejob.Job):
            raise TypeError("Joblist elements must be Job not " +
                            value.__class__.__name__)
        list.__setitem__(self, key, value)
        Joblist.alljobs[value["Job"]] = value

    def append(self, value):
        """Access jobs"""
        if not isinstance(value, modulejob.Job):
            raise TypeError("Joblist elements must be Job not " +
                            value.__class__.__name__)
        list.append(self, value)
        Joblist.alljobs[value["Job"]] = value

    def __setslice__(self, i, j, sequence):
        """Access jobs"""
        for k, value in enumerate(sequence):
            if not isinstance(value, modulejob.Job):
                raise TypeError("item " + value.__class__.__name__ +
                                ": Joblist elements must be Job not " + k)
            else:
                Joblist.alljobs[value["Job"]] = value
        list.__setslice__(self, i, j, sequence)

    def __add__(self, other):
        """Access jobs"""
        return Joblist(jobs=self + other)

    def __radd__(self, other):
        """Access jobs"""
        return Joblist(jobs=other + self)

    def __iadd__(self, sequence):
        """Access jobs"""
        for k, value in enumerate(sequence):
            if not isinstance(value, modulejob.Job):
                raise TypeError("item " + value.__class__.__name__ +
                                ": Joblist elements must be Job not " + k)
            else:
                Joblist.alljobs[value["Job"]] = value
        for job in sequence:
            self.append(job)

    def readjobs(self, args):
        """Read jobs from LSF"""
        p = Popen(["bjobs", "-w", "-X"] + args, stdout=PIPE, stderr=PIPE)
        out, err = p.communicate()
        out = out.decode()
        err = err.decode()
        if "No unfinished job found" in err:
            return
        for line in out.split("\n")[1:-1]:
            line = line.split()
            data = {
                "Job": line[0],
                "User": line[1],
                "Status": line[2],
                "queue": line[3],
                "Job Name": line[6]
            }
            match = re.search("(\[\d+\])$", line[-4])
            if match:
                data["Job"] += match.groups()[0]
            procs = {}
            for proc in line[5].split(":"):
                proc = proc.split("*")
                if len(proc) == 1:
                    procs[proc[0]] = 1
                else:
                    procs[proc[1]] = int(proc[0])
            data["Processors"] = procs
            if data["Job"] in Joblist.alljobs:
                self.append(Joblist.alljobs[data["Job"]])
            else:
                self.append(modulejob.Job(data))

    def wait(self, check_freq=1):
        """Wait for all jobs in this list to complete.

        @param - check_freq time (in seconds) to sleep between checking."""
        while True:
            done = True
            for j in self:
                j.read()
                try:
                    if j['Status'] not in ['EXIT', 'DONE']:
                        done = False
                except KeyError:
                    # If job has been forgotten about then
                    # this also counts as done.
                    pass
            if done:
                return
            sleep(check_freq)

    def groupby(self, key=None):
        """sort the jobs in groups by attributes"""
        if not key:
            return {None: self}
        result = {}
        for job in self:
            if key not in job:
                value = None
            else:
                value = job[key]
            if type(value) is dict:
                value = tuple(value.items())
            if type(value) is list:
                value = tuple(value)
            if value not in result:
                result[value] = Joblist()
            result[value].append(job)
            continue
        return result

    def display(self, long=False, wide=False, title=None, parallel=True,
                header=True):
        """list the jobs"""
        if len(self) == 0:
            return
        # read job data in parallel
        threads = {}
        if parallel:
            strptime("", "")  # hack to make pseude thread-safe
            for job in self:
                if not job.initialized and not job.initializing:
                    t = threading.Thread(target=job.init)
                    t.start()
                    threads[job["Job"]] = t
        # begin output
        screencols = int(check_output(["tput", "cols"]))
        if long:
            if title:
                print(title.center(screencols, "-"))
            for job in self:
                if job["Job"] in threads:
                    threads[job["Job"]].join()
                if "Job Name" in job:
                    f = " {Job} --- {Job Name} --- {User} --- {Status} "
                else:
                    f = " {Job} --- --- {User} --- {Status} "
                header = f.format(**job)
                print(header.center(screencols, "-"))
                print(job)
            return
        whoami = os.getenv("USER")
        lens = {
            "id": 14,
            "name": 20,
            "status": 8,
            "user": 10,
            "time": 12,
        }
        if wide:
            lens["name"] = 32
            lens["queue"] = 8
            lens["project"] = 8
        if header:
            h = "Job".ljust(lens["id"]) + "Job Name".ljust(lens["name"])
            h += "Status".ljust(lens["status"]) + "User".ljust(lens["user"])
            if wide:
                h += "Queue".ljust(lens["queue"])
                h += "Project".ljust(lens["project"])
            h += "Wait/Runtime".rjust(lens["time"]) + "  Resources"
            h = h.replace(" ", "-")
            if title:
                h += (" " + title + " ").center(screencols - len(h), "-")
            else:
                h += (screencols - len(h)) * "-"
            print(h)
        for job in self:
            if job["Job"] in threads:
                threads[job["Job"]].join()
            # Job
            l = (job["Job"] + " ").ljust(lens["id"])
            # Job Name
            jobname = job["Job Name"] if "Job Name" in job else ""
            if not wide:
                if len(jobname) >= lens["name"]:
                    jobname = jobname[:lens["name"] - 2] + "*"
                jobname += " "
            l += jobname.ljust(lens["name"])
            # Status
            if job["Status"] == "PEND":
                c = "r"
            elif job["Status"] == "RUN":
                c = "g"
            else:
                c = "y"
            l += color((job["Status"] + " ").ljust(lens["status"]), c)
            # User
            if wide:
                username = job["Userstr"]
            else:
                username = job["User"]
            if job["User"] == whoami:
                c = "g"
            else:
                c = 0
            l += color((username + " ").ljust(lens["user"]), c)
            # Project
            if wide:
                l += job["Queue"].ljust(lens["queue"])
                l += job["Project"].ljust(lens["project"])
            # Wait/Runtime
            if "runtime" in job:
                t = job["runtime"]
            else:
                t = job["waittime"]
            s = format_duration(t)
            l += s.rjust(lens["time"])
            # Resources
            # Time
            l += "  " + format_duration(job["RUNLIMIT"]) + "  "
            # Memory
            l += format_mem(job["MEMLIMIT"]).rjust(7)
            if job["Status"] == "RUN":
                # %usage
                l += " {:>3}%t".format(100 * job["runtime"] // job["RUNLIMIT"])
                if "MEM" in job:
                    maxmem = job["MEMLIMIT"] * job["Processors Requested"]
                    l += " {:>3}%m".format(100 * job["MEM"] // maxmem)
                else:
                    l += "      "
                # Execution hosts
                if job["Exclusive Execution"]:
                    l += "    "
                if wide or len(job["Processors"]) == 1:
                    l += job["Processorsstr"]
                else:
                    l += job["Hostgroupsstr"]
            elif job["Status"] == "PEND":
                # #cores
                l += str(job["Nodes Requested"]).rjust(4)
                if "Exclusive Execution" in job and job["Exclusive Execution"]:
                    l += " nexcl" if "ptile" in job else " excl "
                else:
                    l += " nodes" if "ptile" in job else " cores"
                # Hosts or architecture
                if "Specified Hosts" in job:
                    if wide or len(job["Specified Hosts"]) == 1:
                        l += "  " + job["Specified Hostsstr"].ljust(16)
                    else:
                        l += "  " + job["Specified Hostgroupsstr"]
                else:
                    match = re.search("\(model\s*==\s*(\w+)\)",
                                      job["Requested Resources"])
                    if match:
                        l += "  " + match.groups()[0].ljust(14)
                if "Reserved" in job:
                    l += "  rsvd:"
                    if wide or len(job["Reserved"]) == 1:
                        l += job["Reservedstr"]
                    else:
                        l += job["Reserved Hostgroupsstr"]
            print(l)
            sys.stdout.flush()
