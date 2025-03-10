import math
import numpy as np
import cv2


def dist_2_pts(x1, y1, x2, y2):
    """
    Calculate the distance between two points
    :param x1:
    :param y1:
    :param x2:
    :param y2:
    :return: distance (np.float)
    """
    return np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def mid_pts(tup1, tup2):
    """
    Get the middle point of two points
    :param tup1: point 1
    :param tup2: point 2
    :return: int x, int y
    """
    return int((tup1[0] + tup2[0]) / 2), int((tup1[1] + tup2[1]) / 2)


def shorten_line(tup1, tup2, percent):
    """
    Shorten a line by a certain percent
    :param tup1:
    :param tup2:
    :param percent:
    :return: (int, int), (int, int)
    """
    x1, y1, x2, y2 = tup1[0], tup1[1], tup2[0], tup2[1]
    x1 = x1 + int((x2 - x1) * percent)
    x2 = x2 - int((x2 - x1) * percent)
    y1 = y1 + int((y2 - y1) * percent)
    y2 = y2 - int((y2 - y1) * percent)
    return (x1, y1), (x2, y2)


def avg_circles(circles: np.array,
                b: int):
    """
    Average the circles in the image
    :param circles: np.array
    :param b: Search parameter
    :return: avg_x, avg_y, avg_radius
    """
    avg_x = 0
    avg_y = 0
    avg_r = 0
    for i in range(b):
        avg_x = avg_x + circles[0][i][0]
        avg_y = avg_y + circles[0][i][1]
        avg_r = avg_r + circles[0][i][2]
    avg_x = int(avg_x / b)
    avg_y = int(avg_y / b)
    avg_r = int(avg_r / b)
    return avg_x, avg_y, avg_r


def point_pos(x0, y0, d, theta):
    """
    Calculate the position of a point based on the distance and angle
    :param x0:
    :param y0:
    :param d:
    :param theta: int, int
    :return:
    """
    theta_rad = math.pi / 2 - math.radians(theta)
    return int(x0 + d * math.cos(theta_rad)), int(y0 + d * math.sin(theta_rad))


def angle_from_pts(x1, y1, x2, y2):
    """
    Calculate the angle between two points
    :param x1:
    :param y1:
    :param x2:
    :param y2:
    :return: angle (float)
    """
    return math.degrees(math.atan2(y2 - y1, x2 - x1))


def get_closest_pt_to_center(x0, y0,
                             x1, y1,
                             x2, y2):
    """
    Get the closest point to the center
    :param x0:
    :param y0:
    :param x1:
    :param y1:
    :param x2:
    :param y2:
    :return: x, y
    """
    d1 = dist_2_pts(x0, y0, x1, y1)
    d2 = dist_2_pts(x0, y0, x2, y2)
    if d1 < d2:
        return x1, y1
    else:
        return x2, y2


def get_further_pt_to_center(x0, y0,
                             x1, y1,
                             x2, y2):
    """
    Get the further point to the center
    :param x0:
    :param y0:
    :param x1:
    :param y1:
    :param x2:
    :param y2:
    :return:
    """
    d1 = dist_2_pts(x0, y0, x1, y1)
    d2 = dist_2_pts(x0, y0, x2, y2)
    if d1 > d2:
        return x1, y1
    else:
        return x2, y2


def get_min_max_from_step(step,
                          cur_val,
                          min_val,
                          max_val):
    """
    Get the min and max values from the step
    :param step:
    :param cur_val:
    :param min_val:
    :param max_val:
    :return:
    """
    step_angle = 360 / step
    angle_to_max = (max_val - cur_val) * step_angle
    angle_to_min = (cur_val - min_val) * step_angle
    return angle_to_min, angle_to_max, step_angle


def define_min_max_values_from_anel(step,
                                    min_val,
                                    max_val):
    """
    Define the min and max values from the angle
    :param step:
    :param min_val:
    :param max_val:
    :return:
    """
    step_angle = 360 / step
    angle_to_max = (max_val - min_val) * step_angle
    return angle_to_max, step_angle


def angle_calculate(min_angle: float,
                    max_angle: float,
                    angle_deviation: float):
    """
    Calculate the angle to be used in the angle_deviation
    :param min_angle:
    :param max_angle:
    :param angle_deviation:
    :return:
    """
    if angle_deviation > 0:
        """
        This means that the needle in calibration image is "after" the zero angle
        """
        min_angle = min_angle - angle_deviation
        max_angle = max_angle - angle_deviation
    else:
        """
        This means that the needle in calibration image is "before" the zero angle
        """
        min_angle = min_angle - angle_deviation
        max_angle = max_angle + angle_deviation
    return min_angle, max_angle


def order_points(pts):
    """
    Order the points in clockwise order
    :param pts:
    :return:
    """
    rect = np.zeros((4, 2), dtype="float32")
    pts = np.array(pts)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect.tolist()


def get_points(pts):
    """
    Get the points from the list of points
    :param pts:
    :return:
    """
    rect = np.zeros((4, 2), dtype="float32")
    pts = np.array(pts)
    for i in range(4):
        rect[i] = pts[i]
    return rect


def get_perspective_points(w,
                           h,
                           scales):
    """
    Get the points that are used for perspective transform from scale values
    :param scales:
    :return:
    """
    top, bottom, left, right = scales
    dest = [[0 + top, 0 + left],
            [w + top, + right],
            [w + bottom, h + right],
            [0 + bottom, h + left]]
    return dest
