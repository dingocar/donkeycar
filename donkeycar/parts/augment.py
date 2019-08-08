'''
    File: augment.py
    Author : Tawn Kramer
    Date : July 2017
'''
import random
from PIL import Image
from PIL import ImageEnhance
import glob
import numpy as np
import math
from donkeycar.parts.dingo_aug import *
import glob

'''
    find_coeffs and persp_transform borrowed from:
    https://stackoverflow.com/questions/14177744/how-does-perspective-transformation-work-in-pil
'''
def find_coeffs(pa, pb):
    matrix = []
    for p1, p2 in zip(pa, pb):
        matrix.append([p1[0], p1[1], 1, 0, 0, 0, -p2[0]*p1[0], -p2[0]*p1[1]])
        matrix.append([0, 0, 0, p1[0], p1[1], 1, -p2[1]*p1[0], -p2[1]*p1[1]])

    A = np.matrix(matrix, dtype=np.float)
    B = np.array(pb).reshape(8)

    res = np.dot(np.linalg.inv(A.T * A) * A.T, B)
    return np.array(res).reshape(8)

def rand_persp_transform(img):
    width, height = img.size
    new_width = math.floor(float(width) * random.uniform(0.9, 1.1))
    xshift = math.floor(float(width) * random.uniform(-0.2, 0.2))
    coeffs = find_coeffs(
        [(0, 0), (256, 0), (256, 256), (0, 256)],
        [(0, 0), (256, 0), (new_width, height), (xshift, height)])

    return img.transform((width, height), Image.PERSPECTIVE, coeffs, Image.BICUBIC)

def augment_image(np_img, shadow_images=None, do_warp_persp=False):
    conv_img = np_img * 255.0
    conv_img = conv_img.astype(np.uint8)
    img = Image.fromarray(conv_img)
    #change the coloration, sharpness, and composite a shadow
    factor = random.uniform(0.5, 2.0)
    img = ImageEnhance.Brightness(img).enhance(factor)
    factor = random.uniform(0.5, 1.0)
    img = ImageEnhance.Contrast(img).enhance(factor)
    factor = random.uniform(0.5, 1.5)
    img = ImageEnhance.Sharpness(img).enhance(factor)
    factor = random.uniform(0.0, 1.0)
    img = ImageEnhance.Color(img).enhance(factor)

    if shadow_images is not None:
        '''
        optionaly composite a shadow, perpared from load_shadow_images
        '''
        iShad = random.randrange(0, len(shadow_images))
        top, mask = shadow_images[iShad]
        theta = random.randrange(-35, 35)
        mask.rotate(theta)
        top.rotate(theta)
        mask = ImageEnhance.Brightness(mask).enhance(random.uniform(0.3, 1.0))
        offset = (random.randrange(-128, 128), random.randrange(-128, 128))
        img.paste(top, offset, mask)
    
    if do_warp_persp:
        '''
        optionaly warp perspective
        '''
        img = rand_persp_transform(img)

    return np.array(img).astype(np.float) / 255.0

def load_shadow_images(path_mask):
    shadow_images = []
    filenames = glob.glob(path_mask)
    for filename in filenames:
        shadow = Image.open(filename)
        shadow.thumbnail((256, 256))
        channels = shadow.split()
        if len(channels) != 4:
            continue
        r, g, b, a = channels
        top = Image.merge("RGB", (r, g, b))
        mask = Image.merge("L", (a,))
        shadow_images.append((top, mask))
    return shadow_images

def load_shadow_image_without_alpha_channel(path_mask):
    shadow_images = []
    filenames = glob.glob(path_mask)
    # Just load filenames. Load the images on the fly during trainging time.
    '''
    for filename in filenames:
        shadow = Image.open(filename)
        shadow.thumbnail((256, 256))
        shadow_images.append(np.asarray(shadow))
    '''
    return filenames

def dingo_aug(cfg, np_img, steering_angle, throttle, shadow_images=None):

    try:
        aug = cfg.AUG_MIRROR_STEERING
        if aug is not None and random_bool(aug[0]):
            # Need to figure out how to effect steering angle
            np_img          = mirror_image(np_img)
            steering_angle *= -1.
    except AttributeError:
        pass

    try:
        aug = cfg.AUG_SALT_AND_PEPPER
        if aug is not None and random_bool(aug[0]):
            per_pixel_prob = aug[1]
            np_img         = salt_and_pepper(np_img, prob = per_pixel_prob)
    except AttributeError:
        pass

    try:
        aug = cfg.AUG_100S_AND_1000S
        if aug is not None and random_bool(aug[0]):
            per_pixel_prob = aug[1]
            np_img         = hundreds_and_thousands(np_img, prob = per_pixel_prob)
    except AttributeError:
        pass

    try:
        aug = cfg.AUG_SHADOW_IMAGES
        if aug is not None and random_bool(aug[0]):
            max_alpha = float(aug[1])
            np_img    = overlay_random_image(np_img, max_alpha, shadow_images)
    except AttributeError:
        pass

    try:
        aug = cfg.AUG_PIXEL_SATURATION
        if aug is not None and random_bool(aug[0]):
            sat_min = aug[1]
            sat_max = aug[2]
            np_img  = saturation(np_img, sat_min, sat_max)
    except AttributeError:
        pass

    try:
        aug = cfg.AUG_SHUFFLE_CHANNELS
        if aug is not None and random_bool(aug[0]):
            np_img = shuffle_channels(np_img)
    except AttributeError:
        pass

    try:
        aug = cfg.AUG_BLOCKOUT
        if aug is not None and random_bool(aug[0]):
            frac_min = aug[1]
            frac_max = aug[2]
            np_img   = blockout(np_img, frac_min, frac_max)
    except AttributeError:
        pass

    try:
        aug = cfg.AUG_JITTER_STEERING
        if aug is not None and random_bool(aug[0]):
            min_delta = aug[1]
            max_delta = aug[2]
            steering  = jitter(steering_angle, aug[1], aug[2])
    except AttributeError:
        pass

    try:
        aug = cfg.AUG_JITTER_THROTTLE
        if aug is not None and random_bool(aug[0]):
            min_delta = aug[1]
            max_delta = aug[2]
            throttle  = jitter(throttle, aug[1], aug[2])
    except AttributeError:
        pass

    try:
        if cfg.AUG_NORMALIZE:
            np_img = np.divide(np_img, 255.)
    except AttributeError:
        pass

    return np_img, steering_angle, throttle

def random_bool(true_prob):
    return np.random.choice([True, False], 1, p=[true_prob, 1.-true_prob])
    


















