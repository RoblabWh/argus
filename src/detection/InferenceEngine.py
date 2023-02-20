from mmdet.apis import init_detector, inference_detector
from pathlib import Path

import sys
import os


def inference(model, batches):
    """
    Runs the inference on a batch of images.
    :param batches:
    :return:
    """
    results = []
    for batch in batches:
        result = inference_detector(model, batch)
        for single in result:
            results.append(single)
    return results


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
        if network_folders is not None:
            cnt_networks = len(network_folders) if (len(network_folders) > 0) else len(checkpoints)
        else:
            cnt_networks = 0
        self.out_folders = []
        self.models = []

        for loading_idx in range(cnt_networks):
            if out_folders:
                self.out_folders.append(out_folders[loading_idx])
            else:
                self.out_folders.append(None)

            # build the model from a config file and a checkpoint file
            if network_folders:
                config, checkpoint = self.get_files(network_folders[loading_idx])
            else:
                config = configs[loading_idx]
                checkpoint = checkpoints[loading_idx]

            self.models.append(init_detector(config, checkpoint, device=device))

    def add_model(self, network_folder, out_folder=None):
        """
        Adds a model to the inference engine.
        :param network_folder:
        :param out_folder:
        :return:
        """
        config, checkpoint = self.get_files(network_folder)
        self.models.append(init_detector(config, checkpoint, device='cuda:0'))
        self.out_folders.append(out_folder)

    def remove_model(self, network_folder):
        """
        Removes a model from the inference engine.
        :param network_folder:
        :return:
        """
        config, checkpoint = self.get_files(network_folder)
        for i, model in enumerate(self.models):
            if model.cfg.filename == config:
                self.models.pop(i)
                self.out_folders.pop(i)
                break

    def get_files(self, network_folder):
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
            print("Config file not found in %s" % str(network_folder))
            sys.exit(1)
        if len(checkpoint) > 1 or len(checkpoint) == 0:
            print("Checkpoint file not found in %s" % str(network_folder))
            sys.exit(1)
        return config[0], checkpoint[0]

    def inference_all(self, datahandler, score_thr):
        """
        Runs the inference on a batch of images for all models loaded.
        :param batches:
        :return:
        """

        results = []
        for i, model in enumerate(self.models):
            result = inference(model, datahandler.batches)
            datahandler.apply_threshold_to_results([result], score_thr)
            #datahandler.save_images(self.out_folders[i], result, model, score_thr)
            results.append(result)

        return results
