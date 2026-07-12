import pandas as pd
import numpy as np
import cv2
import os
import torch
import gc
from tqdm import tqdm
from scipy.spatial.distance import directed_hausdorff
from skimage.segmentation import find_boundaries

# Changed to SAM 1 imports
from segment_anything import sam_model_registry, SamPredictor

# CONFIGURATION
FEATURE_SPLIT_CSV = "features_split.csv" 
DATASET_ROOT_DIR = "../Final_Data"
OUTPUT_DIR = "evaluation_results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Configuration for SAM 1 ViT-B models only
EVAL_CONFIGS = [
    {
        "name": "SAM1_ViT_B_Raw",
        "model_type": "vit_b",
        "checkpoint": "sam_vit_b_01ec64.pth",
        "finetuned_weights": None
    },
    {
        "name": "SAM1_ViT_B_Finetuned",
        "model_type": "vit_b",
        "checkpoint": "sam_vit_b_01ec64.pth",
        "finetuned_weights": "./sam1_vit_b_finetuned_weights/sam1_vit_b_finetuned_best.pth"
    }
]

# METRICS MATH
def compute_iou(pred, target):
    intersection = np.logical_and(pred, target).sum()
    union = np.logical_or(pred, target).sum()
    if union == 0: return 1.0
    return intersection / union

def compute_ae(pred, target):
    return np.sum(np.abs(pred.astype(float) - target.astype(float)))

def compute_hd(pred, target):
    if np.sum(pred) == 0 or np.sum(target) == 0: return 0.0 
    u = np.array(np.where(pred > 0)).T
    v = np.array(np.where(target > 0)).T
    return max(directed_hausdorff(u, v)[0], directed_hausdorff(v, u)[0])

def compute_bf(pred, target):
    if np.all(pred == target): return 1.0
    p_boundary = find_boundaries(pred, mode='thick')
    t_boundary = find_boundaries(target, mode='thick')
    intersection = np.logical_and(p_boundary, t_boundary).sum()
    if intersection == 0: return 0.0
    precision = intersection / (p_boundary.sum() + 1e-6)
    recall = intersection / (t_boundary.sum() + 1e-6)
    return (2 * precision * recall) / (precision + recall + 1e-6)

# DATASET LOADING (Strictly Test Split)
df_full = pd.read_csv(FEATURE_SPLIT_CSV)
test_df = df_full[df_full['split'] == 'test'].copy().reset_index(drop=True)
device = "cuda" if torch.cuda.is_available() else "cpu"

all_summaries = []

# MAIN INFERENCE LOOP
for config in EVAL_CONFIGS:
    model_name = config['name']
    print("\n" + "="*60)
    print(f"🚀 INITIALIZING EVALUATION FOR: {model_name}")
    print("="*60)
    
    # SAM 1 Initialization
    sam_model = sam_model_registry[config['model_type']](checkpoint=config['checkpoint'])
    sam_model.to(device=device)
    
    if config['finetuned_weights'] and os.path.exists(config['finetuned_weights']):
        print(f"Injecting fine-tuned weights from {config['finetuned_weights']}...")
        sam_model.load_state_dict(torch.load(config['finetuned_weights'], map_location=device))
    elif config['finetuned_weights']:
        print(f"⚠️ Warning: Finetuned weights {config['finetuned_weights']} not found! Evaluating RAW.")
    
    predictor = SamPredictor(sam_model)
    
    ious, bfs, hds, aes, gt_areas, pred_areas = [], [], [], [], [], []
    
    with torch.inference_mode():
        pbar = tqdm(test_df.iterrows(), total=len(test_df), desc=f"Eval {model_name}")
        for idx, row in pbar:
            img_path = os.path.normpath(os.path.join(DATASET_ROOT_DIR, row['image_path']))
            gt_path = os.path.normpath(os.path.join(DATASET_ROOT_DIR, row['mask_polygon_path']))
            
            if not os.path.exists(img_path) or not os.path.exists(gt_path):
                ious.append(0); bfs.append(0); hds.append(0); aes.append(0)
                gt_areas.append(0); pred_areas.append(0)
                continue

            x_str, y_str = str(row['mask_coordinates']).replace('"', '').split(',')
            point_coords = np.array([[int(x_str), int(y_str)]])
            point_labels = np.array([1]) 
            
            image = cv2.imread(img_path)
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            gt_mask = cv2.imread(gt_path, cv2.IMREAD_GRAYSCALE)
            gt_mask_bin = (gt_mask > 0).astype(np.uint8)
            
            predictor.set_image(image_rgb)
            masks, scores, _ = predictor.predict(
                point_coords=point_coords, point_labels=point_labels, multimask_output=False
            )
            pred_mask_bin = (masks[0] > 0).astype(np.uint8)
            
            ious.append(compute_iou(pred_mask_bin, gt_mask_bin))
            bfs.append(compute_bf(pred_mask_bin, gt_mask_bin))
            hds.append(compute_hd(pred_mask_bin, gt_mask_bin))
            aes.append(compute_ae(pred_mask_bin, gt_mask_bin))
            gt_areas.append(np.sum(gt_mask_bin))
            pred_areas.append(np.sum(pred_mask_bin))
            
            pbar.set_postfix({"Mean_IoU": f"{np.mean(ious):.4f}"})

    # Safely append new columns to the existing test_df structure
    results_df = test_df.copy()
    results_df['model_name'] = model_name
    results_df['pred_iou'] = ious  
    results_df['boundary_f_score'] = bfs
    results_df['hausdorff_distance'] = hds
    results_df['absolute_error'] = aes
    results_df['gt_area'] = gt_areas
    results_df['pred_area'] = pred_areas
    
    results_csv_path = os.path.join(OUTPUT_DIR, f"results_{model_name}.csv")
    results_df.to_csv(results_csv_path, index=False)

    # Store summary for the LaTeX table
    all_summaries.append({
        "Model": model_name.replace("_", " "),
        "IoU": np.mean(ious),
        "BF": np.mean(bfs),
        "HD (px)": np.mean(hds),
        "AE": np.mean(aes)
    })
    
    # Memory Cleanup
    del sam_model, predictor
    torch.cuda.empty_cache()
    gc.collect()

# GENERATE LATEX TABLE FOR OVERLEAF
summary_df = pd.DataFrame(all_summaries)

# Identify best values to bold them in LaTeX
best_iou = summary_df['IoU'].max()
best_bf = summary_df['BF'].max()
best_hd = summary_df['HD (px)'].min()
best_ae = summary_df['AE'].min()

latex_str = "\\begin{table}[h!]\n\\centering\n\\begin{tabular}{lcccc}\n\\toprule\n"
latex_str += "\\textbf{Model} & \\textbf{IoU $\\uparrow$} & \\textbf{Boundary F-Score $\\uparrow$} & \\textbf{Hausdorff Dist $\\downarrow$} & \\textbf{Absolute Error $\\downarrow$} \\\\\n\\midrule\n"

for _, row in summary_df.iterrows():
    iou_str = f"\\textbf{{{row['IoU']:.4f}}}" if row['IoU'] == best_iou else f"{row['IoU']:.4f}"
    bf_str = f"\\textbf{{{row['BF']:.4f}}}" if row['BF'] == best_bf else f"{row['BF']:.4f}"
    hd_str = f"\\textbf{{{row['HD (px)']:.2f}}}" if row['HD (px)'] == best_hd else f"{row['HD (px)']:.2f}"
    ae_str = f"\\textbf{{{row['AE']:.2f}}}" if row['AE'] == best_ae else f"{row['AE']:.2f}"
    
    latex_str += f"{row['Model']} & {iou_str} & {bf_str} & {hd_str} & {ae_str} \\\\\n"

latex_str += "\\bottomrule\n\\end{tabular}\n\\caption{Performance Comparison of SAM 1 Models on Rooftop Segmentation.}\n\\label{tab:sam1_results}\n\\end{table}"

latex_path = os.path.join(OUTPUT_DIR, "unified_latex_table.tex")
with open(latex_path, "w") as f:
    f.write(latex_str)

print("\n" + "="*60)
print(f"ALL EVALUATIONS COMPLETED!")
print(f"Results saved to '{OUTPUT_DIR}/'.")
print(f"LaTeX Table generated at '{latex_path}'.")
print("="*60)