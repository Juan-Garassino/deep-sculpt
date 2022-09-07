import matplotlib.pyplot as plt
from IPython import display
import time
import warnings

warnings.filterwarnings("ignore")
import os

from tensorflow.data import Dataset
from tensorflow import GradientTape, function, Variable
from tensorflow.random import normal
from tensorflow.train import Checkpoint, CheckpointManager

from google.cloud import storage
from tensorflow import GradientTape, function

from deepSculpt.source.preprocessing import OneHotEncoderDecoder
from deepSculpt.source.data import DataLoaderCreator
from deepSculpt.model.model import (
    make_three_dimentional_generator,
    make_three_dimentional_critic,
)
from deepSculpt.model.losses import discriminator_loss, generator_loss
from deepSculpt.model.optimizers import generator_optimizer, discriminator_optimizer

from deepSculpt.utils.snapshots import generate_and_save_snapshot
from deepSculpt.utils.checkpoint import (
    generate_and_save_checkpoint,
    load_model_from_cgp,
)

from deepSculpt.utils.params import (
    BUFFER_SIZE,
    SEED,
    MINIBATCHES,
)

from colorama import Fore, Style

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

if int(os.environ.get("CREATE_DATA")) == 0:

    data = DataLoaderCreator(
        path_volumes=os.environ.get("FILE_TO_LOAD_VOLUMES"),
        path_colors=os.environ.get("FILE_TO_LOAD_COLORS"),
    )

    if int(os.environ.get("LOCALLY")) == 1:
        volumes, colors = data.load_locally()

    else:
        volumes, colors = data.load_from_gcp()

else:
    print("error")

preprocessing_class_o = OneHotEncoderDecoder(colors)

o_encode, o_classes = preprocessing_class_o.ohe_encoder()

print("\n⏹ " + Fore.YELLOW + "The classes are: {}".format(o_classes))

train_dataset = (
    Dataset.from_tensor_slices(o_encode)
    .shuffle(BUFFER_SIZE)
    .take(int(os.environ.get("TRAIN_SIZE")))
    .batch(int(os.environ.get("BATCH_SIZE")))
)

generator = make_three_dimentional_generator()

print("\n⏹ " + Fore.BLUE + "The Generators summary is" + Fore.YELLOW + "\n")

print(generator.summary())

discriminator = make_three_dimentional_critic()

print("\n⏹ " + Fore.BLUE + "The Discriminators summary is" + Fore.YELLOW + "\n")

print(discriminator.summary())

print(Style.RESET_ALL)


if os.environ.get("LOCALLY") and not os.environ.get("COLAB"):
    checkpoint_dir = (
        "/home/juan-garassino/code/juan-garassino/deepSculpt/results/checkpoints"
    )

if os.environ.get("LOCALLY") and os.environ.get("COLAB"):
    checkpoint_dir = (
        "/content/drive/MyDrive/repositories/deepSculpt/results/checkpoints"
    )

if not os.environ.get("LOCALLY"):
    checkpoint_dir = "gs://deepsculpt/checkpoints"

    # storage_location = f"results/{STORAGE_FILENAME}"

    bucket = storage.Client().bucket(os.environ.get("BUCKET_NAME"))

    # checkpoint_prefix = os.path.join(checkpoint_dir, "checkpoint")

checkpoint = Checkpoint(
    step=Variable(1),
    generator_optimizer=generator_optimizer,
    discriminator_optimizer=discriminator_optimizer,
    generator=generator,
    discriminator=discriminator,
)

manager = CheckpointManager(
    checkpoint=checkpoint,
    directory=checkpoint_dir,
    max_to_keep=3,
    checkpoint_name="checkpoint",
)


@function  # Notice the use of "tf.function" This annotation causes the function to be "compiled"
def train_step(images):  # train for just ONE STEP aka one forward and back propagation

    with GradientTape() as gen_tape, GradientTape() as disc_tape:  # get the gradient for each parameter for this step
        generated_images = generator(SEED, training=True)  # iterates over the noises

        real_output = discriminator(
            images, training=True
        )  # trains discriminator based on labeled real pics
        fake_output = discriminator(
            generated_images, training=True
        )  # trains discriminator based on labeled generated pics
        # why it doesnt traing all at ones

        gen_loss = generator_loss(
            fake_output
        )  # calculating the generator loss function previously defined
        disc_loss = discriminator_loss(
            real_output, fake_output
        )  # calculating the descrim loss function previously defined

    # print(f"gen loss : {gen_loss}")
    # print(f"gen loss : {disc_loss}")

    gradients_of_generator = gen_tape.gradient(gen_loss, generator.trainable_variables)
    # saving the gradients of each trainable variable of the generator

    gradients_of_discriminator = disc_tape.gradient(
        disc_loss, discriminator.trainable_variables
    )
    # saving the gradients of each trainable variable of the discriminator

    generator_optimizer.apply_gradients(
        zip(gradients_of_generator, generator.trainable_variables)
    )
    # applying the gradients on the trainable variables of the generator to update the parameters
    discriminator_optimizer.apply_gradients(
        zip(gradients_of_discriminator, discriminator.trainable_variables)
    )
    # applying the gradients on the trainable variables of the generator to update the parameters


def trainer(
    dataset, epochs, locally=os.environ.get("LOCALLY")
):  # load checkpoint, checkpoint + manager

    if not locally:
        load_model_from_cgp(checkpoint, manager)  # REEEEEESTOREEEEEE

    if manager.latest_checkpoint:
        print(
            "\n🔼 "
            + Fore.YELLOW
            + "Restored from {}...".format(manager.latest_checkpoint)
            + Style.RESET_ALL
        )
    else:
        print("\n⏹ " + Fore.GREEN + "Initializing from scratch" + Style.RESET_ALL)

    for epoch in range(epochs):

        start = time.time()

        print("\n⏩ " + Fore.RED + "Epoch number %d" % (epoch + 1,) + Style.RESET_ALL)

        for index, image_batch in enumerate(dataset):
            noise = normal(
                [int(os.environ.get("BATCH_SIZE")), int(os.environ.get("NOISE_DIM"))]
            )  # tf.random.normal([os.environ.get('BATCH_SIZE'), noise_dim]) # generate the noises [batch size, latent space 100 dimention vector]

            with GradientTape() as gen_tape, GradientTape() as disc_tape:  # get the gradient for each parameter for this step
                generated_images = generator(
                    noise, training=True
                )  # iterates over the noises

                real_output = discriminator(
                    image_batch, training=True
                )  # trains discriminator based on labeled real pics
                fake_output = discriminator(
                    generated_images, training=True
                )  # trains discriminator based on labeled generated pics
                # why it doesnt traing all at ones

                gen_loss = generator_loss(
                    fake_output
                )  # calculating the generator loss function previously defined
                disc_loss = discriminator_loss(
                    real_output, fake_output
                )  # calculating the descrim loss function previously defined

            if (index + 1) % MINIBATCHES[index]:
                minibatch_start = time.time()

                print(
                    "\n⏩ "
                    + Fore.MAGENTA
                    + "Minibatch number %d" % (index + 1,)
                    + Style.RESET_ALL
                    + "\n"
                )

                print(
                    "\nℹ️ "
                    + Fore.CYAN
                    + "Discriminator Loss: {:.4f}, Generator Loss: {:.4f}".format(
                        disc_loss, gen_loss
                    )
                    + Style.RESET_ALL
                )

                print(
                    "\n📶 "
                    + Fore.MAGENTA
                    + "Time for minibatches between {} and {} is {} sec".format(
                        index + 1,
                        index + 1 + int(os.environ.get("BATCH_SIZE")),
                        time.time() - minibatch_start,
                    )
                    + Style.RESET_ALL
                )

            gradients_of_generator = gen_tape.gradient(
                gen_loss, generator.trainable_variables
            )
            # saving the gradients of each trainable variable of the generator
            gradients_of_discriminator = disc_tape.gradient(
                disc_loss, discriminator.trainable_variables
            )
            # saving the gradients of each trainable variable of the discriminator

            generator_optimizer.apply_gradients(
                zip(gradients_of_generator, generator.trainable_variables)
            )
            # applying the gradients on the trainable variables of the generator to update the parameters
            discriminator_optimizer.apply_gradients(
                zip(gradients_of_discriminator, discriminator.trainable_variables)
            )
            # applying the gradients on the trainable variables of the generator to update the parameters

        # Produce images
        display.clear_output(wait=True)  # clearing output !!!TO BE CHECKED!!!
        # generate_and_save_images(generator, epoch + 1, seed)

        if os.environ.get("LOCALLY") and not os.environ.get("COLAB"):

            if (epoch + 1) % int(
                os.environ.get("MODEL_CHECKPOINT")
            ) == 0:  # Save the model every 15 epochs

                os.chdir(
                    "/home/juan-garassino/code/juan-garassino/deepSculpt/results/checkpoints"
                )

                save_path = manager.save()

                print(
                    "Saved checkpoint for step {}: {}".format(
                        int(checkpoint.step), save_path
                    )
                )

                # generate_and_save_checkpoint(
                #    checkpoint
                # )  # saving weights and biases previously calculated by the train step gradients

                checkpoint.step.assign_add(1)

            if (epoch + 1) % int(os.environ.get("PICTURE_SNAPSHOT")) == 0:
                os.chdir(
                    "/home/juan-garassino/code/juan-garassino/deepSculpt/results/snapshots"
                )
                generate_and_save_snapshot(
                    generator, epoch + 1, preprocessing_class_o, SEED
                )

        if os.environ.get("LOCALLY") and os.environ.get("COLAB"):

            if (epoch + 1) % int(
                os.environ.get("MODEL_CHECKPOINT")
            ) == 0:  # Save the model every 15 epochs

                os.chdir(
                    "/content/drive/MyDrive/repositories/deepSculpt/results/checkpoints"
                )

                save_path = manager.save()

                print(
                    "Saved checkpoint for step {}: {}".format(
                        int(checkpoint.step), save_path
                    )
                )

                # generate_and_save_checkpoint(
                #    checkpoint
                # )  # saving weights and biases previously calculated by the train step gradients

                checkpoint.step.assign_add(1)

            if (epoch + 1) % int(os.environ.get("PICTURE_SNAPSHOT")) == 0:
                os.chdir(
                    "/content/drive/MyDrive/repositories/deepSculpt/results/snapshots"
                )
                generate_and_save_snapshot(
                    generator, epoch + 1, preprocessing_class_o, SEED
                )

        if not os.environ.get("LOCALLY"):
            # Save the model every 15 epochs
            if (epoch + 1) % os.environ.get("MODEL_CHECKPOINT") == 0:
                generate_and_save_checkpoint(
                    checkpoint, manager, bucket
                )  # saving weights and biases previously calculated by the train step gradients
            if (epoch + 1) % int(os.environ.get("PICTURE_SNAPSHOT")) == 0:
                generate_and_save_snapshot(
                    generator, epoch + 1, preprocessing_class_o, SEED
                )

        print(
            "\n📶 "
            + Fore.MAGENTA
            + "Time for epoch {} is {} sec".format(epoch + 1, time.time() - start)
            + Style.RESET_ALL
        )

        plt.close("all")

    # Generate after the final epoch
    display.clear_output(wait=True)
    # generate_and_save_images(generator, epochs, seed)


if __name__ == "__main__":
    trainer(train_dataset, int(os.environ.get("EPOCHS")))
