from mmdet.apis import DetInferencer
from mmengine import Config
from pathlib import Path

import sys
import os


class InferenceEngine:

    def __init__(self, device='cuda:0', out_folders=[], network_folders=None, configs=None, checkpoints=None):
        """
        The InferenceEngine class is used to run the inference of a MMDetection Net on a folder of images.

        :param device: 'cpu' or 'cuda:0'
        :param out_folders: List of output folders for the images to save (not used for single image; use out_file instead)
        :param network_folder: Folder where checkpoints and configs are. If provided, the files in this folder are used
        :param config: Config file for MMDetection
        :param checkpoint: Checkpoint file for MMDetection
        """

        # number of networks to load
        if type(network_folders) is not type(type):
            cnt_networks = len(network_folders) if (len(network_folders) > 0) else len(checkpoints)
        else:
            cnt_networks = len(checkpoints)
        self.out_folders = []
        self.models = []
        self.configs = []
        self.device = device

        for loading_idx in range(cnt_networks):
            if out_folders:
                self.out_folders.append(out_folders[loading_idx])
            else:
                self.out_folders.append('')

            # build the model from a config file and a checkpoint file
            if type(network_folders) is not type(type):
                config, checkpoint = self.get_files_(network_folders[loading_idx])
            else:
                config = configs[loading_idx]
                checkpoint = checkpoints[loading_idx]

            # Build the model from a config file and a checkpoint file using the DetInferencer class
            self.models.append(DetInferencer(model=config, weights=checkpoint, device=self.device))
            self.configs.append(Config.fromfile(config))

    def add_model(self, network_folder, out_folder=None):
        """
        Adds a model to the inference engine.
        :param network_folder:
        :param out_folder:
        :return:
        """
        config, checkpoint = self.get_files_(network_folder)
        # Build the model from a config file and a checkpoint file using the DetInferencer class
        self.models.append(DetInferencer(model=config, weights=checkpoint, device=self.device))
        self.configs.append(Config.fromfile(config))
        self.out_folders.append(out_folder)

    def remove_model(self, network_folder):
        """
        Removes a model from the inference engine.
        :param network_folder:
        :return:
        """
        config, checkpoint = self.get_files_(network_folder)
        for i, model in enumerate(self.models):
            if model.cfg.filename == config:
                self.models.pop(i)
                self.configs.pop(i)
                self.out_folders.pop(i)
                break

    def get_files_(self, network_folder):
        """
        Returns the config and checkpoint file of a network folder.
        :param network_folder:
        :return:
        """
        network_folder = Path(network_folder)
        config = []
        checkpoint = []
        for root, dirs, files in os.walk(network_folder):
            for file in files:
                basename = os.path.basename(file).lower()
                ext = os.path.splitext(basename)[-1].lower()
                if ext == '.py':
                    config.append(os.path.join(root, file))
                elif ext == '.pth':
                    checkpoint.append(os.path.join(root, file))

        if len(config) > 1 or len(config) == 0:
            print("Config file not found in %s. Maybe multiples?" % str(network_folder))
            sys.exit(1)
        if len(checkpoint) > 1 or len(checkpoint) == 0:
            print("Checkpoint file not found in %s. Maybe multiples?" % str(network_folder))
            sys.exit(1)
        return config[0], checkpoint[0]

    def inference_all(self, data, score_thr, batch_size):
        """
        Runs the inference on a batch of images for all models loaded.
        :param batches:
        :return:
        """

        results = []
        for i, model in enumerate(self.models):
            result = model(data, batch_size=batch_size, return_datasample=True, no_save_vis=False, pred_score_thr=score_thr, out_dir=self.out_folders[i])
            results.append(result)

        return results
