# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
#
# Automatic reading generation with kakasi and mecab.
#

from __future__ import annotations

import os
import re
import subprocess
import sys
from typing import Optional

from anki.hooks import addHook
from anki.notes import Note
from anki.utils import is_mac, is_win, strip_html
from aqt import gui_hooks, mw
from aqt.editor import Editor
from aqt.qt import *
from aqt.utils import showInfo, restoreGeom, saveGeom

from .notetypes import isJapaneseNoteType
from .lookup import lookup

config = mw.addonManager.getConfig(__name__)

srcField = config["srcField"]
englishField = config["englishField"]

kakasiArgs = ["-isjis", "-osjis", "-u", "-JH", "-KH"]
mecabArgs = ["--node-format=%m[%f[7]] ", "--eos-format=\n", "--unk-format=%m[] "]

supportDir = os.path.join(os.path.dirname(__file__), "support")


def escapeText(text: str) -> str:
    # strip characters that trip up kakasi/mecab
    text = text.replace("\n", " ")
    text = text.replace("\uff5e", "~")
    text = re.sub("<br( /)?>", "---newline---", text)
    text = strip_html(text)
    text = text.replace("---newline---", "<br>")
    return text


if sys.platform == "win32":
    si = subprocess.STARTUPINFO()
    try:
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    except:
        # pylint: disable=no-member
        si.dwFlags |= subprocess._subprocess.STARTF_USESHOWWINDOW
else:
    si = None

# Mecab
##########################################################################


def mungeForPlatform(popen: list[str]) -> list[str]:
    if is_win:
        popen = [os.path.normpath(x) for x in popen]
        popen[0] += ".exe"
    elif not is_mac:
        popen[0] += ".lin"
    return popen


class MecabController(object):
    def __init__(self) -> None:
        self.mecab: subprocess.Popen | None = None

    def setup(self) -> None:
        self.mecabCmd = mungeForPlatform(
            [os.path.join(supportDir, "mecab")]
            + mecabArgs
            + [
                "-d",
                supportDir,
                "-r",
                os.path.join(supportDir, "mecabrc"),
                "-u",
                os.path.join(supportDir, "user_dic.dic"),
            ]
        )
        os.environ["DYLD_LIBRARY_PATH"] = supportDir
        os.environ["LD_LIBRARY_PATH"] = supportDir
        if not is_win:
            os.chmod(self.mecabCmd[0], 0o755)

    def ensureOpen(self) -> None:
        if not self.mecab:
            self.setup()
            try:
                self.mecab = subprocess.Popen(
                    self.mecabCmd,
                    bufsize=-1,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    startupinfo=si,
                )
            except OSError as exc:
                raise Exception(
                    "Please ensure your Linux system has 64 bit binary support."
                ) from exc

    def reading(self, expr: str) -> str:
        self.ensureOpen()
        expr = escapeText(expr)
        self.mecab.stdin.write(expr.encode("utf-8", "ignore") + b"\n")
        self.mecab.stdin.flush()
        assert self.mecab
        expr = self.mecab.stdout.readline().rstrip(b"\r\n").decode("utf-8", "replace")
        out = []
        for node in expr.split(" "):
            if not node:
                break
            m = re.match(r"(.+)\[(.*)\]", node)
            if not m:
                sys.stderr.write(
                    "Unexpected output from mecab. Perhaps your Windows username contains non-Latin text?: {}\n".format(
                        repr(expr)
                    )
                )
                return ""

            (kanji, reading) = m.groups()
            # hiragana, punctuation, not japanese, or lacking a reading
            if kanji == reading or not reading:
                out.append(kanji)
                continue
            # katakana
            if kanji == kakasi.reading(reading):
                out.append(kanji)
                continue
            # convert to hiragana
            reading = kakasi.reading(reading)
            # ended up the same
            if reading == kanji:
                out.append(kanji)
                continue
            # don't add readings of numbers
            if kanji in "一二三四五六七八九十０１２３４５６７８９":
                out.append(kanji)
                continue
            # strip matching characters and beginning and end of reading and kanji
            # reading should always be at least as long as the kanji
            placeL = 0
            placeR = 0
            for i in range(1, len(kanji)):
                if kanji[-i] != reading[-i]:
                    break
                placeR = i
            for i in range(0, len(kanji) - 1):
                if kanji[i] != reading[i]:
                    break
                placeL = i + 1
            if placeL == 0:
                if placeR == 0:
                    out.append(" %s[%s]" % (kanji, reading))
                else:
                    out.append(
                        " %s[%s]%s"
                        % (kanji[:-placeR], reading[:-placeR], reading[-placeR:])
                    )
            else:
                if placeR == 0:
                    out.append(
                        "%s %s[%s]"
                        % (reading[:placeL], kanji[placeL:], reading[placeL:])
                    )
                else:
                    out.append(
                        "%s %s[%s]%s"
                        % (
                            reading[:placeL],
                            kanji[placeL:-placeR],
                            reading[placeL:-placeR],
                            reading[-placeR:],
                        )
                    )
        fin = ""
        for c, s in enumerate(out):
            if c < len(out) - 1 and re.match("^[A-Za-z0-9]+$", out[c + 1]):
                s += " "
            fin += s
        return fin.strip().replace("< br>", "<br>")


# Kakasi
##########################################################################


class KakasiController(object):
    def __init__(self) -> None:
        self.kakasi: subprocess.Popen | None = None

    def setup(self) -> None:
        self.kakasiCmd = mungeForPlatform(
            [os.path.join(supportDir, "kakasi")] + kakasiArgs
        )
        os.environ["ITAIJIDICT"] = os.path.join(supportDir, "itaijidict")
        os.environ["KANWADICT"] = os.path.join(supportDir, "kanwadict")
        if not is_win:
            os.chmod(self.kakasiCmd[0], 0o755)

    def ensureOpen(self) -> None:
        if not self.kakasi:
            self.setup()
            try:
                self.kakasi = subprocess.Popen(
                    self.kakasiCmd,
                    bufsize=-1,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    startupinfo=si,
                )
            except OSError as exc:
                raise Exception("Please install kakasi") from exc

    def reading(self, expr: str) -> str:
        self.ensureOpen()
        expr = escapeText(expr)
        self.kakasi.stdin.write(expr.encode("sjis", "ignore") + b"\n")
        self.kakasi.stdin.flush()
        res = self.kakasi.stdout.readline().rstrip(b"\r\n").decode("sjis", "replace")
        return res


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


# Button and Editor Integration
##########################################################################

def get_reading_for_text(text: str) -> Optional[str]:
    """Get the reading for the given text."""
    global mecab
    if not mecab:
        return None
    
    if not text:
        return None
    
    # Generate reading
    try:
        reading = mecab.reading(text)
        return reading
    except Exception as e:
        mecab = None
        raise


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
    english_text = ""
    
    # Show the dialog
    dialog = ReadingDefinitionDialog(editor.parentWindow, src_text, reading, english_text)
    if dialog.exec():
        # User clicked OK - update the source field with the edited reading
        note[srcField] = dialog.get_reading()
        note[englishField] = dialog.get_definition()
            
        editor.loadNote()
        editor.web.setFocus()
        showInfo(f"Reading added to field '{srcField}'.")


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

# Init
##########################################################################

kakasi = KakasiController()
mecab = MecabController()

# Tests
##########################################################################

if __name__ == "__main__":
    expr = "カリン、自分でまいた種は自分で刈り取れ"
    print(mecab.reading(expr).encode("utf-8"))
    expr = "昨日、林檎を2個買った。"
    print(mecab.reading(expr).encode("utf-8"))
    expr = "真莉、大好きだよん＾＾"
    print(mecab.reading(expr).encode("utf-8"))
    expr = "彼２０００万も使った。"
    print(mecab.reading(expr).encode("utf-8"))
    expr = "彼二千三百六十円も使った。"
    print(mecab.reading(expr).encode("utf-8"))
    expr = "千葉"
    print(mecab.reading(expr).encode("utf-8"))
