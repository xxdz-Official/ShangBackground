# ui_scaling.py
"""Qt/PySide6 DPI 缩放配置助手。

Qt 的进程级 DPI 缩放环境变量需要在 QApplication 创建之前设置，
因此这里保持为纯 Python 小模块，供 main.py 在最早阶段调用。
"""
from __future__ import annotations

import os

DEFAULT_DPI_SCALE = 1.0
MIN_DPI_SCALE = 0.75
MAX_DPI_SCALE = 2.0


def clamp_dpi_scale(value, default: float = DEFAULT_DPI_SCALE) -> float:
    try:
        scale = float(value)
    except (TypeError, ValueError):
        scale = default
    return max(MIN_DPI_SCALE, min(MAX_DPI_SCALE, scale))


def dpi_percent(value) -> int:
    return int(round(clamp_dpi_scale(value) * 100))


def apply_dpi_environment(config: dict) -> float:
    """在 QApplication 创建前应用程序内 DPI 缩放。

    返回实际使用的缩放倍率。1.0 表示跟随 Qt/系统默认，不强制写 QT_SCALE_FACTOR。
    """
    scale = clamp_dpi_scale(config.get("dpi_scale", DEFAULT_DPI_SCALE))
    # 使用 PassThrough 让 Qt 保留用户填写的小数倍率，减少多显示器/非整数缩放下的抖动。
    os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")
    if abs(scale - 1.0) < 0.001:
        os.environ.pop("QT_SCALE_FACTOR", None)
    else:
        os.environ["QT_SCALE_FACTOR"] = f"{scale:.2f}".rstrip("0").rstrip(".")
    return scale
