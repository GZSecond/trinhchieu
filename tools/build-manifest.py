#!/usr/bin/env python3
"""Quét thư mục photos/ rồi sinh photos.json + thumbs/*.jpg cho kho ảnh chung.

Chạy từ thư mục gốc của repo:   python3 tools/build-manifest.py
Cần Pillow (pip install pillow). GitHub Action trong .github/workflows tự chạy file này.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHOTOS = os.path.join(ROOT, "photos")
THUMBS = os.path.join(ROOT, "thumbs")
OUT = os.path.join(ROOT, "photos.json")
EXTS = {".gif", ".jpg", ".jpeg", ".png", ".webp", ".svg"}
THUMB_MAX = 160  # cạnh dài nhất của ảnh nhỏ (px), giống trang gốc


def natural_key(name):
    # anh2.gif đứng trước anh10.gif
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def make_thumb(src, dst):
    with Image.open(src) as im:
        w, h = im.size
        im.seek(0)  # GIF: lấy khung hình đầu
        fr = im.convert("RGB")
        k = min(1.0, THUMB_MAX / max(w, h))
        fr = fr.resize((max(1, round(w * k)), max(1, round(h * k))), Image.LANCZOS)
        fr.save(dst, "JPEG", quality=60, optimize=True)
        return w, h


def main():
    if not os.path.isdir(PHOTOS):
        sys.exit("Không thấy thư mục photos/")
    os.makedirs(THUMBS, exist_ok=True)

    names = sorted(
        (n for n in os.listdir(PHOTOS) if os.path.splitext(n)[1].lower() in EXTS),
        key=natural_key,
    )

    old = {}
    if os.path.exists(OUT):
        try:
            with open(OUT, encoding="utf-8") as f:
                old = {p["name"]: p for p in json.load(f).get("photos", [])}
        except Exception:
            old = {}

    photos, keep = [], set()
    for n in names:
        src = os.path.join(PHOTOS, n)
        stem = os.path.splitext(n)[0]
        tname = stem + ".jpg"
        dst = os.path.join(THUMBS, tname)
        size = os.path.getsize(src)
        prev = old.get(n)
        # Không tính lại nếu ảnh chưa đổi (cùng dung lượng và đã có thumbnail)
        if prev and prev.get("bytes") == size and os.path.exists(dst) and prev.get("w") and prev.get("h"):
            w, h = prev["w"], prev["h"]
        else:
            try:
                w, h = make_thumb(src, dst)
            except Exception as e:  # file hỏng: bỏ qua, không làm hỏng cả kho
                print(f"! Bỏ qua {n}: {e}", file=sys.stderr)
                continue
        keep.add(tname)
        photos.append({
            "file": f"photos/{n}",
            "name": n,
            "w": w,
            "h": h,
            "bytes": size,
            "thumb": f"thumbs/{tname}",
        })

    # Xóa thumbnail của ảnh đã bị gỡ khỏi photos/
    for t in os.listdir(THUMBS):
        if t.endswith(".jpg") and t not in keep:
            os.remove(os.path.join(THUMBS, t))

    manifest = {
        "version": 1,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(photos),
        "photos": photos,
    }
    # Chỉ ghi lại khi danh sách thật sự đổi, tránh commit rỗng liên tục
    new_body = json.dumps({**manifest, "generated": ""}, ensure_ascii=False, sort_keys=True)
    old_body = ""
    if os.path.exists(OUT):
        try:
            with open(OUT, encoding="utf-8") as f:
                old_body = json.dumps({**json.load(f), "generated": ""}, ensure_ascii=False, sort_keys=True)
        except Exception:
            pass
    if new_body != old_body:
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print(f"Đã ghi photos.json ({len(photos)} ảnh)")
    else:
        print(f"photos.json không đổi ({len(photos)} ảnh)")


if __name__ == "__main__":
    main()
