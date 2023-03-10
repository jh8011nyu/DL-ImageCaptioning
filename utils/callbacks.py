'''
callback classes to monitor the training process
'''

from .logger import Logger
import torch
import os
#import json

class Callbacks:
    def __init__(self,
                 logger: Logger, 
                 output_dir: str,
                 save_final_model: bool=False):
        self.logger = logger
        self.save_final_model = save_final_model
        self.output_dir = output_dir

        self.best_score = 0.0
        self.mode = "max"
    
    def better_score(self, score: float) -> bool:
        '''
        check if score improves
        '''
        if self.mode == "max":
            return (score-self.best_score) > self.threshold
        elif self.mode == "min":
            return (self.best_score-score) > self.threshold

    def save_checkpoint(self, model):
        '''
        save new best model
        '''
        self.logger.log_message(f"Saving new best-model with accuracy: {self.best_score:.4f}")
        torch.save(model.state_dict(), os.path.join(self.output_dir, "best-model.pt"))

    def exit_training(self, model):
        '''
        quit training
        '''
        self.logger.log_block(f"Exiting from training early. Best model score: {self.best_score:.4f}. Saving final model: {self.save_final_model} ")
        if self.save_final_model:
            self.logger.log_message("Saving model ...")
            torch.save(model.state_dict(), os.path.join(self.output_dir, "final-model.pt"))
            self.logger.log_message("Done.")


class EarlyStopping(Callbacks):
    '''
    exit training when model stops improving for more than patient number of epochs

    Parameters:
    ===========
    `logger`: logger object
    `output_dir`: output path to save log file and model checkpoint
    `save_final_model`: saving model before exiting the training
    `patience`: number of epochs to ignore before early stopping
    `mode`: `max` or `min`. max means model is looking for higher score
    `threshold`: value to determine if this epoch is bad
    '''
    def __init__(self, 
                 logger: Logger,
                 output_dir: str,
                 save_final_model :bool=False,
                 patience: int=5, 
                 mode :str="max", 
                 threshold: float=0.0001):
        super().__init__(logger, output_dir, save_final_model)

        self.patience = patience
        self.mode = mode
        self.threshold = threshold

        self.best_score = 0.0 if self.mode == "max" else float("inf")
        self.num_bad_epoch = 0

    def __call__(self, model, score: float):
        '''
        save model for new best score, else check for early stopping condition
        '''
        if self.better_score(score):
            self.best_score = score
            self.num_bad_epoch = 0
            self.save_checkpoint(model)
            return True
        else:
            self.num_bad_epoch += 1
            self.logger.log_new_line()
            self.logger.log_message(f"Bad Epoch. Total num bad epoch: {self.num_bad_epoch}")
            if self.num_bad_epoch >= self.patience:
                self.exit_training(model)
                return False
            return True

    def save_epoch_checkpoint(self, model):
        self.logger.log_new_line()
        self.logger.log_message(f'Saving Epoch Checkpoint')
        torch.save(model.state_dict(), os.path.join(self.output_dir, "checkpoint-model.pt"))

    def save_state_dict_checkpoint(self, epoch, lr_scheduler, optimizer):
        torch.save({
            'epoch':epoch,
            'scheduler':lr_scheduler.state_dict(),
            'optimizer':optimizer.state_dict()
        },
        os.path.join(self.output_dir, 'state_dict_checkpoint.pt'))