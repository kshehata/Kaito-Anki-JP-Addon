
from aqt.qt import *

from .utils import *
from .chatgpt import ChatGPT

from aqt import mw
import urllib.parse
import requests

def search_google_images(search_term):# Helper to search Google Images
    """ Helper to search Google Images for the given term and return a list of image URLs. """
    # print("Searching for images: " + search_term)
    results = []
    search_term = urllib.parse.quote(search_term)
    
    # Check API configuration
    config = mw.addonManager.getConfig(__name__)
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

# Prompt Image Page
##########################################################################

class PromptImagePage(QWidget):
    def __init__(self, parent, japanese_text, english_text, chatgpt=None):
        super().__init__(parent)
        self.japanese_text = japanese_text
        self.english_text = english_text
        self.image_thumbnails = []
        self.selected_image_data = None
        self.chatgpt = chatgpt if chatgpt else ChatGPT(mw.addonManager.getConfig(__name__))

        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Create a grid layout for images
        self.image_grid = QGridLayout()
        
        # Create a scroll area for the image grid
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_content.setLayout(self.image_grid)
        scroll_area.setWidget(scroll_content)
        
        layout.addWidget(scroll_area)
        
        # Add a refresh button to search again
        refresh_button = QPushButton("Search Again")
        refresh_button.clicked.connect(self.search_images)
        layout.addWidget(refresh_button)

    def clear_image_grid(self):
        """Clear all widgets from the image grid."""
        clear_container(self.image_grid)

    def set_reading_and_definition(self, reading, definition):
        """Set the reading and definition for the prompt image page."""
        self.reading = reading
        self.definition = definition
        self.search_images()
    
    def search_images(self):
        """Search Google Images for both Japanese text and English meaning, and display results alternating between the two."""
        # Clear previous images
        self.clear_image_grid()
        self.image_thumbnails = []
        self.prompt_image_data = None
        
        # Show loading indicator
        loading_label = QLabel("Searching for images...")
        self.image_grid.addWidget(loading_label, 0, 0)

        simple_background_query(self.parent, lambda _: self.chatgpt.gen_prompt_image(self.japanese_text, self.english_text), self.add_chatgpt_image)
        simple_background_query(self.parent, lambda _: search_google_images(self.japanese_text), self.add_prompt_images)
        simple_background_query(self.parent, lambda _: search_google_images(self.english_text), self.add_prompt_images)

    def add_prompt_images(self, images):
        """Add images to the prompt images list."""
        if len(self.image_thumbnails) < 1:
            self.image_thumbnails = images
        else:
            self.image_thumbnails = [val for pair in zip(self.image_thumbnails, images) for val in pair]
        self.clear_image_grid()
        self.display_images()

    def add_chatgpt_image(self, image_data):
        """Add the ChatGPT-generated image to the image grid."""
        if not image_data:
            return

        # Insert the ChatGPT image at the beginning of the list
        image_data["thumbnail"] = pixmap_for_image(image_data["image"]).scaled(150, 150)
        self.image_thumbnails.insert(0, image_data)
        
        # Display all images including the new ChatGPT one
        self.clear_image_grid()
        self.display_images()

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

    def on_image_clicked(self):
        """Helper method to handle image clicks."""
        # Get the sender (the clicked label)
        sender = self.sender()
        if hasattr(sender, 'data'):
            self.select_image(sender.data)

    # TODO: there's got to be a way to simplify this.
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

    def get_prompt_html(self):
        """Get the selected image URL."""
        if not self.prompt_image_data:
            return None

        image = self.prompt_image_data.get("image", None)
        if not image:
            image = load_image_from_url(self.prompt_image_data["url"])

        return save_image(image, f"kaito_{self.japanese_text}.jpg")
