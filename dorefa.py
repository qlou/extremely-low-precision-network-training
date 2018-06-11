#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File: dorefa.py
# Author: Yuxin Wu <ppwwyyxxc@gmail.com>

import tensorflow as tf

# just a hack to avoid repeatedly registering the gradient
GRAD_DEFINED = False

def get_dorefa(bitW, bitA, bitG):
    """ return the three quantization functions fw, fa, fg, for weights,
    activations and gradients respectively"""
    G = tf.get_default_graph()

    def quantize(x, k):
        clip_x = tf.clip_by_value(x, -1.0, float((2**(k-1)-1))/float(2**(k-1)))
        n = float(2**(k-1))
        with G.gradient_override_map({"Floor": "Identity"}):
            #return tf.round(clip_x * n) / n
            return tf.floor(clip_x * n) / n

    def fw1(x):
        with G.gradient_override_map({"Sign": "Identity"}):
            E = tf.stop_gradient(tf.reduce_mean(tf.abs(x)))
            return tf.sign(x / E) * E

    def fw2(x):
        E = tf.stop_gradient(tf.reduce_mean(tf.abs(x)))
        #clip_x = tf.clip_by_value(x, -E, E)
        #with G.gradient_override_map({"Floor": "Identity"}):
        #    return (tf.round(clip_x/E + 1) - 1)* E
        with G.gradient_override_map({"Sign": "Identity"}):
            return 0.5 * E * (tf.sign(x / E - 0.7) + tf.sign(x / E + 0.7))

    def fw4(x):
        x = tf.tanh(x)
        x = x / tf.reduce_max(tf.abs(x))
        return  quantize(x, 4)

    def fw8(x):
        x = tf.tanh(x)
        x = x / tf.reduce_max(tf.abs(x))
        return  quantize(x, 8)

    def fa(x):
        if bitA == 32:
            return x
        return quantize(x, bitA)

    global GRAD_DEFINED
    if not GRAD_DEFINED:
        @tf.RegisterGradient("FGGrad")
        def grad_fg(op, x):
            rank = x.get_shape().ndims
            assert rank is not None
            maxx = tf.reduce_max(tf.abs(x), list(range(1,rank)), keep_dims=True)
            x = x / maxx
            n = float(2**bitG-1)
            x = x * 0.5 + 0.5 + tf.random_uniform(
                    tf.shape(x), minval=-0.5/n, maxval=0.5/n)
            x = tf.clip_by_value(x, 0.0, 1.0)
            x = quantize(x, bitG) - 0.5
            return x * maxx * 2
    GRAD_DEFINED = True

    def fg(x):
        if bitG == 32:
            return x
        with G.gradient_override_map({"Identity": "FGGrad"}):
            return tf.identity(x)
    return fw1, fw2, fw4, fw8, fa, fg

