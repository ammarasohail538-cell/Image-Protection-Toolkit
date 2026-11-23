from PIL import Image, ImageOps, ExifTags
import os

def _open(path):
    img = Image.open(path)
    # phones store rotation in metadata; apply it now, because saving drops metadata
    return ImageOps.exif_transpose(img)

def _flatten(img):
    # JPEG/BMP have no transparency, so paste transparent images onto a white background
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[3])
        return background
    return img.convert("RGB")

def _save(img, out_path, **kwargs):
    if out_path.lower().endswith((".jpg", ".jpeg", ".bmp")):
        img = _flatten(img)
    img.save(out_path, **kwargs)

def _output_path(path, suffix, ext=None):
    base, original_ext = os.path.splitext(path)
    return base + suffix + (ext or original_ext)

def compress_image(path, quality=70, out_format="JPG"):
    if not 10 <= quality <= 95:
        raise ValueError("Quality must be between 10 and 95.")
    
    img = _open(path)
    out_format = (out_format or "JPG").upper()
    
    if out_format == "WEBP":
        out = _output_path(path, "_compressed", ".webp")
        img.save(out, "WEBP", quality=quality, method=6)
    else:
        img = _flatten(img)
        out = _output_path(path, "_compressed", ".jpg")
        img.save(out, "JPEG", quality=quality, optimize=True, progressive=True)
    return out

def resize_image(path, width, height=None, keep_aspect=True, resample="LANCZOS"):
    if not 16 <= width <= 8000:
        raise ValueError("Width must be between 16 and 8000 pixels.")
    
    img = _open(path)
    orig_w, orig_h = img.size

    resample_methods = {
        "LANCZOS": Image.LANCZOS,
        "BICUBIC": Image.BICUBIC,
        "BILINEAR": Image.BILINEAR,
        "NEAREST": Image.NEAREST
    }
    method = resample_methods.get(str(resample).upper(), Image.LANCZOS)

    if keep_aspect or height is None or height <= 0:
        target_height = max(1, round(orig_h * width / orig_w))
    else:
        if not 16 <= height <= 8000:
            raise ValueError("Height must be between 16 and 8000 pixels.")
        target_height = height

    out = _output_path(path, "_resized")
    resized_img = img.resize((width, target_height), method)
    _save(resized_img, out)
    return out

FORMATS = {
    "JPG": ".jpg",
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
    "BMP": ".bmp",
    "TIFF": ".tiff",
    "ICO": ".ico"
}

def convert_image(path, target):
    target = target.upper()
    if target not in FORMATS:
        raise ValueError("Unsupported format. Allowed: " + ", ".join(FORMATS.keys()))
    
    out_ext = FORMATS[target]
    out = _output_path(path, "_converted", out_ext)
    img = _open(path)

    if target == "ICO":
        # ICO needs small square icon sizes
        img = _flatten(img)
        img.resize((64, 64), Image.LANCZOS).save(out, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    elif target in ("JPG", "JPEG"):
        _save(img, out, format="JPEG", quality=92, optimize=True)
    elif target == "WEBP":
        img.save(out, format="WEBP", quality=90, method=6)
    elif target == "PNG":
        img.save(out, format="PNG", optimize=True)
    else:
        _save(img, out)
    return out

def remove_metadata(path):
    out = _output_path(path, "_clean")
    _save(_open(path), out)  # only pixels are written, so EXIF/GPS data is left behind
    return out

def get_metadata_info(path):
    """Inspects EXIF and image metadata without modifying the file."""
    try:
        img = Image.open(path)
        exif = img.getexif()
        data = {
            "Format": img.format,
            "Mode": img.mode,
            "Dimensions": f"{img.width} x {img.height} px",
            "Has EXIF": bool(exif),
            "Details": {}
        }
        
        if exif:
            for tag_id, value in exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                # avoid large binary dump strings
                if isinstance(value, bytes):
                    value = f"<{len(value)} bytes binary data>"
                elif str(value).strip():
                    data["Details"][tag_name] = str(value)
        
        return data
    except Exception as e:
        return {"Format": "Unknown", "Has EXIF": False, "Error": str(e), "Details": {}}
