"""Seurat's Trame application composition root."""

import argparse
from pathlib import Path

from trame.app import TrameApp

from controllers import attach_controllers
from db import CampaignDb
from ingest_campaign import parse_campaign
from sqlite_store import open_sqlite_collection
from ui import build_ui

from . import module as seurat_module
from .backends import LocalCampaignBackend
from .state import init_state


def _expanded_path(path):
    return str(Path(path).expanduser()) if path else ""


class SeuratApp(TrameApp):
    """Own and connect the server, data model, controllers, and UI."""

    def __init__(
        self,
        campaign_path,
        image_association_schema_path="",
        campaign_schema_path="",
        server=None,
        collection=None,
        db=None,
        controller_attacher=attach_controllers,
        ui_builder=build_ui,
    ):
        super().__init__(server, client_type="vue3")
        self.server.enable_module(seurat_module)

        self.campaign_path = _expanded_path(campaign_path)
        self.image_association_schema_path = _expanded_path(
            image_association_schema_path
        )
        self.campaign_schema_path = _expanded_path(campaign_schema_path)

        self.collection = collection or open_sqlite_collection(self.campaign_path)
        print(f"Seurat sidecar DB: {self.collection.path}")

        self.db = db or CampaignDb(self.collection)
        self.backend = LocalCampaignBackend(self.db)
        init_state(self.state, self.db)

        self.refresh_variable_list = controller_attacher(
            server=self.server,
            backend=self.backend,
            db=self.db,
            collection=self.collection,
            parse_campaign=parse_campaign,
            campaign_path=self.campaign_path,
            image_association_schema_path=self.image_association_schema_path,
            campaign_schema_path=self.campaign_schema_path,
        )
        self.ui = ui_builder(
            self.server,
            self.refresh_variable_list,
            campaign_name=Path(self.campaign_path).name,
        )


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("campaign_path", help="Path to .aca campaign file")
    parser.add_argument(
        "--image-association-schema",
        default="",
        help="Optional path to image association schema text/YAML file.",
    )
    parser.add_argument(
        "--campaign-schema",
        default="",
        help="Optional path to campaign schema YAML; overrides embedded schema.yaml.",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    app = SeuratApp(
        campaign_path=args.campaign_path,
        image_association_schema_path=args.image_association_schema,
        campaign_schema_path=args.campaign_schema,
    )
    app.server.start()
