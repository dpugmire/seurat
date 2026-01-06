import os
import argparse
from pymongo import MongoClient
from adios2 import FileReader

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

    parse_campaign(args.campaign)

    coll = get_collection()
    print("Inserted docs:", coll.count_documents({"campaign_path": args.campaign}))
    print("Distinct variable_name:", len(coll.distinct("variable_name")))


if __name__ == "__main__":
    main()
