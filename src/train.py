# USAGE:
#   Training loops and checkpoint saving
#
import datetime
import time

import numpy as np
import optuna
import torch
import torch.nn as nn
from torch.optim.lr_scheduler import ReduceLROnPlateau
from torchvision.transforms import CenterCrop

from src.lib.utils import print_cuda_memory


def train_model(model,
                criterion,
                optimizer,
                device,
                train_loader,
                epochs,
                val_loader,
                num_val_samples=10,
                checkpoint_every=None,
                verbose=True,
                eval_every=100,
                writer=None,
                scheduler=None):

    # TODO: - docstring

    TRAIN_LOSS_GLOBAL = [] # perists through epochs, stores the mean of each epoch
    VAL_LOSS_GLOBAL = [] # perists through epochs, stores the mean of each epoch

    TIME = []

    BEST_VAL_ACC = 1e5
    
    if writer:
        in_frames, _ = next(iter(train_loader))
        in_frames = in_frames.to(device=device)
        writer.add_graph(model, input_to_model=in_frames, verbose=False)
        
    for epoch in range(epochs):
        start_epoch = time.time()
        TRAIN_LOSS_EPOCH = [] # stores values inside the current epoch
        VAL_LOSS_EPOCH = [] # stores values inside the current epoch
        

        for batch_idx, (in_frames, out_frames) in enumerate(train_loader):
            model.train()

            start_batch = time.time()

            # data to cuda if possible
            in_frames = in_frames.to(device=device)
            out_frames = out_frames.to(device=device)

            # forward
            frames_pred = model(in_frames)
            loss = criterion(frames_pred, out_frames)

            # backward
            optimizer.zero_grad()
            loss.backward()

            # gradient descent or adam step
            optimizer.step()

            end_batch = time.time()
            TIME.append(end_batch - start_batch)

            TRAIN_LOSS_EPOCH.append(loss.detach().item())

            if (batch_idx > 0 and batch_idx % eval_every == 0) or (batch_idx == len(train_loader)-1 ) :
                model.eval()
                VAL_LOSS_LOCAL = [] #stores values for this validation run
                start_val = time.time()
                with torch.no_grad():
                    for val_batch_idx, (in_frames, out_frames) in enumerate(val_loader):

                        in_frames = in_frames.to(device=device)
                        out_frames = out_frames.to(device=device)

                        frames_pred = model(in_frames)
                        val_loss = criterion(frames_pred, out_frames)

                        VAL_LOSS_LOCAL.append(val_loss.detach().item())

                        if val_batch_idx == num_val_samples:
                            if (batch_idx == len(train_loader)-1) and writer:
                                # enter if last batch of the epoch and there is a writer
                                writer.add_images('groundtruth_batch', out_frames, epoch)
                                writer.add_images('predictions_batch', frames_pred, epoch)
                            break

                end_val = time.time()
                val_time = end_val - start_val
                CURRENT_VAL_ACC = sum(VAL_LOSS_LOCAL)/len(VAL_LOSS_LOCAL)
                VAL_LOSS_EPOCH.append(CURRENT_VAL_ACC)
                
                CURRENT_TRAIN_ACC = sum(TRAIN_LOSS_EPOCH[batch_idx-eval_every:])/len(TRAIN_LOSS_EPOCH[batch_idx-eval_every:])

                if verbose:
                    # print statistics
                    print(f'Epoch({epoch + 1}/{epochs}) | Batch({batch_idx:04d}/{len(train_loader)}) | ', end='')
                    print(f'Train_loss({(CURRENT_TRAIN_ACC):06.4f}) | Val_loss({CURRENT_VAL_ACC:.4f}) | ', end='')
                    print(f'Time_per_batch({sum(TIME)/len(TIME):.2f}s) | Val_time({val_time:.2f}s)') 
                    TIME = []
                    
                if writer: 
                    #add values to tensorboard 
                    writer.add_scalar("Loss in train GLOBAL",CURRENT_TRAIN_ACC , batch_idx + epoch*(len(train_loader)))
                    writer.add_scalar("Loss in val GLOBAL" , CURRENT_VAL_ACC,  batch_idx + epoch*(len(train_loader)))
        
        #epoch end      
        end_epoch = time.time()
        TRAIN_LOSS_GLOBAL.append(sum(TRAIN_LOSS_EPOCH)/len(TRAIN_LOSS_EPOCH))
        VAL_LOSS_GLOBAL.append(sum(VAL_LOSS_EPOCH)/len(VAL_LOSS_EPOCH))
        
        if scheduler:
            scheduler.step(VAL_LOSS_GLOBAL[-1])
        
        if writer: 
            #add values to tensorboard 
            writer.add_scalar("TRAIN LOSS, EPOCH MEAN",TRAIN_LOSS_GLOBAL[-1], epoch)
            writer.add_scalar("VALIDATION LOSS, EPOCH MEAN" , VAL_LOSS_GLOBAL[-1] , epoch)
            writer.add_scalar("Learning rate", optimizer.state_dict()["param_groups"][0]["lr"], epoch)
          
        if verbose:
            print(
                f'Time elapsed in current epoch: {(end_epoch - start_epoch):.2f} secs.')

        if CURRENT_VAL_ACC < BEST_VAL_ACC:
            BEST_VAL_ACC = CURRENT_VAL_ACC
            model_dict = {
                'epoch': epoch + 1,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'train_loss_per_batch': TRAIN_LOSS_EPOCH,
                'train_loss_epoch_mean': TRAIN_LOSS_GLOBAL[-1]
            }


        if checkpoint_every is not None and (epoch + 1) % checkpoint_every == 0:
            PATH = 'checkpoints/'
            ts = datetime.datetime.now().strftime("%d-%m-%Y_%H:%M")
            NAME = 'model_epoch' + str(epoch + 1) + '_' + str(ts) + '.pt'

            torch.save(model_dict, PATH + NAME)
            
    return TRAIN_LOSS_GLOBAL, VAL_LOSS_GLOBAL


def weights_init(model):
    if isinstance(model, nn.Conv2d):
        torch.nn.init.xavier_normal_(model.weight)
        if model.bias is not None:
          nn.init.constant_(model.bias.data, 0)

# how to apply

# 1) load model , ex: model = UNet(...)
# 2) model.apply(weights_init)

def train_model_2(model,
                criterion,
                optimizer,
                device,
                train_loader,
                epochs,
                val_loader,
                checkpoint_every=None,
                verbose=True,
                writer=None,
                scheduler=None,
                model_name='model',
                save_images=True):
    """ This train function evaluates on all the validation dataset one time per epoch

    Args:
        model (torch.model): [description]
        criterion (torch.criterion): [description]
        optimizer (torch.optim): [description]
        device ([type]): [description]
        train_loader ([type]): [description]
        epochs (int): [description]
        val_loader ([type]): [description]
        checkpoint_every (int, optional): [description]. Defaults to None.
        verbose (bool, optional): Print trainning status. Defaults to True.
        writer (tensorboard.writer, optional): Logs loss values to tensorboard. Defaults to None.
        scheduler ([type], optional): [description]. Defaults to None.

    Returns:
        TRAIN_LOSS_GLOBAL, VAL_LOSS_GLOBAL: Lists containing the mean error of each epoch
    """    
    TRAIN_LOSS_GLOBAL = [] #perists through epochs, stores the mean of each epoch
    VAL_LOSS_GLOBAL = []
    
    TIME = []

    BEST_VAL_ACC = 1e5
    
    if writer:
        in_frames, _ = next(iter(train_loader))
        in_frames = in_frames.to(device=device)
        writer.add_graph(model, input_to_model=in_frames, verbose=False)
        
    for epoch in range(epochs):
        start_epoch = time.time()
        TRAIN_LOSS_EPOCH = [] #stores values inside the current epoch

        for batch_idx, (in_frames, out_frames) in enumerate(train_loader):
            model.train()

            in_frames = in_frames.to(device=device)
            out_frames = out_frames.to(device=device)

            # forward
            frames_pred = model(in_frames)
            loss = criterion(frames_pred, out_frames)

            # backward
            optimizer.zero_grad()
            loss.backward()

            # gradient descent or adam step
            optimizer.step()

            TRAIN_LOSS_EPOCH.append(loss.detach().item())
            
        TRAIN_LOSS_GLOBAL.append(sum(TRAIN_LOSS_EPOCH)/len(TRAIN_LOSS_EPOCH))
        
        #evaluation
        model.eval()

        with torch.no_grad():
            VAL_LOSS_EPOCH = []
            for val_batch_idx, (in_frames, out_frames) in enumerate(val_loader):
                in_frames = in_frames.to(device=device)
                out_frames = out_frames.to(device=device)

                frames_pred = model(in_frames)
                val_loss = criterion(frames_pred, out_frames)

                VAL_LOSS_EPOCH.append(val_loss.detach().item())
                
                if writer and (val_batch_idx == 0) and save_images and epoch>35:
                    writer.add_images('groundtruth_batch', out_frames[:10], epoch)
                    writer.add_images('predictions_batch', frames_pred[:10], epoch)
                    
        VAL_LOSS_GLOBAL.append(sum(VAL_LOSS_EPOCH)/len(VAL_LOSS_EPOCH))

        if scheduler:
            scheduler.step(VAL_LOSS_GLOBAL[-1])
        
        end_epoch = time.time()
        TIME = end_epoch - start_epoch
        
        if verbose:
            # print statistics
            print(f'Epoch({epoch + 1}/{epochs}) | ', end='')
            print(f'Train_loss({(TRAIN_LOSS_GLOBAL[-1]):06.4f}) | Val_loss({VAL_LOSS_GLOBAL[-1]:.4f}) | ', end='')
            print(f'Time_Epoch({TIME:.2f}s)') # this part maybe dont print
                    
        if writer: 
            #add values to tensorboard 
            writer.add_scalar("TRAIN LOSS, EPOCH MEAN", TRAIN_LOSS_GLOBAL[-1], epoch)
            writer.add_scalar("VALIDATION LOSS, EPOCH MEAN", VAL_LOSS_GLOBAL[-1] , epoch)
            writer.add_scalar("Learning rate", optimizer.state_dict()["param_groups"][0]["lr"], epoch)            

        if VAL_LOSS_GLOBAL[-1] < BEST_VAL_ACC:
            if verbose:
                print('New Best Model')
            BEST_VAL_ACC = VAL_LOSS_GLOBAL[-1]
            model_dict = {
                'epoch': epoch + 1,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'train_loss_epoch_mean': TRAIN_LOSS_GLOBAL[-1],
                'val_loss_epoch_mean': VAL_LOSS_GLOBAL[-1]
            }
            model_not_saved = True

        if checkpoint_every is not None and (epoch + 1) % checkpoint_every == 0:
            if model_not_saved:
                if verbose:
                    print('Saving Checkpoint')
                PATH = 'checkpoints/'
                ts = datetime.datetime.now().strftime("%d-%m-%Y_%H:%M")
                NAME =  model_name + '_' + str(epoch + 1) + '_' + str(ts) + '.pt'

                torch.save(model_dict, PATH + NAME)
                model_not_saved = False
                
    # if training finished and best model not saved
    if model_not_saved:
        if verbose:
            print('Saving Checkpoint')
        PATH = 'checkpoints/'
        ts = datetime.datetime.now().strftime("%d-%m-%Y_%H:%M")
        NAME =  model_name + '_' + str(epoch + 1) + '_' + str(ts) + '.pt'

        torch.save(model_dict, PATH + NAME)
    
    return TRAIN_LOSS_GLOBAL, VAL_LOSS_GLOBAL


def train_model_SSIM(
                        model,
                        train_criterion,
                        val_criterion,
                        optimizer,
                        device,
                        train_loader,
                        epochs,
                        val_loader,
                        checkpoint_every=None,
                        verbose=True,
                        writer=None,
                        scheduler=None,
                        model_name='model',
                        save_images=True):
    
    """ This train function evaluates on all the validation dataset one time per epoch

    Args:
        model (torch.model): [description]
        criterion (torch.criterion): [description]
        optimizer (torch.optim): [description]
        device ([type]): [description]
        train_loader ([type]): [description]
        epochs (int): [description]
        val_loader ([type]): [description]
        checkpoint_every (int, optional): [description]. Defaults to None.
        verbose (bool, optional): Print trainning status. Defaults to True.
        writer (tensorboard.writer, optional): Logs loss values to tensorboard. Defaults to None.
        scheduler ([type], optional): [description]. Defaults to None.

    Returns:
        TRAIN_LOSS_GLOBAL, VAL_LOSS_GLOBAL: Lists containing the mean error of each epoch
    """    
    TRAIN_LOSS_GLOBAL = [] #perists through epochs, stores the mean of each epoch
    VAL_LOSS_GLOBAL = []
    
    TIME = []

    BEST_VAL_ACC = 1e5
    
    if writer:
        in_frames, _ = next(iter(train_loader))
        in_frames = in_frames.to(device=device)
        writer.add_graph(model, input_to_model=in_frames, verbose=False)
        
    for epoch in range(epochs):
        start_epoch = time.time()
        TRAIN_LOSS_EPOCH = [] #stores values inside the current epoch

        for batch_idx, (in_frames, out_frames) in enumerate(train_loader):
            model.train()

            in_frames = in_frames.to(device=device)
            out_frames = out_frames.to(device=device)

            # forward
            frames_pred = model(in_frames)
            loss = 1 - train_criterion(frames_pred, out_frames)

            # backward
            optimizer.zero_grad()
            loss.backward()

            # gradient descent or adam step
            optimizer.step()

            TRAIN_LOSS_EPOCH.append(loss.detach().item())
            
        TRAIN_LOSS_GLOBAL.append(sum(TRAIN_LOSS_EPOCH)/len(TRAIN_LOSS_EPOCH))
        
        #evaluation
        model.eval()

        with torch.no_grad():
            VAL_LOSS_EPOCH = []
            for val_batch_idx, (in_frames, out_frames) in enumerate(val_loader):
                in_frames = in_frames.to(device=device)
                out_frames = out_frames.to(device=device)

                frames_pred = model(in_frames)
                val_loss = val_criterion(frames_pred, out_frames)

                VAL_LOSS_EPOCH.append(val_loss.detach().item())
                
                if writer and (val_batch_idx == 0) and save_images and epoch>35:
                    writer.add_images('groundtruth_batch', out_frames[:10], epoch)
                    writer.add_images('predictions_batch', frames_pred[:10], epoch)
                    
        VAL_LOSS_GLOBAL.append(sum(VAL_LOSS_EPOCH)/len(VAL_LOSS_EPOCH))

        if scheduler:
            scheduler.step(VAL_LOSS_GLOBAL[-1])
        
        end_epoch = time.time()
        TIME = end_epoch - start_epoch
        
        if verbose:
            # print statistics
            print(f'Epoch({epoch + 1}/{epochs}) | ', end='')
            print(f'Train_loss({(TRAIN_LOSS_GLOBAL[-1]):06.4f}) | Val_loss({VAL_LOSS_GLOBAL[-1]:.4f}) | ', end='')
            print(f'Time_Epoch({TIME:.2f}s)') # this part maybe dont print
                    
        if writer: 
            #add values to tensorboard 
            writer.add_scalar("TRAIN LOSS, EPOCH MEAN", TRAIN_LOSS_GLOBAL[-1], epoch)
            writer.add_scalar("VALIDATION LOSS, EPOCH MEAN", VAL_LOSS_GLOBAL[-1] , epoch)
            writer.add_scalar("Learning rate", optimizer.state_dict()["param_groups"][0]["lr"], epoch)            

        if VAL_LOSS_GLOBAL[-1] < BEST_VAL_ACC:
            if verbose:
                print('New Best Model')
            BEST_VAL_ACC = VAL_LOSS_GLOBAL[-1]
            model_dict = {
                'epoch': epoch + 1,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'train_loss_epoch_mean': TRAIN_LOSS_GLOBAL[-1],
                'val_loss_epoch_mean': VAL_LOSS_GLOBAL[-1]
            }
            model_not_saved = True

        if checkpoint_every is not None and (epoch + 1) % checkpoint_every == 0:
            if model_not_saved:
                if verbose:
                    print('Saving Checkpoint')
                PATH = 'checkpoints/'
                ts = datetime.datetime.now().strftime("%d-%m-%Y_%H:%M")
                NAME =  model_name + '_' + str(epoch + 1) + '_' + str(ts) + '.pt'

                torch.save(model_dict, PATH + NAME)
                model_not_saved = False
                
    # if training finished and best model not saved
    if model_not_saved:
        if verbose:
            print('Saving Checkpoint')
        PATH = 'checkpoints/'
        ts = datetime.datetime.now().strftime("%d-%m-%Y_%H:%M")
        NAME =  model_name + '_' + str(epoch + 1) + '_' + str(ts) + '.pt'

        torch.save(model_dict, PATH + NAME)
    
    return TRAIN_LOSS_GLOBAL, VAL_LOSS_GLOBAL


def train_model_cyclicLR(   model,
                            criterion,
                            optimizer,
                            device,
                            train_loader,
                            epochs,
                            val_loader,
                            checkpoint_every=None,
                            verbose=True,
                            writer=None,
                            scheduler=None,
                            model_name='model',
                            save_images=True):
    """ This train function evaluates on all the validation dataset one time per epoch

    Args:
        model (torch.model): [description]
        criterion (torch.criterion): [description]
        optimizer (torch.optim): [description]
        device ([type]): [description]
        train_loader ([type]): [description]
        epochs (int): [description]
        val_loader ([type]): [description]
        checkpoint_every (int, optional): [description]. Defaults to None.
        verbose (bool, optional): Print trainning status. Defaults to True.
        writer (tensorboard.writer, optional): Logs loss values to tensorboard. Defaults to None.
        scheduler ([type], optional): [description]. Defaults to None.

    Returns:
        TRAIN_LOSS_GLOBAL, VAL_LOSS_GLOBAL: Lists containing the mean error of each epoch
    """    
    TRAIN_LOSS_GLOBAL = [] #perists through epochs, stores the mean of each epoch
    VAL_LOSS_GLOBAL = []
    
    TIME = []

    BEST_VAL_ACC = 1e5
    
    if writer:
        in_frames, _ = next(iter(train_loader))
        in_frames = in_frames.to(device=device)
        writer.add_graph(model, input_to_model=in_frames, verbose=False)
        
    for epoch in range(epochs):
        start_epoch = time.time()
        TRAIN_LOSS_EPOCH = [] #stores values inside the current epoch

        for batch_idx, (in_frames, out_frames) in enumerate(train_loader):
            model.train()

            in_frames = in_frames.to(device=device)
            out_frames = out_frames.to(device=device)

            # forward
            frames_pred = model(in_frames)
            loss = criterion(frames_pred, out_frames)

            # backward
            optimizer.zero_grad()
            loss.backward()

            # gradient descent or adam step
            optimizer.step()

            TRAIN_LOSS_EPOCH.append(loss.detach().item())
            
            if scheduler:
                scheduler.step()
            
        TRAIN_LOSS_GLOBAL.append(sum(TRAIN_LOSS_EPOCH)/len(TRAIN_LOSS_EPOCH))
        
        #evaluation
        model.eval()

        with torch.no_grad():
            VAL_LOSS_EPOCH = []
            for val_batch_idx, (in_frames, out_frames) in enumerate(val_loader):
                in_frames = in_frames.to(device=device)
                out_frames = out_frames.to(device=device)

                frames_pred = model(in_frames)
                val_loss = criterion(frames_pred, out_frames)

                VAL_LOSS_EPOCH.append(val_loss.detach().item())
                
                if writer and (val_batch_idx == 0) and save_images and epoch>35:
                    writer.add_images('groundtruth_batch', out_frames[:10], epoch)
                    writer.add_images('predictions_batch', frames_pred[:10], epoch)
                    
        VAL_LOSS_GLOBAL.append(sum(VAL_LOSS_EPOCH)/len(VAL_LOSS_EPOCH))

        
        
        end_epoch = time.time()
        TIME = end_epoch - start_epoch
        
        if verbose:
            # print statistics
            print(f'Epoch({epoch + 1}/{epochs}) | ', end='')
            print(f'Train_loss({(TRAIN_LOSS_GLOBAL[-1]):06.4f}) | Val_loss({VAL_LOSS_GLOBAL[-1]:.4f}) | ', end='')
            print(f'Time_Epoch({TIME:.2f}s)') # this part maybe dont print
                    
        if writer: 
            #add values to tensorboard 
            writer.add_scalar("TRAIN LOSS, EPOCH MEAN", TRAIN_LOSS_GLOBAL[-1], epoch)
            writer.add_scalar("VALIDATION LOSS, EPOCH MEAN", VAL_LOSS_GLOBAL[-1] , epoch)
            writer.add_scalar("Learning rate", scheduler.get_last_lr()[-1], epoch)            

        if VAL_LOSS_GLOBAL[-1] < BEST_VAL_ACC:
            if verbose:
                print('New Best Model')
            BEST_VAL_ACC = VAL_LOSS_GLOBAL[-1]
            model_dict = {
                'epoch': epoch + 1,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'train_loss_epoch_mean': TRAIN_LOSS_GLOBAL[-1],
                'val_loss_epoch_mean': VAL_LOSS_GLOBAL[-1]
            }
            model_not_saved = True

        if checkpoint_every is not None and (epoch + 1) % checkpoint_every == 0:
            if model_not_saved:
                if verbose:
                    print('Saving Checkpoint')
                PATH = 'checkpoints/'
                ts = datetime.datetime.now().strftime("%d-%m-%Y_%H:%M")
                NAME =  model_name + '_' + str(epoch + 1) + '_' + str(ts) + '.pt'

                torch.save(model_dict, PATH + NAME)
                model_not_saved = False
                
    # if training finished and best model not saved
    if model_not_saved:
        if verbose:
            print('Saving Checkpoint')
        PATH = 'checkpoints/'
        ts = datetime.datetime.now().strftime("%d-%m-%Y_%H:%M")
        NAME =  model_name + '_' + str(epoch + 1) + '_' + str(ts) + '.pt'

        torch.save(model_dict, PATH + NAME)
    
    return TRAIN_LOSS_GLOBAL, VAL_LOSS_GLOBAL