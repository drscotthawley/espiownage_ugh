# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/00_core.ipynb (unless otherwise specified).

__all__ = ['mkdir_if_needed', 'meta_to_img_path', 'meta_to_mask_path', 'meta_from_str', 'combine_file_and_tl_lists',
           'meta_to_df', 'fix_abangle', 'draw_ellipse', 'ellipse_to_bbox', 'ring_float_to_class_int', 'crop_to_bbox',
           'acc_reg', 'acc_reg05', 'acc_reg1', 'acc_reg15', 'acc_reg2']

# Cell
import cv2
from PIL import Image
import numpy as np
from pathlib import Path
import os
import pandas as pd
import torch
from fastai.torch_core import flatten_check

# Cell
def mkdir_if_needed(path:str):
    try:                # go ahead and try to make the the directory
        os.makedirs(path)
    except FileExistsError: pass
    except OSError as exception:
        if exception.errno != errno.EEXIST:  # ignore error if dir already exists
            raise

# Cell
def meta_to_img_path(
    meta_file:str, # filename of .csv file with annotations
    img_bank='images/',         # alternate location of image files, if not in same dir as meta file
    ):
    '''Suggest the image file that corresponds with an annotation CSV file'''
    meta_file, img_dir = Path(meta_file), Path(os.path.expanduser(img_bank))
    img_file = meta_file.with_suffix('.png')  # check same directory as meta first
    if os.path.exists(img_file): return img_file
    return img_dir / Path(img_file.name)  # return from image storage directory

# Cell
def meta_to_mask_path(
    meta_file:str, # filename of .csv file with annotations
    mask_dir='masks/',  # output directory; assumed to exist
    ):
    "provides name for segmentation mask file"
    csv_path = Path(meta_file)
    return Path(mask_dir + csv_path.stem+'_P.png')  # _P because that's what CAMVID dataset does

# Cell
def meta_from_str(s):
    "e.g., 06241902_proc_00510_0_45_88_236_1.0 -> 06241902_proc_00510.csv"
    # grab numbers on either side of _proc_
    s = s.split('.')[0]
    splits = s.split('_')
    return splits[0]+'_'+splits[1]+'_'+splits[2]+'.csv'

# Cell
def combine_file_and_tl_lists(file_list, top_loss_list):
    """for ellipse editor, but adding here:
    Go through tl list, and if elem e is not in file list, don't copy
    then go through file_list, and if e is already in, don't add"""
    if [] == top_loss_list: return file_list
    new_list = []
    basenames = [os.path.basename(f) for f in file_list]
    fldirname = os.path.dirname(file_list[0])
    meta_top_loss_list = [meta_from_str(x) for x in top_loss_list] # convert from whatever janky name is in tl list
    for e in meta_top_loss_list:
        if e in basenames: new_list.append(fldirname+'/'+e)
    for e in file_list:
        if e not in new_list: new_list.append(e)
    return new_list

# Cell
def meta_to_df(
    meta_file,  # csv file of ellipse data for an image
    ):
    "Reads in an espiownage/SPNet CSV file of ellipse data and returns a Pandas DataFrame"
    col_names = ['cx', 'cy', 'a', 'b', 'angle', 'rings']
    df = pd.read_csv(meta_file, header=None, names=col_names)
    df.drop_duplicates(inplace=True)  # sometimes the data from Zooniverse has duplicate rows
    for index, row in df.iterrows() : # fixup stuff
        [cx, cy, a, b, angle] = [int(round(x)) for x in [row['cx'], row['cy'], row['a'], row['b'], row['angle']]]
        a, b, angle = fix_abangle(a,b,angle)
        row['cx'], row['cy'], row['a'], row['b'], row['angle'] = cx, cy, a, b, angle
    return df

# Cell
def fix_abangle(
    a:float, # semimajor axis
    b:float, # semiminor axis
    angle:float,  # orientation angle in degrees
    ):
    "Makes sure semimajor axis > semiminor axis, and angles are consistent"
    if b > a:
        a, b, angle = b, a, angle+90
    if angle < 0: angle += 180
    elif angle >= 180: angle -= 180
    return a, b, angle

# Cell
def draw_ellipse(
    img,         # a cv2 image, *not* a PIL image (similar for grayscale but not RGB)
    center:tuple,      # (cx, cy) tuple
    axes:tuple,        # (a,b) semimajor & minor axes
    angle:float,       # orientation angle in degrees
    color=(0),   # color to draw. tuple or int
    thickness=2, # thickness ofthe lines we draw
    filled=False,  # whether to draw the ellipse as filled or not
    lineType=cv2.LINE_8,  # as opposed to LINE_AA, typically we DON'T want antialiasing for this app
    startAngle=0, endAngle=360, # arc-angles. should stay at 0 & 360 for full ellipses.
    shift=0, #10,      # shift is for sub-pixel resolution and AA figures. don't need it.
    ):
    """"Draws an ellipse into image.    """
    center = [int(round(x* 2**shift)) for x in center]
    axes = [int(round(x* 2**shift)) for x in axes]
    if filled: lineType, thickness = cv2.FILLED, -1
    ellipse = cv2.ellipse(
        img, center, axes, -angle,   # -angle because the web interface is "upside down"
        startAngle, endAngle, color,
        thickness, lineType, shift)
    return ellipse

# Cell
def ellipse_to_bbox(
    cx:float, # x-coordinate of center of ellipse
    cy:float, # y-coordinate of center of ellipse
    a:float,  # semimajor axis
    b:float,  # semiminor axis
    angle_deg:float,  # orientation angle in degrees
    coco=False, # COCO style bbox has last 2 nums as width & height of bbox
    width=512, height=384, # image dimensions for clipping
    clip=True, # clip values at max values of image width & height
    nozero=True,  # Lots of downstream apps hate zero-dimension bounding box. This returns None
    ):
    "converts ellipse to bounding box"
    rad = np.radians(angle_deg)
    a2, b2, cos2, sin2 = [x**2 for x in [a, b, np.cos(rad), np.sin(rad)]]
    delta_x, delta_y = np.sqrt(a2*cos2 + b2*sin2), np.sqrt(a2*sin2 + b2*cos2)
    xmin, xmax = cx - delta_x,  cx + delta_x
    ymin, ymax = cy - delta_y,  cy + delta_y
    if (xmin > xmax): xmin, xmax = xmax, xmin  # error correction, swap
    if (ymin > ymax): ymin, ymax = ymax, ymin  # swap
    if clip:
        xmin, xmax = np.clip(xmin, 0, width),  np.clip(xmax, 0, width)
        ymin, ymax = np.clip(ymin, 0, height), np.clip(ymax, 0, height)
    if coco: return [round(x, 2) for x in [xmin, ymin, xmax-xmin, ymax-ymin]] # coco is a list, floats are ok
    bbox = int(xmin), int(ymin), int(xmax), int(ymax)
    # Image.crop does not like zero-size dimensions but its error message is cryptic
    if ((xmax-xmin > 0) and (ymax-ymin > 0)) or (not nozero): return bbox
    else:
        print(f"ellipse_to_bbox: Error: zero-dim bbox = {bbox}. Returning None.")
        return None

# Cell
def ring_float_to_class_int(rings:float, step=0.1):
    """Ring value rounded to classifier value; rounded to nearest step size"""
    return round(rings/step)

# Cell
def crop_to_bbox(
    img,        # an image (PIL preferred, but will convert from cv2 if neede)
    bbox,       # [xmin, ymin, d3, d4] where d3,d4 are either xmax,ymax (default) or see coco (below)
    coco=False, # COCO style input bbox has last 2 nums as width & height of bbox
    width=512, height=384, # image dimensions for clipping
    clip=True,  # clip values at max values of image width & height
    ):
    "Crops an image to bbox, returns cropped image"
    if isinstance(img,np.ndarray): img = Image.fromarray(img)  # convert cv2 image to PIL
    xmin, ymin = bbox[0], bbox[1]
    if coco: xmax, ymax = bbox[0]+bbox[2], bbox[1]+bbox[3]
    else:    xmax, ymax = bbox[2], bbox[3]
    if clip:
        xmin, xmax = np.clip(xmin, 0, width),  np.clip(xmax, 0, width)
        ymin, ymax = np.clip(ymin, 0, height), np.clip(ymax, 0, height)
    # check ordering
    if (xmin > xmax): xmin, xmax = xmax, xmin  # error correction, swap
    if (ymin > ymax): ymin, ymax = ymax, ymin  # swap
    crop_bb = (int(xmin), int(ymin), int(xmax), int(ymax))

    # Image.crop does not like zero-size dimensions but its error message is cryptic
    if (xmax-xmin > 0) and (ymax-ymin > 0): return img.crop(crop_bb)
    else:
        print(f"crop_to_bbox: Error: zero-dim crop request, crop_bb = {crop_bb}. Returning None.")
        return None

# Cell
def acc_reg(inp, targ, bin_size=1):
    "Accuracy for regression: Are we within +/- bin_size?"
    inp,targ = flatten_check(inp,targ) # https://docs.fast.ai/metrics.html#flatten_check
    where_correct = (inp-targ).abs() < bin_size
    return where_correct.float().mean()

# Cell
def acc_reg05(inp, targ): return acc_reg(inp, targ, bin_size=0.5)

# Cell
def acc_reg1(inp, targ): return acc_reg(inp, targ, bin_size=1)

# Cell
def acc_reg15(inp, targ): return acc_reg(inp, targ, bin_size=1.5)

# Cell
def acc_reg2(inp, targ): return acc_reg(inp, targ, bin_size=2)