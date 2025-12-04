import psycopg2
import psycopg2.extras
import json
import os

def read_data_from_db():
    """
    Connects to the PostgreSQL database, reads the first 10 rows from specified tables,
    and prints them in a JSON format.
    """
    config_path = os.path.join('config', 'db_config.json')
    
    if not os.path.exists(config_path):
        print(f"Error: Database configuration file not found at '{config_path}'")
        print("Please create it based on 'config/db_config.example.json'")
        return

    try:
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            config = json.load(f)
        pg_config = config.get('postgres')
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error reading or parsing configuration file: {e}")
        return

    conn = None
    try:
        # Connect to the database
        conn = psycopg2.connect(**pg_config)
        
        # Use a dictionary cursor to get results as dicts
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        tables_to_read = ['assets', 'work_history', 'events', 'chat_history', 'metrics', 'documents', 'doc_chunks']
        all_data = {}

        print("--- Reading data from database ---")
        for table in tables_to_read:
            try:
                print(f"\n--- Querying table: {table} ---")
                query = f"SELECT * FROM {table} LIMIT 10;"
                cursor.execute(query)
                
                rows = cursor.fetchall()
                
                if not rows:
                    print("No data found.")
                    all_data[table] = []
                    continue

                # Convert rows to a list of dictionaries
                results = [dict(row) for row in rows]
                
                # Pretty print the JSON output
                formatted_json = json.dumps(results, indent=2, default=str)
                print(formatted_json)
                all_data[table] = results

            except psycopg2.Error as e:
                print(f"An error occurred while querying table {table}: {e}")
                conn.rollback() # Rollback any transaction state
        
        return all_data

    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
    finally:
        if conn:
            conn.close()
            # print("\n--- Database connection closed ---")

if __name__ == "__main__":
    read_data_from_db()
