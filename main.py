import sys
import os
import random
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QWidget, QFileDialog, QFontDialog # Added QFontDialog
from PySide6.QtGui import QIcon, QAction, QFont, QPixmap, QColor # Added QFont, QPixmap, QColor
from PySide6.QtCore import QPoint, QTimer
import winreg
import win32com.client
import pythoncom

# Assume database_manager.py and card_widget.py are in the same directory
from database_manager import DatabaseManager
from card_widget import CardWidget

# --- Configuration ---
INITIAL_CARD_COUNT = 3
DB_PATH = "words.db" # Relative to main.py location

class CardManager(QWidget): # Inherit QWidget to handle signals/slots easily
    def __init__(self, db_manager):
        super().__init__() # Initialize QWidget base class
        self.db_manager = db_manager
        self.active_cards = [] # List to keep track of card widgets
        self.max_cards = INITIAL_CARD_COUNT
        self.screen_geometry = QApplication.primaryScreen().availableGeometry()
        # Store current font, initialize with default from CardWidget
        self.current_font = QFont("Arial", 14) 
        self.last_card_position = None  # Son kartın konumunu saklamak için

        # Timer to periodically check if more cards need to be added
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self.add_cards_if_needed)
        self.check_timer.start(2000) # Check every 2 seconds

        # Initial card creation
        self.add_cards_if_needed()


    def get_random_position(self):
        """Generates a random position within the screen bounds, avoiding edges slightly."""
        margin = 50 # Pixels from edge
        card_width_estimate = 200 # Approximate width for calculation
        card_height_estimate = 100 # Approximate height

        max_x = self.screen_geometry.width() - card_width_estimate - margin
        max_y = self.screen_geometry.height() - card_height_estimate - margin

        x = random.randint(margin, max(margin, max_x))
        y = random.randint(margin, max(margin, max_y))
        return QPoint(x, y)

    def create_card(self, word_data):
        """Creates and shows a single card widget."""
        word_id, english, turkish = word_data

        # Eğer son kart konumu varsa onu kullan, yoksa veritabanından al
        if self.last_card_position:
            initial_pos = self.last_card_position
        else:
            # Veritabanından kayıtlı son konumu al
            last_pos_str = self.db_manager.get_setting('last_card_position')
            if last_pos_str:
                try:
                    x, y = map(int, last_pos_str.split(','))
                    initial_pos = QPoint(x, y)
                except:
                    initial_pos = self.get_random_position()
            else:
                initial_pos = self.get_random_position()

        card = CardWidget(word_id, english, turkish, self.db_manager, initial_pos)
        card.update_font(self.current_font.family(), self.current_font.pointSize())
        card.learned_signal.connect(self.handle_learned)
        card.closed_signal.connect(self.handle_card_closed)
        card.show()
        self.active_cards.append(card)
        
        # Son kartın konumunu sakla
        self.last_card_position = initial_pos
        
        print(f"Created card for '{english}' (ID: {word_id}) at {initial_pos.x()},{initial_pos.y()}")

    def is_overlapping(self, new_pos, tolerance=50):
        """Checks if the new position overlaps significantly with existing cards."""
        # Sabit kart boyutlarını kullan
        card_width = 250  # CardWidget'ın varsayılan genişliği
        card_height = 180  # CardWidget'ın varsayılan yüksekliği
        
        new_rect = QWidget().geometry()
        new_rect.moveTo(new_pos)
        new_rect.setWidth(card_width)
        new_rect.setHeight(card_height)

        for card in self.active_cards:
            if card.geometry().intersects(new_rect.adjusted(-tolerance, -tolerance, tolerance, tolerance)):
                return True
        return False


    def add_cards_if_needed(self):
        """Fetches words and creates cards until the max_cards limit is reached."""
        needed = self.max_cards - len(self.active_cards)
        if needed <= 0:
            return

        print(f"Need to add {needed} cards.")
        words_to_add = self.db_manager.get_unlearned_words(needed)

        if not words_to_add:
            print("No more unlearned words in the database.")
            # Optionally disable timer or show message
            return

        for word_data in words_to_add:
            # Ensure we don't exceed max_cards if fewer words were returned
            if len(self.active_cards) < self.max_cards:
                 self.create_card(word_data)
            else:
                 break # Stop if we hit the limit during creation

    def handle_learned(self, word_id):
        """Handles the learned signal from a card."""
        print(f"[Manager] Received learned signal for word ID: {word_id}")
        success = self.db_manager.mark_as_learned(word_id)
        if success:
            print(f"[Manager] Successfully marked word ID {word_id} as learned in DB.")
        else:
            print(f"[Manager] Failed to mark word ID {word_id} as learned in DB.")
        # The card closes itself after emitting the signal via its close_card method

    def handle_card_closed(self, card_instance):
        """Handles the closed signal from a card."""
        print(f"[Manager] Received closed signal from card: {card_instance}")
        if card_instance in self.active_cards:
            # Kartın son konumunu sakla
            self.last_card_position = card_instance.pos()
            # Veritabanına son konumu kaydet
            self.db_manager.save_setting('last_card_position', f"{self.last_card_position.x()},{self.last_card_position.y()}")
            
            self.active_cards.remove(card_instance)
            print(f"[Manager] Removed card from active list. Count: {len(self.active_cards)}")
        # No need to call card_instance.close() here, it's already closing/closed.
        # Trigger check to add more cards if needed
        self.add_cards_if_needed()

    def set_max_cards(self, count):
        """Sets the desired number of active cards."""
        new_max = max(0, count) # Ensure non-negative
        print(f"Setting max cards to: {new_max}")
        self.max_cards = new_max

        # Close excess cards if needed
        while len(self.active_cards) > self.max_cards:
            card_to_close = self.active_cards[-1] # Close the last one added
            print(f"Closing excess card: {card_to_close.english_text}")
            card_to_close.close_card() # This will trigger handle_card_closed

        # Add cards if needed (will be handled by timer or called explicitly)
        self.add_cards_if_needed()

    def set_font_for_all_cards(self, font):
        """Applies the selected font to all active cards."""
        self.current_font = font
        print(f"Applying font: {font.family()}, Size: {font.pointSize()} to {len(self.active_cards)} cards.")
        for card in self.active_cards:
            card.update_font(font.family(), font.pointSize())

    def center_all_cards(self):
        """Tüm aktif kartları ekranın ortasına konumlandırır."""
        if not self.active_cards:
            return

        # Ekran boyutlarını al
        screen = QApplication.primaryScreen().availableGeometry()
        screen_center = screen.center()

        # İlk kartı merkeze yerleştir ve konumunu diğer kartlar için referans al
        first_card = self.active_cards[0]
        card_size = first_card.size()
        x = screen_center.x() - (card_size.width() // 2)
        y = screen_center.y() - (card_size.height() // 2)
        
        # Kartları merkeze yerleştir
        for card in self.active_cards:
            card.move(x, y)
            card.raise_()
            card.activateWindow()
        
        # Son konumu kaydet
        self.last_card_position = QPoint(x, y)
        self.db_manager.save_setting('last_card_position', f"{x},{y}")
        print(f"All cards centered at position: {x},{y}")

    def close_all_cards(self):
        """Closes all active card widgets."""
        print("Closing all cards...")
        # Iterate over a copy of the list because closing modifies the original list
        for card in list(self.active_cards):
            card.close_card()
        print("All cards closed.")

    def hide_all_cards(self):
        """Tüm aktif kartları gizler."""
        print("Hiding all cards...")
        for card in self.active_cards:
            card.hide()
        print("All cards hidden.")

    def show_all_cards(self):
        """Tüm aktif kartları gösterir."""
        print("Showing all cards...")
        for card in self.active_cards:
            card.show()
        print("All cards shown.")


# --- System Tray ---
def setup_tray_icon(app, manager):
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("System tray not available on this system.")
        return None

    # Create default icon
    icon = QIcon()
    pixmap = QPixmap(16, 16)
    pixmap.fill(QColor(60, 60, 80))
    icon.addPixmap(pixmap)
    
    tray_icon = QSystemTrayIcon(icon, parent=app)
    tray_icon.setToolTip("English Flashcards")

    menu = QMenu()

    # Appearance submenu
    appearance_menu = menu.addMenu("Görünüm")
    
    # Text color submenu
    colors = {
        "Beyaz": "#FFFFFF",
        "Sarı": "#FFEB3B",
        "Açık Mavi": "#03A9F4",
        "Açık Yeşil": "#8BC34A",
        "Turuncu": "#FF9800",
        "Pembe": "#E91E63"
    }
    
    color_menu = appearance_menu.addMenu("Yazı Rengi")
    for color_name, color_code in colors.items():
        color_action = QAction(color_name, parent=app)
        color_action.triggered.connect(lambda checked, c=color_code: change_text_color(manager, c))
        color_menu.addAction(color_action)

    appearance_menu.addSeparator()

    # Font Action
    font_action = QAction("Yazı Tipi...", parent=app)
    font_action.triggered.connect(lambda: trigger_font_change(manager))
    appearance_menu.addAction(font_action)

    menu.addSeparator()

    # Card Count Control submenu
    card_menu = menu.addMenu("Kart Sayısı")
    
    add_card_action = QAction("Bir Kart Ekle", parent=app)
    add_card_action.triggered.connect(lambda: manager.set_max_cards(manager.max_cards + 1))
    card_menu.addAction(add_card_action)

    remove_card_action = QAction("Bir Kart Azalt", parent=app)
    remove_card_action.triggered.connect(lambda: manager.set_max_cards(manager.max_cards - 1))
    card_menu.addAction(remove_card_action)

    reset_cards_action = QAction("3 Karta Sıfırla", parent=app)
    reset_cards_action.triggered.connect(lambda: manager.set_max_cards(3))
    card_menu.addAction(reset_cards_action)

    menu.addSeparator()

    # Word Management submenu
    word_menu = menu.addMenu("Kelime Yönetimi")
    
    import_action = QAction("Txt'den Kelime Ekle...", parent=app)
    import_action.triggered.connect(lambda: trigger_import(manager.db_manager))
    word_menu.addAction(import_action)

    stats_action = QAction("İstatistikleri Göster", parent=app)
    stats_action.triggered.connect(lambda: show_stats(manager.db_manager))
    word_menu.addAction(stats_action)

    menu.addSeparator()

    # Kartları Ortala seçeneği
    center_cards_action = QAction("Kartları Ortala", parent=app)
    center_cards_action.triggered.connect(manager.center_all_cards)
    menu.addAction(center_cards_action)

    menu.addSeparator()

    # Hide/Show all cards
    toggle_cards_action = QAction("Kartları Gizle", parent=app)
    def toggle_cards():
        if toggle_cards_action.text() == "Kartları Gizle":
            manager.hide_all_cards()
            toggle_cards_action.setText("Kartları Göster")
        else:
            manager.show_all_cards()
            toggle_cards_action.setText("Kartları Gizle")
    toggle_cards_action.triggered.connect(toggle_cards)
    menu.addAction(toggle_cards_action)

    menu.addSeparator()

    # Quit Action
    quit_action = QAction("Çıkış", parent=app)
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)

    tray_icon.setContextMenu(menu)
    tray_icon.show()
    return tray_icon

def change_text_color(manager, color):
    """Tüm kartların metin rengini değiştirir"""
    for card in manager.active_cards:
        card.set_text_color(color)

def show_stats(db_manager):
    """İstatistikleri göster"""
    from PySide6.QtWidgets import QMessageBox
    
    stats = db_manager.get_stats()
    message = (
        f"Toplam Kelime: {stats['total']}\n"
        f"Öğrenilen: {stats['learned']}\n"
        f"Öğrenilecek: {stats['unlearned']}"
    )
    
    msg_box = QMessageBox()
    msg_box.setWindowTitle("İstatistikler")
    msg_box.setText(message)
    msg_box.setIcon(QMessageBox.Icon.Information)
    msg_box.exec_()
    
    # Konsola da yazdır
    print("\n--- Database Stats ---")
    print(message)
    print("--------------------\n")


# --- Font Change Function ---
def trigger_font_change(manager):
    """Opens a font dialog and applies the selected font to all cards."""
    font, ok = QFontDialog.getFont(manager.current_font, None, "Select Font") # Pass current font
    
    if ok:
        print(f"Font selected: {font.family()}, Size: {font.pointSize()}")
        manager.set_font_for_all_cards(font)
    else:
        print("Font selection cancelled.")


# --- Import Function ---
def trigger_import(db_manager):
    """Opens a file dialog and imports words from the selected text file."""
    filepath, _ = QFileDialog.getOpenFileName(
        None, # Parent window
        "Select Word File to Import", # Dialog title
        "", # Starting directory (empty means default/last used)
        "Text Files (*.txt);;All Files (*)" # File filters
    )
    
    if filepath:
        print(f"Attempting to import words from: {filepath}")
        # Assuming ' - ' as the separator, defined in database_manager
        success, failed = db_manager.import_from_text_file(filepath) 
        print(f"Import finished. Success: {success}, Failed/Skipped: {failed}")
        # Optional: Show a message box with results
        # from PySide6.QtWidgets import QMessageBox
        # QMessageBox.information(None, "Import Complete", f"Successfully imported: {success}\nFailed/Skipped: {failed}")
    else:
        print("Import cancelled by user.")


def create_startup_shortcut():
    """Windows başlangıçta otomatik başlatma için kısayol oluşturur"""
    try:
        # Startup klasörünün yolunu al
        startup_folder = os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
        
        # Exe dosyasının tam yolunu al
        if getattr(sys, 'frozen', False):
            # PyInstaller ile oluşturulan exe için
            exe_path = sys.executable
        else:
            # Normal Python betiği için
            exe_path = os.path.abspath(__file__)
        
        # Kısayol dosyasının yolu
        shortcut_path = os.path.join(startup_folder, 'English_Flashcards.lnk')
        
        # Eğer kısayol zaten varsa, oluşturma
        if os.path.exists(shortcut_path):
            return
            
        # Windows Shell nesnesi oluştur
        shell = win32com.client.Dispatch("WScript.Shell")
        
        # Kısayol oluştur
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.TargetPath = exe_path
        shortcut.WorkingDirectory = os.path.dirname(exe_path)
        shortcut.IconLocation = exe_path
        shortcut.save()
        
        print("Startup shortcut created successfully")
    except Exception as e:
        print(f"Error creating startup shortcut: {e}")

# --- Main Execution ---
if __name__ == "__main__":
    # Ensure the application quits when the last window is closed (important for tray icon mode)
    QApplication.setQuitOnLastWindowClosed(False)

    # Startup kısayolu oluştur
    create_startup_shortcut()

    app = QApplication(sys.argv)

    # --- Database Setup ---
    # Check if DB exists, maybe add initial words if empty?
    db = DatabaseManager(DB_PATH)
    stats = db.get_stats()
    if stats['total'] == 0:
        print("Database is empty. Adding some example words.")
        db.add_word("hello", "merhaba")
        db.add_word("world", "dünya")
        db.add_word("python", "piton")
        db.add_word("computer", "bilgisayar")
        db.add_word("learn", "öğrenmek")


    # --- Card Manager ---
    manager = CardManager(db)

    # --- System Tray Setup ---
    tray_icon = setup_tray_icon(app, manager)
    if tray_icon is None and not QSystemTrayIcon.isSystemTrayAvailable():
         print("Error: System tray is required but not available. Exiting.")
         # If no tray, the app might exit immediately without a visible window.
         # Need a fallback or exit.
         # sys.exit(1) # Or create a minimal control window

    # --- Application Exit Handling ---
    def on_quit():
        print("Quitting application...")
        manager.close_all_cards()
        db.close()
        print("Cleanup complete. Exiting.")

    app.aboutToQuit.connect(on_quit)


    print(f"Application started. Displaying {manager.max_cards} card(s). Right-click tray icon for options.")
    sys.exit(app.exec())
