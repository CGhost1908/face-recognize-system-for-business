import os
import shutil
from database import get_db_connection

conn = get_db_connection()
c = conn.cursor()

# Remove duplicate Guest_* from users, user_embeddings, entry_logs
c.execute("DELETE FROM users WHERE name LIKE 'Guest_%'")
c.execute("DELETE FROM user_embeddings WHERE user_name LIKE 'Guest_%'")
c.execute("DELETE FROM entry_logs WHERE user_name LIKE 'Guest_%'")
conn.commit()

c.execute("SELECT id, name, user_type FROM users")
rows = c.fetchall()
print(f"Cleaned database! Remaining users ({len(rows)}):")
for r in rows:
    print(f"  ID: {r['id']} | Name: {r['name']} | Type: {r['user_type']}")

conn.close()

# Also clean duplicate folders in dataset/
dataset_dir = os.path.join(os.path.dirname(__file__), 'dataset')
for item in os.listdir(dataset_dir):
    if item.startswith('Guest_'):
        folder_path = os.path.join(dataset_dir, item)
        if os.path.isdir(folder_path):
            shutil.rmtree(folder_path, ignore_errors=True)
print("Cleaned duplicate guest folders from dataset directory.")
