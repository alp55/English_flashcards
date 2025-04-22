import sqlite3
import os

DB_NAME = "words.db"

class DatabaseManager:
    def __init__(self, db_path=DB_NAME):
        """Initializes the database connection and creates the table if needed."""
        # Ensure the directory for the db exists if a path is provided
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._create_table()

    def _create_table(self):
        """Creates the words table if it doesn't exist."""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                english TEXT NOT NULL UNIQUE,
                turkish TEXT NOT NULL,
                learned BOOLEAN NOT NULL DEFAULT 0
            )
        ''')
        
        # Settings table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')
        self.conn.commit()

    def add_word(self, english, turkish):
        """Adds a single word pair to the database. Ignores if English word already exists."""
        try:
            self.cursor.execute('''
                INSERT INTO words (english, turkish) VALUES (?, ?)
            ''', (english.strip(), turkish.strip()))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Handle cases where the English word (UNIQUE constraint) already exists
            print(f"Word '{english}' already exists. Skipping.")
            return False
        except Exception as e:
            print(f"Error adding word '{english}': {e}")
            return False


    def import_from_text_file(self, filepath, separator=' - '):
        """Imports words from a text file.
        
        Args:
            filepath (str): Path to the text file.
            separator (str): The string separating English and Turkish words.
        
        Returns:
            tuple: (success_count, failure_count)
        """
        success_count = 0
        failure_count = 0
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or separator not in line:
                        print(f"Skipping invalid line: {line}")
                        failure_count += 1
                        continue
                    
                    parts = line.split(separator, 1)
                    if len(parts) == 2:
                        english, turkish = parts
                        if self.add_word(english.strip(), turkish.strip()):
                            success_count += 1
                        else:
                            # add_word handles IntegrityError (duplicates)
                            failure_count +=1 
                    else:
                        print(f"Skipping improperly formatted line: {line}")
                        failure_count += 1
        except FileNotFoundError:
            print(f"Error: File not found at {filepath}")
            return 0, 0
        except Exception as e:
            print(f"An error occurred during import: {e}")
            return success_count, failure_count
            
        print(f"Import complete. Added: {success_count}, Failed/Skipped: {failure_count}")
        return success_count, failure_count

    def get_unlearned_words(self, count=10):
        """Fetches a specified number of unlearned words."""
        self.cursor.execute('''
            SELECT id, english, turkish FROM words 
            WHERE learned = 0 
            ORDER BY RANDOM() 
            LIMIT ?
        ''', (count,))
        return self.cursor.fetchall() # Returns list of tuples (id, english, turkish)

    def mark_as_learned(self, word_id):
        """Marks a word as learned in the database."""
        try:
            self.cursor.execute('''
                UPDATE words SET learned = 1 WHERE id = ?
            ''', (word_id,))
            self.conn.commit()
            return self.cursor.rowcount > 0 # Returns True if a row was updated
        except Exception as e:
            print(f"Error marking word ID {word_id} as learned: {e}")
            return False
            
    def get_stats(self):
        """Returns statistics about the words in the database."""
        try:
            self.cursor.execute("SELECT COUNT(*) FROM words")
            total = self.cursor.fetchone()[0]
            self.cursor.execute("SELECT COUNT(*) FROM words WHERE learned = 1")
            learned = self.cursor.fetchone()[0]
            unlearned = total - learned
            return {"total": total, "learned": learned, "unlearned": unlearned}
        except Exception as e:
            print(f"Error getting stats: {e}")
            return {"total": 0, "learned": 0, "unlearned": 0}

    def save_setting(self, key, value):
        """Ayarları veritabanına kaydet"""
        self.cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value)
            VALUES (?, ?)
        ''', (key, str(value)))
        self.conn.commit()

    def get_setting(self, key, default=None):
        """Veritabanından ayar değerini al"""
        self.cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        result = self.cursor.fetchone()
        return result[0] if result else default

    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()
            print("Database connection closed.")

if __name__ == '__main__':
    # Example Usage (for testing)
    db_manager = DatabaseManager()
    
    # Add some words
    db_manager.add_word("hello", "merhaba")
    db_manager.add_word("world", "dünya")
    db_manager.add_word("computer", "bilgisayar")
    
    # Create a dummy import file
    dummy_file = "temp_import.txt"
    with open(dummy_file, "w", encoding="utf-8") as f:
        f.write("cat - kedi\n")
        f.write("dog - köpek\n")
        f.write("house - ev\n")
        f.write("hello - selam\n") # Duplicate test
        f.write("invalid line\n") # Invalid format test
        
    # Import from file
    print("\nImporting from file:")
    db_manager.import_from_text_file(dummy_file)
    os.remove(dummy_file) # Clean up dummy file
    
    # Get unlearned words
    print("\nUnlearned words:")
    unlearned = db_manager.get_unlearned_words(5)
    for word_id, eng, tur in unlearned:
        print(f"ID: {word_id}, Eng: {eng}, Tur: {tur}")
        
    # Mark one as learned (assuming ID 1 exists)
    if unlearned:
        first_word_id = unlearned[0][0]
        print(f"\nMarking word ID {first_word_id} as learned...")
        if db_manager.mark_as_learned(first_word_id):
             print("Marked successfully.")
        else:
             print("Failed to mark as learned.")

    # Get stats
    print("\nDatabase Stats:")
    stats = db_manager.get_stats()
    print(stats)

    # Close connection
    db_manager.close()
