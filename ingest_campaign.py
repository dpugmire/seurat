import os, io, struct, re
import argparse
from pymongo import MongoClient
from adios2 import FileReader

import numpy as np
from PIL import Image
from bson.binary import Binary
from typing import Optional, Any

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "catnip_campaigns")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "campaign_entries")


def get_collection():
    client = MongoClient(MONGO_URI)
    return client[MONGO_DB][MONGO_COLLECTION]


def clear_collection():
    get_collection().delete_many({})


def _to_simple_string(input: str) -> str:
    return input.translate(str.maketrans("", "", '"'))


def _to_float(value: Any) -> Optional[float]:
    """
    Best-effort conversion to float.
    Handles ADIOS metadata values that may be strings.
    Returns None if conversion fails.
    """
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        try:
            return float(str(value).strip())
        except Exception:
            return None


def extract_file_var(input: str) -> tuple[str, str, str, str, str]:
    parts = input.split("/")
    if len(parts) < 2:
        raise ValueError(f"Invalid file variable format: {input}")
    producer = parts[0]
    casename = parts[1]
    varname = parts[-1]
    filename = parts[-2]
    varpath = "/".join(parts[0:-1])
    return (varname, filename, varpath, producer, casename)


def extract_file_var_img(input: str) -> tuple[str, str, str, str, str]:
    parts = input.split("/")
    if len(parts) < 4:
        raise ValueError(f"Invalid image variable format: {input}")

    producer, casename, filename, varname, _ = _parse_image_path_components(parts)
    varpath = input
    return (varname, filename, varpath, producer, casename)


def get_visualization_name(input: str) -> str:
    parts = input.split("/")
    _, _, _, _, visualization_name = _parse_image_path_components(parts)
    return visualization_name


def _parse_image_path_components(parts: list[str]) -> tuple[str, str, str, str, str]:
    """
    Parse campaign image logical paths by anchoring on the .bp segment.

    Expected robust layout:
      <producer>/<optional-casename>/.../<file.bp>/<var>/images/<vis>/<image>.png[/<size>]
    """
    producer = parts[0] if parts else ""
    casename = parts[1] if len(parts) > 1 else ""
    filename = parts[2] if len(parts) > 2 else ""
    varname = parts[3] if len(parts) > 3 else ""
    visualization_name = ""

    bp_idx = next((i for i, p in enumerate(parts) if p.lower().endswith(".bp")), -1)
    if bp_idx >= 0:
        filename = parts[bp_idx]
        if bp_idx - 1 >= 0:
            casename = parts[bp_idx - 1]
        if bp_idx + 1 < len(parts):
            varname = parts[bp_idx + 1]

        if "images" in parts[bp_idx + 1 :]:
            rel_idx = parts[bp_idx + 1 :].index("images")
            images_idx = bp_idx + 1 + rel_idx
            if images_idx + 1 < len(parts):
                visualization_name = parts[images_idx + 1]
        elif bp_idx + 2 < len(parts):
            candidate = parts[bp_idx + 2]
            if not candidate.lower().endswith(".png") and not re.fullmatch(r"\d+x\d+", candidate):
                visualization_name = candidate

    return producer, casename, filename, varname, visualization_name


def png_size(png_bytes: bytes) -> tuple[int, int]:
    # assumes valid PNG
    width, height = struct.unpack(">II", png_bytes[16:24])
    return int(width), int(height)


_PNG_SIG = b"\x89PNG\r\n\x1a\n"


def array_to_png_bytes(img: np.ndarray) -> bytes:
    """
    Accepts either:
      - Pixel arrays: (H,W), (H,W,3), (H,W,4) -> encodes to PNG
      - Already-encoded PNG bytes: (N,) uint8/int8 -> returns bytes directly
    """
    if img is None:
        raise ValueError("img is None")

    # If ADIOS returns a scalar or list, normalize
    img = np.asarray(img)

    # Case A: 1D "byte stream" (likely already PNG bytes)
    if img.ndim == 1:
        if img.dtype != np.uint8:
            img_u8 = img.astype(np.uint8, copy=False)
        else:
            img_u8 = img

        data = img_u8.tobytes()

        if not data.startswith(_PNG_SIG):
            raise ValueError(
                f"1D image payload does not look like PNG bytes. "
                f"len={len(data)} first8={data[:8]!r}"
            )

        return data

    # Case B: pixel arrays -> encode to PNG
    if img.dtype != np.uint8:
        img = np.clip(img, 0, 255).astype(np.uint8)

    if img.ndim == 2:
        mode = "L"
    elif img.ndim == 3 and img.shape[2] == 3:
        mode = "RGB"
    elif img.ndim == 3 and img.shape[2] == 4:
        mode = "RGBA"
    else:
        raise ValueError(f"Unexpected image array shape: {img.shape}, dtype={img.dtype}")

    pil = Image.fromarray(img, mode=mode)
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return buf.getvalue()


# Match ".../image.000450.png/..." and capture 000450
_FRAME_RE = re.compile(r"(?:^|/)(?:image)\.(\d+)\.png(?:/|$)")


def extract_frame_index_from_varpath(varpath: str) -> Optional[int]:
    if not varpath:
        return None
    m = _FRAME_RE.search(varpath)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _extract_min_max_from_varinfo(varinfo: Any) -> tuple[Optional[float], Optional[float]]:
    """
    ADIOS available_variables() returns a dict of metadata values.
    Typically 'Min'/'Max' appear as strings.
    We normalize those into numeric min/max fields for DB querying.
    """
    if not isinstance(varinfo, dict):
        return (None, None)

    # Primary: top-level keys from ADIOS variable info
    raw_min = varinfo.get("Min", None)
    raw_max = varinfo.get("Max", None)

    # Some pipelines might store these under different capitalization.
    if raw_min is None:
        raw_min = varinfo.get("min", None)
    if raw_max is None:
        raw_max = varinfo.get("max", None)

    fmin = _to_float(raw_min)
    fmax = _to_float(raw_max)
    return (fmin, fmax)


def parse_campaign(campaign_path: str, collection):
    print("reading: ", campaign_path)

    with FileReader(campaign_path) as fr:
        vars_dict = fr.available_variables()
        attrs_dict = fr.available_attributes()

        for varname, varinfo in vars_dict.items():
            type_key = varname + "/__dataset_type__"
            loc_key = varname + "/__dataset_location__"

            var_type = "variable"
            var_location = "local"
            if type_key in attrs_dict:
                var_type = _to_simple_string(attrs_dict[type_key]["Value"])
            if loc_key in attrs_dict:
                var_location = _to_simple_string(attrs_dict[loc_key]["Value"])

            if var_type == "variable":
                var, file, varpath, producer, casename = extract_file_var(varname)
            else:
                var, file, varpath, producer, casename = extract_file_var_img(varname)

            metadata = varinfo

            if var_type == "image":
                img_data = fr.read(varpath)
                png_bytes = array_to_png_bytes(img_data)
                img_width, img_height = png_size(png_bytes)

                visualization_name = get_visualization_name(varname)

                # frame_index from ".../image.000450.png/..."
                frame_index = extract_frame_index_from_varpath(varpath)
                if frame_index is None:
                    # fallback: try to locate the "image.*.png" segment (avoid 480x480)
                    parts = varpath.split("/")
                    candidate = next((p for p in parts if p.startswith("image.") and p.endswith(".png")), "")
                    if candidate:
                        digits = re.findall(r"(\d+)", candidate)
                        frame_index = int(digits[-1]) if digits else None

                document = {
                    "campaign_path": campaign_path,
                    "file": file,
                    "variable_name": var,
                    "visualization_name": visualization_name,
                    "variable_path": varpath,
                    "variable_type": var_type,
                    "producer": producer,
                    "casename": casename,
                    "variable_location": var_location,
                    "metadata": metadata,
                    "movie_cache": 1,
                    "frame_index": int(frame_index) if frame_index is not None else 0,
                    "image_bytes": Binary(png_bytes),
                    "image_width": img_width,
                    "image_height": img_height,
                }
            else:
                # NEW: normalize min/max into top-level numeric fields for querying
                fmin, fmax = _extract_min_max_from_varinfo(varinfo)

                document = {
                    "campaign_path": campaign_path,
                    "file": file,
                    "variable_name": var,
                    "variable_path": varpath,
                    "variable_type": var_type,
                    "producer": producer,
                    "casename": casename,
                    "variable_location": var_location,
                    "metadata": metadata,
                    # These fields enable queries like: min > 1.0, max <= 10
                    # They will be absent/None if not available.
                    "min": fmin,
                    "max": fmax,
                }

            collection.insert_one(document)

    print(collection.distinct("campaign_path"))
    print(collection.count_documents({}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("campaign", help="Path to .aca campaign file")
    ap.add_argument("--clear", action="store_true", help="Clear collection before ingest")
    args = ap.parse_args()

    if args.clear:
        clear_collection()

    collection = get_collection()
    parse_campaign(args.campaign, collection)

    coll = get_collection()
    print("Inserted docs:", coll.count_documents({"campaign_path": args.campaign}))
    print("Distinct variable_name:", len(coll.distinct("variable_name")))


if __name__ == "__main__":
    main()
