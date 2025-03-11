from __future__ import annotations

import os

from anki.hooks import addHook
from anki.notes import Note
from aqt import mw
from aqt.editor import Editor
from aqt.qt import *
from aqt.utils import showInfo

from .notetypes import isJapaneseNoteType
from .reading import get_reading_for_text
from .jdict import get_english_meanings


def on_generate_reading_button(editor: Editor):
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
    
    # Get source text
    src_text = mw.col.media.strip(note[srcField])
    if not src_text:
        showInfo(f"The field '{srcField}' is empty.")
        return
    
    reading = get_reading_for_text(src_text)
    if not reading:
        showInfo("Could not generate reading, please add your own.")
        return
    note[srcField] = reading

    english_text = get_english_meanings(src_text)
    if not english_text:
        showInfo("Could not generate English meaning, please add your own.")
        return
    note[englishField] = english_text
    editor.loadNote()
    editor.web.setFocus()


def add_reading_button(buttons, editor):
    """Add a button to the editor toolbar."""
    icon_path = "magnify-light.svg"
    # icon_path = os.path.join(os.path.dirname(__file__), "icons", "reading.svg")
    
    # if os.path.exists(icon_path):
    #     icon = icon_path
    # else:
    #     icon = "text-speak"
    
    editor._links['reading'] = on_generate_reading_button
    return buttons + [editor._addButton(
        icon_path,
        "reading", # link name
        "Update Reading and Meaning")]

addHook("setupEditorButtons", add_reading_button)
