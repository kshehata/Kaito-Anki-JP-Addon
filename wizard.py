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
mnemonicField = config.get("mnemonicField", "Mnemonic")  # Add default mnemonic field
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
    response = requests.get(url, timeout=5)
    if response.status_code != 200:
        raise Exception(f"Failed to load image: HTTP {response.status_code}")
    
    return response.content

def pixmap_for_image(image):
    pixmap = QPixmap()
    pixmap.loadFromData(image)
    return pixmap

def save_image(image, filename):
    """Save image to file and get HTML for it."""
    media_file = mw.col.media.write_data(filename, image)
    return f"<img src='{media_file}'>"

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
                    image = load_image_from_url(item["image"]["thumbnailLink"])
                    if image:
                        results.append({
                            "url": item["link"],
                            "thumbnail": pixmap_for_image(image).scaled(150, 150),
                        })
    return results

# Reading/Definition Dialog
##########################################################################

class VocabWizard(QDialog):
    def __init__(self, parent, japanese_text, reading_text, english_text=""):
        super().__init__(parent)
        self.setWindowTitle("Kaito's Vocab Wizard")
        self.setMinimumWidth(800)  # Increased width for image display
        self.japanese_text = japanese_text
        self.reading_text = reading_text
        self.english_text = english_text
        self.current_page = 0
        self.prompt_image_data = None
        self.selected_mnemonic_index = None
        self.image_thumbnails = []
        self.mnemonic_images = {}  # Store mnemonic images by index
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
        
        # Create mnemonic page (new second page)
        self.mnemonic_page = QWidget()
        mnemonic_layout = QVBoxLayout()
        
        # Mnemonic selection instructions
        mnemonic_label = QLabel(f"Select a mnemonic story for '{self.japanese_text}':")
        mnemonic_layout.addWidget(mnemonic_label)
        
        # Create a vertical layout for mnemonic stories
        self.mnemonic_list = QVBoxLayout()
        
        # Create a scroll area for the mnemonic list
        mnemonic_scroll_area = QScrollArea()
        mnemonic_scroll_area.setWidgetResizable(True)
        mnemonic_scroll_content = QWidget()
        mnemonic_scroll_content.setLayout(self.mnemonic_list)
        mnemonic_scroll_area.setWidget(mnemonic_scroll_content)
        
        mnemonic_layout.addWidget(mnemonic_scroll_area)
        
        # Add a refresh button to generate new mnemonics
        refresh_mnemonic_button = QPushButton("Generate New Mnemonics")
        refresh_mnemonic_button.clicked.connect(self.generate_mnemonics)
        mnemonic_layout.addWidget(refresh_mnemonic_button)
        
        self.mnemonic_page.setLayout(mnemonic_layout)
        
        # Create image selection page (now the third page)
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
        self.stack.addWidget(self.mnemonic_page)
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
            
            # If moving to the mnemonic page, generate mnemonics
            if self.stack.currentIndex() == 1:  # Mnemonic page
                # Update the english text
                self.english_text = self.definition_display.toPlainText()
                self.generate_mnemonics()
                # Disable Next button until a mnemonic is selected
                self.next_button.setEnabled(False)
            
            # If moving to the image page, search for images
            elif self.stack.currentIndex() == 2:  # Image page
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
        if current == 2 and not self.prompt_image_data:  # Image page
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

    def simple_background_query(self, fn, success):
        """Run an operation in the background and call a success callback with the result."""
        op = QueryOp(
            parent=self,
            op=fn,
            success=success,
        )
        op.without_collection().run_in_background()
        

    def search_images(self):
        """Search Google Images for both Japanese text and English meaning, and display results alternating between the two."""
        # Clear previous images
        self.clear_image_grid()
        self.image_thumbnails = []
        # Reset selected image URL
        self.prompt_image_data = None
        
        # Show loading indicator
        loading_label = QLabel("Searching for images...")
        self.image_grid.addWidget(loading_label, 0, 0)

        self.simple_background_query(lambda _: generate_chatgpt_prompt_image(self.japanese_text, self.english_text), self.add_chatgpt_image)
        self.simple_background_query(lambda _: search_google_images(self.japanese_text), self.add_prompt_images)
        self.simple_background_query(lambda _: search_google_images(self.english_text), self.add_prompt_images)

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
                    
                    # Store the image data as a property on the label
                    image_label.data = image_data
                    
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

    def select_image(self, image_data):
        """Handle image selection."""
        # Store the selected URL
        self.prompt_image_data = image_data

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
                        if hasattr(label, 'data') and label.data["url"] == image_data["url"]:
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
    
    def get_prompt_html(self):
        """Get the selected image URL."""
        if not self.prompt_image_data:
            return None

        image = self.prompt_image_data.get("image", None)
        if not image:
            image = load_image_from_url(self.prompt_image_data["url"])
        
        return save_image(image, f"kaito_{self.japanese_text}.jpg")

    def closeEvent(self, event):
        saveGeom(self, "readingDefinition")
        super().closeEvent(event)

    def on_image_clicked(self):
        """Helper method to handle image clicks."""
        # Get the sender (the clicked label)
        sender = self.sender()
        if hasattr(sender, 'data'):
            self.select_image(sender.data)

    def generate_mnemonics(self):
        """Generate mnemonic stories using ChatGPT."""
        # Clear previous mnemonics
        self.clear_mnemonic_list()
        
        # Show loading indicator
        loading_label = QLabel("Generating mnemonics...")
        self.mnemonic_list.addWidget(loading_label)
        
        # Get the current reading and definition
        reading = self.reading_display.toPlainText()
        definition = self.definition_display.toPlainText()
        
        # Run the query in the background
        self.simple_background_query(
            lambda _: generate_chatgpt_mnemonics(self.japanese_text, reading, definition),
            self.display_mnemonics
        )
    
    def clear_mnemonic_list(self):
        """Clear all widgets from the mnemonic list."""
        while self.mnemonic_list.count():
            item = self.mnemonic_list.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
    
    def generate_mnemonic_image(self, index, story):
        """Generate an illustration for a mnemonic story using ChatGPT."""
        # Get the prompt template from config
        prompt_template = config.get("chatgpt_mnemonic_image_prompt_template", 
                                   "Illustrate the following story: {story}")
        prompt = prompt_template.format(story=story)
        
        # Generate image in background
        self.simple_background_query(
            lambda _: generate_chatgpt_image(prompt),
            lambda result: self.update_mnemonic_image(index, result)
        )

    def update_mnemonic_image(self, index, image_data):
        """Update the mnemonic story's illustration."""
        if not image_data:
            return
        
        # Store the image data
        self.mnemonic_images[index] = image_data
        
        # Update the display
        container = self.mnemonic_list.itemAt(index).widget()
        image_container = container.findChild(QWidget, f"image_container_{index}")
        if image_container:
            # Clear existing widgets
            while image_container.layout().count():
                item = image_container.layout().takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            # Create image label
            image_label = QLabel()
            image_label.setFixedSize(200, 200)
            image_label.setScaledContents(True)
            image_label.setPixmap(image_data["thumbnail"])
            
            # Create regenerate button
            regen_button = QPushButton("Regenerate Illustration")
            regen_button.clicked.connect(lambda: self.generate_mnemonic_image(index, self.mnemonic_editors[index].toPlainText()))
            
            # Add to layout
            image_container.layout().addWidget(image_label)
            image_container.layout().addWidget(regen_button)

    def display_mnemonics(self, mnemonics):
        """Display the generated mnemonics in the list."""
        self.clear_mnemonic_list()
        
        if not mnemonics or len(mnemonics) == 0:
            error_label = QLabel("Failed to generate mnemonics. Please try again.")
            self.mnemonic_list.addWidget(error_label)
            return
        
        # Create a button group to ensure only one radio button can be selected
        self.mnemonic_button_group = QButtonGroup(self)
        
        # Store references to the text editors
        self.mnemonic_editors = []
        
        for i, mnemonic in enumerate(mnemonics):
            # Create a container for each mnemonic
            container = QFrame()
            container.setObjectName(f"mnemonic_container_{i}")  # Set object name for styling
            container.setStyleSheet("border: 1px solid #cccccc; border-radius: 5px; padding: 10px; margin: 5px;")
            container_layout = QHBoxLayout()
            container.setLayout(container_layout)
            
            # Create radio button for selection (no text label)
            radio = QRadioButton()
            
            # Add the radio button to the button group
            self.mnemonic_button_group.addButton(radio)
            self.mnemonic_button_group.setId(radio, i)
            
            # Create editable text area for the mnemonic
            text_edit = QTextEdit()
            text_edit.setPlainText(mnemonic)
            text_edit.setStyleSheet("padding: 5px;")
            text_edit.setMinimumHeight(80)  # Set a minimum height for better editing
            
            # Store reference to the editor
            self.mnemonic_editors.append(text_edit)
            
            # Add to container
            container_layout.addWidget(radio)
            container_layout.addWidget(text_edit, 1)  # Give the text a stretch factor of 1
            
            # Create right side container for image
            image_container = QWidget()
            image_container.setObjectName(f"image_container_{i}")
            image_layout = QVBoxLayout()
            image_container.setLayout(image_layout)
            # Show loading indicator
            loading_label = QLabel("Generating illustration...")
            image_container.layout().addWidget(loading_label)
            container_layout.addWidget(image_container)
            
            # Add to list
            self.mnemonic_list.addWidget(container)
            
            # Generate initial image
            self.generate_mnemonic_image(i, mnemonic)
        
        # Connect the button group's buttonClicked signal to handle selection
        self.mnemonic_button_group.buttonClicked.connect(
            lambda button: self.select_mnemonic(self.mnemonic_button_group.id(button))
        )
    
    def select_mnemonic(self, index):
        """Handle mnemonic selection."""
        # Store the index of the selected mnemonic
        self.selected_mnemonic_index = index
        
        # Update visual feedback for the selected mnemonic
        for i, editor in enumerate(self.mnemonic_editors):
            container = self.mnemonic_list.itemAt(i).widget()
            if i == index:
                # Highlight the selected container
                container.setStyleSheet("border: 2px solid #4CAF50; border-radius: 5px; padding: 10px; margin: 5px; background-color: #f0f8f0;")
            else:
                # Reset other containers
                container.setStyleSheet("border: 1px solid #cccccc; border-radius: 5px; padding: 10px; margin: 5px;")
        
        # Enable the Next button now that a mnemonic is selected
        self.next_button.setEnabled(True)
        # Make the Next button more prominent
        self.next_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 5px 10px;")
    
    def get_selected_mnemonic(self):
        """Get the selected mnemonic text and its illustration."""
        if self.selected_mnemonic_index is None:
            return None
        
        # Get the current text from the selected editor
        text = self.mnemonic_editors[self.selected_mnemonic_index].toPlainText()
        if self.mnemonic_images.get(self.selected_mnemonic_index, None):
            text += "\n\n" + save_image(self.mnemonic_images[
                self.selected_mnemonic_index]["image"],
                f"kaito_mnemonic_{self.japanese_text}.jpg")
                
        return text

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
        
        # Add the selected mnemonic if available
        selected_mnemonic = dialog.get_selected_mnemonic()
        if selected_mnemonic and mnemonicField in note:
            note[mnemonicField] = selected_mnemonic
        
        # Add the selected image if available
        try:
            prompt_html = dialog.get_prompt_html()
            if prompt_html and imageField in note:
                note[imageField] = prompt_html
        except Exception as e:
            showInfo(f"Error adding image prompt: {str(e)}")
            
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

def generate_chatgpt_prompt_image(japanese_text, english_text):
    """Generate an image using ChatGPT based on the Japanese and English text."""
    prompt_template = config.get("chatgpt_image_prompt_template", 
                               "Create a simple, clear illustration to represent'{japanese}' meaning '{english}'. The image should be minimalist and educational.")
    prompt = prompt_template.format(japanese=japanese_text, english=english_text)
    print("ChatGPT Prompt Image Prompt: " + prompt)
    return generate_chatgpt_image(prompt)
    # print("Shortcutting ChatGPT")
    # url = 'https://oaidalleapiprodscus.blob.core.windows.net/private/org-gKiTH4bzIh5r71w1xXJo1Exi/user-pdf8FzTUpzng0o5c2LriNjgZ/img-GXGaApbaUCxVmD4QonHGWdXM.png?st=2025-03-09T05%3A48%3A15Z&se=2025-03-09T07%3A48%3A15Z&sp=r&sv=2024-08-04&sr=b&rscd=inline&rsct=image/png&skoid=d505667d-d6c1-4a0a-bac7-5c84a87759f8&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-03-08T22%3A05%3A50Z&ske=2025-03-09T22%3A05%3A50Z&sks=b&skv=2024-08-04&sig=vnvJo1l%2BFNrapSjii5Wwqwqvi/r%2BPsn9qdtRKlaFvMA%3D'
    # return {
    #     "url": url,
    #     "thumbnail": load_image_from_url(url),
    #     "source": "ChatGPT",
    #     "title": "AI Generated Image"
    # }

def generate_chatgpt_image(prompt):
    """Helper to generate an image using ChatGPT for the given prompt."""
    api_key = config.get("openai_api_key")
    if not api_key:
        return None
    
    # print("Shortcutting image generation")
    # url = "https://files.oaiusercontent.com/file-JA1s3hdSFoBs9TSoF5hm1d?se=2025-03-09T10%3A01%3A41Z&sp=r&sv=2024-08-04&sr=b&rscc=max-age%3D604800%2C%20immutable%2C%20private&rscd=attachment%3B%20filename%3Ddd5bc415-0348-465b-8170-a9126235c22a.webp&sig=lRo5nv0qkp6zIWAdVAfNh8AMsv32inKJtAd%2BAzOf1a8%3D"
    # image = load_image_from_url(url)

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

    # print("ChatGPT Response: " + str(response.json()))
    if response.status_code != 200:
        raise Exception("Failed to generate image with ChatGPT: " + str(response.json()))
    
    data = response.json()
    if "data" not in data or len(data["data"]) < 1:
        return None
    image = load_image_from_url(data["data"][0]["url"])

    return {
        "url": data["data"][0]["url"],
        "thumbnail": pixmap_for_image(image).scaled(150, 150),
        "image": image,
        "source": "ChatGPT",
        "title": "AI Generated Image"
    }

def generate_chatgpt_mnemonics(japanese_text, reading, english_text):
    """Generate mnemonic stories using ChatGPT."""
    api_key = config.get("openai_api_key")
    if not api_key:
        return []
    
    prompt_template = config.get("chatgpt_mnemonics_prompt_template", 
                               "Write a short (< 100 words) story as a mnemonic for remembering the Japanese word '{japanese_text}' (pronounced '{reading}') meaning '{english_text}'. Write 4 such stories, each separated by 2 new lines. Make the stories short and memorable, connecting the pronunciation to the meaning.")
    
    prompt = prompt_template.format(japanese_text=japanese_text, reading=reading, english_text=english_text)
    # print("ChatGPT Mnemonics Prompt: " + prompt)

    # return ['**Story 1:**  \nIn a small town, a little girl named Iku had a fluffy puppy named Nuno. Every morning, Iku would call out, "Inu, come here!" as she played with her dog in the sunny garden. The cheerful bark of Nuno echoed, reminding everyone that "inu" means dog.', '**Story 2:**  \nOne day, a funny dog named Inu decided to join a race. As he sprinted past the finish line, the crowd shouted, “I knew he would win!” Inu wagged his tail, proving that dogs can be champions.', '**Story 3:**  \nIn a magical forest, the wise owl told a story about a brave dog named Inu who saved the day. "Inu," he said, "is the hero of our tale," making the forest animals cheer for their beloved dog.', '**Story 4:**  \nAt a festival, a clown performed tricks with his pet dog named Inu. As the clown juggled, he exclaimed, “I knew Inu would steal the show!” The audience laughed, forever associating Inu with the joyful spirit of dogs.']
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        },
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant that creates memorable mnemonics for language learning."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        },
        timeout=30
    )
    
    if response.status_code != 200:
        raise Exception("Failed to generate mnemonics with ChatGPT: " + str(response.json()))
    
    print("ChatGPT Mnemonics Response: " + str(response.json()))

    data = response.json()
    if "choices" not in data or len(data["choices"]) < 1:
        return []
    
    # Extract the content from the response
    content = data["choices"][0]["message"]["content"]
    
    # Split the content by double newlines to get individual stories
    stories = [story.strip() for story in content.split("\n\n") 
              if story.strip() and len(story.strip()) >= 10]
    print("Stories: " + str(stories))
    return stories