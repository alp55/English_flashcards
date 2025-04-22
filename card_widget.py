import sys
# Add necessary imports
import requests
from PySide6.QtWidgets import (QWidget, QLabel, QPushButton, QVBoxLayout, QApplication, QSizePolicy, QHBoxLayout)
from PySide6.QtCore import Qt, Signal, QPoint, QPropertyAnimation, QEasingCurve, Property, QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QMouseEvent, QPalette, QCursor, QPixmap, QImage

# Pixabay API Key (Consider moving this to a config file or environment variable)
PIXABAY_API_KEY = "38326855-7df9d0fe9cd4818c505baef9c"

class CardWidget(QWidget):
    learned_signal = Signal(int)
    closed_signal = Signal(object)

    def __init__(self, word_id, english, turkish, db_manager, initial_pos=None, parent=None):
        super().__init__(parent)
        self.word_id = word_id
        self.english_text = english
        self.turkish_text = turkish
        self.db_manager = db_manager
        self.is_english_visible = True
        self._drag_start_position = None
        self.drag_enabled = False  # Sürükleme kontrolü için yeni değişken

        # Ayarlardan renk ve konum bilgisini al
        self.text_color = QColor(self.db_manager.get_setting('text_color', '#F0F0F0'))
        self.background_color = QColor(60, 60, 80, 210)
        self.border_radius = 12
        
        # --- Window Properties ---
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |  # Çerçevesiz pencere
            Qt.WindowType.Tool |                 # Görev çubuğunda görünmez
            Qt.WindowType.WindowStaysOnBottomHint  # En alt katmanda kalır
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)  # Tıklandığında bile en üste çıkmaz

        # --- Styling ---
        self.setMinimumSize(250, 250) # Minimum size increased
        self.resize(300, 300)         # Initial size increased

        # --- Title Bar ---
        self.title_bar = QWidget(self)
        self.title_bar.setFixedHeight(30)  # Başlık çubuğu yüksekliği
        self.title_bar.setStyleSheet("""
            QWidget {
                background-color: #444444;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }
        """)
        
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(5, 0, 5, 0)
        title_layout.setSpacing(2)

        # Close button (sağ üst)
        self.close_button = QPushButton("×", self)
        self.close_button.setFixedSize(20, 20)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: #AA5555;
                color: white;
                border: none;
                border-radius: 3px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #CC6666; }
        """)
        
        title_layout.addStretch()
        title_layout.addWidget(self.close_button)

        # --- Main Content ---
        # Add image label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumHeight(100) # Give some space for the image
        self.image_label.setStyleSheet("background-color: #555; border-radius: 5px;") # Placeholder style

        self.english_label = QLabel(self.english_text)
        self.turkish_label = QLabel(self.turkish_text)
        self.learned_button = QPushButton("Learned")

        # --- Styling Widgets ---
        self.current_font_family = "Arial"
        self.current_font_size = 14
        self.update_font(self.current_font_family, self.current_font_size)

        self.turkish_label.setVisible(False)

        self.learned_button.setFont(QFont(self.current_font_family, max(8, self.current_font_size - 2)))
        self.learned_button.setStyleSheet("""
            QPushButton {
                background-color: #55AA55;
                color: white;
                border: none;
                padding: 5px;
                border-radius: 5px;
                min-height: 20px;
            }
            QPushButton:hover { background-color: #448844; }
            QPushButton:pressed { background-color: #336633; }
        """)
        self.learned_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        # --- Layout ---
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 10)  # Üst margin'i 0 yapıyoruz
        main_layout.setSpacing(0)
        
        main_layout.addWidget(self.title_bar)
        
        content_widget = QWidget()
        content_widget.setStyleSheet("""
            QWidget {
                background: transparent;
            }
        """)
        
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10) # Adjusted margins
        content_layout.setSpacing(8) # Adjusted spacing

        # Add image label to layout
        content_layout.addWidget(self.image_label)
        content_layout.addSpacing(5) # Add space between image and text
        
        # Kelimeleri içeren container
        words_container = QWidget()
        words_layout = QVBoxLayout(words_container)
        words_layout.setContentsMargins(0, 0, 0, 0)
        words_layout.setSpacing(5)
        words_layout.addWidget(self.english_label)
        words_layout.addWidget(self.turkish_label)
        
        # Adjust stretch factors if needed, or remove them
        # content_layout.addStretch(1)
        content_layout.addWidget(words_container)
        # content_layout.addStretch(1)
        content_layout.addSpacing(10) # Space before button
        content_layout.addWidget(self.learned_button, alignment=Qt.AlignmentFlag.AlignCenter) # Center button
        
        main_layout.addWidget(content_widget)
        self.setLayout(main_layout)

        # --- Connections ---
        self.learned_button.clicked.connect(self.mark_learned)
        self.close_button.clicked.connect(self.close_card)

        # --- Initial Position ---
        if initial_pos:
            self.move(initial_pos)
        else:
            # Son kaydedilen pozisyonu al, yoksa ekranın ortasına yerleştir
            last_pos_str = self.db_manager.get_setting('last_card_position')
            if last_pos_str:
                try:
                    x, y = map(int, last_pos_str.split(','))
                    self.move(x, y)
                except:
                    self.center_on_screen()
            else:
                self.center_on_screen()

        # --- Animation Setup ---
        self._opacity = 1.0
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(150)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        # --- Fetch Image ---
        self.fetch_and_display_image(self.english_text)

    # --- Image Fetching and Display ---
    def fetch_image_url(self, query):
        """Fetches an image URL from Pixabay based on the query."""
        url = "https://pixabay.com/api/"
        params = {
            'key': PIXABAY_API_KEY,
            'q': query,
            'image_type': 'photo',
            'per_page': 3 # Fetch a few in case the first is bad
        }
        try:
            response = requests.get(url, params=params, timeout=5) # Add timeout
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            data = response.json()
            if data['hits']:
                # Maybe add logic later to pick the best hit, for now take the first
                return data['hits'][0]['webformatURL']
            else:
                print(f"No image found on Pixabay for '{query}'")
                return None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching image URL for '{query}': {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during image URL fetch: {e}")
            return None

    def display_image_from_url(self, image_url):
        """Downloads image data from URL and displays it."""
        if not image_url:
            self.image_label.setText("No Image") # Placeholder text
            self.image_label.setStyleSheet("background-color: #555; border-radius: 5px; color: #AAA;")
            return

        try:
            response = requests.get(image_url, timeout=10) # Add timeout
            response.raise_for_status()

            image_data = response.content
            pixmap = QPixmap()
            if pixmap.loadFromData(image_data):
                # Scale pixmap to fit the label while keeping aspect ratio
                scaled_pixmap = pixmap.scaled(self.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.image_label.setPixmap(scaled_pixmap)
                self.image_label.setStyleSheet("") # Clear background style if image loads
            else:
                print("Failed to load image data into QPixmap.")
                self.image_label.setText("Load Error")
                self.image_label.setStyleSheet("background-color: #773333; border-radius: 5px; color: #FCC;")


        except requests.exceptions.RequestException as e:
            print(f"Error downloading image data: {e}")
            self.image_label.setText("Net Error")
            self.image_label.setStyleSheet("background-color: #773333; border-radius: 5px; color: #FCC;")
        except Exception as e:
            print(f"An unexpected error occurred during image display: {e}")
            self.image_label.setText("Disp Error")
            self.image_label.setStyleSheet("background-color: #773333; border-radius: 5px; color: #FCC;")


    def fetch_and_display_image(self, query):
        """Fetches the image URL and then displays the image."""
        # Consider running this in a separate thread for complex apps
        # to avoid blocking the UI during network requests.
        image_url = self.fetch_image_url(query)
        self.display_image_from_url(image_url)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            # Tıklanan pozisyonun başlık çubuğunda olup olmadığını kontrol et
            if self.title_bar.geometry().contains(event.pos()):
                self._drag_start_position = event.globalPosition().toPoint() - self.pos()
            elif not any(child.underMouse() for child in [self.learned_button, self.close_button]):
                self.flip_card()
                event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_start_position is not None:
            newPos = event.globalPosition().toPoint() - self._drag_start_position
            self.move(newPos)
            # Kartın yeni konumunu kaydet
            self.db_manager.save_setting('last_card_position', f"{newPos.x()},{newPos.y()}")
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_position = None
        super().mouseReleaseEvent(event)

    # --- Custom Painting for Background ---
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing) # Smooth edges
        painter.setBrush(QBrush(self.background_color))
        painter.setPen(QPen(Qt.PenStyle.NoPen)) # No border outline
        # Draw rounded rectangle background
        painter.drawRoundedRect(self.rect(), self.border_radius, self.border_radius)
        super().paintEvent(event) # Ensure child widgets are painted

    # --- Window Opacity Property for Animation ---
    @Property(float)
    def windowOpacity(self):
        return self._opacity

    @windowOpacity.setter
    def windowOpacity(self, value):
        self._opacity = value
        self.setWindowOpacity(value)


    # --- Interaction ---
    def flip_card(self):
        # Simple fade-out/fade-in animation
        self.animation.stop()
        self.animation.setDirection(QPropertyAnimation.Direction.Forward) # Fade out
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        self.animation.finished.connect(self._toggle_visibility_and_fade_in)
        # Ensure animation doesn't restart if already running
        if self.animation.state() == QPropertyAnimation.State.Stopped:
            self.animation.setDirection(QPropertyAnimation.Direction.Forward) # Fade out
            self.animation.setStartValue(1.0)
            self.animation.setEndValue(0.0)
            # Use a lambda to disconnect after execution, preventing issues if called rapidly
            connection = lambda: self._toggle_visibility_and_fade_in()
            try:
                 self.animation.finished.disconnect() # Disconnect previous potentially
            except RuntimeError:
                 pass # No connection existed
            self.animation.finished.connect(connection)
            self.animation.start()


    def _toggle_visibility_and_fade_in(self):
        # This runs after fade-out completes
        try:
            self.animation.finished.disconnect() # Disconnect self
        except RuntimeError:
            pass # Ignore if already disconnected

        self.is_english_visible = not self.is_english_visible
        self.english_label.setVisible(self.is_english_visible)
        self.turkish_label.setVisible(not self.is_english_visible)

        # Fade back in
        self.animation.setDirection(QPropertyAnimation.Direction.Forward) # Fade in
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.start()


    def mark_learned(self):
        print(f"Marking word ID {self.word_id} as learned.")
        # Option 1: Call db_manager directly (if passed in)
        # success = self.db_manager.mark_as_learned(self.word_id)

        # Option 2: Emit signal (preferred for decoupling)
        self.learned_signal.emit(self.word_id)

        # Close the card after marking as learned
        self.close_card()

    def close_card(self):
        # Optional: Add fade-out animation before closing
        self.closed_signal.emit(self) # Notify manager
        self.close() # Close the widget window

    def center_on_screen(self):
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        widget_geometry = self.frameGeometry()
        x = (screen_geometry.width() - widget_geometry.width()) // 2
        y = (screen_geometry.height() - widget_geometry.height()) // 2
        self.move(x, y)

    def update_font(self, family, size):
        """Updates the font for the text labels."""
        self.current_font_family = family
        self.current_font_size = size
        font_bold = QFont(family, size, QFont.Weight.Bold)
        font_normal = QFont(family, max(8, size - 2)) # Button font slightly smaller, min size 8

        for label in [self.english_label, self.turkish_label]:
            label.setFont(font_bold)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            # Set text color using palette
            palette = label.palette()
            palette.setColor(QPalette.ColorRole.WindowText, self.text_color)
            label.setPalette(palette)

        self.learned_button.setFont(font_normal)

    def set_text_color(self, color):
        """Kartın metin rengini değiştirir"""
        if isinstance(color, str):
            color = QColor(color)
        self.text_color = color
        self.db_manager.save_setting('text_color', color.name())
        
        # Rengi etiketlere uygula
        for label in [self.english_label, self.turkish_label]:
            palette = label.palette()
            palette.setColor(QPalette.ColorRole.WindowText, self.text_color)
            label.setPalette(palette)

        self.update()  # Widget'ı yeniden çiz


# --- Example Usage (for testing this widget directly) ---
if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Dummy db_manager for testing signals
    class DummyDBManager:
        def mark_as_learned(self, word_id):
            print(f"[DummyDB] Marked word ID {word_id} as learned.")
            return True

        def get_setting(self, key, default=None):
            return default

        def save_setting(self, key, value):
            print(f"[DummyDB] Saved setting {key} = {value}")

    dummy_db = DummyDBManager()

    # Create a card
    card = CardWidget(1, "Example", "Örnek", dummy_db)

    # Connect signal for testing
    def handle_learned(word_id):
        print(f"[TestApp] Received learned signal for word ID: {word_id}")

    def handle_closed(widget_instance):
         print(f"[TestApp] Received closed signal for widget: {widget_instance}")
         # In a real app, the manager would remove this from its list

    card.learned_signal.connect(handle_learned)
    card.closed_signal.connect(handle_closed)

    card.show()
    sys.exit(app.exec())
