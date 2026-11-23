from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes
import hashlib

def derive_key(password, salt):
    # derives a fixed 32-byte AES key; the high count slows brute-force attacks
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

    # file format: salt + iv + hash + ciphertext
    output_path = file_path + '.enc'
    with open(output_path, 'wb') as f:
        f.write(salt + iv + original_hash + ciphertext)
    return output_path

def decrypt_image(file_path, password):
    with open(file_path, 'rb') as f:
        raw = f.read()

    # too small to hold salt+iv+hash means it's not one of our files
    if len(raw) < 64:
        raise ValueError("Invalid encrypted file: The file is corrupted or not a valid .enc file produced by this application.")

    salt = raw[:16]
    iv = raw[16:32]
    stored_hash = raw[32:64]
    ciphertext = raw[64:]

    # AES-CBC ciphertext must be a multiple of 16 bytes
    if len(ciphertext) % 16 != 0:
        raise ValueError("Invalid encrypted file: Corrupted ciphertext structure.")

    key = derive_key(password, salt)
    cipher = AES.new(key, AES.MODE_CBC, iv=iv)
    padded_data = cipher.decrypt(ciphertext)

    pad_len = padded_data[-1]
    if pad_len < 1 or pad_len > 16:
        raise ValueError("Incorrect password or corrupted encrypted file. Key verification failed.")

    plaintext = padded_data[:-pad_len]

    # mismatch = wrong password or tampered file
    if calculate_hash(plaintext) != stored_hash:
        raise ValueError("Incorrect password or file has been tampered with! SHA-256 cryptographic verification failed.")

    output_path = file_path.replace('.enc', '_decrypted.jpg')
    with open(output_path, 'wb') as f:
        f.write(plaintext)
    return output_path
