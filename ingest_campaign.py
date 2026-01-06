import os, io, struct
import argparse
from pymongo import MongoClient
from adios2 import FileReader

import numpy as np
from PIL import Image
from bson.binary import Binary

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


def extract_file_var(input: str) -> tuple[str, str, str, str]:
    parts = input.split("/")
    if len(parts) < 2:
        raise ValueError(f"Invalid file variable format: {input}")
    producer = parts[0]
    varname = parts[-1]
    filename = parts[-2]
    varpath = "/".join(parts[0:-1])
    return (varname, filename, varpath, producer)


def extract_file_var_img(input: str) -> tuple[str, str, str, str]:
    parts = input.split("/")
    if len(parts) < 4:
        raise ValueError(f"Invalid image variable format: {input}")
    producer = parts[0]
    varname = parts[3]
    filename = parts[2]
    varpath = input
    return (varname, filename, varpath, producer)


def get_visualization_name(input: str) -> str:
    parts = input.split("/")
    if "images" in parts:
        idx = parts.index("images")
        return parts[idx + 1]
    return ""

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
        # Convert to raw bytes
        # (handles uint8 / int8 / etc. safely by casting)
        if img.dtype != np.uint8:
            img_u8 = img.astype(np.uint8, copy=False)
        else:
            img_u8 = img

        data = img_u8.tobytes()

        # Optional: validate PNG signature (helps catch wrong data)
        # If this fails but you *know* it's a different format, remove the check.
        if not data.startswith(_PNG_SIG):
            # Not necessarily wrong, but it isn't a PNG file stream.
            # You can still store it, but the browser won't display it as PNG.
            raise ValueError(
                f"1D image payload does not look like PNG bytes. "
                f"len={len(data)} first8={data[:8]!r}"
            )

        return data

    # Case B: pixel arrays -> encode to PNG
    if img.dtype != np.uint8:
        # If data is float in [0,1] or [0,255], you may need scaling.
        # For now, assume it is already 0..255-ish.
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


def parse_campaign(campaign_path: str, collection):
    #collection = get_collection()
    print('reading: ', campaign_path)

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
                var, file, varpath, producer = extract_file_var(varname)
            else:
                var, file, varpath, producer = extract_file_var_img(varname)

            metadata = varinfo

            if var_type == "image":
                #get the bytes.
                img_data = fr.read(varpath)
                png_bytes = array_to_png_bytes(img_data)
                img_width, img_height = png_size(png_bytes)

                visualization_name = get_visualization_name(varname)
                document = {
                    "campaign_path": campaign_path,
                    "file": file,
                    "variable_name": var,
                    "visualization_name": visualization_name,
                    "variable_path": varpath,
                    "variable_type": var_type,
                    "producer": producer,
                    "variable_location": var_location,
                    "metadata": metadata,
                    "movie_cache": 1,
                    "image_bytes": Binary(png_bytes),
                    "image_width": img_width,
                    "image_height": img_height,
                }
            else:
                document = {
                    "campaign_path": campaign_path,
                    "file": file,
                    "variable_name": var,
                    "variable_path": varpath,
                    "variable_type": var_type,
                    "producer": producer,
                    "variable_location": var_location,
                    "metadata": metadata,
                }

            collection.insert_one(document)


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
