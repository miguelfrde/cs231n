import multiprocessing
import os
import re
import _pickle as pickle

import tensorflow as tf
import tensorflow.contrib.slim.nets
import numpy as np

from models import spotify


PATH_MAGNATAGATUNE = 'datasets/magnatagatune'

INPUT_SHAPE = (628, 128)
CLASSES = [
    'classical', 'instrumental', 'electronica', 'techno',
    'male voice', 'rock', 'ambient', 'female voice', 'opera',
    'indian', 'choir', 'pop', 'heavy metal', 'jazz', 'new age',
    'dance', 'country', 'eastern', 'baroque', 'funk', 'hard rock',
    'trance', 'folk', 'oriental', 'medieval', 'irish', 'blues',
    'middle eastern', 'punk', 'celtic', 'arabic', 'rap',
    'industrial', 'world', 'hip hop', 'disco', 'soft rock',
    'jungle', 'reggae', 'happy',
]
BATCH_SIZE = 32
EPOCHS = 100
LEARNING_RATE = 1e-3
NUM_WORKERS = multiprocessing.cpu_count()


def _load_pickle(filename):
    with open(filename, 'rb') as f:
        return pickle.load(f)

def _list_dataset(dataset_name):
    dataset_path = os.path.join(PATH_MAGNATAGATUNE, dataset_name)
    labels_file = os.path.join(dataset_path, 'labels.pickle')
    filenames = [os.path.join(dataset_path, '%d.pickle') % i for i, f in enumerate(os.listdir(dataset_path))
                 if re.match(r'\d+\.pickle', f)]
    labels = _load_pickle(labels_file)
    return filenames, np.asarray(labels)


def _parse_function(filename, label):
    spectogram = tf.cast(_load_pickle(filename), tf.float32)
    return spectogram, label


def _init_datasets(train_filenames, val_filenames, train_labels, val_labels):
    train_filenames = tf.constant(train_filenames)
    train_labels = tf.constant(train_labels)
    train_dataset = tf.contrib.data.Dataset.from_tensor_slices((train_filenames, train_labels))
    print(train_dataset.output_types)
    print(train_dataset.output_shapes)
    train_dataset = train_dataset.map(
        lambda filename, label: tf.py_func(
                _parse_function, [filename, label], [tf.float32, label.dtype]),
        num_threads=NUM_WORKERS, output_buffer_size=BATCH_SIZE)
    print(train_dataset.output_types)
    print(train_dataset.output_shapes)
    train_dataset = train_dataset.shuffle(buffer_size=10000)
    batched_train_dataset = train_dataset.batch(BATCH_SIZE)
    print(batched_train_dataset.output_types)
    print(batched_train_dataset.output_shapes)

    iterator = tf.contrib.data.Iterator.from_structure(
        batched_train_dataset.output_types, batched_train_dataset.output_shapes)
    spectograms, labels = iterator.get_next()

    train_init_op = iterator.make_initializer(batched_train_dataset)
    #val_init_op = iterator.make_initializer(batched_val_dataset)

    return spectograms, labels, train_init_op, None


def main():
    train_filenames, train_labels = _list_dataset('train')
    val_filenames, val_labels = _list_dataset('val')

    graph = tf.Graph()
    with graph.as_default():
        spectograms, labels, train_init_op, val_init_op = _init_datasets(
            train_filenames, val_filenames, train_labels, val_labels)

        is_training = tf.placeholder(tf.bool)
        output_layer = spotify.get_tf(spectograms, len(CLASSES), activation='sigmoid')
        #output_layer = tf.contrib.slim.nets.vgg.vgg_16(spectograms, num_classes=len(CLASSES))

        tf.losses.mean_squared_error(labels=labels, predictions=output_layer)
        loss = tf.losses.get_total_loss()

        optimizer =  tf.train.GradientDescentOptimizer(LEARNING_RATE)
        train_op = optimizer.minimize(loss)

        correct_prediction = tf.equal(
            tf.round(tf.nn.sigmoid(output_layer)),
            tf.round(tf.cast(labels, tf.float32)))
        accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))
        tf.get_default_graph().finalize()

        with tf.Session(graph=graph) as sess:
            for epoch in range(EPOCHS):
                print('Epoch %d / %d' % (epoch + 1, EPOCHS))
                sess.run(train_init_op)
                while True:
                    try:
                        _ = sess.run(train_op, {is_training: True})
                    except tf.errors.OutOfRangeError:
                        break

                # Check accuracy on the train and val sets every epoch
                train_acc = check_accuracy(sess, correct_prediction, is_training, train_init_op)
                val_acc = check_accuracy(sess, correct_prediction, is_training, val_init_op)
                print('  Train accuracy: %f' % train_acc)
                print('  Val accuracy: %f\n' % val_acc)


if __name__ == '__main__':
    main()
