from __future__ import annotations

import os
import sys
from typing import Optional

from anki.notes import Note
from aqt import mw
from aqt.editor import Editor
from aqt.qt import *
from aqt.utils import showInfo, restoreGeom, saveGeom

from .notetypes import isJapaneseNoteType
from .reading import get_reading_for_text

config = mw.addonManager.getConfig(__name__)

srcField = config["srcField"]
englishField = config["englishField"]

supportDir = os.path.join(os.path.dirname(__file__), "support")

# try to import jamdict from lib folder
ADDON_PATH = os.path.dirname(os.path.abspath(__file__))
LIB_PATH = os.path.join(ADDON_PATH, "lib")
if not os.path.exists(LIB_PATH):
    os.makedirs(LIB_PATH)
sys.path.insert(0, LIB_PATH)
from jamdict import Jamdict
jdict = Jamdict()

from anki.hooks import addHook

# Reading/Definition Dialog
##########################################################################

class ReadingDefinitionDialog(QDialog):
    def __init__(self, parent, japanese_text, reading_text, english_text=""):
        super().__init__(parent)
        self.setWindowTitle("Japanese Reading")
        self.setMinimumWidth(400)
        self.japanese_text = japanese_text
        self.reading_text = reading_text
        self.english_text = english_text
        self.setup_ui()
        restoreGeom(self, "readingDefinition")

    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Japanese text
        japanese_label = QLabel("Japanese:")
        self.japanese_display = QLabel(self.japanese_text)
        self.japanese_display.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        # Reading text - now editable
        reading_label = QLabel("Reading:")
        self.reading_display = QTextEdit()
        self.reading_display.setPlainText(self.reading_text)
        # self.reading_display.setMinimumHeight(80)
        self.reading_display.setStyleSheet("font-size: 16px;")
        
        # Definition - now editable
        definition_label = QLabel("Definition:")
        self.definition_display = QTextEdit()
        # self.definition_display.setMinimumHeight(100)
        
        if self.english_text:
            self.definition_display.setPlainText(self.english_text)
        else:
            # Provide a hint for the user
            self.definition_display.setPlaceholderText("Enter definition here or look up on Jisho.org")
            
        # Add a button to look up on Jisho
        jisho_button = QPushButton("Look up on Jisho.org")
        jisho_button.clicked.connect(self.open_jisho)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        # Add to layout
        layout.addWidget(japanese_label)
        layout.addWidget(self.japanese_display)
        layout.addWidget(reading_label)
        layout.addWidget(self.reading_display)
        layout.addWidget(definition_label)
        layout.addWidget(self.definition_display)
        layout.addWidget(jisho_button)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        
    def open_jisho(self):
        """Open Jisho.org to look up the Japanese text."""
        url = f"https://jisho.org/search/{self.japanese_text}"
        QDesktopServices.openUrl(QUrl(url))
        
    def get_reading(self):
        """Get the edited reading text."""
        return self.reading_display.toPlainText()
        
    def get_definition(self):
        """Get the edited definition text."""
        return self.definition_display.toPlainText()

    def closeEvent(self, event):
        saveGeom(self, "readingDefinition")
        super().closeEvent(event)

def get_english_meanings(japanese_word):    
    # Look up the word
    result = jdict.lookup(japanese_word)
    
    # Extract meanings
    meanings = []
    
    # Process entries from JMdict (Japanese-English dictionary)
    if result.entries:
        for entry in result.entries:
            # Get all senses (meanings)
            for sense in entry.senses:
                # Extract English glosses
                glosses = [gloss.text for gloss in sense.gloss]
                if glosses:
                    meanings.append("; ".join(glosses))
    
    return "\n".join(meanings)

def on_generate_reading_button(editor: Editor):
    """Handle the generate reading button click."""
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
    
    # Get source text
    src_text = mw.col.media.strip(note[srcField])
    if not src_text:
        showInfo(f"The field '{srcField}' is empty.")
        return
    
    # Get the reading
    reading = get_reading_for_text(src_text)
    print("Got reading: " + reading)
    if not reading:
        showInfo(f"Could not generate reading for text in '{srcField}'.")
        return
    
    # Get English text if available
    english_text = get_english_meanings(src_text)
    
    # Show the dialog
    dialog = ReadingDefinitionDialog(editor.parentWindow, src_text, reading, english_text)
    if dialog.exec():
        # User clicked OK - update the source field with the edited reading
        note[srcField] = dialog.get_reading()
        note[englishField] = dialog.get_definition()
            
        editor.loadNote()
        editor.web.setFocus()


def add_reading_button(buttons, editor):
    """Add a button to the editor toolbar."""
    icon_path = os.path.join(os.path.dirname(__file__), "icons", "reading.svg")
    
    if os.path.exists(icon_path):
        icon = icon_path
    else:
        icon = "text-speak"
    
    editor._links['kaito'] = on_generate_reading_button
    return buttons + [editor._addButton(
        icon_path,
        "kaito", # link name
        "Kaito's Japanese Magic")]

addHook("setupEditorButtons", add_reading_button)
