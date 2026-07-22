import argparse
from pathlib import Path

from trame.app import get_server

from ingest_campaign import parse_campaign

from db import CampaignDb
from controllers import attach_controllers
from sqlite_store import open_sqlite_collection
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
    ap.add_argument(
        "--campaign-schema",
        default="",
        help="Optional path to campaign schema YAML; overrides embedded schema.yaml.",
    )
    args = ap.parse_args()

    image_association_schema_path = ""
    if args.image_association_schema:
        image_association_schema_path = str(Path(args.image_association_schema).expanduser())

    campaign_schema_path = ""
    if args.campaign_schema:
        campaign_schema_path = str(Path(args.campaign_schema).expanduser())

    campaign_path = str(Path(args.campaign_path).expanduser())
    collection = open_sqlite_collection(campaign_path)
    print(f"Seurat sidecar DB: {collection.path}")

    server = get_server(client_type="vue3")
    state, ctrl = server.state, server.controller

    db = CampaignDb(collection)

    init_state(state, db)

    refresh_variable_list = attach_controllers(
        server=server,
        db=db,
        collection=collection,
        parse_campaign=parse_campaign,
        campaign_path=campaign_path,
        image_association_schema_path=image_association_schema_path,
        campaign_schema_path=campaign_schema_path,
    )

    build_ui(
        server,
        refresh_variable_list,
        campaign_name=Path(campaign_path).name,
    )

    server.start()


if __name__ == "__main__":
    main()
