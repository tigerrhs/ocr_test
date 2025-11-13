import cv2
import numpy as np
from PIL import Image

from file_manager import source_image
from common_module import write_log, etc_config


def pix_to_image(pix):
    '''PyMuPDF2로 읽은 페이지 이미지 pix를 cv2 이미지로 변환'''
    image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 3:
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    elif pix.n == 4:
        image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGRA)
    return image


def dec_to_image(decFile):
    img_array = np.frombuffer(decFile, dtype=np.uint8)
    image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    return image


def convert_tiff_to_png(tiff_path, time_str, file_name, oid):
    tiff_image = Image.open(tiff_path)

    paths = []
    for i in range(tiff_image.n_frames):
        tiff_image.seek(i)
        frame = tiff_image.copy()
        png_path = source_image(time_str, i, 'png', file_name)
        rgb_image = frame.convert('RGB')
        cv_image = cv2.cvtColor(np.array(rgb_image), cv2.COLOR_RGB2BGR)
        angle = correct_skew(png_path, cv_image)
        if angle:
            write_log(f'[TIFF → PNG] {png_path}, {angle}˚ rotated', etc_config['LOG_LEVEL_INFO'], oid)
        else:
            cv2.imwrite(png_path, cv_image)
            write_log(f'[TIFF → PNG] {png_path}', etc_config['LOG_LEVEL_INFO'], oid)
        paths.append(png_path)
    return paths

def convert_gif_to_png(gif_path, png_path, oid):
    image = Image.open(gif_path).convert("RGB")
    np_image = np.array(image)
    cv_image = cv2.cvtColor(np.array(np_image), cv2.COLOR_RGB2BGR)
    angle = correct_skew(png_path, cv_image)
    if angle:
        write_log(f'[GIF → PNG] {png_path}, {angle}˚ rotated', etc_config['LOG_LEVEL_INFO'], oid)
    else:
        cv2.imwrite(png_path, cv_image)
        write_log(f'[GIF → PNG] {png_path}', etc_config['LOG_LEVEL_INFO'], oid)


def find_angle(angles):
    if not angles:
        return 0
    
    # 빈 너비 설정 (근사치의 범위)
    bin_width = 0.001
    most_angle = find_most_frequent_approx_value(angles, bin_width)
    # 최대 빈도 각도 값만 필터링
    nangles = []
    for angle in angles:
        if angle > most_angle - bin_width and angle < most_angle + bin_width:
            nangles.append(angle)
    # 각도 평균을 구함
    average_angle = np.mean(nangles)

    if abs(average_angle) > 5 or abs(average_angle) < 1e-4:
        average_angle = 0

    return average_angle


def find_most_frequent_approx_value(values, bin_width, show_hist=False):
    # 히스토그램 계산
    min_value = min(values)
    max_value = max(values)
    if min_value == max_value:
        return min_value
    
    bins = np.arange(min_value, max_value + bin_width, bin_width)
    hist, bin_edges = np.histogram(values, bins=bins)

    # def show_angles_hist():     # 히스토그램 확인
    #     plt.hist(values, bins=bins, edgecolor='black')
    #     plt.xlabel('Value')
    #     plt.ylabel('Frequency')
    #     plt.title('most frequent angle')
    #     plt.show()

    # if show_hist:
    #     show_angles_hist()

    # 가장 빈도 높은 구간 찾기
    max_bin_index = np.argmax(hist)

    # 구간의 중앙값을 가장 빈도 높은 값으로 선택
    most_frequent_value = (bin_edges[max_bin_index] + bin_edges[max_bin_index + 1]) / 2

    return most_frequent_value


# def draw_hough(orig_image, lines):
#     image = orig_image.copy()
#     if lines is not None:
#         for line in lines:
#             rho, theta = line[0]

#             a = np.cos(theta)
#             b = np.sin(theta)
#             x0 = a * rho
#             y0 = b * rho

#             x1 = int(x0 + 1000 * (-b))
#             y1 = int(y0 + 1000 * (a))
#             x2 = int(x0 - 1000 * (-b))
#             y2 = int(y0 - 1000 * (a))

#             cv2.line(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
#     # cv2.imwrite(filename, image)
#     image = cv2.resize(image, (int(image.shape[1] * 0.5), int(image.shape[0] * 0.5)))
#     cv2.imshow('houghline', image)
#     cv2.waitKey(0)


# def dynamic_houghlines_binary(edges, low=50, high=2000):
#     while low <= high:
#         mid = (low + high) // 2
#         lines = cv2.HoughLines(edges, 1, np.pi / 180, mid)
        
#         if lines is None or len(lines) < 20:
#             high = mid - 1
#         elif len(lines) > 500:
#             low = mid + 1
#         else:
#             break

#     return lines


def dynamic_houghlines_binary(edges, low=50, high=2000):
    mid = 200
    lines = None

    while low <= high:
        lines = cv2.HoughLines(edges, 1, np.pi / 180, mid)
        if lines is not None:
            if 10 <= len(lines) <= 500:
                return lines
            
            if len(lines) > 500:
                low = mid + 1
            
            elif len(lines) < 10:
                high = mid - 1

        else:
            high = mid - 1

        mid = (low + high) // 2


    return lines


def correct_skew(image_path, image):
    # 2. 이미지를 회색조로 변환
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 3. 엣지 검출
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    # 4. 선 검출
    lines = dynamic_houghlines_binary(edges)

    if lines is None:
        # 'no hough lines'
        return 0
    
    # 검출된 선의 각도를 추출
    angles = []
    # maxCount = 5
    for line in lines:
        rho, theta = line[0]
        angle = (theta * 180 / np.pi) - 90  # 수평선 기준으로 각도 계산
        angles.append(angle)
        # if len(angles) > maxCount:
        #     break

    # 5. 평균 각도를 계산하여 이미지 회전
    average_angle = find_angle(angles)

    if average_angle:
        # 회전
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        rot_mat = cv2.getRotationMatrix2D(center, average_angle, 1.0)

        # 회전 후 이미지의 크기 계산
        abs_cos = abs(rot_mat[0, 0])
        abs_sin = abs(rot_mat[0, 1])
        w = int(h * abs_sin + w * abs_cos)
        h = int(h * abs_cos + w * abs_sin)
        rot_mat[0, 2] += (w / 2) - center[0]
        rot_mat[1, 2] += (h / 2) - center[1]

        # 회전된 이미지 계산
        rotated = cv2.warpAffine(image, rot_mat, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        
    else:
        # 'no angles'
        return 0

    # 6. 이미지 저장
    cv2.imwrite(image_path, rotated)
    return average_angle