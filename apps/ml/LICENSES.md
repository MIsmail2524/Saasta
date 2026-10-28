# Model licenses

Saasta only ships models whose code **and** weights allow commercial use. Checked October 2026.

| Component | Use | License |
|---|---|---|
| Marqo-FashionSigLIP (ViT-B-16-SigLIP) | Image/text fashion embeddings, zero-shot understanding | Apache-2.0 |
| FASHN VTON v1.5 | Garment try-on (tops, bottoms, one-pieces) | Apache-2.0 |
| DWPose (YOLOX-L, RTMPose wholebody) | Pose keypoints for accessory placement | Apache-2.0 |
| open_clip | Model loading | MIT |

Rejected for commercial use (CC BY-NC-SA or no license): CatVTON, IDM-VTON, OOTDiffusion, FitDiT, Voost,
StableVITON, catvton-flux weights, and the VITON-HD / DressCode research datasets. Do not add them.

Our fine-tuned checkpoints (`training/`) are trained only on data we have rights to: partner-store photos
from stores that opted in (`allow_training`), and our own crawled catalog metadata for retrieval pairs.
