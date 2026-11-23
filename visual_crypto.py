import os
import io
import base64
import hashlib
import numpy as np
from PIL import Image

def get_pin_rng(pin: str):
    """
    Derives a cryptographically strong, reproducible PRNG seed from a user PIN or secret word.
    """
    if not pin or not pin.strip():
        return np.random.default_rng()
    # Hash PIN using SHA-256 and take first 8 bytes as uint64 seed
    seed_bytes = hashlib.sha256(pin.strip().encode("utf-8")).digest()
    seed_int = int.from_bytes(seed_bytes[:8], byteorder="big")
    return np.random.default_rng(seed_int)

def process_visual_crypto(image_path_or_bytes, threshold=128, max_dimension=450, pin=""):
    """
    Naor-Shamir (2, 2) Visual Cryptography Scheme with optional Secret PIN.
    Splits a binary secret image into two noisy shares.
    If a PIN is provided, Share 1 is generated deterministically from the PIN,
    so the receiver only needs Share 2 and the PIN to unlock the image.
    """
    if isinstance(image_path_or_bytes, Image.Image):
        im = image_path_or_bytes.copy()
    else:
        im = Image.open(image_path_or_bytes)

    # Convert to grayscale
    im = im.convert("L")

    # Resize proportionally if larger than max_dimension to preserve responsiveness
    w, h = im.size
    if max(w, h) > max_dimension:
        scale = max_dimension / max(w, h)
        new_w = max(16, int(w * scale))
        new_h = max(16, int(h * scale))
        im = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
        w, h = new_w, new_h

    # Binarize image (True = White/Light, False = Black/Dark)
    arr = np.array(im)
    binary = arr >= int(threshold)

    # Share dimensions: 2x2 expansion per secret pixel
    s_h, s_w = h * 2, w * 2
    share1_arr = np.zeros((s_h, s_w), dtype=np.uint8)
    share2_arr = np.zeros((s_h, s_w), dtype=np.uint8)

    # Define the 2x2 basis subpixel patterns
    # Pattern A: [Black, White / White, Black]
    # Pattern B: [White, Black / Black, White]
    pat_A = np.array([[0, 255], [255, 0]], dtype=np.uint8)
    pat_B = np.array([[255, 0], [0, 255]], dtype=np.uint8)

    # Seed RNG with secret PIN if provided, otherwise uniform random
    rng = get_pin_rng(pin)
    coin = rng.integers(0, 2, size=(h, w))

    for y in range(h):
        for x in range(w):
            choice = pat_A if coin[y, x] == 0 else pat_B
            comp   = pat_B if coin[y, x] == 0 else pat_A

            # Share 1 always receives the chosen subpixel pattern
            share1_arr[y*2:y*2+2, x*2:x*2+2] = choice

            # Share 2 receives:
            # - identical pattern if original pixel is White (lets light through on overlay)
            # - complementary pattern if original pixel is Black (blocks all light on overlay)
            if binary[y, x]:
                share2_arr[y*2:y*2+2, x*2:x*2+2] = choice
            else:
                share2_arr[y*2:y*2+2, x*2:x*2+2] = comp

    # Digital physical optical stacking simulation (Minimum / Boolean AND)
    overlay_arr = np.minimum(share1_arr, share2_arr)

    share1_img = Image.fromarray(share1_arr, mode="L")
    share2_img = Image.fromarray(share2_arr, mode="L")
    overlay_img = Image.fromarray(overlay_arr, mode="L")

    return share1_img, share2_img, overlay_img, (w, h)

def unlock_share_with_pin(share_input, pin: str):
    """
    Given a received Share (typically Share 2) and the Secret PIN,
    regenerates Share 1 using the PIN seed and overlays them to reveal the secret image.
    If the PIN is correct, the secret image is revealed.
    If the PIN is incorrect, the result is completely unintelligible noise.
    """
    if isinstance(share_input, Image.Image):
        share2_im = share_input.copy().convert("L")
    else:
        share2_im = Image.open(share_input).convert("L")
    s_w, s_h = share2_im.size

    w, h = s_w // 2, s_h // 2

    pat_A = np.array([[0, 255], [255, 0]], dtype=np.uint8)
    pat_B = np.array([[255, 0], [0, 255]], dtype=np.uint8)

    rng = get_pin_rng(pin)
    coin = rng.integers(0, 2, size=(h, w))

    share1_arr = np.zeros((s_h, s_w), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            choice = pat_A if coin[y, x] == 0 else pat_B
            share1_arr[y*2:y*2+2, x*2:x*2+2] = choice

    share2_arr = np.array(share2_im)
    unlocked_overlay = np.minimum(share1_arr, share2_arr)

    share1_im = Image.fromarray(share1_arr, mode="L")
    unlocked_im = Image.fromarray(unlocked_overlay, mode="L")
    return unlocked_im, share1_im, (s_w, s_h)

def image_to_base64_data_uri(pil_img, format="PNG"):
    buf = io.BytesIO()
    pil_img.save(buf, format=format)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    return f"data:image/{format.lower()};base64,{encoded}"

def combine_two_shares(share1_input, share2_input):
    """
    Overlays two visual crypto shares.
    """
    if isinstance(share1_input, Image.Image):
        im1 = share1_input.copy().convert("L")
    else:
        im1 = Image.open(share1_input).convert("L")

    if isinstance(share2_input, Image.Image):
        im2 = share2_input.copy().convert("L")
    else:
        im2 = Image.open(share2_input).convert("L")

    # Match sizes if needed
    if im1.size != im2.size:
        im2 = im2.resize(im1.size, Image.Resampling.NEAREST)

    arr1 = np.array(im1)
    arr2 = np.array(im2)
    overlay = np.minimum(arr1, arr2)
    return Image.fromarray(overlay, mode="L")
