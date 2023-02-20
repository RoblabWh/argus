import os
from pathlib import Path

from datahandler import DataHandler
from InferenceEngine import InferenceEngine

number_of_networks = 4

def main():
    networks_weights_folder = "./model_weights"
    weights_paths_list = []

    weights_paths_list.append(networks_weights_folder + "/deformable_detr_twostage_refine_r50_16x2_50e_coco_fire_04")
    if number_of_networks >= 2:
        weights_paths_list.append(networks_weights_folder + "/tood_r101_fpn_dconv_c3-c5_mstrain_2x_coco_fire_5")
        if number_of_networks >= 3:
            weights_paths_list.append(networks_weights_folder + "/vfnet_x101_32x4d_fpn_mdconv_c3-c5_mstrain_2x_coco_fire_1")
            if number_of_networks >= 4:
                weights_paths_list.append(networks_weights_folder + "/yolox_s_8x8_300e_coco_fire_300_4")
                if number_of_networks >= 5:
                    weights_paths_list.append(networks_weights_folder + "/autoassign_r50_fpn_8x2_1x_coco_fire_0")

    images_path_list = []
    #add all images to list found in directory images
    for file in os.listdir("images"):
        if file.endswith(".JPG") or file.endswith(".jpg") or file.endswith(".png") or file.endswith(".PNG"):
            images_path_list.append(os.path.join("images", file))

    config_path = "config/custom/config.py"
    ann_path = "ann2.json" # vom project manager geben lassen

    data_handler = DataHandler(config_path, ann_path)
    data_handler.set_image_paths(images_path_list, 2)
    data_handler.create_empty_ann()

    engine = InferenceEngine(network_folders=weights_paths_list)
    results = engine.inference_all(data_handler, 0.3)
    bboxes = data_handler.compare_results(results)
    data_handler.create_coco()
    #data_handler.save_images("result", bboxes, engine.models[0], 0.3)
    data_handler.save_results_in_json(bboxes)
    data_handler.structure_ann_by_images()


if __name__ == '__main__':
    main()