# Saasta's models

Saasta owns its whole stack: no calls to external AI, search or scraping APIs at runtime. We start from
open-weight foundations whose licenses allow commercial use, run them on our own servers, and make them
ours by fine-tuning on data we have rights to.

## 1. Fashion understanding and search: `saasta-siglip`

- **Base:** Marqo-FashionSigLIP (ViT-B-16-SigLIP, Apache-2.0). One embedding space for images and text.
- **Used for:** visual search (image to image), text search (text to image), zero-shot category, colour and
  attributes (`apps/api/app/search/labels.py`), refinement ("same but black"), dataset labelling.
- **Ours:** `apps/ml/training/finetune_embed.py` fine-tunes it with the SigLIP loss on opted-in catalog
  pairs (product photo ↔ title + category + colour), measuring held-out recall@5 before and after.
  It learns local vocabulary (kurta, khussa, jhumka, lawn, gharara) and local photography styles.
- **Serve:** `SAASTA_ML_EMBED_CHECKPOINT=weights/saasta-siglip.pt`, then `python -m app.admin index` to re-embed.

## 2. Garment try-on (tops, bottoms, full suits)

- **Base:** FASHN VTON v1.5 (Apache-2.0 code and weights), self-hosted in `apps/ml/app/garment.py`.
  Maskless, pixel-space diffusion. GPU recommended. CPU runs in float32 and takes minutes per image.
- **Ours, next step:** `apps/ml/training/build_tryon_dataset.py` builds a licensed paired dataset from
  stores that opted in. Each product's flat-lay image plus its on-model images become a pair, labelled
  automatically by our embedding model. Public try-on datasets (VITON-HD, DressCode) are research-only and
  barely include shalwar kameez, lehenga or dupatta, so this dataset is the moat.
- **Training plan:** once we have about 20k pairs and GPU budget (one 8×A100 week or a few weeks on one GPU),
  fine-tune the try-on model on our pairs. Target: eastern wear quality, dupatta drape, embroidery fidelity.
  The upstream repo ships inference only, so fine-tuning code is ours to write against its architecture.
  The dataset builder comes first because data is the bottleneck, not code.

## 3. Accessory try-on (necklaces, earrings, glasses, watches, bags, shoes)

No permissively licensed model covers accessories, so we built our own engine (`apps/ml/app/place.py`):
1. **Pose:** DWPose ONNX weights (Apache-2.0) with our own minimal inference code (`apps/ml/app/pose.py`):
   YOLOX person detection, then RTMPose keypoints.
2. **Cut-out:** our own studio-background removal (border colour model + flood fill, which keeps inner holes
   like stones and chain gaps). It rejects busy backgrounds instead of producing a bad result.
3. **Placement:** anatomical anchors and scale from shoulder width: necklace at the collarbone, earrings
   under the ears, glasses across the eyes (rotated to the head tilt), a watch on the wrist (along the forearm),
   a bag at the hand, shoes at the ankles. Plus a soft contact shadow.

It's fast (about 1 s on CPU) and deterministic. Next: a small learned harmonisation model trained on the same
opted-in data, so lighting and occlusion (hair over earrings) look natural.

## Data rules

- Shopper uploads and try-on selfies are **never** used for training.
- Only stores with `allow_training` (opt-in at signup, revocable) contribute training photos.
- Crawled data is used for search only: titles, prices, links and embeddings. Crawled images are not re-hosted
  and not used to train.
