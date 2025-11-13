"""  
Copyright (c) 2019-present NAVER Corp.
MIT License
"""

# -*- coding: utf-8 -*-
import torch
import torch.backends.cudnn as cudnn
from torch.autograd import Variable
import cv2
import numpy as np
from craft.craft_utils import adjustResultCoordinates, getDetBoxes
from craft.imgproc import resize_aspect_ratio, normalizeMeanVariance
from craft.craft import CRAFT
from collections import OrderedDict


def copyStateDict(state_dict):
    if list(state_dict.keys())[0].startswith("module"):
        start_idx = 1
    else:
        start_idx = 0
    new_state_dict = OrderedDict()
    for k, v in state_dict.items():
        name = ".".join(k.split(".")[start_idx:])
        new_state_dict[name] = v
    return new_state_dict


def str2bool(v):
    return v.lower() in ("yes", "y", "true", "t", "1")


# global g_opt

def test_net(net, image, text_threshold, link_threshold, low_text, cuda, canvas_size, mag_ratio, refine_net=None):
    # t0 = time.time()

    # resize
    img_resized, target_ratio = resize_aspect_ratio(image, square_size=canvas_size,
                                                                  interpolation=cv2.INTER_LINEAR, mag_ratio=mag_ratio)

    ratio_h = ratio_w = 1 / target_ratio

    # preprocessing
    x = normalizeMeanVariance(img_resized)
    x = torch.from_numpy(x).permute(2, 0, 1)  # [h, w, c] to [c, h, w]
    x = Variable(x.unsqueeze(0))  # [c, h, w] to [b, c, h, w]

    if cuda:
        x = x.cuda()

    # forward pass
    with torch.no_grad():
        y, feature = net(x)

    # make score and link map
    score_text = y[0, :, :, 0].cpu().data.numpy()
    score_link = y[0, :, :, 1].cpu().data.numpy()

    # refine link
    if refine_net is not None:
        with torch.no_grad():
            y_refiner = refine_net(y, feature)

        score_link = y_refiner[0, :, :, 0].cpu().data.numpy()

    # t0 = time.time() - t0
    # t1 = time.time()

    # Post-processing
    boxes = getDetBoxes(score_text, score_link, text_threshold, link_threshold, low_text)

    # coordinate adjustment
    boxes = adjustResultCoordinates(boxes, ratio_w, ratio_h)

    # render results (optional)
    render_img = score_text.copy()
    render_img = np.hstack((render_img, score_link))

    # if args.show_time : print("\ninfer/postproc time : {:.3f}/{:.3f}".format(t0, t1))

    return boxes


def get_detector(trained_model, cuda, refine, refiner_model):
    # load net
    net = CRAFT()  # initialize

    # print('Loading weights from checkpoint (' + trained_model + ')')
    if cuda:
        net.load_state_dict(copyStateDict(torch.load(trained_model)))
    else:
        # == Mac 은 CUDA 지원 안함으로 위의 로직 패스하고 대신 아래 로직 사용! ==
        net.load_state_dict(copyStateDict(torch.load(trained_model, map_location='cpu')))

    if cuda:
        net = net.cuda()
        net = torch.nn.DataParallel(net)
        cudnn.benchmark = False

    net.eval()

    # LinkRefiner
    refine_net = None

    if refine:
        from craft.refinenet import RefineNet
        refine_net = RefineNet()
        print('Loading weights of refiner from checkpoint (' + refiner_model + ')')

        if cuda:
            refine_net.load_state_dict(copyStateDict(torch.load(refiner_model)))
            refine_net = refine_net.cuda()
            refine_net = torch.nn.DataParallel(refine_net)
        else:
            # == Mac 은 CUDA 지원 안함으로 위의 로직 패스하고 대신 아래 로직 사용! ==
            refine_net.load_state_dict(copyStateDict(torch.load(refiner_model, map_location='cpu')))

        refine_net.eval()
        poly = True

    # t = time.time()
    return net, refine_net