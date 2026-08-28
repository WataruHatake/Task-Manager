from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from dandori.services.task_service import TaskService

COLOR_OPTIONS = (
    ("グレー", "#8E8E93"),
    ("ブルー", "#6B90B2"),
    ("コーラル", "#ED6A5A"),
    ("パープル", "#B076C8"),
    ("ピンク", "#F2A0B4"),
    ("モス", "#84AE92"),
)


class CategoryManagerDialog(QDialog):
    categories_changed = Signal()

    def __init__(self, task_service: TaskService, parent=None) -> None:
        super().__init__(parent)
        self.task_service = task_service
        self.selected_category_id: str | None = None
        self.setWindowTitle("カテゴリ管理")
        self.setMinimumSize(360, 380)
        self.resize(440, 500)

        title = QLabel("カテゴリ管理")
        title.setObjectName("pageTitle")
        description = QLabel("カテゴリの追加、名称変更、色変更ができます。")
        description.setObjectName("muted")

        self.category_list = QListWidget()
        self.category_list.currentItemChanged.connect(self._select_category)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("カテゴリ名")
        self.color_combo = QComboBox()
        for label, color in COLOR_OPTIONS:
            self.color_combo.addItem(label, color)
            index = self.color_combo.count() - 1
            self.color_combo.setItemData(index, QColor(color), Qt.ItemDataRole.DecorationRole)

        new_button = QPushButton("新規")
        new_button.clicked.connect(self._new_category)
        save_button = QPushButton("保存")
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self._save_category)
        self.delete_button = QPushButton("削除")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.clicked.connect(self._delete_category)
        close_button = QPushButton("閉じる")
        close_button.clicked.connect(self.accept)

        editor = QVBoxLayout()
        editor.setSpacing(8)
        editor.addWidget(QLabel("カテゴリ名"))
        editor.addWidget(self.name_edit)
        editor.addWidget(QLabel("表示色"))
        editor.addWidget(self.color_combo)

        actions = QHBoxLayout()
        actions.addWidget(new_button)
        actions.addWidget(self.delete_button)
        actions.addStretch()
        actions.addWidget(close_button)
        actions.addWidget(save_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 18)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(self.category_list, 1)
        layout.addLayout(editor)
        layout.addLayout(actions)
        self._reload_categories()

    def _reload_categories(self, preferred_id: str | None = None) -> None:
        self.category_list.clear()
        selected_row = 0
        for row, category in enumerate(self.task_service.list_categories()):
            item = QListWidgetItem(f"●  {category.name}")
            item.setData(Qt.ItemDataRole.UserRole, category.id)
            item.setData(Qt.ItemDataRole.UserRole + 1, category.name)
            item.setData(Qt.ItemDataRole.UserRole + 2, category.color)
            item.setForeground(QColor(category.color))
            self.category_list.addItem(item)
            if category.id == preferred_id:
                selected_row = row
        if self.category_list.count():
            self.category_list.setCurrentRow(selected_row)
        else:
            self._new_category()

    def _select_category(self, current: QListWidgetItem | None, _previous=None) -> None:
        if current is None:
            return
        self.selected_category_id = current.data(Qt.ItemDataRole.UserRole)
        name = current.data(Qt.ItemDataRole.UserRole + 1)
        color = current.data(Qt.ItemDataRole.UserRole + 2)
        self.name_edit.setText(name)
        color_index = self.color_combo.findData(color)
        self.color_combo.setCurrentIndex(max(0, color_index))
        is_default = name == "未分類"
        self.name_edit.setEnabled(not is_default)
        self.delete_button.setEnabled(not is_default)

    def _new_category(self) -> None:
        self.category_list.clearSelection()
        self.selected_category_id = None
        self.name_edit.setEnabled(True)
        self.name_edit.clear()
        self.color_combo.setCurrentIndex(0)
        self.delete_button.setEnabled(False)
        self.name_edit.setFocus()

    def _save_category(self) -> None:
        try:
            if self.selected_category_id is None:
                category = self.task_service.create_category(
                    self.name_edit.text(), self.color_combo.currentData()
                )
            else:
                category = self.task_service.update_category(
                    self.selected_category_id,
                    self.name_edit.text(),
                    self.color_combo.currentData(),
                )
        except (ValueError, LookupError) as error:
            QMessageBox.warning(self, "保存できません", str(error))
            return
        self.categories_changed.emit()
        self._reload_categories(category.id)

    def _delete_category(self) -> None:
        if self.selected_category_id is None:
            return
        answer = QMessageBox.question(
            self,
            "カテゴリを削除",
            "このカテゴリを削除しますか？登録済みタスクは「未分類」へ移動します。",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.task_service.delete_category(self.selected_category_id)
        except (ValueError, LookupError) as error:
            QMessageBox.warning(self, "削除できません", str(error))
            return
        self.categories_changed.emit()
        self._reload_categories()
