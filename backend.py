from pathlib import Path
import sys
import copy
from PySide6.QtCore import QObject, Slot, Signal, Property, QThread, QEventLoop, Qt
from PySide6.QtWidgets import (
    QFileDialog, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QFrame, QComboBox, QSlider, QCheckBox, QSpinBox, QToolButton,
    QGroupBox, QScrollArea, QWidget, QStackedWidget, QMessageBox, QInputDialog,
    QSizeGrip
)
from PySide6.QtGui import QIcon, QColor

# ==============================================================================
#   DEBUG CONFIGURATION
# ==============================================================================
DEBUG_MODE = False  # Set to True for verbose logs, False for clean logs


# ==============================================================================
#  CONFIRMATION & PROGRESS DIALOGS
# ==============================================================================

class TaggingConfirmDialog(QDialog):
    def __init__(self, count, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TagGUI Next - Confirm Auto-Tag")
        self.resize(420, 200)
        self.setModal(True)

        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        icon_path = Path(__file__).parent / "assets" / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)

        card = QFrame()
        card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(12)

        header_layout = QHBoxLayout()
        badge = QLabel("✨")
        badge.setStyleSheet("""
            background: rgba(99, 102, 241, 0.2);
            border: 1px solid rgba(99, 102, 241, 0.4);
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 14px;
        """)
        header_layout.addWidget(badge)

        title = QLabel("RUN LOCAL PYTORCH AUTOTAG")
        title.setObjectName("titleLabel")
        header_layout.addWidget(title)
        header_layout.addStretch()
        card_layout.addLayout(header_layout)

        desc = QLabel(
            f"Run local PyTorch auto-tagger for <b>{count}</b> selected image(s)? This will process images using your selected model configuration.")
        desc.setObjectName("descLabel")
        desc.setWordWrap(True)
        card_layout.addWidget(desc)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.clicked.connect(self.reject)

        self.confirm_btn = QPushButton("Start AutoTag")
        self.confirm_btn.setObjectName("confirmBtn")
        self.confirm_btn.clicked.connect(self.accept)

        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.confirm_btn)
        card_layout.addLayout(btn_layout)

        main_layout.addWidget(card)

class DeleteConfirmDialog(QDialog):
    def __init__(self, filename, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TagGUI Next - Confirm Deletion")
        self.resize(420, 200)
        self.setModal(True)

        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        icon_path = Path(__file__).parent / "assets" / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)

        card = QFrame()
        card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(12)

        header_layout = QHBoxLayout()
        badge = QLabel("🗑️")
        badge.setStyleSheet("""
            background: rgba(239, 68, 68, 0.2);
            border: 1px solid rgba(239, 68, 68, 0.4);
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 14px;
        """)
        header_layout.addWidget(badge)

        title = QLabel("DELETE IMAGE & TAGS")
        title.setObjectName("titleLabel")
        header_layout.addWidget(title)
        header_layout.addStretch()
        card_layout.addLayout(header_layout)

        desc = QLabel(
            f"Are you sure you want to delete <b>{filename}</b> and its corresponding <code>.txt</code> tags file? This moves them to the local dataset trash.")
        desc.setObjectName("descLabel")
        desc.setWordWrap(True)
        card_layout.addWidget(desc)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.clicked.connect(self.reject)

        self.confirm_btn = QPushButton("Delete Files")
        self.confirm_btn.setObjectName("deleteBtn")
        self.confirm_btn.clicked.connect(self.accept)

        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.confirm_btn)
        card_layout.addLayout(btn_layout)

        main_layout.addWidget(card)

class TaggingProgressDialog(QDialog):
    def __init__(self, worker_ref=None, parent=None):
        super().__init__(parent)
        self.worker_ref = worker_ref
        self.setWindowTitle("TagGUI Next - Auto-Tagging")
        self.resize(620, 420)
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        icon_path = Path(__file__).parent / "assets" / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)

        card = QFrame()
        card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(12)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        badge = QLabel("✨")
        badge.setStyleSheet("""
            background: rgba(99, 102, 241, 0.2);
            border: 1px solid rgba(99, 102, 241, 0.4);
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 14px;
        """)
        header_layout.addWidget(badge)

        header_text = QVBoxLayout()
        header_text.setSpacing(2)

        title = QLabel("AUTOTAG BATCH PROCESS")
        title.setObjectName("titleLabel")

        self.status_label = QLabel("Initializing engine...")
        self.status_label.setObjectName("statusLabel")

        header_text.addWidget(title)
        header_text.addWidget(self.status_label)
        header_layout.addLayout(header_text)
        header_layout.addStretch()

        card_layout.addLayout(header_layout)

        self.log_output = QTextEdit()
        self.log_output.setObjectName("logOutput")
        self.log_output.setReadOnly(True)
        card_layout.addWidget(self.log_output)

        footer_layout = QHBoxLayout()
        footer_layout.addStretch()

        self.abort_btn = QPushButton("Abort")
        self.abort_btn.setObjectName("cancelBtn")
        self.abort_btn.clicked.connect(self.on_abort_clicked)
        footer_layout.addWidget(self.abort_btn)

        self.close_btn = QPushButton("Done")
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)
        footer_layout.addWidget(self.close_btn)

        card_layout.addLayout(footer_layout)
        main_layout.addWidget(card)

    def on_abort_clicked(self):
        self.abort_btn.setEnabled(False)
        self.status_label.setText("Aborting process...")
        self.status_label.setStyleSheet("color: #f87171; font-size: 11px; font-family: monospace; font-weight: bold;")
        if self.worker_ref:
            self.worker_ref.cancel()

    def append_log(self, text: str):
        self.log_output.append(text)
        sb = self.log_output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def tagging_finished(self):
        self.status_label.setText("Batch Auto-Tagging Complete / Aborted!")
        self.status_label.setStyleSheet("color: #34d399; font-size: 11px; font-family: monospace; font-weight: bold;")
        self.abort_btn.setEnabled(False)
        self.close_btn.setEnabled(True)
        self.setWindowFlags(self.windowFlags() | Qt.WindowCloseButtonHint)
        self.show()

class CustomPromptDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TagGUI Next - Add Custom Prompt")
        self.resize(480, 240)
        self.setMinimumSize(400, 240)
        self.setModal(True)

        # Enable window resize capability alongside frameless hint
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowSystemMenuHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        icon_path = Path(__file__).parent / "assets" / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.dragPosition = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        card = QFrame()
        card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(12)

        # Header
        header_layout = QHBoxLayout()
        badge = QLabel("💬")
        badge.setStyleSheet("""
            background: rgba(99, 102, 241, 0.2);
            border: 1px solid rgba(99, 102, 241, 0.4);
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 14px;
        """)
        header_layout.addWidget(badge)

        title = QLabel("ADD CUSTOM PROMPT / TASK COMMAND")
        title.setObjectName("titleLabel")
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Close X Button
        self.close_icon_btn = QToolButton()
        self.close_icon_btn.setObjectName("dialogCloseBtn")
        self.close_icon_btn.setText("×")
        self.close_icon_btn.setFixedSize(20, 20)
        self.close_icon_btn.setCursor(Qt.PointingHandCursor)
        self.close_icon_btn.setStyleSheet("""
            QToolButton#dialogCloseBtn {
                background: transparent;
                border: none;
                color: #94a3b8;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        self.close_icon_btn.clicked.connect(self.reject)
        header_layout.addWidget(self.close_icon_btn)
        card_layout.addLayout(header_layout)

        # Text Input Area
        self.text_edit = QTextEdit()
        self.text_edit.setObjectName("logOutput")  # Reuses your clean text edit styling
        self.text_edit.setPlaceholderText("Enter custom prompt or task command...")
        self.text_edit.setMinimumHeight(80)
        card_layout.addWidget(self.text_edit)

        # Footer Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.clicked.connect(self.reject)

        self.confirm_btn = QPushButton("Add Prompt")
        self.confirm_btn.setObjectName("confirmBtn")
        self.confirm_btn.clicked.connect(self.accept)

        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.confirm_btn)
        card_layout.addLayout(btn_layout)

        main_layout.addWidget(card)

        # Instantiate QSizeGrip as a direct child for bottom-right corner resizing
        self.size_grip = QSizeGrip(self)
        self.size_grip.setStyleSheet("background: transparent;")
        self.size_grip.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        grip_size = 16
        self.size_grip.setGeometry(self.width() - grip_size - 12, self.height() - grip_size - 12, grip_size, grip_size)
        self.size_grip.raise_()

    # --- Window Dragging Handlers ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragPosition = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.dragPosition is not None:
            self.move(event.globalPosition().toPoint() - self.dragPosition)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.dragPosition = None
        event.accept()

    def get_prompt_text(self):
        return self.text_edit.toPlainText().strip()

class EditPromptDialog(QDialog):
    def __init__(self, title_text="Edit Tag / Caption", initial_value="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("TagGUI Next - Edit")
        self.resize(480, 240)
        self.setMinimumSize(400, 240)
        self.setModal(True)

        # Enable window resize capability alongside frameless hint
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowSystemMenuHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        icon_path = Path(__file__).parent / "assets" / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.dragPosition = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        card = QFrame()
        card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(12)

        # Header
        header_layout = QHBoxLayout()
        badge = QLabel("✏️")
        badge.setStyleSheet("""
            background: rgba(99, 102, 241, 0.2);
            border: 1px solid rgba(99, 102, 241, 0.4);
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 14px;
        """)
        header_layout.addWidget(badge)

        title = QLabel(title_text.upper())
        title.setObjectName("titleLabel")
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Close X Button
        self.close_icon_btn = QToolButton()
        self.close_icon_btn.setObjectName("dialogCloseBtn")
        self.close_icon_btn.setText("×")
        self.close_icon_btn.setFixedSize(20, 20)
        self.close_icon_btn.setCursor(Qt.PointingHandCursor)
        self.close_icon_btn.setStyleSheet("""
            QToolButton#dialogCloseBtn {
                background: transparent;
                border: none;
                color: #94a3b8;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        self.close_icon_btn.clicked.connect(self.reject)
        header_layout.addWidget(self.close_icon_btn)
        card_layout.addLayout(header_layout)

        # Text Input Area
        self.text_edit = QTextEdit()
        self.text_edit.setObjectName("logOutput")
        self.text_edit.setPlainText(initial_value)
        self.text_edit.setMinimumHeight(100)
        card_layout.addWidget(self.text_edit)

        # Footer Buttons (Clean layout without size grip inside it)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.clicked.connect(self.reject)

        self.confirm_btn = QPushButton("Save Changes")
        self.confirm_btn.setObjectName("confirmBtn")
        self.confirm_btn.clicked.connect(self.accept)

        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.confirm_btn)
        card_layout.addLayout(btn_layout)

        main_layout.addWidget(card)

        # Instantiate QSizeGrip as a direct child of the dialog window
        self.size_grip = QSizeGrip(self)
        self.size_grip.setStyleSheet("background: transparent;")
        self.size_grip.raise_()

        self.text_edit.setFocus()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Lock QSizeGrip to the bottom-right corner of the window
        grip_size = 16
        self.size_grip.setGeometry(self.width() - grip_size - 12, self.height() - grip_size - 12, grip_size, grip_size)
        self.size_grip.raise_()

    # --- Window Dragging Handlers ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragPosition = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.dragPosition is not None:
            self.move(event.globalPosition().toPoint() - self.dragPosition)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.dragPosition = None
        event.accept()

    def get_edited_text(self):
        return self.text_edit.toPlainText().strip()


# ------------------------------------
# Settings Dialog UI & Save Logic
# -------------------------------------

class SettingsDialog(QDialog):
    def __init__(self, current_settings, available_interrogators, parent=None):
        super().__init__(parent)

        self.setObjectName("SettingsDialog")
        self.setWindowTitle("TagGUI Next - Interrogator Settings")
        self.resize(520, 720)
        self.setModal(True)

        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        icon_path = Path(__file__).parent / "assets" / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.settings_data = copy.deepcopy(current_settings)
        self.available_interrogators = available_interrogators
        self.dragPosition = None

        # Main layout wrapping card frame
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        card = QFrame()
        card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        # Header
        header_layout = QHBoxLayout()
        badge = QLabel("⚙️")
        badge.setStyleSheet("""
            background: rgba(99, 102, 241, 0.2);
            border: 1px solid rgba(99, 102, 241, 0.4);
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 14px;
        """)
        header_layout.addWidget(badge)

        title = QLabel("INTERROGATOR SETTINGS")
        title.setObjectName("titleLabel")
        header_layout.addWidget(title)
        header_layout.addStretch()

        # --- Top-Right Close Button ---
        self.close_icon_btn = QToolButton()
        self.close_icon_btn.setObjectName("dialogCloseBtn")
        self.close_icon_btn.setText("×")
        self.close_icon_btn.setFixedSize(20, 20)
        self.close_icon_btn.setCursor(Qt.PointingHandCursor)
        self.close_icon_btn.setStyleSheet("""
            QToolButton#dialogCloseBtn {
                background: transparent;
                border: none;
                color: #94a3b8;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        self.close_icon_btn.clicked.connect(self.reject)
        header_layout.addWidget(self.close_icon_btn)
        # -----------------------------------

        card_layout.addLayout(header_layout)

        # Scrollable Form Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        scroll_content = QWidget()
        scroll_content.setObjectName("scrollContent")

        form_layout = QVBoxLayout(scroll_content)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(14)

        # --- Model Selection (Pinned to Top) ---
        form_layout.addWidget(QLabel("Interrogator Model:"))
        self.model_combo = QComboBox()

        # Sort models alphabetically by family first, then by name
        sorted_interrogators = sorted(
            self.available_interrogators,
            key=lambda x: (x.get("family", ""), x.get("name", ""))
        )

        current_family = None
        current_model_id = self.settings_data.get("model_name", "SmilingWolf/wd-eva02-large-tagger-v3")

        for m in sorted_interrogators:
            family = m.get("family", "Other")

            # Insert a category header separator when the family changes
            if family != current_family:
                current_family = family
                self.model_combo.addItem(f"─── {current_family.upper()} ───", None)
                sep_index = self.model_combo.count() - 1

                # Make the separator non-selectable, muted, and bold
                model_model = self.model_combo.model()
                if model_model:
                    item = model_model.item(sep_index)
                    if item:
                        item.setEnabled(False)  # Unselectable divider
                        item.setForeground(QColor("#64748b"))  # Muted slate color
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)

            is_installed = m.get("installed", False)
            is_selected = (m["id"] == current_model_id)

            # Show checkmark ONLY if this specific model is currently selected
            if is_selected:
                display_name = f"  ✓ {m['name']}"
            elif is_installed:
                display_name = f"    {m['name']} (Installed)"
            else:
                display_name = f"    {m['name']}"

            # Add item to combo box
            self.model_combo.addItem(display_name, m["id"])
            index = self.model_combo.count() - 1

            # Apply font color based on installation status or selection
            if is_selected:
                self.model_combo.setItemData(index, QColor("#38bdf8"), Qt.ForegroundRole)  # Bright accent for selected
            elif is_installed:
                self.model_combo.setItemData(index, QColor("#34d399"), Qt.ForegroundRole)  # Emerald for installed
            else:
                self.model_combo.setItemData(index, QColor("#64748b"), Qt.ForegroundRole)  # Dimmed for uninstalled


        index = self.model_combo.findData(current_model_id)
        if index >= 0:
            self.model_combo.setCurrentIndex(index)
        form_layout.addWidget(self.model_combo)

        # --- Variable Settings Stack ---
        self.settings_stack = QStackedWidget()
        self.settings_stack.setMinimumHeight(300)

        # 1. Qwen Settings Group
        self.qwen_group = QGroupBox("Qwen Generation Settings")
        qwen_layout = QVBoxLayout(self.qwen_group)
        qwen_layout.setSpacing(10)

        self.thinking_cb = QCheckBox("Enable Thinking Mode (Temp: 0.6, Top-P: 0.95)")
        self.thinking_cb.setChecked(self.settings_data.get("thinking_mode", False))
        self.thinking_cb.stateChanged.connect(self.on_thinking_toggled)
        qwen_layout.addWidget(self.thinking_cb)

        # Temperature
        temp_header = QHBoxLayout()
        temp_header.addWidget(QLabel("Temperature"))
        self.temp_val_lbl = QLabel(f"{self.settings_data.get('temperature', 0.7):.2f}")
        self.temp_val_lbl.setObjectName("statusLabel")
        temp_header.addWidget(self.temp_val_lbl)
        qwen_layout.addLayout(temp_header)

        self.temp_slider = QSlider(Qt.Horizontal)
        self.temp_slider.setRange(1, 15)
        self.temp_slider.setValue(int(self.settings_data.get("temperature", 0.7) * 10))
        self.temp_slider.valueChanged.connect(lambda v: self.temp_val_lbl.setText(f"{v / 10.0:.2f}"))
        qwen_layout.addWidget(self.temp_slider)

        # Top-P
        top_p_header = QHBoxLayout()
        top_p_header.addWidget(QLabel("Top-P"))
        self.top_p_val_lbl = QLabel(f"{self.settings_data.get('top_p', 0.8):.2f}")
        self.top_p_val_lbl.setObjectName("statusLabel")
        top_p_header.addWidget(self.top_p_val_lbl)
        qwen_layout.addLayout(top_p_header)

        self.top_p_slider = QSlider(Qt.Horizontal)
        self.top_p_slider.setRange(1, 10)
        self.top_p_slider.setValue(int(self.settings_data.get("top_p", 0.8) * 10))
        self.top_p_slider.valueChanged.connect(lambda v: self.top_p_val_lbl.setText(f"{v / 10.0:.2f}"))
        qwen_layout.addWidget(self.top_p_slider)

        # Top-K
        qwen_layout.addWidget(QLabel("Top-K"))
        self.top_k_spin = QSpinBox()
        self.top_k_spin.setRange(1, 100)
        self.top_k_spin.setValue(int(self.settings_data.get("top_k", 20)))
        qwen_layout.addWidget(self.top_k_spin)

        # --- Qwen Max New Tokens ---
        qwen_layout.addWidget(QLabel("Max New Tokens"))
        self.qwen_max_tokens_spin = QSpinBox()
        self.qwen_max_tokens_spin.setRange(10, 2048)
        self.qwen_max_tokens_spin.setValue(int(self.settings_data.get("qwen_max_new_tokens", 256)))
        qwen_layout.addWidget(self.qwen_max_tokens_spin)

        # --- Qwen Min New Tokens ---
        qwen_layout.addWidget(QLabel("Min New Tokens"))
        self.qwen_min_tokens_spin = QSpinBox()
        self.qwen_min_tokens_spin.setRange(0, 512)
        self.qwen_min_tokens_spin.setValue(int(self.settings_data.get("qwen_min_new_tokens", 10)))
        qwen_layout.addWidget(self.qwen_min_tokens_spin)

        # Task Command / Prompt Mode for Qwen
        qwen_layout.addWidget(QLabel("Task Command / Prompt Mode"))
        qwen_cmd_row = QHBoxLayout()
        self.qwen_task_cmd_combo = QComboBox()
        self.qwen_task_cmd_combo.setStyleSheet("background-color: #181a24; color: #e2e8f0;")
        qwen_cmd_row.addWidget(self.qwen_task_cmd_combo, stretch=1)

        self.qwen_add_custom_btn = QPushButton("Add Custom")
        self.qwen_add_custom_btn.setObjectName("cancelBtn")
        self.qwen_add_custom_btn.clicked.connect(self.add_custom_prompt)
        qwen_cmd_row.addWidget(self.qwen_add_custom_btn)
        qwen_layout.addLayout(qwen_cmd_row)

        self.settings_stack.addWidget(self.qwen_group)

        # 2. Tagger Thresholds Group (Styled as QGroupBox)
        self.tagger_group = QGroupBox("WD Tagger Threshold Settings")
        tagger_layout = QVBoxLayout(self.tagger_group)
        tagger_layout.setContentsMargins(12, 12, 12, 12)  # <--- Add clean inner padding
        tagger_layout.setSpacing(6)                      # <--- Reduce spacing between elements (was 10)

        gen_header = QHBoxLayout()
        gen_header.addWidget(QLabel("General Threshold"))
        self.gen_val_lbl = QLabel(f"{self.settings_data.get('general_threshold', 0.35):.2f}")
        self.gen_val_lbl.setObjectName("statusLabel")
        gen_header.addWidget(self.gen_val_lbl)
        tagger_layout.addLayout(gen_header)

        self.gen_slider = QSlider(Qt.Horizontal)
        self.gen_slider.setRange(0, 100)
        self.gen_slider.setValue(int(self.settings_data.get("general_threshold", 0.35) * 100))
        self.gen_slider.valueChanged.connect(lambda v: self.gen_val_lbl.setText(f"{v / 100.0:.2f}"))
        tagger_layout.addWidget(self.gen_slider)

        self.gen_mcut_cb = QCheckBox("Use MCut threshold for General tags")
        self.gen_mcut_cb.setChecked(self.settings_data.get("general_mcut_enabled", False))
        tagger_layout.addWidget(self.gen_mcut_cb)

        char_header = QHBoxLayout()
        char_header.addWidget(QLabel("Character Threshold"))
        self.char_val_lbl = QLabel(f"{self.settings_data.get('character_threshold', 0.85):.2f}")
        self.char_val_lbl.setObjectName("statusLabel")
        char_header.addWidget(self.char_val_lbl)
        tagger_layout.addLayout(char_header)

        self.char_slider = QSlider(Qt.Horizontal)
        self.char_slider.setRange(0, 100)
        self.char_slider.setValue(int(self.settings_data.get("character_threshold", 0.85) * 100))
        self.char_slider.valueChanged.connect(lambda v: self.char_val_lbl.setText(f"{v / 100.0:.2f}"))
        tagger_layout.addWidget(self.char_slider)

        self.char_mcut_cb = QCheckBox("Use MCut threshold for Character tags")
        self.char_mcut_cb.setChecked(self.settings_data.get("character_mcut_enabled", False))
        tagger_layout.addWidget(self.char_mcut_cb)

        tagger_layout.addStretch()  # <--- Pushes all elements to the top and eliminates loose gaps
        self.settings_stack.addWidget(self.tagger_group)

        # 3. Captioner / Task Command Group (Styled as QGroupBox)
        self.captioner_group = QGroupBox("Captioner Generation Settings")
        captioner_layout = QVBoxLayout(self.captioner_group)
        captioner_layout.setSpacing(10)

        captioner_layout.addWidget(QLabel("Task Command / Prompt Mode"))

        captioner_cmd_row = QHBoxLayout()
        self.captioner_task_cmd_combo = QComboBox()
        self.captioner_task_cmd_combo.setStyleSheet("background-color: #181a24; color: #e2e8f0;")
        captioner_cmd_row.addWidget(self.captioner_task_cmd_combo, stretch=1)

        self.captioner_add_custom_btn = QPushButton("Add Custom")
        self.captioner_add_custom_btn.setObjectName("cancelBtn")
        self.captioner_add_custom_btn.clicked.connect(self.add_custom_prompt)
        captioner_cmd_row.addWidget(self.captioner_add_custom_btn)

        captioner_layout.addLayout(captioner_cmd_row)

        # Do Sample Checkbox
        self.captioner_do_sample_cb = QCheckBox("Do Sample (Sampling Generation)")
        self.captioner_do_sample_cb.setChecked(self.settings_data.get("captioner_do_sample", True))
        captioner_layout.addWidget(self.captioner_do_sample_cb)

        # Temperature
        cap_temp_header = QHBoxLayout()
        cap_temp_header.addWidget(QLabel("Temperature"))
        self.cap_temp_val_lbl = QLabel(f"{self.settings_data.get('captioner_temperature', 0.7):.2f}")
        self.cap_temp_val_lbl.setObjectName("statusLabel")
        cap_temp_header.addWidget(self.cap_temp_val_lbl)
        captioner_layout.addLayout(cap_temp_header)

        self.cap_temp_slider = QSlider(Qt.Horizontal)
        self.cap_temp_slider.setRange(1, 20)  # 0.1 to 2.0
        self.cap_temp_slider.setValue(int(self.settings_data.get("captioner_temperature", 0.7) * 10))
        self.cap_temp_slider.valueChanged.connect(lambda v: self.cap_temp_val_lbl.setText(f"{v / 10.0:.2f}"))
        captioner_layout.addWidget(self.cap_temp_slider)

        # Repetition Penalty
        cap_rep_header = QHBoxLayout()
        cap_rep_header.addWidget(QLabel("Repetition Penalty"))
        self.cap_rep_val_lbl = QLabel(f"{self.settings_data.get('captioner_repetition_penalty', 1.2):.2f}")
        self.cap_rep_val_lbl.setObjectName("statusLabel")
        cap_rep_header.addWidget(self.cap_rep_val_lbl)
        captioner_layout.addLayout(cap_rep_header)

        self.cap_rep_slider = QSlider(Qt.Horizontal)
        self.cap_rep_slider.setRange(10, 20)  # 1.0 to 2.0
        self.cap_rep_slider.setValue(int(self.settings_data.get("captioner_repetition_penalty", 1.2) * 10))
        self.cap_rep_slider.valueChanged.connect(lambda v: self.cap_rep_val_lbl.setText(f"{v / 10.0:.2f}"))
        captioner_layout.addWidget(self.cap_rep_slider)

        # Max New Tokens
        captioner_layout.addWidget(QLabel("Max New Tokens"))
        self.cap_max_tokens_spin = QSpinBox()
        self.cap_max_tokens_spin.setRange(10, 512)
        self.cap_max_tokens_spin.setValue(int(self.settings_data.get("captioner_max_new_tokens", 150)))
        captioner_layout.addWidget(self.cap_max_tokens_spin)

        # Min Length
        self.cap_min_len_label = QLabel("Min Length")
        captioner_layout.addWidget(self.cap_min_len_label)
        self.cap_min_len_spin = QSpinBox()
        self.cap_min_len_spin.setRange(0, 200)
        self.cap_min_len_spin.setValue(int(self.settings_data.get("captioner_min_length", 30)))
        captioner_layout.addWidget(self.cap_min_len_spin)

        # Num Beams
        captioner_layout.addWidget(QLabel("Num Beams"))
        self.cap_beams_spin = QSpinBox()
        self.cap_beams_spin.setRange(1, 10)
        self.cap_beams_spin.setValue(int(self.settings_data.get("captioner_num_beams", 3)))
        captioner_layout.addWidget(self.cap_beams_spin)

        self.settings_stack.addWidget(self.captioner_group)

        captioner_layout.addStretch(1)  # Pushes all visible controls to the top
        form_layout.addWidget(self.settings_stack)


        # --- AutoTag Mode (Pinned to Bottom of Form) ---
        form_layout.addWidget(QLabel("AutoTag Mode:"))
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItem("Add to existing tags", "add")
        self.strategy_combo.addItem("Replace existing tags (keep keywords)", "replace")
        strat_val = self.settings_data.get("tag_strategy", "add")
        self.strategy_combo.setCurrentIndex(0 if strat_val == "add" else 1)
        form_layout.addWidget(self.strategy_combo)

        scroll.setWidget(scroll_content)
        card_layout.addWidget(scroll)

        # --- Footer Buttons ---
        btn_layout = QHBoxLayout()

        self.reset_btn = QPushButton("Reset Defaults")
        self.reset_btn.setObjectName("cancelBtn")
        self.reset_btn.clicked.connect(self.reset_to_defaults)
        btn_layout.addWidget(self.reset_btn)

        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.clicked.connect(self.reject)

        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setObjectName("confirmBtn")
        self.save_btn.clicked.connect(self.accept)

        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        card_layout.addLayout(btn_layout)

        main_layout.addWidget(card)

        self.model_combo.currentIndexChanged.connect(self.update_visibility)
        self.update_visibility()

    # --- Window Dragging Handlers ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragPosition = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.dragPosition is not None:
            self.move(event.globalPosition().toPoint() - self.dragPosition)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.dragPosition = None
        event.accept()

    def on_thinking_toggled(self, state):
        if state == Qt.Checked.value or state == 2:
            self.temp_slider.setValue(6)
            self.top_p_slider.setValue(9)
            self.top_k_spin.setValue(20)
        else:
            self.temp_slider.setValue(7)
            self.top_p_slider.setValue(8)
            self.top_k_spin.setValue(20)

    def add_custom_prompt(self):
        dialog = CustomPromptDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            text = dialog.get_prompt_text()
            if text:
                cmd = text
                if "custom_commands" not in self.settings_data:
                    self.settings_data["custom_commands"] = []
                if cmd not in self.settings_data["custom_commands"]:
                    self.settings_data["custom_commands"].append(cmd)
                self.update_visibility()
                if self.qwen_group.isVisible():
                    self.qwen_task_cmd_combo.setCurrentText(cmd)
                elif self.captioner_group.isVisible():
                    self.captioner_task_cmd_combo.setCurrentText(cmd)

# ---------------------------------------------
#    Reset to Default Values
# ---------------------------------------------
    def reset_to_defaults(self):
        selected_id = self.model_combo.currentData()
        model_info = next((m for m in self.available_interrogators if m["id"] == selected_id), None)
        category = model_info.get("category", "") if model_info else ""

        if category in ["qwen", "joycaption", "llama"]:  # <--- Updated condition
            self.thinking_cb.setChecked(False)
            self.temp_slider.setValue(7)
            self.top_p_slider.setValue(8)
            self.top_k_spin.setValue(20)
            self.qwen_max_tokens_spin.setValue(256)
            self.qwen_min_tokens_spin.setValue(10)
            self.qwen_task_cmd_combo.setCurrentIndex(0)

        elif category == "tagger":
            self.gen_slider.setValue(35)
            self.gen_mcut_cb.setChecked(False)
            self.char_slider.setValue(85)
            self.char_mcut_cb.setChecked(False)

        elif category in ["florence2", "moondream", "captioner"]:
            self.captioner_task_cmd_combo.setCurrentIndex(0)
            self.captioner_do_sample_cb.setChecked(True)
            self.cap_temp_slider.setValue(7)
            self.cap_rep_slider.setValue(12)
            self.cap_max_tokens_spin.setValue(150)
            self.cap_min_len_spin.setValue(30)
            self.cap_beams_spin.setValue(3)

        self.strategy_combo.setCurrentIndex(0)

    def update_visibility(self):
        selected_id = self.model_combo.currentData()
        model_info = next((m for m in self.available_interrogators if m["id"] == selected_id), None)
        category = model_info.get("category", "") if model_info else ""
        family_name = model_info.get("family", "Captioner") if model_info else "Captioner"

        # Get default commands specific to THIS model family, avoiding cross-contamination
        default_cmds = list(model_info.get("commands", ["<CAPTION>", "<DETAILED_CAPTION>"])) if model_info else ["<CAPTION>", "<DETAILED_CAPTION>"]

        # Only look up model-specific saved commands; DO NOT fallback to a global default task_command across families
        model_commands_dict = self.settings_data.get("model_commands", {})
        current_cmd = model_commands_dict.get(selected_id, default_cmds[0])

        if DEBUG_MODE:
            print(f"[DEBUG LOAD] Model ID: {selected_id} | Family: {family_name} | Category: {category} | Target Command: {current_cmd}")

        # Build unified command list (Model Defaults + Saved Custom Prompts)
        cmds = list(default_cmds)
        customs = self.settings_data.get("custom_commands", [])

        for c in customs:
            if c not in cmds:
                cmds.append(c)

        if category in ["qwen", "joycaption", "llama"]:
            self.settings_stack.setCurrentWidget(self.qwen_group)
            self.qwen_group.setVisible(True)
            self.tagger_group.setVisible(False)
            self.captioner_group.setVisible(False)

            # Title update for clarity
            self.qwen_group.setTitle(f"{family_name} (LLM) Generation Settings")

            # Show Max & Min tokens, Temp, Top-P, Top-K
            self.qwen_max_tokens_spin.setVisible(True)
            self.qwen_min_tokens_spin.setVisible(True)

            self.qwen_task_cmd_combo.blockSignals(True)
            self.qwen_task_cmd_combo.clear()  # <--- Prevents duplicate entries piling up
            for cmd in cmds:
                self.qwen_task_cmd_combo.addItem(cmd)

            idx = self.qwen_task_cmd_combo.findText(current_cmd)
            self.qwen_task_cmd_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self.qwen_task_cmd_combo.blockSignals(False)

        elif category in ["florence2", "moondream", "captioner"]:
            self.settings_stack.setCurrentWidget(self.captioner_group)
            self.captioner_group.setVisible(True)
            self.qwen_group.setVisible(False)
            self.tagger_group.setVisible(False)

            self.captioner_group.setTitle(f"{family_name} Generation Settings")

            # --- DYNAMIC FLORENCE-2 CONTROLS & SPACING ---
            is_florence = (category == "florence2")

            # 1. Toggle visibility for both the spinbox and its matching label
            self.cap_min_len_spin.setVisible(not is_florence)
            if hasattr(self, "cap_min_len_label"):
                self.cap_min_len_label.setVisible(not is_florence)

            # 2. Keep layout compact by enforcing minimal spacing/margins
            # (Ensures hidden widgets don't leave structural gaps)
            captioner_layout = self.captioner_group.layout()
            if captioner_layout:
                captioner_layout.activate()

            self.captioner_task_cmd_combo.blockSignals(True)
            self.captioner_task_cmd_combo.clear()
            for cmd in cmds:
                self.captioner_task_cmd_combo.addItem(cmd)

            idx = self.captioner_task_cmd_combo.findText(current_cmd)
            self.captioner_task_cmd_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self.captioner_task_cmd_combo.blockSignals(False)

        elif category == "tagger":
            self.settings_stack.setCurrentWidget(self.tagger_group)
            self.tagger_group.setVisible(True)
            self.qwen_group.setVisible(False)
            self.captioner_group.setVisible(False)
        else:
            self.qwen_group.setVisible(False)
            self.tagger_group.setVisible(False)
            self.captioner_group.setVisible(False)


    # -------------------------------------------------------
    #           Update Settings
    # -------------------------------------------------------
    def get_updated_settings(self):
        self.settings_data["model_name"] = self.model_combo.currentData()
        self.settings_data["thinking_mode"] = self.thinking_cb.isChecked()
        self.settings_data["temperature"] = self.temp_slider.value() / 10.0
        self.settings_data["top_p"] = self.top_p_slider.value() / 10.0
        self.settings_data["top_k"] = self.top_k_spin.value()
        self.settings_data["qwen_max_new_tokens"] = self.qwen_max_tokens_spin.value()
        self.settings_data["qwen_min_new_tokens"] = self.qwen_min_tokens_spin.value()
        self.settings_data["general_threshold"] = self.gen_slider.value() / 100.0
        self.settings_data["general_mcut_enabled"] = self.gen_mcut_cb.isChecked()
        self.settings_data["character_threshold"] = self.char_slider.value() / 100.0
        self.settings_data["character_mcut_enabled"] = self.char_mcut_cb.isChecked()
        self.settings_data["tag_strategy"] = self.strategy_combo.currentData()
        self.settings_data["captioner_do_sample"] = self.captioner_do_sample_cb.isChecked()
        self.settings_data["captioner_temperature"] = self.cap_temp_slider.value() / 10.0
        self.settings_data["captioner_repetition_penalty"] = self.cap_rep_slider.value() / 10.0
        self.settings_data["captioner_max_new_tokens"] = self.cap_max_tokens_spin.value()
        self.settings_data["captioner_min_length"] = self.cap_min_len_spin.value()
        self.settings_data["captioner_num_beams"] = self.cap_beams_spin.value()

        if not isinstance(self.settings_data.get("model_commands"), dict):
            self.settings_data["model_commands"] = {}

        selected_id = self.model_combo.currentData()
        model_info = next((m for m in self.available_interrogators if m["id"] == selected_id), None)
        default_cmds = model_info.get("commands", []) if model_info else []

        active_txt = ""
        if self.settings_stack.currentWidget() == self.qwen_group:
            active_txt = self.qwen_task_cmd_combo.currentText()
        elif self.settings_stack.currentWidget() == self.captioner_group:
            active_txt = self.captioner_task_cmd_combo.currentText()

        if active_txt:
            self.settings_data["task_command"] = active_txt
            # Only record to model_commands if it's not a default command bleeding over
            self.settings_data["model_commands"][selected_id] = active_txt

            # Strictly guard custom_commands: never add model built-in defaults here
            if active_txt not in default_cmds:
                if "custom_commands" not in self.settings_data:
                    self.settings_data["custom_commands"] = []
                if active_txt not in self.settings_data["custom_commands"]:
                    self.settings_data["custom_commands"].append(active_txt)

            if DEBUG_MODE:
                print(f"[DEBUG SAVE] Active Command for Model {selected_id} -> {active_txt}")

        if DEBUG_MODE:
            print("==================================================")
            print("[DEBUG SAVE SETTINGS] Final Dictionary Payload:")
            for key, val in self.settings_data.items():
                print(f"  • {key}: {val}")
            print("==================================================")

        return self.settings_data