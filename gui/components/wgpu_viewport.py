from __future__ import annotations

import math
import platform
import traceback

import numpy as np
from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from core.model_preview.dae_geometry import PreviewModel
from gui.components.viewport_common import (
    DEFAULT_PITCH, DEFAULT_YAW, TEX_CAP_FULL, TEX_CAP_NORMAL,
    build_ranges, build_surface_ranges, compute_fit, group_bounds, pot,
)

_SAMPLES = 4
_UBO_SIZE = 256
_COLOR_FORMAT = "rgba8unorm"
_DEPTH_FORMAT = "depth24plus"

_WGSL = """
struct Uniforms {
    mvp: mat4x4<f32>,
    nmat: mat4x4<f32>,
    base: vec4<f32>,
    params: vec4<f32>,   // x = alpha, y = has texture, z = has detail, w = skin-layer mode (2 = with surface maps)
    paint: vec4<f32>,    // car paint colour under the skin, w = 1 when under_tex holds the layers below
    mat: vec4<f32>,      // roughness, metallic, clearcoat, retroreflectivity
    detail: vec4<f32>,   // detail scale x, y, clearcoat roughness, w = has palette
    paint1: vec4<f32>,   // colorable skin: paint 1 / 2 / 3.  w = UV flags: 1 has mask, 2 mask on UV0, 4 surface on UV0, 8 under on UV0
    paint2: vec4<f32>,
    paint3: vec4<f32>,
};
@group(0) @binding(0) var<uniform> u: Uniforms;
@group(0) @binding(1) var tex: texture_2d<f32>;
@group(0) @binding(2) var samp: sampler;
@group(0) @binding(3) var detail_tex: texture_2d<f32>;
@group(0) @binding(4) var palette_tex: texture_2d<f32>;
@group(0) @binding(5) var surface_tex: texture_2d<f32>;
@group(0) @binding(6) var under_tex: texture_2d<f32>;
@group(0) @binding(7) var mask_tex: texture_2d<f32>;

struct VIn {
    @location(0) pos: vec3<f32>,
    @location(1) nrm: vec3<f32>,
    @location(2) uv: vec2<f32>,
    @location(3) uv2: vec2<f32>,
};
struct VOut {
    @builtin(position) clip: vec4<f32>,
    @location(0) n: vec3<f32>,
    @location(1) uv: vec2<f32>,
    @location(2) pos: vec3<f32>,
    @location(3) uv0: vec2<f32>,
};

@vertex
fn vs_main(v: VIn) -> VOut {
    var o: VOut;
    let nm = mat3x3<f32>(u.nmat[0].xyz, u.nmat[1].xyz, u.nmat[2].xyz);
    o.n = nm * v.nrm;
    o.uv = select(v.uv, v.uv2, u.base.w > 0.5);
    o.uv0 = v.uv2;
    o.pos = nm * v.pos;
    o.clip = u.mvp * vec4<f32>(v.pos, 1.0);
    return o;
}

@fragment
fn fs_main(v: VOut, @builtin(front_facing) front: bool) -> @location(0) vec4<f32> {
    var n = normalize(v.n);
    if (!front) { n = -n; }
    let ldir = normalize(vec3<f32>(0.35, 0.55, 0.75));
    let d = max(dot(n, ldir), 0.0);
    let fill = max(dot(n, normalize(vec3<f32>(-0.6, -0.2, 0.4))), 0.0);
    var light = 0.42 + 0.62 * d + 0.18 * fill;

    // sample everything up front: texture sampling must stay in uniform control flow
    let t = textureSample(tex, samp, v.uv);
    let pm = textureSample(palette_tex, samp, v.uv);
    // Each map of a skin stage is read with its own UV set: BeamNG keeps opacity / normal maps and the
    // layers below on the model's first set (uv0) while a livery colour sits on the second one (uv).
    let fl = u32(u.paint1.w + 0.5);
    let has_mask = (fl & 1u) != 0u;
    let uv_mask = select(v.uv, v.uv0, (fl & 2u) != 0u);
    let uv_surf = select(v.uv, v.uv0, (fl & 4u) != 0u);
    let uv_under = select(v.uv, v.uv0, (fl & 8u) != 0u);
    let uv_detail = select(v.uv, v.uv0, (fl & 16u) != 0u);
    let dt = textureSample(detail_tex, samp, uv_detail * u.detail.xy).rgb;
    let sf = textureSample(surface_tex, samp, uv_surf);
    let ut = textureSample(under_tex, samp, uv_under);
    let mk = textureSample(mask_tex, samp, uv_mask).r;
    let dp1 = dpdx(v.pos);
    let dp2 = dpdy(v.pos);
    let duv1 = dpdx(uv_surf);
    let duv2 = dpdy(uv_surf);

    let has_tex = u.params.y > 0.5;
    let has_detail = u.params.z > 0.5;
    let skin_mode = u.params.w > 0.5;
    var c = select(u.base.rgb, t.rgb, has_tex);
    if (!skin_mode) {
        return vec4<f32>(c * light, u.params.x);
    }

    // colorable skin: the base colour map is drawn first and is never recoloured; the
    // colorPaletteMap goes on top of it. Its red / green / blue areas become Paint 1 / 2 / 3,
    // white (and its alpha, if it has one) means "not painted": the base shows through.
    if (u.detail.w > 0.5) {
        let pal = pm.rgb - vec3<f32>(min(pm.r, min(pm.g, pm.b)));
        let cov = max(pal.r, max(pal.g, pal.b)) * pm.a;
        let pc = (u.paint1.rgb * pal.r + u.paint2.rgb * pal.g + u.paint3.rgb * pal.b)
                 / max(pal.r + pal.g + pal.b, 0.0001);
        c = mix(c, pc, cov);
    }

    // BeamNG-style skin layer on top of the car paint
    var cover = select(1.0, t.a, has_tex);
    if (has_mask) { cover = mk; }
    var rough = u.mat.x;
    var metal = u.mat.y;
    if (u.params.w > 1.5) {
        var ts = vec3<f32>(sf.r * 2.0 - 1.0, -(sf.g * 2.0 - 1.0), 0.0);
        ts.z = sqrt(max(1.0 - dot(ts.xy, ts.xy), 0.0));
        let dp2p = cross(dp2, n);
        let dp1p = cross(n, dp1);
        let tt = dp2p * duv1.x + dp1p * duv2.x;
        let bb = dp2p * duv1.y + dp1p * duv2.y;
        let inv = inverseSqrt(max(max(dot(tt, tt), dot(bb, bb)), 1e-20));
        n = normalize(tt * inv * ts.x + bb * inv * ts.y + n * ts.z);
        let d2 = max(dot(n, ldir), 0.0);
        let fill2 = max(dot(n, normalize(vec3<f32>(-0.6, -0.2, 0.4))), 0.0);
        light = 0.42 + 0.62 * d2 + 0.18 * fill2;
        rough = rough * sf.b;
        metal = metal * sf.a;
    }
    if (has_detail) {
        cover = cover * dt.r;
        rough = rough * dt.g;
        metal = metal * dt.b;
    }
    rough = clamp(rough, 0.05, 1.0);
    // what shows where this layer lets go: the layers below it, then the car paint
    let below = mix(u.paint.rgb, ut.rgb, ut.a * u.paint.w);
    let albedo = mix(below, c, cover);

    let vdir = vec3<f32>(0.0, 0.0, 1.0);
    let h = normalize(ldir + vdir);
    let nh = max(dot(n, h), 0.0);
    let shin = mix(6.0, 400.0, pow(1.0 - rough, 2.0));
    let spec_col = mix(vec3<f32>(0.35), c, metal);
    let spec = spec_col * pow(nh, shin) * (1.0 - 0.7 * rough) * cover;
    let shin_coat = mix(60.0, 1200.0, pow(1.0 - u.detail.z, 2.0));
    let coat = u.mat.z * pow(nh, shin_coat) * 0.35;
    let ndv = max(dot(n, vdir), 0.0);
    let retro = c * u.mat.w * pow(ndv, 3.0) * 0.30 * cover;

    // metalness (darkening) and clear coat belong to this layer only: outside the opacity
    // mask the layers below / the car paint are drawn untouched, so the detail maps cannot
    // show up there
    let lit = mix(below * light, c * light * (1.0 - 0.6 * metal), cover);
    let col = lit + spec + vec3<f32>(coat * cover) + retro;
    return vec4<f32>(clamp(col, vec3<f32>(0.0), vec3<f32>(1.0)), u.params.x);
}
"""

_BACKEND_LABEL = {"D3D12": "Direct3D 12", "Vulkan": "Vulkan", "Metal": "Metal",
                  "OpenGL": "OpenGL (wgpu)", "D3D11": "Direct3D 11"}
_TYPE_RANK = {"DiscreteGPU": 0, "IntegratedGPU": 1, "VirtualGPU": 2, "Unknown": 3, "CPU": 4}
_BACKEND_RANK = {
    "Windows": {"D3D12": 0, "Vulkan": 1, "OpenGL": 3},
    "Linux": {"Vulkan": 0, "OpenGL": 3},
    "Darwin": {"Metal": 0, "Vulkan": 2, "OpenGL": 3},
}


class WgpuUnavailable(RuntimeError):
    pass


def _info(adapter) -> dict:
    try:
        info = adapter.info
        return dict(info) if info is not None else {}
    except Exception:
        return {}


def _pick_adapter(wgpu, backend: str | None):
    try:
        adapters = list(wgpu.gpu.enumerate_adapters_sync())
    except Exception as e:
        print(f"[DEBUG] wgpu: enumerate_adapters unavailable ({type(e).__name__}: {e}), using default adapter")
        adapters = []
    if not adapters:
        if backend:
            import os
            os.environ.setdefault("WGPU_BACKEND_TYPE", backend)
        return wgpu.gpu.request_adapter_sync(power_preference="high-performance")

    system_rank = _BACKEND_RANK.get(platform.system(), {})
    pool = adapters
    if backend:
        pool = [a for a in adapters if str(_info(a).get("backend_type", "")).lower() == backend.lower()]
        if not pool:
            found = sorted({str(_info(a).get("backend_type", "?")) for a in adapters})
            raise WgpuUnavailable(
                f"No {_BACKEND_LABEL.get(backend, backend)} graphics adapter found "
                f"(available: {', '.join(found) or 'none'})."
            )

    def rank(a):
        i = _info(a)
        return (_TYPE_RANK.get(str(i.get("adapter_type", "Unknown")), 3),
                system_rank.get(str(i.get("backend_type", "")), 2))

    return sorted(pool, key=rank)[0]


_GPU_CACHE: dict = {}


def _limit(limits, name: str, default):
    try:
        for key in (name, name.replace("_", "-")):
            if key in limits:
                return limits[key]
    except Exception:
        pass
    return default


class _Gpu:
    def __init__(self, backend: str | None):
        import wgpu
        self.wgpu = wgpu
        self.adapter = _pick_adapter(wgpu, backend)
        self.device = self._request_device()
        info = _info(self.adapter)
        self.backend_type = str(info.get("backend_type", backend or "?"))
        self.device_name = str(info.get("device") or info.get("description") or "unknown GPU")
        self.is_software = str(info.get("adapter_type", "")) == "CPU"
        limits = self.device.limits
        self.max_texture = int(_limit(limits, "max_texture_dimension_2d", 8192))
        self.max_buffer = int(_limit(limits, "max_buffer_size", 256 * 1024 * 1024))
        print(f"[DEBUG] wgpu: max texture {self.max_texture}px, max buffer {self.max_buffer // (1024 * 1024)} MB")
        self.description = f"{_BACKEND_LABEL.get(self.backend_type, self.backend_type)} (wgpu) - {self.device_name}"
        self._pipelines = None

    def _request_device(self):
        try:
            adapter_limits = self.adapter.limits
        except Exception:
            adapter_limits = {}
        wanted = {}
        for name in ("max_texture_dimension_2d", "max_buffer_size"):
            value = _limit(adapter_limits, name, 0)
            if value:
                wanted[name] = int(value)
        for style in (lambda k: k, lambda k: k.replace("_", "-")):
            try:
                return self.adapter.request_device_sync(
                    required_limits={style(k): v for k, v in wanted.items()})
            except Exception as e:
                print(f"[DEBUG] wgpu: request_device with raised limits failed ({type(e).__name__}: {e})")
        return self.adapter.request_device_sync()

    def pipelines(self):
        if self._pipelines is None:
            wgpu, dev = self.wgpu, self.device
            module = dev.create_shader_module(code=_WGSL)
            bgl = dev.create_bind_group_layout(entries=[
                {"binding": 0, "visibility": wgpu.ShaderStage.VERTEX | wgpu.ShaderStage.FRAGMENT,
                 "buffer": {"type": "uniform"}},
                {"binding": 1, "visibility": wgpu.ShaderStage.FRAGMENT,
                 "texture": {"sample_type": "float", "view_dimension": "2d"}},
                {"binding": 2, "visibility": wgpu.ShaderStage.FRAGMENT,
                 "sampler": {"type": "filtering"}},
                {"binding": 3, "visibility": wgpu.ShaderStage.FRAGMENT,
                 "texture": {"sample_type": "float", "view_dimension": "2d"}},
                {"binding": 4, "visibility": wgpu.ShaderStage.FRAGMENT,
                 "texture": {"sample_type": "float", "view_dimension": "2d"}},
                {"binding": 5, "visibility": wgpu.ShaderStage.FRAGMENT,
                 "texture": {"sample_type": "float", "view_dimension": "2d"}},
                {"binding": 6, "visibility": wgpu.ShaderStage.FRAGMENT,
                 "texture": {"sample_type": "float", "view_dimension": "2d"}},
                {"binding": 7, "visibility": wgpu.ShaderStage.FRAGMENT,
                 "texture": {"sample_type": "float", "view_dimension": "2d"}},
            ])
            layout = dev.create_pipeline_layout(bind_group_layouts=[bgl])
            vertex = {
                "module": module, "entry_point": "vs_main",
                "buffers": [{
                    "array_stride": 40, "step_mode": "vertex",
                    "attributes": [
                        {"format": "float32x3", "offset": 0, "shader_location": 0},
                        {"format": "float32x3", "offset": 12, "shader_location": 1},
                        {"format": "float32x2", "offset": 24, "shader_location": 2},
                        {"format": "float32x2", "offset": 32, "shader_location": 3},
                    ],
                }],
            }
            primitive = {"topology": "triangle-list", "cull_mode": "none", "front_face": "ccw"}
            blend = {
                "color": {"src_factor": "src-alpha", "dst_factor": "one-minus-src-alpha", "operation": "add"},
                "alpha": {"src_factor": "one", "dst_factor": "one-minus-src-alpha", "operation": "add"},
            }

            def make(glass: bool):
                target = {"format": _COLOR_FORMAT}
                if glass:
                    target["blend"] = blend
                return dev.create_render_pipeline(
                    layout=layout, vertex=vertex, primitive=primitive,
                    depth_stencil={"format": _DEPTH_FORMAT, "depth_write_enabled": not glass,
                                   "depth_compare": "less-equal"},
                    multisample={"count": _SAMPLES},
                    fragment={"module": module, "entry_point": "fs_main", "targets": [target]},
                )

            self._pipelines = (bgl, make(False), make(True))
        return self._pipelines


def get_gpu(backend: str | None) -> _Gpu:
    key = backend or "auto"
    if key not in _GPU_CACHE:
        _GPU_CACHE[key] = _Gpu(backend)
    return _GPU_CACHE[key]


def _perspective(fov_deg: float, aspect: float, near: float, far: float) -> np.ndarray:
    f = 1.0 / math.tan(math.radians(fov_deg) / 2.0)
    m = np.zeros((4, 4), dtype=np.float64)
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = far / (near - far)
    m[2, 3] = near * far / (near - far)
    m[3, 2] = -1.0
    return m


def _rot_axis(deg: float, axis: int) -> np.ndarray:
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4)
    if axis == 0:
        m[1, 1], m[1, 2], m[2, 1], m[2, 2] = c, -s, s, c
    else:
        m[0, 0], m[0, 2], m[2, 0], m[2, 2] = c, s, -s, c
    return m


def _translate(v) -> np.ndarray:
    m = np.eye(4)
    m[:3, 3] = v
    return m


def _gpu_bytes(m: np.ndarray) -> bytes:
    return np.ascontiguousarray(m.T, dtype=np.float32).tobytes()


class WgpuViewport(QWidget):
    glError = Signal(str)
    rendererInfo = Signal(str, bool)

    def __init__(self, backend: str | None = None, parent=None):
        super().__init__(parent)
        self._backend = backend
        self.setMinimumSize(240, 240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)

        self._gpu: _Gpu | None = None
        self._failed = False
        self._gpu_reported = False

        self._model: PreviewModel | None = None
        self._model_dirty = False
        self._group_bounds: list = []
        self._visible: set[str] = set()
        self._unskinned: set[str] = set()
        self._plain: set[str] = set()
        self._skin_groups: set[str] | None = None
        self._ranges: list[tuple[int, int, int]] = []
        self._image: QImage | None = None
        self._image_dirty = False

        self._vbuf = None
        self._tex = None
        self._tex_view = None
        self._detail_tex = None
        self._detail_view = None
        self._material = None
        self._variant_material = None
        self._variant_groups: set[str] = set()
        self._variant_ranges: list[tuple[int, int]] = []
        self._variant_images: dict[str, QImage] = {}
        self._variant_dirty = False
        self._variant_views: dict[str, object] = {}
        self._detail_image: QImage | None = None
        self._detail_dirty = False
        self._palette_tex = None
        self._palette_view = None
        self._palette_image: QImage | None = None
        self._palette_dirty = False
        self._surface_tex = None
        self._surface_view = None
        self._surface_image: QImage | None = None
        self._surface_dirty = False
        self._under_tex = None
        self._under_view = None
        self._under_image: QImage | None = None
        self._under_dirty = False
        self._mask_tex = None
        self._mask_view = None
        self._mask_image: QImage | None = None
        self._mask_dirty = False
        self._smat_materials: dict = {}
        self._smat_images: dict[str, dict[str, QImage]] = {}
        self._smat_views: dict[str, dict] = {}
        self._smat_groups: dict[str, tuple] = {}
        self._smat_assign: dict[str, str] = {}
        self._smat_ranges: dict[str, list[tuple[int, int]]] = {}
        self._smat_dirty = False
        self._palette_colors = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
        self._paint = (0.92, 0.92, 0.93)
        self._dummy_view = None
        self._sampler = None
        self._ubufs = None
        self._bind_groups = None
        self._targets = None
        self._frame: QImage | None = None
        self._dirty = True

        self._bg = QColor(24, 24, 28)
        self._base = (0.62, 0.64, 0.68)
        self._glass_base = (0.50, 0.64, 0.74)
        self._plain_base = (0.30, 0.31, 0.34)

        self._yaw = DEFAULT_YAW
        self._pitch = DEFAULT_PITCH
        self._distance = 8.0
        self._target = np.zeros(3)
        self._radius = 3.0
        self._fitted = False
        self._last_pos = QPoint()

    def set_background(self, color: QColor):
        self._bg = QColor(color)
        self._invalidate()

    def set_model(self, model: PreviewModel | None):
        self._model = model
        self._model_dirty = True
        self._fitted = False
        self._group_bounds = group_bounds(model) if model is not None else []
        self._visible = set()
        self._ranges = []
        self._invalidate()

    def set_unskinned_groups(self, names: set[str]):
        self._unskinned = set(names)
        self._rebuild_ranges()
        self._invalidate()

    def set_plain_groups(self, names: set[str]):
        self._plain = set(names)
        self._rebuild_ranges()
        self._invalidate()

    def set_skin_groups(self, names: set[str] | None):
        self._skin_groups = None if names is None else set(names)
        self._rebuild_ranges()
        self._invalidate()

    def set_visible_groups(self, names: set[str], refit: bool = False):
        self._visible = set(names)
        self._rebuild_ranges()
        if refit or (not self._fitted and self._visible):
            self.fit_view()
        self._invalidate()

    def set_texture_image(self, image: QImage | None, full_res: bool = False):
        if image is not None and not image.isNull():
            cap = TEX_CAP_FULL if full_res else TEX_CAP_NORMAL
            if self._gpu is not None:
                cap = min(cap, self._gpu.max_texture)
            w, h = pot(image.width(), cap), pot(image.height(), cap)
            if (w, h) != (image.width(), image.height()):
                image = image.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            image = image.convertToFormat(QImage.Format_RGBA8888)
        else:
            image = None
        self._image = image
        self._image_dirty = True
        self._invalidate()

    def set_material(self, material, full_res: bool = False):
        self._material = material
        detail = None
        if material is not None:
            if material.albedo is not None:
                self.set_texture_image(material.albedo, full_res=full_res)
            if material.detail is not None and not material.detail.isNull():
                cap = 1024
                if self._gpu is not None:
                    cap = min(cap, self._gpu.max_texture)
                w, h = pot(material.detail.width(), cap), pot(material.detail.height(), cap)
                detail = material.detail
                if (w, h) != (detail.width(), detail.height()):
                    detail = detail.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                detail = detail.convertToFormat(QImage.Format_RGBA8888)
        self._detail_image = detail
        self._detail_dirty = True
        palette = None
        if material is not None and material.palette is not None and not material.palette.isNull():
            cap = TEX_CAP_FULL if full_res else TEX_CAP_NORMAL
            if self._gpu is not None:
                cap = min(cap, self._gpu.max_texture)
            palette = material.palette
            w, h = pot(palette.width(), cap), pot(palette.height(), cap)
            if (w, h) != (palette.width(), palette.height()):
                palette = palette.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            palette = palette.convertToFormat(QImage.Format_RGBA8888)
        self._palette_image = palette
        self._palette_dirty = True
        surface = None
        if material is not None and material.surface is not None and not material.surface.isNull():
            cap = TEX_CAP_FULL if full_res else TEX_CAP_NORMAL
            if self._gpu is not None:
                cap = min(cap, self._gpu.max_texture)
            surface = material.surface
            w, h = pot(surface.width(), cap), pot(surface.height(), cap)
            if (w, h) != (surface.width(), surface.height()):
                surface = surface.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            surface = surface.convertToFormat(QImage.Format_RGBA8888)
        self._surface_image = surface
        self._surface_dirty = True
        under = None
        if material is not None and getattr(material, "under", None) is not None and not material.under.isNull():
            cap = TEX_CAP_FULL if full_res else TEX_CAP_NORMAL
            if self._gpu is not None:
                cap = min(cap, self._gpu.max_texture)
            under = material.under
            uw, uh = pot(under.width(), cap), pot(under.height(), cap)
            if (uw, uh) != (under.width(), under.height()):
                under = under.scaled(uw, uh, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            under = under.convertToFormat(QImage.Format_RGBA8888)
        self._under_image = under
        self._under_dirty = True
        mask = None
        if material is not None and getattr(material, "mask", None) is not None and not material.mask.isNull():
            cap = TEX_CAP_FULL if full_res else TEX_CAP_NORMAL
            if self._gpu is not None:
                cap = min(cap, self._gpu.max_texture)
            mask = material.mask
            mw, mh = pot(mask.width(), cap), pot(mask.height(), cap)
            if (mw, mh) != (mask.width(), mask.height()):
                mask = mask.scaled(mw, mh, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            mask = mask.convertToFormat(QImage.Format_RGBA8888)
        self._mask_image = mask
        self._mask_dirty = True
        self._invalidate()

    def set_variant_material(self, material, groups: set[str], full_res: bool = False):
        self._variant_material = material
        self._variant_groups = set(groups)
        self._variant_images = {}
        if material is not None:
            cap = TEX_CAP_FULL if full_res else TEX_CAP_NORMAL
            if self._gpu is not None:
                cap = min(cap, self._gpu.max_texture)
            for name, image, image_cap in (
                ("albedo", material.albedo, cap),
                ("detail", material.detail, min(1024, cap)),
                ("palette", material.palette, cap),
                ("surface", material.surface, cap),
                ("under", material.under, cap),
                ("mask", getattr(material, "mask", None), cap),
            ):
                if image is None or image.isNull():
                    continue
                width, height = pot(image.width(), image_cap), pot(image.height(), image_cap)
                if (width, height) != (image.width(), image.height()):
                    image = image.scaled(width, height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                self._variant_images[name] = image.convertToFormat(QImage.Format_RGBA8888)
        self._variant_dirty = True
        self._rebuild_ranges()
        self._invalidate()

    def set_surface_materials(self, materials: dict):
        self._smat_materials = dict(materials or {})
        cap = 1024 if self._gpu is None else min(1024, self._gpu.max_texture)
        images: dict[str, dict[str, QImage]] = {}
        for key, material in self._smat_materials.items():
            entry = {}
            for name, image in (("albedo", material.albedo), ("surface", material.surface)):
                if image is None or image.isNull():
                    continue
                w, h = pot(image.width(), cap), pot(image.height(), cap)
                if (w, h) != (image.width(), image.height()):
                    image = image.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                entry[name] = image.convertToFormat(QImage.Format_RGBA8888)
            images[key] = entry
        self._smat_images = images
        self._smat_dirty = True
        self._rebuild_ranges()
        self._invalidate()

    def set_surface_assignments(self, assignments: dict):
        self._smat_assign = dict(assignments or {})
        self._rebuild_ranges()
        self._invalidate()

    def set_palette_colors(self, colors):
        self._palette_colors = [tuple(float(v) for v in c[:3]) for c in list(colors)[:3]]
        self._invalidate()

    def fit_view(self):
        fit = compute_fit(self._model, self._group_bounds, self._visible)
        if fit is None:
            return
        center, radius, distance, size, kept, total = fit
        self._target = np.array(center, dtype=np.float64)
        self._radius = radius
        self._distance = distance
        self._fitted = True
        print(f"[DEBUG] model preview fit (wgpu): size={size} dist={distance:.2f} kept={kept}/{total} parts")
        self._invalidate()

    def reset_view(self):
        self._yaw = DEFAULT_YAW
        self._pitch = DEFAULT_PITCH
        self.fit_view()

    def _rebuild_ranges(self):
        assign = {g: k for g, k in self._smat_assign.items() if k in self._smat_images}
        surface = frozenset(assign)
        self._smat_ranges = build_surface_ranges(self._model, self._visible, self._unskinned, assign)
        self._ranges = build_ranges(
            self._model, self._visible, self._unskinned, self._plain, self._skin_groups, surface
        )
        ranges = build_ranges(
            self._model, self._visible, self._unskinned, self._plain, self._variant_groups, surface
        )
        self._variant_ranges = [(first, count) for first, count, mode in ranges if mode == 1]

    def _invalidate(self):
        self._dirty = True
        self.update()

    def _fail(self, message: str):
        if self._failed:
            return
        self._failed = True
        print(f"[ERROR] model preview (wgpu): {message}")
        QTimer.singleShot(0, lambda: self.glError.emit(message))

    def _ensure_gpu(self) -> bool:
        if self._gpu is not None:
            return True
        if self._failed:
            return False
        try:
            self._gpu = get_gpu(self._backend)
            self._gpu.pipelines()
            self._sampler = self._gpu.device.create_sampler(
                address_mode_u="repeat", address_mode_v="repeat",
                mag_filter="linear", min_filter="linear", mipmap_filter="linear",
                max_anisotropy=8,
            )
            dummy = QImage(1, 1, QImage.Format_RGBA8888)
            dummy.fill(QColor(255, 255, 255, 255))
            self._dummy_view = self._make_texture_view(dummy, keep="_dummy_tex")
        except ImportError:
            self._fail("The 'wgpu' package is not installed (pip install wgpu).")
            return False
        except Exception as e:
            traceback.print_exc()
            self._gpu = None
            self._fail(f"{type(e).__name__}: {e}")
            return False
        if not self._gpu_reported:
            self._gpu_reported = True
            desc, sw = self._gpu.description, self._gpu.is_software
            QTimer.singleShot(0, lambda: self.rendererInfo.emit(desc, sw))
        return True

    def _make_texture_view(self, image: QImage, keep: str | None = "_tex"):
        gpu = self._gpu
        wgpu, dev = gpu.wgpu, gpu.device
        img = image.convertToFormat(QImage.Format_RGBA8888).mirrored(False, True)
        w, h = img.width(), img.height()
        print(f"[DEBUG] wgpu: uploading texture {w}x{h} ({keep})")
        levels = int(math.floor(math.log2(max(w, h)))) + 1
        tex = dev.create_texture(
            size=(w, h, 1), format=_COLOR_FORMAT, mip_level_count=levels,
            usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST,
        )
        level_img = img
        for level in range(levels):
            lw, lh = level_img.width(), level_img.height()
            data = np.frombuffer(level_img.constBits(), dtype=np.uint8, count=lw * lh * 4)
            dev.queue.write_texture(
                {"texture": tex, "mip_level": level, "origin": (0, 0, 0)},
                data.tobytes(),
                {"offset": 0, "bytes_per_row": lw * 4, "rows_per_image": lh},
                (lw, lh, 1),
            )
            if level + 1 < levels:
                level_img = level_img.scaled(max(1, lw // 2), max(1, lh // 2),
                                             Qt.IgnoreAspectRatio, Qt.SmoothTransformation
                                             ).convertToFormat(QImage.Format_RGBA8888)
        view = tex.create_view()
        if keep:
            setattr(self, keep, tex)
        return view

    def _upload(self):
        gpu = self._gpu
        wgpu, dev = gpu.wgpu, gpu.device
        if self._model_dirty:
            self._model_dirty = False
            self._vbuf = None
            if self._model is not None:
                data = np.ascontiguousarray(self._model.vertices, dtype=np.float32)
                if data.nbytes > gpu.max_buffer:
                    raise WgpuUnavailable(
                        f"Model is too large for this GPU ({data.nbytes // (1024 * 1024)} MB vertex data, "
                        f"limit {gpu.max_buffer // (1024 * 1024)} MB).")
                self._vbuf = dev.create_buffer_with_data(data=data.tobytes(), usage=wgpu.BufferUsage.VERTEX)
        if self._image_dirty:
            self._image_dirty = False
            self._tex = None
            self._tex_view = None
            if self._image is not None:
                self._tex_view = self._make_texture_view(self._image, "_tex")
            self._bind_groups = None
        if self._detail_dirty:
            self._detail_dirty = False
            self._detail_tex = None
            self._detail_view = None
            if self._detail_image is not None:
                self._detail_view = self._make_texture_view(self._detail_image, "_detail_tex")
            self._bind_groups = None
        if self._palette_dirty:
            self._palette_dirty = False
            self._palette_tex = None
            self._palette_view = None
            if self._palette_image is not None:
                self._palette_view = self._make_texture_view(self._palette_image, "_palette_tex")
            self._bind_groups = None
        if self._surface_dirty:
            self._surface_dirty = False
            self._surface_tex = None
            self._surface_view = None
            if self._surface_image is not None:
                self._surface_view = self._make_texture_view(self._surface_image, "_surface_tex")
            self._bind_groups = None
        if self._under_dirty:
            self._under_dirty = False
            self._under_tex = None
            self._under_view = None
            if self._under_image is not None:
                self._under_view = self._make_texture_view(self._under_image, "_under_tex")
            self._bind_groups = None
        if self._mask_dirty:
            self._mask_dirty = False
            self._mask_tex = None
            self._mask_view = None
            if self._mask_image is not None:
                self._mask_view = self._make_texture_view(self._mask_image, "_mask_tex")
            self._bind_groups = None
        if self._variant_dirty:
            self._variant_dirty = False
            for name in self._variant_views:
                setattr(self, f"_variant_{name}_tex", None)
            self._variant_views = {
                name: self._make_texture_view(image, f"_variant_{name}_tex")
                for name, image in self._variant_images.items()
            }
            self._bind_groups = None
        if self._smat_dirty:
            self._smat_dirty = False
            self._smat_views = {}
            self._smat_groups = {}
        for key in self._smat_ranges:
            if key in self._smat_groups:
                continue
            views = {}
            for name, image in self._smat_images.get(key, {}).items():
                view = self._make_texture_view(image, "_smat_keep")
                views[name] = (self._smat_keep, view)
            self._smat_views[key] = views
            ubuf = dev.create_buffer(size=_UBO_SIZE, usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST)
            albedo = views["albedo"][1] if "albedo" in views else self._dummy_view
            surface = views["surface"][1] if "surface" in views else self._dummy_view
            group = dev.create_bind_group(layout=gpu.pipelines()[0], entries=[
                {"binding": 0, "resource": {"buffer": ubuf, "offset": 0, "size": _UBO_SIZE}},
                {"binding": 1, "resource": albedo},
                {"binding": 2, "resource": self._sampler},
                {"binding": 3, "resource": self._dummy_view},
                {"binding": 4, "resource": self._dummy_view},
                {"binding": 5, "resource": surface},
                {"binding": 6, "resource": self._dummy_view},
                {"binding": 7, "resource": self._dummy_view}])
            self._smat_groups[key] = (ubuf, group, "albedo" in views, "surface" in views)
        if self._ubufs is None:
            self._ubufs = [dev.create_buffer(size=_UBO_SIZE, usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST)
                           for _ in range(4)]
            self._bind_groups = None
        if self._bind_groups is None:
            bgl = gpu.pipelines()[0]
            skin_view = self._tex_view or self._dummy_view
            detail_view = self._detail_view or self._dummy_view
            palette_view = self._palette_view or self._dummy_view
            surface_view = self._surface_view or self._dummy_view
            under_view = self._under_view or self._dummy_view
            mask_view = self._mask_view or self._dummy_view
            variant_albedo = self._variant_views.get("albedo", self._dummy_view)
            variant_detail = self._variant_views.get("detail", self._dummy_view)
            variant_palette = self._variant_views.get("palette", self._dummy_view)
            variant_surface = self._variant_views.get("surface", self._dummy_view)
            variant_under = self._variant_views.get("under", self._dummy_view)
            variant_mask = self._variant_views.get("mask", self._dummy_view)
            self._bind_groups = [
                dev.create_bind_group(layout=bgl, entries=[
                    {"binding": 0, "resource": {"buffer": self._ubufs[0], "offset": 0, "size": _UBO_SIZE}},
                    {"binding": 1, "resource": skin_view},
                    {"binding": 2, "resource": self._sampler},
                    {"binding": 3, "resource": detail_view},
                    {"binding": 4, "resource": palette_view},
                    {"binding": 5, "resource": surface_view},
                    {"binding": 6, "resource": under_view},
                    {"binding": 7, "resource": mask_view}]),
                dev.create_bind_group(layout=bgl, entries=[
                    {"binding": 0, "resource": {"buffer": self._ubufs[1], "offset": 0, "size": _UBO_SIZE}},
                    {"binding": 1, "resource": self._dummy_view},
                    {"binding": 2, "resource": self._sampler},
                    {"binding": 3, "resource": self._dummy_view},
                    {"binding": 4, "resource": self._dummy_view},
                    {"binding": 5, "resource": self._dummy_view},
                    {"binding": 6, "resource": self._dummy_view},
                    {"binding": 7, "resource": self._dummy_view}]),
                dev.create_bind_group(layout=bgl, entries=[
                    {"binding": 0, "resource": {"buffer": self._ubufs[2], "offset": 0, "size": _UBO_SIZE}},
                    {"binding": 1, "resource": self._dummy_view},
                    {"binding": 2, "resource": self._sampler},
                    {"binding": 3, "resource": self._dummy_view},
                    {"binding": 4, "resource": self._dummy_view},
                    {"binding": 5, "resource": self._dummy_view},
                    {"binding": 6, "resource": self._dummy_view},
                    {"binding": 7, "resource": self._dummy_view}]),
                dev.create_bind_group(layout=bgl, entries=[
                    {"binding": 0, "resource": {"buffer": self._ubufs[3], "offset": 0, "size": _UBO_SIZE}},
                    {"binding": 1, "resource": variant_albedo},
                    {"binding": 2, "resource": self._sampler},
                    {"binding": 3, "resource": variant_detail},
                    {"binding": 4, "resource": variant_palette},
                    {"binding": 5, "resource": variant_surface},
                    {"binding": 6, "resource": variant_under},
                    {"binding": 7, "resource": variant_mask}]),
            ]

    def _ensure_targets(self, w: int, h: int):
        if self._targets is not None and self._targets[0] == w and self._targets[1] == h:
            return
        gpu = self._gpu
        wgpu, dev = gpu.wgpu, gpu.device
        pw = ((w + 63) // 64) * 64
        usage = wgpu.TextureUsage.RENDER_ATTACHMENT
        msaa = dev.create_texture(size=(pw, h, 1), format=_COLOR_FORMAT, usage=usage, sample_count=_SAMPLES)
        resolve = dev.create_texture(size=(pw, h, 1), format=_COLOR_FORMAT,
                                     usage=usage | wgpu.TextureUsage.COPY_SRC)
        depth = dev.create_texture(size=(pw, h, 1), format=_DEPTH_FORMAT, usage=usage, sample_count=_SAMPLES)
        readback = dev.create_buffer(size=pw * 4 * h,
                                     usage=wgpu.BufferUsage.MAP_READ | wgpu.BufferUsage.COPY_DST)
        self._targets = (w, h, pw, msaa.create_view(), resolve, resolve.create_view(),
                         depth.create_view(), readback, msaa, depth)

    def _matrices(self, w: int, h: int):
        rot = _rot_axis(self._pitch, 0) @ _rot_axis(self._yaw, 1)
        view = _translate((0.0, 0.0, -self._distance)) @ rot @ _translate(-self._target)
        near = max(self._radius * 0.02, 0.005)
        far = self._distance + self._radius * 4.0
        proj = _perspective(44.0, w / max(h, 1), near, far)
        nmat = np.eye(4)
        try:
            nmat[:3, :3] = np.linalg.inv(view[:3, :3]).T
        except np.linalg.LinAlgError:
            pass
        return proj @ view, nmat

    def _uniforms(self, mvp, nmat, base, alpha, has_tex, material=None, has_detail=False,
                  has_palette=None, has_surface=None, has_under=None, stock_uv=False,
                  has_mask=None) -> bytes:
        skin = material is not None and has_tex
        has_palette = self._palette_view is not None if has_palette is None else has_palette
        has_surface = self._surface_view is not None if has_surface is None else has_surface
        has_under = self._under_view is not None if has_under is None else has_under
        has_mask = self._mask_view is not None if has_mask is None else has_mask
        uv_flags = 0.0
        if skin and has_mask:
            uv_flags += 1.0 + (2.0 if getattr(material, "mask_uv0", False) else 0.0)
        if skin and getattr(material, "surface_uv0", False):
            uv_flags += 4.0
        if skin and getattr(material, "under_uv0", False):
            uv_flags += 8.0
        if skin and has_detail and getattr(material, "detail_uv0", False):
            uv_flags += 16.0
        if skin:
            mat_vals = [material.roughness, material.metallic, material.clearcoat, material.retroreflectivity]
            detail_vals = [float(material.detail_scale[0]), float(material.detail_scale[1]),
                           material.clearcoat_roughness,
                           1.0 if has_palette else 0.0]
        else:
            mat_vals = [1.0, 0.0, 0.0, 0.0]
            detail_vals = [1.0, 1.0, 0.0, 0.0]
        return (_gpu_bytes(mvp) + _gpu_bytes(nmat)
                + np.array([*base, 1.0 if stock_uv else 0.0], dtype=np.float32).tobytes()
                + np.array([alpha, 1.0 if has_tex else 0.0,
                            1.0 if (skin and has_detail) else 0.0,
                            (2.0 if has_surface else 1.0) if skin else 0.0],
                           dtype=np.float32).tobytes()
                + np.array([*self._paint, 1.0 if (skin and has_under) else 0.0],
                           dtype=np.float32).tobytes()
                + np.array(mat_vals, dtype=np.float32).tobytes()
                + np.array(detail_vals, dtype=np.float32).tobytes()
                + b"".join(np.array([*(self._palette_colors + [(1.0, 1.0, 1.0)] * 3)[i][:3],
                                     uv_flags if i == 0 else 1.0],
                                    dtype=np.float32).tobytes() for i in range(3)))

    def _render(self) -> QImage | None:
        if not self._ensure_gpu():
            return None
        gpu = self._gpu
        wgpu, dev = gpu.wgpu, gpu.device
        dpr = self.devicePixelRatioF()
        w, h = max(1, int(self.width() * dpr)), max(1, int(self.height() * dpr))
        self._upload()
        self._ensure_targets(w, h)
        _, _, pw, msaa_view, resolve_tex, resolve_view, depth_view, readback, *_ = self._targets

        bg = self._bg
        skinned = [(f, c) for f, c, mode in self._ranges if mode == 1]
        plain = [(f, c) for f, c, mode in self._ranges if mode == 2]
        glass = [(f, c) for f, c, mode in self._ranges if mode == 0]
        has_variant = self._variant_material is not None and "albedo" in self._variant_views

        if self._vbuf is not None and self._ranges:
            mvp, nmat = self._matrices(w, h)
            dev.queue.write_buffer(self._ubufs[0], 0, self._uniforms(
                mvp, nmat, self._base, 1.0, self._tex_view is not None,
                self._material, self._detail_view is not None))
            dev.queue.write_buffer(self._ubufs[1], 0, self._uniforms(
                mvp, nmat, self._glass_base, 0.38, False))
            dev.queue.write_buffer(self._ubufs[2], 0, self._uniforms(
                mvp, nmat, self._plain_base, 1.0, False))
            for key, (ubuf, _group, has_albedo, has_surface) in self._smat_groups.items():
                material = self._smat_materials.get(key)
                if material is None or key not in self._smat_ranges:
                    continue
                dev.queue.write_buffer(ubuf, 0, self._uniforms(
                    mvp, nmat, self._plain_base, 1.0, has_albedo, material, False,
                    False, has_surface, False, stock_uv=True, has_mask=False))
            if has_variant:
                dev.queue.write_buffer(self._ubufs[3], 0, self._uniforms(
                    mvp, nmat, self._base, 1.0, True,
                    self._variant_material, "detail" in self._variant_views,
                    "palette" in self._variant_views,
                    "surface" in self._variant_views,
                    "under" in self._variant_views,
                    has_mask="mask" in self._variant_views))

        enc = dev.create_command_encoder()
        rp = enc.begin_render_pass(
            color_attachments=[{
                "view": msaa_view, "resolve_target": resolve_view,
                "clear_value": (bg.redF(), bg.greenF(), bg.blueF(), 1.0),
                "load_op": "clear", "store_op": "discard",
            }],
            depth_stencil_attachment={
                "view": depth_view, "depth_clear_value": 1.0,
                "depth_load_op": "clear", "depth_store_op": "discard",
            },
        )
        if self._vbuf is not None and self._ranges:
            _, opaque, glass_pipe = gpu.pipelines()
            rp.set_viewport(0, 0, w, h, 0.0, 1.0)
            rp.set_scissor_rect(0, 0, w, h)
            rp.set_vertex_buffer(0, self._vbuf)
            for key, key_ranges in self._smat_ranges.items():
                entry = self._smat_groups.get(key)
                if entry is None or key not in self._smat_materials:
                    continue
                rp.set_pipeline(opaque)
                rp.set_bind_group(0, entry[1])
                for first, count in key_ranges:
                    rp.draw(count, 1, first, 0)
            if skinned:
                rp.set_pipeline(opaque)
                rp.set_bind_group(0, self._bind_groups[0])
                for first, count in skinned:
                    rp.draw(count, 1, first, 0)
            if has_variant and self._variant_ranges:
                rp.set_pipeline(opaque)
                rp.set_bind_group(0, self._bind_groups[3])
                for first, count in self._variant_ranges:
                    rp.draw(count, 1, first, 0)
            if plain:
                rp.set_pipeline(opaque)
                rp.set_bind_group(0, self._bind_groups[2])
                for first, count in plain:
                    rp.draw(count, 1, first, 0)
            if glass:
                rp.set_pipeline(glass_pipe)
                rp.set_bind_group(0, self._bind_groups[1])
                for first, count in glass:
                    rp.draw(count, 1, first, 0)
        rp.end()
        enc.copy_texture_to_buffer(
            {"texture": resolve_tex, "mip_level": 0, "origin": (0, 0, 0)},
            {"buffer": readback, "offset": 0, "bytes_per_row": pw * 4, "rows_per_image": h},
            (pw, h, 1),
        )
        dev.queue.submit([enc.finish()])
        readback.map_sync(wgpu.MapMode.READ)
        try:
            raw = bytes(readback.read_mapped(copy=True))
        finally:
            readback.unmap()
        img = QImage(raw, w, h, pw * 4, QImage.Format_RGBA8888).copy()
        img.setDevicePixelRatio(dpr)
        return img

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            if self._dirty or self._frame is None or self._frame_size_changed():
                try:
                    frame = self._render()
                except Exception as e:
                    traceback.print_exc()
                    self._fail(f"{type(e).__name__}: {e}")
                    frame = None
                if frame is not None:
                    self._frame = frame
                    self._dirty = False
            if self._frame is not None:
                painter.drawImage(0, 0, self._frame)
            else:
                painter.fillRect(self.rect(), self._bg)
        finally:
            painter.end()

    def _frame_size_changed(self) -> bool:
        if self._frame is None:
            return True
        dpr = self.devicePixelRatioF()
        return (self._frame.width() != max(1, int(self.width() * dpr))
                or self._frame.height() != max(1, int(self.height() * dpr)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._invalidate()

    def mousePressEvent(self, event):
        self._last_pos = event.position().toPoint()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        dx = pos.x() - self._last_pos.x()
        dy = pos.y() - self._last_pos.y()
        self._last_pos = pos
        if event.buttons() & Qt.LeftButton:
            self._yaw += dx * 0.45
            self._pitch = max(-89.0, min(89.0, self._pitch + dy * 0.45))
        elif event.buttons() & (Qt.RightButton | Qt.MiddleButton):
            rot = _rot_axis(self._pitch, 0) @ _rot_axis(self._yaw, 1)
            right, up = rot[0, :3], rot[1, :3]
            scale = self._distance * 0.0016
            self._target = self._target - right * (dx * scale) + up * (dy * scale)
        self._invalidate()

    def wheelEvent(self, event):
        steps = event.angleDelta().y() / 120.0
        self._distance = max(self._radius * 0.15, min(self._radius * 20.0, self._distance * (0.88 ** steps)))
        self._invalidate()

    def mouseDoubleClickEvent(self, event):
        self.reset_view()
