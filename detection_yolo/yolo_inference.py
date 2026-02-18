from ultralytics import YOLO
from PIL import Image
import numpy as np
import os
import logging

import math

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING)

class YOLOInferencer:
    def __init__(self, model_name="yolo11m.pt", imgsz=640, device="cuda:0", progress_callback=None):
        self.model = YOLO(model_name)
        self.imgsz = imgsz
        self.device = device
        self.progress_callback = progress_callback


    def generate_sliding_windows(self, img, depths=1, overlap=0.20, min_tile=96):
        """
        Returns:
            tiles:   [PIL.Image]
            offsets: [(x_offset, y_offset)]
            W, H    : original dimensions
        """
        W, H = img.size
        min_side = min(W, H)

        tiles = []
        offsets = []

        for depth in range(depths):
            # tile size shrinks per depth
            base = min_side / (2 ** depth)
            tile_size = int(base * (1 + overlap))

            if tile_size < min_tile:
                break

            # sliding stride (controls overlap)
            stride = int(tile_size * (1 - overlap))
            if stride < 32:
                stride = tile_size  # failsafe

            for y in range(0, H, stride):
                for x in range(0, W, stride):
                    x2 = min(x + tile_size, W)
                    y2 = min(y + tile_size, H)

                    tiles.append(img.crop((x, y, x2, y2)))
                    offsets.append((x, y))

                    if x2 == W:
                        break
                if y2 == H:
                    break

        return tiles, offsets, W, H
    
    def global_nms(self, dets, iou_thresh=0.50, fuse_thresh=0.90, merge_classes=None):
        """
        det = { 'bbox': [xmin, ymin, w, h], 'score': float, 'category_name': str }
        """
        if not dets:
            return []
    
        if merge_classes is None:
            merge_classes = set()

        boxes = []
        scores = []
        labels = []

        for det in dets:
            x, y, w, h = det["bbox"]
            boxes.append([x, y, x+w, y+h])
            scores.append(det["score"])
            labels.append(det["category_name"])

        boxes = np.array(boxes)
        scores = np.array(scores)
        labels = np.array(labels)

        used = np.zeros(len(dets), dtype=bool)
        output = []

        # --------------------------------
        # NMS per class
        # --------------------------------
        for cls in set(labels):
            cls_idxs = np.where(labels == cls)[0]
            cls_boxes = boxes[cls_idxs].copy()
            cls_scores = scores[cls_idxs].copy()

            order = np.argsort(-cls_scores)
            cls_idxs = cls_idxs[order]
            cls_boxes = cls_boxes[order]

            while len(cls_idxs) > 0:
                i = cls_idxs[0]

                if not used[i]:
                    used[i] = True

                keep_box = boxes[i].copy()
                keep_score = scores[i]
                keep_label = labels[i]

                # --------------------------------
                # Compute IoU with remaining boxes
                # --------------------------------
                if len(cls_idxs) > 1:
                    rest = cls_idxs[1:]
                    rest_boxes = cls_boxes[1:]

                    xx1 = np.maximum(keep_box[0], rest_boxes[:,0])
                    yy1 = np.maximum(keep_box[1], rest_boxes[:,1])
                    xx2 = np.minimum(keep_box[2], rest_boxes[:,2])
                    yy2 = np.minimum(keep_box[3], rest_boxes[:,3])

                    inter = np.maximum(0, xx2-xx1) * np.maximum(0, yy2-yy1)
                    area_keep = (keep_box[2]-keep_box[0]) * (keep_box[3]-keep_box[1])
                    area_rest = (rest_boxes[:,2]-rest_boxes[:,0]) * (rest_boxes[:,3]-rest_boxes[:,1])
                    union = area_keep + area_rest - inter
                    iou = inter / np.maximum(union, 1e-6)

                    # Normal NMS suppression
                    suppressed = iou >= iou_thresh

                    # ------------------------------------------
                    # EXTRA: cross-class fusion for merge group
                    # ------------------------------------------
                    for j, idx in enumerate(rest):
                        if used[idx]:
                            continue
                        if iou[j] >= fuse_thresh:
                            # same merge group?
                            merge_classes_list = []
                            for key, val in merge_classes.items():
                                if keep_label in val:
                                    merge_classes_list = val
                                    break
                            if keep_label in merge_classes_list and labels[idx] in merge_classes_list:
                                # ---- fuse bounding boxes ----
                                b2 = boxes[idx]
                                s2 = scores[idx]
                                l2 = labels[idx]

                                # weighted average by score
                                keep_box = (keep_box * keep_score + b2 * s2) / (keep_score + s2)

                                # keep highest score label
                                if s2 > keep_score:
                                    keep_label = l2

                                keep_score = max(keep_score, s2)

                                used[idx] = True
                                suppressed[j] = True

                    remain = np.where(~suppressed)[0]
                    cls_idxs = cls_idxs[remain+1]
                    cls_boxes = cls_boxes[remain+1]
                else:
                    cls_idxs = []

                super_label = None
                for key, val in merge_classes.items():
                    if keep_label in val:
                        super_label = key
                        break
                # Save fused/kept detection
                xmin, ymin, xmax, ymax = keep_box
                output.append({
                    "bbox": [xmin, ymin, xmax-xmin, ymax-ymin],
                    "score": float(keep_score),
                    "category_name": keep_label if not super_label else super_label
                })

        return output
    
    def convert_yolo_boxes(self, result, x_offset, y_offset, class_map):
        out = []
        for box in result.boxes:
            xyxy = box.xyxy[0].cpu().numpy()
            cls = int(box.cls)
            score = float(box.conf)

            xmin, ymin, xmax, ymax = xyxy

            out.append({
                "bbox": [
                    float(xmin + x_offset),
                    float(ymin + y_offset),
                    float(xmax - xmin),
                    float(ymax - ymin)
                ],
                "score": score,
                # "category_name": "vehicle" if class_map[cls] != "pedestrian" else class_map[cls]
                "category_name": class_map[cls]
            })

        return out
    

    def infer_image(self, img, depths=2, overlap=0.20, batch_size=2):
        """
        Run YOLO:
          1) once on the full-res image
          2) many times on sliding-window tiles
          3) merge + global NMS
        """
        # ----------------------------
        # 1) Full-image inference
        # ----------------------------
        full_res = self.model(img, device=self.device, imgsz=self.imgsz)[0]
        class_map = full_res.names

        results = self.convert_yolo_boxes(full_res, 0, 0, class_map)

        # ----------------------------
        # 2) Sliding window inference
        # ----------------------------
        tiles, offsets, W, H = self.generate_sliding_windows(img, depths, overlap)

        # for tile, (ox, oy) in zip(tiles, offsets):
        #     r = self.model(tile, device=self.device)[0]
        #     tile_boxes = self.convert_yolo_boxes(r, ox, oy, class_map)
        #     results.extend(tile_boxes)

        all_results = []
        n = len(tiles)

        for i in range(0, n, batch_size):
            batch = tiles[i:i + batch_size]

            # YOLO accepts list of PIL images directly
            preds = self.model(batch, device=self.device)

            # preds is a List[Result]; extend the accumulator
            all_results.extend(preds)


        # Restore global coords
        for r, (ox, oy) in zip(all_results, offsets):
            results.extend(self.convert_yolo_boxes(r, ox, oy, class_map))



        # ----------------------------
        # 3) Global NMS merging
        # ----------------------------
        MERGE_CLASSES = {"land_vehicle": ["car", "bus", "truck", "van", "vehicle",  "tractor", "trailer", "awning-tricycle", "tricycle"],
                         "small_vehicle": ["motor", "bicycle"]}

        outputs = self.global_nms(results, iou_thresh=0.50, merge_classes=MERGE_CLASSES)

        return outputs
    
    def run(self, images):
        final_results = []

        for idx, image in enumerate(images):
            img_path = image["url"]

            # Load image
            img = Image.open(img_path).convert("RGB")

            detections = self.infer_image(img, depths=2, overlap=0.25, batch_size=16)

            for det in detections:
                det["image_id"] = image["id"]

            final_results.extend(detections)

            # if(idx % 2) == 0:
            #     logger.info(f"[YOLOInferencer] Processing image {idx+1}/{len(images)}")
            #     if self.progress_callback:
            #         self.progress_callback(idx + 1, len(images), f"Processed {idx + 1} of {len(images)} images")

        return final_results




    # # ----------------------------------------------------
    # # Split image into  6 equal tiles
    # # ----------------------------------------------------
    # def split_into_tiles(self, img: Image.Image):
    #     w, h = img.size
    #     w2, h2 = w // 3, h // 3

    #     # tiles = {
    #     #     "TL": img.crop((0,    0,    w2,  h2)),
    #     #     "TR": img.crop((w2,   0,    w,   h2)),
    #     #     "BL": img.crop((0,    h2,   w2,  h)),
    #     #     "BR": img.crop((w2,   h2,   w,   h)),
    #     # }
    #     tiles = {
    #         "TL": img.crop((0,    0,    w2,  h2)),
    #         "TM" : img.crop((w2,   0,   2*w2,   h2)),
    #         "TR": img.crop((2*w2,   0,   w,   h2)),
    #         "BL": img.crop((0,    h2,   w2,  h)),
    #         "BM": img.crop((w2,   h2,   2*w2,   h)),
    #         "BR": img.crop((2*w2,   h2,   w,   h)),
    #     }

    #     # offsets for later bbox transformation
    #     # offsets = {
    #     #     "TL": (0, 0),
    #     #     "TR": (w2, 0),
    #     #     "BL": (0, h2),
    #     #     "BR": (w2, h2)
    #     # }
    #     offsets = {
    #         "TL": (0, 0),
    #         "TM": (w2, 0),
    #         "TR": (2*w2, 0),
    #         "BL": (0, h2),
    #         "BM": (w2, h2),
    #         "BR": (2*w2, h2)
    #     }

    #     return tiles, offsets, w, h

    # # ----------------------------------------------------
    # # Convert YOLO output → your annotation format
    # # ----------------------------------------------------
    # def convert_boxes(self, result, x_offset=0, y_offset=0):
    #     ann_list = []

    #     for box in result.boxes:
    #         xyxy = box.xyxy[0].cpu().numpy().tolist()
    #         cls = int(box.cls[0])
    #         score = float(box.conf[0])

    #         xmin, ymin, xmax, ymax = xyxy

    #         ann = {
    #             "box": {
    #                 "xmin": int(xmin + x_offset),
    #                 "ymin": int(ymin + y_offset),
    #                 "xmax": int(xmax + x_offset),
    #                 "ymax": int(ymax + y_offset),
    #             },
    #             "label": result.names[cls],
    #             "score": score,
    #         }
    #         ann_list.append(ann)

    #     return ann_list

    # # ----------------------------------------------------
    # # Main inference
    # # ----------------------------------------------------
    # def run(self, images):


    #     final_results = []

    #     for idx, image in enumerate(images):
            
    #         img_path = image["url"]

    #         # Load image
    #         img = Image.open(img_path).convert("RGB")

    #         # Prepare outputs
    #         full_image_annotations = []
    #         tile_annotations = []

    #         # -----------------------------
    #         # 1) RUN ON FULL IMAGE
    #         # -----------------------------
    #         full_result = self.model(img, device=self.device)[0]
    #         full_image_annotations = self.convert_boxes(full_result, 0, 0)

    #         # -----------------------------
    #         # 2) RUN ON TILES
    #         # -----------------------------
    #         tiles, offsets, W, H = self.split_into_tiles(img)

    #         tile_imgs = list(tiles.values())
    #         tile_keys = list(tiles.keys())

    #         time_results = []
    #         for tile_img in tile_imgs:
    #             tile_results = self.model(tile_img, device=self.device)[0]
    #             time_results.append(tile_results)

    #         for tile_key, tile_res in zip(tile_keys, time_results):
    #             x_off, y_off = offsets[tile_key]
    #             converted = self.convert_boxes(tile_res, x_off, y_off)
    #             tile_annotations.extend(converted)

    #         # -----------------------------
    #         # 3) Combine + Return
    #         # -----------------------------
    #         combined = full_image_annotations + tile_annotations

    #         for det in combined:
    #             det["image_id"] = image["id"]
    #             bbox = det.pop("box")
    #             #width height to xmin ymin
    #             # det["bbox"] = [bbox["xmax"], bbox["ymax"], bbox["xmin"], bbox["ymin"]]
    #             det["bbox"] = [bbox["xmin"], bbox["ymin"],bbox["xmax"] - bbox["xmin"], bbox["ymax"] - bbox["ymin"]]
    #             det["category_name"] = "vehicle"
    #         final_results += combined

    #         if(idx % 10) == 0:
    #             logger.info(f"[YOLOInferencer] Processing image {idx+1}/{len(images)}")
    #             if self.progress_callback:
    #                 self.progress_callback(idx + 1, len(images), f"Processed {idx + 1} of {len(images)} images")

    #     return final_results
