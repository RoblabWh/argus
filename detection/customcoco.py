import mmengine
import numpy as np
import torch
from mmdet.registry import DATASETS
from pathlib import Path

from mmdet.datasets.api_wrappers import COCO
@DATASETS.register_module()
class CustomCOCO(COCO):

    CLASSES = ('fire', 'vehicle', 'human')
    PALETTE = [(220, 20, 60), (119, 11, 32), (0, 0, 142)]

    def __init__(self, ann_file=None, score_thr=0.3, keep_coco_format=True):
        super().__init__(annotation_file=ann_file)
        self.score_thr = score_thr
        self.keep_coco_format = keep_coco_format

    def results2json(self, results, outfile_prefix):
        """Dump the detection results to a COCO style json file.

        There are 3 types of results: proposals, bbox predictions, mask
        predictions, and they have different data types. This method will
        automatically recognize the type, and dump them to json files.

        Args:
            results (list[dict]): Testing results of the dataset.
            outfile_prefix (str): The filename prefix of the json files. If the
                prefix is "somepath/xxx", the json files will be named
                "somepath/xxx.bbox.json", "somepath/xxx.segm.json",
                "somepath/xxx.proposal.json".

        Returns:
            dict[str: str]: Possible keys are "bbox", "segm", "proposal", and \
                values are corresponding filenames.
        """
        result_files = dict()
        if isinstance(results, dict):
            json_results = self._det2json(results)
            result_files['bbox'] = f'{outfile_prefix}.bbox.json'
            mmengine.dump(json_results, result_files['bbox'])
        else:
            raise TypeError('invalid type of results')
        return result_files

    def xyxy2xywh(self, bbox):
        """Convert ``xyxy`` style bounding boxes to ``xywh`` style for COCO
        evaluation.

        Args:
            bbox (numpy.ndarray): The bounding boxes, shape (4, ), in
                ``xyxy`` order.

        Returns:
            list[float]: The converted bounding boxes, in ``xywh`` order.
        """

        _bbox = bbox.tolist()
        return [
            _bbox[0],
            _bbox[1],
            _bbox[2] - _bbox[0],
            _bbox[3] - _bbox[1],
        ]

    def __len__(self):
        return len(self.dataset['images'])

    def _det2json(self, results):

        coco_correction = 0
        if self.keep_coco_format:
            coco_correction = 1

        json_results = []
        id = 1
        for image in self.dataset['images']:
            img_id = image['id']
            result_pred = results['predictions'][img_id]
            #assert (image['file_name'] == Path(result_pred.img_path).name), "Something wrong with the image path"
            pred_instances = result_pred.pred_instances
            if isinstance(result_pred.pred_instances.scores, torch.Tensor):
                scores = np.array(result_pred.pred_instances.scores.cpu())
            else:
                scores = np.array(result_pred.pred_instances.scores)
            if isinstance(result_pred.pred_instances.bboxes, torch.Tensor):
                bboxes = np.array(result_pred.pred_instances.bboxes.cpu())
            else:
                bboxes = np.array(result_pred.pred_instances.bboxes)
            if isinstance(result_pred.pred_instances.labels, torch.Tensor):
                labels = np.array(result_pred.pred_instances.labels.cpu())
            else:
                labels = np.array(result_pred.pred_instances.labels)
            for instance in range(len(pred_instances)):
                if scores[instance] > self.score_thr:
                    data = dict()
                    data['id'] = id
                    id += 1
                    data['image_id'] = img_id
                    data['bbox'] = self.xyxy2xywh(bboxes[instance])
                    data['score'] = float(scores[instance])
                    data['category_id'] = labels[instance] + coco_correction # add 1 to stay in COCO format
                    data['segmentation'] = []
                    json_results.append(data)
        return json_results

    def get_ann_info(self, idx):
        return self.data_infos[idx]['ann']