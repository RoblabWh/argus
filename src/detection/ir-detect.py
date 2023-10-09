import argparse
import utils as u
from datahandler import DataHandler
from annotationhandler import AnnotationHandler
from inference_engine import InferenceEngine


def main():

    parser = argparse.ArgumentParser(description='Inference for MMDetection')
    # Single Image, if --img is None, the input folder is used and searched for images
    parser.add_argument('--img', default=None, help='Input Image Path')
    parser.add_argument('--out_file', default='result.jpg', help='Output file for MMDetection')
    parser.add_argument('--create_coco', default=False, help='Create coco annotation file with the results from the inference')
    parser.add_argument('--netfolders', default=str, nargs='+', help='List of folders where checkpoints and configs are '
                                                                     'if provided, the files in this folder are used'
                                                                     'and other params are ignored')
    parser.add_argument('--configs', default=str, nargs='+', help='Config file/s for MMDetection')
    parser.add_argument('--checkpoints', default=str, nargs='+', help='Checkpoint file/s for MMDetection')
    parser.add_argument('--inputfolder', default=str, help='Input folder that is searched')
    parser.add_argument('--outfolders', type=str, nargs='+', default=[], help='Output folder/s for the images to save (not used for single image; use out_file instead)')
    parser.add_argument('--extensions', type=str, nargs='+', default=['.jpg'], help='File extensions that are searched for')
    parser.add_argument('--pattern', default='.', help='Regex Pattern for input images')
    parser.add_argument('--include_subdirs', default=False, help='Searches images additionally in all subdirs of input_folder (default: False)')
    parser.add_argument('--score_thr', default=0.5, help='Threshold for BBox Detection (default: 0.5)')
    parser.add_argument('--batch_size', default=5, help='Batch size for Model (default: 5)')
    #parser.add_argument('--split_images', type=bool, default=False, help='Split images into tiles fore more precise detection (default: False)')
    parser.add_argument('--split_images', action='store_true', help='Split images into tiles fore more precise detection (default: False)')
    args = parser.parse_args()
    u.assert_arguments(args)

    engine = InferenceEngine(out_folders=args.outfolders, configs=args.configs,
                             checkpoints=args.checkpoints, network_folders=args.netfolders)

    # Init DataHandler
    datahandler = DataHandler(args)
    if args.split_images:
        print("option --split_images is set, images will be split into tiles")
        datahandler.preprocess()
    data = datahandler.get_image_paths_str()

    # No PyTorch DataLoader needed because MMDetection implements its own DataLoader
    # dataloader = DataLoader(datahandler, batch_size=2, shuffle=False)

    # Inference, sometimes the matplotlib backend crashes, then saving won't work. Try again.
    results = engine.inference_all(data, score_thr=args.score_thr, batch_size=args.batch_size)
    # print("results: ", str(results))
    if args.split_images:
        datahandler.postprocess_images(results=results)
    results = datahandler.merge_bboxes(results=results)

    # Create AnnotationFile from Results
    if args.create_coco:
        annotationhandler = AnnotationHandler(args)
        annotationhandler.create_empty_ann(datahandler.image_paths)
        annotationhandler.save_results_in_json(results)


if __name__ == '__main__':
    main()