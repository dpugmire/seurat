import os, re, json, sqlite3
import argparse
from pathlib import Path
from adios2 import FileReader

import numpy as np
from typing import Optional, Any, Dict, List, Pattern

from sqlite_store import open_sqlite_collection


DEFAULT_CAMPAIGN_PATH = os.getenv("CAMPAIGN_PATH", "kh.aca")


def get_collection(campaign_path: Optional[str] = None):
    return open_sqlite_collection(campaign_path or DEFAULT_CAMPAIGN_PATH)


def clear_collection(campaign_path: Optional[str] = None):
    get_collection(campaign_path).delete_many({})


def _to_simple_string(input: str) -> str:
    return input.translate(str.maketrans("", "", '"'))


def _load_image_association_schema_text(schema_path: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Load an optional image association schema text/YAML file.
    Returns (resolved_path_str, text) or (None, None) when schema_path is not set.
    """
    if not schema_path:
        return (None, None)

    p = Path(schema_path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"Image association schema file not found: {p}")
    if not p.is_file():
        raise ValueError(f"Image association schema path is not a file: {p}")

    text = p.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"Image association schema file is empty: {p}")

    return (str(p), text)


_IMAGE_ASSOC_MODES = {"first_match_wins", "all_matches"}
_IMAGE_ASSOC_UNMATCHED = {"warn", "error", "ignore"}
_IMAGE_SIZE_SEGMENT_RE = re.compile(r"^\d+x\d+$")
# hpc-campaign writes the visualization API into the ACA SQLite database.
# All four tables are needed to map an image item back to its source variables.
_VISUALIZATION_API_TABLES = {
    "visualization_sequence",
    "visualization_variable",
    "visualization_item",
    "dataset",
}
_DISPLAY_ROLE_PRIORITY = {
    "color-by": 0,
    "y-axis": 1,
    "contour-by": 2,
    "streamline-by": 3,
    "variable": 4,
    "primary": 5,
    "x-axis": 90,
}
_NONDISPLAY_ROLES = {"x-axis"}
SCALAR_FIELD_ITEM_TYPE = "SCALAR_FIELD"
SCALAR_FIELD_VARIABLE_TYPE = "scalarField"


def _compile_path_template(path_template: str) -> Pattern[str]:
    """
    Compile a path_template supporting:
      - glob tokens: *, **, ?
      - named captures: {name} -> one path segment ([^/]+)
    """
    template = str(path_template or "").strip()
    if not template:
        raise ValueError("Empty path_template")

    parts: List[str] = ["^"]
    i = 0
    seen_fields = set()

    while i < len(template):
        ch = template[i]
        if ch == "{":
            end = template.find("}", i + 1)
            if end < 0:
                raise ValueError(f"Unclosed '{{' in path_template: {path_template!r}")
            field = template[i + 1 : end].strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field or ""):
                raise ValueError(f"Invalid capture field '{field}' in path_template: {path_template!r}")
            if field in seen_fields:
                parts.append(f"(?P={field})")
            else:
                parts.append(f"(?P<{field}>[^/]+)")
                seen_fields.add(field)
            i = end + 1
            continue

        if ch == "*":
            if (i + 1) < len(template) and template[i + 1] == "*":
                parts.append(".*")
                i += 2
            else:
                parts.append("[^/]*")
                i += 1
            continue

        if ch == "?":
            parts.append("[^/]")
            i += 1
            continue

        parts.append(re.escape(ch))
        i += 1

    parts.append("$")
    return re.compile("".join(parts))


def _load_image_association_schema(schema_file: str, schema_text: str) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "Image association schema requires PyYAML. "
            "Install with: pip install pyyaml"
        ) from e

    try:
        data = yaml.safe_load(schema_text)
    except Exception as e:
        raise ValueError(f"Invalid YAML in schema file {schema_file}: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"Schema root must be a mapping: {schema_file}")

    try:
        schema_version = int(data.get("schema_version", 0))
    except Exception as e:
        raise ValueError(f"schema_version must be an integer in {schema_file}") from e
    if schema_version != 1:
        raise ValueError(f"Unsupported schema_version={schema_version} in {schema_file}; expected 1")

    matching = data.get("matching", {}) or {}
    if not isinstance(matching, dict):
        raise ValueError(f"'matching' must be a mapping in {schema_file}")

    mode = str(matching.get("mode", "first_match_wins") or "first_match_wins").strip()
    if mode not in _IMAGE_ASSOC_MODES:
        raise ValueError(f"Unsupported matching.mode={mode!r} in {schema_file}")

    on_unmatched = str(matching.get("on_unmatched", "warn") or "warn").strip()
    if on_unmatched not in _IMAGE_ASSOC_UNMATCHED:
        raise ValueError(f"Unsupported matching.on_unmatched={on_unmatched!r} in {schema_file}")

    raw_rules = data.get("rules", [])
    if not isinstance(raw_rules, list):
        raise ValueError(f"'rules' must be a list in {schema_file}")

    rules: List[Dict[str, Any]] = []
    for idx, raw in enumerate(raw_rules):
        if not isinstance(raw, dict):
            raise ValueError(f"Rule at index {idx} is not a mapping in {schema_file}")

        rule_id = str(raw.get("id", f"rule_{idx + 1}") or f"rule_{idx + 1}").strip()
        if not rule_id:
            rule_id = f"rule_{idx + 1}"

        try:
            priority = int(raw.get("priority", 1000))
        except Exception as e:
            raise ValueError(f"Rule '{rule_id}' has non-integer priority in {schema_file}") from e

        path_template = str(raw.get("path_template", "") or "").strip()
        if not path_template:
            raise ValueError(f"Rule '{rule_id}' missing path_template in {schema_file}")

        associate = raw.get("associate", {}) or {}
        if not isinstance(associate, dict):
            raise ValueError(f"Rule '{rule_id}' has non-mapping 'associate' in {schema_file}")

        variable_from = str(associate.get("variable_from", "") or "").strip()
        visualization_from = str(associate.get("visualization_from", "") or "").strip()
        fixed_variable = str(associate.get("variable", "") or "").strip()
        fixed_visualization = str(associate.get("visualization", "") or "").strip()

        if not (variable_from or fixed_variable):
            raise ValueError(
                f"Rule '{rule_id}' requires associate.variable_from or associate.variable in {schema_file}"
            )
        if not (visualization_from or fixed_visualization):
            raise ValueError(
                f"Rule '{rule_id}' requires associate.visualization_from or associate.visualization in {schema_file}"
            )

        compiled = _compile_path_template(path_template)
        rules.append(
            {
                "id": rule_id,
                "priority": priority,
                "order": idx,
                "path_template": path_template,
                "pattern": compiled,
                "variable_from": variable_from,
                "visualization_from": visualization_from,
                "fixed_variable": fixed_variable,
                "fixed_visualization": fixed_visualization,
            }
        )

    raw_name_map = data.get("physical_to_logical", {}) or {}
    exact_name_map: Dict[str, str] = {}
    regex_name_map: List[Dict[str, Any]] = []
    if raw_name_map:
        if not isinstance(raw_name_map, dict):
            raise ValueError(f"'physical_to_logical' must be a mapping in {schema_file}")

        # Shorthand form:
        # physical_to_logical:
        #   hll_pressure: pressure
        has_structured_keys = "exact" in raw_name_map or "regex" in raw_name_map
        if not has_structured_keys:
            for physical_name, logical_name in raw_name_map.items():
                p = str(physical_name or "").strip()
                l = str(logical_name or "").strip()
                if not p or not l:
                    continue
                exact_name_map[p] = l
        else:
            raw_exact = raw_name_map.get("exact", {}) or {}
            if not isinstance(raw_exact, dict):
                raise ValueError(f"'physical_to_logical.exact' must be a mapping in {schema_file}")
            for physical_name, logical_name in raw_exact.items():
                p = str(physical_name or "").strip()
                l = str(logical_name or "").strip()
                if not p or not l:
                    continue
                exact_name_map[p] = l

            raw_regex = raw_name_map.get("regex", []) or []
            if not isinstance(raw_regex, list):
                raise ValueError(f"'physical_to_logical.regex' must be a list in {schema_file}")
            for idx, item in enumerate(raw_regex):
                if not isinstance(item, dict):
                    raise ValueError(
                        f"'physical_to_logical.regex[{idx}]' must be a mapping in {schema_file}"
                    )
                pattern_text = str(item.get("pattern", "") or "").strip()
                replace_text = str(item.get("replace", "") or "")
                if not pattern_text:
                    raise ValueError(
                        f"'physical_to_logical.regex[{idx}].pattern' is required in {schema_file}"
                    )
                try:
                    compiled_pattern = re.compile(pattern_text)
                except Exception as e:
                    raise ValueError(
                        f"Invalid regex pattern in physical_to_logical.regex[{idx}] "
                        f"for {schema_file}: {e}"
                    ) from e
                regex_name_map.append(
                    {
                        "pattern": compiled_pattern,
                        "replace": replace_text,
                    }
                )

    rules.sort(key=lambda r: (int(r["priority"]), int(r["order"])))
    return {
        "schema_file": schema_file,
        "schema_version": schema_version,
        "mode": mode,
        "on_unmatched": on_unmatched,
        "rules": rules,
        "physical_to_logical_exact": exact_name_map,
        "physical_to_logical_regex": regex_name_map,
    }


def _map_physical_to_logical_name(physical_name: str, schema: Optional[Dict[str, Any]]) -> str:
    name = str(physical_name or "")
    if not schema:
        return name

    exact_map = schema.get("physical_to_logical_exact", {}) or {}
    mapped = exact_map.get(name, None)
    if isinstance(mapped, str) and mapped:
        return mapped

    regex_rules = schema.get("physical_to_logical_regex", []) or []
    for rule in regex_rules:
        pattern = rule.get("pattern", None)
        replace = str(rule.get("replace", "") or "")
        if pattern is None:
            continue
        if pattern.search(name):
            out = pattern.sub(replace, name, count=1)
            if out:
                return out

    return name


def _display_name_from_physical_name(physical_name: str, schema: Optional[Dict[str, Any]]) -> str:
    mapped = _map_physical_to_logical_name(physical_name, schema)
    if mapped != physical_name:
        return mapped

    parts = [part for part in str(mapped or "").strip("/").split("/") if part]
    if parts:
        return parts[-1]

    return mapped


def _join_variable_id(source_dataset: str, variable_name: str) -> str:
    source = str(source_dataset or "").strip("/")
    name = str(variable_name or "").strip("/")
    if not name:
        return source
    if source and (name == source or name.startswith(source + "/")):
        return name
    return f"{source}/{name}".strip("/") if source else name


def _raw_variable_id(varpath: str, variable_name: str) -> str:
    return _join_variable_id(str(varpath or ""), str(variable_name or ""))


def _image_path_candidates(varpath: str) -> List[str]:
    """
    Build candidate logical paths for matching.
    Some campaigns append '/<width>x<height>' after image.<t>.png.
    """
    p = str(varpath or "").replace("\\", "/").strip("/")
    if not p:
        return []

    candidates = [p]
    parts = p.split("/")
    if parts and _IMAGE_SIZE_SEGMENT_RE.fullmatch(parts[-1]):
        trimmed = "/".join(parts[:-1]).strip("/")
        if trimmed and trimmed not in candidates:
            candidates.append(trimmed)
    return candidates


def _match_image_association(varpath: str, schema: Dict[str, Any]) -> Optional[Dict[str, str]]:
    candidates = _image_path_candidates(varpath)
    if not candidates:
        return None

    mode = str(schema.get("mode", "first_match_wins"))
    matches: List[Dict[str, str]] = []

    for rule in schema.get("rules", []):
        pattern = rule.get("pattern")
        if not pattern:
            continue

        for candidate in candidates:
            m = pattern.match(candidate)
            if not m:
                continue

            groups = m.groupdict()
            variable_name = str(rule.get("fixed_variable", "") or "")
            visualization_name = str(rule.get("fixed_visualization", "") or "")

            variable_from = str(rule.get("variable_from", "") or "")
            if variable_from:
                variable_name = str(groups.get(variable_from, "") or "")

            visualization_from = str(rule.get("visualization_from", "") or "")
            if visualization_from:
                visualization_name = str(groups.get(visualization_from, "") or "")

            matched = {
                "rule_id": str(rule.get("id", "") or ""),
                "candidate": candidate,
                "variable_name": variable_name,
                "visualization_name": visualization_name,
            }
            matches.append(matched)
            break

        if matches and mode == "first_match_wins":
            return matches[0]

    if not matches:
        return None

    if len(matches) > 1:
        first = matches[0]
        for m in matches[1:]:
            if (
                m.get("variable_name", "") != first.get("variable_name", "")
                or m.get("visualization_name", "") != first.get("visualization_name", "")
            ):
                print(
                    "[warn] conflicting image association matches for "
                    f"{varpath!r}; using first rule '{first.get('rule_id', '')}'"
                )
                break
    return matches[0]


def _json_object_or_empty(value: Any) -> Dict[str, Any]:
    """
    Decode JSON metadata stored by hpc-campaign visualization tables.

    The current API stores dictionaries, but this helper is intentionally
    forgiving so older or hand-written metadata does not break ingestion.
    """
    if value is None:
        return {}

    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")

    if not isinstance(value, str):
        return {}

    text = value.strip()
    if not text:
        return {}

    try:
        decoded = json.loads(text)
    except Exception:
        return {"raw": text}

    if isinstance(decoded, dict):
        return decoded
    return {"value": decoded}


def _visualization_short_name(sequence_name: str) -> str:
    """
    Convert a full sequence path to the user-facing visualization token.

    New API sequences are typically named:
      <dataset>/visualizations/<name>

    The viewer should show and filter on <name>, not the entire dataset path.
    """
    name = str(sequence_name or "").strip("/")
    marker = "/visualizations/"
    if marker in name:
        token = name.split(marker, 1)[1].strip("/")
        if token:
            return token

    if "/" in name:
        return name.rsplit("/", 1)[-1]
    return name


def _role_sort_key(role: str) -> tuple[int, str]:
    role_norm = str(role or "").strip().lower()
    return (_DISPLAY_ROLE_PRIORITY.get(role_norm, 50), role_norm)


def _normalize_visualization_variables(variables: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Dedupe visualization variables while preserving all roles per variable.

    A heatmap_contour visualization may reference the same variable twice with
    roles color-by and contour-by. The viewer only needs one document per
    variable, but keeping all roles makes the association inspectable later.
    """
    grouped: Dict[tuple[str, str], Dict[str, Any]] = {}

    for spec in variables:
        name = str(spec.get("name", "") or "").strip()
        if not name:
            continue

        source_dataset = str(spec.get("source_dataset", "") or "").strip()
        role = str(spec.get("role", "") or "variable").strip()
        role_norm = role.lower()
        key = (name, source_dataset)

        entry = grouped.setdefault(
            key,
            {
                "name": name,
                "source_dataset": source_dataset,
                "roles": [],
            },
        )
        if role_norm and role_norm not in entry["roles"]:
            entry["roles"].append(role_norm)

    normalized = list(grouped.values())
    for entry in normalized:
        entry["roles"].sort(key=_role_sort_key)

    normalized.sort(
        key=lambda entry: (
            min((_role_sort_key(role)[0] for role in entry.get("roles", [])), default=50),
            str(entry.get("name", "")),
            str(entry.get("source_dataset", "")),
        )
    )
    return normalized


def _display_visualization_variables(variables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Pick variables that should appear in the viewer's variable list.

    Axis variables like time are metadata for a plot, not usually the data a
    scientist wants to browse. If x-axis is the only role present, keep it as a
    fallback so the image remains reachable.
    """
    display_variables = [
        entry
        for entry in variables
        if set(entry.get("roles", [])) - _NONDISPLAY_ROLES
    ]
    return display_variables or variables


def _load_visualization_api_index(campaign_path: str) -> Dict[str, Dict[str, Any]]:
    """
    Load hpc-campaign visualization API associations from the ACA SQLite tables.

    FileReader exposes image payloads as ADIOS variables, while SCALAR_FIELD
    payloads are stored as embedded ACA blobs. In both cases the semantic
    source-variable association lives in SQLite tables:

      visualization_sequence -> visualization_variable -> visualization_item

    The returned dictionary is keyed by visualization item dataset name. Image
    variables read through ADIOS may append a trailing '/<width>x<height>', so
    image callers should use _image_path_candidates() when looking up entries.
    """
    path = Path(campaign_path).expanduser()
    if not path.exists():
        return {}

    try:
        con = sqlite3.connect(str(path))
        con.row_factory = sqlite3.Row
    except sqlite3.Error as e:
        print(f"[warn] could not open ACA SQLite metadata for visualization API: {e}")
        return {}

    try:
        available_tables = {
            str(row["name"])
            for row in con.execute("select name from sqlite_master where type = 'table'")
        }
        if not _VISUALIZATION_API_TABLES.issubset(available_tables):
            return {}

        scalar_metadata_select = "sf.metadata as scalar_field_metadata"
        scalar_metadata_join = "left join scalar_field as sf on sf.datasetid = item_dataset.rowid"
        if "scalar_field" not in available_tables:
            scalar_metadata_select = "NULL as scalar_field_metadata"
            scalar_metadata_join = ""

        # The visualization API describes payloads semantically, while the
        # payload datasets hold either rendered images or raw scalar fields.
        # This join builds the bridge: sequence -> item dataset, plus sequence
        # -> source vars.
        rows = con.execute(
            f"""
            select
                vs.visid as visid,
                vs.name as sequence_name,
                vs.vistype as visualization_kind,
                vs.metadata as sequence_metadata,
                vi.item_order as item_order,
                vi.item_type as item_type,
                vi.item_uuid as item_uuid,
                vi.metadata as item_metadata,
                item_dataset.name as item_name,
                item_dataset.fileformat as item_fileformat,
                {scalar_metadata_select},
                source_dataset.name as source_dataset,
                vv.variable_name as variable_name,
                vv.role as role
            from visualization_sequence as vs
            join visualization_item as vi on vi.visid = vs.visid
            left join dataset as item_dataset on item_dataset.uuid = vi.item_uuid
            {scalar_metadata_join}
            left join visualization_variable as vv on vv.visid = vs.visid
            left join dataset as source_dataset on source_dataset.rowid = vv.datasetid
            where upper(vi.item_type) in ('IMAGE', 'SCALAR_FIELD')
            order by vs.visid, vi.item_order, vv.variable_name, vv.role
            """
        )

        index: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            item_name = str(row["item_name"] or "").strip("/")
            if not item_name:
                continue

            sequence_name = str(row["sequence_name"] or "")
            # Key by the item dataset path because that is what FileReader gives
            # us for IMAGE variables and what direct SQLite reads use for
            # SCALAR_FIELD payloads.
            entry = index.setdefault(
                item_name,
                {
                    "sequence_id": int(row["visid"]),
                    "sequence_name": sequence_name,
                    "visualization_name": _visualization_short_name(sequence_name),
                    "visualization_kind": str(row["visualization_kind"] or ""),
                    "sequence_metadata": _json_object_or_empty(row["sequence_metadata"]),
                    "item_order": int(row["item_order"]),
                    "item_type": str(row["item_type"] or ""),
                    "item_uuid": str(row["item_uuid"] or ""),
                    "item_metadata": _json_object_or_empty(row["item_metadata"]),
                    "item_dataset_name": item_name,
                    "item_file_format": str(row["item_fileformat"] or ""),
                    "scalar_field_metadata": _json_object_or_empty(row["scalar_field_metadata"]),
                    "variables": [],
                },
            )

            variable_name = str(row["variable_name"] or "").strip()
            if variable_name:
                # variable_name is the simulation variable used by the
                # visualization; source_dataset names the BP/output dataset it
                # came from. role explains how the variable was used.
                entry["variables"].append(
                    {
                        "name": variable_name,
                        "role": str(row["role"] or "variable"),
                        "source_dataset": str(row["source_dataset"] or ""),
                    }
                )

        for entry in index.values():
            variables = _normalize_visualization_variables(entry.get("variables", []))
            entry["variables"] = variables
            entry["display_variables"] = _display_visualization_variables(variables)

        return index
    except sqlite3.Error as e:
        print(f"[warn] could not read visualization API metadata: {e}")
        return {}
    finally:
        con.close()


def _lookup_visualization_api_image(
    varpath: str,
    visualization_api_index: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    # ADIOS may expose image datasets with an added size suffix such as
    # /480x480. Try both the exact path and normalized candidates.
    for candidate in _image_path_candidates(varpath):
        entry = visualization_api_index.get(candidate)
        if entry is not None:
            return entry
    return None


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

    bp_idx = next((i for i, p in enumerate(parts) if p.lower().endswith(".bp")), -1)
    if bp_idx >= 0:
        filename = parts[bp_idx]
        if bp_idx - 1 >= 0:
            casename = parts[bp_idx - 1]
        if bp_idx + 1 < len(parts):
            varname = "/".join(parts[bp_idx + 1 :])
            varpath = "/".join(parts[: bp_idx + 1])

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


def _source_dataset_from_path(varpath: str) -> str:
    """
    Return the logical source dataset path for an ADIOS variable/image path.

    New visualization API entries carry this explicitly. This fallback keeps
    legacy and raw-variable documents queryable through the same field.
    """
    parts = str(varpath or "").strip("/").split("/")
    if not parts or parts == [""]:
        return ""

    bp_idx = next((i for i, p in enumerate(parts) if p.lower().endswith(".bp")), -1)
    if bp_idx >= 0:
        return "/".join(parts[: bp_idx + 1])

    if len(parts) > 1:
        return "/".join(parts[:-1])
    return str(varpath or "").strip("/")


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


def parse_campaign(
    campaign_path: str,
    collection,
    image_association_schema_path: Optional[str] = None,
):
    print("reading: ", campaign_path)
    schema_file, _schema_text = _load_image_association_schema_text(image_association_schema_path)
    image_assoc_schema = None
    if schema_file:
        print("image association schema:", schema_file)
        image_assoc_schema = _load_image_association_schema(schema_file, _schema_text or "")
        print(
            "image association mode:",
            image_assoc_schema.get("mode"),
            "on_unmatched:",
            image_assoc_schema.get("on_unmatched"),
            "rules:",
            len(image_assoc_schema.get("rules", [])),
            "name_map_exact:",
            len(image_assoc_schema.get("physical_to_logical_exact", {})),
            "name_map_regex:",
            len(image_assoc_schema.get("physical_to_logical_regex", [])),
        )
    var_stats = {}
    image_assoc_matched = 0
    image_assoc_unmatched = 0
    visualization_api_matched = 0
    scalar_field_visualization_count = 0
    skipped_non_visual_data = 0
    # Load the visualization API once from SQLite metadata, then use it while
    # walking ADIOS variables. Older campaigns without these tables fall back to
    # schema or legacy path parsing.
    visualization_api_index = _load_visualization_api_index(campaign_path)
    if visualization_api_index:
        print("visualization API item associations:", len(visualization_api_index))

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
            var_type = str(var_type or "variable").strip().lower()

            if var_type == "variable":
                var, file, varpath, producer, casename = extract_file_var(varname)
                source_dataset = varpath
            elif var_type == "image":
                var, file, varpath, producer, casename = extract_file_var_img(varname)
                source_dataset = _source_dataset_from_path(varpath)
            else:
                skipped_non_visual_data += 1
                continue

            physical_var = str(var or "")
            var = _map_physical_to_logical_name(physical_var, image_assoc_schema)
            metadata = varinfo

            #print('Var: ', var, 'varpath: ', varpath)
            ## check if it's a statistical variable (e.g. ends with "_stats") and if so, include min/max in the document for easier querying
            if var_type == 'variable' and '_stats' in varpath :
                data = []
                n = var.rfind('_')
                baseVar, statType = var[:n], var[n+1:]
                print('Stat variable detected: ', var, 'varpath: ', varpath, baseVar, statType)
                data = fr.read(varname)
                if baseVar not in var_stats :
                    var_stats[baseVar] = []
                var_stats[baseVar].append((producer, source_dataset, statType, data[0]))
                continue

            if var_type == "image":
                visualization_name = get_visualization_name(varname)
                association_rule_id = ""
                association_source = "legacy"
                visualization_api_entry = _lookup_visualization_api_image(varpath, visualization_api_index)
                visualization_variables: List[Dict[str, Any]] = []
                # Default legacy association: the image belongs to the variable
                # parsed from its path. The visualization API can replace this
                # with one or more explicit source variables and roles.
                image_variable_records = [
                    {
                        "physical_var": physical_var,
                        "logical_var": var,
                        "variable_id": physical_var,
                        "roles": [],
                        "source_dataset": source_dataset,
                    }
                ]

                if visualization_api_entry is not None:
                    visualization_api_matched += 1
                    # Prefer API metadata over path-derived names. This is what
                    # lets a heatmap/contour/streamline image be attached to the
                    # actual simulation variable instead of the image dataset.
                    visualization_name = str(
                        visualization_api_entry.get("visualization_name", "") or visualization_name
                    )
                    visualization_variables = list(visualization_api_entry.get("variables", []))
                    display_variables = list(visualization_api_entry.get("display_variables", []))
                    if display_variables:
                        # Insert one viewer document per displayed source
                        # variable. Multi-variable visualizations therefore show
                        # up under each meaningful variable in the UI.
                        image_variable_records = []
                        for api_var in display_variables:
                            api_physical_var = str(api_var.get("name", "") or "").strip()
                            if not api_physical_var:
                                continue
                            image_variable_records.append(
                                {
                                    "physical_var": api_physical_var,
                                    "logical_var": _map_physical_to_logical_name(
                                        api_physical_var,
                                        image_assoc_schema,
                                    ),
                                    "variable_id": api_physical_var,
                                    "roles": list(api_var.get("roles", [])),
                                    "source_dataset": str(api_var.get("source_dataset", "") or ""),
                                }
                            )
                    association_source = "visualization-api"

                if image_assoc_schema is not None:
                    assoc = _match_image_association(varpath, image_assoc_schema)
                    if assoc:
                        image_assoc_matched += 1
                        mapped_var = str(assoc.get("variable_name", "") or "").strip()
                        mapped_vis = str(assoc.get("visualization_name", "") or "").strip()

                        if mapped_var:
                            physical_var = mapped_var
                            var = _map_physical_to_logical_name(mapped_var, image_assoc_schema)
                            image_variable_records = [
                                {
                                    "physical_var": physical_var,
                                    "logical_var": var,
                                    "variable_id": physical_var,
                                    "roles": [],
                                    "source_dataset": source_dataset,
                                }
                            ]
                        if mapped_vis:
                            visualization_name = mapped_vis
                        association_rule_id = str(assoc.get("rule_id", "") or "")
                        association_source = "schema"
                    elif visualization_api_entry is None:
                        image_assoc_unmatched += 1
                        action = str(image_assoc_schema.get("on_unmatched", "warn"))
                        msg = (
                            f"image association schema did not match path: {varpath!r} "
                            f"(fallback to legacy path parser)"
                        )
                        if action == "error":
                            raise ValueError(msg)
                        if action == "warn":
                            print("[warn]", msg)
                        association_source = "legacy-unmatched"

                if not image_variable_records:
                    image_variable_records = [
                        {
                            "physical_var": physical_var,
                            "logical_var": var,
                            "variable_id": physical_var,
                            "roles": [],
                            "source_dataset": source_dataset,
                        }
                    ]

                # frame_index from ".../image.000450.png/..."
                frame_index = extract_frame_index_from_varpath(varpath)
                if frame_index is None:
                    # fallback: try to locate the "image.*.png" segment (avoid 480x480)
                    parts = varpath.split("/")
                    candidate = next((p for p in parts if p.startswith("image.") and p.endswith(".png")), "")
                    if candidate:
                        digits = re.findall(r"(\d+)", candidate)
                        frame_index = int(digits[-1]) if digits else None

                base_document = {
                    "campaign_path": campaign_path,
                    "file": file,
                    "visualization_name": visualization_name,
                    "variable_path": varpath,
                    "variable_type": var_type,
                    "producer": producer,
                    "casename": casename,
                    "variable_location": var_location,
                    "metadata": metadata,
                    "movie_cache": 1,
                    "frame_index": int(frame_index) if frame_index is not None else 0,
                    "image_storage": "aca",
                    "association_source": association_source,
                    "association_rule_id": association_rule_id,
                }

                if visualization_api_entry is not None:
                    # Preserve the raw API metadata so downstream UI or
                    # debugging code can inspect the original sequence/item
                    # relationship without reopening the ACA SQLite database.
                    base_document.update(
                        {
                            "visualization_sequence_name": str(
                                visualization_api_entry.get("sequence_name", "") or ""
                            ),
                            "visualization_kind": str(
                                visualization_api_entry.get("visualization_kind", "") or ""
                            ),
                            "visualization_variables": visualization_variables,
                            "visualization_item_order": int(
                                visualization_api_entry.get("item_order", 0) or 0
                            ),
                            "visualization_item_uuid": str(
                                visualization_api_entry.get("item_uuid", "") or ""
                            ),
                            "visualization_sequence_metadata": visualization_api_entry.get(
                                "sequence_metadata",
                                {},
                            ),
                            "visualization_item_metadata": visualization_api_entry.get(
                                "item_metadata",
                                {},
                            ),
                        }
                    )

                for record in image_variable_records:
                    record_source_dataset = str(record.get("source_dataset", "") or source_dataset)
                    document = dict(base_document)
                    # These fields are the normalized viewer-facing association:
                    # which source variable this image represents, which source
                    # dataset it came from, and which visualization roles it had.
                    document.update(
                        {
                            "variable_id": record.get("variable_id")
                            or record["physical_var"],
                            "variable_name": record["logical_var"],
                            "variable_name_physical": record["physical_var"],
                            "source_dataset": record_source_dataset,
                            "visualization_roles": record["roles"],
                            "visualization_source_dataset": record_source_dataset,
                        }
                    )
                    collection.insert_one(document)
                continue
            else:
                # NEW: normalize min/max into top-level numeric fields for querying
                fmin, fmax = _extract_min_max_from_varinfo(varinfo)

                document = {
                    "campaign_path": campaign_path,
                    "file": file,
                    "variable_id": physical_var,
                    "variable_name": var,
                    "variable_name_physical": physical_var,
                    "source_dataset": source_dataset,
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

    for visualization_api_entry in visualization_api_index.values():
        item_type = str(visualization_api_entry.get("item_type", "") or "").strip().upper()
        if item_type != SCALAR_FIELD_ITEM_TYPE:
            continue

        item_name = str(visualization_api_entry.get("item_dataset_name", "") or "").strip("/")
        if not item_name:
            continue

        visualization_name = str(visualization_api_entry.get("visualization_name", "") or "")
        scalar_metadata = dict(visualization_api_entry.get("scalar_field_metadata", {}) or {})
        item_metadata = dict(visualization_api_entry.get("item_metadata", {}) or {})

        display_variables = list(visualization_api_entry.get("display_variables", []))
        scalar_variable_records: List[Dict[str, Any]] = []
        if display_variables:
            for api_var in display_variables:
                api_physical_var = str(api_var.get("name", "") or "").strip()
                if not api_physical_var:
                    continue
                scalar_variable_records.append(
                    {
                        "physical_var": api_physical_var,
                        "logical_var": _map_physical_to_logical_name(
                            api_physical_var,
                            image_assoc_schema,
                        ),
                        "variable_id": api_physical_var,
                        "roles": list(api_var.get("roles", [])),
                        "source_dataset": str(api_var.get("source_dataset", "") or ""),
                    }
                )

        if not scalar_variable_records:
            fallback_var = visualization_name or item_name
            scalar_variable_records = [
                {
                    "physical_var": fallback_var,
                    "logical_var": _map_physical_to_logical_name(fallback_var, image_assoc_schema),
                    "variable_id": fallback_var,
                    "roles": [],
                    "source_dataset": "",
                }
            ]

        fmin = _to_float(scalar_metadata.get("min", None))
        fmax = _to_float(scalar_metadata.get("max", None))

        base_document = {
            "campaign_path": campaign_path,
            "file": "",
            "visualization_name": visualization_name,
            "variable_path": item_name,
            "variable_type": SCALAR_FIELD_VARIABLE_TYPE,
            "payload_type": SCALAR_FIELD_ITEM_TYPE,
            "producer": "",
            "casename": "",
            "variable_location": "local",
            "metadata": scalar_metadata,
            "scalar_field_metadata": scalar_metadata,
            "movie_cache": 1,
            "frame_index": int(visualization_api_entry.get("item_order", 0) or 0),
            "image_storage": "aca",
            "association_source": "visualization-api",
            "association_rule_id": "",
            "visualization_sequence_name": str(visualization_api_entry.get("sequence_name", "") or ""),
            "visualization_kind": str(visualization_api_entry.get("visualization_kind", "") or ""),
            "visualization_variables": list(visualization_api_entry.get("variables", [])),
            "visualization_item_order": int(visualization_api_entry.get("item_order", 0) or 0),
            "visualization_item_uuid": str(visualization_api_entry.get("item_uuid", "") or ""),
            "visualization_item_type": item_type,
            "visualization_sequence_metadata": visualization_api_entry.get("sequence_metadata", {}),
            "visualization_item_metadata": item_metadata,
            "min": fmin,
            "max": fmax,
        }

        for record in scalar_variable_records:
            record_source_dataset = str(record.get("source_dataset", "") or "")
            document = dict(base_document)
            document.update(
                {
                    "variable_id": record.get("variable_id") or record["physical_var"],
                    "variable_name": record["logical_var"],
                    "variable_name_physical": record["physical_var"],
                    "source_dataset": record_source_dataset,
                    "visualization_roles": record["roles"],
                    "visualization_source_dataset": record_source_dataset,
                }
            )
            collection.insert_one(document)
            scalar_field_visualization_count += 1

    print('Add statistics')
    for v in var_stats.items() :
        vname, stats = v
        logical_vname = _map_physical_to_logical_name(vname, image_assoc_schema)
        for stat in stats :
            producer, source_dataset, statType, data = stat
            document = {"campaign_path": campaign_path,
                        "variable_id": vname,
                        "variable_name": logical_vname,
                        "variable_name_physical": vname,
                        "source_dataset": source_dataset,
                        "variable_type": 'statistic',
                        "producer": producer,
                        "statistic_type": statType,
                        "data": data.tolist()}
            collection.insert_one(document)

    if image_assoc_schema is not None:
        print(
            "image association summary:",
            f"matched={image_assoc_matched}",
            f"unmatched={image_assoc_unmatched}",
            f"mode={image_assoc_schema.get('mode')}",
            f"on_unmatched={image_assoc_schema.get('on_unmatched')}",
        )
    if visualization_api_index:
        print(
            "visualization API association summary:",
            f"matched={visualization_api_matched}",
            f"available={len(visualization_api_index)}",
        )
    if scalar_field_visualization_count:
        print("visualization API scalar field associations:", scalar_field_visualization_count)
    if skipped_non_visual_data:
        print("Skipped non-visual datasets:", skipped_non_visual_data)

    print(collection.distinct("campaign_path"))
    print(collection.count_documents({}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("campaign", help="Path to .aca campaign file")
    ap.add_argument("--clear", action="store_true", help="Clear collection before ingest")
    ap.add_argument(
        "--image-association-schema",
        default=None,
        help="Optional path to image association schema text/YAML file.",
    )
    args = ap.parse_args()

    if args.clear:
        clear_collection(args.campaign)

    collection = get_collection(args.campaign)
    parse_campaign(
        args.campaign,
        collection,
        image_association_schema_path=args.image_association_schema,
    )

    coll = get_collection(args.campaign)
    print("Inserted docs:", coll.count_documents({"campaign_path": args.campaign}))
    print("Distinct variable_name:", len(coll.distinct("variable_name")))


if __name__ == "__main__":
    main()
