from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from core.model_preview import material as material_mod


class _Job(QRunnable):
    def __init__(self, owner: "PreviewJobs", kind: str, token: int, fn: Callable):
        super().__init__()
        self.setAutoDelete(True)
        self._owner, self._kind, self._token, self._fn = owner, kind, token, fn

    def run(self):
        if not self._owner.is_current(self._kind, self._token):
            return
        try:
            result, error = self._fn(), ""
        except Exception as e:
            import traceback
            traceback.print_exc()
            result, error = None, f"{type(e).__name__}: {e}"
        self._owner.finished.emit(self._kind, self._token, result, error)


class PreviewJobs(QObject):
    finished = Signal(str, int, object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._tokens: dict[str, int] = {}

    def submit(self, kind: str, fn: Callable) -> int:
        token = self._tokens.get(kind, 0) + 1
        self._tokens[kind] = token
        self._pool.start(_Job(self, kind, token, fn))
        return token

    def is_current(self, kind: str, token: int) -> bool:
        return self._tokens.get(kind) == token

    def cancel(self, kind: str) -> None:
        self._tokens[kind] = self._tokens.get(kind, 0) + 1


def texture_job(stage, resolve, path, full, load_image, cached):
    if stage:
        files = material_mod.stage_files(stage, resolve)
        stamp = material_mod.stage_stamp(files)
        if cached is not None and cached[0] == stamp and cached[1] == full:
            cached_materials = cached[2]
            if isinstance(cached_materials, material_mod.PreviewMaterialSet):
                material = material_mod.apply_factors(
                    cached_materials.base,
                    {key: value for key, value in stage.items() if key != "_variant"},
                )
                variant_stage = stage.get("_variant")
                variant = cached_materials.variant
                if variant is not None and isinstance(variant_stage, dict):
                    variant = material_mod.apply_factors(variant, variant_stage)
                return "material", material_mod.PreviewMaterialSet(material, variant), stamp, full
            return "material", material_mod.apply_factors(cached_materials, stage), stamp, full
        variant_stage = stage.get("_variant")
        base_stage = {key: value for key, value in stage.items() if key != "_variant"}
        mat = material_mod.build_material(
            base_stage, resolve, lambda p: load_image(p, full), full)
        if mat is not None:
            variant = None
            if isinstance(variant_stage, dict):
                variant = material_mod.build_material(
                    variant_stage, resolve, lambda p: load_image(p, full), full)
            if variant is not None:
                mat = material_mod.PreviewMaterialSet(mat, variant)
            return "material", mat, stamp, full
    img = load_image(path, full) if path else None
    return "image", img, None, full


def sources_job(carid, extra_roots=()):
    from core.model_preview.sources import collect_sources
    return collect_sources(carid, tuple(extra_roots))


def surface_job(model, defs, vfs, load_image, paint=None):
    return model, material_mod.build_surface_materials(defs, vfs, lambda p: load_image(p, False), paint)
