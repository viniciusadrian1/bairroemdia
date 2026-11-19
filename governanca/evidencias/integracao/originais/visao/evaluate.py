"""Run the integrated ONNX adapter on a labelled image sequence.

Produces single-class AP at IoU .50:.95 using 101-point interpolated recall.
This is a transparent educational implementation, not the official COCO API.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import statistics
import time

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]


def load_adapter():
    spec = importlib.util.spec_from_file_location('bairro_vision', ROOT / '02-solucao-integrada/app/backend/providers/vision.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def iou(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - intersection
    return intersection / union if union > 0 else 0.0


def score(predictions, ground_truth, threshold=0.5):
    total_gt = sum(len(v) for v in ground_truth.values())
    matched = {name: set() for name in ground_truth}
    tp, fp = [], []
    for pred in sorted(predictions, key=lambda row: row['confidence'], reverse=True):
        available = [(iou(pred['bbox'], box), index) for index, box in enumerate(ground_truth[pred['image']])
                     if index not in matched[pred['image']]]
        best = max(available, default=(0.0, -1))
        hit = best[0] >= threshold
        if hit: matched[pred['image']].add(best[1])
        tp.append(int(hit))
        fp.append(int(not hit))
    cumulative_tp = np.cumsum(tp)
    cumulative_fp = np.cumsum(fp)
    recall = cumulative_tp / total_gt if total_gt else np.zeros(len(tp))
    precision = cumulative_tp / np.maximum(cumulative_tp + cumulative_fp, 1)
    ap = float(np.mean([max(precision[recall >= r], default=0.0) for r in np.linspace(0, 1, 101)])) if total_gt else None
    return {'tp': sum(tp), 'fp': sum(fp), 'fn': total_gt-sum(tp),
            'precision': sum(tp)/(len(tp)) if tp else 0.0,
            'recall': sum(tp)/total_gt if total_gt else None, 'ap': ap}


def evaluate(images, labels, output, confidence=0.25):
    adapter = load_adapter()
    paths = sorted(p for p in images.iterdir() if p.suffix.lower() in {'.jpg','.jpeg','.png'})
    if not paths: raise ValueError('Nenhuma imagem encontrada.')
    output.mkdir(parents=True, exist_ok=True)
    ground_truth, predictions, runs = {}, [], []
    # Low threshold retains ranked predictions for the PR/AP curve. UI uses .25.
    os.environ['VISION_CONFIDENCE'] = '0.001'
    wall_start = time.perf_counter()
    for path in paths:
        result = adapter.analyze_image(path.read_bytes())
        if result['mode'] != 'model': raise RuntimeError('Detector indisponível: ' + ' '.join(result['warnings']))
        label_file = labels / (path.stem + '.txt')
        if not label_file.exists(): raise FileNotFoundError(label_file)
        boxes = []
        for line in label_file.read_text().splitlines():
            class_id, cx, cy, width, height = map(float, line.split())
            if class_id != 0: raise ValueError('A avaliação atual espera uma única classe: buraco.')
            if not all(0 <= v <= 1 for v in (cx, cy, width, height)): raise ValueError('Rótulo YOLO fora do intervalo.')
            w, h = result['width'], result['height']
            boxes.append([(cx-width/2)*w, (cy-height/2)*h, (cx+width/2)*w, (cy+height/2)*h])
        ground_truth[path.name] = boxes
        predictions.extend(dict(det, image=path.name) for det in result['detections'])
        visible = [d for d in result['detections'] if d['confidence'] >= confidence]
        # Scientific evidence: annotate model outputs and supplied ground truth.
        image = Image.open(path).convert('RGB')
        draw = ImageDraw.Draw(image)
        for box in boxes: draw.rectangle(box, outline='blue', width=2)
        for det in visible:
            draw.rectangle(det['bbox'], outline='red', width=3)
            draw.text(tuple(det['bbox'][:2]), f"buraco {det['confidence']:.2f}", fill='red')
        image.save(output / (path.stem + '.png'))
        runs.append({'image': path.name, 'ground_truth_count': len(boxes),
                     'visible_detections': visible, **result})
    elapsed = time.perf_counter()-wall_start
    selected = [p for p in predictions if p['confidence'] >= confidence]
    operating = score(selected, ground_truth)
    by_iou = {f'{t:.2f}': score(predictions, ground_truth, float(t))['ap'] for t in np.arange(.5,.96,.05)}
    latency = [r['latency_ms'] for r in runs]
    warm = latency[1:] or latency
    metrics = {'sample_images': len(paths), 'ground_truth_boxes': sum(map(len,ground_truth.values())),
               'operating_confidence': confidence, 'operating_iou': .5, 'operating_metrics': operating,
               'AP50': by_iou['0.50'], 'mAP50_95': statistics.mean(by_iou.values()), 'AP_by_IoU': by_iou,
               'AP_method': 'single-class, 101 recall points, IoU .50:.95, predictions >=.001, NMS .45; not official COCO evaluator',
               'mean_latency_ms_including_first': statistics.mean(latency),
               'mean_latency_ms_after_first': statistics.mean(warm), 'first_latency_ms': latency[0],
               'FPS_adapter_after_first': 1000/statistics.mean(warm),
               'FPS_pipeline_including_loading_labels_and_saving_annotations': len(paths)/elapsed,
               'hardware': {'platform': platform.platform(), 'processor': platform.processor(), 'python': platform.python_version(),
                            'logical_cpu_count': os.cpu_count()},
               'input_resolutions': sorted(set(f"{r['width']}x{r['height']}" for r in runs)),
               'network_input': '640x640 letterbox, RGB float32 /255',
               'limitation': 'External model and published test subset. Independence from model training not audited; this is local smoke evaluation, not proof of generalization. No Brazilian field validation.'}
    (output/'metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'predictions.json').write_text(json.dumps(runs,ensure_ascii=False,indent=2),encoding='utf-8')
    return metrics


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--images', type=Path, required=True)
    parser.add_argument('--labels', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.environ['VISION_MODEL_PATH'] = str(args.model.resolve())
    print(json.dumps(evaluate(args.images,args.labels,args.output),ensure_ascii=True,indent=2))
