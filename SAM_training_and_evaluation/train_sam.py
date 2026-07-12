import os
import cv2
import torch
import random
import gc
import numpy as np
import pandas as pd
from tqdm import tqdm
from torch.utils.data import Dataset, DataLoader
import torch.nn.functional as F
import torchvision.ops as ops
import torchvision.transforms as transforms
from sklearn.model_selection import train_test_split

from segment_anything import sam_model_registry

# 1. REPRODUCIBILITY
def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

set_seed(42)

# 2. GLOBAL HYPERPARAMETERS
CSV_PATH = "features_split.csv"
ROOT_DIR = "../Final_Data"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

MAX_EPOCHS = 20
BATCH_SIZE = 1           
ACCUMULATION_STEPS = 8   
LR = 1e-4                

VAL_RATIO = 0.15         
PATIENCE = 5             
MIN_DELTA = 0.001        

# Configuration for SAM 1 ViT-B fine-tuning
MODELS_TO_TRAIN = [
    {
        "name": "SAM 1 ViT-B",
        "type": "vit_b",
        "checkpoint": "sam_vit_b_01ec64.pth",
        "save_dir": "sam1_vit_b_finetuned_weights",
        "best_name": "sam1_vit_b_finetuned_best.pth"
    }
]

# 3. GLOBAL DATASET (Shared Splits)
df_full = pd.read_csv(CSV_PATH)
train_only = df_full[df_full['split'] == 'train'].reset_index(drop=True)

# Generate one global split so both models are evaluated on the exact same validation images
train_df, val_df = train_test_split(train_only, test_size=VAL_RATIO, random_state=42, shuffle=True)

print(f"Total pure training images: {len(train_df)}")
print(f"Total validation images (Early Stop gauge): {len(val_df)}\n")

# Added Resize(1024, 1024) because SAM 1 strictly requires 1024x1024 images
sam_transform = transforms.Compose([
    transforms.ToTensor(), 
    transforms.Resize((1024, 1024), antialias=True),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]) # Stats of ImageNet dataset
])

class RooftopDataset(Dataset):
    def __init__(self, dataframe):
        self.df = dataframe.reset_index(drop=True)

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        img = cv2.cvtColor(cv2.imread(os.path.normpath(os.path.join(ROOT_DIR, row["image_path"]))), cv2.COLOR_BGR2RGB)
        mask = cv2.imread(os.path.normpath(os.path.join(ROOT_DIR, row["mask_polygon_path"])), 0)
        
        orig_h, orig_w = mask.shape
        mask = cv2.resize(mask, (1024, 1024), interpolation=cv2.INTER_NEAREST)
        mask = (mask > 0).astype(np.float32)

        coords = np.array([list(map(float, row["mask_coordinates"].split(",")))])
        coords[0, 0] = coords[0, 0] * (1024 / orig_w)
        coords[0, 1] = coords[0, 1] * (1024 / orig_h)
        labels = np.array([1]) 

        img_tensor = sam_transform(img).float()
        mask_tensor = torch.tensor(mask).unsqueeze(0).float()
        return img_tensor, mask_tensor, torch.tensor(coords).float(), torch.tensor(labels).long()

train_loader = DataLoader(RooftopDataset(train_df), batch_size=BATCH_SIZE, shuffle=True)
val_loader = DataLoader(RooftopDataset(val_df), batch_size=1, shuffle=False)

# 4. LOSS & VALIDATION ENGINE
def calc_loss(pred_mask, gt_mask):
    focal_loss = ops.sigmoid_focal_loss(pred_mask, gt_mask, alpha=0.25, gamma=2.0, reduction='mean')
    pred_sigmoid = torch.sigmoid(pred_mask)
    intersection = (pred_sigmoid * gt_mask).sum()
    union = pred_sigmoid.sum() + gt_mask.sum()
    dice_loss = 1 - (2. * intersection + 1e-5) / (union + 1e-5)
    return (20.0 * focal_loss) + dice_loss

def validate_model(model, val_loader):
    model.eval()
    ious = []
    with torch.no_grad():
        with torch.amp.autocast(device_type='cuda', dtype=torch.float16):
            for img, gt_mask, coords, labels in tqdm(val_loader, desc="Validating", leave=False):
                img, gt_mask, coords, labels = img.to(DEVICE), gt_mask.to(DEVICE), coords.to(DEVICE), labels.to(DEVICE)
                if coords.dim() == 2: coords = coords.unsqueeze(1)
                if labels.dim() == 1: labels = labels.unsqueeze(1)

                # SAM 1 validation forward pass
                image_embedding = model.image_encoder(img)
                
                sparse_embeddings, dense_embeddings = model.prompt_encoder(
                    points=(coords, labels), boxes=None, masks=None
                )
                
                low_res_masks, _ = model.mask_decoder(
                    image_embeddings=image_embedding,
                    image_pe=model.prompt_encoder.get_dense_pe(),
                    sparse_prompt_embeddings=sparse_embeddings,
                    dense_prompt_embeddings=dense_embeddings,
                    multimask_output=False,
                )
                
                pred_mask = F.interpolate(low_res_masks, size=gt_mask.shape[-2:], mode="bilinear", align_corners=False)
                pred_bin = (torch.sigmoid(pred_mask) > 0.5).float()
                
                intersection = (pred_bin * gt_mask).sum()
                union = pred_bin.sum() + gt_mask.sum() - intersection
                iou = (intersection + 1e-6) / (union + 1e-6)
                ious.append(iou.item())
            
    model.train() 
    return np.mean(ious)

# 5. CORE TRAINING FUNCTION
def train_sam_model(config):
    print("="*60)
    print(f"INITIALIZING TRAINING PIPELINE FOR: {config['name']}")
    print("="*60)

    os.makedirs(config['save_dir'], exist_ok=True)
    best_model_path = os.path.join(config['save_dir'], config['best_name'])

    # Initialize SAM 1 from the registry
    sam_model = sam_model_registry[config['type']](checkpoint=config['checkpoint'])
    sam_model.to(DEVICE)
    sam_model.train()
    
    for param in sam_model.image_encoder.parameters(): 
        param.requires_grad = False

    optimizer = torch.optim.AdamW([
        {'params': sam_model.mask_decoder.parameters()},
        {'params': sam_model.prompt_encoder.parameters()}
    ], lr=LR, weight_decay=1e-4)

    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='max', factor=0.5, patience=2)
    scaler = torch.amp.GradScaler('cuda')

    best_iou = 0.0
    patience_counter = 0

    for epoch in range(MAX_EPOCHS):
        epoch_loss = 0
        optimizer.zero_grad()
        progress_bar = tqdm(enumerate(train_loader), total=len(train_loader), desc=f"Epoch {epoch+1}/{MAX_EPOCHS}")
        
        for step, (img, gt_mask, coords, labels) in progress_bar:
            img, gt_mask, coords, labels = img.to(DEVICE), gt_mask.to(DEVICE), coords.to(DEVICE), labels.to(DEVICE)
            if coords.dim() == 2: coords = coords.unsqueeze(1)
            if labels.dim() == 1: labels = labels.unsqueeze(1)

            with torch.amp.autocast(device_type='cuda', dtype=torch.float16):
                with torch.no_grad():
                    # SAM 1 forward pass
                    image_embedding = sam_model.image_encoder(img)

                sparse_embeddings, dense_embeddings = sam_model.prompt_encoder(points=(coords, labels), boxes=None, masks=None)
                
                low_res_masks, _ = sam_model.mask_decoder(
                    image_embeddings=image_embedding, 
                    image_pe=sam_model.prompt_encoder.get_dense_pe(),
                    sparse_prompt_embeddings=sparse_embeddings, 
                    dense_prompt_embeddings=dense_embeddings,
                    multimask_output=False,
                )
                
                pred_mask = F.interpolate(low_res_masks, size=gt_mask.shape[-2:], mode="bilinear", align_corners=False)
                loss = calc_loss(pred_mask, gt_mask) / ACCUMULATION_STEPS

            scaler.scale(loss).backward()
            if (step + 1) % ACCUMULATION_STEPS == 0:
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad()
            epoch_loss += loss.item() * ACCUMULATION_STEPS
            progress_bar.set_postfix({"Loss": f"{loss.item() * ACCUMULATION_STEPS:.4f}"})

        print(f"\nEvaluating {config['name']} Epoch {epoch+1}...")
        current_iou = validate_model(sam_model, val_loader)
        
        old_lr = optimizer.param_groups[0]['lr']
        scheduler.step(current_iou)
        if optimizer.param_groups[0]['lr'] < old_lr: 
            print(f"📉 LR reduced from {old_lr:.6e} to {optimizer.param_groups[0]['lr']:.6e}")
            
        print(f"Epoch {epoch+1} Results -> Train Loss: {epoch_loss/len(train_loader):.4f} | Val IoU: {current_iou:.4f}")

        if current_iou > best_iou + MIN_DELTA:
            print(f"🚀 Meaningful Improvement! ({best_iou:.4f} -> {current_iou:.4f}). Saving best model...")
            best_iou = current_iou
            torch.save(sam_model.state_dict(), best_model_path)
            patience_counter = 0
        else:
            patience_counter += 1
            print(f"No improvement. Patience: {patience_counter}/{PATIENCE}")
            if patience_counter >= PATIENCE:
                print(f"Early stopping triggered! Best {config['name']} model saved at {best_model_path}")
                break

    print(f"\n{config['name']} Training Complete! Peak Validation IoU: {best_iou:.4f}.\n")
    
    # Critical Memory Cleanup before starting the next model
    del sam_model, optimizer, scheduler, scaler
    torch.cuda.empty_cache()
    gc.collect()

# ==========================================
# 6. EXECUTION SCRIPT
# ==========================================
if __name__ == "__main__":
    for config in MODELS_TO_TRAIN:
        train_sam_model(config)
    print("ALL MODELS SUCCESSFULLY TRAINED!")