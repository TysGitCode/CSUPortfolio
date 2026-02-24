import os
import sys
import json
import time
import subprocess
from dataclasses import dataclass
from urllib.parse import urlparse

from PySide6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel,
    QObject, QThread, Signal, QSize
)
from PySide6.QtGui import (
    QGuiApplication, QAction, QPainter, QColor, QFontMetrics
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox,
    QTableView, QAbstractItemView, QFrame, QListWidget, QListWidgetItem,
    QProgressBar, QSplitter, QToolButton, QMenu, QSizePolicy,
    QSlider, QStyledItemDelegate
)

# Optional: modern Material theme
try:
    from qt_material import apply_stylesheet
except Exception:
    apply_stylesheet = None


# ----------------------------
# Configuration & Persistence
# ----------------------------
DEFAULT_EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

URLS = [
    "https://mingle-portal.inforcloudsuite.com/v2/AF5F3Z6N66Z5JHZF_PRD/7b10ad79-6a97-44e9-802e-78ab22ee8902?favoriteContext=https://fin-af5f3z6n66z5jhzf-prd.inforcloudsuite.com/fsm/Payables/page/PayablesVendorsUX1?csk.lidkey=f08e535f959830a0683f848c390409e5%26menu=Payables.Vendors%26selectedPanel=Dashboard%26LogicalId=lid%253A%252F%252Finfor.fsm.fsm&LogicalId=lid://infor.fsm.fsm",
    "https://mingle-portal.inforcloudsuite.com/v2/AF5F3Z6N66Z5JHZF_TST/16d5e21e-b15e-4fc5-bb9d-80888a1f280f?favoriteContext=https://fin-af5f3z6n66z5jhzf-tst.inforcloudsuite.com/fsm/GlobalLedger/report/catalog?requestType=reportCatalog%26csk.lidkey=f08e535f959830a0683f848c390409e5%26selectedPanel=printfiles%26LogicalId=lid%253A%252F%252Finfor.fsm.fsm&LogicalId=lid://infor.fsm.fsm",
    "https://mingle-portal.inforcloudsuite.com/v2/AF5F3Z6N66Z5JHZF_TRN/0d6740de-c79e-4c51-b06b-1ed589930b3e?inforWorkspace=infor.fsm.controller",
    "https://mingle-stage01-portal.inforcloudsuite.com/v2/AF5F3Z6N66Z5JHZF_PP1/2c8000b7-19ec-4fa4-a873-3e716288d759?favoriteContext=https:%2F%2Fhcm-af5f3z6n66z5jhzf-pp1.inforcloudsuite.com%2Fhcm%2FAdministration%2Fpage%2FResourceSearchPage%3Fcsk.lidkey%3D6c1c5c1ea968a432ae27aa06e4c73e17%26menu%3DLRCCompAnalysis.Resources%26customhp%3Dtrue%26selectedPanel%3DResourceSearch%26LogicalId%3Dlid:%252F%252Finfor.lawson-ghr.ghr110-prod-useast1&LogicalId=lid:%2F%2Finfor.lawson-ghr.ghr110-prod-useast1"
]

APP_ID = "EdgeURLSelectorQt"
APP_DIR = os.path.join(os.environ.get("APPDATA", os.getcwd()), APP_ID)
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
os.makedirs(APP_DIR, exist_ok=True)


def load_config():
    """
    Config format:
      {
        "edge_path": "...",
        "selected": [true/false ...]     # index-aligned with URLS
        "delay": 1.75,
        "order": ["url1", "url2", ...]   # ordered selected URLs (drag order)
      }
    """
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            if "selected" not in cfg:
                cfg["selected"] = [False] * len(URLS)
            if "delay" not in cfg:
                cfg["delay"] = 1.75
            if "order" not in cfg:
                cfg["order"] = []
            if "edge_path" not in cfg:
                cfg["edge_path"] = DEFAULT_EDGE_PATH
            return cfg
    except Exception:
        return {"edge_path": DEFAULT_EDGE_PATH, "selected": [False] * len(URLS), "delay": 1.75, "order": []}


def save_config(edge_path, selected, delay, order):
    cfg = {"edge_path": edge_path, "selected": selected, "delay": delay, "order": order}
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


# ----------------------------
# Helpers
# ----------------------------
def parse_env_hint(url: str) -> str:
    parsed = urlparse(url)
    parts = (parsed.path or "").strip("/").split("/")
    if len(parts) >= 2:
        second = parts[1]
        if "_" in second:
            return second.split("_")[-1].upper()
    host = (parsed.hostname or "").lower()
    for tag in ("prd", "tst", "trn", "pp1", "dev", "stage"):
        if tag in host:
            return tag.upper()
    return ""


def host_of(url: str) -> str:
    return urlparse(url).hostname or "unknown-host"


def short_path(url: str) -> str:
    p = urlparse(url).path or "/"
    return p if len(p) <= 58 else (p[:55] + "…")


def open_in_edge_guest(edge_path, urls_to_open, delay_sec=1.75, status_cb=None):
    """
    Open each URL in a separate Edge "guest-like" profile directory.
    Uses temp EdgeGuestProfile_1..N directories.
    """
    temp_dir = os.environ.get("TEMP", os.getcwd())
    total = len(urls_to_open)

    for i, url in enumerate(urls_to_open, start=1):
        if status_cb:
            status_cb(f"Opening {i}/{total} …")

        guest_profile_path = os.path.join(temp_dir, f"EdgeGuestProfile_{i}")
        os.makedirs(guest_profile_path, exist_ok=True)

        args = [
            edge_path,
            f"--user-data-dir={guest_profile_path}",
            "--new-window",
            "--start-maximized",
            url
        ]
        subprocess.Popen(args)
        time.sleep(delay_sec)

    if status_cb:
        status_cb("Done.")


# ----------------------------
# Data Model
# ----------------------------
@dataclass
class UrlItem:
    url: str
    selected: bool = False

    @property
    def host(self) -> str:
        return host_of(self.url)

    @property
    def env(self) -> str:
        return parse_env_hint(self.url)

    @property
    def path(self) -> str:
        return short_path(self.url)


class UrlTableModel(QAbstractTableModel):
    COL_SELECTED = 0
    COL_ENV = 1
    COL_HOST = 2
    COL_PATH = 3
    COL_URL = 4

    headers = ["", "ENV", "Host", "Path", "URL"]

    def __init__(self, items: list[UrlItem]):
        super().__init__()
        self.items = items

    def rowCount(self, parent=QModelIndex()):
        return len(self.items)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        return self.headers[section] if orientation == Qt.Horizontal else str(section + 1)

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.NoItemFlags

        base = Qt.ItemIsSelectable | Qt.ItemIsEnabled

        # Make check column explicitly editable + checkable for reliable toggling
        if index.column() == self.COL_SELECTED:
            return base | Qt.ItemIsUserCheckable | Qt.ItemIsEditable

        return base

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        item = self.items[index.row()]
        col = index.column()

        if col == self.COL_SELECTED:
            if role == Qt.CheckStateRole:
                return Qt.Checked if item.selected else Qt.Unchecked
            return None

        if role == Qt.DisplayRole:
            if col == self.COL_ENV:
                return item.env or "—"
            if col == self.COL_HOST:
                return item.host
            if col == self.COL_PATH:
                return item.path
            if col == self.COL_URL:
                return item.url

        if role == Qt.ToolTipRole and col in (self.COL_ENV, self.COL_HOST, self.COL_PATH):
            return item.url

        return None

    def setData(self, index: QModelIndex, value, role=Qt.EditRole):
        if not index.isValid():
            return False

        if index.column() == self.COL_SELECTED and role in (Qt.CheckStateRole, Qt.EditRole):
            # PySide6 may pass Qt.CheckState enum, bool, or int
            if isinstance(value, Qt.CheckState):
                new_state = (value == Qt.CheckState.Checked)
            elif isinstance(value, bool):
                new_state = value
            elif isinstance(value, int):
                new_state = (value == int(Qt.CheckState.Checked))
            else:
                # last-resort fallback for weird values
                s = str(value).strip().lower()
                new_state = s in ("true", "1", "checked", "yes", "y")

            self.items[index.row()].selected = new_state
            self.dataChanged.emit(index, index, [Qt.CheckStateRole])
            return True

        return False

    def select_all(self, state: bool):
        if not self.items:
            return
        self.beginResetModel()
        for it in self.items:
            it.selected = state
        self.endResetModel()

    def selected_urls(self) -> list[str]:
        return [it.url for it in self.items if it.selected]

    def selected_flags(self) -> list[bool]:
        return [bool(it.selected) for it in self.items]


class UrlFilterProxy(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setSortCaseSensitivity(Qt.CaseInsensitive)

    def filterAcceptsRow(self, source_row, source_parent):
        model: UrlTableModel = self.sourceModel()  # type: ignore
        text = self.filterRegularExpression().pattern().strip().lower()
        if not text:
            return True

        it = model.items[source_row]
        hay = f"{it.env} {it.host} {it.path} {it.url}".lower()
        return text in hay


# ----------------------------
# Fancy ENV Chip Delegate
# ----------------------------
class EnvChipDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option, index):
        val = (index.data(Qt.DisplayRole) or "—").strip().upper()
        colors = {
            "PRD": ("#B42318", "#FEE4E2"),
            "TST": ("#B54708", "#FEF0C7"),
            "TRN": ("#5925DC", "#EDE9FE"),
            "PP1": ("#026AA2", "#E0F2FE"),
            "STAGE": ("#026AA2", "#E0F2FE"),
            "DEV": ("#027A48", "#D1FADF"),
            "—": ("#344054", "#F2F4F7")
        }
        fg, bg = colors.get(val, ("#344054", "#F2F4F7"))

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        rect = option.rect.adjusted(8, 6, -8, -6)
        radius = rect.height() / 2

        painter.setPen(QColor(bg))
        painter.setBrush(QColor(bg))
        painter.drawRoundedRect(rect, radius, radius)

        painter.setPen(QColor(fg))
        fm = QFontMetrics(option.font)
        painter.drawText(rect, Qt.AlignCenter, fm.elidedText(val, Qt.ElideRight, rect.width()))
        painter.restore()

    def sizeHint(self, option, index):
        s = super().sizeHint(option, index)
        return QSize(s.width(), max(s.height(), 28))


# ----------------------------
# Draggable Selected List (Drag-order launching)
# ----------------------------
class DraggableSelectedList(QListWidget):
    """
    QListWidget that supports internal drag reorder and emits the current URL order.
    Each QListWidgetItem stores URL in Qt.UserRole.
    """
    orderChanged = Signal(list)

    def __init__(self):
        super().__init__()
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def dropEvent(self, event):
        super().dropEvent(event)
        self.orderChanged.emit(self.current_order())

    def current_order(self) -> list[str]:
        out = []
        for i in range(self.count()):
            it = self.item(i)
            url = it.data(Qt.UserRole)
            if url:
                out.append(url)
        return out


# ----------------------------
# Worker Thread
# ----------------------------
class LauncherWorker(QObject):
    status = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, edge_path: str, urls: list[str], delay: float):
        super().__init__()
        self.edge_path = edge_path
        self.urls = urls
        self.delay = delay

    def run(self):
        try:
            open_in_edge_guest(self.edge_path, self.urls, delay_sec=self.delay, status_cb=self.status.emit)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit()


# ----------------------------
# Main Window
# ----------------------------
class MainWindow(QMainWindow):
    def __init__(self, urls: list[str]):
        super().__init__()
        self.setWindowTitle("Edge URL Launcher — Guest Profiles")
        self.resize(1320, 780)

        self.cfg = load_config()
        self.items = [UrlItem(u) for u in urls]

        # Restore selections
        prev_sel = self.cfg.get("selected", [False] * len(self.items))
        for it, flag in zip(self.items, prev_sel):
            it.selected = bool(flag)

        self.model = UrlTableModel(self.items)
        self.proxy = UrlFilterProxy()
        self.proxy.setSourceModel(self.model)

        # Launch order list (authoritative for launching)
        self.launch_order: list[str] = []
        self._restore_launch_order()

        self._build_ui()
        self._rebuild_selected_list_from_order()
        self._update_counts()

    # ----------------------------
    # Launch order management
    # ----------------------------
    def _restore_launch_order(self):
        """
        Restore saved drag order from config, intersect with current selected URLs,
        then append any selected URLs not already in the saved order.
        """
        selected_set = set(self.model.selected_urls())
        saved_order = self.cfg.get("order", [])
        saved_order = [u for u in saved_order if u in selected_set]

        # append newly selected items not present in saved order
        for u in self.model.selected_urls():
            if u not in saved_order:
                saved_order.append(u)

        self.launch_order = saved_order

    def _sync_launch_order_with_selection(self):
        """
        Keep launch_order in sync with current selection without destroying
        any user-defined drag order:
          - remove deselected
          - append newly selected at end
        """
        selected = self.model.selected_urls()
        selected_set = set(selected)

        # remove deselected
        self.launch_order = [u for u in self.launch_order if u in selected_set]

        # append new selections at end
        for u in selected:
            if u not in self.launch_order:
                self.launch_order.append(u)

    def _rebuild_selected_list_from_order(self):
        """
        Rebuild right pane list widget from launch_order, using each URL stored in item UserRole.
        """
        self.selected_list.blockSignals(True)
        self.selected_list.clear()

        if not self.launch_order:
            it = QListWidgetItem("No URLs selected.")
            it.setFlags(Qt.NoItemFlags)
            self.selected_list.addItem(it)
            self.selected_list.blockSignals(False)
            return

        # Create list entries in order
        url_to_item = {it.url: it for it in self.items}

        for url in self.launch_order:
            it = url_to_item.get(url)
            if not it:
                continue
            label = f"{it.host}   •   {it.env or '—'}   •   {it.path}"
            row = QListWidgetItem(label)
            row.setToolTip(url)
            row.setData(Qt.UserRole, url)
            self.selected_list.addItem(row)

        self.selected_list.blockSignals(False)

    # ----------------------------
    # UI
    # ----------------------------
    def _build_ui(self):
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        # Header Card
        header = QFrame()
        header.setObjectName("HeaderCard")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(16, 14, 16, 14)

        title = QLabel("Select URLs to Open")
        title.setObjectName("Title")
        subtitle = QLabel("Drag to set launch order. Launch opens URLs in that exact order (separate guest-like Edge profiles).")
        subtitle.setObjectName("Subtitle")

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        # Edge path + delay row
        row = QFrame()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)

        self.edge_edit = QLineEdit(self.cfg.get("edge_path", DEFAULT_EDGE_PATH))
        self.edge_edit.setPlaceholderText(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_edge)

        validate_btn = QPushButton("Validate")
        validate_btn.setObjectName("Primary")
        validate_btn.clicked.connect(self._validate_edge)

        delay_label = QLabel("Launch delay (sec)")
        delay_label.setObjectName("Caption")

        self.delay_slider = QSlider(Qt.Horizontal)
        self.delay_slider.setRange(50, 350)  # 0.50s - 3.50s
        self.delay_slider.setValue(int(float(self.cfg.get("delay", 1.75)) * 100))
        self.delay_value = QLabel(f"{self.delay_slider.value()/100:.2f}")
        self.delay_value.setMinimumWidth(48)
        self.delay_slider.valueChanged.connect(lambda v: self.delay_value.setText(f"{v/100:.2f}"))

        row_layout.addWidget(QLabel("Edge path"), 0)
        row_layout.addWidget(self.edge_edit, 1)
        row_layout.addWidget(browse_btn, 0)
        row_layout.addWidget(validate_btn, 0)
        row_layout.addSpacing(12)
        row_layout.addWidget(delay_label, 0)
        row_layout.addWidget(self.delay_slider, 0)
        row_layout.addWidget(self.delay_value, 0)

        # Splitter
        splitter = QSplitter(Qt.Horizontal)

        # Left pane
        left = QFrame()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        topbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search host, env, path, or URL…")
        self.search.textChanged.connect(self._on_search)

        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self._set_all(True))
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(lambda: self._set_all(False))

        self.counts = QLabel("")
        self.counts.setObjectName("Status")

        more_btn = QToolButton()
        more_btn.setText("⋯")
        more_btn.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(more_btn)

        menu.addAction("Copy selected URLs").triggered.connect(self._copy_selected_urls)
        menu.addAction("Copy all URLs").triggered.connect(self._copy_all_urls)
        menu.addSeparator()
        menu.addAction("Select all (filtered)").triggered.connect(self._select_filtered)
        menu.addAction("Clear all (filtered)").triggered.connect(self._clear_filtered)

        more_btn.setMenu(menu)

        topbar.addWidget(self.search, 1)
        topbar.addWidget(select_all_btn)
        topbar.addWidget(clear_btn)
        topbar.addWidget(more_btn)
        topbar.addWidget(self.counts)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(UrlTableModel.COL_HOST, Qt.AscendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.AllEditTriggers)

        # Click-anywhere toggles selection (checkbox column)
        self.table.clicked.connect(self._on_table_clicked)

        # ENV chips
        self.table.setItemDelegateForColumn(UrlTableModel.COL_ENV, EnvChipDelegate(self.table))

        self.table.setColumnWidth(UrlTableModel.COL_SELECTED, 44)
        self.table.setColumnWidth(UrlTableModel.COL_ENV, 90)
        self.table.setColumnWidth(UrlTableModel.COL_HOST, 360)
        self.table.setColumnWidth(UrlTableModel.COL_PATH, 290)
        self.table.setColumnHidden(UrlTableModel.COL_URL, True)

        # Right pane
        right = QFrame()
        right.setObjectName("RightCard")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(14, 14, 14, 14)
        right_layout.setSpacing(10)

        right_title = QLabel("Selected URLs (Drag to reorder launch sequence)")
        right_title.setObjectName("Caption")

        self.selected_list = DraggableSelectedList()
        self.selected_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.selected_list.orderChanged.connect(self._on_drag_order_changed)

        # Context menu for selected list
        self.selected_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.selected_list.customContextMenuRequested.connect(self._selected_list_context_menu)

        bottom = QFrame()
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        self.open_btn = QPushButton("Open Selected (In Drag Order)")
        self.open_btn.setObjectName("Primary")
        self.open_btn.clicked.connect(self._open_selected_in_order)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.progress.setFixedHeight(10)
        self.progress.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.status = QLabel("Ready.")
        self.status.setObjectName("Status")

        bottom_layout.addWidget(self.open_btn)
        bottom_layout.addWidget(self.progress, 1)
        bottom_layout.addWidget(self.status)

        right_layout.addWidget(right_title)
        right_layout.addWidget(self.selected_list, 1)
        right_layout.addWidget(bottom)

        left_layout.addLayout(topbar)
        left_layout.addWidget(self.table, 1)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        root_layout.addWidget(header)
        root_layout.addWidget(row)
        root_layout.addWidget(splitter, 1)

        self.setCentralWidget(root)

        # When model changes, update selection panel without destroying drag order
        self.model.dataChanged.connect(self._on_selection_changed)
        self.model.modelReset.connect(self._on_selection_changed)

        # Table context menu
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_context_menu)

        self._apply_qss()

    def _apply_qss(self):
        self.setStyleSheet("""
            #HeaderCard, #RightCard {
                background: rgba(255,255,255,0.92);
                border: 1px solid rgba(0,0,0,0.08);
                border-radius: 14px;
            }
            QLabel#Title { font-size: 18px; font-weight: 800; }
            QLabel#Subtitle { color: rgba(0,0,0,0.65); }
            QLabel#Status { color: rgba(0,0,0,0.65); }
            QPushButton#Primary { padding: 8px 14px; font-weight: 800; }
            QLineEdit { padding: 8px 10px; }
            QTableView {
                border: 1px solid rgba(0,0,0,0.08);
                border-radius: 10px;
            }
        """)

    # ----------------------------
    # Selection changes -> sync order
    # ----------------------------
    def _on_selection_changed(self, *args, **kwargs):
        self._sync_launch_order_with_selection()
        self._rebuild_selected_list_from_order()
        self._update_counts()

    def _on_drag_order_changed(self, new_order: list):
        """
        Drag reorder is authoritative: update launch_order to the dragged order.
        """
        # If list contains the "No URLs selected." placeholder, ignore
        if len(new_order) == 1 and not new_order[0]:
            return
        self.launch_order = new_order
        self.status.setText("Launch order updated.")
        self._update_counts()

    # ----------------------------
    # Checkbox behavior (reliable)
    # ----------------------------
    def _on_table_clicked(self, proxy_index: QModelIndex):
        if not proxy_index.isValid():
            return
        source_index = self.proxy.mapToSource(proxy_index)
        row = source_index.row()
        check_ix = self.model.index(row, UrlTableModel.COL_SELECTED)
        current = (self.model.data(check_ix, Qt.CheckStateRole) == Qt.Checked)
        self.model.setData(check_ix, Qt.Unchecked if current else Qt.Checked, Qt.CheckStateRole)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            ix = self.table.currentIndex()
            if ix.isValid():
                self._on_table_clicked(ix)
                return
        super().keyPressEvent(event)

    # ----------------------------
    # Context menus
    # ----------------------------
    def _table_context_menu(self, pos):
        ix = self.table.indexAt(pos)
        menu = QMenu(self)

        act_copy = menu.addAction("Copy URL")
        act_open = menu.addAction("Open this URL now")
        menu.addSeparator()
        act_sel = menu.addAction("Select row")
        act_unsel = menu.addAction("Unselect row")

        chosen = menu.exec_(self.table.viewport().mapToGlobal(pos))
        if not ix.isValid():
            return

        src = self.proxy.mapToSource(ix)
        row = src.row()
        url = self.model.items[row].url

        if chosen == act_copy:
            self._copy_text(url)
        elif chosen == act_open:
            self._open_urls([url])
        elif chosen == act_sel:
            self.model.items[row].selected = True
            check_ix = self.model.index(row, UrlTableModel.COL_SELECTED)
            self.model.dataChanged.emit(check_ix, check_ix, [Qt.CheckStateRole])
        elif chosen == act_unsel:
            self.model.items[row].selected = False
            check_ix = self.model.index(row, UrlTableModel.COL_SELECTED)
            self.model.dataChanged.emit(check_ix, check_ix, [Qt.CheckStateRole])

    def _selected_list_context_menu(self, pos):
        it = self.selected_list.itemAt(pos)
        menu = QMenu(self)

        act_copy = menu.addAction("Copy URL")
        act_open = menu.addAction("Open this URL now")
        menu.addSeparator()
        act_remove = menu.addAction("Remove (unselect)")

        chosen = menu.exec_(self.selected_list.viewport().mapToGlobal(pos))
        if not it:
            return

        url = it.data(Qt.UserRole)
        if not url:
            return

        if chosen == act_copy:
            self._copy_text(url)
        elif chosen == act_open:
            self._open_urls([url])
        elif chosen == act_remove:
            # Unselect in model
            for i, model_it in enumerate(self.items):
                if model_it.url == url:
                    model_it.selected = False
                    check_ix = self.model.index(i, UrlTableModel.COL_SELECTED)
                    self.model.dataChanged.emit(check_ix, check_ix, [Qt.CheckStateRole])
                    break

    # ----------------------------
    # Actions
    # ----------------------------
    def _browse_edge(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select msedge.exe",
            os.path.dirname(self.edge_edit.text()),
            "Edge Executable (msedge.exe);;Executables (*.exe);;All Files (*.*)"
        )
        if path:
            self.edge_edit.setText(path)

    def _validate_edge(self):
        path = self.edge_edit.text().strip('"')
        if not path or not os.path.isfile(path):
            QMessageBox.critical(self, "Edge Not Found",
                                 "The path does not point to an existing file.\n\n"
                                 "Update the Microsoft Edge path and try again.")
            self.status.setText("Invalid Edge path.")
            return
        self.status.setText("Edge executable validated.")
        QMessageBox.information(self, "Validated", "Edge path looks good!")

    def _on_search(self, text: str):
        self.proxy.setFilterFixedString(text)
        self._update_counts()

    def _set_all(self, flag: bool):
        self.model.select_all(flag)
        self.status.setText("All URLs selected." if flag else "Selection cleared.")

    def _select_filtered(self):
        for r in range(self.proxy.rowCount()):
            src = self.proxy.mapToSource(self.proxy.index(r, 0))
            self.model.items[src.row()].selected = True
        self.model.layoutChanged.emit()

    def _clear_filtered(self):
        for r in range(self.proxy.rowCount()):
            src = self.proxy.mapToSource(self.proxy.index(r, 0))
            self.model.items[src.row()].selected = False
        self.model.layoutChanged.emit()

    def _update_counts(self):
        total = len(self.items)
        filtered = self.proxy.rowCount()
        selected = len([it for it in self.items if it.selected])
        ordered = len(self.launch_order)
        self.counts.setText(f"{selected} selected • {ordered} ordered • {filtered}/{total} shown")

    def _copy_text(self, text: str):
        QGuiApplication.clipboard().setText(text)
        self.status.setText("Copied to clipboard.")

    def _copy_selected_urls(self):
        urls = self.model.selected_urls()
        if not urls:
            self.status.setText("No URLs selected.")
            return
        self._copy_text("\n".join(urls))

    def _copy_all_urls(self):
        self._copy_text("\n".join([it.url for it in self.items]))

    # ----------------------------
    # Launching (uses drag order)
    # ----------------------------
    def _open_urls(self, urls: list[str]):
        edge_path = self.edge_edit.text().strip('"')
        if not os.path.isfile(edge_path):
            self.status.setText("Edge path invalid.")
            QMessageBox.critical(self, "Edge Not Found", "Edge path is invalid. Please validate/update it.")
            return

        self.open_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.status.setText(f"Opening {len(urls)} URL(s)…")

        delay = self.delay_slider.value() / 100.0

        self.thread = QThread()
        self.worker = LauncherWorker(edge_path=edge_path, urls=urls, delay=delay)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.status.connect(self.status.setText)
        self.worker.error.connect(lambda msg: QMessageBox.critical(self, "Error", msg))
        self.worker.finished.connect(self._launch_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def _open_selected_in_order(self):
        # Ensure order is synced in case selection changed
        self._sync_launch_order_with_selection()

        if not self.launch_order:
            self.status.setText("No URLs selected.")
            QMessageBox.warning(self, "No Selection", "Select at least one URL to open.")
            return

        # Launch exactly in drag order
        self._open_urls(self.launch_order)

    def _launch_finished(self):
        self.progress.setVisible(False)
        self.open_btn.setEnabled(True)
        self.status.setText("Done.")

    # ----------------------------
    # Persist on close
    # ----------------------------
    def closeEvent(self, event):
        # Ensure order matches selection and save it
        self._sync_launch_order_with_selection()
        save_config(
            self.edge_edit.text(),
            self.model.selected_flags(),
            self.delay_slider.value() / 100.0,
            self.launch_order
        )
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)

    # Apply modern Material theme if available
    if apply_stylesheet:
        apply_stylesheet(app, theme="light_blue.xml", extra={"density_scale": "0", "font_size": "13"})

    w = MainWindow(URLS)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()