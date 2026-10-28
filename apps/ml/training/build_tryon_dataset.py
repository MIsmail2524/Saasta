"""Build Saasta's own try-on training set from partner stores that opted in (allow_training).

Stores already shoot exactly what try-on models learn from: the garment alone (flat-lay / ghost
mannequin) and the same garment worn by a model. For each opted-in product we pull every product
image, label each one with our embedding model (garment-only vs worn), and write pairs:

  out/
    cloth/<id>.jpg        garment alone
    image/<id>_<n>.jpg    person wearing it
    pairs.jsonl           {"cloth": ..., "image": ..., "category": ..., "store": ..., "product_url": ...}

  python -m app.admin export-training-stores ../ml/data/stores.txt   # in apps/api
  python training/build_tryon_dataset.py --stores data/stores.txt --out data/tryon

This dataset is the moat: public try-on datasets (VITON-HD, DressCode) are research-only, and ours is
licensed by the stores themselves, with South Asian garments those datasets barely cover.
"""
import argparse
import io
import json
import os
import time
import urllib.request

import numpy as np
from PIL import Image

from app import embed

UA = "SaastaBot/1.0 (+https://saasta.pk/bot)"
WORN = ["a photo of a person wearing clothes", "a fashion model posing in an outfit"]
ALONE = ["a product photo of a garment on a plain background", "a flat lay photo of clothing",
         "a garment on an invisible mannequin"]
CATEGORY = {"one-pieces": ["a dress", "a shalwar kameez suit", "a lehenga", "a jumpsuit", "a saree"],
            "tops": ["a shirt", "a kurta", "a t-shirt", "a jacket", "a sweater"],
            "bottoms": ["trousers", "jeans", "a skirt", "shalwar"]}


def fetch(url, limit=10_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": UA})  # noqa: S310 - https store URLs we build
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 - opted-in store domains only
        return r.read(limit)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stores", required=True, help="file with one opted-in Shopify domain per line")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-products", type=int, default=2000)
    args = ap.parse_args()
    os.makedirs(f"{args.out}/cloth", exist_ok=True)
    os.makedirs(f"{args.out}/image", exist_ok=True)

    worn_v, alone_v = embed.texts(WORN).mean(0), embed.texts(ALONE).mean(0)
    cat_names = list(CATEGORY)
    cat_v = np.stack([embed.texts(p).mean(0) for p in CATEGORY.values()])
    pairs = open(f"{args.out}/pairs.jsonl", "a", encoding="utf-8")

    for domain in [d.strip() for d in open(args.stores) if d.strip() and not d.startswith("#")]:
        page, n = 1, 0
        while n < args.max_products:
            try:
                products = json.loads(fetch(f"https://{domain}/products.json?limit=250&page={page}"))["products"]
            except Exception as e:  # noqa: BLE001
                print(f"{domain}: stop ({type(e).__name__})")
                break
            if not products:
                break
            for p in products:
                srcs = [i["src"] for i in p.get("images", [])][:8]
                if len(srcs) < 2:
                    continue
                jpegs = []
                for s in srcs:
                    try:
                        buf = io.BytesIO()
                        Image.open(io.BytesIO(fetch(s))).convert("RGB").save(buf, "JPEG", quality=95)
                        jpegs.append(buf.getvalue())
                    except Exception:  # noqa: BLE001, S112
                        continue
                    time.sleep(0.5)
                if len(jpegs) < 2:
                    continue
                v = embed.images(jpegs)
                alone_score = v @ alone_v - v @ worn_v
                cloth_i = int(alone_score.argmax())
                worn_i = [i for i in range(len(jpegs)) if alone_score[i] < -0.02]
                if alone_score[cloth_i] < 0.02 or not worn_i:
                    continue  # no clean garment-only shot, or no worn shot
                category = cat_names[int((cat_v @ v[cloth_i]).argmax())]
                pid = f"{domain}-{p['id']}"
                with open(f"{args.out}/cloth/{pid}.jpg", "wb") as f:
                    f.write(jpegs[cloth_i])
                for k, i in enumerate(worn_i):
                    name = f"{pid}_{k}.jpg"
                    with open(f"{args.out}/image/{name}", "wb") as f:
                        f.write(jpegs[i])
                    pairs.write(json.dumps({"cloth": f"cloth/{pid}.jpg", "image": f"image/{name}",
                                            "category": category, "store": domain,
                                            "product_url": f"https://{domain}/products/{p['handle']}"}) + "\n")
                n += 1
            page += 1
        print(f"{domain}: {n} products")
    pairs.close()


if __name__ == "__main__":
    main()
