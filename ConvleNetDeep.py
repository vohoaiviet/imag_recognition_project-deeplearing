"""This tutorial introduces the LeNet5 neural network architecture
using Theano.  LeNet5 is a convolutional neural network, good for
classifying images. This tutorial shows how to build the architecture,
and comes with all the hyper-parameters you need to reproduce the
paper's MNIST results.


This implementation simplifies the model in the following ways:

 - LeNetConvPool doesn't implement location-specific gain and bias parameters
 - LeNetConvPool doesn't implement pooling by average, it implements pooling
   by max.
 - Digit classification is implemented with a logistic regression rather than
   an RBF network
 - LeNet5 was not fully-connected convolutions at second layer

References:
 - Y. LeCun, L. Bottou, Y. Bengio and P. Haffner:
   Gradient-Based Learning Applied to Document
   Recognition, Proceedings of the IEEE, 86(11):2278-2324, November 1998.
   http://yann.lecun.com/exdb/publis/pdf/lecun-98.pdf

"""

from __future__ import print_function

import os
import sys
import timeit
import pandas
import matplotlib.pyplot as plt
import numpy

from scipy.cluster.vq import whiten
from theano.tensor.nnet import relu

import theano
import theano.tensor as T
from theano.tensor.signal import downsample
from theano.tensor.nnet import conv2d

from LogisticRegression import LogisticRegression
from MLP import HiddenLayer
from unpickle import unpickle


class LeNetConvPoolLayer(object):
    """Pool Layer of a convolutional network """

    def __init__(self, rng, input, filter_shape, image_shape, poolsize=(2, 2)):
        """
        Allocate a LeNetConvPoolLayer with shared variable internal parameters.

        :type rng: numpy.random.RandomState
        :param rng: a random number generator used to initialize weights

        :type input: theano.tensor.dtensor4
        :param input: symbolic image tensor, of shape image_shape

        :type filter_shape: tuple or list of length 4
        :param filter_shape: (number of filters, num input feature maps,
                              filter height, filter width)

        :type image_shape: tuple or list of length 4
        :param image_shape: (batch size, num input feature maps,
                             image height, image width)

        :type poolsize: tuple or list of length 2
        :param poolsize: the downsampling (pooling) factor (#rows, #cols)
        """

        assert image_shape[1] == filter_shape[1]
        self.input = input

        # there are "num input feature maps * filter height * filter width"
        # inputs to each hidden unit
        fan_in = numpy.prod(filter_shape[1:])
        # each unit in the lower layer receives a gradient from:
        # "num output feature maps * filter height * filter width" /
        #   pooling size
        fan_out = (filter_shape[0] * numpy.prod(filter_shape[2:]) //
                   numpy.prod(poolsize))
        # initialize weights with random weights
        W_bound = numpy.sqrt(6. / (fan_in + fan_out))
        self.W = theano.shared(
            numpy.asarray(
                rng.uniform(low=-W_bound, high=W_bound, size=filter_shape),
                dtype=theano.config.floatX
            ),
            borrow=True
        )

        # the bias is a 1D tensor -- one bias per output feature map
        b_values = numpy.zeros((filter_shape[0],), dtype=theano.config.floatX)
        self.b = theano.shared(value=b_values, borrow=True)

        # convolve input feature maps with filters
        conv_out = conv2d(
            input=input,
            filters=self.W,
            filter_shape=filter_shape,
            image_shape=image_shape
        )

        # downsample each feature map individually, using maxpooling
        pooled_out = downsample.max_pool_2d(
            input=conv_out,
            ds=poolsize,
            ignore_border=True
        )

        # add the bias term. Since the bias is a vector (1D array), we first
        # reshape it to a tensor of shape (1, n_filters, 1, 1). Each bias will
        # thus be broadcasted across mini-batches and feature map
        # width & height
        self.output = relu(pooled_out + self.b.dimshuffle('x', 0, 'x', 'x'))

        # store parameters of this layer
        self.params = [self.W, self.b]

        # keep track of model input
        self.input = input


def evaluate_lenet5(learning_rate=0.15, n_epochs=200,
                    dataset='mnist.pkl.gz',
                    nkerns=[32, 32, 64], batch_size=500):
    """ Demonstrates lenet on CIFAR-10 dataset

    :type learning_rate: float
    :param learning_rate: learning rate used (factor for the stochastic
                          gradient)

    :type n_epochs: int
    :param n_epochs: maximal number of epochs to run the optimizer

    :type nkerns: list of ints
    :param nkerns: number of kernels on each layer
    """

    rng = numpy.random.RandomState(23455)

    def shared_dataset(data_xy, borrow=True):

        """ Function that loads the dataset into shared variables

        The reason we store our dataset in shared variables is to allow
        Theano to copy it into the GPU memory (when code is run on GPU).
        Since copying data into the GPU is slow, copying a minibatch everytime
        is needed (the default behaviour if the data is not in a shared
        variable) would lead to a large decrease in performance.
        """
        data_x, data_y = data_xy
        shared_x = theano.shared(numpy.asarray(data_x,
                                               dtype=theano.config.floatX),
                                 borrow=borrow)
        shared_y = theano.shared(numpy.asarray(data_y,
                                               dtype=theano.config.floatX),
                                 borrow=borrow)
        # When storing data on the GPU it has to be stored as floats
        # therefore we will store the labels as ``floatX`` as well
        # (``shared_y`` does exactly that). But during our computations
        # we need them as ints (we use labels as index, and if they are
        # floats it doesn't make sense) therefore instead of returning
        # ``shared_y`` we will have to cast it to int. This little hack
        # lets ous get around this issue
        return shared_x, T.cast(shared_y, 'int32')

    data_batch_1 = unpickle('cifar-10-batches-py/data_batch_1')
    data_batch_2 = unpickle('cifar-10-batches-py/data_batch_2')
    data_batch_3 = unpickle('cifar-10-batches-py/data_batch_3')
    data_batch_4 = unpickle('cifar-10-batches-py/data_batch_4')
    data_batch_5 = unpickle('cifar-10-batches-py/data_batch_5')
    test = unpickle('cifar-10-batches-py/test_batch')

    train_set_1 = data_batch_1["data"]
    train_set_2 = data_batch_2["data"]
    train_set_3 = data_batch_3["data"]
    train_set_4 = data_batch_4["data"]
    train_set_5 = data_batch_5["data"]
    X_train = numpy.concatenate((train_set_1, train_set_2, train_set_3, train_set_4, train_set_5), axis=0)

    y_train = numpy.concatenate((data_batch_1["labels"], data_batch_2["labels"], data_batch_3["labels"],
                                 data_batch_4["labels"], data_batch_5["labels"]))

    test_set = test["data"]
    Xte_rows = test_set.reshape(train_set_1.shape[0], 32 * 32 * 3)
    Yte = numpy.asarray(test["labels"])

    Xval_rows = X_train[:7500, :]  # take first 1000 for validation
    Yval = y_train[:7500]
    Xtr_rows = X_train[7500:50000, :]  # keep last 49,000 for train
    Ytr = y_train[7500:50000]

    mean_train = Xtr_rows.mean(axis=0)
    stdv_train = Xte_rows.std(axis=0)
    Xtr_rows = (Xtr_rows - mean_train) / stdv_train
    Xval_rows = (Xval_rows - mean_train) / stdv_train
    Xte_rows = (Xte_rows - mean_train) / stdv_train
    learning_rate = theano.shared(learning_rate)

    """whitening"""

    """
    Xtr_rows -= numpy.mean(Xtr_rows, axis=0) # zero-center the data (important)
    cov = numpy.dot(Xtr_rows.T, Xtr_rows) / Xtr_rows.shape[0]
    U,S,V = numpy.linalg.svd(cov)

    Xrot = numpy.dot(Xtr_rows, U)# decorrelate the data
    Xrot_reduced = numpy.dot(Xtr_rows, U[:,:100])

    # whiten the data:
    # divide by the eigenvalues (which are square roots of the singular values)
    Xwhite = Xrot / numpy.sqrt(S + 1e-5)"""

    """whitening"""

    #Xtr_rows = whiten(Xtr_rows)
    # zero-center the data (important)
    """cov = numpy.dot(Xtr_rows.T, Xtr_rows) / Xtr_rows.shape[0]
    U,S,V = numpy.linalg.svd(cov)

    Xrot = numpy.dot(Xtr_rows, U)

    Xtr_rows = Xrot / numpy.sqrt(S + 1e-5)

    Xval_rot = numpy.dot(Xval_rows,U)
    Xval_rows = Xval_rot / numpy.sqrt(S + 1e-5)

    Xte_rot = numpy.dot(Xte_rows,U)
    Xte_rows = Xte_rot / numpy.sqrt(S + 1e-5)
    """

    train_set = (Xtr_rows, Ytr)
    valid_set = (Xval_rows, Yval)
    test_set = (Xte_rows, Yte)

    test_set_x, test_set_y = shared_dataset(test_set)
    valid_set_x, valid_set_y = shared_dataset(valid_set)
    train_set_x, train_set_y = shared_dataset(train_set)
    datasets = [(train_set_x, train_set_y), (valid_set_x, valid_set_y),
                (test_set_x, test_set_y)]

    train_set_x, train_set_y = datasets[0]
    valid_set_x, valid_set_y = datasets[1]
    test_set_x, test_set_y = datasets[2]

    # compute number of minibatches for training, validation and testing
    n_train_batches = train_set_x.get_value(borrow=True).shape[0]
    n_valid_batches = valid_set_x.get_value(borrow=True).shape[0]
    n_test_batches = test_set_x.get_value(borrow=True).shape[0]
    n_train_batches //= batch_size
    n_valid_batches //= batch_size
    n_test_batches //= batch_size

    # allocate symbolic variables for the data
    index = T.lscalar()  # index to a [mini]batch

    # start-snippet-1
    x = T.matrix('x')   # the data is presented as rasterized images
    y = T.ivector('y')  # the labels are presented as 1D vector of [int] labels

    ######################
    # BUILD ACTUAL MODEL #
    ######################
    print('... building the model')

    # Reshape matrix of rasterized images of shape (batch_size, 28 * 28)
    # to a 4D tensor, compatible with our LeNetConvPoolLayer
    # (28, 28) is the size of MNIST images.
    layer0_input = x.reshape((batch_size, 3, 32, 32))

    # Construct the first convolutional pooling layer:
    # filtering reduces the image size to (32-5+1 , 32-5+1) = (28, 28)
    # maxpooling reduces this further to (28/2, 28/2) = (14, 14)
    # 4D output tensor is thus of shape (batch_size, nkerns[0], 14, 14)
    layer0 = LeNetConvPoolLayer(
        rng,
        input=layer0_input,
        image_shape=(batch_size, 3, 32, 32),
        filter_shape=(nkerns[0], 3, 5, 5),
        poolsize=(2, 2)
    )

    # Construct the second convolutional pooling layer
    # filtering reduces the image size to (14-5+1, 14-5+1) = (10, 10)
    # maxpooling reduces this further to (10/2, 10/2) = (5, 5)
    # 4D output tensor is thus of shape (batch_size, nkerns[1], 5, 5)
    layer1 = LeNetConvPoolLayer(
        rng,
        input=layer0.output,
        image_shape=(batch_size, nkerns[0], 14, 14),
        filter_shape=(nkerns[1], nkerns[0], 5, 5),
        poolsize=(2, 2)
    )

    # Construct the third convolutional pooling layer
    # filtering reduces the image size to (5-2+1, 5-2+1) = (4, 4)
    # maxpooling reduces this further to (4/2, 4/2) = (2, 2)
    # 4D output tensor is thus of shape (batch_size, nkerns[2], 2, 2)

    layer2conv = LeNetConvPoolLayer(
     rng,
        input=layer1.output,
        image_shape=(batch_size, nkerns[1], 5, 5),
        filter_shape=(nkerns[2], nkerns[1], 2, 2),
        poolsize=(2, 2)
    )


    # the HiddenLayer being fully-connected, it operates on 2D matrices of
    # shape (batch_size, num_pixels) (i.e matrix of rasterized images).
    # This will generate a matrix of shape (batch_size, nkerns[1] * 4 * 4),
    # or (500, 50 * 4 * 4) = (500, 800) with the default values.
    layer2_input = layer2conv.output.flatten(2)

    print (layer2_input.shape)
    # construct a fully-connected sigmoidal layer
    layer2 = HiddenLayer(
        rng,
        input=layer2_input,
        n_in=nkerns[2] * 2 * 2,
        n_out=500,
        activation=relu
    )

    # classify the values of the fully-connected sigmoidal layer
    layer3 = LogisticRegression(input=layer2.output, n_in=500, n_out=10)

    # the cost we minimize during training is the NLL of the model
    L2_reg = 0.01
    L2_sqr = (
            (layer2.W ** 2).sum() + (layer2conv.W ** 2).sum()
             + (layer3.W ** 2).sum()
        )

    cost = layer3.negative_log_likelihood(y) + L2_reg * L2_sqr

    # create a function to compute the mistakes that are made by the model
    test_model = theano.function(
        [index],
        layer3.errors(y),
        givens={
            x: test_set_x[index * batch_size: (index + 1) * batch_size],
            y: test_set_y[index * batch_size: (index + 1) * batch_size]
        }
    )

    validate_model = theano.function(
        [index],
        layer3.errors(y),
        givens={
            x: valid_set_x[index * batch_size: (index + 1) * batch_size],
            y: valid_set_y[index * batch_size: (index + 1) * batch_size]
        }
    )

    # create a list of all model parameters to be fit by gradient descent
    params = layer3.params + layer2.params + layer1.params + layer0.params

    # create a list of gradients for all model parameters
    grads = T.grad(cost, params)

    # train_model is a function that updates the model parameters by
    # SGD Since this model has many parameters, it would be tedious to
    # manually create an update rule for each model parameter. We thus
    # create the updates list by automatically looping over all
    # (params[i], grads[i]) pairs.
    updates = [
        (param_i, param_i - learning_rate * grad_i)
        for param_i, grad_i in zip(params, grads)
    ]

    train_model = theano.function(
        [index],
        cost,
        updates=updates,
        givens={
            x: train_set_x[index * batch_size: (index + 1) * batch_size],
            y: train_set_y[index * batch_size: (index + 1) * batch_size]
        }
    )
    # end-snippet-1

    ###############
    # TRAIN MODEL #
    ###############
    print('... training')
    # early-stopping parameters
    patience = 10000  # look as this many examples regardless
    patience_increase = 2  # wait this much longer when a new best is
                           # found
    improvement_threshold = 0.995  # a relative improvement of this much is
                                   # considered significant
    validation_frequency = min(n_train_batches, patience // 2)
                                  # go through this many
                                  # minibatche before checking the network
                                  # on the validation set; in this case we
                                  # check every epoch

    best_validation_loss = numpy.inf
    best_iter = 0
    test_score = 0.
    start_time = timeit.default_timer()

    epoch = 0
    done_looping = False

    epoch_loss_list = []
    epoch_val_list = []

    while (epoch < n_epochs) and (not done_looping):
        epoch += 1
        if epoch == 10:
            learning_rate.set_value(0.1)
        if epoch >= 18 and learning_rate.get_value() >= 0.1 * (0.9 ** 6):
           learning_rate.set_value(learning_rate.get_value()*0.9)
        if epoch > 3:
            epoch_loss_np = numpy.reshape(epoch_loss_list, newshape=(len(epoch_loss_list), 3))
            epoch_val_np = numpy.reshape(epoch_val_list, newshape=(len(epoch_val_list), 3))
            numpy.savetxt(fname='epoc_cost.csv', X=epoch_loss_np,
                          fmt='%1.3f')
            numpy.savetxt(fname='epoc_val_error.csv', X=epoch_val_np,
                          fmt='%1.3f')

        for minibatch_index in range(n_train_batches):

            iter = (epoch - 1) * n_train_batches + minibatch_index

            if iter % 100 == 0:
                print('training @ iter = ', iter)
            cost_ij = train_model(minibatch_index)

            epoch_loss_entry = [iter, epoch, float(cost_ij)]
            epoch_loss_list.append(epoch_loss_entry)

            if (iter + 1) % validation_frequency == 0:

                # compute zero-one loss on validation set
                validation_losses = [validate_model(i) for i
                                     in range(n_valid_batches)]
                this_validation_loss = numpy.mean(validation_losses)
                print('epoch %i, minibatch %i/%i, validation error %f %%' %
                      (epoch, minibatch_index + 1, n_train_batches,
                       this_validation_loss * 100.))
                epoch_val_entry = [iter, epoch, this_validation_loss]
                epoch_val_list.append(epoch_val_entry)

                # if we got the best validation score until now
                if this_validation_loss < best_validation_loss:
                    # improve patience if loss improvement is good enough
                    if this_validation_loss < best_validation_loss *  \
                       improvement_threshold:
                        patience = max(patience, iter * patience_increase)

                    # save best validation score and iteration number
                    best_validation_loss = this_validation_loss
                    best_iter = iter

                    # test it on the test set
                    test_losses = [
                        test_model(i)
                        for i in range(n_test_batches)
                    ]
                    test_score = numpy.mean(test_losses)
                    print(('     epoch %i, minibatch %i/%i, test error of '
                           'best model %f %%') %
                          (epoch, minibatch_index + 1, n_train_batches,
                           test_score * 100.))

            if patience <= iter:
                done_looping = True
                break

    end_time = timeit.default_timer()
    print('Optimization complete.')
    print('Best validation score of %f %% obtained at iteration %i, '
          'with test performance %f %%' %
          (best_validation_loss * 100., best_iter + 1, test_score * 100.))
    print(('The code for file ' +
           os.path.split(__file__)[1] +
           ' ran for %.2fm' % ((end_time - start_time) / 60.)), file=sys.stderr)

    epoch_loss_np = numpy.reshape(epoch_loss_list, newshape=(len(epoch_loss_list), 3))
    epoch_val_np = numpy.reshape(epoch_val_list, newshape=(len(epoch_val_list), 3))

    epoch_loss = pandas.DataFrame({"iter": epoch_loss_np[:, 0], "epoch": epoch_loss_np[:, 1],
                                   "cost": epoch_loss_np[:, 2]})
    epoch_vall = pandas.DataFrame({"iter": epoch_val_np[:, 0], "epoch": epoch_val_np[:, 1],
                                   "val_error": epoch_val_np[:, 2]})
    epoc_avg_loss = pandas.DataFrame(epoch_loss.groupby(['epoch']).mean()["cost"])
    epoc_avg_val = pandas.DataFrame(epoch_vall.groupby(['epoch']).mean()["val_error"])
    epoc_avg_loss = pandas.DataFrame({"epoch": epoc_avg_loss.index.values, "cost": epoc_avg_loss["cost"]})
    epoc_avg_loss_val = pandas.DataFrame({"epoch": epoc_avg_val.index.values, "val_error": epoc_avg_val["val_error"]})
    epoc_avg_loss.plot(kind="line", x="epoch", y="cost")
    plt.show()
    epoc_avg_loss_val.plot(kind='line', x="epoch", y="val_error")
    plt.show()

if __name__ == '__main__':
    evaluate_lenet5()


def experiment(state, channel):
    evaluate_lenet5(state.learning_rate, dataset=state.dataset)