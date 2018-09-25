"""
Author: Herman Kamper
Contact: kamperh@gmail.com
Date: 2018
"""

import numpy.testing as npt
from tflego import *



#-----------------------------------------------------------------------------#
#                          NUMPY EQUIVALENT FUNCTIONS                         #
#-----------------------------------------------------------------------------#

def np_linear(x, W, b):
    return np.dot(x, W) + b


def np_rnn(x, x_lengths, W, b, maxlength=None):
    """Calculates the output for a basic RNN."""
    if maxlength is None:
        maxlength = max(x_lengths)
    outputs = np.zeros((x.shape[0], maxlength, W.shape[1]))
    for i_data in xrange(x.shape[0]):
        cur_x_sequence = x[i_data, :x_lengths[i_data], :]
        prev_state = np.zeros(W.shape[1])
        for i_step, cur_x in enumerate(cur_x_sequence):
            cur_state = np.tanh(np.dot(np.hstack((cur_x, prev_state)), W) + b)
            outputs[i_data, i_step, :] = cur_state
            prev_state = cur_state
    return outputs


def np_multi_rnn(x, x_lengths, weights, biases, maxlength=None):
    """
    Push the input `x` through the RNN. The `weights`
    and `biases` should be lists of the parameters of each layer.
    """
    for W, b in zip(weights, biases):
        x = np_rnn(x, x_lengths, W, b, maxlength)
    return x


def np_encdec_lazydynamic(x, x_lengths, W_encoder, b_encoder, W_decoder,
        b_decoder, W_output, b_output, maxlength=None):

    if maxlength is None:
        maxlength = max(x_lengths)

    # Encoder
    encoder_output = np_rnn(x, x_lengths, W_encoder, b_encoder, maxlength)
    encoder_states = []
    for i_data, l in enumerate(x_lengths):
        encoder_states.append(encoder_output[i_data, l - 1, :])
    encoder_states = np.array(encoder_states)

    # Decoder

    # Repeat encoder states
    n_hidden = W_encoder.shape[-1]
    decoder_input = np.reshape(
        np.repeat(encoder_states, maxlength, axis=0), [-1, maxlength, n_hidden]
        )
    
    # Decoding RNN
    decoder_output = np_rnn(
        decoder_input, x_lengths, W_decoder, b_decoder, maxlength
        )

    # Final linear layer
    decoder_output_linear = np.zeros(x.shape)
    decoder_output_list = []
    for i_data in xrange(x.shape[0]):
        cur_decoder_sequence = decoder_output[i_data, :x_lengths[i_data], :]
        cur_decoder_list = []
        for i_step, cur_decoder in enumerate(cur_decoder_sequence):
            output_linear = np_linear(
                cur_decoder, W_output, b_output
                )
            decoder_output_linear[i_data, i_step, :] = output_linear
            cur_decoder_list.append(output_linear)
        decoder_output_list.append(np.array(cur_decoder_list))
    decoder_output = decoder_output_linear

    return encoder_states, decoder_output, decoder_output_list


#-----------------------------------------------------------------------------#
#                                TEST FUNCTIONS                               #
#-----------------------------------------------------------------------------#

def test_rnn():

    tf.reset_default_graph()

    # Random seed
    np.random.seed(1)
    tf.set_random_seed(1)

    # Test data
    n_input = 10
    n_data = 11
    n_maxlength = 12
    test_data = np.zeros((n_data, n_maxlength, n_input), dtype=NP_DTYPE)
    lengths = []
    for i_data in xrange(n_data):
        length = np.random.randint(1, n_maxlength + 1)
        lengths.append(length)
        test_data[i_data, :length, :] = np.random.randn(length, n_input)
    lengths = np.array(lengths, dtype=NP_ITYPE)

    # Model parameters
    n_hidden = 13
    rnn_type = "rnn"

    # TensorFlow model
    x = tf.placeholder(TF_DTYPE, [None, n_maxlength, n_input])
    x_lengths = tf.placeholder(TF_DTYPE, [None])
    rnn_outputs, rnn_states = build_rnn(
        x, x_lengths, n_hidden, rnn_type=rnn_type
        )
    with tf.variable_scope("rnn/basic_rnn_cell", reuse=True):
        W = tf.get_variable("kernel")
        b = tf.get_variable("bias")

    # TensorFlow graph
    init = tf.global_variables_initializer()
    with tf.Session() as session:
        session.run(init)
        
        # Output
        tf_output = rnn_outputs.eval({x: test_data, x_lengths: lengths})
        
        # Weights
        W = W.eval()
        b = b.eval()

    # NumPy model
    np_output = np_rnn(test_data, lengths, W, b, n_maxlength)

    npt.assert_almost_equal(tf_output, np_output, decimal=5)


def test_multi_rnn():

    tf.reset_default_graph()

    # Random seed
    np.random.seed(1)
    tf.set_random_seed(1)

    # Test data
    n_input = 10
    n_data = 11
    n_maxlength = 12
    test_data = np.zeros((n_data, n_maxlength, n_input), dtype=NP_DTYPE)
    lengths = []
    for i_data in xrange(n_data):
        length = np.random.randint(1, n_maxlength + 1)
        lengths.append(length)
        test_data[i_data, :length, :] = np.random.randn(length, n_input)
    lengths = np.array(lengths, dtype=NP_ITYPE)

    # Model parameters
    n_hiddens = [13, 14]
    rnn_type = "rnn"

    # TensorFlow model
    x = tf.placeholder(TF_DTYPE, [None, n_maxlength, n_input])
    x_lengths = tf.placeholder(TF_DTYPE, [None])
    rnn_outputs, rnn_states = build_multi_rnn(x, x_lengths, n_hiddens, rnn_type=rnn_type)
    with tf.variable_scope("rnn_layer_0/rnn/basic_rnn_cell", reuse=True) as vs:
        W_0 = tf.get_variable("kernel")
        b_0 = tf.get_variable("bias")
    with tf.variable_scope("rnn_layer_1/rnn/basic_rnn_cell", reuse=True) as vs:
        W_1 = tf.get_variable("kernel")
        b_1 = tf.get_variable("bias")

    # TensorFlow graph
    init = tf.global_variables_initializer()
    with tf.Session() as session:
        session.run(init)

        # Output
        tf_output = rnn_outputs.eval({x: test_data, x_lengths: lengths})

        # Weights
        W_0 = W_0.eval()
        b_0 = b_0.eval()
        W_1 = W_1.eval()
        b_1 = b_1.eval()

    # Numpy model
    np_output = np_multi_rnn(test_data, lengths, [W_0, W_1], [b_0, b_1], n_maxlength)

    npt.assert_almost_equal(tf_output, np_output, decimal=5)


def test_encdec_lazydynamic():

    tf.reset_default_graph()

    # Random seed
    np.random.seed(1)
    tf.set_random_seed(1)

    # Test data
    n_input = 4
    n_data = 3
    n_maxlength = 5
    test_data = np.zeros((n_data, n_maxlength, n_input), dtype=NP_DTYPE)
    lengths = []
    for i_data in xrange(n_data):
        length = np.random.randint(1, n_maxlength + 1)
        lengths.append(length)
        test_data[i_data, :length, :] = np.random.randn(length, n_input)
    lengths = np.array(lengths, dtype=NP_ITYPE)

    # Model parameters
    n_hidden = 6
    rnn_type = "rnn"

    # TensorFlow model
    x = tf.placeholder(TF_DTYPE, [None, None, n_input])
    x_lengths = tf.placeholder(TF_ITYPE, [None])
    network_dict = build_encdec_lazydynamic(
        x, x_lengths, n_hidden, rnn_type=rnn_type
        )
    encoder_states = network_dict["encoder_states"]
    decoder_output = network_dict["decoder_output"]
    with tf.variable_scope("rnn_encoder/basic_rnn_cell", reuse=True):
        W_encoder = tf.get_variable("kernel")
        b_encoder = tf.get_variable("bias")
    with tf.variable_scope("rnn_decoder/basic_rnn_cell", reuse=True):
        W_decoder = tf.get_variable("kernel")
        b_decoder = tf.get_variable("bias")
    with tf.variable_scope("rnn_decoder/linear_output", reuse=True):
        W_output = tf.get_variable("W")
        b_output = tf.get_variable("b")

    # TensorFlow graph
    init = tf.global_variables_initializer()
    with tf.Session() as session:
        session.run(init)

        # Output
        tf_encoder_states = encoder_states.eval(
            {x: test_data, x_lengths: lengths}
            )
        tf_decoder_output = decoder_output.eval(
            {x: test_data, x_lengths: lengths}
            )

        # Weights
        W_encoder = W_encoder.eval()
        b_encoder = b_encoder.eval()
        W_decoder = W_decoder.eval()
        b_decoder = b_decoder.eval()
        W_output = W_output.eval()
        b_output = b_output.eval()

    np_encoder_states, np_decoder_output, _ = np_encdec_lazydynamic(
        test_data, lengths, W_encoder, b_encoder, W_decoder, b_decoder,
        W_output, b_output, n_maxlength
        )

    npt.assert_almost_equal(tf_encoder_states, np_encoder_states, decimal=5)
    npt.assert_almost_equal(tf_decoder_output, np_decoder_output, decimal=5)


def test_encdec_lazydynamic_masked_loss():

    tf.reset_default_graph()

    # Random seed
    np.random.seed(1)
    tf.set_random_seed(1)

    # Test data
    n_input = 4
    n_data = 3
    n_maxlength = 5
    test_data = np.zeros((n_data, n_maxlength, n_input), dtype=NP_DTYPE)
    test_data_list = []
    lengths = []
    for i_data in xrange(n_data):
        length = np.random.randint(1, n_maxlength + 1)
        lengths.append(length)
        seq = np.random.randn(length, n_input)
        test_data[i_data, :length, :] = seq
        test_data_list.append(seq)
    lengths = np.array(lengths, dtype=NP_ITYPE)

    # Model parameters
    n_hidden = 6
    rnn_type = "rnn"

    # TensorFlow model
    x = tf.placeholder(TF_DTYPE, [None, None, n_input])
    x_lengths = tf.placeholder(TF_ITYPE, [None])
    network_dict = build_encdec_lazydynamic(
        x, x_lengths, n_hidden, rnn_type=rnn_type
        )
    encoder_states = network_dict["encoder_states"]
    decoder_output = network_dict["decoder_output"]
    mask = network_dict["mask"]
    with tf.variable_scope("rnn_encoder/basic_rnn_cell", reuse=True):
        W_encoder = tf.get_variable("kernel")
        b_encoder = tf.get_variable("bias")
    with tf.variable_scope("rnn_decoder/basic_rnn_cell", reuse=True):
        W_decoder = tf.get_variable("kernel")
        b_decoder = tf.get_variable("bias")
    with tf.variable_scope("rnn_decoder/linear_output", reuse=True):
        W_output = tf.get_variable("W")
        b_output = tf.get_variable("b")

    # TensorFlow loss
    loss = tf.reduce_mean(
        tf.reduce_sum(tf.reduce_mean(tf.square(x - decoder_output), -1), -1) /
        tf.reduce_sum(mask, 1)
        )  # https://danijar.com/variable-sequence-lengths-in-tensorflow/

    # TensorFlow graph
    init = tf.global_variables_initializer()
    with tf.Session() as session:
        session.run(init)

        # Output
        tf_encoder_states = encoder_states.eval(
            {x: test_data, x_lengths: lengths}
            )
        tf_decoder_output = decoder_output.eval(
            {x: test_data, x_lengths: lengths}
            )
        tf_loss = loss.eval({x: test_data, x_lengths: lengths})

        # Weights
        W_encoder = W_encoder.eval()
        b_encoder = b_encoder.eval()
        W_decoder = W_decoder.eval()
        b_decoder = b_decoder.eval()
        W_output = W_output.eval()
        b_output = b_output.eval()

    _, _, np_decoder_list = np_encdec_lazydynamic(
        test_data, lengths, W_encoder, b_encoder, W_decoder, b_decoder,
        W_output, b_output, n_maxlength
        )

    # NumPy loss
    losses = []
    for i_data, x_seq in enumerate(test_data_list):
        y_seq = np_decoder_list[i_data]
        mse = ((y_seq - x_seq)**2).mean()
        losses.append(mse)
    np_loss = np.mean(losses)

    npt.assert_almost_equal(tf_loss, np_loss, decimal=5)


def test_vq():

    tf.reset_default_graph()

    # Random seed
    np.random.seed(1)
    tf.set_random_seed(1)

    # Test data
    D = 5
    K = 3
    test_data = np.random.randn(4, D)

    # TensorFlow model
    x = tf.placeholder(TF_DTYPE, [None, D])
    vq = build_vq(x, K, D)
    embeds = vq["embeds"]
    z_q = vq["z_q"]

    # TensorFlow graph
    init = tf.global_variables_initializer()
    with tf.Session() as session:
        session.run(init)
        tf_embeds = embeds.eval()
        tf_z_q = z_q.eval({x: test_data})

    # NumPy equivalent
    np_z_q = []
    for x_test in test_data:
        dists = []
        for embed in tf_embeds:
            dists.append(np.linalg.norm(x_test - embed))
        np_z_q.append(tf_embeds[np.argmin(dists)])

    npt.assert_almost_equal(tf_z_q, np_z_q)