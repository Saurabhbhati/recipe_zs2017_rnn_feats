#!/usr/bin/env python

"""
Train a Siamese triplets network.

Author: Herman Kamper
Contact: kamperh@gmail.com
Date: 2018
"""

from __future__ import division
from __future__ import print_function
from datetime import datetime
from os import path
from scipy.spatial.distance import pdist
import argparse
import cPickle as pickle
import hashlib
import numpy as np
import os
import sys
import tensorflow as tf

sys.path.append(path.join("..", "src"))

from tflego import NP_DTYPE, TF_DTYPE, NP_ITYPE, TF_ITYPE
import batching
import data_io
import samediff
import tflego
import training


#-----------------------------------------------------------------------------#
#                           DEFAULT TRAINING OPTIONS                          #
#-----------------------------------------------------------------------------#

default_options_dict = {
        "data_dir": path.join("data", "buckeye.mfcc"),
        "train_tag": "gt",                  # "gt", "gt2", "utd"
        "max_length": 100,
        "bidirectional": False,
        "rnn_type": "gru",                  # "lstm", "gru", "rnn"
        "rnn_n_hiddens": [400, 400, 400],
        "ff_n_hiddens": [130],              # embedding dimensionality
        "margin": 0.2,
        "learning_rate": 0.001,
        "rnn_keep_prob": 1.0,
        "ff_keep_prob": 1.0,
        "n_epochs": 10,
        "batch_size": 300,
        "n_buckets": 3,
        "extrinsic_usefinal": False,        # if True, during final extrinsic
                                            # evaluation, the final saved model
                                            # will be used (instead of the
                                            # validation best)
        "use_test_for_val": False,
        "n_val_interval": 1,
        "rnd_seed": 1,
    }


#-----------------------------------------------------------------------------#
#                              TRAINING FUNCTIONS                             #
#-----------------------------------------------------------------------------#

def build_siamese_rnn_side(x, x_lengths, rnn_n_hiddens, ff_n_hiddens,
        rnn_type="lstm", rnn_keep_prob=1.0, ff_keep_prob=1.0,
        bidirectional=False):
    """
    Multi-layer RNN serving as one side of a Siamese model.

    Parameters
    ----------
    x : Tensor [n_data, maxlength, d_in]
    """

    if bidirectional:
        rnn_outputs, rnn_states = tflego.build_bidirectional_multi_rnn(
            x, x_lengths, rnn_n_hiddens, rnn_type=rnn_type,
            keep_prob=rnn_keep_prob
            )
    else:
        rnn_outputs, rnn_states = tflego.build_multi_rnn(
            x, x_lengths, rnn_n_hiddens, rnn_type=rnn_type,
            keep_prob=rnn_keep_prob
            )
    if rnn_type == "lstm":
        rnn_states = rnn_states.h
    rnn = tflego.build_feedforward(
        rnn_states, ff_n_hiddens, keep_prob=ff_keep_prob
        )
    return rnn


def build_siamese_from_options_dict(x, x_lengths, options_dict):
    network_dict = {}
    rnn = build_siamese_rnn_side(
        x, x_lengths, options_dict["rnn_n_hiddens"],
        options_dict["ff_n_hiddens"], options_dict["rnn_type"],
        options_dict["rnn_keep_prob"], options_dict["ff_keep_prob"],
        options_dict["bidirectional"]
        )
    rnn = tf.nn.l2_normalize(rnn, axis=1)
    network_dict["output"] = rnn
    return network_dict


def train_siamese(options_dict):
    """Train and save a Siamese triplets model."""

    # PRELIMINARY

    print(datetime.now())

    # Output directory
    hasher = hashlib.md5(repr(sorted(options_dict.items())).encode("ascii"))
    hash_str = hasher.hexdigest()[:10]
    model_dir = path.join(
        "models", path.split(options_dict["data_dir"])[-1] + "." +
        options_dict["train_tag"], options_dict["script"], hash_str
        )
    options_dict_fn = path.join(model_dir, "options_dict.pkl")
    print("Model directory:", model_dir)
    if not os.path.isdir(model_dir):
        os.makedirs(model_dir)
    print("Options:", options_dict)

    # Random seeds
    np.random.seed(options_dict["rnd_seed"])
    tf.set_random_seed(options_dict["rnd_seed"])


    # LOAD AND FORMAT DATA

    # Training data
    train_tag = options_dict["train_tag"]
    npz_fn = path.join(
        options_dict["data_dir"], "train." + train_tag + ".npz"
        )
    train_x, train_labels, train_lengths, train_keys = (
        data_io.load_data_from_npz(npz_fn, None)
        )

    # Convert training labels to integers
    train_label_set = list(set(train_labels))
    label_to_id = {}
    for i, label in enumerate(sorted(train_label_set)):
        label_to_id[label] = i
    train_y = []
    for label in train_labels:
        train_y.append(label_to_id[label])
    train_y = np.array(train_y, dtype=NP_ITYPE)

    # Validation data
    if options_dict["use_test_for_val"]:
        npz_fn = path.join(options_dict["data_dir"], "test.npz")
    else:
        npz_fn = path.join(options_dict["data_dir"], "val.npz")
    val_x, val_labels, val_lengths, val_keys = data_io.load_data_from_npz(
        npz_fn
        )

    # Truncate and limit dimensionality
    max_length = options_dict["max_length"]
    d_frame = 13  # None
    options_dict["n_input"] = d_frame
    print("Limiting dimensionality:", d_frame)
    print("Limiting length:", max_length)
    data_io.trunc_and_limit_dim(train_x, train_lengths, d_frame, max_length)
    data_io.trunc_and_limit_dim(val_x, val_lengths, d_frame, max_length)


    # DEFINE MODEL

    print(datetime.now())
    print("Building model")

    # Model filenames
    intermediate_model_fn = path.join(model_dir, "siamese.tmp.ckpt")
    model_fn = path.join(model_dir, "siamese.best_val.ckpt")

    # Model graph
    x = tf.placeholder(TF_DTYPE, [None, None, options_dict["n_input"]])
    x_lengths = tf.placeholder(TF_ITYPE, [None])
    y = tf.placeholder(TF_ITYPE, [None])
    network_dict = build_siamese_from_options_dict(x, x_lengths, options_dict)
    output = network_dict["output"]

    # Semi-hard triplets loss
    loss = tf.contrib.losses.metric_learning.triplet_semihard_loss(
        labels=y, embeddings=output, margin=options_dict["margin"]
        )
    optimizer = tf.train.AdamOptimizer(
        learning_rate=options_dict["learning_rate"]
        ).minimize(loss)


    # TRAIN AND VALIDATE

    print(datetime.now())
    print("Training model")

    # Validation function
    def samediff_val(normalise=False):
        # Embed validation
        np.random.seed(options_dict["rnd_seed"])
        val_batch_iterator = batching.SimpleIterator(val_x, len(val_x), False)
        labels = [val_labels[i] for i in val_batch_iterator.indices]
        saver = tf.train.Saver()
        with tf.Session() as session:
            saver.restore(session, val_model_fn)
            for batch_x_padded, batch_x_lengths in val_batch_iterator:
                np_x = batch_x_padded
                np_x_lengths = batch_x_lengths
                np_z = session.run(
                    [output], feed_dict={x: np_x, x_lengths: np_x_lengths}
                    )[0]
                break  # single batch

        embed_dict = {}
        for i, utt_key in enumerate(
                [val_keys[i] for i in val_batch_iterator.indices]):
            embed_dict[utt_key] = np_z[i]

        # Same-different
        if normalise:
            np_z_normalised = (np_z - np_z.mean(axis=0))/np_z.std(axis=0)
            distances = pdist(np_z_normalised, metric="cosine")
            matches = samediff.generate_matches_array(labels)
            ap, prb = samediff.average_precision(
                distances[matches == True], distances[matches == False]
                )
        else:
            distances = pdist(np_z, metric="cosine")
            matches = samediff.generate_matches_array(labels)
            ap, prb = samediff.average_precision(
                distances[matches == True], distances[matches == False]
                )    
        return [prb, -ap]

    # Train Siamese model
    val_model_fn = intermediate_model_fn
    train_batch_iterator = batching.LabelledBucketIterator(
        train_x, train_y, options_dict["batch_size"],
        n_buckets=options_dict["n_buckets"], shuffle_every_epoch=True
        )
    record_dict = training.train_fixed_epochs_external_val(
        options_dict["n_epochs"], optimizer, loss, train_batch_iterator, [x,
        x_lengths, y], samediff_val, save_model_fn=intermediate_model_fn,
        save_best_val_model_fn=model_fn,
        n_val_interval=options_dict["n_val_interval"]
        )

    # Save record
    record_dict_fn = path.join(model_dir, "record_dict.pkl")
    print("Writing:", record_dict_fn)
    with open(record_dict_fn, "wb") as f:
        pickle.dump(record_dict, f, -1)

    # Save options_dict
    options_dict_fn = path.join(model_dir, "options_dict.pkl")
    print("Writing:" + options_dict_fn)
    with open(options_dict_fn, "wb") as f:
        pickle.dump(options_dict, f, -1)


    # FINAL EXTRINSIC EVALUATION

    print ("Performing final validation")
    if options_dict["extrinsic_usefinal"]:
        val_model_fn = intermediate_model_fn
    else:
        val_model_fn = model_fn
    prb, ap = samediff_val(normalise=False)
    ap = -ap
    prb_normalised, ap_normalised = samediff_val(normalise=True)
    ap_normalised = -ap_normalised
    print("Validation AP:", ap)
    print("Validation AP with normalisation:", ap_normalised)
    ap_fn = path.join(model_dir, "val_ap.txt")
    print("Writing:", ap_fn)
    with open(ap_fn, "w") as f:
        f.write(str(ap) + "\n")
        f.write(str(ap_normalised) + "\n")
    print("Validation model:", val_model_fn)

    print(datetime.now())


#-----------------------------------------------------------------------------#
#                              UTILITY FUNCTIONS                              #
#-----------------------------------------------------------------------------#

def check_argv():
    """Check the command line arguments."""
    parser = argparse.ArgumentParser(
        description=__doc__.strip().split("\n")[0]
        )
    parser.add_argument(
        "--data_dir", type=str,
        help="load data from this directory (default: %(default)s)",
        default=default_options_dict["data_dir"]
        )
    parser.add_argument(
        "--n_epochs", type=int,
        help="number of epochs of training (default: %(default)s)",
        default=default_options_dict["n_epochs"]
        )
    parser.add_argument(
        "--batch_size", type=int,
        help="size of mini-batch (default: %(default)s)",
        default=default_options_dict["batch_size"]
        )
    parser.add_argument(
        "--train_tag", type=str, choices=["gt", "gt2", "utd", "rnd"],
        help="training set tag (default: %(default)s)",
        default=default_options_dict["train_tag"]
        )
    parser.add_argument(
        "--extrinsic_usefinal", action="store_true",
        help="if set, during final extrinsic evaluation, the final saved "
        "model will be used instead of the validation best (default: "
        "%(default)s)",
        default=default_options_dict["extrinsic_usefinal"]
        )
    parser.add_argument(
        "--use_test_for_val", action="store_true",
        help="if set, use the test data for validation (cheating, so only "
        "use when doing final evaluation, otherwise this is cheating) "
        "(default: %(default)s)",
        default=default_options_dict["use_test_for_val"]
        )
    parser.add_argument(
        "--rnd_seed", type=int, help="random seed (default: %(default)s)",
        default=default_options_dict["rnd_seed"]
        )
    return parser.parse_args()


#-----------------------------------------------------------------------------#
#                                MAIN FUNCTION                                #
#-----------------------------------------------------------------------------#

def main():
    args = check_argv()

    # Set options
    options_dict = default_options_dict.copy()
    options_dict["script"] = "train_siamese"
    options_dict["data_dir"] = args.data_dir
    options_dict["n_epochs"] = args.n_epochs
    options_dict["batch_size"] = args.batch_size
    options_dict["extrinsic_usefinal"] = args.extrinsic_usefinal
    options_dict["use_test_for_val"] = args.use_test_for_val
    options_dict["train_tag"] = args.train_tag
    options_dict["rnd_seed"] = args.rnd_seed

    # Train model
    train_siamese(options_dict)    


if __name__ == "__main__":
    main()
