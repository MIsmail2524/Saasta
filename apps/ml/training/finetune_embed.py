"""Fine-tune our fashion embedding model on Saasta's own catalog (image <-> product text).

Makes the search model ours: it learns local categories (kurta, khussa, jhumka, lawn, ...) and
how Pakistani stores photograph products. Uses the SigLIP sigmoid contrastive loss.

  python -m app.admin export-training ../ml/data/catalog.jsonl     # in apps/api
  python training/finetune_embed.py --data data/catalog.jsonl --out weights/saasta-siglip.pt

Then serve it:  SAASTA_ML_EMBED_CHECKPOINT=weights/saasta-siglip.pt
GPU strongly recommended; --max-steps keeps CPU smoke runs short.
"""
import argparse
import io
import json
import random
import urllib.request

import open_clip
import torch
import torch.nn.functional as F
from PIL import Image
from torch.utils.data import DataLoader, Dataset

MODEL = "hf-hub:Marqo/marqo-fashionSigLIP"


class CatalogPairs(Dataset):
    def __init__(self, rows, preprocess, tokenizer):
        self.rows, self.preprocess, self.tokenizer = rows, preprocess, tokenizer

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        if r.get("path"):
            img = Image.open(r["path"])
        else:  # exported rows point at our own media store or opted-in partner images
            with urllib.request.urlopen(r["image_url"], timeout=20) as resp:  # noqa: S310 - trusted export
                img = Image.open(io.BytesIO(resp.read(8_000_000)))
        text = r["text"]
        return self.preprocess(img.convert("RGB")), self.tokenizer([text])[0]


def siglip_loss(img, txt, scale, bias):
    logits = img @ txt.T * scale + bias
    labels = 2 * torch.eye(len(img), device=img.device) - 1  # +1 on the diagonal, -1 elsewhere
    return -F.logsigmoid(labels * logits).sum() / len(img)


@torch.no_grad()
def recall_at_k(model, loader, device, k=5):
    imgs, txts = [], []
    for x, t in loader:
        imgs.append(F.normalize(model.encode_image(x.to(device)), dim=-1))
        txts.append(F.normalize(model.encode_text(t.to(device)), dim=-1))
    i, t = torch.cat(imgs), torch.cat(txts)
    sims = i @ t.T
    hits = (sims.topk(min(k, len(t)), dim=1).indices == torch.arange(len(i), device=device)[:, None]).any(1)
    return hits.float().mean().item()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument("--max-steps", type=int, default=0)
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, _, preprocess = open_clip.create_model_and_transforms(MODEL)
    tokenizer = open_clip.get_tokenizer(MODEL)
    model.to(device)

    rows = [json.loads(line) for line in open(args.data, encoding="utf-8") if line.strip()]
    random.Random(7).shuffle(rows)  # noqa: S311 - reproducible split, not crypto
    cut = max(1, len(rows) // 20)
    train, val = rows[cut:], rows[:cut]
    tl = DataLoader(CatalogPairs(train, preprocess, tokenizer), batch_size=args.batch, shuffle=True,
                    num_workers=4, drop_last=True)
    vl = DataLoader(CatalogPairs(val, preprocess, tokenizer), batch_size=args.batch, num_workers=4)

    model.eval()
    print(f"baseline recall@5 on held-out: {recall_at_k(model, vl, device):.3f}")
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr, weight_decay=0.05)
    step = 0
    for epoch in range(args.epochs):
        model.train()
        for x, t in tl:
            img = F.normalize(model.encode_image(x.to(device)), dim=-1)
            txt = F.normalize(model.encode_text(t.to(device)), dim=-1)
            loss = siglip_loss(img, txt, model.logit_scale.exp(), model.logit_bias)
            opt.zero_grad()
            loss.backward()
            opt.step()
            step += 1
            if step % 50 == 0:
                print(f"epoch {epoch} step {step} loss {loss.item():.4f}")
            if args.max_steps and step >= args.max_steps:
                break
        model.eval()
        print(f"epoch {epoch} recall@5: {recall_at_k(model, vl, device):.3f}")
        if args.max_steps and step >= args.max_steps:
            break
    torch.save({"model": model.state_dict(), "base": MODEL}, args.out)
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()
