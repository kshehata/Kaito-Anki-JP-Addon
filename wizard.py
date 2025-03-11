from __future__ import annotations

import os
import sys
import requests
import json
import urllib.parse
from typing import Optional, List
from functools import partial

from anki.hooks import addHook
from anki.notes import Note
from aqt import mw
from aqt.editor import Editor
from aqt.qt import *
from aqt.utils import showInfo, restoreGeom, saveGeom

from .notetypes import isJapaneseNoteType
from .prompt_image_page import PromptImagePage
from .mnemonic_page import MnemonicPage

config = mw.addonManager.getConfig(__name__)

srcField = config["srcField"]
englishField = config["englishField"]
imageField = config.get("imageField", "Image")  # Add default image field
mnemonicField = config.get("mnemonicField", "Mnemonic")  # Add default mnemonic field
supportDir = os.path.join(os.path.dirname(__file__), "support")


# Overall Wizard
##########################################################################

class VocabWizard(QDialog):
    def __init__(self, parent, japanese_text, english_text):
        super().__init__(parent)
        self.setWindowTitle("Kaito's Vocab Wizard")
        self.japanese_text = japanese_text
        self.english_text = english_text
        self.setup_ui()

        # Trigger searches on startup
        self.prompt_image_page.search_images()
        self.mnemonic_page.generate_mnemonics()

    def setup_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Header with Japanese and English text
        header_layout = QHBoxLayout()
        japanese_label = QLabel("Japanese:")
        self.japanese_display = QLabel(self.japanese_text)
        self.japanese_display.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(japanese_label)
        header_layout.addWidget(self.japanese_display)

        english_label = QLabel("English:")
        self.english_display = QLabel(self.english_text)
        self.english_display.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(english_label)
        header_layout.addWidget(self.english_display)

        header = QWidget()
        header.setLayout(header_layout)
        layout.addWidget(header)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        self.prompt_image_page = PromptImagePage(self, self.japanese_text, self.english_text)
        self.tabs.addTab(self.prompt_image_page, "Prompt Image")

        self.mnemonic_page = MnemonicPage(self, self.japanese_text, self.english_text)
        self.tabs.addTab(self.mnemonic_page, "Mnemonic")
        
        # Add standard buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_prompt_image(self):
        return self.prompt_image_page.get_prompt_html()

    def get_mnemonic(self):
        return self.mnemonic_page.get_selected_mnemonic()


def on_trigger_wizard_button(editor: Editor):
    """Handle the generate reading button click."""
    config = mw.addonManager.getConfig(__name__)
    if "srcField" not in config:
        showInfo("Please configure the source field in the addon settings.")
        return
    if "englishField" not in config:
        showInfo("Please configure the English field in the addon settings.")
        return

    srcField = config["srcField"]
    englishField = config["englishField"]

    note = editor.note
    if not note or not isJapaneseNoteType(note.note_type()["name"]):
        showInfo("This is not a Japanese note type.")
        return
    
    # Check if source field exists
    if srcField not in note:
        showInfo(f"This note type is missing the required field: {srcField}")
        return
    
    if englishField not in note:
        showInfo(f"This note type is missing the required field: {englishField}")
        return
    
    # Get source and English text from note.
    japanese_text = mw.col.media.strip(note[srcField])
    if not japanese_text:
        showInfo(f"The field '{srcField}' is empty.")
        return
    english_text = note[englishField]
    
    # Show the dialog
    dialog = VocabWizard(editor.parentWindow, japanese_text, english_text)
    if dialog.exec():
        prompt_image = dialog.get_prompt_image()
        if prompt_image and imageField in note:
            note[imageField] = prompt_image

        mnemonic = dialog.get_mnemonic()
        if mnemonic and mnemonicField in note:
            note[mnemonicField] = mnemonic

        editor.loadNote()
        editor.web.setFocus()


def add_wizard_button(buttons, editor):
    """Add a button to the editor toolbar."""
    icon_path = os.path.join(os.path.dirname(__file__), "icons", "reading.svg")
    
    if os.path.exists(icon_path):
        icon = icon_path
    else:
        icon = "text-speak"

    editor._links['kaito'] = on_trigger_wizard_button
    return buttons + [editor._addButton(
        icon_path,
        "kaito", # link name
        "Kaito's Vocab Wizard")]

addHook("setupEditorButtons", add_wizard_button)
