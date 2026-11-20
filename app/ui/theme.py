"""界面配色与样式表。"""
from __future__ import annotations

from pathlib import Path

COLORS = {
    "bg": "#12141b",
    "panel": "#191c25",
    "panel_alt": "#20242f",
    "border": "#2b3040",
    "text": "#e8eaf2",
    "muted": "#8b93a7",
    "accent": "#5b8def",
    "accent_hover": "#739ff5",
    "danger": "#eb5757",
    "success": "#2ecc71",
    "warning": "#f2c94c",
}

STYLESHEET_TEMPLATE = """
* {
    font-family: "Microsoft YaHei UI", "Segoe UI", "PingFang SC", sans-serif;
    font-size: 13px;
    color: #e8eaf2;
}
QMainWindow, QDialog {
    background: #12141b;
}
QWidget#Page, QScrollArea, QScrollArea > QWidget > QWidget {
    background: transparent;
}
QFrame#Card {
    background: #191c25;
    border: 1px solid #2b3040;
    border-radius: 14px;
}
QLabel#SectionTitle {
    font-size: 14px;
    font-weight: 600;
    color: #dfe3ee;
}
QLabel#Muted, QLabel#Hint {
    color: #8b93a7;
}
QLabel#FileName {
    font-size: 15px;
    font-weight: 600;
}
QLabel#Error {
    color: #ff7a7a;
}
QLabel#Success {
    color: #2ecc71;
}
QLabel#Chip {
    background: #20242f;
    border: 1px solid #2b3040;
    border-radius: 9px;
    padding: 2px 9px;
    color: #aab2c5;
    font-size: 12px;
}
QPushButton {
    background: #232837;
    border: 1px solid #2f3546;
    border-radius: 8px;
    padding: 7px 14px;
    color: #dfe3ee;
}
QPushButton:hover {
    background: #2a3042;
    border-color: #3b4358;
}
QPushButton:pressed {
    background: #202432;
}
QPushButton:disabled {
    color: #5c6478;
    background: #1b1f2a;
    border-color: #262b38;
}
QPushButton#Primary {
    background: #5b8def;
    border: none;
    color: #ffffff;
    font-weight: 600;
    padding: 9px 22px;
}
QPushButton#Primary:hover {
    background: #739ff5;
}
QPushButton#Primary:disabled {
    background: #303a52;
    color: #7f879b;
}
QPushButton#Ghost {
    background: transparent;
    border: 1px solid transparent;
    color: #9aa3b7;
    padding: 6px 10px;
}
QPushButton#Ghost:hover {
    background: #20242f;
    color: #e8eaf2;
}
QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 5px 8px;
    color: #c9cfdd;
}
QToolButton:hover {
    background: #232837;
    color: #ffffff;
}
QToolButton:checked {
    background: #2b3d63;
    color: #9dbcff;
}
QSlider {
    background: transparent;
}
QMenu {
    background: #1b1f2a;
    border: 1px solid #2a3040;
    border-radius: 8px;
    padding: 6px;
}
QMenu::item {
    padding: 7px 22px 7px 14px;
    border-radius: 6px;
    color: #cfd6e6;
}
QMenu::item:selected {
    background: #2b3d63;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background: #262b38;
    margin: 4px 8px;
}
QSlider::groove:horizontal {
    height: 3px;
    background: #2b3040;
    border-radius: 1px;
}
QSlider::sub-page:horizontal {
    background: #4d6fae;
    border-radius: 1px;
}
QSlider::handle:horizontal {
    width: 10px;
    height: 10px;
    margin: -4px 0;
    border-radius: 5px;
    background: #c2cde4;
}
QSlider::handle:horizontal:hover {
    background: #ffffff;
}
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {
    background: #1d212c;
    border: 1px solid #2f3546;
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: #5b8def;
}
QComboBox:hover, QLineEdit:hover {
    border-color: #3b4358;
}
QComboBox:focus, QLineEdit:focus {
    border-color: #5b8def;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QComboBox::down-arrow {
    image: url("$ARROW");
    width: 10px;
    height: 6px;
    margin-right: 8px;
}
QComboBox QAbstractItemView {
    background: #1d212c;
    border: 1px solid #2f3546;
    selection-background-color: #2b3d63;
    outline: none;
    padding: 4px;
}
QProgressBar {
    background: #1d212c;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}
QProgressBar::chunk {
    background: #5b8def;
    border-radius: 4px;
}
QPlainTextEdit, QTextEdit {
    background: #151821;
    border: 1px solid #2b3040;
    border-radius: 8px;
    color: #a8b0c2;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 11px;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #333a4c;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #414a61;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #333a4c;
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::add-line, QScrollBar::sub-line {
    width: 0;
    height: 0;
}
QScrollBar::add-page, QScrollBar::sub-page {
    background: transparent;
}
QSplitter::handle {
    background: #232837;
}
QToolTip {
    background: #232837;
    color: #e8eaf2;
    border: 1px solid #394054;
    padding: 5px 8px;
}
QFrame#Divider {
    background: #262b38;
    max-height: 1px;
    min-height: 1px;
}
QWidget#Shell {
    background: #12141b;
}
QFrame#Ribbon {
    background: #151922;
    border-bottom: 1px solid #262b38;
}
QLabel#Logo {
    font-size: 16px;
    font-weight: 700;
    color: #f4f6fb;
}
QLabel#LogoSub {
    font-size: 10.5px;
    color: #7d8598;
}
QLabel#ProjectName {
    font-size: 13px;
    font-weight: 600;
    color: #dfe3ee;
}
QFrame#VLine {
    background: #262b38;
    max-width: 1px;
    min-width: 1px;
    margin: 4px 0;
}
QFrame#Transport {
    background: #151922;
    border-top: 1px solid #262b38;
}
QLabel#Timecode {
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12.5px;
    color: #c3cada;
}
QLabel#DialogTitle {
    font-size: 19px;
    font-weight: 700;
    color: #f4f6fb;
}
QFrame#Panel {
    background: #151922;
    border: 1px solid #262b38;
    border-radius: 14px;
}
QListWidget, QTreeWidget, QTableWidget {
    background: transparent;
    border: none;
}
"""

_ARROW_ICON = (Path(__file__).resolve().parent / "assets" / "chevron-down.svg").as_posix()

STYLESHEET = STYLESHEET_TEMPLATE.replace("$ARROW", _ARROW_ICON)
