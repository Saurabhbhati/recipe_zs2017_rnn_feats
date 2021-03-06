#!/usr/bin/env python

"""
Get the SCP containing the desired segments.

Author: Herman Kamper
Contact: kamperh@gmail.com
Date: 2011-2015, 2018
"""

from __future__ import division
from __future__ import print_function
from os import path
import argparse
import os
import sys

sys.path.append(path.join(".."))

from utils import shell

data_dir = path.join("..", "..", "data")


#-----------------------------------------------------------------------------#
#                              UTILITY FUNCTIONS                              #
#-----------------------------------------------------------------------------#

def check_argv():
    """Check the command line arguments."""
    parser = argparse.ArgumentParser(
        description=__doc__.strip().split("\n")[0], add_help=False
        )
    parser.add_argument("dataset", type=str, choices=["buckeye", "xitsonga"])
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    return parser.parse_args()


#-----------------------------------------------------------------------------#
#                                MAIN FUNCTION                                #
#-----------------------------------------------------------------------------#

def main():
    args = check_argv()

    if args.dataset == "buckeye":
        fa_fn = path.join(data_dir, "english.wrd")
    elif args.dataset == "xitsonga":
        fa_fn = path.join(data_dir, "xitsonga.wrd")

    list_dir = path.join(args.dataset, "lists")
    scp_dir = path.join(args.dataset, "scp")
    feat_dir = path.join(args.dataset, "raw")
    output_list = path.join(list_dir, "segments.list")
    output_scp = path.join(scp_dir, args.dataset + ".fbank.raw.segments.scp")

    for d in [list_dir]:
        if not path.isdir(d):
            os.makedirs(d)
    feat_dir = path.abspath(feat_dir)

    print("Reading:", fa_fn)
    segments = []  # (utterance, start_time, end_time)
    prev_utterance = ""
    prev_token_label = ""
    prev_end_time = -1
    start_time = -1
    with open(fa_fn, "r") as f:
        for line in f:
            utterance, start_token, end_token, token_label = line.strip(
                ).split()
            start_token = float(start_token)
            end_token = float(end_token)
            utterance = utterance.replace("_", "-")

            if token_label in ["SIL", "SPN"]:
                continue
            if prev_end_time != start_token or prev_utterance != utterance:
                if prev_end_time != -1:
                    segments.append(
                        (prev_utterance, start_time, prev_end_time)
                        )
                start_time = start_token

            prev_end_time = end_token
            prev_token_label = token_label
            prev_utterance = utterance
        segments.append((prev_utterance, start_time, prev_end_time))

    print("Writing:", output_list)
    with open(output_list, "w") as f:
        for utt, start, end in segments:
            f.write(utt + " " + str(start) + " " + str(end) + "\n")

    print("Getting raw audio file lengths")
    lengths = {}
    for line in shell(
            "HList -z -h " + path.join(feat_dir, "*.fbank" +
            " | paste - - - - - ")
            ).split("\n"):
        if len(line) == 0:
            continue
        line = line.split(" ")
        line = [i for i in line if i != ""]
        utt = line[line.index("Source:") + 1]
        utt = path.splitext(path.split(utt)[-1])[0]
        frames = line[line.index("Samples:") + 1]
        lengths[utt] = int(frames)

    print("Writing:", output_scp)
    f = open(output_scp, "w")
    for basename, start_time, end_time in segments:
        start = int(round(float(start_time) * 100))
        end = int(round(float(end_time) * 100))
        if end > lengths[basename]:
            if start > lengths[basename]:
                print("Warning: Problem with lengths (truncating):", basename)
                continue
            end = lengths[basename] - 1
        segment_label = "%s_%06d-%06d.fbank" % (basename, start, end)
        f.write(
            segment_label + "=" + path.join(feat_dir, basename + ".fbank") + "["
            + str(start) + "," + str(end) + "]\n"
            )
    f.close()


if __name__ == "__main__":
    main()
