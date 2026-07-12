import os
import sys
import math
import base64
import cv2
import torch
import requests
import numpy as np

from segment_anything import sam_model_registry, SamPredictor

#==============================================================
# CONSTANTS
#==============================================================

ZOOM      = 20
IMG_SIZE  = 1024
TILE_SIZE = 256

MODEL_TYPE   = "vit_b"
WEIGHTS_PATH = "./checkpoints/sam1_vit_b_csv2_best.pth"
DEVICE       = "cuda" if torch.cuda.is_available() else "cpu"

#==============================================================
# MODEL
#==============================================================

_predictor = None

def get_predictor():
    global _predictor
    if _predictor is None:
        print("\nLoading SAM ViT-B model...")
        sam = sam_model_registry[MODEL_TYPE](checkpoint=None)
        state_dict = torch.load(WEIGHTS_PATH, map_location=DEVICE)
        sam.load_state_dict(state_dict)
        sam.to(device=DEVICE)
        _predictor = SamPredictor(sam)
        print("Model ready ✅")
    return _predictor

#==============================================================
# MASK REFINEMENT — your existing function, unchanged
#==============================================================

def refine_mask(mask):
    mask = mask.astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(mask, kernel, iterations=1)
    contours, _ = cv2.findContours(
        dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if len(contours) == 0:
        return mask.astype(bool)
    contour = max(contours, key=cv2.contourArea)
    arc_len = cv2.arcLength(contour, True)
    area    = cv2.contourArea(contour)
    epsilon = 0.01 * arc_len if area < 5000 else 0.02 * arc_len
    approx  = cv2.approxPolyDP(contour, epsilon, True)
    clean_mask = np.zeros_like(mask)
    cv2.drawContours(clean_mask, [approx], -1, 1, thickness=-1)
    final_mask = cv2.erode(clean_mask, kernel, iterations=1)
    return final_mask.astype(bool)

#==============================================================
# TILE DOWNLOAD — unchanged
#==============================================================

def latlon_to_tile(lat, lon, zoom):
    lat_rad = math.radians(lat)
    n       = 2.0 ** zoom
    xtile   = int((lon + 180.0) / 360.0 * n)
    ytile   = int(
        (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi)
        / 2.0 * n
    )
    return xtile, ytile


def download_satellite_image(lat, lon):
    print(f"\nDownloading tiles for ({lat:.6f}, {lon:.6f})...")
    tiles_needed = IMG_SIZE // TILE_SIZE
    xtile, ytile = latlon_to_tile(lat, lon, ZOOM)
    image        = np.zeros((IMG_SIZE, IMG_SIZE, 3), dtype=np.uint8)
    start_x      = xtile - tiles_needed // 2
    start_y      = ytile - tiles_needed // 2

    for dx in range(tiles_needed):
        for dy in range(tiles_needed):
            url = (f"https://mt1.google.com/vt/lyrs=s"
                   f"&x={start_x+dx}&y={start_y+dy}&z={ZOOM}")
            r   = requests.get(url, timeout=10)
            if r.status_code != 200:
                raise RuntimeError(f"Tile download failed: {url}")
            tile = cv2.imdecode(
                np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR
            )
            image[
                dy * TILE_SIZE:(dy + 1) * TILE_SIZE,
                dx * TILE_SIZE:(dx + 1) * TILE_SIZE
            ] = tile

    print("Satellite tiles ready ✅")
    return image

#==============================================================
# CENTROID — unchanged
#==============================================================

def compute_centroid(mask):
    mask = mask.astype(np.uint8)
    M    = cv2.moments(mask)
    if M["m00"] == 0:
        return None, None
    cx = int(M["m10"] / M["m00"])
    cy = int(M["m01"] / M["m00"])
    return cx, cy

#==============================================================
# AREA — unchanged
#==============================================================

def compute_roof_area(mask, lat, zoom):
    pixel_count      = int(np.sum(mask.astype(bool)))
    lat_rad          = math.radians(lat)
    meters_per_pixel = (156543.03392 * math.cos(lat_rad)) / (2 ** zoom)
    area_m2          = pixel_count * (meters_per_pixel ** 2)
    area_ft2         = area_m2 * 10.7639
    return pixel_count, meters_per_pixel, area_m2, area_ft2

#==============================================================
# DRAW — unchanged
#==============================================================

def draw_result(image, mask, cx, cy):
    overlay = image.copy()
    if mask is not None:
        overlay[mask.astype(bool)] = [0, 255, 0]
        result      = cv2.addWeighted(image, 0.7, overlay, 0.3, 0)
        mask_uint8  = (mask * 255).astype(np.uint8)
        contours, _ = cv2.findContours(
            mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        cv2.drawContours(result, contours, -1, (0, 100, 0), 1)
        cv2.circle(result, (cx, cy), 7, (255, 0, 0), -1)
    else:
        result = image.copy()
        cv2.circle(result, (IMG_SIZE // 2, IMG_SIZE // 2), 8, (0, 0, 255), -1)
    return result

#==============================================================
# IMAGE → BASE64 — unchanged
#==============================================================

def image_to_base64(image_bgr):
    _, buffer = cv2.imencode('.png', image_bgr)
    b64 = base64.b64encode(buffer).decode('utf-8')
    return f"data:image/png;base64,{b64}"

#==============================================================
# NEW: COORDINATE CONVERSIONS (pixel ↔ lat/lon)
# These are needed for polygon extraction and editing
#==============================================================

def pixel_to_latlon(px, py, ref_lat, ref_lon):
    """Convert pixel x,y inside the 1024×1024 image → lat/lon"""
    xtile, ytile = latlon_to_tile(ref_lat, ref_lon, ZOOM)
    start_x      = xtile - (IMG_SIZE // TILE_SIZE) // 2
    start_y      = ytile - (IMG_SIZE // TILE_SIZE) // 2
    n            = 2.0 ** ZOOM
    tile_x       = start_x + px / TILE_SIZE
    tile_y       = start_y + py / TILE_SIZE
    lon          = tile_x / n * 360.0 - 180.0
    lat_rad      = math.atan(math.sinh(math.pi * (1 - 2 * tile_y / n)))
    lat          = math.degrees(lat_rad)
    return lat, lon


def latlon_to_pixel(lat, lon, ref_lat, ref_lon):
    """Convert lat/lon → pixel x,y inside the 1024×1024 image"""
    xtile, ytile = latlon_to_tile(ref_lat, ref_lon, ZOOM)
    start_x      = xtile - (IMG_SIZE // TILE_SIZE) // 2
    start_y      = ytile - (IMG_SIZE // TILE_SIZE) // 2
    n            = 2.0 ** ZOOM
    lat_rad      = math.radians(lat)
    exact_x      = (lon + 180.0) / 360.0 * n
    exact_y      = (
        (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi)
        / 2.0 * n
    )
    px = int((exact_x - start_x) * TILE_SIZE)
    py = int((exact_y - start_y) * TILE_SIZE)
    px = max(0, min(IMG_SIZE - 1, px))
    py = max(0, min(IMG_SIZE - 1, py))
    return px, py

#==============================================================
# NEW: MASK → POLYGON in lat/lon
#==============================================================

def mask_to_polygon(mask, ref_lat, ref_lon, epsilon_factor=0.005):
    """
    Convert binary mask → simplified polygon in lat/lon coords.
    epsilon_factor: 0.005 = good balance of detail vs simplicity
    """
    mask_u8     = (mask.astype(np.uint8) * 255)
    contours, _ = cv2.findContours(
        mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours:
        return []
    cnt     = max(contours, key=cv2.contourArea)
    epsilon = epsilon_factor * cv2.arcLength(cnt, True)
    approx  = cv2.approxPolyDP(cnt, epsilon, True)
    pts_px  = approx.reshape(-1, 2)

    polygon = []
    for px, py in pts_px:
        lat, lon = pixel_to_latlon(int(px), int(py), ref_lat, ref_lon)
        polygon.append([lat, lon])
    return polygon

#==============================================================
# NEW: POLYGON → MASK (for recalculation after editing)
#==============================================================

def polygon_to_mask(polygon_latlon, ref_lat, ref_lon):
    """Convert edited lat/lon polygon → binary mask"""
    pts = []
    for lat, lon in polygon_latlon:
        px, py = latlon_to_pixel(lat, lon, ref_lat, ref_lon)
        pts.append([px, py])
    pts  = np.array(pts, dtype=np.int32)
    mask = np.zeros((IMG_SIZE, IMG_SIZE), dtype=np.uint8)
    cv2.fillPoly(mask, [pts], 1)
    return mask.astype(bool)

#==============================================================
# NEW: SNAP TO RECTANGLE
#==============================================================

def snap_to_rectangle(polygon_latlon, ref_lat, ref_lon):
    """
    Fit minimum area rectangle → straight edges.
    Returns 4-point rectangle in lat/lon.
    """
    pts = []
    for lat, lon in polygon_latlon:
        px, py = latlon_to_pixel(lat, lon, ref_lat, ref_lon)
        pts.append([px, py])
    pts     = np.array(pts, dtype=np.float32)
    rect    = cv2.minAreaRect(pts)
    box_pts = cv2.boxPoints(rect).astype(int)
    rectangle = []
    for px, py in box_pts:
        lat, lon = pixel_to_latlon(int(px), int(py), ref_lat, ref_lon)
        rectangle.append([lat, lon])
    return rectangle

#==============================================================
# MAIN CALLABLE — estimate_roof
# Your original working code + polygon added at the end
#==============================================================

def estimate_roof(lat: float, lon: float) -> dict:
    try:
        # 1. Download tiles — unchanged
        image = download_satellite_image(lat, lon)

        # 2. Get model — unchanged
        predictor = get_predictor()

        # 3. Set image — unchanged
        print("Running inference...")
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        predictor.set_image(image_rgb)

        # 4. Compute prompt pixel — unchanged
        xtile, ytile = latlon_to_tile(lat, lon, ZOOM)
        start_x      = xtile - (IMG_SIZE // TILE_SIZE) // 2
        start_y      = ytile - (IMG_SIZE // TILE_SIZE) // 2
        n            = 2.0 ** ZOOM
        lat_rad      = math.radians(lat)
        exact_x      = (lon + 180.0) / 360.0 * n
        exact_y      = (
            (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi)
            / 2.0 * n
        )
        prompt_x = int((exact_x - start_x) * TILE_SIZE)
        prompt_y = int((exact_y - start_y) * TILE_SIZE)
        prompt_x = max(0, min(IMG_SIZE - 1, prompt_x))
        prompt_y = max(0, min(IMG_SIZE - 1, prompt_y))

        # 5. SAM predict — unchanged
        input_point = np.array([[prompt_x, prompt_y]])
        input_label = np.array([1])
        masks, scores, logits = predictor.predict(
            point_coords=input_point,
            point_labels=input_label,
            multimask_output=False,
        )
        best_mask = masks[0]

        # 6. Refine — unchanged
        best_mask = refine_mask(best_mask)

        # 7. Centroid + distance — unchanged
        cx, cy = compute_centroid(best_mask)
        dist   = (
            math.sqrt((cx - prompt_x)**2 + (cy - prompt_y)**2)
            if cx else 9999
        )

        # 8. Draw + encode — unchanged
        result_image = draw_result(image, best_mask, prompt_x, prompt_y)
        image_b64    = image_to_base64(result_image)

        # 9. Area — unchanged
        pixel_count, mpp, area_m2, area_ft2 = compute_roof_area(
            best_mask, lat, ZOOM
        )

        # 10. NEW: Extract polygon in lat/lon
        polygon = mask_to_polygon(best_mask, lat, lon, epsilon_factor=0.005)
        print(f"Polygon vertices: {len(polygon)}")

        return {
            "roof_found":       True,
            "area_m2":          round(area_m2, 2),
            "area_ft2":         round(area_ft2, 2),
            "pixel_count":      pixel_count,
            "meters_per_pixel": round(mpp, 6),
            "distance_px":      round(dist, 1),
            "image_base64":     image_b64,
            "polygon":          polygon,   # NEW
            "lat":              lat,
            "lon":              lon,
        }

    except Exception as e:
        raise RuntimeError(f"Pipeline error: {str(e)}")

#==============================================================
# NEW: RECALCULATE FROM EDITED POLYGON
#==============================================================

def recalculate_from_polygon(polygon: list,
                              ref_lat: float,
                              ref_lon: float) -> dict:
    try:
        mask = polygon_to_mask(polygon, ref_lat, ref_lon)
        pixel_count, mpp, area_m2, area_ft2 = compute_roof_area(
            mask, ref_lat, ZOOM
        )
        return {
            "area_m2":          round(area_m2, 2),
            "area_ft2":         round(area_ft2, 2),
            "pixel_count":      pixel_count,
            "meters_per_pixel": round(mpp, 6),
        }
    except Exception as e:
        raise RuntimeError(f"Recalculate error: {str(e)}")

#==============================================================
# NEW: SNAP POLYGON TO RECTANGLE
#==============================================================

def snap_polygon_to_rectangle(polygon: list,
                               ref_lat: float,
                               ref_lon: float) -> dict:
    try:
        rect_polygon = snap_to_rectangle(polygon, ref_lat, ref_lon)
        mask         = polygon_to_mask(rect_polygon, ref_lat, ref_lon)
        pixel_count, mpp, area_m2, area_ft2 = compute_roof_area(
            mask, ref_lat, ZOOM
        )
        return {
            "polygon":          rect_polygon,
            "area_m2":          round(area_m2, 2),
            "area_ft2":         round(area_ft2, 2),
            "pixel_count":      pixel_count,
            "meters_per_pixel": round(mpp, 6),
        }
    except Exception as e:
        raise RuntimeError(f"Snap error: {str(e)}")
