from aqt import mw
from aqt.qt import *

from .utils import *
from .chatgpt import ChatGPT
# Mnemonic Page
##########################################################################

class MnemonicPage(QWizardPage):
    def __init__(self, parent, japanese_text, english_text, chatgpt=None):
        super().__init__(parent)
        self.japanese_text = japanese_text
        self.english_text = english_text
        self.chatgpt = chatgpt if chatgpt else ChatGPT(mw.addonManager.getConfig(__name__))
        self.mnemonic_images = []

        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Create a scroll area for the mnemonic list
        self.mnemonic_list = QVBoxLayout()
        mnemonic_scroll_area = QScrollArea()
        mnemonic_scroll_area.setWidgetResizable(True)
        mnemonic_scroll_content = QWidget()
        mnemonic_scroll_content.setLayout(self.mnemonic_list)
        mnemonic_scroll_area.setWidget(mnemonic_scroll_content)
        layout.addWidget(mnemonic_scroll_area)
        
        # Add a refresh button to generate new mnemonics
        refresh_mnemonic_button = QPushButton("Generate New Mnemonics")
        refresh_mnemonic_button.clicked.connect(self.generate_mnemonics)
        layout.addWidget(refresh_mnemonic_button)

    def clear_mnemonic_list(self):
        """Clear all widgets from the mnemonic list."""
        clear_container(self.mnemonic_list)
    
    def generate_mnemonics(self):
        """Generate mnemonic stories using ChatGPT."""
        self.clear_mnemonic_list()
        
        # Show loading indicator
        loading_label = QLabel("Generating mnemonics...")
        self.mnemonic_list.addWidget(loading_label)
        
        # Run the query in the background
        simple_background_query(
            self.parent,
            lambda _: self.chatgpt.gen_mnemonics(self.japanese_text, self.english_text),
            self.display_mnemonics
        )
    
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
        self.mnemonic_images = [None] * len(mnemonics)
        
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

    def generate_mnemonic_image(self, index, story):
        """Generate an illustration for a mnemonic story using ChatGPT."""
        # Generate image in background
        simple_background_query(
            self.parent,
            lambda _: self.chatgpt.gen_mnemonic_image(story),
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
            clear_container(image_container.layout())
            
            # Create image label
            image_label = QLabel()
            image_label.setFixedSize(200, 200)
            image_label.setScaledContents(True)
            image_label.setPixmap(pixmap_for_image(image_data["image"]).scaled(150, 150))
            
            # Create regenerate button
            regen_button = QPushButton("Regenerate Illustration")
            regen_button.clicked.connect(lambda: self.generate_mnemonic_image(index, self.mnemonic_editors[index].toPlainText()))
            
            # Add to layout
            image_container.layout().addWidget(image_label)
            image_container.layout().addWidget(regen_button)

    def get_selected_mnemonic(self):
        """Get the selected mnemonic text and its illustration."""
        if self.selected_mnemonic_index is None:
            return None
        
        # Get the current text from the selected editor
        text = self.mnemonic_editors[self.selected_mnemonic_index].toPlainText()
        if self.mnemonic_images[self.selected_mnemonic_index]:
            text += "<br>\n" + save_image(
                self.mnemonic_images[self.selected_mnemonic_index]["image"],
                f"kaito_mnemonic_{self.japanese_text}.jpg")
                
        return text

