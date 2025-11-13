# Copyright (c) Facebook, Inc. and its affiliates.

import json
import torch
import cv2
import shutil
import time
from PIL import Image
from configs import detectron_config

from detectron2.config import get_cfg
from detectron2.engine.defaults import DefaultPredictor
from file_manager import make_detectron_directory, detectron_table_path, detectron_figure_path

from common_module import write_log
from configs import etc_config

# class = ['table', 'figure']
table_threshold = float(detectron_config['table_threshold'])
figure_threshold = float(detectron_config['figure_threshold'])
debug_mode = detectron_config['debug_mode'] == 'True'

def setup_cfg():
    '''Detectron2 설정'''
    cfg = get_cfg()
    cfg.merge_from_file(detectron_config['config_yaml'])

    threshold = min(table_threshold, figure_threshold)

    cfg.MODEL.ROI_HEADS.NUM_CLASSES = 2  # 클래스 개수 설정 (table, figure)
    cfg.MODEL.WEIGHTS = detectron_config['weights']
    cfg.MODEL.RETINANET.SCORE_THRESH_TEST = threshold
    cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = threshold
    cfg.MODEL.PANOPTIC_FPN.COMBINE.INSTANCES_CONFIDENCE_THRESH = threshold
    cfg.MODEL.DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    cfg.freeze()
    return cfg

predictor = DefaultPredictor(setup_cfg())


def filter_containing_boxes(boxes, scores, containment_threshold=0.7):
    '''겹치는 박스 중 score가 낮은 것 제거'''
    if len(boxes) == 0:
        return boxes, scores

    keep = [True] * len(boxes)

    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            iou = calculate_iou(boxes[i], boxes[j])

            if iou > 0:
                area_i = calculate_area(boxes[i])
                area_j = calculate_area(boxes[j])
                
                # 겹치는 비율 계산
                overlap_i = iou / area_i
                overlap_j = iou / area_j

                if overlap_i > containment_threshold or overlap_j > containment_threshold:
                    if scores[i] >= scores[j]:
                        keep[j] = False
                    else:
                        keep[i] = False

    filtered_boxes = [box for box, k in zip(boxes, keep) if k]
    filtered_scores = [score for score, k in zip(scores, keep) if k]
    return filtered_boxes, filtered_scores


def calculate_iou(box1, box2):
    '''두 박스의 교차 영역 넓이 계산'''
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    
    if x2 <= x1 or y2 <= y1:
        return 0
    return (x2 - x1) * (y2 - y1)


def calculate_area(box):
    '''박스의 넓이 계산'''
    return (box[2] - box[0]) * (box[3] - box[1])


def process_image(image, predictor, image_path, oid, fig_savepath=''):
    '''한 페이지 이미지 처리'''
    # 추론 시작 시간 기록
    inference_start_time = time.time()

    # 객체 검출
    predictions = predictor(image)

    # 추론 종료 시간 기록
    inference_time = time.time() - inference_start_time

    if 'instances' not in predictions:
        write_log(f'[detectron] 객체 검출 결과 없음: {image_path}', etc_config['LOG_LEVEL_WARNING'], oid)
        return [], 0, [], inference_time, 0.0

    instances = predictions['instances']

    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(rgb_image)  # PIL 이미지

    # table
    tables = []
    indices = torch.where(instances.pred_classes == 0)[0]
    indices = indices[instances.scores[indices] >= table_threshold]
    boxes = instances.pred_boxes[indices].tensor.tolist()
    scores = instances.scores[indices].tolist()
    boxes, scores = filter_containing_boxes(boxes, scores)   # 큰 박스 필터링 (table인 경우에만)

    if debug_mode:
        for i, box in enumerate(boxes):
            table_img = image.crop(box)
            table_image_path = detectron_table_path(image_path, i)
            table_img.save(table_image_path)

    for box in boxes:
        tables.append(list(map(lambda x: round(x, 2), box)))

    table_count = len(boxes)

    # 그림 이미지 저장 시작 시간 기록
    figure_save_start_time = time.time()
    figure_save_time = 0.0

    # figure
    indices = torch.where(instances.pred_classes == 1)[0]
    indices = indices[instances.scores[indices] >= figure_threshold]
    boxes = instances.pred_boxes[indices].tensor.tolist()
    scores = instances.scores[indices].tolist()

    page_num = image_path.split('_')[1].split('.')[0]

    figure_images = list()
    for i, box in enumerate(boxes):
        figure_img = image.crop(box)
        figure_image_path = f'{fig_savepath}_{page_num}_{i}.png'
        figure_img.save(figure_image_path)
        figure_images.append(figure_image_path)
        if debug_mode:
            shutil.copy(figure_image_path, detectron_figure_path(image_path, i))

    figure_count = len(figure_images)
    figure_save_time = time.time() - figure_save_start_time

    # 전체 처리 시간 계산 및 기록
    log_string = (f'[detectron] {int(page_num):>2}페이지 │ 표 {table_count}개 / 그림 {figure_count}개 탐지 │ 추론 시간: {inference_time:.4f}초')
    if figure_count:
        log_string += f' │ 그림 이미지 저장: {figure_save_time:.4f}초'
    write_log(log_string, etc_config['LOG_LEVEL_INFO'], oid)

    return tables, table_count, figure_images, inference_time, figure_save_time

def detection_request(image_path_list, json_output_path, timeStr, fig_savepath, oid):
    make_detectron_directory(timeStr, debug_mode)
    detectron_results = dict()
    total_infer_time = 0.0
    total_tables = 0
    total_save_time = 0.0
    all_figure_images = []

    for image_path in image_path_list:
        image = cv2.imread(image_path)
        if image is None:
            write_log(f'[detectron] 이미지를 읽을 수 없음: {image_path}', etc_config['LOG_LEVEL_ERROR'], oid)
            return None, None, 'E300'
        
        if len(image.shape) == 2:  # 흑백 이미지
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        elif image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)

        try:
            tables, table_count, figure_images, infer_time, save_time = process_image(image, predictor, image_path, oid, fig_savepath)
        except:
            write_log(f'[detectron] 추론 중 오류: {image_path}', etc_config['LOG_LEVEL_ERROR'], oid)
            return None, None, 'E300'
        if tables:
            detectron_results[image_path] = tables
            total_tables += table_count
        total_infer_time += infer_time
        total_save_time += save_time
        all_figure_images.extend(figure_images)

    # 전체 결과 요약 로그
    write_log(
        f"[detectron] 전체 결과 │ 총 표 {total_tables}개 / 그림 {len(all_figure_images)}개 │ "
        f"총 추론 시간: {total_infer_time:.4f}초 │ 총 이미지 저장 시간: {total_save_time:.4f}초",
        etc_config['LOG_LEVEL_INFO'], oid
    )

    try:
        with open(json_output_path, 'w', encoding='utf-8') as f:
            json.dump(detectron_results, f, ensure_ascii=False, indent=2)
    except Exception as e:
        write_log(f'[detectron] {json_output_path}:' + str(e), etc_config['LOG_LEVEL_ERROR'], oid)
        return None, None, 'E301'

    return detectron_results, all_figure_images, None