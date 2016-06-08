#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
Usage:
python ffnn_pointwise.txt config.ini
'''

import sys
import os
import chainer
import numpy as np
import configparser
import chainer.functions as F
from chainer import optimizers


def create_vocab():
    vocab = dict()
    for f in [train_file, test_file]:
        for line in open(f):
            for char in ''.join(line.strip().split()):
                if char not in vocab:
                    vocab[char] = len(vocab)
    vocab['<s>'] = len(vocab)
    vocab['</s>'] = len(vocab)
    return vocab

def init_model(vocab_size):
    model = chainer.FunctionSet(
        embed=F.EmbedID(vocab_size, embed_units),
        hidden1=F.Linear(window * embed_units, hidden_units),
        output=F.Linear(hidden_units, label_num),
    )
    opt = optimizers.AdaGrad(lr=learning_rate)
    opt.setup(model)
    return model, opt

def make_label(sent):
    labels = list()
    pre_char = ' '
    if label_num == 2: # BI
        for char in sent:
            if not char == ' ':
                if pre_char == ' ':
                    labels.append(0)
                elif not pre_char == ' ':
                    labels.append(1)
            pre_char = char
    return labels

def label2seq(x, labels):
    seq = list()
    for i in range(len(x)):
        if label_num == 2:
            if i == 0:
                seq.append(x[i])
            elif labels[i] == 0:
                seq.append(' ')
                seq.append(x[i])
            else:
                seq.append(x[i])
    return seq


def train(char2id, model, optimizer):
    print('####Training####')
    train_flag = True
    for epoch in range(n_epoch):
        batch_count = 0
        accum_loss = 0
        line_cnt = 0
        for line in open(train_file):
            line_cnt += 1
            print("####epoch: {0} trainig sentence: {1}".format(epoch,\
                                                 line_cnt), '\r', end='')
            x = ''.join(line.strip().split())
            t = make_label(line.strip())
            for target in range(len(x)):
                label = t[target]
                pred, loss = forward_one(x, target, label, train_flag)
                accum_loss += loss
                #print('loss:',loss.data)
            #print('accum loss', accum_loss.data)
            batch_count += 1
            if batch_count == batch_size:
                optimizer.zero_grads()
                accum_loss.backward()
                optimizer.weight_decay(lam)
                optimizer.update()
                accum_loss = 0
                batch_count = 0
     
        if not batch_count == 0:
            optimizer.zero_grads()
            accum_loss.backward()
            optimizer.weight_decay(lam)
            optimizer.update()
            accum_loss = 0
            batch_count = 0
        epoch_test(char2id, model, epoch)
    print('\nTraining Done!')


def epoch_test(char2id, model, epoch):
    train_flag = False
    labels = list()
    line_cnt = 0
    result_file = '{0}_{1}.txt'.format(result_raw.split('.txt')[0], epoch)
    for line in open(test_file):
        line_cnt += 1
        print('####epoch: {0} test and evaluation sentence: {1}####'\
                        .format(epoch,line_cnt), '\r', end = '')
        x = ''.join(line.strip().split())
        t = make_label(line.strip())
        dists = list()
        for target in range(len(x)):
            label = t[target]
            labels.append(label)
            dist, acc = forward_one(x, target, label, train_flag)
            dists.append(dist)
        with open(result_file, 'a') as test:
            test.write("{0}\n".format(''.join(label2seq(x, dists))))
        labels = list()
    os.system('bash eval_japanese_ws.sh {0} {1} > temp'\
                                            .format(result_file, test_file))
    os.system('echo "####epoch{0} evaluation####" >> {1}'\
                                            .format(epoch, evaluation))
    os.system('cat temp >> {0}'.format(evaluation))
    os.system('rm temp')
        #print('predict sequence:', ''.join(label2seq(x,dists)))

def get_onehot(num):
    return chainer.Variable(np.array([num], dtype=np.int32))

def forward_one(x, target, label, train_flag):
    # make input window vector
    distance = window // 2
    char_vecs = list()
    x = list(x)
    for i in range(distance):
        x.append('</s>')
        x.insert(0,'<s>')
    for i in range(-distance+1 , distance + 2):
        char = x[target + i]
        char_id = char2id[char]
        char_vec = model.embed(get_onehot(char_id))
        char_vecs.append(char_vec)
    concat = F.concat(tuple(char_vecs))
    hidden = F.sigmoid(model.hidden1(concat))
    output = model.output(hidden)
    dist = F.softmax(output)
    correct = get_onehot(label)
    return np.argmax(dist.data), F.softmax_cross_entropy(output, correct)


if __name__ == '__main__':
    # reading config
    ini_file = sys.argv[1]
    ini = configparser.SafeConfigParser()
    ini.read(ini_file)
    train_file = ini.get('Data', 'train')
    test_file = ini.get('Data', 'test')
    result_raw = ini.get('Result', 'raw')
    config_file = ini.get('Result', 'config')
    evaluation = ini.get('Result', 'evaluation')
    window = int(ini.get('Parameters', 'window'))
    embed_units = int(ini.get('Parameters', 'embed_units'))
    hidden_units = int(ini.get('Parameters', 'hidden_units'))
    lam = float(ini.get('Parameters', 'lam'))
    label_num = int(ini.get('Settings', 'label_num'))
    batch_size = int(ini.get('Settings', 'batch_size'))
    learning_rate = float(ini.get('Parameters', 'learning_rate'))
    n_epoch = int(ini.get('Settings', 'n_epoch'))
    with open(config_file, 'w') as config:
        ini.write(config)

    char2id = create_vocab()
    model, opt = init_model(len(char2id))
    train(char2id, model, opt)
    #test(char2id, model)
