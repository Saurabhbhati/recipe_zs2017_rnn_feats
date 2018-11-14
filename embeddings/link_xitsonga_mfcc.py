#!/usr/bin/env python

"""
Create links to the MFCC files.

Author: Herman Kamper
Contact: kamperh@gmail.com
Date: 2018
"""

from __future__ import division
from __future__ import print_function
from os import path
import numpy as np
import os

relative_features_dir = path.join("..", "..", "..", "features")
output_dir = path.join("data", "xitsonga.mfcc")


def main():

    # Create output directory
    if not path.isdir(output_dir):
        os.makedirs(output_dir)

    # Training: UTD discovered words
    npz_fn = path.join(
        relative_features_dir, "wordpairs", "xitsonga",
        "xitsonga_utd_terms.mfcc.cmvn_dd.npz"
        )
    link_fn = path.join(output_dir, "train.utd.npz")
    if not path.isfile(link_fn):
        print("Linking:", npz_fn, "to", link_fn)
        os.symlink(npz_fn, link_fn)

    # Test
    npz_fn = path.join(
        relative_features_dir, "wordpairs", "xitsonga",
        "xitsonga.samediff.mfcc.cmvn_dd.npz"
        )
    link_fn = path.join(output_dir, "test.npz")
    if not path.isfile(link_fn):
        print("Linking:", npz_fn, "to", link_fn)
        os.symlink(npz_fn, link_fn)


if __name__ == "__main__":
    main()
