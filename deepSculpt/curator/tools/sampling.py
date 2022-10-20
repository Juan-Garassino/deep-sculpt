import os
from deepSculpt.curator.curator import DataLoaderCreator
from deepSculpt.source.preprocessing import OneHotEncoderDecoder
from colorama import Fore, Style
import numpy as np
from tensorflow.data import Dataset
from deepSculpt.tools.params import BUFFER_SIZE
import tensorflow as tf


def sampling():  # convert to spare tensor

    # Loads the data
    if int(os.environ.get("CREATE_DATA")) == 0:

        data = DataLoaderCreator(
            path_volumes=os.environ.get("FILE_TO_LOAD_VOLUMES"),
            path_colors=os.environ.get("FILE_TO_LOAD_COLORS"),
        )

        if int(os.environ.get("INSTANCE")) == 1:
            volumes, colors = data.load_locally()

        else:
            volumes, colors = data.load_from_gcp()

    # Creates the data
    if int(os.environ.get("CREATE_DATA")) == 1:

        data = DataLoaderCreator()

        volumes, colors = data.create_sculpts(
            n_samples=int(os.environ.get("N_SAMPLES_CREATE")),
            n_edge_elements=0,
            n_plane_elements=2,
            n_volume_elements=2,
            color_edges="dimgrey",
            color_planes="snow",
            color_volumes=["crimson", "turquoise", "gold"],
            verbose=False,
            void_dim=int(os.environ.get("VOID_DIM")),
        )

    if isinstance(colors, np.ndarray) == False:
        print("error")

    # Preproccess the data
    preprocessing_class_o = OneHotEncoderDecoder(colors)

    o_encode, o_classes = preprocessing_class_o.ohe_encoder()

    print(
        "\n⏹ "
        + Fore.YELLOW
        + "Just preproccess data from shape {} to {}".format(
            colors.shape, o_encode.shape
        )
        + Style.RESET_ALL
    )

    print(
        "\n⏹ " + Fore.YELLOW + "The classes are: {}".format(o_classes) + Style.RESET_ALL
    )

    # o_encode = tf.sparse.from_dense(o_encode)

    # Creates the dataset
    train_dataset = (
        Dataset.from_tensor_slices(o_encode)
        .shuffle(BUFFER_SIZE)
        .take(int(os.environ.get("TRAIN_SIZE")))
        .batch(int(os.environ.get("BATCH_SIZE")))
    )

    return train_dataset, preprocessing_class_o
