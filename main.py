import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes
import hashlib
import os
import sqlite3
from datetime import datetime

# --- Core encryption logic ---

def derive_key(password, salt):
    # derives a fixed 32-byte AES key from the password
    # PBKDF2's repeat count slows this down on purpose, resisting brute-force
    return PBKDF2(password, salt, dkLen=32, count=100000)

def calculate_hash(data):
    # SHA-256 hash, used to verify correct password / detect tampering
    return hashlib.sha256(data).digest()

def encrypt_image(file_path, password):
    with open(file_path, 'rb') as f:
        plaintext = f.read()

    original_hash = calculate_hash(plaintext)

    salt = get_random_bytes(16)
    key = derive_key(password, salt)

    cipher = AES.new(key, AES.MODE_CBC)
    iv = cipher.iv

    pad_len = 16 - (len(plaintext) % 16)
    padded_data = plaintext + bytes([pad_len]) * pad_len

    ciphertext = cipher.encrypt(padded_data)

    # file format: salt + iv + hash + ciphertext, in that order
    output_path = file_path + '.enc'
    with open(output_path, 'wb') as f:
        f.write(salt + iv + original_hash + ciphertext)

    return output_path

def decrypt_image(file_path, password):
    with open(file_path, 'rb') as f:
        raw = f.read()

    # file too small to contain salt+iv+hash means it's not a valid .enc file
    if len(raw) < 64:
        raise ValueError("This file is too small to be a valid encrypted file from this app.")

    salt = raw[:16]
    iv = raw[16:32]
    stored_hash = raw[32:64]
    ciphertext = raw[64:]

    # AES-CBC ciphertext must be a multiple of 16 bytes
    if len(ciphertext) % 16 != 0:
        raise ValueError("This file's structure doesn't match an encrypted file from this app.")

    key = derive_key(password, salt)
    cipher = AES.new(key, AES.MODE_CBC, iv=iv)

    padded_data = cipher.decrypt(ciphertext)

    pad_len = padded_data[-1]
    plaintext = padded_data[:-pad_len]

    new_hash = calculate_hash(plaintext)

    # mismatch = wrong password or tampered file
    if new_hash != stored_hash:
        raise ValueError("Hash mismatch - wrong password or file was tampered with")

    output_path = file_path.replace('.enc', '_decrypted.jpg')
    with open(output_path, 'wb') as f:
        f.write(plaintext)

    return output_path

# --- Activity Log (SQLite) ---

def init_database():
    # creates the log table once; does nothing on later runs if it already exists
    conn = sqlite3.connect("activity_log.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            action TEXT,
            status TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_activity(filename, action, status):
    # records one row per encrypt/decrypt attempt, success or failure
    conn = sqlite3.connect("activity_log.db")
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # "?" placeholders avoid SQL injection when inserting filenames
    cursor.execute(
        "INSERT INTO logs (filename, action, status, timestamp) VALUES (?, ?, ?, ?)",
        (filename, action, status, timestamp)
    )
    conn.commit()
    conn.close()

def view_log():
    # opens a separate window (Toplevel) so the main app stays open behind it
    log_window = tk.Toplevel(root)
    log_window.title("Activity Log")
    log_window.geometry("500x300")

    columns = ("Filename", "Action", "Status", "Timestamp")
    tree = ttk.Treeview(log_window, columns=columns, show="headings")
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=110)
    tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    conn = sqlite3.connect("activity_log.db")
    cursor = conn.cursor()
    cursor.execute("SELECT filename, action, status, timestamp FROM logs ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    for row in rows:
        tree.insert("", tk.END, values=row)

# --- File Queue Management ---

file_queue = []

def add_file():
    # single-file picker used repeatedly, avoids trackpad multi-select issues
    file_path = filedialog.askopenfilename(title="Select a file to add to the queue")
    if not file_path:
        return
    file_queue.append(file_path)
    file_listbox.insert(tk.END, os.path.basename(file_path))

def remove_selected():
    selected_index = file_listbox.curselection()
    if not selected_index:
        messagebox.showinfo("Info", "Select a file in the list first to remove it")
        return
    index = selected_index[0]
    file_listbox.delete(index)
    del file_queue[index]

def clear_queue():
    file_queue.clear()
    file_listbox.delete(0, tk.END)

# --- Button click handlers ---

def encrypt_queue():
    if not file_queue:
        messagebox.showerror("Error", "No files in the queue - click 'Add File' first")
        return

    password = password_entry.get()
    if not password:
        messagebox.showerror("Error", "Please enter a password")
        return

    encrypted_files = []

    for file_path in file_queue:
        filename = os.path.basename(file_path)
        try:
            output = encrypt_image(file_path, password)
            encrypted_files.append(output)
            log_activity(filename, "Encrypt", "Success")
        except Exception:
            log_activity(filename, "Encrypt", "Failed")
            messagebox.showerror("Error", f"Failed to encrypt {filename}")
            return

    summary = "\n".join(encrypted_files)
    messagebox.showinfo("Success", f"Encrypted {len(encrypted_files)} file(s):\n{summary}")


def decrypt_queue():
    if not file_queue:
        messagebox.showerror("Error", "No files in the queue - click 'Add File' first")
        return

    password = password_entry.get()
    if not password:
        messagebox.showerror("Error", "Please enter a password")
        return

    decrypted_files = []

    for file_path in file_queue:
        filename = os.path.basename(file_path)
        try:
            output = decrypt_image(file_path, password)
            decrypted_files.append(output)
            log_activity(filename, "Decrypt", "Success")
        except ValueError as e:
            log_activity(filename, "Decrypt", "Failed")
            messagebox.showerror(
                "Verification Failed",
                f"Stopped at file: {filename}\n\n{str(e)}\n\n"
                f"{len(decrypted_files)} file(s) were successfully decrypted before this failure."
            )
            return
        except Exception:
            log_activity(filename, "Decrypt", "Failed")
            messagebox.showerror(
                "Error",
                f"Stopped at file: {filename}\nDecryption failed - file may be corrupted.\n\n"
                f"{len(decrypted_files)} file(s) were successfully decrypted before this failure."
            )
            return

    summary = "\n".join(decrypted_files)
    messagebox.showinfo("Success", f"Decrypted {len(decrypted_files)} file(s):\n{summary}")

# --- GUI (Tkinter) ---

init_database()

root = tk.Tk()
root.title("Image Protection Toolkit")
root.geometry("420x450")

tk.Label(root, text="Password:").pack(pady=(15, 0))
password_entry = tk.Entry(root, show="*", width=30)
password_entry.pack(pady=5)

tk.Label(root, text="File Queue:").pack(pady=(10, 0))
file_listbox = tk.Listbox(root, width=50, height=8)
file_listbox.pack(pady=5)

queue_button_frame = tk.Frame(root)
queue_button_frame.pack(pady=5)
tk.Button(queue_button_frame, text="Add File", command=add_file, width=12).pack(side=tk.LEFT, padx=3)
tk.Button(queue_button_frame, text="Remove Selected", command=remove_selected, width=14).pack(side=tk.LEFT, padx=3)
tk.Button(queue_button_frame, text="Clear Queue", command=clear_queue, width=12).pack(side=tk.LEFT, padx=3)

action_button_frame = tk.Frame(root)
action_button_frame.pack(pady=10)
tk.Button(action_button_frame, text="Encrypt Queue", command=encrypt_queue, width=15).pack(side=tk.LEFT, padx=5)
tk.Button(action_button_frame, text="Decrypt Queue", command=decrypt_queue, width=15).pack(side=tk.LEFT, padx=5)

tk.Button(root, text="View Activity Log", command=view_log, width=20).pack(pady=10)

root.mainloop()