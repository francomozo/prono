# USAGE:
#   Functions to load images, custom datasets, dataloaders and collate_fn,
#   train/val/test splits, date computations.
#

import datetime
import os
import random
import re

import cv2 as cv
import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset
from torch.utils.data._utils.collate import default_collate

import src.lib.preprocessing_functions as pf
import src.lib.utils as utils


class MontevideoDataset(Dataset):
    def __init__(self, path, in_channel=3, out_channel=1,min_time_diff=5,max_time_diff=15,csv_path = None):
        super(MontevideoDataset, self).__init__()

        self.path = path
        self.in_channel = in_channel
        self.out_channel = out_channel
        self.min_time_diff = min_time_diff
        self.max_time_diff = max_time_diff
        
        if csv_path is None:
            self.sequence_df = utils.sequence_df_generator(path=path,
                                                            in_channel=in_channel,
                                                            out_channel= out_channel, 
                                                            min_time_diff= min_time_diff, 
                                                            max_time_diff= max_time_diff)
        else:
            self.sequence_df = pd.read_csv(csv_path, header= None)
    def __getitem__(self, index): 

        # images loading

        for i in range(self.in_channel + self.out_channel):
            if i == 0:  # first image in in_frames
                in_frames = np.load(os.path.join(
                    self.path, self.sequence_df.values[index][i]))
                in_frames = in_frames[np.newaxis]
            if i > 0 and i < self.in_channel:  # next images in in_frames
                aux = np.load(os.path.join(
                    self.path, self.sequence_df.values[index][i]))
                aux = aux[np.newaxis]
                in_frames = np.concatenate((in_frames, aux), axis=0)
            if i == self.in_channel:  # first image in out_frames
                out_frames = np.load(os.path.join(
                    self.path, self.sequence_df.values[index][i]))
                out_frames = out_frames[np.newaxis]
            if i > self.in_channel:
                aux = np.load(os.path.join(
                    self.path, self.sequence_df.values[index][i]))
                aux = aux[np.newaxis]
                out_frames = np.concatenate((out_frames, aux), axis=0)
                
        if self.transform:
            in_frames, out_frames = self.transform(in_frames,out_frames)            
            
        return in_frames, out_frames

    def __len__(self):
        return (len(self.sequence_df))

class MontevideoFoldersDataset(Dataset):
    """Dataset for Montevideo Dataset separated by folders named 2020XXX
    """    
    def __init__(self, path, in_channel=3, out_channel=1,min_time_diff=5,max_time_diff=15, csv_path=None, transform =None):
        super(MontevideoFoldersDataset, self).__init__()

        self.path = path
        self.in_channel = in_channel
        self.out_channel = out_channel
        self.min_time_diff = min_time_diff
        self.max_time_diff = max_time_diff
        self.transform = transform
        if csv_path is None:
            self.sequence_df = utils.sequence_df_generator_folders(path=path,
                                                                    in_channel=in_channel,
                                                                    out_channel= out_channel, 
                                                                    min_time_diff= min_time_diff, 
                                                                    max_time_diff= max_time_diff)
        else:
            self.sequence_df = pd.read_csv(csv_path, header= None)

    def __getitem__(self, index):

        # images loading

        for i in range(self.in_channel + self.out_channel):
            if i == 0:  # first image in in_frames
                in_frames = np.load(os.path.join(
                    self.path,self.sequence_df.values[index][i][4:11] ,self.sequence_df.values[index][i]))
                in_frames = in_frames[np.newaxis]
            if i > 0 and i < self.in_channel:  # next images in in_frames
                aux = np.load(os.path.join(
                    self.path,self.sequence_df.values[index][i][4:11] , self.sequence_df.values[index][i]))
                aux = aux[np.newaxis]
                in_frames = np.concatenate((in_frames, aux), axis=0)
            if i == self.in_channel:  # first image in out_frames
                out_frames = np.load(os.path.join(
                    self.path,self.sequence_df.values[index][i][4:11] , self.sequence_df.values[index][i]))
                out_frames = out_frames[np.newaxis]
            if i > self.in_channel:
                aux = np.load(os.path.join(
                    self.path,self.sequence_df.values[index][i][4:11] , self.sequence_df.values[index][i]))
                aux = aux[np.newaxis]
                out_frames = np.concatenate((out_frames, aux), axis=0)

        if self.transform:
            if type(self.transform) == list:
                for function in self.transform:
                    in_frames, out_frames = function(in_frames,out_frames) 
            else:
                in_frames, out_frames = self.transform(in_frames,out_frames) 
        
        return in_frames, out_frames

    def __len__(self):
        return (len(self.sequence_df))
    
    
class MovingMnistDataset(Dataset):
    def __init__(self, path, n_frames=4, shuffle=False):
        super(MovingMnistDataset, self).__init__()

        self.path = path
        self.shuffle = shuffle
        self.n_frames = n_frames
        self.filenames = sorted(os.listdir(path))

        # Aux variables for indexing correctly
        self.seq_num = 0
        self.rel_idx = 0
        self.seq_length = np.load(
            self.path + self.filenames[self.seq_num]).shape[0]

    def __getitem__(self, idx):

        # some initialization for each epoch
        if idx == 0 and self.shuffle:
            random.shuffle(self.filenames)
        if idx == 0:
            self.seq_num = 0

        # sequence number management
        if (idx + (self.n_frames - 1) * (self.seq_num + 1)) % self.seq_length == 0:
            self.seq_num += 1

        # index within the sequence
        self.rel_idx = (idx + (self.n_frames - 1) *
                        self.seq_num) % self.seq_length
        if idx <= self.seq_length - self.n_frames:
            self.rel_idx = idx

        # images loading
        if self.rel_idx == 0:
            self.images = torch.FloatTensor(
                [np.load(self.path + self.filenames[self.seq_num])]
            ).squeeze()

        frames_in = self.images[self.rel_idx: self.rel_idx+self.n_frames - 1]
        frames_out = self.images[self.rel_idx +
                                 self.n_frames - 1].unsqueeze(dim=0)

        # return indexes
        curr_idxs = np.arange(self.rel_idx, self.rel_idx + self.n_frames)

        return self.seq_num, curr_idxs, frames_in, frames_out

    def __len__(self):
        return ((self.seq_length - self.n_frames) * len(self.filenames))


class SatelliteImagesDatasetSW(Dataset):
    """ South America Satellite Images Dataset

    Args:
        root_dir (string): Directory with all images from day n.
        window (int): Size of the moving window to load the images.
        transform (callable, optional): Optional transform to be applied on a sample.


    Returns:
        [dict]: {'images': images, 'time_stamps': time_stamps}
    """

    dia_ref = datetime.datetime(2019, 12, 31)

    def __init__(self,
                 root_dir,
                 window=1,
                 transform=None,
                 fading_window=True,
                 load_cosangs=False,
                 meta_path='data/meta'
                 ):
        self.root_dir = root_dir
        self.images_list = np.sort(os.listdir(self.root_dir))
        self.transform = transform
        self.window = window
        self.fading_window = fading_window
        self.load_cosangs = load_cosangs

        if load_cosangs:
            self.meta_path = meta_path

        # Load the first "window" images to mem
        img_names = [os.path.join(self.root_dir, self.images_list[idx])  # esto es todo el path
                     for idx in range(self.window)]

        images = np.array([np.load(img_name)
                          for img_name in img_names])  # cargo imagenes

        if self.transform:
            images = np.array([self.transform(image) for image in images])

        parsed_img_names = [re.sub("[^0-9]", "", self.images_list[idx])
                            for idx in range(self.window)]

        time_stamps = [self.dia_ref + datetime.timedelta(days=int(img_name[4:7]),
                                                         hours=int(
                                                             img_name[7:9]),
                                                         minutes=int(
                                                             img_name[9:11]),
                                                         seconds=int(img_name[11:]))
                       for img_name in parsed_img_names]

        self.__samples = {'images': images,
                          'time_stamps': [utils.datetime2str(ts) for ts in time_stamps]}

        if self.load_cosangs:
            cosangs_masks = np.array([
                utils.get_cosangs_mask(
                    meta_path=self.meta_path, img_name=img_name)[1]
                for img_name in self.images_list
            ])

            if self.transform:
                cosangs_masks = np.array(
                    [self.transform(mask) for mask in cosangs_masks])

            self.__samples['cosangs_masks'] = cosangs_masks

    def __len__(self):
        if self.fading_window:
            return len(self.images_list)
        else:
            return len(self.images_list) - self.window + 1

    def __getitem__(self, idx):
        if idx == 0:
            return self.__samples
        else:
            # 1) Delete whats left out of the window
            self.__samples['images'] = np.delete(
                self.__samples['images'], obj=0, axis=0)
            del self.__samples['time_stamps'][0]

            if self.load_cosangs:
                self.__samples['cosangs_masks'] = np.delete(
                    self.__samples['cosangs_masks'], obj=0, axis=0)

            # If i have images left to load:
            #   a) Load images, ts, cosangs (if load_cosangs)
            #   b) Append to dictionary
            if idx < len(self.images_list) - self.window + 1:
                next_image = os.path.join(
                    self.root_dir, self.images_list[idx + self.window - 1])

                image = np.load(next_image)

                if self.transform:
                    image = np.array(self.transform(image))

                self.__samples['images'] = np.append(
                    self.__samples['images'],
                    values=image[np.newaxis, ...],
                    axis=0
                )

                img_name = re.sub(
                    "[^0-9]", "", self.images_list[idx + self.window - 1])

                time_stamp = self.dia_ref + datetime.timedelta(days=int(img_name[4:7]),
                                                               hours=int(
                                                                   img_name[7:9]),
                                                               minutes=int(
                                                                   img_name[9:11]),
                                                               seconds=int(img_name[11:]))

                self.__samples['time_stamps'].append(
                    utils.datetime2str(time_stamp))

                if self.load_cosangs:
                    cosangs_mask = utils.get_cosangs_mask(
                        meta_path=self.meta_path,
                        img_name=self.images_list[idx + self.window - 1]
                    )[1]

                    if self.transform:
                        cosangs_mask = np.array(self.transform(cosangs_mask))

                    self.__samples['cosangs_masks'] = np.append(
                        self.__samples['cosangs_masks'],
                        values=cosangs_mask[np.newaxis, ...],
                        axis=0
                    )
            # If i dont have images left:
            else:
                if self.fading_window:
                    self.window -= 1

            return self.__samples


def collate_fn_sw(batch):
    """Custom collate_fn to load images into batches
       using a moving window

    Returns:
        [dict]: {'images': images, 'time_stamps': time_stamps} 
                Includes key 'cosangs_masks' if load_mask = True 
                in SatelliteImagesDatasetSW.
    """
    samples = default_collate(batch)
    samples['images'] = samples['images'].squeeze()
    samples['time_stamps'] = [''.join(ts) for ts in samples['time_stamps']]

    if len(samples.keys()) == 3:
        samples['cosangs_masks'] = samples['cosangs_masks'].squeeze()
    return samples


class SatelliteImagesDatasetSW_NoMasks(Dataset):
    """ South America Satellite Images Dataset
    Args:
        root_dir (string): Directory with all images from day n.
        window (int): Size of the moving window to load the images.
        transform (callable, optional): Optional transform to be applied on a sample.


    Returns:
        [dict]: {'images': images, 'time_stamps': time_stamps}
    """

    dia_ref = datetime.datetime(2019, 12, 31)

    def __init__(self, root_dir, window=1, transform=None):
        self.root_dir = root_dir
        self.images_list = np.sort(os.listdir(self.root_dir))
        self.transform = transform
        self.window = window

        # Load the first "window" images to mem
        img_names = [os.path.join(self.root_dir, self.images_list[idx])
                     for idx in range(self.window)]

        images = np.array([np.load(img_name) for img_name in img_names])

        if self.transform:
            images = np.array([self.transform(image) for image in images])

        img_names = [re.sub("[^0-9]", "", self.images_list[idx])
                     for idx in range(self.window)]

        time_stamps = [self.dia_ref + datetime.timedelta(days=int(img_name[4:7]),
                                                         hours=int(
                                                             img_name[7:9]),
                                                         minutes=int(
                                                             img_name[9:11]),
                                                         seconds=int(img_name[11:]))
                       for img_name in img_names]

        self.__samples = {'images': images,
                          'time_stamps': [utils.datetime2str(ts) for ts in time_stamps]}

    def __len__(self):
        return len(self.images_list) - self.window + 1

    def __getitem__(self, idx):
        if idx == 0:
            return self.__samples
        else:

            next_image = os.path.join(
                self.root_dir, self.images_list[idx + self.window - 1])

            image = np.load(next_image)

            if self.transform:
                image = np.array(self.transform(image))

            img_name = re.sub(
                "[^0-9]", "", self.images_list[idx + self.window - 1])

            time_stamp = self.dia_ref + datetime.timedelta(days=int(img_name[4:7]),
                                                           hours=int(
                                                               img_name[7:9]),
                                                           minutes=int(
                                                               img_name[9:11]),
                                                           seconds=int(img_name[11:]))

            self.__samples['images'] = np.append(
                np.delete(self.__samples['images'],
                          obj=0,
                          axis=0
                          ),
                values=image[np.newaxis, ...],
                axis=0
            )

            del self.__samples['time_stamps'][0]
            self.__samples['time_stamps'].append(
                utils.datetime2str(time_stamp))

            return self.__samples


def load_images_from_folder(folder, crop_region=0):
    """Loads images stored as Numpy arrays of nth-day to a list

    Args:
        folder (str): Where the images of day X are stored
        crop_region (bool, optional): Regions 0(dont crop), 1, 2 and 3(Uruguay).

    Returns:
        images (list): List of Numpy arrays containing the images
        time_stamp (list): List with datetime of the images
    """

    current_imgs = []
    time_stamp = []
    dia_ref = datetime.datetime(2019, 12, 31)

    for filename in np.sort(os.listdir(folder)):
        img = np.load(os.path.join(folder, filename))

        if crop_region == 1:
            current_imgs.append(img[300:2500, 600:2800])
        elif crop_region == 2:
            current_imgs.append(img[500:2100, 800:2400])
        elif crop_region == 3:
            current_imgs.append(img[700:1700, 1200:2200])
        else:
            current_imgs.append(img)

        img_name = re.sub("[^0-9]", "", filename)
        dt_image = dia_ref + datetime.timedelta(days=int(img_name[4:7]), hours=int(img_name[7:9]),
                                                minutes=int(img_name[9:11]), seconds=int(img_name[11:]))
        time_stamp.append(dt_image)

    return current_imgs, time_stamp


def load_by_batches(folder, current_imgs, time_stamp, list_size, last_img_filename="", crop_region=0):
    """Loads the first "list_size" images from "folder" if "current_imgs"=[],
        if not, deletes the first element in the list, shift left on position, and
        reads the next image and time-stamp

    Args:
        folder (str): Where .npy arrays are stored
        current_imgs (list): Numpy arrays storing the images
        time_stamp ([type]): [description]
        list_size (int): Quantity of images to load , should be equal to the prediction horizon + 1
        crop_region (bool, optional): Regions 0(dont crop), 1, 2 and 3(Uruguay).
    """

    dia_ref = datetime.datetime(2019, 12, 31)
    sorted_img_list = np.sort(os.listdir(folder))

    if current_imgs == []:
        # for nth_img in range(list_size + 1):
        for nth_img in range(list_size):
            filename = sorted_img_list[nth_img]  # stores last img
            img = np.load(os.path.join(folder, filename))

            if crop_region == 1:
                current_imgs.append(img[300:2500, 600:2800])
            elif crop_region == 2:
                current_imgs.append(img[500:2100, 800:2400])
            elif crop_region == 3:
                current_imgs.append(img[700:1700, 1200:2200])
            else:
                current_imgs.append(img)

            img_name = re.sub("[^0-9]", "", filename)
            dt_image = dia_ref + datetime.timedelta(days=int(img_name[4:7]), hours=int(img_name[7:9]),
                                                    minutes=int(img_name[9:11]), seconds=int(img_name[11:]))
            time_stamp.append(dt_image)
    else:
        del current_imgs[0]
        del time_stamp[0]

        last_img_index = np.where(sorted_img_list == last_img_filename)[0][0]

        new_img_filename = sorted_img_list[last_img_index + 1]

        current_imgs.append(np.load(os.path.join(folder, new_img_filename)))

        img_name = re.sub("[^0-9]", "", new_img_filename)
        dt_image = dia_ref + datetime.timedelta(days=int(img_name[4:7]), hours=int(img_name[7:9]),
                                                minutes=int(img_name[9:11]), seconds=int(img_name[11:]))
        time_stamp.append(dt_image)

        filename = new_img_filename

    return current_imgs, time_stamp, filename


def load_img(meta_path='data/meta',
             img_name='ART_2020020_111017.FR',
             mk_folder_path='data/C02-MK/2020',
             img_folder_path='data/C02-FR/2020'
             ):
    """ Loads image from .FR .MK and metadata files into Numpy array

    Args:
        meta_path (str, optional): Defaults to 'data/meta'.
        img_name (str, optional): Defaults to 'ART_2020020_111017.FR'.
        mk_folder_path (str, optional): Defaults to 'data/C02-MK/2020'.
        img_folder_path (str, optional): Defaults to 'data/C02-FR/2020'.
    """

    lats, lons = pf.read_meta(meta_path)

    dtime = pf.get_dtime(img_name)

    cosangs, cos_mask = pf.get_cosangs(dtime, lats, lons)
    img_mask = pf.load_mask(
        img_name, mk_folder_path, lats.size, lons.size
    )
    img = pf.load_img(
        img_name, img_folder_path, lats.size, lons.size
    )
    rimg = cv.inpaint(img, img_mask, 3, cv.INPAINT_NS)
    rp_image = pf.normalize(rimg, cosangs, 0.15)

    return rp_image


def save_imgs_2npy(meta_path='data/meta',
                   mk_folder_path='data/C02-MK/2020',
                   img_folder_path='data/C02-FR/2020',
                   destintation_path='data/images',
                   split_days_into_folders=True
                   ):
    """Saves images from "img_folder_path" to "destintation_path" as Numpy arrays
       (Uses load_img() function)

    Args:
        meta_path (str, optional): Defaults to 'data/meta'.
        mk_folder_path (str, optional): Defaults to 'data/C02-MK/2020'.
        img_folder_path (str, optional): Defaults to 'data/C02-FR/2020'.
        destintation_path (str, optional): Defaults to 'data/images'.
        split_days_into_folders (bool, optional): Defaults to False.
    """

    for filename in os.listdir(img_folder_path):
        img = load_img(  # added needed arguments (franchesoni)
            meta_path=meta_path,
            img_name=filename,
            mk_folder_path=mk_folder_path,
            img_folder_path=img_folder_path,
        )

        img = np.asarray(img)

        if (True):  # sets pixel over 100 to 100
            img = np.clip(img, 0, 100)
        if (False):  # sets pixel over 100 to image mean
            img[img > 100] = np.mean(img)
        if (False):  # sets pixel over 100+std to image mean and pixel between 100 and 100+std to 100
            img[img > 100 + np.std(img)] = np.mean(img)
            img[img > 100] = 100

        if split_days_into_folders:
            day = re.sub("[^0-9]", "", filename)[4:7].lstrip("0")
            try:
                os.makedirs(os.path.join(
                    os.getcwd(), destintation_path, "dia_" + day))
            except:
                pass
            path = os.path.join(destintation_path, "day_" +
                                day, os.path.splitext(filename)[0] + ".npy")

        else:
            try:
                os.makedirs(os.path.join(
                    os.getcwd(), destintation_path, "loaded_images"))
            except:
                pass
            path = os.path.join(destintation_path, 'loaded_images',
                                os.path.splitext(filename)[0] + ".npy")

        np.save(path, img)


def save_imgs_list_2npy(imgs_list=[],
                        meta_path='data/meta',
                        mk_folder_path='data/C02-MK/2020',
                        img_folder_path='data/C02-FR/2020',
                        destintation_path='data/images',
                        split_days_into_folders=True
                        ):
    """Saves images as Numpy arrays to folders

    Args:
        imgs_list[] (list): List containing the names of the images to be saved. ie: days.
        meta_path (str, optional): Defaults to 'data/meta'.
        mk_folder_path (str, optional): Defaults to 'data/C02-MK/2020'.
        img_folder_path (str, optional): Defaults to 'data/C02-FR/2020'.
        destintation_path (str, optional): Defaults to 'data/images'.
        split_days_into_folders (bool, optional): Defaults to False.
    """

    for filename in imgs_list:
        img = load_img(  # added needed arguments (franchesoni)
            meta_path=meta_path,
            img_name=filename,
            mk_folder_path=mk_folder_path,
            img_folder_path=img_folder_path,
        )

        # cut montevideo
        img = img[1550:1550+256, 1600:1600+256]

        # image clipping

        if (True):  # sets pixel over 100 to 100
            img = np.clip(img, 0, 100)
        if (False):  # sets pixel over 100 to image mean
            img[img > 100] = np.mean(img)
        if (False):  # sets pixel over 100+std to image mean and pixel between 100 and 100+std to 100
            img[img > 100 + np.std(img)] = np.mean(img)
            img[img > 100] = 100

        if split_days_into_folders:
            day = re.sub("[^0-9]", "", filename)[:7]
            try:
                os.makedirs(os.path.join(
                    os.getcwd(), destintation_path, day))
            except:
                pass
            path = os.path.join(destintation_path,
                                day, os.path.splitext(filename)[0] + ".npy")

        else:
            try:
                os.makedirs(os.path.join(
                    os.getcwd(), destintation_path, "loaded_images"))
            except:
                pass
            path = os.path.join(destintation_path, 'loaded_images',
                                os.path.splitext(filename)[0] + ".npy")

        np.save(path, img)


class MontevideoFoldersDataset_w_time(Dataset):
    """Dataset for Montevideo Dataset separated by folders named 2020XXX
    """    
    def __init__(self, path, in_channel=3, out_channel=1,min_time_diff=5,max_time_diff=15, csv_path=None, transform =None):
        super(MontevideoFoldersDataset_w_time, self).__init__()

        self.path = path
        self.in_channel = in_channel
        self.out_channel = out_channel
        self.min_time_diff = min_time_diff
        self.max_time_diff = max_time_diff
        self.transform = transform
        if csv_path is None:
            self.sequence_df = utils.sequence_df_generator_folders(path=path,
                                                                    in_channel=in_channel,
                                                                    out_channel= out_channel, 
                                                                    min_time_diff= min_time_diff, 
                                                                    max_time_diff= max_time_diff)
        else:
            self.sequence_df = pd.read_csv(csv_path, header= None)

    def __getitem__(self, index):

        # images loading

        out_time=[]
        for i in range(self.in_channel + self.out_channel):
            if i == 0:  # first image in in_frames
                in_frames = np.load(os.path.join(
                    self.path,self.sequence_df.values[index][i][4:11] ,self.sequence_df.values[index][i]))
                in_frames = in_frames[np.newaxis]
            if i > 0 and i < self.in_channel:  # next images in in_frames
                aux = np.load(os.path.join(
                    self.path,self.sequence_df.values[index][i][4:11] , self.sequence_df.values[index][i]))
                aux = aux[np.newaxis]
                in_frames = np.concatenate((in_frames, aux), axis=0)
            if i == self.in_channel:  # first image in out_frames
                out_frames = np.load(os.path.join(
                    self.path,self.sequence_df.values[index][i][4:11] , self.sequence_df.values[index][i]))
                out_frames = out_frames[np.newaxis]
                out_time.append(self.sequence_df.values[index][i][12:18])
            if i > self.in_channel:
                aux = np.load(os.path.join(
                    self.path,self.sequence_df.values[index][i][4:11] , self.sequence_df.values[index][i]))
                aux = aux[np.newaxis]
                out_frames = np.concatenate((out_frames, aux), axis=0)
                # ART_2020xxx_hhmmss.npy
                
                out_time.append(self.sequence_df.values[index][i][12:18])

        if self.transform:
            if type(self.transform) == list:
                for function in self.transform:
                    in_frames, out_frames = function(in_frames,out_frames) 
            else:
                in_frames, out_frames = self.transform(in_frames,out_frames) 
        
        return in_frames, out_frames, out_time

    def __len__(self):
        return (len(self.sequence_df))