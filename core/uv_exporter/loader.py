
import os

from core.mesh_data import MeshParseError, UVMesh
from core.parsers.cdae_parser import list_uv_channels as _list_cdae_uv_channels
from core.parsers.cdae_parser import parse_cdae
from core.parsers.dae_parser import list_uv_sets as _list_dae_uv_sets
from core.parsers.dae_parser import parse_dae
from core.parsers.obj_parser import parse_obj
from core.parsers.pim_parser import list_uv_tags as _list_pim_uv_tags
from core.parsers.pim_parser import parse_pim
from core.parsers.scs_converter import (
    ConversionFailedError,
    ConverterNotFoundError,
    convert_pmg_to_pim,
)

SUPPORTED_EXTENSIONS = {".obj", ".dae", ".cdae", ".pim", ".pmg", ".pmd"}

MULTI_CHANNEL_EXTENSIONS = {".dae", ".cdae", ".pim"}

def list_uv_channels(path: str) -> list[tuple[str, str]]:
    ext = os.path.splitext(path)[1].lower()

    if ext == ".dae":
        return [(s, f"UV Set {s}") for s in _list_dae_uv_sets(path)]

    if ext == ".cdae":
        return _list_cdae_uv_channels(path)

    if ext == ".pim":
        return [(tag, tag) for tag in _list_pim_uv_tags(path)]

    return []

def load_mesh(path: str, base_dir: str | None = None, uv_channel: str | None = None) -> UVMesh:
    ext = os.path.splitext(path)[1].lower()

    if ext == ".obj":
        return parse_obj(path)

    if ext == ".dae":
        return parse_dae(path, uv_set=uv_channel)

    if ext == ".cdae":
        return parse_cdae(path, uv_channel=uv_channel)

    if ext == ".pim":
        return parse_pim(path, uv_tag=uv_channel)

    if ext in (".pmg", ".pmd"):
        try:
            pim_path = convert_pmg_to_pim(path, base_dir=base_dir)
        except ConverterNotFoundError as e:
            raise MeshParseError(str(e)) from e
        except ConversionFailedError as e:
            raise MeshParseError(
                f"Automatic conversion from {ext} to .pim failed: {e}"
            ) from e
        mesh = parse_pim(pim_path, uv_tag=uv_channel)
        mesh.warnings.insert(
            0, f"Auto-converted from {os.path.basename(path)} via ConverterPIX."
        )
        return mesh

    raise MeshParseError(
        f"Unsupported file type '{ext}'. Supported: "
        f"{', '.join(sorted(SUPPORTED_EXTENSIONS))}"
    )
