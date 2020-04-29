import math
import os
import shutil

import torch
from collections import OrderedDict


def extract_checkpoint_data(args, model):
    best_rms_error = math.inf

    epoch = 1
    rms_errors = []
    best_rms_errors = []
    learning_rates = []

    if not args.reset:
        saved = load_checkpoint(args.output_path, args.device)
        if saved:
            epoch = saved.get('epoch', epoch)
            best_rms_error = saved.get('best_RMSError', best_rms_error)
            rms_errors = saved.get('RMSErrors', rms_errors)
            best_rms_errors = saved.get('best_RMSErrors', best_rms_errors)
            learning_rates = saved.get('learning_rates', learning_rates)
            print(
                'Loading checkpoint : [Epoch: %d | RMSError: %.5f].' % (
                    epoch,
                    best_rms_error)
            )

            # We should start training on the epoch after the last full epoch
            epoch = epoch + 1

            try:
                state = saved['state_dict']
                model.load_state_dict(state)
            except RuntimeError:
                # The most likely cause of a failure to load is that there is a leading "module." from training. This is
                # normal for models trained with DataParallel. If not using DataParallel, then the "module." needs to be
                # removed.
                state = remove_module_from_state(saved)
                model.load_state_dict(state)
        else:
            print('Warning: Could not read checkpoint!')

    return rms_errors, best_rms_error, best_rms_errors, epoch, learning_rates


def load_checkpoint(checkpoints_path, device, filename='checkpoint.pth.tar'):
    filename = os.path.join(checkpoints_path, filename)
    print(filename)
    if not os.path.isfile(filename):
        return None
    state = torch.load(filename, map_location=device)
    return state


def save_checkpoint(state, is_best, checkpointsPath, saveCheckpoints, filename='checkpoint.pth.tar'):
    resultsFilename = os.path.join(checkpointsPath, 'results.json')
    checkpointFilename = os.path.join(checkpointsPath, filename)

    torch.save(state, checkpointFilename)

    if saveCheckpoints:
        shutil.copyfile(checkpointFilename,
                        os.path.join(checkpointsPath, 'checkpoint' + str(state['epoch']) + '.pth.tar'))
        shutil.copyfile(resultsFilename, os.path.join(checkpointsPath, 'results' + str(state['epoch']) + '.json'))
        shutil.copyfile('ITrackerModel.py', os.path.join(checkpointsPath, 'ITrackerModel.py'))
        shutil.copyfile('ITrackerData.py', os.path.join(checkpointsPath, 'ITrackerData.py'))

    bestFilename = os.path.join(checkpointsPath, 'best_' + filename)
    bestResultsFilename = os.path.join(checkpointsPath, 'best_results.json')

    if is_best:
        shutil.copyfile(checkpointFilename, bestFilename)
        shutil.copyfile(resultsFilename, bestResultsFilename)


def remove_module_from_state(saved_state):
    # when using Cuda for training we use DataParallel. When using DataParallel, there is a
    # 'module.' added to the namespace of the item in the dictionary.
    # remove 'module.' from the front of the name to make it compatible with cpu only
    state = OrderedDict()

    for key, value in saved_state['state_dict'].items():
        state[key[7:]] = value.to(device='cpu')

    return state