import json
import cv2
import copy
import numpy as np
import warnings


def empty_coco_ann():
    annotations = {'images': [], 'categories': [
        {
            "supercategory": "Defect",
            "id": 1,
            "name": "fire"
        },
        {
            "supercategory": "Defect",
            "id": 2,
            "name": "vehicle"
        },
        {
            "supercategory": "Defect",
            "id": 3,
            "name": "human"
        }
    ], 'annotations': []}
    return annotations


def read_json(path):
    """
    A function that reads a json file and returns the data.
    :param path:
    :return:
    """
    with open(path) as f:
        data = json.load(f)
    return data


def draw_bboxes(img, bboxes, category_id):
    """
    A function that draws bounding boxes on an image.
    :param img:
    :param bboxes:
    :return:
    """
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]

    if category_id >= len(colors):
        color = (255, 255, 255)
    else:
        color = colors[category_id]

    categories = ["fire", "vehicle", "human"]

    for bbox in bboxes:
        x, y, w, h = bbox
        # Display BBOX
        cv2.rectangle(img, (int(x), int(y)), (int(x + w), int(y + h)), color, 2)

        # Display category ID
        text_position = (int(x + w) - 30, int(y) + 20)
        cv2.putText(img, str(category_id) + categories[category_id], text_position, cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    return img


def compare_images(img1, img2, threshold=10):
    """
    A function that compares two images and returns if they are the same.
    :param img1:
    :param img2:
    :param threshold:
    :return:
    """
    diff = cv2.absdiff(img1, img2)
    diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    diff = cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)[1]
    return not np.any(diff)


# TODO testen
def delete_from_json_images(json_file, img_names):
    """
    A function that deletes an image and its annotations from a json file.
    :param json_file: Annotation file
    :param img_names: Image basenames list
    :return:
    """
    with open(json_file) as f:
        data = json.load(f)
    new_images = []
    deleted_ids = []
    for img in data['images']:
        if img['file_name'] not in img_names:
            new_images.append(img)
        else:
            deleted_ids.append(img['id'])

    data['images'] = new_images
    with open(json_file, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    delete_from_json_annotation(json_file, deleted_ids)

def delete_images_from_json(json_file, images):
    """
    A function that deletes images from a json file.
    :param json_file:
    :param images:
    """
    with open(json_file) as f:
        data = json.load(f)
    new_images = []
    for img in data['images']:
        if img['file_name'] not in images:
            new_images.append(img)

    data['images'] = new_images
    with open(json_file, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def delete_from_json_annotation(json_file, annotation):
    """
    A function that deletes an annotation from a json file.
    :param json_file:
    :param annotation:
    :return:
    """
    with open(json_file) as f:
        data = json.load(f)
    new_annotations = []
    for ann in data['annotations']:
        if ann['image_id'] not in annotation:
            new_annotations.append(ann)
    data['annotations'] = new_annotations
    with open(json_file, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def group_annotations_by_image(annotations):
    grouped_annotations = {}
    for ann in annotations:
        if ann["image_id"] not in grouped_annotations:
            grouped_annotations[ann["image_id"]] = []
        grouped_annotations[ann["image_id"]].append(ann)
    return grouped_annotations


def update_annotations(coco_data, new_images, intersection_threshold=0.15):
    """
    A function that updates the annotations of a COCO dataset normally called after the dataset was splitted.
    :param coco_data: loaded JSON file of a COCO dataset in a dictionary
    :param new_images: list of images to add that where created by splitting the original images
                       [("00000_1.jpg", x1, y1, width1, height1), ...]
    :return: new COCO dataset
    """
    new_annotations = []
    new_images_data = []
    starting_image_id = len(coco_data["images"])
    starting_annotation_id = len(coco_data["annotations"])

    for new_image_name, x, y, width, height in new_images:
        # Find the original image ID by its file name
        original_image_id = None
        for image in coco_data["images"]:
            if image["file_name"] == new_image_name.split("_")[0] + ".jpg":
                original_image_id = image["id"]
                break

        if original_image_id is None:
            print(f"Original image not found for {new_image_name}")
            continue

        # Create new image data entry
        new_image_data = copy.deepcopy(image)
        new_image_data["file_name"] = new_image_name
        new_image_data["id"] = starting_image_id + len(new_images_data) + 1
        new_image_data["width"] = width
        new_image_data["height"] = height
        new_images_data.append(new_image_data)

        # Update the annotations for the new image
        for annotation in coco_data["annotations"]:
            if annotation["image_id"] == original_image_id:
                new_annotation = copy.deepcopy(annotation)
                new_annotation["id"] = starting_annotation_id + len(new_annotations) + 1
                new_annotation["image_id"] = new_image_data["id"]

                # Update the bounding box coordinates
                old_x, old_y, old_w, old_h = new_annotation["bbox"]
                new_x = max(0, old_x - x)
                new_y = max(0, old_y - y)
                new_w = min(width - new_x, min(old_w, old_x + old_w - x))
                new_h = min(height - new_y, min(old_h, old_y + old_h - y))

                # Check if the bounding box intersects the new image by more than the threshold
                # That's not exactly using old_x and old_y here, but shouldn't be a broblem
                intersection_ratio = calc_iou([old_x, old_y, new_w, new_h], new_annotation['bbox'])

                if intersection_ratio >= intersection_threshold:
                    new_annotation["bbox"] = [new_x, new_y, new_w, new_h]
                    new_annotations.append(new_annotation)

    # Update the COCO data with the new image data and annotations
    coco_data["images"] = new_images_data
    coco_data["annotations"] = new_annotations

    return coco_data


def calc_iou(bbox1, bbox2):
    """
    Calculates the IoU for two bounding boxes
    :param bbox1: bounding box 1 in COCO format [x, y, width, height]
    :param bbox2: bounding box 2 in COCO format [x, y, width, height]
    :return: IoU
    """
    x1 = max(bbox1[0], bbox2[0])
    y1 = max(bbox1[1], bbox2[1])
    x2 = min(bbox1[0] + bbox1[2], bbox2[0] + bbox2[2])
    y2 = min(bbox1[1] + bbox1[3], bbox2[1] + bbox2[3])
    w = max(0, x2 - x1)
    h = max(0, y2 - y1)
    inter = w * h
    area1 = bbox1[2] * bbox1[3]
    area2 = bbox2[2] * bbox2[3]
    union = area1 + area2 - inter
    if union == 0:
        iou = 0
    else:
        iou = inter / union

    return iou


def split_image(image):
    """
    Splits the image if it's too large, recursively checks if the new images are too large, too.
    :param image: image to split
    :return: list of images along with their coordinates in the original image
    """
    h, w = image.shape[:2]
    if h > 1200 or w > 1200:
        image_coordinates = split_image_into_four(image)
        new_images = []
        for img, x, y in image_coordinates:
            for sub_img, sub_x, sub_y in split_image(img):
                new_images.append((sub_img, x + sub_x, y + sub_y))
        return new_images
    else:
        return [(image, 0, 0)]


def split_image_into_four(image):
    """
    Splits a large image into four smaller ones.
    :param image: large image
    :return: list of four smaller images along with their coordinates in the original image
    """
    h, w = image.shape[:2]
    overlap = 0
    h2 = h // 2
    w2 = w // 2

    return [
        (image[:h2 + overlap, :w2 + overlap], 0, 0),
        (image[:h2 + overlap, w2 - overlap:], w2 - overlap, 0),
        (image[h2 - overlap:, :w2 + overlap], 0, h2 - overlap),
        (image[h2 - overlap:, w2 - overlap:], w2 - overlap, h2 - overlap),
    ]


def assert_arguments(args):
    """
    Asserts that the arguments are valid. If not, the program is terminated.
    :param args: arguments
    """
    assert type(args.inputfolder) == str or type(
        args.img) == str, "Set an inputfolder with --inputfolder to your data or with --img a single image to process"
    assert ((type(args.checkpoints) and type(args.configs)) == list) or type(args.netfolders) == list, \
        "Either checkpoints and configs or netfolders must be specified."
    if not (type(args.netfolders) == list):
        assert (len(args.checkpoints) == len(args.configs)), "Number of checkpoints and configs must be equal or empty."
        assert (len(args.outfolders) == len(args.checkpoints) or len(
            args.outfolders) == 0), "For every network loaded specify one outfolder or no outfolder"
    else:
        assert (len(args.outfolders) == len(args.netfolders) or len(
            args.outfolders) == 0), "For every network loaded specify one outfolder or no outfolder"
    assert 0 <= args.score_thr <= 1, "Score threshold must be in [0, 1]."
    assert args.batch_size >= 1 and isinstance(args.batch_size, int), "Batch size must be greater than 0 and integer."
    if args.batch_size > 10:
        warnings.warn("Batch size is less than 10, which might lead to performance issues.")
    return