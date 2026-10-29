#!/usr/bin/env python3
"""
portrait.py - Samples portrait points from an image to create an animated dot-matrix particle cloud.
Requires: Pillow, numpy
Saves: dots.json (consumed by generate.py)
"""

import sys
import os
import json
import math
import numpy as np
from PIL import Image, ImageFilter

def process_portrait(image_path, output_json="dots.json", num_points=1900):
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found at: {image_path}")
    
    img = Image.open(image_path).convert("RGB")
    arr = np.array(img)
    h_orig, w_orig, _ = arr.shape

    # 1. Background removal
    # The background is composed of deep navy blue tones where Blue is significantly higher than Red & Green
    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    b = arr[:, :, 2].astype(int)

    is_bg = (b > r + 15) & (b > g + 15) & (b > 55)
    fg_mask = ~is_bg

    # 2. Crop to head, face and collar
    # In 1080x1080: head starts ~80, chin ~750, collar/hoodie ~1000, x ~150 to 930
    y0, y1 = 70, 1020
    x0, x1 = 150, 930

    crop_fg = fg_mask[y0:y1, x0:x1]
    cropped_rgb = arr[y0:y1, x0:x1]
    ch, cw = crop_fg.shape

    # 3. Detect edges & features
    edges_img = img.filter(ImageFilter.FIND_EDGES).convert("L")
    crop_edges = np.array(edges_img)[y0:y1, x0:x1].astype(float)
    crop_edges[~crop_fg] = 0

    cr = cropped_rgb[:, :, 0].astype(int)
    cg = cropped_rgb[:, :, 1].astype(int)
    cb = cropped_rgb[:, :, 2].astype(int)

    # Detect dark regions (hair & sunglasses)
    is_black = (cr < 28) & (cg < 28) & (cb < 28) & crop_fg
    # Detect skin
    is_skin = (cr > 75) & (cg > 35) & (cb < 75) & crop_fg
    # Detect hoodie
    is_hoodie = (cr > 50) & (cb > 90) & (cg < 50) & crop_fg

    # 4. Construct weighting field
    weight = np.zeros((ch, cw), dtype=float)
    # High weight on facial contour edges, sunglasses boundary, and jawline
    weight += (crop_edges ** 1.25) * 2.8

    # Sunglasses fill
    sunglasses_box = np.zeros_like(is_black)
    # in crop coords: y ~ 350 to 510, x ~ 170 to 610
    sunglasses_box[340:510, 160:620] = True
    weight[is_black & sunglasses_box] += 130.0

    # Afro hair texture & perimeter
    weight[is_black & ~sunglasses_box] += 48.0

    # Face skin stippling
    weight[is_skin] += 32.0

    # Lips enhancement (around y=560..630, x=300..480 in crop coordinates)
    lips_box = np.zeros_like(is_skin)
    lips_box[550:640, 290:490] = True
    weight[is_skin & lips_box] += 40.0

    # Hoodie collar lines
    weight[is_hoodie] += 22.0

    # Strictly zero out background
    weight[~crop_fg] = 0

    # 5. Probabilistic sampling
    flat_w = weight.flatten()
    total_w = flat_w.sum()
    if total_w == 0:
        raise ValueError("Could not detect foreground features in portrait.")
    
    probs = flat_w / total_w
    np.random.seed(1337)
    sample_indices = np.random.choice(len(flat_w), size=num_points, replace=False, p=probs)
    ys, xs = np.unravel_index(sample_indices, (ch, cw))

    # 6. Normalize coordinates to target SVG panel (220 width x 250 height)
    # Add gentle padding inside panel: x in [15, 205], y in [15, 235]
    min_x, max_x = xs.min(), xs.max()
    min_y, max_y = ys.min(), ys.max()

    target_w = 190.0
    target_h = 220.0
    offset_x = 15.0
    offset_y = 15.0

    scale = min(target_w / (max_x - min_x), target_h / (max_y - min_y))
    center_shift_x = (220.0 - (max_x - min_x) * scale) / 2.0
    center_shift_y = (250.0 - (max_y - min_y) * scale) / 2.0

    # 7. Scatter trajectory assignment
    # 32 distinct scatter trajectories: angle around center, distance 50-130px
    num_groups = 32
    scatter_vectors = []
    for g_id in range(num_groups):
        angle = (2.0 * math.pi / num_groups) * g_id + (np.random.rand() * 0.2 - 0.1)
        dist = np.random.uniform(50.0, 140.0)
        scatter_vectors.append({
            "dx": round(math.cos(angle) * dist, 1),
            "dy": round(math.sin(angle) * dist, 1),
            "delay": round((g_id % 8) * 0.12, 2)
        })

    dots = []
    for x_orig, y_orig in zip(xs, ys):
        norm_x = round(center_shift_x + (x_orig - min_x) * scale, 1)
        norm_y = round(center_shift_y + (y_orig - min_y) * scale, 1)
        
        # Assign group based on angle from center + pseudo-random jitter
        c_dx = norm_x - 110.0
        c_dy = norm_y - 125.0
        pt_angle = (math.atan2(c_dy, c_dx) + 2 * math.pi) % (2 * math.pi)
        base_group = int((pt_angle / (2 * math.pi)) * num_groups) % num_groups
        # add slight group jitter so nearby points scatter organically
        jittered_group = (base_group + np.random.choice([-1, 0, 1])) % num_groups

        # Determine dot category / radius:
        # Sunglasses & edge points get slightly more prominent radius (1.3), fill points 1.0
        is_feature = (is_black[y_orig, x_orig] and sunglasses_box[y_orig, x_orig]) or (crop_edges[y_orig, x_orig] > 40)
        radius = 1.3 if is_feature else 1.05

        dots.append({
            "x": norm_x,
            "y": norm_y,
            "r": radius,
            "g": int(jittered_group),
            "feat": bool(is_feature)
        })

    output_data = {
        "panel": {"width": 220, "height": 250},
        "num_dots": len(dots),
        "scatter_groups": scatter_vectors,
        "dots": dots
    }

    with open(output_json, "w") as f:
        json.dump(output_data, f, separators=(',', ':'))

    print(f"Successfully generated {len(dots)} dots saved to {output_json}")
    return output_data

if __name__ == "__main__":
    pfp_path = sys.argv[1] if len(sys.argv) > 1 else "../public/Bullish PFP 2.png"
    out_file = sys.argv[2] if len(sys.argv) > 2 else "dots.json"
    process_portrait(pfp_path, out_file)
