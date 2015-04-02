#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Learn sentiment-specific word embeddings from tweets.

Author: Giuseppe Attardi
"""

import logging
import numpy as np
import argparse
from ConfigParser import ConfigParser

# allow executing from anywhere without installing the package
import sys
import os
import distutils.util
builddir = os.path.dirname(os.path.realpath(__file__)) + '/../build/lib.'
libdir = builddir + distutils.util.get_platform() + '-' + '.'.join(map(str, sys.version_info[:2]))
sys.path.append(libdir)

# local
from deepnl import *
from deepnl.extractors import *
from deepnl.reader import TweetReader
from deepnl.network import Network
from deepnl.sentiwords import SentimentTrainer

# ----------------------------------------------------------------------
# Auxiliary functions

def create_trainer(args, converter):
    """
    Creates or loads a neural network according to the specified args.
    """

    logger = logging.getLogger("Logger")

    if args.load:
        logger.info("Loading provided network...")
        trainer = SentimentTrainer.load(args.load)
        trainer.learning_rate = args.learning_rate
    else:
        logger.info('Creating new network...')
        trainer = SentimentTrainer(converter, args.learning_rate,
                                   args.window/2, args.window/2,
                                   args.hidden, args.ngrams, args.alpha)

    trainer.saver = saver(args.output, args.vectors)

    logger.info("... with the following parameters:")
    logger.info(trainer.nn.description())
    
    return trainer

def saver(model_file, vectors_file):
    """Function for saving model periodically"""
    def save(trainer):
        # save embeddings also separately
        if vector_file:
            trainer.save_vectors(vectors_file)
        trainer.save(model_file)
    return save

# ----------------------------------------------------------------------

if __name__ == '__main__':

    # set the seed for replicability
    np.random.seed(42)

    defaults = {}
    
    parser = argparse.ArgumentParser(description="Learn word embeddings.")
    
    parser.add_argument('-c', '--config', dest='config_file',
                        help='Specify config file', metavar='FILE')

    # args, remaining_argv = parser.parse_known_args()

    # if args.config_file:
    #     config = ConfigParser.SafeConfigParser()
    #     config.read([args.config_file])
    #     defaults = dict(config.items('Defaults'))

    # parser.set_defaults(**defaults)

    parser.add_argument('-w', '--window', type=int, default=5,
                        help='Size of the word window (default 5)',
                             dest='window')
    parser.add_argument('-s', '--embeddings-size', type=int, default=50,
                        help='Number of features per word (default 50)',
                        dest='embeddings_size')
    parser.add_argument('-e', '--epochs', type=int, default=100,
                        help='Number of training epochs (default 100)',
                        dest='iterations')
    parser.add_argument('-l', '--learning-rate', type=float, default=0.001,
                        help='Learning rate for network weights (default 0.001)',
                        dest='learning_rate')
    parser.add_argument('-n', '--hidden', type=int, default=200,
                        help='Number of hidden neurons (default 200)')
    parser.add_argument('--ngrams', type=int, default=2,
                        help='Length of ngrams (default 2)')
    parser.add_argument('--alpha', type=float, default=0.5,
                        help='Relative weight of normal wrt sentiment score (default 0.5)')
    parser.add_argument('--train', type=str, default=None,
                        help='File with text corpus for training.',
                        required=True)
    parser.add_argument('-o', '--output', type=str, default=None,
                        help='File where to save embeddings')
    parser.add_argument('--vocab', type=str, default=None,
                        help='Vocabulary file, either read or created')
    parser.add_argument('--vectors', type=str, default=None,
                        help='Embeddings file, either read or created')
    parser.add_argument('--load', type=str, default=None,
                        help='Load previously saved model')
    parser.add_argument('--threads', type=int, default=1,
                        help='Number of threads (default 1)')
    parser.add_argument('--variant', type=str, default=None,
                        help='Either "senna" (default), "polyglot", "word2vec" or "gensym".')
    parser.add_argument('-v', '--verbose', help='Verbose mode',
                        action='store_true')

    args = parser.parse_args()

    log_format = '%(message)s'
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(format=log_format, level=log_level)
    logger = logging.getLogger("Logger")

    config = ConfigParser()
    if args.config_file:
        config.read(args.config_file)

    # merge args with config

    reader = TweetReader(args.ngrams)
    reader.read(args.train)
    loaded_vocab = False
    if args.vocab and os.path.exists(args.vocab):
        loaded_vocab = True
        vocab = reader.load_vocabulary(args.vocab)
    else:
        vocab = reader.create_vocabulary(reader.sentences)
    tokens = []
    for l in vocab: tokens.extend(l) # flatten ngrams dictionaries
    embeddings = Embeddings(args.embeddings_size, vocab=tokens,
                            variant=args.variant)

    converter = Converter()
    converter.add_extractor(embeddings)

    trainer = create_trainer(args, converter)

    report_intervals = max(args.iterations / 200, 1)
    report_intervals = 10000    # DEBUG

    logger.info("Starting training")

    # a generator expression (can be iterated several times)
    # It caches converted sentences, avoiding repeated conversions
    converted_sentences = converter.generator(reader.sentences, cache=True)
    trainer.train(converted_sentences, args.iterations, report_intervals,
                  reader.polarities, embeddings.dict)
    
    logger.info("Saving trained model ...")
    
    if args.vocab and not loaded_vocab:
        embeddings.save_vocabulary(args.vocab)
    if args.vectors:
        embeddings.save_vectors(args.vectors)
    trainer.save(args.output)
    logger.info("... to %s" % args.output)
