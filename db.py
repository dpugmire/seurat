import io
import math
import statistics
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from adios2 import FileReader
from bson.binary import Binary
from PIL import Image, ImageDraw, ImageFont
from pymongo.errors import PyMongoError

from media_utils import frames_to_mp4_bytes, mp4_bytes_to_data_uri, png_bytes_to_data_uri
from query_parser import and_filter


GENERATED_SCALAR_PLOT_VIS = "generated_timeseries"
GENERATED_SCALAR_PLOT_VERSION = 3


def to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        try:
            return float(str(value).strip())
        except Exception:
            return None


class CampaignDb:
    def __init__(self, collection):
        self.collection = collection
        self.ok = True
        self.last_error = ""

        try:
            _ = self.collection.database.client.admin.command("ping")
        except Exception as e:
            self.ok = False
            self.last_error = f"{type(e).__name__}: {e}"

    @staticmethod
    def _metadata_ndims(metadata: Any) -> Optional[int]:
        if not isinstance(metadata, dict):
            return None

        single_value = metadata.get("SingleValue", None)
        if isinstance(single_value, bool) and single_value:
            return 0
        if isinstance(single_value, str) and single_value.strip().lower() in {"true", "1", "yes"}:
            return 0

        raw_shape = metadata.get("Shape", metadata.get("shape", None))
        if raw_shape is None:
            return None

        text = str(raw_shape).strip()
        if not text:
            return None

        cleaned = text
        for ch in "[]()":
            cleaned = cleaned.replace(ch, "")

        parts = [p.strip() for p in cleaned.split(",") if p.strip()]
        if not parts and cleaned:
            parts = [p.strip() for p in cleaned.split() if p.strip()]
        if not parts:
            return None

        dims: List[int] = []
        for p in parts:
            try:
                dims.append(int(float(p)))
            except Exception:
                continue

        if dims:
            if len(dims) == 1 and dims[0] <= 1:
                return 0
            return len(dims)

        return len(parts)

    @staticmethod
    def _variable_filter(variable_id: str, variable_type: Optional[str] = None) -> Dict[str, Any]:
        query: Dict[str, Any] = {"variable_id": variable_id}
        if variable_type:
            query["variable_type"] = variable_type
        return query

    @staticmethod
    def _variable_display_path(doc: Dict[str, Any]) -> str:
        variable_id = str(doc.get("variable_id", "") or "").strip("/")
        source_dataset = str(doc.get("source_dataset", "") or "").strip("/")
        if source_dataset and variable_id.startswith(source_dataset + "/"):
            return variable_id[len(source_dataset) + 1 :]
        return variable_id

    @staticmethod
    def _variable_parent_path(display_path: str) -> str:
        parts = [part for part in str(display_path or "").strip("/").split("/") if part]
        if len(parts) <= 1:
            return ""
        return "/".join(parts[:-1])

    @staticmethod
    def _adios_variable_read_path(doc: Dict[str, Any]) -> str:
        variable_id = str(doc.get("variable_id", "") or "").strip("/")
        source_dataset = str(doc.get("source_dataset", "") or "").strip("/")
        variable_path = str(doc.get("variable_path", "") or "").strip("/")

        if variable_id and source_dataset and variable_id.startswith(source_dataset + "/"):
            return variable_id
        if variable_id and source_dataset:
            return f"{source_dataset}/{variable_id}"
        if variable_id:
            return variable_id
        return variable_path

    @staticmethod
    def _metadata_steps_count(metadata: Any) -> int:
        if not isinstance(metadata, dict):
            return 1
        for key in ("AvailableStepsCount", "Steps", "steps"):
            raw = metadata.get(key, None)
            try:
                count = int(float(str(raw).strip()))
            except Exception:
                continue
            if count > 0:
                return count
        return 1

    @staticmethod
    def _plot_source_label(doc: Dict[str, Any]) -> str:
        source_dataset = str(doc.get("source_dataset", "") or "")
        if source_dataset:
            return source_dataset
        producer = str(doc.get("producer", "") or "")
        casename = str(doc.get("casename", "") or "")
        file_name = str(doc.get("file", "") or "")
        parts = [p for p in (producer, casename, file_name) if p]
        return " / ".join(parts)

    def _classify_variable_group(
        self,
        variable_id: str,
        extra_filter: Optional[Dict[str, Any]] = None,
    ) -> str:
        vis_names = set(self.distinct_visualization_names_for_variable(variable_id, extra_filter=extra_filter))

        if vis_names.intersection({"heatmap", "contour", "heatmap_contour", "streamlines"}):
            return "2D"
        if vis_names and vis_names.issubset({"timeseries"}):
            return "Scalars"

        query = and_filter(self._variable_filter(variable_id, "variable"), extra_filter)
        try:
            one = self.collection.find_one(query, {"_id": 0, "metadata": 1})
        except Exception:
            one = None
        ndims = self._metadata_ndims((one or {}).get("metadata", {}))
        if ndims is not None:
            return "2D" if ndims >= 2 else "Scalars"

        if "timeseries" in vis_names:
            return "Scalars"
        return "2D"

    def distinct_variables(
        self,
        extra_filter: Optional[Dict[str, Any]] = None,
        only_visualized: bool = False,
    ) -> List[Dict[str, str]]:
        if not self.ok:
            return []
        try:
            image_query = and_filter({"variable_type": "image", "visualization_name": {"$ne": ""}}, extra_filter)
            queries = [image_query] if only_visualized else [
                and_filter({"variable_type": "variable"}, extra_filter),
                image_query,
            ]
            proj = {
                "_id": 0,
                "variable_id": 1,
                "variable_name": 1,
                "variable_name_physical": 1,
                "variable_path": 1,
                "source_dataset": 1,
            }

            by_id: Dict[str, Dict[str, str]] = {}
            for query in queries:
                for doc in self.collection.find(query, proj):
                    variable_id = str(doc.get("variable_id", "") or "").strip()
                    if not variable_id:
                        variable_id = str(doc.get("variable_name", "") or "").strip()
                    if not variable_id or variable_id in by_id:
                        continue

                    name = str(doc.get("variable_name", "") or "").strip()
                    if not name:
                        physical = str(doc.get("variable_name_physical", "") or "").strip("/")
                        name = physical.rsplit("/", 1)[-1] if physical else variable_id.rsplit("/", 1)[-1]

                    display_path = self._variable_display_path({**doc, "variable_id": variable_id})
                    by_id[variable_id] = {
                        "id": variable_id,
                        "name": name,
                        "label": name,
                        "path": display_path,
                        "source_dataset": str(doc.get("source_dataset", "") or ""),
                    }

            counts: Dict[str, int] = {}
            for item in by_id.values():
                counts[item["name"]] = counts.get(item["name"], 0) + 1

            variables = list(by_id.values())
            for item in variables:
                if counts.get(item["name"], 0) <= 1:
                    continue
                parent = self._variable_parent_path(item.get("path", ""))
                item["label"] = f"{item['name']} [{parent}]" if parent else item["name"]

            variables.sort(key=lambda item: (item["name"].lower(), item["label"].lower(), item["id"]))
            return variables
        except PyMongoError as e:
            self.last_error = f"{type(e).__name__}: {e}"
            self.ok = False
            return []

    def distinct_variable_names(
        self,
        extra_filter: Optional[Dict[str, Any]] = None,
        only_visualized: bool = False,
    ) -> List[str]:
        return [
            item["id"]
            for item in self.distinct_variables(
                extra_filter=extra_filter,
                only_visualized=only_visualized,
            )
        ]

    def grouped_variable_names(
        self,
        extra_filter: Optional[Dict[str, Any]] = None,
        only_visualized: bool = False,
    ) -> List[Dict[str, Any]]:
        variables = self.distinct_variables(
            extra_filter=extra_filter,
            only_visualized=only_visualized,
        )
        groups: Dict[str, List[Dict[str, str]]] = {"Scalars": [], "2D": []}

        for variable in variables:
            group = self._classify_variable_group(variable["id"], extra_filter=extra_filter)
            if group not in groups:
                group = "2D"
            groups[group].append(variable)

        ordered = []
        if groups["Scalars"]:
            ordered.append({"name": "Scalars", "variables": groups["Scalars"]})
        if groups["2D"]:
            ordered.append({"name": "2D", "variables": groups["2D"]})
        return ordered

    def _image_sources_for_variable(
        self,
        variable_id: str,
        extra_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        base_query: Dict[str, Any] = {
            "variable_id": variable_id,
            "variable_type": "image",
            "visualization_name": {"$ne": ""},
        }
        query = and_filter(base_query, extra_filter)
        proj = {
            "_id": 0,
            "variable_id": 1,
            "variable_path": 1,
            "source_dataset": 1,
            "producer": 1,
            "casename": 1,
            "file": 1,
        }

        cursor = self.collection.find(query, proj).sort(
            [("source_dataset", 1), ("producer", 1), ("casename", 1), ("file", 1)]
        )
        seen = set()
        sources: List[Dict[str, Any]] = []
        for doc in cursor:
            source_dataset = (
                "" if doc.get("source_dataset", None) is None else str(doc.get("source_dataset"))
            )
            producer = "" if doc.get("producer", None) is None else str(doc.get("producer"))
            casename = "" if doc.get("casename", None) is None else str(doc.get("casename"))
            file = "" if doc.get("file", None) is None else str(doc.get("file"))
            key = source_dataset or (producer, casename, file)
            if key in seen:
                continue
            seen.add(key)
            sources.append(
                {
                    "source_dataset": source_dataset,
                    "variable_id": str(doc.get("variable_id", "") or ""),
                    "variable_path": str(doc.get("variable_path", "") or ""),
                    "producer": producer,
                    "casename": casename,
                    "file": file,
                    "min": None,
                    "max": None,
                }
            )
        return sources

    def distinct_visualization_names_for_variable(
        self,
        variable_id: str,
        extra_filter: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        if not self.ok or not variable_id:
            return []
        try:
            base_query: Dict[str, Any] = {
                "variable_id": variable_id,
                "variable_type": "image",
                "visualization_name": {"$ne": ""},
            }
            query = and_filter(base_query, extra_filter)
            names = self.collection.distinct("visualization_name", query)
            names = [n for n in names if isinstance(n, str) and n]
            names.sort()
            return names
        except PyMongoError as e:
            self.last_error = f"{type(e).__name__}: {e}"
            self.ok = False
            return []

    def scalar_plot_candidate(
        self,
        variable_id: str,
        source_filter: Optional[Dict[str, Any]] = None,
        extra_filter: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.ok or not variable_id:
            return {}

        base_query = self._variable_filter(variable_id, "variable")
        query = and_filter(base_query, source_filter) if source_filter else base_query
        query = and_filter(query, extra_filter)
        proj = {
            "_id": 0,
            "campaign_path": 1,
            "file": 1,
            "variable_id": 1,
            "variable_name": 1,
            "variable_name_physical": 1,
            "variable_path": 1,
            "source_dataset": 1,
            "producer": 1,
            "casename": 1,
            "metadata": 1,
            "min": 1,
            "max": 1,
        }

        try:
            doc = self.collection.find_one(query, proj, sort=[("source_dataset", 1), ("_id", 1)])
        except PyMongoError as e:
            self.last_error = f"{type(e).__name__}: {e}"
            self.ok = False
            return {}

        if not doc:
            return {}

        metadata = doc.get("metadata", {})
        ndims = self._metadata_ndims(metadata)
        if ndims is None or ndims > 1:
            return {}

        read_path = self._adios_variable_read_path(doc)
        if not read_path:
            return {}

        source_fields = {
            "source_dataset": str(doc.get("source_dataset", "") or ""),
            "producer": str(doc.get("producer", "") or ""),
            "casename": str(doc.get("casename", "") or ""),
            "file": str(doc.get("file", "") or ""),
        }
        source_filter_out: Dict[str, str] = {"variable_id": variable_id}
        if source_fields["source_dataset"]:
            source_filter_out["source_dataset"] = source_fields["source_dataset"]
        else:
            for key in ("producer", "casename", "file"):
                if source_fields[key]:
                    source_filter_out[key] = source_fields[key]

        return {
            "variable_id": variable_id,
            "variable_name": str(doc.get("variable_name", "") or variable_id),
            "variable_path": read_path,
            "metadata": metadata,
            "source_fields": source_fields,
            "source_filter": source_filter_out,
            "source_label": self._plot_source_label(doc),
            "min": doc.get("min", None),
            "max": doc.get("max", None),
        }

    @staticmethod
    def _draw_line_plot_png(
        x_values: Any,
        y_values: Any,
        title: str,
        x_label: str,
        y_label: str,
        width: int = 900,
        height: int = 750,
    ) -> bytes:
        x = np.asarray(x_values, dtype=float).reshape(-1)
        y = np.asarray(y_values, dtype=float).reshape(-1)
        n = min(int(x.size), int(y.size))
        if n <= 0:
            raise ValueError("No finite values available for plot")
        x = x[:n]
        y = y[:n]
        mask = np.isfinite(x) & np.isfinite(y)
        x = x[mask]
        y = y[mask]
        if x.size <= 0:
            raise ValueError("No finite values available for plot")

        width = max(360, int(width))
        height = max(300, int(height))
        img = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(img)
        label_font = CampaignDb._plot_font(28)
        tick_font = CampaignDb._plot_font(26)

        left = 106
        right = 38
        top = 72
        bottom = 96
        plot_w = max(1, width - left - right)
        plot_h = max(1, height - top - bottom)

        xmin = float(np.min(x))
        xmax = float(np.max(x))
        ymin = float(np.min(y))
        ymax = float(np.max(y))
        if math.isclose(xmin, xmax):
            xmin -= 0.5
            xmax += 0.5
        if math.isclose(ymin, ymax):
            pad = abs(ymin) * 0.05 if ymin else 1.0
            ymin -= pad
            ymax += pad
        else:
            pad = (ymax - ymin) * 0.06
            ymin -= pad
            ymax += pad

        def sx(value: float) -> float:
            return left + ((float(value) - xmin) / (xmax - xmin)) * plot_w

        def sy(value: float) -> float:
            return top + plot_h - ((float(value) - ymin) / (ymax - ymin)) * plot_h

        def fit_text(text: str, font: Any, max_width: float) -> str:
            text = str(text or "")
            if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
                return text
            ellipsis = "..."
            while text and draw.textbbox((0, 0), text + ellipsis, font=font)[2] > max_width:
                text = text[:-1]
            return text + ellipsis if text else ellipsis

        draw.rectangle([left, top, left + plot_w, top + plot_h], outline="#3f3f3f", width=2)
        for i in range(5):
            frac = i / 4.0
            gx = left + frac * plot_w
            gy = top + frac * plot_h
            draw.line([(gx, top), (gx, top + plot_h)], fill="#eeeeee", width=2)
            draw.line([(left, gy), (left + plot_w, gy)], fill="#eeeeee", width=2)

            xv = xmin + frac * (xmax - xmin)
            yv = ymax - frac * (ymax - ymin)
            x_text = f"{xv:.3g}"
            y_text = f"{yv:.3g}"
            x_bbox = draw.textbbox((0, 0), x_text, font=tick_font)
            y_bbox = draw.textbbox((0, 0), y_text, font=tick_font)
            draw.text(
                (gx - (x_bbox[2] - x_bbox[0]) / 2, top + plot_h + 14),
                x_text,
                fill="#333333",
                font=tick_font,
            )
            draw.text(
                (left - 16 - (y_bbox[2] - y_bbox[0]), gy - (y_bbox[3] - y_bbox[1]) / 2),
                y_text,
                fill="#333333",
                font=tick_font,
            )

        points = [(sx(xv), sy(yv)) for xv, yv in zip(x, y)]
        if len(points) == 1:
            px, py = points[0]
            draw.ellipse([px - 5, py - 5, px + 5, py + 5], fill="#1565c0")
        else:
            draw.line(points, fill="#1565c0", width=6)
            for px, py in points[:: max(1, len(points) // 60)]:
                draw.ellipse([px - 3, py - 3, px + 3, py + 3], fill="#1565c0")

        source_line = fit_text(title, label_font, plot_w)
        if source_line:
            draw.text((left, 24), source_line, fill="#555555", font=label_font)
        x_bbox = draw.textbbox((0, 0), x_label, font=label_font)
        draw.text(
            (left + plot_w / 2 - (x_bbox[2] - x_bbox[0]) / 2, height - 46),
            x_label,
            fill="#333333",
            font=label_font,
        )

        out = io.BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()

    @staticmethod
    def _plot_font(size: int):
        for path in (
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        ):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
        try:
            return ImageFont.load_default(size=size)
        except Exception:
            return ImageFont.load_default()

    @staticmethod
    def _read_plot_series(campaign_path: str, variable_path: str, metadata: Any, source_dataset: str) -> Tuple[np.ndarray, np.ndarray, str]:
        steps_count = CampaignDb._metadata_steps_count(metadata)
        ndims = CampaignDb._metadata_ndims(metadata)
        with FileReader(campaign_path) as fr:
            kwargs = {"step_selection": [0, steps_count]} if steps_count > 1 else {}
            y_raw = np.asarray(fr.read(variable_path, **kwargs), dtype=float)

            if ndims == 0:
                y = y_raw.reshape(-1)
                x = np.arange(y.size, dtype=float)
                x_label = "step"
                time_path = f"{source_dataset}/time" if source_dataset else ""
                if time_path:
                    try:
                        t_raw = np.asarray(fr.read(time_path, **kwargs), dtype=float).reshape(-1)
                        if t_raw.size == y.size:
                            x = t_raw
                            x_label = "time"
                    except Exception:
                        pass
                return x, y, x_label

            if y_raw.ndim >= 2:
                y = np.asarray(y_raw[-1], dtype=float).reshape(-1)
            else:
                y = y_raw.reshape(-1)
            x = np.arange(y.size, dtype=float)
            return x, y, "index"

    def get_or_create_generated_scalar_plot_tile(
        self,
        campaign_path: str,
        variable_id: str,
        source_filter: Optional[Dict[str, Any]] = None,
        extra_filter: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        candidate = self.scalar_plot_candidate(variable_id, source_filter=source_filter, extra_filter=extra_filter)
        if not candidate:
            return {}

        cache_query: Dict[str, Any] = {
            "campaign_path": campaign_path,
            "variable_id": variable_id,
            "variable_type": "image",
            "visualization_name": GENERATED_SCALAR_PLOT_VIS,
            "generated_plot_version": GENERATED_SCALAR_PLOT_VERSION,
            "association_source": "generated-scalar-plot",
        }
        source_fields = dict(candidate.get("source_fields", {}) or {})
        if source_fields.get("source_dataset"):
            cache_query["source_dataset"] = source_fields["source_dataset"]
        else:
            for key in ("producer", "casename", "file"):
                if source_fields.get(key):
                    cache_query[key] = source_fields[key]

        proj = {
            "_id": 1,
            "source_dataset": 1,
            "variable_id": 1,
            "variable_name": 1,
            "producer": 1,
            "casename": 1,
            "file": 1,
            "visualization_name": 1,
            "image_bytes": 1,
            "status": 1,
            "note": 1,
        }

        try:
            cached = self.collection.find_one(and_filter(cache_query, extra_filter), proj)
        except PyMongoError as e:
            self.last_error = f"{type(e).__name__}: {e}"
            self.ok = False
            cached = None

        if cached and cached.get("image_bytes"):
            return {
                "variable_name": str(cached.get("variable_name", "") or candidate["variable_name"]),
                "variable_id": variable_id,
                "visualization_name": GENERATED_SCALAR_PLOT_VIS,
                "selected_visualization": GENERATED_SCALAR_PLOT_VIS,
                "visualization_options": [GENERATED_SCALAR_PLOT_VIS],
                "source_dataset": str(cached.get("source_dataset", "") or ""),
                "producer": str(cached.get("producer", "") or ""),
                "casename": str(cached.get("casename", "") or ""),
                "file": str(cached.get("file", "") or ""),
                "src": png_bytes_to_data_uri(bytes(cached.get("image_bytes"))),
                "media_type": "image",
                "status": "ok",
                "note": str(cached.get("note", "") or "generated scalar plot"),
            }

        x, y, x_label = self._read_plot_series(
            campaign_path,
            str(candidate.get("variable_path", "") or ""),
            candidate.get("metadata", {}),
            str(source_fields.get("source_dataset", "") or ""),
        )
        source_label = str(candidate.get("source_label", "") or "")
        png_bytes = self._draw_line_plot_png(
            x,
            y,
            source_label,
            x_label,
            str(candidate.get("variable_name", "") or variable_id),
        )

        doc = {
            **cache_query,
            "variable_name": str(candidate.get("variable_name", "") or variable_id),
            "variable_name_physical": variable_id,
            "variable_path": str(candidate.get("variable_path", "") or ""),
            "source_dataset": str(source_fields.get("source_dataset", "") or ""),
            "producer": str(source_fields.get("producer", "") or ""),
            "casename": str(source_fields.get("casename", "") or ""),
            "file": str(source_fields.get("file", "") or ""),
            "variable_location": "generated",
            "metadata": candidate.get("metadata", {}),
            "movie_cache": 1,
            "frame_index": 0,
            "image_width": 900,
            "image_height": 750,
            "image_bytes": Binary(png_bytes),
            "media_type": "image",
            "status": "ok",
            "note": "generated scalar plot",
            "min": candidate.get("min", None),
            "max": candidate.get("max", None),
        }
        try:
            self.collection.insert_one(doc)
        except PyMongoError as e:
            self.last_error = f"{type(e).__name__}: {e}"
            self.ok = False

        return {
            "variable_name": doc["variable_name"],
            "variable_id": variable_id,
            "visualization_name": GENERATED_SCALAR_PLOT_VIS,
            "selected_visualization": GENERATED_SCALAR_PLOT_VIS,
            "visualization_options": [GENERATED_SCALAR_PLOT_VIS],
            "source_dataset": doc["source_dataset"],
            "producer": doc["producer"],
            "casename": doc["casename"],
            "file": doc["file"],
            "src": png_bytes_to_data_uri(png_bytes),
            "media_type": "image",
            "status": "ok",
            "note": "generated scalar plot",
        }

    def variable_min_max_summary(
        self,
        variable_id: str,
        extra_filter: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.ok or not variable_id:
            return {}

        base_query = self._variable_filter(variable_id, "variable")
        query = and_filter(base_query, extra_filter)

        proj = {
            "_id": 0,
            "variable_id": 1,
            "source_dataset": 1,
            "producer": 1,
            "casename": 1,
            "file": 1,
            "variable_name": 1,
            "variable_name_physical": 1,
            "variable_path": 1,
            "metadata": 1,
            "Min": 1,
            "Max": 1,
            "min": 1,
            "max": 1,
        }

        try:
            source_docs = list(self.collection.find(query, proj))

            mins: List[float] = []
            maxs: List[float] = []
            num_sources = 0
            sources: List[Dict[str, Any]] = []

            for doc in source_docs:
                num_sources += 1

                fmin = to_float(doc.get("min", None))
                fmax = to_float(doc.get("max", None))

                if fmin is None or fmax is None:
                    md = doc.get("metadata", {})
                    if not isinstance(md, dict):
                        md = {}
                    raw_min = md.get("Min", doc.get("Min", None))
                    raw_max = md.get("Max", doc.get("Max", None))
                    fmin = to_float(raw_min) if fmin is None else fmin
                    fmax = to_float(raw_max) if fmax is None else fmax

                if (fmin is not None) and (fmax is not None):
                    mins.append(fmin)
                    maxs.append(fmax)

                sources.append(
                    {
                        "source_dataset": (
                            ""
                            if doc.get("source_dataset", None) is None
                            else str(doc.get("source_dataset"))
                        ),
                        "variable_id": "" if doc.get("variable_id", None) is None else str(doc.get("variable_id")),
                        "producer": "" if doc.get("producer", None) is None else str(doc.get("producer")),
                        "casename": "" if doc.get("casename", None) is None else str(doc.get("casename")),
                        "file": "" if doc.get("file", None) is None else str(doc.get("file")),
                        "variable_path": "" if doc.get("variable_path", None) is None else str(doc.get("variable_path")),
                        "min": fmin,
                        "max": fmax,
                    }
                )

            valid = len(mins)

            # Stage 2 support: if this variable has no ADIOS variable docs, but does
            # have image docs, return source rows with n/a min/max so the viewer can
            # still browse visualizations.
            if num_sources == 0:
                image_sources = self._image_sources_for_variable(variable_id, extra_filter=extra_filter)
                return {
                    "variable": variable_id,
                    "num_sources": len(image_sources),
                    "global_min": None,
                    "global_max": None,
                    "mean_min": None,
                    "mean_max": None,
                    "median_min": None,
                    "median_max": None,
                    "sources": image_sources,
                }

            return {
                "variable": variable_id,
                "num_sources": num_sources,
                "global_min": min(mins) if valid else None,
                "global_max": max(maxs) if valid else None,
                "mean_min": statistics.fmean(mins) if valid else None,
                "mean_max": statistics.fmean(maxs) if valid else None,
                "median_min": statistics.median(mins) if valid else None,
                "median_max": statistics.median(maxs) if valid else None,
                "sources": sources,
            }

        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            self.ok = False
            return {}

    def get_movie_frames_for_stream(
        self,
        variable_id: str,
        visualization_name: str,
        producer: str,
        casename: str,
        file: str = "",
        source_dataset: str = "",
        extra_filter: Optional[Dict[str, Any]] = None,
        limit_frames: int = 240,
    ) -> Tuple[List[bytes], int]:
        if not self.ok or not variable_id:
            return ([], 0)

        base_query: Dict[str, Any] = {
            "variable_id": variable_id,
            "variable_type": "image",
            "visualization_name": visualization_name,
        }
        if source_dataset:
            base_query["source_dataset"] = source_dataset
        else:
            base_query["producer"] = producer
            base_query["casename"] = casename
            if file:
                base_query["file"] = file

        query = and_filter(base_query, extra_filter)

        proj = {"_id": 1, "image_bytes": 1, "frame_index": 1}

        try:
            total = int(self.collection.count_documents(query))
            cursor = (
                self.collection.find(query, proj)
                .sort([("frame_index", 1), ("_id", 1)])
                .limit(int(limit_frames))
            )

            frames: List[bytes] = []
            for doc in cursor:
                img = doc.get("image_bytes", None)
                if img:
                    try:
                        frames.append(bytes(img))
                    except Exception:
                        continue

            return (frames, total)

        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            self.ok = False
            return ([], 0)

    def get_first_movie_tiles_for_variable(
        self,
        variable_id: str,
        extra_filter: Optional[Dict[str, Any]] = None,
        limit: int = 4,
        limit_frames: int = 240,
        fps: int = 24,
    ) -> List[Dict[str, Any]]:
        if not self.ok or not variable_id:
            return []

        base_query: Dict[str, Any] = {
            "variable_id": variable_id,
            "variable_type": "image",
            "visualization_name": {"$ne": ""},
        }
        query = and_filter(base_query, extra_filter)

        proj = {
            "_id": 1,
            "source_dataset": 1,
            "variable_id": 1,
            "variable_name": 1,
            "producer": 1,
            "casename": 1,
            "file": 1,
            "visualization_name": 1,
        }

        try:
            cursor = self.collection.find(query, proj).sort([("_id", 1)])

            seen = set()
            tiles: List[Dict[str, Any]] = []

            for doc in cursor:
                vis = str(doc.get("visualization_name", "") or "")
                source_dataset = str(doc.get("source_dataset", "") or "")
                producer = str(doc.get("producer", "") or "")
                casename = str(doc.get("casename", "") or "")
                file = str(doc.get("file", "") or "")

                if not vis:
                    continue

                key = (vis, source_dataset) if source_dataset else (vis, producer, casename, file)
                if key in seen:
                    continue
                seen.add(key)

                frames, total = self.get_movie_frames_for_stream(
                    variable_id,
                    visualization_name=vis,
                    producer=producer,
                    casename=casename,
                    file=file,
                    source_dataset=source_dataset,
                    extra_filter=extra_filter,
                    limit_frames=limit_frames,
                )

                src = ""
                media_type = "video"
                status = "ok"
                note = ""

                if not frames:
                    status = "no-frames"
                    note = "no frames"
                elif len(frames) == 1:
                    src = png_bytes_to_data_uri(frames[0])
                    media_type = "image"
                    note = "1 frame (rendered as image)"
                else:
                    try:
                        mp4 = frames_to_mp4_bytes(frames, fps=fps)
                        src = mp4_bytes_to_data_uri(mp4)
                        note = f"{len(frames)} of {total} frames" if total > len(frames) else f"{len(frames)} frames"
                    except Exception as e:
                        status = "build-failed"
                        note = f"{type(e).__name__}: {e}"
                        src = ""

                tiles.append(
                    {
                        "variable_name": str(doc.get("variable_name", "") or variable_id),
                        "variable_id": variable_id,
                        "visualization_name": vis,
                        "source_dataset": source_dataset,
                        "producer": producer,
                        "casename": casename,
                        "file": file,
                        "src": src,
                        "media_type": media_type,
                        "status": status,
                        "note": note,
                    }
                )

                if len(tiles) >= int(limit):
                    break

            return tiles

        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            self.ok = False
            return []
