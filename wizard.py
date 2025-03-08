from __future__ import annotations

import os
import sys
import requests
import json
import urllib.parse
from typing import Optional, List
from functools import partial

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
imageField = config.get("imageField", "Image")  # Add default image field

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
        self.setWindowTitle("Japanese Reading Wizard")
        self.setMinimumWidth(600)  # Increased width for image display
        self.japanese_text = japanese_text
        self.reading_text = reading_text
        self.english_text = english_text
        self.current_page = 0
        self.selected_image_url = None
        self.image_thumbnails = []
        self.setup_ui()
        restoreGeom(self, "readingDefinition")

    def setup_ui(self):
        main_layout = QVBoxLayout()
        
        # Create stacked widget for pages
        self.stack = QStackedWidget()
        
        # Create first page (reading page)
        self.reading_page = QWidget()
        reading_layout = QVBoxLayout()
        
        # Japanese text
        japanese_label = QLabel("Japanese:")
        self.japanese_display = QLabel(self.japanese_text)
        self.japanese_display.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        # Reading text - now editable
        reading_label = QLabel("Reading:")
        self.reading_display = QTextEdit()
        self.reading_display.setPlainText(self.reading_text)
        self.reading_display.setStyleSheet("font-size: 16px;")
        
        # Add a button to look up on Jisho
        jisho_button = QPushButton("Look up on Jisho.org")
        jisho_button.clicked.connect(self.open_jisho)
        
        # Add to layout
        reading_layout.addWidget(japanese_label)
        reading_layout.addWidget(self.japanese_display)
        reading_layout.addWidget(reading_label)
        reading_layout.addWidget(self.reading_display)
        reading_layout.addWidget(jisho_button)
        
        self.reading_page.setLayout(reading_layout)
        
        # Create second page (definition page)
        self.definition_page = QWidget()
        definition_layout = QVBoxLayout()
        
        # Definition - now editable
        definition_label = QLabel("Definition:")
        self.definition_display = QTextEdit()
        
        if self.english_text:
            self.definition_display.setPlainText(self.english_text)
        else:
            # Provide a hint for the user
            self.definition_display.setPlaceholderText("Enter definition here or look up on Jisho.org")
        
        definition_layout.addWidget(definition_label)
        definition_layout.addWidget(self.definition_display)
        
        self.definition_page.setLayout(definition_layout)
        
        # Create third page (image selection page)
        self.image_page = QWidget()
        image_layout = QVBoxLayout()
        
        # Image selection instructions
        image_label = QLabel(f"Select an image for '{self.japanese_text}':")
        image_layout.addWidget(image_label)
        
        # Create a grid layout for images
        self.image_grid = QGridLayout()
        
        # Create a scroll area for the image grid
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_content.setLayout(self.image_grid)
        scroll_area.setWidget(scroll_content)
        
        image_layout.addWidget(scroll_area)
        
        # Add a refresh button to search again
        refresh_button = QPushButton("Search Again")
        refresh_button.clicked.connect(self.search_images)
        image_layout.addWidget(refresh_button)
        
        self.image_page.setLayout(image_layout)
        
        # Add pages to stack
        self.stack.addWidget(self.reading_page)
        self.stack.addWidget(self.definition_page)
        self.stack.addWidget(self.image_page)
        
        # Navigation buttons
        nav_layout = QHBoxLayout()
        
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self.go_back)
        self.back_button.setEnabled(False)  # Disabled on first page
        
        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.go_next)
        
        self.finish_button = QPushButton("Finish")
        self.finish_button.clicked.connect(self.accept)
        self.finish_button.setVisible(False)  # Hidden until last page
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        nav_layout.addWidget(self.back_button)
        nav_layout.addWidget(self.next_button)
        nav_layout.addWidget(self.finish_button)
        nav_layout.addWidget(self.cancel_button)
        
        # Add to main layout
        main_layout.addWidget(self.stack)
        main_layout.addLayout(nav_layout)
        
        self.setLayout(main_layout)
        
    def go_next(self):
        """Move to the next page in the wizard."""
        current = self.stack.currentIndex()
        if current < self.stack.count() - 1:
            self.stack.setCurrentIndex(current + 1)
            self.update_buttons()
            
            # If moving to the image page, search for images
            if self.stack.currentIndex() == 2:  # Image page
                self.search_images()
    
    def go_back(self):
        """Move to the previous page in the wizard."""
        current = self.stack.currentIndex()
        if current > 0:
            self.stack.setCurrentIndex(current - 1)
            self.update_buttons()
    
    def update_buttons(self):
        """Update button states based on current page."""
        current = self.stack.currentIndex()
        self.back_button.setEnabled(current > 0)
        
        # On last page, show Finish instead of Next
        is_last_page = current == self.stack.count() - 1
        self.next_button.setVisible(not is_last_page)
        self.finish_button.setVisible(is_last_page)
        
    def open_jisho(self):
        """Open Jisho.org to look up the Japanese text."""
        url = f"https://jisho.org/search/{self.japanese_text}"
        QDesktopServices.openUrl(QUrl(url))
    
    def search_images(self):
        """Search Google Images for the Japanese text and display results."""
        # Clear previous images
        self.clear_image_grid()
        self.image_thumbnails = []
        
        # Show loading indicator
        loading_label = QLabel("Searching for images...")
        self.image_grid.addWidget(loading_label, 0, 0)
        QApplication.processEvents()
        
        try:
            # Get search term
            search_term = urllib.parse.quote(self.japanese_text)
            
            # Check API configuration
            api_key = config.get("google_api_key", "")
            cx = config.get("google_cx", "")
            
            if not api_key or not cx:
                # Show message and open browser
                self.clear_image_grid()
                msg = QLabel("API key not configured. Opening Google Images in browser.")
                self.image_grid.addWidget(msg, 0, 0)
                
                # Open browser
                url = f"https://www.google.com/search?q={search_term}&tbm=isch"
                QDesktopServices.openUrl(QUrl(url))
                return
            
            # Make API request
            url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={cx}&q={search_term}&searchType=image&num=10"
            response = requests.get(url, timeout=10)
            
            # Check response status
            if response.status_code != 200:
                self.clear_image_grid()
                error = QLabel(f"API Error: HTTP {response.status_code}")
                self.image_grid.addWidget(error, 0, 0)
                return
            
            # Parse JSON response
            data = response.json()
            
            # Check for API errors
            if "error" in data:
                self.clear_image_grid()
                error = QLabel(f"API Error: {data['error'].get('message', 'Unknown error')}")
                self.image_grid.addWidget(error, 0, 0)
                return
            
            # Extract image data
            if "items" in data:
                for item in data["items"]:
                    if "link" in item and "image" in item and "thumbnailLink" in item["image"]:
                        self.image_thumbnails.append({
                            "url": item["link"],
                            "thumbnail": item["image"]["thumbnailLink"]
                        })
            
            # Clear loading and display results
            self.clear_image_grid()
            
            if self.image_thumbnails:
                self.display_images()
            else:
                msg = QLabel("No images found. Try a different search term.")
                self.image_grid.addWidget(msg, 0, 0)
            
        except requests.exceptions.RequestException as e:
            self.clear_image_grid()
            error = QLabel(f"Network error: {str(e)}")
            self.image_grid.addWidget(error, 0, 0)
            print(f"Network error: {str(e)}")
        except Exception as e:
            self.clear_image_grid()
            error = QLabel(f"Error: {str(e)}")
            self.image_grid.addWidget(error, 0, 0)
            print(f"Error searching for images: {str(e)}")
            import traceback
            print(traceback.format_exc())
    
    def clear_image_grid(self):
        """Clear all widgets from the image grid."""
        while self.image_grid.count():
            item = self.image_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
    
    def display_images(self):
        """Display the found images in the grid."""
        try:
            for i, image_data in enumerate(self.image_thumbnails):
                try:
                    # Create a simple container widget
                    container = QWidget()
                    container.setStyleSheet("border: 1px solid #cccccc; padding: 5px;")
                    container_layout = QVBoxLayout()
                    container.setLayout(container_layout)
                    
                    # Create label for image
                    image_label = QLabel()
                    # Don't set alignment - it's causing issues
                    image_label.setFixedSize(150, 150)
                    image_label.setScaledContents(True)
                    
                    # Load image from URL
                    pixmap = self.load_image_from_url(image_data["thumbnail"])
                    if pixmap:
                        # Just scale the pixmap without transformation flags
                        image_label.setPixmap(pixmap.scaled(150, 150))
                    else:
                        image_label.setText("Failed to load")
                        image_label.setStyleSheet("color: red;")
                    
                    # Create select button
                    select_button = QPushButton("Select")
                    select_button.clicked.connect(partial(self.select_image, image_data["url"]))
                    
                    # Add to container
                    container_layout.addWidget(image_label)
                    container_layout.addWidget(select_button)
                    
                    # Add to grid (2x5 grid)
                    row = i // 5
                    col = i % 5
                    self.image_grid.addWidget(container, row, col)
                except Exception as e:
                    print(f"Error displaying image {i}: {str(e)}")
                    # Continue with next image
        except Exception as e:
            self.clear_image_grid()
            error_label = QLabel(f"Error displaying images: {str(e)}")
            self.image_grid.addWidget(error_label, 0, 0)
            print(f"Error in display_images: {str(e)}")
            import traceback
            print(traceback.format_exc())
    
    def load_image_from_url(self, url):
        """Load an image from a URL and return a QPixmap."""
        try:
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                print(f"Failed to load image: HTTP {response.status_code}")
                return None
            
            pixmap = QPixmap()
            pixmap.loadFromData(response.content)
            return pixmap
        except Exception as e:
            print(f"Error loading image: {str(e)}")
            return None
    
    def select_image(self, url):
        """Handle image selection."""
        self.selected_image_url = url
        
        # Add visual feedback for selection
        status_label = QLabel(f"✓ Image selected")
        status_label.setStyleSheet("color: green; font-weight: bold;")
        
        # Clear any existing status messages
        for i in range(self.image_grid.count()):
            item = self.image_grid.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), QLabel) and item.widget().text().startswith("✓"):
                item.widget().deleteLater()
        
        # Add the status message at the top - without alignment parameter
        self.image_grid.addWidget(status_label, 0, 0, 1, 5)
        
        # Enable the finish button to allow completing the wizard
        self.finish_button.setEnabled(True)
        
        # Optional: scroll to top to show the confirmation
        if hasattr(self.image_grid.parentWidget().parentWidget(), "verticalScrollBar"):
            self.image_grid.parentWidget().parentWidget().verticalScrollBar().setValue(0)
    
    def get_reading(self):
        """Get the edited reading text."""
        return self.reading_display.toPlainText()
        
    def get_definition(self):
        """Get the edited definition text."""
        return self.definition_display.toPlainText()
    
    def get_selected_image_url(self):
        """Get the selected image URL."""
        return self.selected_image_url

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
        
        # Add the selected image if available
        selected_image_url = dialog.get_selected_image_url()
        if selected_image_url and imageField in note:
            # Download the image and add it to the media collection
            try:
                response = requests.get(selected_image_url)
                if response.status_code == 200:
                    # Generate a filename based on the Japanese text
                    filename = f"kaito_{src_text}.jpg"
                    # Save to Anki media folder
                    media_file = mw.col.media.write_data(filename, response.content)
                    # Add to note
                    note[imageField] = f'<img src="{media_file}">'
            except Exception as e:
                showInfo(f"Error adding image: {str(e)}")
            
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
