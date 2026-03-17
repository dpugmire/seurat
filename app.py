import argparse
from pathlib import Path

from pymongo import MongoClient
from trame.app import get_server

from ingest_campaign import parse_campaign

from config import MONGO_COLLECTION, MONGO_DB, MONGO_URI
from db import CampaignDb
from controllers import attach_controllers
from state_init import init_state
from ui import build_ui


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("campaign_path", help="Path to .aca campaign file")
    ap.add_argument(
        "--image-association-schema",
        default="",
        help="Optional path to image association schema text/YAML file.",
    )
    args = ap.parse_args()

    schema_path = ""
    if args.image_association_schema:
        schema_path = str(Path(args.image_association_schema).expanduser())

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=1500)
    collection = client[MONGO_DB][MONGO_COLLECTION]

    server = get_server(client_type="vue3")
    state, ctrl = server.state, server.controller

    db = CampaignDb(collection)

    init_state(state, db)

    refresh_variable_list = attach_controllers(
        server=server,
        db=db,
        collection=collection,
        parse_campaign=parse_campaign,
        campaign_path=args.campaign_path,
        image_association_schema_path=schema_path,
    )

    build_ui(
        server,
        refresh_variable_list,
        campaign_name=Path(args.campaign_path).name,
    )

    server.start()


if __name__ == "__main__":
    main()
