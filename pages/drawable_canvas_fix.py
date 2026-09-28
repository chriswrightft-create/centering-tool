"""
Optional override for ``streamlit_drawable_canvas.st_canvas``.

The stock widget passes a ``/media/...`` PNG URL as ``backgroundImageURL``. The
iframe script resolves it as ``streamlitOrigin + backgroundImageURL``, which is
correct for path-style URLs.

An experimental **data URL** path exists (``png_data_url_for_drawable_canvas``) for
people who wanted to avoid ``/media/`` races. On Streamlit 1.50+ the same script
still does ``origin + backgroundImageURL``, which turns ``data:image/...`` into an
invalid URL and yields a **blank canvas**, so data URLs are **off by default**.

Set ``GRADING_DRAWABLE_CANVAS_DATA_URL=1`` (or ``true`` / ``on``) to opt into the
experimental data URL path (not recommended on current Streamlit + drawable-canvas).

On Streamlit Community Cloud, ``pages/line_mark_canvas_js.py`` also paints the same
JPEG data URL used for the zoom lens onto the drawable-canvas background layer when
``/media/`` URLs fail inside the component iframe.
"""

from __future__ import annotations

import os
import inspect
from typing import Any, Optional

import numpy as np
import streamlit_drawable_canvas as drawable_module

from pages.streamlit_canvas_image import png_data_url_for_drawable_canvas

_original_st_canvas = drawable_module.st_canvas
# These private hooks existed in streamlit-drawable-canvas 0.9.x. Starting with
# 0.10.0 the package uses Components v2 and handles data URLs publicly.
_component_func = getattr(drawable_module, "_component_func", None)
_resize_img = getattr(drawable_module, "_resize_img", None)
_data_url_to_image = getattr(drawable_module, "_data_url_to_image", None)
_canvas_result_type = getattr(drawable_module, "CanvasResult", Any)


def prefer_data_url_background() -> bool:
    raw = os.environ.get("GRADING_DRAWABLE_CANVAS_DATA_URL", "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _st_canvas_data_url_background(
    fill_color: str = "#eee",
    stroke_width: int = 20,
    stroke_color: str = "black",
    background_color: str = "",
    background_image: Any = None,
    update_streamlit: bool = True,
    height: int = 400,
    width: int = 600,
    drawing_mode: str = "freedraw",
    initial_drawing: Optional[dict] = None,
    display_toolbar: bool = True,
    point_display_radius: int = 3,
    key=None,
) -> Any:
    background_image_url = None
    if background_image is not None:
        resized = _resize_img(background_image, height, width)
        background_image_url = png_data_url_for_drawable_canvas(resized)

    initial_drawing = {"version": "4.4.0"} if initial_drawing is None else initial_drawing
    initial_drawing["background"] = background_color

    component_value = _component_func(
        fillColor=fill_color,
        strokeWidth=stroke_width,
        strokeColor=stroke_color,
        backgroundColor=background_color,
        backgroundImageURL=background_image_url,
        realtimeUpdateStreamlit=update_streamlit and (drawing_mode != "polygon"),
        canvasHeight=height,
        canvasWidth=width,
        drawingMode=drawing_mode,
        initialDrawing=initial_drawing,
        displayToolbar=display_toolbar,
        displayRadius=point_display_radius,
        key=key,
        default=None,
    )
    if component_value is None:
        return _canvas_result_type

    return _canvas_result_type(
        np.asarray(_data_url_to_image(component_value["data"])),
        component_value["raw"],
    )


def st_canvas(*args: Any, **kwargs: Any) -> Any:
    if prefer_data_url_background() and all(
        hook is not None for hook in (_component_func, _resize_img, _data_url_to_image)
    ):
        return _st_canvas_data_url_background(*args, **kwargs)
    if "display_toolbar" not in inspect.signature(_original_st_canvas).parameters:
        kwargs.pop("display_toolbar", None)
    return _original_st_canvas(*args, **kwargs)


def install_drawable_canvas_data_url_background() -> None:
    drawable_module.st_canvas = st_canvas
