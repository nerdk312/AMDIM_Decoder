import os
from enum import Enum

from PIL import Image
import numpy as np
import torch
from torchvision import datasets, transforms


INTERP = 3


class Dataset(Enum): # Nawid - Different number for each dataset
    C10 = 1
    C100 = 2
    STL10 = 3
    IN128 = 4
    PLACES205 = 5


def get_encoder_size(dataset): # Nawid - Different encoder size - The encoder size represents the size of the input into the encoder eg 32 x32 image
    if dataset in [Dataset.C10, Dataset.C100]:
        return 32
    if dataset == Dataset.STL10:
        return 64 # Nawid - Changed the image size from 64 to 128
    if dataset in [Dataset.IN128, Dataset.PLACES205]:
        return 128
    raise RuntimeError("Couldn't get encoder size, unknown dataset: {}".format(dataset))


def get_dataset(dataset_name): # Nawid- Obtains the dataset
    try:
        return Dataset[dataset_name.upper()]
    except KeyError as e:
        raise KeyError("Unknown dataset '" + dataset_name + "'. Must be one of "
                       + ', '.join([d.name for d in Dataset]))


class RandomTranslateWithReflect: # Nawid - Translates the image randomly
    '''
    Translate image randomly

    Translate vertically and horizontally by n pixels where
    n is integer drawn uniformly independently for each axis
    from [-max_translation, max_translation].

    Fill the uncovered blank area with reflect padding.
    '''

    def __init__(self, max_translation):
        self.max_translation = max_translation

    def __call__(self, old_image):
        xtranslation, ytranslation = np.random.randint(-self.max_translation,
                                                       self.max_translation + 1,
                                                       size=2)
        xpad, ypad = abs(xtranslation), abs(ytranslation)
        xsize, ysize = old_image.size

        flipped_lr = old_image.transpose(Image.FLIP_LEFT_RIGHT)
        flipped_tb = old_image.transpose(Image.FLIP_TOP_BOTTOM)
        flipped_both = old_image.transpose(Image.ROTATE_180)

        new_image = Image.new("RGB", (xsize + 2 * xpad, ysize + 2 * ypad))

        new_image.paste(old_image, (xpad, ypad))

        new_image.paste(flipped_lr, (xpad + xsize - 1, ypad))
        new_image.paste(flipped_lr, (xpad - xsize + 1, ypad))

        new_image.paste(flipped_tb, (xpad, ypad + ysize - 1))
        new_image.paste(flipped_tb, (xpad, ypad - ysize + 1))

        new_image.paste(flipped_both, (xpad - xsize + 1, ypad - ysize + 1))
        new_image.paste(flipped_both, (xpad + xsize - 1, ypad - ysize + 1))
        new_image.paste(flipped_both, (xpad - xsize + 1, ypad + ysize - 1))
        new_image.paste(flipped_both, (xpad + xsize - 1, ypad + ysize - 1))

        new_image = new_image.crop((xpad - xtranslation,
                                    ypad - ytranslation,
                                    xpad + xsize - xtranslation,
                                    ypad + ysize - ytranslation))
        return new_image


class TransformsC10: # Nawid - Transforms Cifar10
    def __init__(self):
        '''
        Apply the same input transform twice
        '''
        # flipping image along vertical axis
        self.flip_lr = transforms.RandomHorizontalFlip(p=0.5)
        # image augmentation functions
        normalize = transforms.Normalize(mean=[x / 255.0 for x in [125.3, 123.0, 113.9]],
                                         std=[x / 255.0 for x in [63.0, 62.1, 66.7]])
        col_jitter = transforms.RandomApply([
            transforms.ColorJitter(0.4, 0.4, 0.4, 0.2)], p=0.8)
        img_jitter = transforms.RandomApply([
            RandomTranslateWithReflect(4)], p=0.8)
        rnd_gray = transforms.RandomGrayscale(p=0.25)
        # main transform for self-supervised training
        '''
        self.train_transform = transforms.Compose([
            img_jitter,
            col_jitter,
            rnd_gray,
            transforms.ToTensor(),
            normalize
        ])
        '''
        # transform for testing
        self.train_transform = transforms.Compose([
            transforms.ToTensor(),
            normalize
        ])

        
        # transform for testing
        self.test_transform = transforms.Compose([
            transforms.ToTensor(),
            normalize
        ])

    def __call__(self, inp): # Nawid-  Input is an image which goes through a random transformation each
        inp = self.flip_lr(inp)
        out1 = self.train_transform(inp)
        out2 = self.train_transform(inp)
        return out1, out2

'''
class TransformsC10:
    def __init__(self):
        normalize = transforms.Normalize(mean=[x / 255.0 for x in [125.3, 123.0, 113.9]],
                                         std=[x / 255.0 for x in [63.0, 62.1, 66.7]])

        self.train_transform = transforms.Compose([
        transforms.ToTensor(),
        normalize
        ])

        self.train_transform_grayscale = transforms.Compose([
        transforms.Grayscale(1),
        transforms.ToTensor(),
        normalize
        ])

        # transform for testing
        self.test_transform = transforms.Compose([
            transforms.ToTensor(),
            normalize
        ])

    def __call__(self,inp):
        out1 = self.train_transform(inp)
        out2 = self.train_transform_grayscale(inp)
        return out1, out2
'''
class TransformsSTL10: # Nawid -Transform STL10
    '''
    Apply the same input transform twice, with independent randomness.
    '''

    def __init__(self):
        # flipping image along vertical axis
        self.flip_lr = transforms.RandomHorizontalFlip(p=0.5)
        normalize = transforms.Normalize(mean=(0.43, 0.42, 0.39), std=(0.27, 0.26, 0.27))
        # image augmentation functions
        col_jitter = transforms.RandomApply([
            transforms.ColorJitter(0.4, 0.4, 0.4, 0.2)], p=0.8)
        rnd_gray = transforms.RandomGrayscale(p=0.25)
        rand_crop = \
            transforms.RandomResizedCrop(64, scale=(0.3, 1.0), ratio=(0.7, 1.4), # Nawid - Changed the resize to 128 from 64
                                         interpolation=INTERP)

        self.test_transform = transforms.Compose([
            transforms.Resize(70, interpolation=INTERP), # Nawid - Changed the resize to 140
            transforms.CenterCrop(64), # Nawid - Changed the crop from 64 to 128
            transforms.ToTensor(),
            normalize
        ])

        self.train_transform = transforms.Compose([
            rand_crop,
            col_jitter,
            rnd_gray,
            transforms.ToTensor(),
            normalize
        ])

    def __call__(self, inp):
        inp = self.flip_lr(inp)
        out1 = self.train_transform(inp)
        out2 = self.train_transform(inp)
        return out1, out2


class TransformsImageNet128: # Nawid -  Performs transforms on image net where the encoded image will be 128 x128
    '''
    ImageNet dataset, for use with 128x128 full image encoder.
    '''
    def __init__(self):
        # image augmentation functions
        self.flip_lr = transforms.RandomHorizontalFlip(p=0.5)
        rand_crop = \
            transforms.RandomResizedCrop(128, scale=(0.3, 1.0), ratio=(0.7, 1.4),
                                         interpolation=INTERP)
        col_jitter = transforms.RandomApply([
            transforms.ColorJitter(0.4, 0.4, 0.4, 0.1)], p=0.8)
        rnd_gray = transforms.RandomGrayscale(p=0.25)
        post_transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225])
        ])
        self.test_transform = transforms.Compose([
            transforms.Resize(146, interpolation=INTERP),
            transforms.CenterCrop(128),
            post_transform
        ])
        self.train_transform = transforms.Compose([
            rand_crop,
            col_jitter,
            rnd_gray,
            post_transform
        ])

    def __call__(self, inp):
        inp = self.flip_lr(inp)
        out1 = self.train_transform(inp)
        out2 = self.train_transform(inp)
        return out1, out2


def build_dataset(dataset, batch_size, input_dir=None, labeled_only=False): # Nawid- Loads the dataset and performs datasets on different implementations

    train_dir, val_dir = _get_directories(dataset, input_dir) # Nawid - Obtains the directory of a dataset

    if dataset == Dataset.C10:
        num_classes = 10
        train_transform = TransformsC10() # Nawid - Obtains the transform for the training set C10
        test_transform = train_transform.test_transform
        train_dataset = datasets.CIFAR10(root='/content/gdrive/My Drive/',
                                         train=True,
                                         transform=train_transform,
                                         download=True)
        test_dataset = datasets.CIFAR10(root='/content/gdrive/My Drive/',
                                        train=False,
                                        transform=test_transform,
                                        download=True)
    elif dataset == Dataset.C100:
        num_classes = 100
        train_transform = TransformsC10()
        test_transform = train_transform.test_transform
        train_dataset = datasets.CIFAR100(root='/content/gdrive/My Drive/',
                                          train=True,
                                          transform=train_transform,
                                          download=True)
        test_dataset = datasets.CIFAR100(root='/content/gdrive/My Drive/',
                                         train=False,
                                         transform=test_transform,
                                         download=True)
    elif dataset == Dataset.STL10:
        num_classes = 10
        train_transform = TransformsSTL10()
        test_transform = train_transform.test_transform
        train_split = 'train' if labeled_only else 'train+unlabeled'
        train_dataset = datasets.STL10(root='/content/gdrive/My Drive/',
                                       split=train_split,
                                       transform=train_transform,
                                       download=True)
        test_dataset = datasets.STL10(root='/content/gdrive/My Drive/',
                                      split='test',
                                      transform=test_transform,
                                      download=True)
    elif dataset == Dataset.IN128:
        num_classes = 1000
        train_transform = TransformsImageNet128()
        test_transform = train_transform.test_transform
        train_dataset = datasets.ImageFolder(train_dir, train_transform)
        test_dataset = datasets.ImageFolder(val_dir, test_transform)
    elif dataset == Dataset.PLACES205:
        num_classes = 1000
        train_transform = TransformsImageNet128()
        test_transform = train_transform.test_transform
        train_dataset = datasets.ImageFolder(train_dir, train_transform)
        test_dataset = datasets.ImageFolder(val_dir, test_transform)

    # build pytorch dataloaders for the datasets
    train_loader = \
        torch.utils.data.DataLoader(dataset=train_dataset,
                                    batch_size=batch_size,
                                    shuffle=True,
                                    pin_memory=True,
                                    drop_last=True,
                                    num_workers=16)
    test_loader = \
        torch.utils.data.DataLoader(dataset=test_dataset,
                                    batch_size=batch_size,
                                    shuffle=True,
                                    pin_memory=True,
                                    drop_last=True,
                                    num_workers=16)

    return train_loader, test_loader, num_classes


def _get_directories(dataset, input_dir): # Nawid - Obtains the directory of a data
    if dataset in [Dataset.C10, Dataset.C100, Dataset.STL10]:
        # Pytorch will download those datasets automatically
        return None, None
    if dataset == Dataset.IN128:
        train_dir = os.path.join(input_dir, 'ILSVRC2012_img_train/')
        val_dir = os.path.join(input_dir, 'ILSVRC2012_img_val/')
    elif dataset == Dataset.PLACES205:
        train_dir = os.path.join(input_dir, 'places205_256_train/')
        val_dir = os.path.join(input_dir, 'places205_256_val/')
    else:
        raise 'Data directories for dataset ' + dataset + ' are not defined'
    return train_dir, val_dir
