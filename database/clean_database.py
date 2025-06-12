from sqlalchemy import create_engine, text
from pathlib import Path

def clean_database():
    # Get the project root directory
    project_root = Path(__file__).parent.parent.parent
    db_path = project_root / "game_data.db"
    
    # Create engine
    engine = create_engine(f'sqlite:///{db_path}')
    
    with engine.connect() as conn:
        # Delete all data from tables
        conn.execute(text("DELETE FROM game_instances;"))
        conn.execute(text("DELETE FROM rooms;"))
        
        # Try to reset SQLite sequence if it exists
        try:
            conn.execute(text("DELETE FROM sqlite_sequence WHERE name='rooms';"))
            conn.execute(text("DELETE FROM sqlite_sequence WHERE name='game_instances';"))
        except Exception:
            pass  # Ignore if sqlite_sequence doesn't exist
        
        conn.commit()
        print("Database cleaned successfully!")

if __name__ == "__main__":
    clean_database() 