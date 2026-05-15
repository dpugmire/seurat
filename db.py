import statistics
from typing import Any, Dict, List, Optional, Tuple

from pymongo.errors import PyMongoError

from media_utils import frames_to_mp4_bytes, mp4_bytes_to_data_uri, png_bytes_to_data_uri
from query_parser import and_filter


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
