from aqt import mw
from aqt.qt import *
from aqt.operations import QueryOp

import requests

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

def clear_container(container):
    """Helper to clear all widgets from a container."""
    while container.count():
        item = container.takeAt(0)
        widget = item.widget()
        if widget:
            widget.deleteLater()

def simple_background_query(parent, fn, success):
    """Run an operation in the background and call a success callback with the result."""
    op = QueryOp(
        parent=parent,
        op=fn,
        success=success,
    )
    op.without_collection().run_in_background()
