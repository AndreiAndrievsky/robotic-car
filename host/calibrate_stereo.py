import cv2
import numpy as np
import glob
import os
from cv2 import aruco


SQUARES_X   = 5
SQUARES_Y   = 7

# initially the sizes were 35 and 20 mms. but the printer
# stretched the squares when I printed the board on paper
SQUARE_SIZE = 0.0372
MARKER_SIZE = 0.0212

DICTIONARY  = aruco.DICT_6X6_50

LEFT_IMAGES  = '../calibration_images/left/*.png'
RIGHT_IMAGES = '../calibration_images/right/*.png'


dictionary = aruco.getPredefinedDictionary(DICTIONARY)
board = aruco.CharucoBoard(
    (SQUARES_X, SQUARES_Y),
    SQUARE_SIZE,
    MARKER_SIZE,
    dictionary
)
detector = aruco.CharucoDetector(board)


def detect_corners(image_paths, label):
    # detect charuco corners, return per-file results keyed by filename
    files  = sorted(glob.glob(image_paths))
    result = {}  # filename : (obj_pts, img_pts, image_size)

    print(f"\n{label} camera: processing {len(files)} images")

    for fname in files:
        img  = cv2.imread(fname)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        charuco_corners, charuco_ids, _, _ = detector.detectBoard(gray)

        n = len(charuco_ids) if charuco_ids is not None else 0
        print(f"  {os.path.basename(fname)}: {n} corners", end=" ")

        if charuco_ids is not None and len(charuco_ids) > 5:
            obj_pts, img_pts = board.matchImagePoints(charuco_corners, charuco_ids)
            result[os.path.basename(fname)] = (obj_pts, img_pts, gray.shape[::-1], charuco_ids.flatten())
            print("used")
        else:
            print("skipped")

    print(f"{label}: {len(result)}/{len(files)} images accepted")
    return result


results_l = detect_corners(LEFT_IMAGES,  "left")
results_r = detect_corners(RIGHT_IMAGES, "right")

print("\nfinding synchronized pairs with matching corner IDs")
stereo_obj = []
stereo_l   = []
stereo_r   = []
image_size = None
valid_count = 0

common = sorted(set(results_l.keys()) & set(results_r.keys()))

for fname in common:
    obj_l, img_l, img_size, ids_l = results_l[fname]
    obj_r, img_r, _, ids_r = results_r[fname]

    # find corner IDs detected in _both_ images
    common_ids = np.intersect1d(ids_l, ids_r)

    if len(common_ids) < 6:
        print(f"{fname}: only {len(common_ids)} common corners")
        continue

    # filter to only common corners
    mask_l = np.isin(ids_l, common_ids)
    mask_r = np.isin(ids_r, common_ids)

    img_l_filtered = img_l[mask_l]
    img_r_filtered = img_r[mask_r]
    obj_filtered   = obj_l[mask_l]  # obj points are same for both

    stereo_obj.append(obj_filtered)
    stereo_l.append(img_l_filtered)
    stereo_r.append(img_r_filtered)
    image_size = img_size
    valid_count += 1
    print(f"{fname}: {len(common_ids)} common corners")

print(f"\n{valid_count} pairs usable for stereo calibration")

if valid_count < 5:
    print("Error: need at least 5 valid pairs!")
    exit(1)

print("\ncalibrating left camera")
obj_pts_l = [results_l[f][0] for f in results_l]
img_pts_l = [results_l[f][1] for f in results_l]
img_size_l = list(results_l.values())[0][2]
ret_l, K_l, dist_l, _, _ = cv2.calibrateCamera(obj_pts_l, img_pts_l, img_size_l, None, None)
print(f"left reprojection error: {ret_l:.4f}px")

print("\ncalibrating right camera")
obj_pts_r = [results_r[f][0] for f in results_r]
img_pts_r = [results_r[f][1] for f in results_r]
img_size_r = list(results_r.values())[0][2]
ret_r, K_r, dist_r, _, _ = cv2.calibrateCamera(obj_pts_r, img_pts_r, img_size_r, None, None)
print(f"right reprojection error: {ret_r:.4f}px")

print("\nstereo calibration")
flags = cv2.CALIB_FIX_INTRINSIC

ret_s, K_l, dist_l, K_r, dist_r, R, T, E, F = cv2.stereoCalibrate(
    stereo_obj, stereo_l, stereo_r,
    K_l, dist_l,
    K_r, dist_r,
    image_size,
    flags=flags
)
print(f"stereo reprojection error: {ret_s:.4f}px")
print(f"\nbaseline: {np.linalg.norm(T)*100:.1f}cm")
print(f"\nT (translation):\n{T}")
print(f"\nR (rotation):\n{R}")

print("\ncomputing rectification maps")
R_l, R_r, P_l, P_r, Q, roi_l, roi_r = cv2.stereoRectify(
    K_l, dist_l, K_r, dist_r,
    image_size, R, T,
    alpha=0
)

map_l1, map_l2 = cv2.initUndistortRectifyMap(K_l, dist_l, R_l, P_l, image_size, cv2.CV_32FC1)
map_r1, map_r2 = cv2.initUndistortRectifyMap(K_r, dist_r, R_r, P_r, image_size, cv2.CV_32FC1)

# save numpy arrays
np.save('calibration/calib_K_l.npy', K_l)
np.save('calibration/calib_P_l.npy', P_l)   # rectified projection matrix, used for PnP on rectified frames
np.save('calibration/calib_K_r.npy', K_r)
np.save('calibration/calib_dist_l.npy', dist_l)
np.save('calibration/calib_dist_r.npy', dist_r)
np.save('calibration/calib_R.npy', R)
np.save('calibration/calib_T.npy', T)
np.save('calibration/calib_Q.npy', Q)
np.save('calibration/calib_map_l1.npy', map_l1)
np.save('calibration/calib_map_l2.npy', map_l2)
np.save('calibration/calib_map_r1.npy', map_r1)
np.save('calibration/calib_map_r2.npy', map_r2)
print("\ncalibration files saved")

# visual check -- epipolar lines
print("\nshowing rectification result")
img_l = cv2.imread(sorted(glob.glob(LEFT_IMAGES))[0])
img_r = cv2.imread(sorted(glob.glob(RIGHT_IMAGES))[0])

rect_l = cv2.remap(img_l, map_l1, map_l2, cv2.INTER_LINEAR)
rect_r = cv2.remap(img_r, map_r1, map_r2, cv2.INTER_LINEAR)

combined = np.hstack([rect_l, rect_r])
for y in range(0, combined.shape[0], 30):
    cv2.line(combined, (0, y), (combined.shape[1], y), (0, 255, 0), 1)

cv2.imshow('rectified epipolar lines should align. press any key to close', combined)
cv2.waitKey(0)
cv2.destroyAllWindows()
