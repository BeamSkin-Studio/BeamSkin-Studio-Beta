from __future__ import annotations

import math
import traceback

import numpy as np
from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QMatrix4x4, QSurfaceFormat, QVector2D, QVector3D, QVector4D
from PySide6.QtOpenGL import QOpenGLBuffer, QOpenGLShader, QOpenGLShaderProgram, QOpenGLTexture
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from core.model_preview.dae_geometry import PreviewModel
from gui.components.viewport_common import (
    DEFAULT_PITCH, DEFAULT_YAW, TEX_CAP_FULL, TEX_CAP_NORMAL,
    build_ranges, build_surface_ranges, compute_fit, group_bounds, looks_like_software, pot,
)

GL_FLOAT = 0x1406
GL_TRIANGLES = 0x0004
GL_DEPTH_TEST = 0x0B71
GL_COLOR_BUFFER_BIT = 0x4000
GL_DEPTH_BUFFER_BIT = 0x0100
GL_LEQUAL = 0x0203
GL_NO_ERROR = 0
GL_VENDOR_INFO_RENDERER = 0x1F01
GL_BLEND = 0x0BE2
GL_SRC_ALPHA = 0x0302
GL_ONE_MINUS_SRC_ALPHA = 0x0303

_VERTEX = """
attribute vec3 aPos;
attribute vec3 aNrm;
attribute vec2 aUv;
attribute vec2 aUv2;
uniform int uStockUv;
uniform mat4 uMvp;
uniform mat3 uNormalMat;
varying vec3 vN;
varying vec2 vUv;
varying vec2 vUv0;
varying vec3 vPos;
void main() {
    vN = uNormalMat * aNrm;
    vPos = uNormalMat * aPos;
    vUv = uStockUv == 1 ? aUv2 : aUv;
    vUv0 = aUv2;                    // the model's first UV set, whatever UV set the colour uses
    gl_Position = uMvp * vec4(aPos, 1.0);
}
"""

_FRAGMENT = """
#ifdef GL_ES
#extension GL_OES_standard_derivatives : enable
precision mediump float;
#endif
uniform sampler2D uTex;
uniform sampler2D uSurface;
uniform sampler2D uUnder;
uniform sampler2D uMask;
uniform int uHasMask;
uniform int uMaskUv0;
uniform int uSurfUv0;
uniform int uUnderUv0;
uniform int uDetailUv0;
uniform int uHasUnder;
uniform int uHasSurface;
uniform sampler2D uDetail;
uniform sampler2D uPalette;
uniform int uHasPalette;
uniform vec3 uPaint1;
uniform vec3 uPaint2;
uniform vec3 uPaint3;
uniform vec3 uBase;
uniform vec3 uPaint;
uniform int uHasTex;
uniform int uHasDetail;
uniform int uMatMode;
uniform vec2 uDetailScale;
uniform vec4 uMat;        // roughness, metallic, clearcoat, retroreflectivity
uniform float uCoatRough;
uniform float uAlpha;
varying vec3 vN;
varying vec2 vUv;
varying vec2 vUv0;
varying vec3 vPos;
void main() {
    vec3 n = normalize(vN);
    if (!gl_FrontFacing) n = -n;
    float d = max(dot(n, normalize(vec3(0.35, 0.55, 0.75))), 0.0);
    float fill = max(dot(n, normalize(vec3(-0.6, -0.2, 0.4))), 0.0);
    float light = 0.42 + 0.62 * d + 0.18 * fill;

    vec3 c = uBase;
    float cover = 1.0;
    if (uHasTex == 1) {
        vec4 t = texture2D(uTex, vUv);
        c = t.rgb;
        if (uMatMode == 1) cover = t.a;
    }
    // opacity mask kept in its own image: BeamNG reads it on UV 0 while the livery colour is on UV 1
    if (uMatMode == 1 && uHasMask == 1) {
        cover = texture2D(uMask, uMaskUv0 == 1 ? vUv0 : vUv).r;
    }
    if (uMatMode == 0) {
        gl_FragColor = vec4(c * light, uAlpha);
        return;
    }

    // colorable skin: the base colour map is drawn first and is never recoloured; the
    // colorPaletteMap goes on top of it. Its red / green / blue areas become Paint 1 / 2 / 3,
    // white (and its alpha, if it has one) means "not painted": the base shows through.
    if (uHasPalette == 1) {
        vec4 pm = texture2D(uPalette, vUv);
        vec3 pal = pm.rgb - min(pm.r, min(pm.g, pm.b));
        float cov = max(pal.r, max(pal.g, pal.b)) * pm.a;
        vec3 pc = (uPaint1 * pal.r + uPaint2 * pal.g + uPaint3 * pal.b)
                  / max(pal.r + pal.g + pal.b, 0.0001);
        c = mix(c, pc, cov);
    }

    // BeamNG-style skin layer on top of the car paint
    float rough = uMat.x;
    float metal = uMat.y;
    if (uHasSurface == 1) {
        vec2 uvS = uSurfUv0 == 1 ? vUv0 : vUv;
        vec4 sf = texture2D(uSurface, uvS);
        vec3 ts = vec3(sf.r * 2.0 - 1.0, -(sf.g * 2.0 - 1.0), 0.0);
        ts.z = sqrt(max(1.0 - dot(ts.xy, ts.xy), 0.0));
        vec3 dp1 = dFdx(vPos);
        vec3 dp2 = dFdy(vPos);
        vec2 duv1 = dFdx(uvS);
        vec2 duv2 = dFdy(uvS);
        vec3 dp2p = cross(dp2, n);
        vec3 dp1p = cross(n, dp1);
        vec3 T = dp2p * duv1.x + dp1p * duv2.x;
        vec3 B = dp2p * duv1.y + dp1p * duv2.y;
        float inv = inversesqrt(max(max(dot(T, T), dot(B, B)), 1e-20));
        n = normalize(T * inv * ts.x + B * inv * ts.y + n * ts.z);
        float d2 = max(dot(n, normalize(vec3(0.35, 0.55, 0.75))), 0.0);
        float fill2 = max(dot(n, normalize(vec3(-0.6, -0.2, 0.4))), 0.0);
        light = 0.42 + 0.62 * d2 + 0.18 * fill2;
        rough *= sf.b;
        metal *= sf.a;
    }
    if (uHasDetail == 1) {
        vec3 dt = texture2D(uDetail, (uDetailUv0 == 1 ? vUv0 : vUv) * uDetailScale).rgb;
        cover *= dt.r;
        rough *= dt.g;
        metal *= dt.b;
    }
    rough = clamp(rough, 0.05, 1.0);
    // what shows where this layer lets go: the layers below it, then the car paint
    vec3 below = uPaint;
    if (uHasUnder == 1) {
        vec4 ut = texture2D(uUnder, uUnderUv0 == 1 ? vUv0 : vUv);
        below = mix(uPaint, ut.rgb, ut.a);
    }
    vec3 albedo = mix(below, c, cover);

    vec3 V = vec3(0.0, 0.0, 1.0);
    vec3 H = normalize(normalize(vec3(0.35, 0.55, 0.75)) + V);
    float nh = max(dot(n, H), 0.0);
    float shin = mix(6.0, 400.0, pow(1.0 - rough, 2.0));
    vec3 specCol = mix(vec3(0.35), c, metal);
    vec3 spec = specCol * pow(nh, shin) * (1.0 - 0.7 * rough) * cover;
    float shinCoat = mix(60.0, 1200.0, pow(1.0 - uCoatRough, 2.0));
    float coat = uMat.z * pow(nh, shinCoat) * 0.35;
    float ndv = max(dot(n, V), 0.0);
    vec3 retro = c * uMat.w * pow(ndv, 3.0) * 0.30 * cover;

    // metalness (darkening) and clear coat belong to this layer only: outside the opacity
    // mask the layers below / the car paint are drawn untouched
    vec3 lit = mix(below * light, c * light * (1.0 - 0.6 * metal), cover);
    vec3 col = lit + spec + vec3(coat * cover) + retro;
    gl_FragColor = vec4(clamp(col, 0.0, 1.0), uAlpha);
}
"""


_pot = pot
_TEX_CAP_NORMAL = TEX_CAP_NORMAL
_TEX_CAP_FULL = TEX_CAP_FULL


class ModelViewport(QOpenGLWidget):
    glError = Signal(str)
    rendererInfo = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        fmt = QSurfaceFormat()
        fmt.setDepthBufferSize(24)
        fmt.setSamples(4)
        fmt.setVersion(2, 1)
        fmt.setProfile(QSurfaceFormat.NoProfile)
        self.setFormat(fmt)
        self.setMinimumSize(240, 240)
        self.setMouseTracking(False)

        self._model: PreviewModel | None = None
        self._model_dirty = False
        self._group_bounds: list[tuple[np.ndarray, np.ndarray]] = []
        self._visible: set[str] = set()
        self._ranges: list[tuple[int, int, int]] = []
        self._unskinned: set[str] = set()
        self._plain: set[str] = set()
        self._skin_groups: set[str] | None = None
        self._image: QImage | None = None
        self._image_dirty = False
        self._material = None
        self._variant_material = None
        self._variant_groups: set[str] = set()
        self._variant_images: dict[str, QImage] = {}
        self._variant_textures: dict[str, QOpenGLTexture] = {}
        self._variant_dirty = True
        self._variant_ranges: list[tuple[int, int]] = []
        self._detail_image: QImage | None = None
        self._detail_dirty = False
        self._detail_texture: QOpenGLTexture | None = None
        self._palette_image: QImage | None = None
        self._palette_dirty = False
        self._palette_texture: QOpenGLTexture | None = None
        self._surface_image: QImage | None = None
        self._surface_dirty = False
        self._surface_texture: QOpenGLTexture | None = None
        self._under_image: QImage | None = None
        self._under_dirty = False
        self._under_texture: QOpenGLTexture | None = None
        self._mask_image: QImage | None = None
        self._mask_dirty = False
        self._mask_texture: QOpenGLTexture | None = None
        self._smat_materials: dict = {}
        self._smat_images: dict[str, dict[str, QImage]] = {}
        self._smat_textures: dict[str, dict[str, QOpenGLTexture]] = {}
        self._smat_assign: dict[str, str] = {}
        self._smat_ranges: dict[str, list[tuple[int, int]]] = {}
        self._smat_dirty = False
        self._palette_colors = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
        self._paint = QVector3D(0.92, 0.92, 0.93)

        self._program: QOpenGLShaderProgram | None = None
        self._buffer: QOpenGLBuffer | None = None
        self._texture: QOpenGLTexture | None = None
        self._gl = None
        self._gl_ready = False
        self._failed = False
        self._watchdog_started = False
        self._watchdog_tries = 0
        self._fitted = False
        self._gl_error_shown = False

        self._bg = QColor(24, 24, 28)
        self._base = QVector3D(0.62, 0.64, 0.68)
        self._glass_base = QVector3D(0.50, 0.64, 0.74)
        self._plain_base = QVector3D(0.30, 0.31, 0.34)

        self._yaw = DEFAULT_YAW
        self._pitch = DEFAULT_PITCH
        self._distance = 8.0
        self._target = QVector3D(0, 0, 0)
        self._radius = 3.0
        self._last_pos = QPoint()

    def set_background(self, color: QColor):
        self._bg = QColor(color)
        self.update()

    def set_model(self, model: PreviewModel | None):
        self._model = model
        self._model_dirty = True
        self._fitted = False
        self._group_bounds = group_bounds(model) if model is not None else []
        self._visible = set()
        self._ranges = []
        self.update()

    def set_unskinned_groups(self, names: set[str]):
        self._unskinned = set(names)
        self._rebuild_ranges()
        self.update()

    def set_plain_groups(self, names: set[str]):
        self._plain = set(names)
        self._rebuild_ranges()
        self.update()

    def set_skin_groups(self, names: set[str] | None):
        self._skin_groups = None if names is None else set(names)
        self._rebuild_ranges()
        self.update()

    def set_visible_groups(self, names: set[str], refit: bool = False):
        self._visible = set(names)
        self._rebuild_ranges()
        if refit or (not self._fitted and self._visible):
            self.fit_view()
        self.update()

    def set_texture_image(self, image: QImage | None, full_res: bool = False):
        if image is not None and not image.isNull():
            cap = _TEX_CAP_FULL if full_res else _TEX_CAP_NORMAL
            w, h = _pot(image.width(), cap), _pot(image.height(), cap)
            if (w, h) != (image.width(), image.height()):
                image = image.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            image = image.convertToFormat(QImage.Format_RGBA8888)
        else:
            image = None
        self._image = image
        self._image_dirty = True
        self.update()

    def set_material(self, material, full_res: bool = False):
        self._material = material
        detail = None
        if material is not None:
            if material.albedo is not None:
                self.set_texture_image(material.albedo, full_res=full_res)
            if material.detail is not None and not material.detail.isNull():
                w, h = _pot(material.detail.width(), 1024), _pot(material.detail.height(), 1024)
                detail = material.detail
                if (w, h) != (detail.width(), detail.height()):
                    detail = detail.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                detail = detail.convertToFormat(QImage.Format_RGBA8888)
        self._detail_image = detail
        self._detail_dirty = True
        palette = None
        if material is not None and material.palette is not None and not material.palette.isNull():
            cap = _TEX_CAP_FULL if full_res else _TEX_CAP_NORMAL
            palette = material.palette
            w, h = _pot(palette.width(), cap), _pot(palette.height(), cap)
            if (w, h) != (palette.width(), palette.height()):
                palette = palette.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            palette = palette.convertToFormat(QImage.Format_RGBA8888)
        self._palette_image = palette
        self._palette_dirty = True
        surface = None
        if material is not None and material.surface is not None and not material.surface.isNull():
            cap = _TEX_CAP_FULL if full_res else _TEX_CAP_NORMAL
            surface = material.surface
            w, h = _pot(surface.width(), cap), _pot(surface.height(), cap)
            if (w, h) != (surface.width(), surface.height()):
                surface = surface.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            surface = surface.convertToFormat(QImage.Format_RGBA8888)
        self._surface_image = surface
        self._surface_dirty = True
        under = None
        if material is not None and getattr(material, "under", None) is not None and not material.under.isNull():
            cap = _TEX_CAP_FULL if full_res else _TEX_CAP_NORMAL
            under = material.under
            uw, uh = _pot(under.width(), cap), _pot(under.height(), cap)
            if (uw, uh) != (under.width(), under.height()):
                under = under.scaled(uw, uh, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            under = under.convertToFormat(QImage.Format_RGBA8888)
        self._under_image = under
        self._under_dirty = True
        mask = None
        if material is not None and getattr(material, "mask", None) is not None and not material.mask.isNull():
            cap = _TEX_CAP_FULL if full_res else _TEX_CAP_NORMAL
            mask = material.mask
            mw, mh = _pot(mask.width(), cap), _pot(mask.height(), cap)
            if (mw, mh) != (mask.width(), mask.height()):
                mask = mask.scaled(mw, mh, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            mask = mask.convertToFormat(QImage.Format_RGBA8888)
        self._mask_image = mask
        self._mask_dirty = True
        self.update()

    def set_variant_material(self, material, groups: set[str], full_res: bool = False):
        self._variant_material = material
        self._variant_groups = set(groups)
        self._variant_images = {}
        if material is not None:
            cap = _TEX_CAP_FULL if full_res else _TEX_CAP_NORMAL
            for name, image, image_cap in (
                ("albedo", material.albedo, cap),
                ("detail", material.detail, 1024),
                ("palette", material.palette, cap),
                ("surface", material.surface, cap),
                ("under", material.under, cap),
                ("mask", getattr(material, "mask", None), cap),
            ):
                if image is None or image.isNull():
                    continue
                width, height = _pot(image.width(), image_cap), _pot(image.height(), image_cap)
                if (width, height) != (image.width(), image.height()):
                    image = image.scaled(width, height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                self._variant_images[name] = image.convertToFormat(QImage.Format_RGBA8888)
        self._variant_dirty = True
        self._rebuild_ranges()
        self.update()

    def set_surface_materials(self, materials: dict):
        self._smat_materials = dict(materials or {})
        images: dict[str, dict[str, QImage]] = {}
        for key, material in self._smat_materials.items():
            entry = {}
            for name, image in (("albedo", material.albedo), ("surface", material.surface)):
                if image is None or image.isNull():
                    continue
                w, h = _pot(image.width(), 1024), _pot(image.height(), 1024)
                if (w, h) != (image.width(), image.height()):
                    image = image.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                entry[name] = image.convertToFormat(QImage.Format_RGBA8888)
            images[key] = entry
        self._smat_images = images
        self._smat_dirty = True
        self._rebuild_ranges()
        self.update()

    def set_surface_assignments(self, assignments: dict):
        self._smat_assign = dict(assignments or {})
        self._rebuild_ranges()
        self.update()

    def set_palette_colors(self, colors):
        self._palette_colors = [tuple(float(v) for v in c[:3]) for c in list(colors)[:3]]
        self.update()

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

    def fit_view(self):
        fit = compute_fit(self._model, self._group_bounds, self._visible)
        if fit is None:
            return
        center, radius, distance, size, kept, total = fit
        self._target = QVector3D(float(center[0]), float(center[1]), float(center[2]))
        self._radius = radius
        self._distance = distance
        self._fitted = True
        print(f"[DEBUG] model preview fit (OpenGL): size={size} dist={distance:.2f} kept={kept}/{total} parts")
        self.update()

    def reset_view(self):
        self._yaw = DEFAULT_YAW
        self._pitch = DEFAULT_PITCH
        self.fit_view()

    def initializeGL(self):
        try:
            ctx = self.context()
            self._gl = ctx.functions()
            self._gl.initializeOpenGLFunctions()
            ctx.aboutToBeDestroyed.connect(self._release_gl)
            prog = QOpenGLShaderProgram(self)
            ok = prog.addShaderFromSourceCode(QOpenGLShader.Vertex, _VERTEX)
            ok = prog.addShaderFromSourceCode(QOpenGLShader.Fragment, _FRAGMENT) and ok
            if not ok or not prog.link():
                raise RuntimeError(prog.log() or "shader compile failed")
            self._program = prog
            self._gl_ready = True
            self._report_renderer()
        except Exception as e:
            self._failed = True
            self.glError.emit(f"{type(e).__name__}: {e}")

    def showEvent(self, event):
        super().showEvent(event)
        if not self._watchdog_started:
            self._watchdog_started = True
            QTimer.singleShot(1500, self._check_context)

    def _check_context(self):
        if self._gl_ready or self._failed:
            return
        if self.isValid() and self._watchdog_tries < 3:
            self._watchdog_tries += 1
            QTimer.singleShot(1500, self._check_context)
            return
        self._failed = True
        msg = "Could not create an OpenGL context on this system"
        print(f"[WARNING] model preview: {msg}")
        self.glError.emit(msg)

    def _report_renderer(self):
        name = ""
        try:
            raw = self._gl.glGetString(GL_VENDOR_INFO_RENDERER)
            if isinstance(raw, (bytes, bytearray)):
                name = bytes(raw).decode("utf-8", "replace")
            elif raw is not None:
                name = str(raw)
        except Exception as e:
            print(f"[DEBUG] model preview: could not read GL_RENDERER: {type(e).__name__}: {e}")
        name = name.strip() or "unknown GPU"
        software = looks_like_software(name)
        print(f"[DEBUG] model preview: OpenGL renderer={name!r} software={software}")
        self.rendererInfo.emit(f"OpenGL - {name}", software)

    def _release_gl(self):
        self.makeCurrent()
        if self._texture is not None:
            self._texture.destroy()
            self._texture = None
        if self._detail_texture is not None:
            self._detail_texture.destroy()
            self._detail_texture = None
            self._detail_dirty = True
        if self._palette_texture is not None:
            self._palette_texture.destroy()
            self._palette_texture = None
            self._palette_dirty = True
        if self._surface_texture is not None:
            self._surface_texture.destroy()
            self._surface_texture = None
            self._surface_dirty = True
        if self._under_texture is not None:
            self._under_texture.destroy()
            self._under_texture = None
            self._under_dirty = True
        if self._mask_texture is not None:
            self._mask_texture.destroy()
            self._mask_texture = None
            self._mask_dirty = True
        for texture in self._variant_textures.values():
            texture.destroy()
        self._variant_textures.clear()
        self._variant_dirty = True
        self._destroy_surface_textures()
        if self._buffer is not None:
            self._buffer.destroy()
            self._buffer = None
        self._program = None
        self._gl_ready = False
        self.doneCurrent()

    def _destroy_surface_textures(self):
        for entry in self._smat_textures.values():
            for texture in entry.values():
                texture.destroy()
        self._smat_textures = {}

    def _upload(self):
        if self._model_dirty:
            self._model_dirty = False
            if self._buffer is not None:
                self._buffer.destroy()
                self._buffer = None
            if self._model is not None:
                buf = QOpenGLBuffer(QOpenGLBuffer.VertexBuffer)
                buf.create()
                buf.bind()
                data = np.ascontiguousarray(self._model.vertices, dtype=np.float32)
                buf.allocate(data.tobytes(), data.nbytes)
                buf.release()
                self._buffer = buf
        if self._image_dirty:
            self._image_dirty = False
            if self._texture is not None:
                self._texture.destroy()
                self._texture = None
            if self._image is not None:
                self._texture = self._create_texture(self._image)
        if self._detail_dirty:
            self._detail_dirty = False
            if self._detail_texture is not None:
                self._detail_texture.destroy()
                self._detail_texture = None
            if self._detail_image is not None:
                self._detail_texture = self._create_texture(self._detail_image)
        if self._palette_dirty:
            self._palette_dirty = False
            if self._palette_texture is not None:
                self._palette_texture.destroy()
                self._palette_texture = None
            if self._palette_image is not None:
                self._palette_texture = self._create_texture(self._palette_image)
        if self._surface_dirty:
            self._surface_dirty = False
            if self._surface_texture is not None:
                self._surface_texture.destroy()
                self._surface_texture = None
            if self._surface_image is not None:
                self._surface_texture = self._create_texture(self._surface_image)
        if self._under_dirty:
            self._under_dirty = False
            if self._under_texture is not None:
                self._under_texture.destroy()
                self._under_texture = None
            if self._under_image is not None:
                self._under_texture = self._create_texture(self._under_image)
        if self._mask_dirty:
            self._mask_dirty = False
            if self._mask_texture is not None:
                self._mask_texture.destroy()
                self._mask_texture = None
            if self._mask_image is not None:
                self._mask_texture = self._create_texture(self._mask_image)
        if self._smat_dirty:
            self._smat_dirty = False
            self._destroy_surface_textures()
        for key in self._smat_ranges:
            if key not in self._smat_textures:
                self._smat_textures[key] = {
                    name: texture
                    for name, image in self._smat_images.get(key, {}).items()
                    if (texture := self._create_texture(image)) is not None
                }
        if self._variant_dirty:
            self._variant_dirty = False
            for texture in self._variant_textures.values():
                texture.destroy()
            self._variant_textures = {
                name: texture
                for name, image in self._variant_images.items()
                if (texture := self._create_texture(image)) is not None
            }

    def _create_texture(self, image: QImage):
        img = image
        for _ in range(4):
            try:
                self._gl.glGetError()
                tex = QOpenGLTexture(img.mirrored(False, True))
                tex.setMinMagFilters(QOpenGLTexture.LinearMipMapLinear, QOpenGLTexture.Linear)
                tex.setWrapMode(QOpenGLTexture.Repeat)
                try:
                    tex.setMaximumAnisotropy(8.0)
                except Exception:
                    pass
                tex.generateMipMaps()
                if tex.isCreated() and tex.textureId() != 0 and self._gl.glGetError() == GL_NO_ERROR:
                    return tex
                tex.destroy()
            except Exception as e:
                print(f"[WARNING] model preview: texture upload failed: {type(e).__name__}: {e}")
            if img.width() <= 256:
                break
            print(f"[WARNING] model preview: texture {img.width()}x{img.height()} failed, retrying at half size")
            img = img.scaled(img.width() // 2, img.height() // 2, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        return None

    def paintGL(self):
        gl = self._gl
        if not self._gl_ready or gl is None:
            return
        gl.glClearColor(self._bg.redF(), self._bg.greenF(), self._bg.blueF(), 1.0)
        gl.glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        try:
            self._upload()
        except Exception as e:
            traceback.print_exc()
            self.glError.emit(f"{type(e).__name__}: {e}")
            return
        if self._buffer is None or not self._ranges or self._program is None:
            return

        dpr = self.devicePixelRatioF()
        w, h = max(1, int(self.width() * dpr)), max(1, int(self.height() * dpr))
        gl.glViewport(0, 0, w, h)
        gl.glEnable(GL_DEPTH_TEST)
        gl.glDepthFunc(GL_LEQUAL)

        view = self._view_matrix()
        proj = QMatrix4x4()
        near = max(self._radius * 0.02, 0.005)
        far = self._distance + self._radius * 4.0
        proj.perspective(44.0, w / h, near, far)

        prog = self._program
        prog.bind()
        prog.setUniformValue("uMvp", proj * view)
        prog.setUniformValue("uNormalMat", view.normalMatrix())

        skinned = [(f, c) for f, c, mode in self._ranges if mode == 1]
        plain = [(f, c) for f, c, mode in self._ranges if mode == 2]
        glass = [(f, c) for f, c, mode in self._ranges if mode == 0]

        self._buffer.bind()
        stride = 10 * 4
        locs = []
        for name, size, offset in (("aPos", 3, 0), ("aNrm", 3, 12), ("aUv", 2, 24), ("aUv2", 2, 32)):
            loc = prog.attributeLocation(name)
            if loc >= 0:
                prog.enableAttributeArray(loc)
                prog.setAttributeBuffer(loc, GL_FLOAT, offset, size, stride)
                locs.append(loc)

        prog.setUniformValue(prog.uniformLocation("uStockUv"), 0)
        if self._smat_ranges:
            prog.setUniformValue(prog.uniformLocation("uStockUv"), 1)
            prog.setUniformValue("uBase", self._plain_base)
            prog.setUniformValue("uPaint", self._paint)
            prog.setUniformValue("uAlpha", 1.0)
            for name in ("uMatMode", "uHasDetail", "uHasPalette", "uHasUnder",
                         "uHasMask", "uMaskUv0", "uSurfUv0", "uUnderUv0", "uDetailUv0"):
                prog.setUniformValue(prog.uniformLocation(name), 1 if name == "uMatMode" else 0)
            prog.setUniformValue("uDetailScale", QVector2D(1.0, 1.0))
            for key, key_ranges in self._smat_ranges.items():
                material = self._smat_materials.get(key)
                textures = self._smat_textures.get(key, {})
                if material is None:
                    continue
                albedo, surface = textures.get("albedo"), textures.get("surface")
                prog.setUniformValue(prog.uniformLocation("uHasTex"), 1 if albedo is not None else 0)
                prog.setUniformValue(prog.uniformLocation("uHasSurface"), 1 if surface is not None else 0)
                prog.setUniformValue("uMat", QVector4D(material.roughness, material.metallic,
                                                       material.clearcoat, 0.0))
                prog.setUniformValue("uCoatRough", float(material.clearcoat_roughness))
                if albedo is not None:
                    albedo.bind(0)
                    prog.setUniformValue(prog.uniformLocation("uTex"), 0)
                if surface is not None:
                    surface.bind(3)
                    prog.setUniformValue(prog.uniformLocation("uSurface"), 3)
                for first, count in key_ranges:
                    gl.glDrawArrays(GL_TRIANGLES, first, count)
                if albedo is not None:
                    albedo.release(0)
                if surface is not None:
                    surface.release(3)
            prog.setUniformValue(prog.uniformLocation("uStockUv"), 0)

        mat = self._material if self._texture is not None else None
        has_detail = mat is not None and self._detail_texture is not None
        if skinned:
            prog.setUniformValue("uBase", self._base)
            prog.setUniformValue("uPaint", self._paint)
            prog.setUniformValue("uAlpha", 1.0)
            prog.setUniformValue(prog.uniformLocation("uMatMode"), 1 if mat is not None else 0)
            prog.setUniformValue(prog.uniformLocation("uHasDetail"), 1 if has_detail else 0)
            if mat is not None:
                prog.setUniformValue("uDetailScale", QVector2D(float(mat.detail_scale[0]), float(mat.detail_scale[1])))
                prog.setUniformValue("uMat", QVector4D(mat.roughness, mat.metallic,
                                                       mat.clearcoat, mat.retroreflectivity))
                prog.setUniformValue("uCoatRough", float(mat.clearcoat_roughness))
            if has_detail:
                self._detail_texture.bind(1)
                prog.setUniformValue(prog.uniformLocation("uDetail"), 1)
            has_surface = mat is not None and self._surface_texture is not None
            prog.setUniformValue(prog.uniformLocation("uHasSurface"), 1 if has_surface else 0)
            if has_surface:
                self._surface_texture.bind(3)
                prog.setUniformValue(prog.uniformLocation("uSurface"), 3)
            has_under = mat is not None and self._under_texture is not None
            prog.setUniformValue(prog.uniformLocation("uHasUnder"), 1 if has_under else 0)
            if has_under:
                self._under_texture.bind(4)
                prog.setUniformValue(prog.uniformLocation("uUnder"), 4)
            has_mask = mat is not None and self._mask_texture is not None
            prog.setUniformValue(prog.uniformLocation("uHasMask"), 1 if has_mask else 0)
            if has_mask:
                self._mask_texture.bind(5)
                prog.setUniformValue(prog.uniformLocation("uMask"), 5)
            prog.setUniformValue(prog.uniformLocation("uMaskUv0"), 1 if (has_mask and mat.mask_uv0) else 0)
            prog.setUniformValue(prog.uniformLocation("uSurfUv0"),
                                 1 if (mat is not None and getattr(mat, "surface_uv0", False)) else 0)
            prog.setUniformValue(prog.uniformLocation("uUnderUv0"),
                                 1 if (mat is not None and getattr(mat, "under_uv0", False)) else 0)
            prog.setUniformValue(prog.uniformLocation("uDetailUv0"),
                                 1 if (has_detail and getattr(mat, "detail_uv0", False)) else 0)
            has_palette = mat is not None and self._palette_texture is not None
            prog.setUniformValue(prog.uniformLocation("uHasPalette"), 1 if has_palette else 0)
            if has_palette:
                self._palette_texture.bind(2)
                prog.setUniformValue(prog.uniformLocation("uPalette"), 2)
                for i, col in enumerate(self._palette_colors[:3]):
                    prog.setUniformValue(f"uPaint{i + 1}", QVector3D(*col))
            if self._texture is not None:
                self._texture.bind(0)
                prog.setUniformValue(prog.uniformLocation("uTex"), 0)
                prog.setUniformValue(prog.uniformLocation("uHasTex"), 1)
            else:
                prog.setUniformValue(prog.uniformLocation("uHasTex"), 0)
            for first, count in skinned:
                gl.glDrawArrays(GL_TRIANGLES, first, count)

        variant_mat = self._variant_material
        variant_textures = self._variant_textures
        variant_albedo = variant_textures.get("albedo")
        if variant_mat is not None and variant_albedo is not None and self._variant_ranges:
            prog.setUniformValue("uBase", self._base)
            prog.setUniformValue("uPaint", self._paint)
            prog.setUniformValue("uAlpha", 1.0)
            prog.setUniformValue(prog.uniformLocation("uMatMode"), 1)
            prog.setUniformValue(prog.uniformLocation("uHasTex"), 1)
            prog.setUniformValue(prog.uniformLocation("uHasDetail"),
                                 1 if variant_textures.get("detail") else 0)
            prog.setUniformValue("uDetailScale", QVector2D(
                float(variant_mat.detail_scale[0]), float(variant_mat.detail_scale[1])))
            prog.setUniformValue("uMat", QVector4D(
                variant_mat.roughness, variant_mat.metallic,
                variant_mat.clearcoat, variant_mat.retroreflectivity))
            prog.setUniformValue("uCoatRough", float(variant_mat.clearcoat_roughness))
            prog.setUniformValue(prog.uniformLocation("uHasSurface"),
                                 1 if variant_textures.get("surface") else 0)
            prog.setUniformValue(prog.uniformLocation("uHasUnder"),
                                 1 if variant_textures.get("under") else 0)
            prog.setUniformValue(prog.uniformLocation("uHasPalette"),
                                 1 if variant_textures.get("palette") else 0)
            variant_has_mask = variant_textures.get("mask") is not None
            prog.setUniformValue(prog.uniformLocation("uHasMask"), 1 if variant_has_mask else 0)
            prog.setUniformValue(prog.uniformLocation("uMaskUv0"),
                                 1 if (variant_has_mask and variant_mat.mask_uv0) else 0)
            prog.setUniformValue(prog.uniformLocation("uSurfUv0"),
                                 1 if getattr(variant_mat, "surface_uv0", False) else 0)
            prog.setUniformValue(prog.uniformLocation("uUnderUv0"),
                                 1 if getattr(variant_mat, "under_uv0", False) else 0)
            prog.setUniformValue(prog.uniformLocation("uDetailUv0"),
                                 1 if getattr(variant_mat, "detail_uv0", False) else 0)
            for unit, name, uniform in (
                (0, "albedo", "uTex"), (1, "detail", "uDetail"),
                (2, "palette", "uPalette"), (3, "surface", "uSurface"),
                (4, "under", "uUnder"), (5, "mask", "uMask"),
            ):
                texture = variant_textures.get(name)
                if texture is not None:
                    texture.bind(unit)
                    prog.setUniformValue(prog.uniformLocation(uniform), unit)
            if variant_textures.get("palette"):
                for i, col in enumerate(self._palette_colors[:3]):
                    prog.setUniformValue(f"uPaint{i + 1}", QVector3D(*col))
            for first, count in self._variant_ranges:
                gl.glDrawArrays(GL_TRIANGLES, first, count)

        if plain:
            prog.setUniformValue("uBase", self._plain_base)
            prog.setUniformValue("uAlpha", 1.0)
            prog.setUniformValue(prog.uniformLocation("uHasTex"), 0)
            prog.setUniformValue(prog.uniformLocation("uMatMode"), 0)
            prog.setUniformValue(prog.uniformLocation("uHasDetail"), 0)
            prog.setUniformValue(prog.uniformLocation("uHasPalette"), 0)
            prog.setUniformValue(prog.uniformLocation("uHasUnder"), 0)
            for first, count in plain:
                gl.glDrawArrays(GL_TRIANGLES, first, count)

        if glass:
            prog.setUniformValue("uBase", self._glass_base)
            prog.setUniformValue("uAlpha", 0.38)
            prog.setUniformValue(prog.uniformLocation("uHasTex"), 0)
            prog.setUniformValue(prog.uniformLocation("uMatMode"), 0)
            prog.setUniformValue(prog.uniformLocation("uHasDetail"), 0)
            gl.glEnable(GL_BLEND)
            gl.glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            gl.glDepthMask(False)
            for first, count in glass:
                gl.glDrawArrays(GL_TRIANGLES, first, count)
            gl.glDepthMask(True)
            gl.glDisable(GL_BLEND)

        err = gl.glGetError()
        if err != GL_NO_ERROR and not self._gl_error_shown:
            self._gl_error_shown = True
            print(f"[WARNING] model preview: glGetError=0x{err:04X} after draw")

        for loc in locs:
            prog.disableAttributeArray(loc)
        self._buffer.release()
        if self._texture is not None:
            self._texture.release(0)
        if self._detail_texture is not None:
            self._detail_texture.release(1)
        if self._palette_texture is not None:
            self._palette_texture.release(2)
        if self._surface_texture is not None:
            self._surface_texture.release(3)
        if self._under_texture is not None:
            self._under_texture.release(4)
        if self._mask_texture is not None:
            self._mask_texture.release(5)
        for texture in self._variant_textures.values():
            texture.release()
        prog.release()

    def _rotation(self) -> QMatrix4x4:
        rot = QMatrix4x4()
        rot.rotate(self._pitch, 1.0, 0.0, 0.0)
        rot.rotate(self._yaw, 0.0, 1.0, 0.0)
        return rot

    def _view_matrix(self) -> QMatrix4x4:
        view = QMatrix4x4()
        view.translate(0.0, 0.0, -self._distance)
        view *= self._rotation()
        view.translate(-self._target)
        return view

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
            rot = self._rotation()
            right = QVector3D(rot.row(0).x(), rot.row(0).y(), rot.row(0).z())
            up = QVector3D(rot.row(1).x(), rot.row(1).y(), rot.row(1).z())
            scale = self._distance * 0.0016
            self._target = self._target - right * (dx * scale) + up * (dy * scale)
        self.update()

    def wheelEvent(self, event):
        steps = event.angleDelta().y() / 120.0
        self._distance = max(self._radius * 0.15, min(self._radius * 20.0, self._distance * (0.88 ** steps)))
        self.update()

    def mouseDoubleClickEvent(self, event):
        self.reset_view()
