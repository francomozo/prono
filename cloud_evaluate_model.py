import os
import numpy as np
import matplotlib.pyplot as plt
import time
import datetime
import pickle
import argparse

import torch
from torch.utils.data import DataLoader

from src import data, evaluate, model, preprocessing, visualization
from src.lib import utils
from src.data import MontevideoFoldersDataset
from src.dl_models.unet import UNet


ap = argparse.ArgumentParser(description='Evaluate multiple models with multiple metrics')

ap.add_argument("--models", nargs="+", default=["Unet"], 
                help="Options: CMV, Persistence, Unet, \"BCMV <kernel_size>\". Defaults to Unet")
ap.add_argument("--metrics", nargs="+", default=["RMSE"],
                help="Defaults to RMSE. Add %% for percentage metric")
ap.add_argument("--csv-path-base", default=None,
                help="Csv path for baseline models (CMV, Persistence, BCMV). Defaults to None.")
ap.add_argument("--csv-path-unet", default=None,
                help="Csv path for unets. Defaults to None.")
ap.add_argument("--data-path", default='/clusteruy/home03/DeepCloud/deepCloud/data/mvd/validation/',
                help="Defaults to /clusteruy/home03/DeepCloud/deepCloud/data/mvd/validation/")
ap.add_argument("--model-path", nargs="*", default=None,
                help="Add model paths for NNs.")
ap.add_argument("--save-errors", default=False, type=bool,
                help="Save results in file. Defaults to False.")
ap.add_argument("--sigmoid", default=False, type=bool,
                help="Sigmoid for unets. Defaults to False.")

ap.add_argument("--window-pad", default=0, type=int,
                help="Size of padding for evaluation, eval window is [w_p//2 : M-w_p//2, w_p//2 : N-w_p//2]. Defaults to 0.")
ap.add_argument("--window-pad-height", default=0, type=int,
                help="Size of height padding for evaluation, eval window is [w_p_h//2 : M-w_p_h//2]. Defaults to 0.")
ap.add_argument("--window-pad-width", default=0, type=int,
                help="Size of width padding for evaluation, eval window is [w_p_w//2 : N-w_p_w//2]. Defaults to 0.")

params = vars(ap.parse_args())
csv_path_base = params['csv_path_base']
csv_path_unet = params['csv_path_unet']
PATH_DATA = params['data_path']
models_names = params['models']
metrics = params['metrics']

for i in range(len(models_names)):
  models_names[i] = models_names[i].lower()
  if models_names[i].find("bcmv") != -1:
      kernel_size = [int(word) for word in models_names[i].split() if word.isdigit()][0]
      models_names[i] = "bcmv"
metrics = [each_string.upper() for each_string in metrics]

#DataLoaders
val_mvd = MontevideoFoldersDataset(path = PATH_DATA, 
                                   in_channel=2, 
                                   out_channel=6,
                                   min_time_diff=5, max_time_diff=15, 
                                   csv_path=csv_path_base)

normalize = preprocessing.normalize_pixels(mean0=False) 
val_mvd_Unet = MontevideoFoldersDataset(path = PATH_DATA, 
                                        in_channel=3, 
                                        out_channel=6,
                                        min_time_diff=5, max_time_diff=15,
                                        transform=normalize, 
                                        csv_path=csv_path_unet)

val_loader = DataLoader(val_mvd)
val_loader_Unet = DataLoader(val_mvd_Unet)

#Definition of models
models = []
model_path_index = 0
device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
for a_model_name in models_names:
  if "cmv" == a_model_name:
    models.append(model.Cmv2())
  if "bcmv" == a_model_name:
    models.append(model.Cmv2(kernel_size=(kernel_size,kernel_size)))
  if "p" == a_model_name or "persistence" == a_model_name:
    models.append(model.Persistence())
  if "unet" == a_model_name:
    if params["model_path"] == None:
      raise ValueError("Use --model-path to add model location.")
    model_path = params["model_path"][model_path_index]
    model_path_index += 1
    model_Unet = UNet(n_channels=3, n_classes=1, bilinear=True, output_sigmoid=params["sigmoid"]).to(device)
    model_Unet.load_state_dict(torch.load(model_path)["model_state_dict"])
    model_Unet.eval()
    models.append(model_Unet)

errors_metrics = {}
for metric in metrics:
    print("\n", metric)
    fix = 1
    #variables for percentage evaluation:
    percentage_pos = metric.find("%") 
    if percentage_pos != -1:
        end_metric = percentage_pos
        error_percentage=True
    else:
        end_metric = len(metric)
        error_percentage=False
        fix = fix*100
    #fix to normalize errors:
    if metric[:end_metric] == 'MSE':
        fix = fix*100

    errors_metric = {}
    for idx, a_model in enumerate(models):
      if models_names[idx] == 'unet':
        val_loader_aux = val_loader_Unet
        device_aux = device
        use_fix = False
      else:
        val_loader_aux = val_loader
        device_aux = None
        use_fix = True
      
      print('\nPredicting', models_names[idx])
      time.sleep(1)
      error_array = evaluate.evaluate_model(a_model, val_loader_aux, 
                                            predict_horizon=6, 
                                            device=device_aux, 
                                            metric=metric[:end_metric], 
                                            error_percentage=error_percentage,
                                            window_pad=params['window_pad'],
                                            window_pad_height=params['window_pad_height'],
                                            window_pad_width=params['window_pad_width'])
      error_mean = np.mean(error_array, axis=0)
      if use_fix:
        error_mean = error_mean/fix
      print(f'Error_mean_{models_names[idx]}: {error_mean}')
      print(f'Error_mean_mean_{models_names[idx]}: {np.mean(error_mean)}')
      errors_metric[models_names[idx]] = error_mean

    errors_metrics[metric] = errors_metric

if params['save_errors']:
  PATH = "reports/errors_evaluate_model/"
  ts = datetime.datetime.now().strftime("%d-%m-%Y_%H-%M")
  NAME = 'errors_models_' + str(ts) + '.pkl'

  a_file = open(os.path.join(PATH, NAME), "wb")
  pickle.dump(errors_metrics, a_file)
  a_file.close()
