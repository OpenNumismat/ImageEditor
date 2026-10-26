from typing import Dict, List, Optional

from PySide6.QtCore import (
    QCoreApplication,
    QObject,
    QRunnable,
    QThreadPool,
    Qt,
    Signal as pyqtSignal,
)
from PySide6.QtGui import QIcon, QImage
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

try:
    from .LibGPhotoCamera import (
        ConfigItem,
        GP_WIDGET_BUTTON,
        GP_WIDGET_DATE,
        GP_WIDGET_MENU,
        GP_WIDGET_RADIO,
        GP_WIDGET_RANGE,
        GP_WIDGET_TEXT,
        GP_WIDGET_TOGGLE,
        LibGPhotoCameraManager,
        Value,
        classify_capture_target,
        get_default_camera_manager,
    )
except ImportError:
    from LibGPhotoCamera import (
        ConfigItem,
        GP_WIDGET_BUTTON,
        GP_WIDGET_DATE,
        GP_WIDGET_MENU,
        GP_WIDGET_RADIO,
        GP_WIDGET_RANGE,
        GP_WIDGET_TEXT,
        GP_WIDGET_TOGGLE,
        LibGPhotoCameraManager,
        Value,
        classify_capture_target,
        get_default_camera_manager,
    )

try:
    from OpenNumismat.Tools.DialogDecorators import storeDlgSizeDecorator
except ModuleNotFoundError:
    from Tools.DialogDecorators import storeDlgSizeDecorator


# Settings hidden from the dialog, matched against libgphoto2 widget names -
# the last segment of the config path (e.g. "ownername" in
# /main/settings/ownername). Widget names are untranslated identifiers, so
# this list hides a setting in every system language; prefer it over the
# labels below when adding entries.
HIDDEN_CAMERA_SETTING_NAMES = frozenset({
    "ownername",
    "datetime",
    "datetimeutc",
    "syncdatetime",
    "syncdatetimeutc",
    "opcode",
    "listallfiles",
    # libgphoto2 driver preference selecting the size of downloaded
    # previews/thumbnails (normal/large, Nikon GetLargeThumb). Not a camera
    # property and irrelevant here: captures download the full image and
    # previews come from gp_camera_capture_preview, never a file preview.
    "thumbsize",
})

# Settings hidden from the dialog, matched against normalized libgphoto2
# labels. Labels are gettext-translated ("Owner Name" becomes e.g.
# "Eigentuemer"), so these entries only match while libgphoto2 answers in
# English - which requires the C locale. Never call locale.setlocale() in
# this app or this list silently stops working; put anything that must hide
# in every language into HIDDEN_CAMERA_SETTING_NAMES above.
HIDDEN_CAMERA_SETTING_LABELS = frozenset({
    "ownername",
    "synchronizecameradateandtimewithpc",
    "dateandtime",
    "cameradateandtime",
    "listallfiles",
    "opcode",
    # "Thumb Size" (libgphoto2's preview-thumbnail download preference);
    # covered by HIDDEN_CAMERA_SETTING_NAMES, kept here as a fallback.
    "thumbsize"
})

# Normalized libgphoto2 section names whose children are momentary triggers
# (bulb, UI lock, autofocus drive, movie mode, raw opcodes, ...) rather than
# capture settings. Writing such a trigger is rejected by some cameras or does
# something unintended, so whole sections are hidden from the dialog.
HIDDEN_CAMERA_SETTING_SECTIONS = frozenset({
    "actions",
})


class _CameraCaptureSignals(QObject):
    """Deliver camera capture results to the dialog's GUI thread."""

    # Emitted from the QThreadPool worker; the receiver lives on the GUI
    # thread, so Qt turns this into a queued connection and the slot runs
    # on the GUI thread. Payloads are (image bytes | None, error | None).
    finished = pyqtSignal(object, object)


class _CameraCaptureTask(QRunnable):
    """Run one camera capture without blocking the dialog's event loop."""

    def __init__(
        self,
        camera_manager: LibGPhotoCameraManager,
        selected: Dict[str, str],
        settings: Dict[str, Value],
        preview: bool,
        restore_target: bool,
        signals: _CameraCaptureSignals,
    ) -> None:
        super().__init__()
        self.camera_manager = camera_manager
        self.selected = selected
        self.settings = settings
        self.preview = preview
        self.restore_target = restore_target
        self.signals = signals

    def run(self) -> None:
        try:
            image_data = self.camera_manager.capture(
                self.selected,
                self.settings,
                preview=self.preview,
                restore_target=self.restore_target,
            )
        except Exception as error:
            self._emit_finished(None, str(error))
        else:
            self._emit_finished(image_data, None)

    def _emit_finished(
        self, image_data: Optional[bytes], error_message: Optional[str]
    ) -> None:
        """Ignore completion if the application has already torn down Qt."""
        try:
            self.signals.finished.emit(image_data, error_message)
        except RuntimeError:
            pass


@storeDlgSizeDecorator
class CameraGPhotoDialog(QDialog):
    """Dialog for choosing a libgphoto2 camera, configuring it, and capturing."""

    image: Optional[QImage]
    camera: LibGPhotoCameraManager

    def __init__(
        self, parent: Optional[QWidget] = None, camera_manager: Optional[LibGPhotoCameraManager] = None
    ) -> None:
        """Build the camera UI and initialize camera discovery.

        Args:
            parent: Optional Qt parent widget.
            camera_manager: Optional shared camera manager; the process default
                manager is used when omitted.
        """
        super().__init__(parent)
        self.setWindowIcon(QIcon(":/camera.png"))
        self.setWindowTitle(self.tr("Camera (libgphoto2)"))
        self.resize(440, 520)

        self.camera = camera_manager or get_default_camera_manager()
        app = QApplication.instance()
        # Hook manager cleanup (restore changed camera settings, sync
        # QSettings) to application shutdown exactly once per manager, even
        # when several dialogs are opened during the process lifetime.
        if app is not None and not getattr(self.camera, "_qt_shutdown_connected", False):
            app.aboutToQuit.connect(self.camera.close)
            self.camera._qt_shutdown_connected = True
        self.image = None
        self._parameters = []
        self._controls = {}
        self._selected = None
        self._changing_camera = False
        self._standard_capture_available = False
        self._preview_available = False
        self._cached_config = False
        self._capture_pending = False
        self._capture_signals = None

        self.cameraSelector = QComboBox()
        self.cameraSelector.currentIndexChanged.connect(self.cameraSelectionChanged)
        self.statusLabel = QLabel()
        self.statusLabel.setWordWrap(True)
        self.previewCheckbox = QCheckBox(self.tr("Capture in preview mode"))
        self.previewCheckbox.toggled.connect(self.previewChanged)
        self.restoreTargetCheckbox = QCheckBox(
            self.tr("Restore original capture target after each shot")
        )
        self.restoreTargetCheckbox.setChecked(True)
        self.restoreTargetCheckbox.toggled.connect(self._configChanged)

        self.reevaluateButton = QPushButton(self.tr("Re-evaluate cameras"))
        self.reevaluateButton.clicked.connect(self.reevaluateCameras)
        self.reloadSettingsButton = QPushButton(self.tr("Use camera's current settings"))
        self.reloadSettingsButton.setToolTip(self.tr(
            "Forget the values saved in this dialog and reload the camera's own "
            "current settings. Camera factory defaults are not reported by "
            "gphoto2, so the values the camera holds now are used."
        ))
        self.reloadSettingsButton.clicked.connect(self.reloadCameraSettings)
        self.reloadSettingsButton.setEnabled(False)

        self.configWidget = QWidget()
        self.configForm = QFormLayout(self.configWidget)
        self.configForm.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.configScroll = QScrollArea()
        self.configScroll.setWidgetResizable(True)
        self.configScroll.setWidget(self.configWidget)

        self.captureButton = QPushButton(self.tr("Shoot"))
        self.captureButton.setEnabled(False)
        self.captureButton.clicked.connect(self.capture)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(self.captureButton)
        layout = QVBoxLayout(self)
        top_buttons = QHBoxLayout()
        top_buttons.addWidget(self.reevaluateButton)
        top_buttons.addWidget(self.reloadSettingsButton)
        layout.addLayout(top_buttons)
        layout.addWidget(self.cameraSelector)
        layout.addWidget(self.previewCheckbox)
        layout.addWidget(self.restoreTargetCheckbox)
        layout.addWidget(self.configScroll, 1)
        layout.addWidget(self.statusLabel)
        layout.addLayout(button_layout)

        self.initializeCameras()

    def initializeCameras(self) -> None:
        """Populate the selector and load the last-used detected camera."""
        try:
            cameras = self.camera.cameras()
        except (OSError, RuntimeError, AttributeError) as error:
            self.cameraSelector.setEnabled(False)
            self.previewCheckbox.setEnabled(False)
            self.restoreTargetCheckbox.setEnabled(False)
            self.statusLabel.setText(self.tr("Could not initialize libgphoto2."))
            QMessageBox.warning(self, self.tr("Camera Error"), str(error))
            return

        self.cameraSelector.blockSignals(True)
        for camera in cameras:
            display = f"{camera['model']} ({camera['port']})" if camera["port"] else camera["model"]
            self.cameraSelector.addItem(display, camera)
        self.cameraSelector.blockSignals(False)

        if not cameras:
            self.cameraSelector.setEnabled(False)
            self.previewCheckbox.setEnabled(False)
            self.restoreTargetCheckbox.setEnabled(False)
            self.reloadSettingsButton.setEnabled(False)
            self.statusLabel.setText(self.tr("No cameras detected."))
            return

        selected_index = 0
        last_camera = self.camera.last_camera
        if last_camera:
            for index, camera in enumerate(cameras):
                if self.camera.camera_key(camera) == self.camera.camera_key(last_camera):
                    selected_index = index
                    break
        # addItem() already moved the empty combo to index 0, so
        # setCurrentIndex() only emits currentIndexChanged when the target
        # index differs; call the handler explicitly to cover the no-change
        # case. When the signal does fire, the handler runs twice - the
        # second pass is cheap because the manager caches the inspection.
        self.cameraSelector.setCurrentIndex(selected_index)
        self.cameraSelectionChanged(selected_index)

    @staticmethod
    def _control_state(widget: QWidget, kind: int) -> Value:
        """Read a control's current value using the type matching its kind."""
        if kind == GP_WIDGET_TOGGLE:
            return int(widget.isChecked())
        if kind in (GP_WIDGET_RADIO, GP_WIDGET_MENU):
            return widget.currentData()
        if kind == GP_WIDGET_TEXT:
            return widget.text()
        return widget.value()

    def _save_current_values(self) -> None:
        """Read editable controls and persist their values for this camera."""
        if self._selected is None:
            return
        values = {}
        for path, (widget, kind, parameter, raw_value, initial_state) in self._controls.items():
            if parameter["readonly"]:
                continue
            state = self._control_state(widget, kind)
            # Keep the raw camera value while a control is untouched. Qt
            # editors coerce values (a toggle value of 2 becomes a checked
            # checkbox, a spin box rounds a float, a menu without the current
            # value in its choices falls back to the first entry), and writing
            # that coerced value back would present it to the camera as a
            # real change - which some cameras reject.
            if state == initial_state:
                if kind == GP_WIDGET_DATE or raw_value is None:
                    # An untouched clock is left out: it ticks, so the saved
                    # value would write a stale time back to the camera. An
                    # unreadable value has nothing to write either. Both are
                    # saved again as soon as the user edits them.
                    continue
                values[path] = raw_value
            else:
                values[path] = state
        self.camera.save_preferences(
            self._selected, values, self.previewCheckbox.isChecked(),
            self.restoreTargetCheckbox.isChecked(),
        )

    def cameraSelectionChanged(self, index: int, save_current: bool = True) -> None:
        """Load a selected camera's schema and restore valid saved values.

        With ``save_current`` false the controls being replaced are dropped
        rather than saved first, which is what reloading from the camera needs.
        """
        if self._changing_camera or index < 0 or self.camera is None:
            return
        if save_current:
            self._save_current_values()
        selected = self.cameraSelector.itemData(index)
        self._selected = selected
        self.captureButton.setEnabled(False)
        self.statusLabel.setText(self.tr("Reading camera settings..."))
        self.statusLabel.repaint()
        try:
            info = self.camera.inspect(selected)
        except (OSError, RuntimeError, AttributeError) as error:
            self._clear_controls()
            # Forget the unreachable camera and the previous camera's
            # capabilities: a stray _configChanged must not save empty
            # values over this camera's stored preferences or judge
            # capture availability from stale state.
            self._selected = None
            self._parameters = []
            self._cached_config = False
            self._preview_available = False
            self._standard_capture_available = False
            self.previewCheckbox.setEnabled(False)
            self.restoreTargetCheckbox.setEnabled(False)
            self.reloadSettingsButton.setEnabled(False)
            self.statusLabel.setText(self.tr("Could not read camera settings."))
            QMessageBox.warning(self, self.tr("Camera Error"), str(error))
            return

        self._parameters = info["parameters"]
        # The manager marks results served from the persisted schema cache
        # (camera currently unreachable) with "_cached"; capture stays
        # disabled in that case.
        self._cached_config = info.pop("_cached", False)
        preferences = self.camera.preferences(selected)
        remembered = preferences.get("settings", {})
        # Retain only values still supported by this camera's config schema.
        supported = {item["path"]: item for item in self._parameters}
        remembered = {
            path: value for path, value in remembered.items()
            if path in supported and not supported[path]["readonly"]
            and (not supported[path]["choices"] or str(value) in supported[path]["choices"])
        }
        self._build_controls(self._parameters, remembered)
        preview_available = info["preview"]
        self._preview_available = preview_available
        self._standard_capture_available = info["capture"]
        self.previewCheckbox.setEnabled(preview_available)
        # Re-enable after a previous camera's settings failed to load.
        self.restoreTargetCheckbox.setEnabled(True)
        self.reloadSettingsButton.setEnabled(True)
        self.previewCheckbox.blockSignals(True)
        preview_default = bool(preferences.get("preview", preview_available)) and preview_available
        if preview_available and not self._standard_capture_available:
            preview_default = True
        self.previewCheckbox.setChecked(preview_default)
        self.previewCheckbox.blockSignals(False)
        self.restoreTargetCheckbox.blockSignals(True)
        self.restoreTargetCheckbox.setChecked(preferences.get("restore_target", True))
        self.restoreTargetCheckbox.blockSignals(False)

        capture_available = self._standard_capture_available or preview_available
        self._update_capture_availability()
        if self._cached_config:
            self.statusLabel.setText(
                self.tr("Camera is unavailable; showing saved settings. Capture is disabled.")
            )
        elif not capture_available:
            self.statusLabel.setText(self.tr("This camera does not advertise image capture."))
        else:
            self.statusLabel.setText(self.tr("Camera settings loaded."))
        self._save_current_values()

    def _standard_ready(self) -> bool:
        """Return whether standard capture currently targets internal RAM."""
        if not self._standard_capture_available:
            return False
        target_control = next(
            ((widget, parameter) for path, (widget, kind, parameter, *_tracked) in self._controls.items()
             if path.endswith("/capturetarget") and kind in (GP_WIDGET_RADIO, GP_WIDGET_MENU)),
            None,
        )
        if target_control:
            value = target_control[0].currentData()
        else:
            target_parameter = next(
                (parameter for parameter in self._parameters
                 if parameter["path"].endswith("/capturetarget")),
                None,
            )
            value = target_parameter["value"] if target_parameter else None
        classification = classify_capture_target(value)
        if classification is not None:
            return classification
        # Labels are gettext-translated, so keyword matching can fail outside
        # the C locale; fall back to the API's verdict. Capture re-checks and
        # forces RAM regardless of what this control displays.
        return self._standard_capture_available

    def _update_capture_availability(self) -> None:
        """Update the capture button and any RAM-safety status message."""
        use_preview = self._preview_available and self.previewCheckbox.isChecked()
        available = not self._cached_config and (
            self._preview_available if use_preview
            else self._standard_ready()
        )
        self.captureButton.setEnabled(available and not self._capture_pending)
        if self._cached_config:
            self.statusLabel.setText(
                self.tr("Camera is unavailable; showing saved settings. Capture is disabled.")
            )
            return
        if not available and not use_preview:
            self.statusLabel.setText(
                self.tr("Standard capture is unavailable unless an internal-RAM target is selected.")
            )

    def _configChanged(self, *_args: object) -> None:
        """Persist changed controls and recalculate capture availability."""
        if self._changing_camera:
            return
        self._save_current_values()
        self._update_capture_availability()

    def _clear_controls(self) -> None:
        """Remove all generated setting rows from the form."""
        while self.configForm.rowCount():
            self.configForm.removeRow(0)
        self._controls.clear()

    def _build_controls(
        self,
        parameters: List[ConfigItem],
        remembered: Dict[str, Value],
    ) -> None:
        """Create controls for supported settings, using remembered values."""
        self._changing_camera = True
        self._clear_controls()
        self._controls = {}
        for parameter in parameters:
            if self._is_hidden_parameter(parameter):
                continue
            kind = parameter["type"]
            if kind == GP_WIDGET_BUTTON:
                continue
            path = parameter["path"]
            value = remembered.get(path, parameter["value"])
            # First-use defaults when nothing is remembered for this camera:
            # prefer the full-size image and an internal-RAM capture target
            # so standard capture is immediately available and safe.
            if path.endswith("/capturesizeclass") and path not in remembered:
                full_image = next(
                    (choice for choice in parameter["choices"]
                     if choice.strip().lower() == "full image"),
                    None,
                )
                if full_image is not None:
                    value = full_image
            if path.endswith("/capturetarget") and path not in remembered:
                internal = next(
                    (choice for choice in parameter["choices"]
                     if self._is_ram_choice(choice)),
                    None,
                )
                if internal is not None:
                    value = internal

            widget = self._make_control(parameter, value)
            if widget is None:
                continue
            widget.setEnabled(not parameter["readonly"])
            widget.setToolTip(path)
            label = self._translate_camera_text(parameter["label"], path, "label")
            self.configForm.addRow(label, widget)
            # Track the raw value and the control state it produced so
            # _save_current_values() can tell a real edit from the coercion
            # the Qt control applies to the raw camera value.
            self._controls[path] = (widget, kind, parameter, value, self._control_state(widget, kind))
            signal = getattr(widget, "currentIndexChanged", None)
            if signal is not None:
                signal.connect(self._configChanged)
            elif kind == GP_WIDGET_TOGGLE:
                widget.toggled.connect(self._configChanged)
            elif kind == GP_WIDGET_TEXT:
                widget.editingFinished.connect(self._configChanged)
            else:
                widget.valueChanged.connect(self._configChanged)
        self._changing_camera = False

    @staticmethod
    def _is_ram_choice(choice: Value) -> bool:
        """Return whether a choice is an internal-memory target.

        Delegates to ``classify_capture_target``; unclassifiable values are
        not RAM here - callers with a driver-setting fallback handle those.
        """
        return classify_capture_target(choice) is True

    @staticmethod
    def _normalize_camera_text(text: str) -> str:
        """Normalize a setting label for comparison with the hidden-label list."""
        return "".join(character for character in text.casefold() if character.isalnum())

    @classmethod
    def _is_hidden_parameter(
        cls: type, parameter: ConfigItem
    ) -> bool:
        """Return whether a config parameter is intentionally hidden.

        Matching the widget name and the config-path section names is
        locale-independent; matching the label only catches libgphoto2's
        English wording, since labels are gettext-translated.
        """
        if cls._normalize_camera_text(parameter.get("name", "")) in HIDDEN_CAMERA_SETTING_NAMES:
            return True
        if cls._normalize_camera_text(parameter.get("label", "")) in HIDDEN_CAMERA_SETTING_LABELS:
            return True
        # The path's segments (not the setting's own name) name the sections
        # holding it; a setting inside a hidden section is hidden as well.
        segments = parameter.get("path", "").strip("/").split("/")[:-1]
        return any(
            cls._normalize_camera_text(segment) in HIDDEN_CAMERA_SETTING_SECTIONS
            for segment in segments
        )

    @staticmethod
    def _translate_camera_text(text: str, path: str, role: str) -> str:
        """Translate dynamic camera text, falling back to libgphoto2's wording.

        The Qt disambiguation (`label:/config/path` or `choice:/config/path`)
        lets catalogs distinguish identical words used by different settings.
        A no-disambiguation lookup also supports generic translations.
        """
        translated = QCoreApplication.translate(
            "CameraSettings", text, f"{role}:{path}"
        )
        if translated == text:
            translated = QCoreApplication.translate("CameraSettings", text)
        return translated

    def _make_control(
        self, parameter: ConfigItem, value: Value
    ) -> Optional[QWidget]:
        """Build the Qt editor matching a libgphoto2 widget type."""
        kind = parameter["type"]
        if kind in (GP_WIDGET_RADIO, GP_WIDGET_MENU):
            combo = QComboBox()
            choices = list(parameter["choices"])
            # A camera can report a value it does not list as a choice; keep
            # it as an extra entry so an untouched control preserves it
            # instead of silently selecting - and writing - the first choice.
            if value is not None and str(value) not in choices:
                choices.insert(0, str(value))
            for choice in choices:
                combo.addItem(
                    self._translate_camera_text(choice, parameter["path"], "choice"),
                    choice,
                )
            if value is not None:
                index = combo.findData(str(value))
                if index >= 0:
                    combo.setCurrentIndex(index)
            return combo
        if kind == GP_WIDGET_TOGGLE:
            checkbox = QCheckBox()
            checkbox.setChecked(bool(value))
            return checkbox
        if kind == GP_WIDGET_TEXT:
            edit = QLineEdit("" if value is None else str(value))
            return edit
        if kind == GP_WIDGET_RANGE:
            # `or` also covers a None range (bounds unreadable) and older
            # persisted caches that omit the key entirely.
            low, high, step = parameter.get("range") or (0.0, 100.0, 1.0)
            spin = QDoubleSpinBox()
            spin.setRange(low, high)
            spin.setSingleStep(step if step > 0 else 1.0)
            spin.setDecimals(4 if step < 1 else 2)
            if value is not None:
                spin.setValue(value)
            return spin
        if kind == GP_WIDGET_DATE:
            spin = QSpinBox()
            spin.setRange(-2147483647, 2147483647)
            if value is not None:
                spin.setValue(value)
            return spin
        return None

    def previewChanged(self, _checked: bool) -> None:
        """Persist preview mode and update capture availability."""
        self._save_current_values()
        self._update_capture_availability()

    def reloadCameraSettings(self) -> None:
        """Reload the camera's own current settings into the dialog.

        Restores settings changed on the camera during this session, drops
        the values saved in this dialog and re-reads the live configuration.
        gphoto2 exposes no factory defaults, so the camera's current
        settings are the closest thing to defaults.
        """
        if self._selected is None or self._capture_pending:
            return
        self.statusLabel.setText(self.tr("Reloading camera settings..."))
        self.statusLabel.repaint()
        try:
            self.camera.release_camera(self._selected)
            self.camera.reset_preferences(self._selected)
        except Exception as error:
            self.statusLabel.setText(self.tr("Could not reload camera settings."))
            QMessageBox.warning(self, self.tr("Camera Error"), str(error))
            return
        self.cameraSelectionChanged(
            self.cameraSelector.currentIndex(), save_current=False
        )

    def reject(self) -> None:
        """Save current preferences before the dialog is dismissed."""
        # Preferences were saved before starting the worker; do not wait on the
        # manager's lock while the camera operation is still in progress.
        if not self._capture_pending:
            self._save_current_values()
        super().reject()

    def capture(self) -> None:
        """Capture the selected image and accept the dialog on success."""
        if self._selected is None or self._capture_pending:
            return
        self._save_current_values()
        # Read the values back from the manager so the worker thread gets a
        # deep copy fully detached from the GUI widgets.
        settings = self.camera.preferences(self._selected).get("settings", {})
        preview = self.previewCheckbox.isChecked() and self.previewCheckbox.isEnabled()
        restore_target = self.restoreTargetCheckbox.isChecked()
        self._capture_pending = True
        self._set_capture_controls_enabled(False)
        self.cameraSelector.setEnabled(False)
        self.statusLabel.setText(self.tr("Capturing preview..." if preview else "Capturing image..."))
        self.statusLabel.repaint()
        signals = _CameraCaptureSignals(QApplication.instance())
        signals.finished.connect(self._captureFinished)
        signals.finished.connect(signals.deleteLater)
        self._capture_signals = signals
        task = _CameraCaptureTask(
            self.camera, self._selected, settings, preview, restore_target, signals
        )
        QThreadPool.globalInstance().start(task)

    def _set_capture_controls_enabled(self, enabled: bool) -> None:
        """Keep camera options fixed while a background capture is running."""
        self.previewCheckbox.setEnabled(enabled and self._preview_available)
        self.restoreTargetCheckbox.setEnabled(enabled and self._selected is not None)
        self.reloadSettingsButton.setEnabled(enabled and self._selected is not None)
        self.reevaluateButton.setEnabled(enabled)
        self.configWidget.setEnabled(enabled)

    def _captureFinished(
        self, image_data: Optional[bytes], error_message: Optional[str]
    ) -> None:
        """Handle capture completion on the GUI thread."""
        self._capture_pending = False
        self._capture_signals = None
        self.cameraSelector.setEnabled(self.cameraSelector.count() > 0)
        self._set_capture_controls_enabled(True)
        self._update_capture_availability()

        if error_message is not None:
            self.statusLabel.setText(self.tr("Capture failed."))
            QMessageBox.warning(self, self.tr("Camera Error"), error_message)
            return

        image = QImage.fromData(image_data or b"")
        if image.isNull():
            self.statusLabel.setText(self.tr("Capture failed."))
            QMessageBox.warning(
                self,
                self.tr("Camera Error"),
                self.tr("The captured data is not a supported image. If the camera shoots RAW, switch its image format to JPEG and try again."),
            )
            return
        self.image = image
        self.accept()

    def reevaluateCameras(self) -> None:
        """Restore changed settings, rediscover cameras, and rebuild selection."""
        self._save_current_values()
        self.captureButton.setEnabled(False)
        self.statusLabel.setText(self.tr("Re-evaluating cameras..."))
        self.statusLabel.repaint()
        try:
            cameras = self.camera.reevaluate()
        except Exception as error:
            self.cameraSelector.setEnabled(False)
            self.statusLabel.setText(self.tr("Could not re-evaluate cameras."))
            QMessageBox.warning(self, self.tr("Camera Error"), str(error))
            return

        # Autodetection can still report a USB camera that is powered off or
        # otherwise unreachable. Only keep candidates that return a live schema.
        available_cameras = []
        for camera in cameras:
            try:
                self.camera.inspect(camera, refresh=True)
            except Exception:
                continue
            available_cameras.append(camera)
        cameras = available_cameras

        last = self.camera.last_camera
        self._changing_camera = True
        self.cameraSelector.blockSignals(True)
        self.cameraSelector.clear()
        for camera in cameras:
            display = f"{camera['model']} ({camera['port']})" if camera["port"] else camera["model"]
            self.cameraSelector.addItem(display, camera)
        self.cameraSelector.blockSignals(False)
        self._changing_camera = False
        if not cameras:
            self._clear_controls()
            self._parameters = []
            self._selected = None
            self._cached_config = False
            self._preview_available = False
            self._standard_capture_available = False
            self.cameraSelector.setEnabled(False)
            self.previewCheckbox.setEnabled(False)
            self.restoreTargetCheckbox.setEnabled(False)
            self.reloadSettingsButton.setEnabled(False)
            self.statusLabel.setText(self.tr("No cameras detected."))
            return
        self.cameraSelector.setEnabled(True)
        self.restoreTargetCheckbox.setEnabled(True)
        index = next((
            i for i, camera in enumerate(cameras)
            if last and self.camera.camera_key(camera) == self.camera.camera_key(last)
        ), 0)
        # Same explicit-call pattern as initializeCameras(): setCurrentIndex
        # is silent when the index does not change (the combo already sits
        # at index 0 after repopulation).
        self.cameraSelector.setCurrentIndex(index)
        self.cameraSelectionChanged(index)
