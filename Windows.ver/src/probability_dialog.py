from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Callable, Iterable

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from probability_math import PERCENT_SCALE, PERCENT_TOTAL_UNITS, distribute_percent_units


@dataclass(slots=True)
class _ProbabilityRow:
    filename: str
    widget: QFrame
    slider: QSlider
    spin: QDoubleSpinBox
    state: QLabel


def distribute_percent_units(values: Iterable[float], total_units: int = PERCENT_TOTAL_UNITS) -> list[int]:
    """Normalize non-negative values into exact 0.1% units using largest remainders."""
    cleaned: list[float] = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 0.0
        cleaned.append(number if math.isfinite(number) and number > 0 else 0.0)

    count = len(cleaned)
    if count == 0:
        return []
    total = sum(cleaned)
    if total <= 0:
        quotient, remainder = divmod(total_units, count)
        return [quotient + (1 if index < remainder else 0) for index in range(count)]

    exact = [value / total * total_units for value in cleaned]
    result = [int(math.floor(value)) for value in exact]
    remainder = total_units - sum(result)
    order = sorted(range(count), key=lambda index: (exact[index] - result[index], -index), reverse=True)
    for index in order[:remainder]:
        result[index] += 1
    return result


class RandomProbabilityDialog(QDialog):
    """Direct percentage editor for weighted wallpaper selection."""

    def __init__(
        self,
        parent: QWidget | None,
        folder: str,
        images: list[str],
        backend,
        translate: Callable[[str], str] = lambda text: text,
        on_saved: Callable[[], None] | None = None,
        logger: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._t = translate
        self._folder = os.path.abspath(folder)
        self._images = list(images)
        self._backend = backend
        self._on_saved = on_saved
        self._logger = logger or (lambda _message: None)
        self._rows: dict[str, _ProbabilityRow] = {}
        self._dirty = False

        self.setWindowTitle(self._t("随机壁纸概率设置（百分比）"))
        self.setModal(False)
        self.resize(920, 700)
        self.setMinimumSize(760, 540)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._build_ui()
        self._load_percentages()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        title = QLabel(self._t("随机壁纸概率设置（百分比）"))
        title.setStyleSheet("font-size: 19px; font-weight: 700;")
        root.addWidget(title)

        explain = QLabel(
            self._t("直接填写每张壁纸的随机百分比。所有项目合计必须为 100%；设为 0% 的壁纸不会参与随机。")
        )
        explain.setWordWrap(True)
        explain.setProperty("muted", True)
        root.addWidget(explain)

        summary_row = QHBoxLayout()
        self._summary_label = QLabel()
        self._summary_label.setStyleSheet("font-weight: 600;")
        self._total_bar = QProgressBar()
        self._total_bar.setRange(0, PERCENT_TOTAL_UNITS)
        self._total_bar.setTextVisible(True)
        self._total_bar.setMinimumWidth(240)
        summary_row.addWidget(self._summary_label, 1)
        summary_row.addWidget(self._total_bar)
        root.addLayout(summary_row)

        self._search = QLineEdit()
        self._search.setClearButtonEnabled(True)
        self._search.setPlaceholderText(self._t("搜索壁纸名称…"))
        self._search.textChanged.connect(self._apply_filter)
        root.addWidget(self._search)

        header = QHBoxLayout()
        name_header = QLabel(self._t("壁纸名称"))
        control_header = QLabel(self._t("随机百分比"))
        state_header = QLabel(self._t("状态"))
        for label in (name_header, control_header, state_header):
            label.setStyleSheet("font-weight: 700;")
        name_header.setMinimumWidth(230)
        control_header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        state_header.setMinimumWidth(88)
        header.addWidget(name_header, 3)
        header.addWidget(control_header, 5)
        header.addWidget(state_header, 1)
        root.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        self._rows_layout = QVBoxLayout(container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(6)

        for image_path in self._images:
            filename = os.path.basename(image_path)
            row_widget = QFrame()
            row_widget.setFrameShape(QFrame.Shape.StyledPanel)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(10, 7, 10, 7)
            row_layout.setSpacing(10)

            name = QLabel(filename)
            name.setToolTip(image_path)
            name.setMinimumWidth(220)
            name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, PERCENT_TOTAL_UNITS)
            slider.setSingleStep(1)
            slider.setPageStep(50)
            slider.setToolTip(self._t("拖动设置 0.0% 到 100.0%"))

            spin = QDoubleSpinBox()
            spin.setRange(0.0, 100.0)
            spin.setDecimals(1)
            spin.setSingleStep(0.1)
            spin.setSuffix("%")
            spin.setKeyboardTracking(False)
            spin.setMinimumWidth(98)

            state = QLabel()
            state.setAlignment(Qt.AlignmentFlag.AlignCenter)
            state.setMinimumWidth(82)

            row_layout.addWidget(name, 3)
            row_layout.addWidget(slider, 4)
            row_layout.addWidget(spin, 1)
            row_layout.addWidget(state, 1)
            self._rows_layout.addWidget(row_widget)

            row = _ProbabilityRow(filename, row_widget, slider, spin, state)
            self._rows[filename] = row
            slider.valueChanged.connect(lambda value, key=filename: self._set_units(key, value, "slider"))
            spin.valueChanged.connect(lambda value, key=filename: self._set_units(key, round(value * PERCENT_SCALE), "spin"))

        self._rows_layout.addStretch(1)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        action_row = QHBoxLayout()
        self._equal_button = QPushButton(self._t("平均分配"))
        self._normalize_button = QPushButton(self._t("按当前比例补足到 100%"))
        self._clear_button = QPushButton(self._t("全部设为 0%"))
        self._save_button = QPushButton(self._t("保存设置"))
        close_button = QPushButton(self._t("关闭"))
        for button in (self._equal_button, self._normalize_button, self._clear_button, self._save_button, close_button):
            button.setMinimumHeight(36)
        for button in (self._equal_button, self._normalize_button, self._clear_button, close_button):
            button.setProperty("secondary", True)

        self._equal_button.clicked.connect(self._set_equal)
        self._normalize_button.clicked.connect(self._normalize_current)
        self._clear_button.clicked.connect(self._clear_all)
        self._save_button.clicked.connect(self._save)
        close_button.clicked.connect(self.close)

        action_row.addWidget(self._equal_button)
        action_row.addWidget(self._normalize_button)
        action_row.addWidget(self._clear_button)
        action_row.addStretch(1)
        action_row.addWidget(self._save_button)
        action_row.addWidget(close_button)
        root.addLayout(action_row)

    def _load_percentages(self) -> None:
        try:
            weights = self._backend.get_probability_weights(self._folder)
            if not isinstance(weights, dict):
                weights = {}
        except Exception as exc:
            self._logger(f"读取随机概率失败: {exc}")
            weights = {}
        default_weight = float(getattr(self._backend, "DEFAULT_WEIGHT", 100.0))
        source_values = []
        for filename in self._rows:
            try:
                value = float(weights.get(filename, default_weight))
            except (TypeError, ValueError):
                value = default_weight
            source_values.append(value)
        self._apply_units(distribute_percent_units(source_values), mark_dirty=False)

    def _set_units(self, filename: str, units: int, source: str) -> None:
        row = self._rows.get(filename)
        if row is None:
            return
        units = max(0, min(PERCENT_TOTAL_UNITS, int(units)))
        if source != "slider":
            blocker = QSignalBlocker(row.slider)
            row.slider.setValue(units)
            del blocker
        if source != "spin":
            blocker = QSignalBlocker(row.spin)
            row.spin.setValue(units / PERCENT_SCALE)
            del blocker
        self._dirty = True
        self._refresh_state()

    def _current_units(self) -> list[int]:
        return [row.slider.value() for row in self._rows.values()]

    def _apply_units(self, values: Iterable[int], mark_dirty: bool = True) -> None:
        for row, units in zip(self._rows.values(), values):
            units = max(0, min(PERCENT_TOTAL_UNITS, int(units)))
            slider_blocker = QSignalBlocker(row.slider)
            spin_blocker = QSignalBlocker(row.spin)
            row.slider.setValue(units)
            row.spin.setValue(units / PERCENT_SCALE)
            del slider_blocker, spin_blocker
        self._dirty = mark_dirty
        self._refresh_state()

    def _set_equal(self) -> None:
        self._apply_units(distribute_percent_units([1.0] * len(self._rows)))

    def _normalize_current(self) -> None:
        self._apply_units(distribute_percent_units(self._current_units()))

    def _clear_all(self) -> None:
        self._apply_units([0] * len(self._rows))

    def _refresh_state(self) -> None:
        units = self._current_units()
        total = sum(units)
        enabled = sum(1 for value in units if value > 0)
        valid = total == PERCENT_TOTAL_UNITS and enabled > 0
        self._save_button.setEnabled(valid)

        self._total_bar.setValue(min(PERCENT_TOTAL_UNITS, total))
        self._total_bar.setFormat(f"{total / PERCENT_SCALE:.1f}% / 100.0%")
        if valid:
            self._summary_label.setText(
                self._t("分配有效") + f" · {self._t('参与随机')}: {enabled}/{len(units)}"
            )
            self._summary_label.setToolTip("")
        else:
            difference = (PERCENT_TOTAL_UNITS - total) / PERCENT_SCALE
            direction = self._t("还需分配") if difference > 0 else self._t("超出")
            self._summary_label.setText(
                f"{self._t('合计')}: {total / PERCENT_SCALE:.1f}% · {direction} {abs(difference):.1f}%"
            )
            self._summary_label.setToolTip(self._t("保存前请让所有项目合计为 100%。"))

        for row in self._rows.values():
            active = row.slider.value() > 0
            row.state.setText(self._t("参与随机") if active else self._t("不参与"))
            row.state.setProperty("active", active)
            row.state.style().unpolish(row.state)
            row.state.style().polish(row.state)

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().casefold()
        for filename, row in self._rows.items():
            row.widget.setVisible(not needle or needle in filename.casefold())

    def _save(self) -> None:
        units = self._current_units()
        if sum(units) != PERCENT_TOTAL_UNITS or not any(units):
            QMessageBox.warning(self, self._t("随机概率"), self._t("保存前请让所有项目合计为 100%。"))
            return
        values = {
            filename: row.slider.value() / PERCENT_SCALE
            for filename, row in self._rows.items()
        }
        try:
            self._backend.save_probability_weights(self._folder, values)
        except Exception as exc:
            self._logger(f"保存随机概率失败: {exc}")
            QMessageBox.warning(self, self._t("随机概率"), self._t("保存失败：") + str(exc))
            return
        self._dirty = False
        self._saved_once = True
        if self._on_saved is not None:
            self._on_saved()
        QMessageBox.information(self, self._t("随机概率"), self._t("随机百分比设置已保存。"))

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        if self._dirty:
            answer = QMessageBox.question(
                self,
                self._t("放弃未保存的更改？"),
                self._t("当前百分比尚未保存，确定关闭吗？"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        event.accept()
