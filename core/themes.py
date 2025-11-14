"""
UI themes and styles for the application.
Migrated from arr_omnitool.py dark theme styling.
"""

from PyQt6.QtWidgets import QApplication
from enum import Enum

# Migrated from arr_omnitool.py - dark theme stylesheet
DARK_STYLESHEET = """
QMainWindow, QDialog, QWidget {
    background-color: #1e1e1e;
    color: #d4d4d4;
}
QTabWidget::pane {
    border: 1px solid #3c3c3c;
    background-color: #252526;
}
QTabBar::tab {
    background-color: #2d2d30;
    color: #d4d4d4;
    padding: 8px 12px;
    border: 1px solid #3c3c3c;
}
QTabBar::tab:selected {
    background-color: #1e1e1e;
    border-bottom-color: #007acc;
}
QTableWidget {
    background-color: #252526;
    alternate-background-color: #2d2d30;
    gridline-color: #3c3c3c;
    color: #d4d4d4;
}
QTableWidget::item:selected {
    background-color: #094771;
}
QHeaderView::section {
    background-color: #2d2d30;
    color: #d4d4d4;
    padding: 4px;
    border: 1px solid #3c3c3c;
}
QPushButton {
    background-color: #0e639c;
    color: #ffffff;
    border: none;
    padding: 5px 15px;
    border-radius: 2px;
}
QPushButton:hover {
    background-color: #1177bb;
}
QPushButton:disabled {
    background-color: #3c3c3c;
    color: #858585;
}
QLineEdit, QTextEdit, QComboBox {
    background-color: #3c3c3c;
    color: #d4d4d4;
    border: 1px solid #555555;
    padding: 3px;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #007acc;
}
QCheckBox, QLabel {
    color: #d4d4d4;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #555555;
    background-color: #3c3c3c;
}
QCheckBox::indicator:checked {
    background-color: #007acc;
    border: 1px solid #007acc;
}
QMenuBar {
    background-color: #2d2d30;
    color: #d4d4d4;
}
QMenu {
    background-color: #2d2d30;
    color: #d4d4d4;
    border: 1px solid #3c3c3c;
}
QMenu::item:selected {
    background-color: #094771;
}
QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 12px;
}
QScrollBar::handle:vertical {
    background-color: #555555;
    border-radius: 6px;
}
QComboBox::drop-down {
    border: none;
    background-color: #555555;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid #d4d4d4;
    margin-right: 5px;
}
"""

# Light theme placeholder for future implementation
LIGHT_STYLESHEET = """
/* Light theme can be added here in future */
QMainWindow, QDialog, QWidget {
    background-color: #ffffff;
    color: #000000;
}
"""


class Theme(Enum):
    """Theme selection enumeration."""
    DARK = "Dark"
    LIGHT = "Light"


def apply_theme(app: QApplication, theme: Theme):
    """
    Apply a theme to the entire application.
    
    Args:
        app: QApplication instance
        theme: Theme enum value (DARK or LIGHT)
    """
    if theme == Theme.DARK:
        app.setStyleSheet(DARK_STYLESHEET)
    elif theme == Theme.LIGHT:
        app.setStyleSheet(LIGHT_STYLESHEET)
    else:
        app.setStyleSheet("")  # Default Qt theme
