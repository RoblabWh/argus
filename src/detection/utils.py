from pycocotools.coco import COCO
import numpy as np
import warnings

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image

def assert_arguments(args):
    assert type(args.inputfolder) == str or type(args.img) == str, "Set an inputfolder with --inputfolder to your data or with --img a single image to process"
    assert ((type(args.checkpoints) and type(args.configs)) == list) or type(args.netfolders) == list, \
        "Either checkpoints and configs or netfolders must be specified."
    if not (type(args.netfolders) == list):
        assert (len(args.checkpoints) == len(args.configs)), "Number of checkpoints and configs must be equal or empty."
        assert (len(args.outfolders) == len(args.checkpoints) or len(args.outfolders) == 0), "For every network loaded specify one outfolder or no outfolder"
    else:
        assert (len(args.outfolders) == len(args.netfolders) or len(args.outfolders) == 0), "For every network loaded specify one outfolder or no outfolder"
    assert 0 <= args.score_thr <= 1, "Score threshold must be in [0, 1]."
    assert args.batch_size >= 1 and isinstance(args.batch_size, int), "Batch size must be greater than 0 and integer."
    if args.batch_size > 10:
        warnings.warn("Batch size is less than 10, which might lead to performance issues.")
    return

def inspect_coco(ann_file, img_prefix, id=0):

    coco_annotation = COCO(annotation_file=ann_file)

    # Category IDs.
    cat_ids = coco_annotation.getCatIds()
    print(f"Number of Unique Categories: {len(cat_ids)}")
    print("Category IDs:")
    print(str(cat_ids) + "\n")  # The IDs are not necessarily consecutive.

    # All categories.
    cats = coco_annotation.loadCats(cat_ids)
    cat_names = [cat["name"] for cat in cats]
    print("Categories Names:")
    print(str(cat_names) + "\n")

    # Category Name -> Category ID.
    for query_name in cat_names:
        query_id = coco_annotation.getCatIds(catNms=[query_name])[0]
        print(f"Category Name: {query_name}, Category ID: {query_id}")
        # Get the ID of all the images containing the object of the category.
        img_ids = coco_annotation.getImgIds(catIds=[query_id])
        print(f"Number of Images Containing {query_name}: {len(img_ids)}\n")

    # Pick one image.
    img_id = img_ids[id]
    img_info = coco_annotation.loadImgs([img_id])[0]
    img_file_name = img_info["file_name"]
    print(
        f"Image ID: {img_id}, File Name: {img_file_name}"
    )

    # Get all the annotations for the specified image.
    ann_ids = coco_annotation.getAnnIds(imgIds=[img_id], iscrowd=None)
    anns = coco_annotation.loadAnns(ann_ids)
    print(f"Annotations for Image ID {img_id}:")
    print(anns)

    # Load img
    img_url = Path(img_prefix) / Path(img_file_name)
    im = Image.open(img_url)

    # Save labeled version.
    my_dpi = 96
    plt.figure(figsize=(2400 / my_dpi, 2400 / my_dpi), dpi=my_dpi)
    plt.axis("off")
    plt.imshow(np.asarray(im))
    # Plot segmentation and bounding box.
    coco_annotation.showAnns(anns, draw_bbox=True)
    plt.savefig(f"{img_id}_annotated.jpg", bbox_inches="tight", pad_inches=0, dpi=my_dpi)
    return
