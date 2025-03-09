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
from aqt.operations import QueryOp
from aqt.qt import *
from aqt.utils import showInfo, restoreGeom, saveGeom

from .notetypes import isJapaneseNoteType
from .reading import get_reading_for_text

# Custom clickable label class
class ClickableLabel(QLabel):
    """A QLabel that emits a clicked signal when clicked."""
    clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super(ClickableLabel, self).__init__(parent)
        self.url = ""
    
    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

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

def load_image_from_url(url):
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

def search_google_images(search_term):# Helper to search Google Images
    """ Helper to search Google Images for the given term and return a list of image URLs. """
    print("Searching for images: " + search_term)
    results = []
    search_term = urllib.parse.quote(search_term)
    
    # Check API configuration
    api_key = config.get("google_api_key", "")
    cx = config.get("google_cx", "")
    
    if not api_key or not cx:
        raise Exception("Google API key not configured.")

    # Make API request for Japanese term
    url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={cx}&q={search_term}&searchType=image&num=10"
    response = requests.get(url, timeout=10)
    
    if response.status_code == 200:
        data = response.json()
        if "items" in data:
            for item in data["items"]:
                if "link" in item and "image" in item and "thumbnailLink" in item["image"]:
                    thumbnail = load_image_from_url(item["image"]["thumbnailLink"])
                    if thumbnail:
                        results.append({
                            "url": item["link"],
                            "thumbnail": thumbnail.scaled(150, 150),
                        })
    return results

# Reading/Definition Dialog
##########################################################################

class VocabWizard(QDialog):
    def __init__(self, parent, japanese_text, reading_text, english_text=""):
        super().__init__(parent)
        self.setWindowTitle("Kaito's Vocab Wizard")
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
        
        # Definition - now on first page
        definition_label = QLabel("Definition:")
        self.definition_display = QTextEdit()
        
        if self.english_text:
            self.definition_display.setPlainText(self.english_text)
        else:
            # Provide a hint for the user
            self.definition_display.setPlaceholderText("Enter definition here or look up on Jisho.org")
        
        # Add a button to look up on Jisho
        jisho_button = QPushButton("Look up on Jisho.org")
        jisho_button.clicked.connect(self.open_jisho)
        
        # Add to layout
        reading_layout.addWidget(japanese_label)
        reading_layout.addWidget(self.japanese_display)
        reading_layout.addWidget(reading_label)
        reading_layout.addWidget(self.reading_display)
        reading_layout.addWidget(definition_label)
        reading_layout.addWidget(self.definition_display)
        reading_layout.addWidget(jisho_button)
        
        self.reading_page.setLayout(reading_layout)
        
        # Create image selection page (now the second page)
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
            if self.stack.currentIndex() == 1:  # Image page
                self.search_images()
                # Disable Next button until an image is selected
                self.next_button.setEnabled(False)
    
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
        
        # Disable Next button on image page until an image is selected
        if current == 1 and not self.selected_image_url:  # Image page
            self.next_button.setEnabled(False)
    
    def open_jisho(self):
        """Open Jisho.org to look up the Japanese text."""
        url = f"https://jisho.org/search/{self.japanese_text}"
        QDesktopServices.openUrl(QUrl(url))

    def add_chatgpt_image(self, image_data):
        """Add the ChatGPT-generated image to the image grid."""
        if not image_data:
            return
        
        # Insert the ChatGPT image at the beginning of the list
        self.image_thumbnails.insert(0, image_data)
        
        # Display all images including the new ChatGPT one
        self.clear_image_grid()
        self.display_images()

    def add_prompt_images(self, images):
        """Add images to the prompt images list."""
        if len(self.image_thumbnails) < 1:
            self.image_thumbnails = images
        else:
            self.image_thumbnails = [val for pair in zip(self.image_thumbnails, images) for val in pair]
        self.clear_image_grid()
        self.display_images()

    def search_images(self):
        """Search Google Images for both Japanese text and English meaning, and display results alternating between the two."""
        # Clear previous images
        self.clear_image_grid()
        self.image_thumbnails = []
        
        # Show loading indicator
        loading_label = QLabel("Searching for images...")
        self.image_grid.addWidget(loading_label, 0, 0)
        QApplication.processEvents()

        chatgpt_op = QueryOp(
            parent=mw,
            op=lambda col: generate_chatgpt_image(self.japanese_text, self.english_text),
            success=self.add_chatgpt_image,
        )
        chatgpt_op.without_collection().run_in_background()

        jp_op = QueryOp(
            # the active window (main window in this case)
            parent=mw,
            # the operation is passed the collection for convenience; you can
            # ignore it if you wish
            op=lambda col: search_google_images(self.japanese_text),
            success=self.add_prompt_images,
        )
        jp_op.without_collection().run_in_background()
        
        en_op = QueryOp(
            parent=mw,
            op=lambda col: search_google_images(self.english_text),
            success=self.add_prompt_images,
        )
        en_op.without_collection().run_in_background()

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
                    
                    # Create clickable label for image
                    image_label = ClickableLabel()
                    image_label.setFixedSize(150, 150)
                    image_label.setScaledContents(True)
                    # Use CSS to indicate clickability
                    image_label.setStyleSheet("border: 1px solid #dddddd; padding: 2px; background-color: #f8f8f8;")
                    
                    # Store the URL as a property on the label
                    image_label.url = image_data["url"]
                    
                    # Connect click event to select_image using a helper method
                    image_label.clicked.connect(self.on_image_clicked)
                    
                    # Load image from URL 
                    image_label.setPixmap(image_data["thumbnail"])

                    # Add to container
                    container_layout.addWidget(image_label)
                    
                    # Add to grid (2x5 grid)
                    row = i // 5
                    col = i % 5
                    self.image_grid.addWidget(container, row, col)
                except Exception as e:
                    print(f"Error displaying image {i}: {str(e)}")
                    import traceback
                    print(traceback.format_exc())
                    # Continue with next image
        except Exception as e:
            self.clear_image_grid()
            error_label = QLabel(f"Error displaying images: {str(e)}")
            self.image_grid.addWidget(error_label, 0, 0)
            print(f"Error in display_images: {str(e)}")
            import traceback
            print(traceback.format_exc())

    def select_image(self, url):
        """Handle image selection."""
        # Store the selected URL
        self.selected_image_url = url
        
        # Find and highlight the selected image
        for i in range(self.image_grid.count()):
            item = self.image_grid.itemAt(i)
            if item and item.widget():
                # Check if this is a container widget
                container = item.widget()
                # Look for the ClickableLabel in the container
                for j in range(container.layout().count()):
                    child = container.layout().itemAt(j)
                    if child and child.widget() and isinstance(child.widget(), ClickableLabel):
                        label = child.widget()
                        # Check if this is the selected image
                        if hasattr(label, 'url') and label.url == url:
                            # Highlight this image
                            label.setStyleSheet("border: 3px solid #4CAF50; padding: 2px; background-color: #f0f0f0;")
                            # Add a small checkmark overlay
                            if not hasattr(label, 'checkmark'):
                                checkmark = QLabel("✓", label)
                                checkmark.setStyleSheet("background-color: #4CAF50; color: white; border-radius: 10px; padding: 2px;")
                                checkmark.setFixedSize(20, 20)
                                checkmark.move(5, 5)  # Position in top-left corner
                                checkmark.show()
                                label.checkmark = checkmark
                        else:
                            # Reset other images
                            label.setStyleSheet("border: 1px solid #dddddd; padding: 2px; background-color: #f8f8f8;")
                            # Remove checkmark if exists
                            if hasattr(label, 'checkmark'):
                                label.checkmark.deleteLater()
                                delattr(label, 'checkmark')
        
        # Enable the Next button now that an image is selected
        self.next_button.setEnabled(True)
        # Make the Next button more prominent
        self.next_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 5px 10px;")
        
        # Add a small status message at the bottom
        status_layout = QHBoxLayout()
        status_widget = QWidget()
        status_widget.setLayout(status_layout)
        
        status_label = QLabel("✓ Image selected - Click 'Next' to continue")
        status_label.setStyleSheet("color: green; font-weight: bold;")
        status_layout.addWidget(status_label)
        
        # Find if there's already a status message
        for i in range(self.image_grid.count()):
            item = self.image_grid.itemAt(i)
            if item and item.widget() and hasattr(item.widget(), 'isStatusWidget') and item.widget().isStatusWidget:
                item.widget().deleteLater()
        
        # Add the status widget at the bottom
        rows = (self.image_grid.count() // 5) + 1  # Calculate number of rows
        status_widget.isStatusWidget = True  # Mark this widget as a status widget
        self.image_grid.addWidget(status_widget, rows, 0, 1, 5)
    
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

    def on_image_clicked(self):
        """Helper method to handle image clicks."""
        # Get the sender (the clicked label)
        sender = self.sender()
        if hasattr(sender, 'url'):
            self.select_image(sender.url)

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
    if not reading:
        showInfo(f"Could not generate reading for text in '{srcField}'.")
        return
    
    # Get English text if available
    english_text = get_english_meanings(src_text)
    
    # Show the dialog
    dialog = VocabWizard(editor.parentWindow, src_text, reading, english_text)
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

def generate_chatgpt_image(japanese_text, english_text):
    """Generate an image using ChatGPT based on the Japanese and English text."""
    api_key = config.get("openai_api_key")
    print("API Key: " + api_key)
    if not api_key:
        return None
    
    prompt_template = config.get("chatgpt_image_prompt_template", 
                               "Create a simple, clear illustration to represent'{japanese}' meaning '{english}'. The image should be minimalist and educational.")
    
    prompt = prompt_template.format(japanese=japanese_text, english=english_text)
    print("ChatGPT Prompt: " + prompt)
    response = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        },
        json={
            "model": "dall-e-3",
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024"
        },
        timeout=30
    )

    print("ChatGPT Response: " + str(response.json()))
    
    if response.status_code != 200:
        raise Exception("Failed to generate image with ChatGPT: " + str(response.json()))
    
    data = response.json()
    if "data" not in data or len(data["data"]) < 1:
        return None
    
    return {
        "url": data["data"][0]["url"],
        "thumbnail": load_image_from_url(data["data"][0]["url"]),
        "source": "ChatGPT",
        "title": "AI Generated Image"
    }
