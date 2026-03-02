import sqlite3

old = sqlite3.connect("database/backup_vps.db")
new = sqlite3.connect("database/purchase_requests.db")

old_cur = old.cursor()
old_cur.execute("SELECT username, signature FROM users WHERE signature IS NOT NULL AND signature != ''")
sigs = old_cur.fetchall()
print(f"التواقيع الموجودة: {len(sigs)}")

new_cur = new.cursor()
for username, sig in sigs:
    new_cur.execute("UPDATE users SET signature = ? WHERE username = ?", (sig, username))
    if new_cur.rowcount > 0:
        print(f"  ok: {username}")
    else:
        print(f"  skip: {username}")

new.commit()
old.close()
new.close()
print("تم!")
