from flask import Flask, render_template, request, send_file, session, redirect, url_for, abort, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import io
import os
import re
import jinja2
import shutil
import tempfile
import hashlib
import zipfile

from crypto_utils import encrypt_image, decrypt_image
from database import (
    init_db, create_user, verify_user, log_activity, get_logs, clear_logs, delete_log,
    verify_admin, get_all_users, get_all_logs, delete_user, admin_delete_log, admin_clear_all_logs,
    create_admin, promote_user_to_admin
)
from image_tools import compress_image, resize_image, convert_image, remove_metadata, get_metadata_info
from password_ai import check_password, generate_strong_password
import visual_crypto

app = Flask(__name__, static_folder=None)

# Resilient template loader: searches in 'templates/' folder, and falls back to root '.' if files were uploaded loose
app.jinja_loader = jinja2.ChoiceLoader([
    jinja2.FileSystemLoader(os.path.join(app.root_path, "templates")),
    jinja2.FileSystemLoader(app.root_path)
])

@app.route("/static/<path:filename>", endpoint="static")
def custom_static(filename):
    static_dir = os.path.join(app.root_path, "static")
    if os.path.exists(os.path.join(static_dir, filename)):
        return send_from_directory(static_dir, filename)
    return send_from_directory(app.root_path, filename)

# the session is a cookie signed with this key, so users cannot edit it to pretend to be someone else
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # accept uploads up to 32 MB for batch processing

init_db()  # make sure the tables exist when the app starts

# --- Card and Tool Definitions (with Easy Plain-English Descriptions) ---

CARDS = [
    {
        "group": "Security & Cryptography",
        "items": [
            {
                "title": "Lock Images with Password",
                "description": "Scramble and lock your photos with a secret password so no unauthorized person can open or view them.",
                "url": "/tool/encrypt",
                "icon": "lock",
                "tag": "AES-256 Encryption",
            },
            {
                "title": "Unlock Encrypted Images",
                "description": "Enter your password to unlock your scrambled files (.enc or .zip) and restore them back to normal photos.",
                "url": "/tool/decrypt",
                "icon": "unlock",
                "tag": "AES-256 Decryption",
            },
            {
                "title": "AI Tamper & Edit Detector",
                "description": "Compare an original photo with an AI-edited or tampered version to instantly prove if any pixel was changed.",
                "url": "/hash",
                "icon": "hash",
                "tag": "Digital Fingerprint • SHA-256",
            },
            {
                "title": "Password Safety Checker",
                "description": "Check how strong your password is and see how fast hackers or AI tools could guess or crack it.",
                "url": "/password-checker",
                "icon": "shield",
                "tag": "AI Pattern Defense",
            },
            {
                "title": "Secret Image Splitter & PIN Unlocker",
                "description": "Split any secret picture into 2 scrambled noise files. Send one share to a friend with a secret PIN to reveal the original image!",
                "url": "/visual-crypto",
                "icon": "layers",
                "tag": "Visual Cryptography",
            },
        ]
    },
    {
        "group": "Image Privacy & Optimization",
        "items": [
            {
                "title": "Wipe Hidden GPS & Camera Info",
                "description": "See and erase hidden GPS coordinates, camera models, and timestamps from your photos before posting them online.",
                "url": "/tool/metadata",
                "icon": "eye-off",
                "tag": "EXIF Privacy Cleaner",
            },
            {
                "title": "Shrink Image File Size",
                "description": "Make image files smaller to save storage space and upload faster on WhatsApp or websites without losing quality.",
                "url": "/tool/compress",
                "icon": "minimize",
                "tag": "Smart Compression",
            },
            {
                "title": "Resize Image Dimensions",
                "description": "Change photo width and height for social media, avatars, or wallpapers without stretching or distorting the picture.",
                "url": "/tool/resize",
                "icon": "aspect-ratio",
                "tag": "Custom Dimensions",
            },
            {
                "title": "Change Image Format",
                "description": "Convert photos between JPG, PNG, WebP, and other formats so they open smoothly on any phone or computer.",
                "url": "/tool/convert",
                "icon": "refresh",
                "tag": "Format Converter",
            },
        ]
    }
]

# dictionary lookup: turns the tool name in the URL (e.g. "compress") into that tool's settings
TOOL_PAGES = {
    "encrypt": {
        "title": "Lock Images with Password",
        "button": "Lock Image(s) with Password",
        "description": "Scramble and lock your image files with military-grade AES-256 encryption.",
        "simple_desc": "Scrambles your image into a locked, unreadable file (.enc). Only someone with your exact secret password can unlock and view it.",
        "icon": "lock",
        "badge": "AES-256-CBC • Batch Ready"
    },
    "decrypt": {
        "title": "Unlock Encrypted Images",
        "button": "Unlock Image(s)",
        "description": "Restore encrypted (.enc) files or entire batch (.zip) archives back to original images.",
        "simple_desc": "Takes your locked (.enc or .zip) file, checks your password, verifies that nobody tampered with it, and turns it back into your original viewable photo.",
        "icon": "unlock",
        "badge": "ZIP & .ENC Supported"
    },
    "compress": {
        "title": "Shrink Image File Size",
        "button": "Shrink File Size",
        "description": "Reduce image file size by optimizing JPEG or modern WebP compression.",
        "simple_desc": "Shrinks your image file size so it sends faster and takes up less space on your phone or computer, while keeping the picture looking sharp and clear.",
        "icon": "minimize",
        "badge": "JPEG & WebP • Batch Ready"
    },
    "resize": {
        "title": "Resize Image Dimensions",
        "button": "Resize Image(s)",
        "description": "Resize single or multiple images to preset or custom dimensions while preserving aspect ratio.",
        "simple_desc": "Changes the width and height (pixel size) of your picture so it fits on screens, websites, or profile pictures without getting stretched or squeezed.",
        "icon": "aspect-ratio",
        "badge": "Lanczos Resampling • Batch Ready"
    },
    "convert": {
        "title": "Change Image Format",
        "button": "Convert Format",
        "description": "Batch convert image formats between JPG, PNG, WEBP, BMP, TIFF, and ICO.",
        "simple_desc": "Changes your image format (e.g. from JPG to PNG or WebP) so it opens on any device, website, or app that requires a specific file type.",
        "icon": "refresh",
        "badge": "Multi-Format • Batch Ready"
    },
    "metadata": {
        "title": "Wipe Hidden GPS & Camera Info",
        "button": "Wipe Hidden Privacy Data",
        "description": "Inspect and strip hidden EXIF metadata, GPS latitude/longitude, and camera details.",
        "simple_desc": "Wipes hidden personal information stored inside your photo — like the exact GPS location where you took it, what phone/camera was used, and the time — to protect your privacy.",
        "icon": "eye-off",
        "badge": "Privacy Hardening • EXIF Inspector"
    },
}

# --- Accounts ---

def validate_signup_password(password: str) -> tuple[bool, str]:
    """
    Enforces strong password policy on account creation:
    Must be at least 8 characters long, and contain letters, numbers, and special symbols.
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Za-z]", password):
        return False, "Password must include at least one letter (a-z, A-Z)."
    if not re.search(r"[0-9]", password):
        return False, "Password must include at least one number (0-9)."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_+=\[\]\\/`~]", password):
        return False, "Password must include at least one special symbol (e.g. !@#$%^&*)."
    return True, ""

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username:
            return render_template("signup.html", message="Please enter a username.")
        valid, err_msg = validate_signup_password(password)
        if not valid:
            return render_template("signup.html", message=err_msg)
        if not create_user(username, password):
            return render_template("signup.html", message="That username is already taken.")
        return redirect(url_for("login"))
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user_id = verify_user(username, password)
        if user_id is None:
            return render_template("login.html", message="Wrong username or password.")
        session["user_id"] = user_id  # this is what "logged in" means
        session["username"] = username
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()  # forgets the user
    return redirect(url_for("login"))

@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    groups = [(g["group"], g["items"]) for g in CARDS]
    return render_template("index.html", groups=groups)

# --- Activity Log & History Management ---

@app.route("/activity")
def activity():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("activity.html", logs=get_logs(session["user_id"]))

@app.route("/activity/clear", methods=["POST"])
def activity_clear():
    if "user_id" not in session:
        return redirect(url_for("login"))
    clear_logs(session["user_id"])
    return redirect(url_for("activity"))

@app.route("/activity/delete/<int:log_id>", methods=["POST"])
def activity_delete(log_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    delete_log(log_id, session["user_id"])
    return redirect(url_for("activity"))

# --- Administrator Control Portal ---

@app.route("/admin")
def admin_root():
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("admin_login"))

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin_id = verify_admin(username, password)
        if admin_id is None:
            return render_template("admin_login.html", message="Invalid administrator credentials.")
        session["is_admin"] = True
        session["admin_username"] = username
        return redirect(url_for("admin_dashboard"))
    return render_template("admin_login.html")

@app.route("/admin/register", methods=["GET", "POST"])
def admin_register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or len(password) < 6:
            return render_template("admin_register.html", message="Enter an administrator username and a password of at least 6 characters.")
        if not create_admin(username, password):
            return render_template("admin_register.html", message="Failed to create administrator account.")
        # Ensure user can also log into regular user toolkit
        create_user(username, password, make_admin=True)
        session["is_admin"] = True
        session["admin_username"] = username
        return redirect(url_for("admin_dashboard"))
    return render_template("admin_register.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    session.pop("admin_username", None)
    return redirect(url_for("admin_login"))

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    all_users = get_all_users()
    all_logs = get_all_logs()
    return render_template("admin_dashboard.html", users=all_users, logs=all_logs)

@app.route("/admin/user/promote/<int:user_id>", methods=["POST"])
def admin_promote_user_route(user_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    promote_user_to_admin(user_id)
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/user/delete/<int:user_id>", methods=["POST"])
def admin_delete_user_route(user_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    delete_user(user_id)
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/log/delete/<int:log_id>", methods=["POST"])
def admin_delete_log_route(log_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    admin_delete_log(log_id)
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/logs/clear", methods=["POST"])
def admin_clear_logs_route():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    admin_clear_all_logs()
    return redirect(url_for("admin_dashboard"))


# --- Shared upload handling (with Multi-File Batch & ZIP Unpacking Support) ---
# Every tool follows the same steps: check login, save the upload to a temporary
# folder, run a function, log the result, send the file back, delete the folder.
# Success returns the file or a ZIP bundle; failure returns JSON that the page shows as a pop-up.

def format_file_size(bytes_val):
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{round(bytes_val / 1024, 1)} KB"
    return f"{round(bytes_val / (1024 * 1024), 2)} MB"

def process_upload(action, func, tool_name=None):
    if "user_id" not in session:
        return jsonify(ok=False, error_type="auth", message="Your session has expired. Please log in again."), 401

    # Extract all files from either 'file' or 'files' input fields (supports multi-upload)
    files = request.files.getlist("files") or request.files.getlist("file")
    valid_files = [f for f in files if f and f.filename.strip() != ""]

    if not valid_files:
        return jsonify(ok=False, error_type="no_file", message="Please choose at least one file to process."), 400

    # Validate file extensions for specialized tools
    if tool_name == "decrypt":
        for f in valid_files:
            fname = f.filename.lower()
            if not (fname.endswith(".enc") or fname.endswith(".zip")):
                return jsonify(
                    ok=False,
                    error_type="wrong_file_type",
                    message=f"Wrong file selected: '{f.filename}' is not an encrypted file or encrypted zip archive. Decryption accepts '.enc' files or your batch '.zip' download."
                ), 400

    if tool_name == "encrypt":
        for f in valid_files:
            fname = f.filename.lower()
            if fname.endswith(".enc"):
                return jsonify(
                    ok=False,
                    error_type="wrong_file_type",
                    message=f"File '{f.filename}' is already encrypted (.enc). Please select standard image files (PNG, JPG, WEBP) to encrypt."
                ), 400

    # every request gets its own temporary folder, so users never overwrite
    # each other's files and cleanup is a single call
    workdir = tempfile.mkdtemp()
    out_paths = []
    processed_names = []
    total_original_bytes = 0

    try:
        # Collect items to process, automatically unpacking any .zip archives (such as batch downloads)
        input_queue = []
        saved_fnames = set()
        for file in valid_files:
            # secure_filename removes dangerous characters (like ../) so an upload cannot write outside the temp folder
            fname = secure_filename(file.filename)
            if not fname:
                fname = "upload.png"

            # Prevent collision if multiple files share the exact same filename
            base, ext = os.path.splitext(fname)
            unique_fname = fname
            counter = 1
            while unique_fname.lower() in saved_fnames:
                unique_fname = f"{base}_{counter}{ext}"
                counter += 1
            saved_fnames.add(unique_fname.lower())

            saved_path = os.path.join(workdir, unique_fname)
            file.save(saved_path)

            if fname.lower().endswith(".zip"):
                # Unpack zip archive directly in workdir
                extracted_dir = os.path.join(workdir, "extracted_" + os.path.splitext(fname)[0])
                os.makedirs(extracted_dir, exist_ok=True)
                with zipfile.ZipFile(saved_path, "r") as zf:
                    for member in zf.namelist():
                        if member.endswith("/") or member.startswith("__MACOSX") or os.path.basename(member).startswith("."):
                            continue
                        member_base = secure_filename(os.path.basename(member))
                        if not member_base:
                            continue
                        if tool_name == "decrypt" and not member_base.lower().endswith(".enc"):
                            continue
                        
                        target_path = os.path.join(extracted_dir, member_base)
                        with zf.open(member) as source, open(target_path, "wb") as target:
                            shutil.copyfileobj(source, target)
                        file_sz = os.path.getsize(target_path)
                        total_original_bytes += file_sz
                        input_queue.append((target_path, member_base, file_sz))

                if tool_name == "decrypt" and not input_queue:
                    return jsonify(
                        ok=False,
                        error_type="wrong_file_type",
                        message=f"The ZIP archive '{file.filename}' does not contain any encrypted (.enc) files. Please select a valid encrypted archive or .enc files."
                    ), 400
            else:
                file_sz = os.path.getsize(saved_path)
                total_original_bytes += file_sz
                input_queue.append((saved_path, file.filename, file_sz))

        if not input_queue:
            return jsonify(ok=False, error_type="no_file", message="No valid files found to process."), 400

        total_output_bytes = 0
        for in_path, orig_name, orig_sz in input_queue:
            out_path = func(in_path, request.form)
            out_paths.append(out_path)
            processed_names.append(orig_name)
            total_output_bytes += os.path.getsize(out_path)

        # Calculate exact change / savings metrics
        diff_bytes = total_original_bytes - total_output_bytes
        if total_original_bytes > 0:
            savings_pct = round((diff_bytes / total_original_bytes) * 100, 1)
        else:
            savings_pct = 0.0

        # Construct easy-to-understand change summary message
        if tool_name == "compress":
            if savings_pct > 0:
                summary_msg = f"Reduced file size by {savings_pct}% (Saved {format_file_size(diff_bytes)})"
                highlight_val = f"{savings_pct}% Size Saved"
            else:
                summary_msg = f"Already optimized: Original file retained ({format_file_size(total_output_bytes)})"
                highlight_val = "Best Size Kept"
        elif tool_name == "encrypt":
            summary_msg = f"100% Encrypted & Locked: All files protected with secret AES-256 key"
            highlight_val = "100% Encrypted"
        elif tool_name == "decrypt":
            summary_msg = f"100% Decrypted & Authenticated: SHA-256 cryptographic integrity verified"
            highlight_val = "100% Restored"
        elif tool_name == "metadata":
            summary_msg = f"100% Privacy Cleaned: All EXIF metadata, GPS coordinates, and camera tags wiped"
            highlight_val = "100% Cleaned"
        elif tool_name == "resize":
            summary_msg = f"100% Resized: Dimensions adjusted successfully to target specifications"
            highlight_val = "100% Resized"
        elif tool_name == "convert":
            target_fmt = request.form.get("format", "Target").upper()
            summary_msg = f"100% Converted: Image successfully converted to {target_fmt} format"
            highlight_val = "100% Converted"
        else:
            summary_msg = f"Operation completed successfully"
            highlight_val = "100% Complete"

        # Batch logging
        if len(processed_names) == 1:
            log_activity(session["user_id"], processed_names[0], action, "Success")
        else:
            log_activity(session["user_id"], f"Batch {action} ({len(processed_names)} files)", action, "Success")

        # Deliver single file or bundle into a ZIP archive
        if len(out_paths) == 1:
            with open(out_paths[0], "rb") as f:
                data = io.BytesIO(f.read())
            download_name = os.path.basename(out_paths[0])
            mimetype = "application/octet-stream"
        else:
            used_arcnames = set()
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for out_path in out_paths:
                    base_name = os.path.basename(out_path)
                    arcname = base_name
                    counter = 1
                    stem, ext = os.path.splitext(base_name)
                    while arcname in used_arcnames:
                        arcname = f"{stem}_{counter}{ext}"
                        counter += 1
                    used_arcnames.add(arcname)
                    zip_file.write(out_path, arcname=arcname)
            zip_buffer.seek(0)
            data = zip_buffer
            download_name = f"{action.lower().replace(' ', '_')}_batch.zip"
            mimetype = "application/zip"

        response = send_file(data, as_attachment=True, download_name=download_name, mimetype=mimetype)
        # Expose rich summary metrics in HTTP headers so the frontend can display exact results
        response.headers["X-Original-Bytes"] = str(total_original_bytes)
        response.headers["X-Output-Bytes"] = str(total_output_bytes)
        response.headers["X-Original-Formatted"] = format_file_size(total_original_bytes)
        response.headers["X-Output-Formatted"] = format_file_size(total_output_bytes)
        response.headers["X-Savings-Percent"] = str(savings_pct)
        response.headers["X-Summary-Message"] = summary_msg
        response.headers["X-Highlight-Val"] = highlight_val
        response.headers["X-Tool-Name"] = tool_name or ""
        response.headers["Access-Control-Expose-Headers"] = (
            "Content-Disposition, X-Original-Bytes, X-Output-Bytes, X-Original-Formatted, "
            "X-Output-Formatted, X-Savings-Percent, X-Summary-Message, X-Highlight-Val, X-Tool-Name"
        )
        return response

    except ValueError as e:
        # our own validation errors, e.g. wrong password or invalid settings
        err_msg = str(e)
        first_file = valid_files[0].filename if valid_files else "Upload"
        log_activity(session["user_id"], first_file, action, "Failed")

        is_pw = "password" in err_msg.lower() or "hash" in err_msg.lower() or "key" in err_msg.lower()
        err_type = "wrong_password" if is_pw else "validation_error"
        return jsonify(ok=False, error_type=err_type, message=err_msg), 400

    except Exception as e:
        first_file = valid_files[0].filename if valid_files else "Upload"
        log_activity(session["user_id"], first_file, action, "Failed")
        return jsonify(ok=False, error_type="processing_error", message="Could not process file. Is the image corrupted or format unsupported?"), 400

    finally:
        shutil.rmtree(workdir, ignore_errors=True)  # always delete the uploaded and result files

# --- Encrypt / Decrypt helpers ---

def do_encrypt(path, form):
    password = form.get("password", "")
    if not password:
        raise ValueError("Please enter a secret encryption password.")
    return encrypt_image(path, password)

def do_decrypt(path, form):
    password = form.get("password", "")
    if not password:
        raise ValueError("Please enter the decryption password.")
    return decrypt_image(path, password)

@app.route("/encrypt", methods=["POST"])
def encrypt():
    return process_upload("Encrypt", do_encrypt, tool_name="encrypt")

@app.route("/decrypt", methods=["POST"])
def decrypt():
    return process_upload("Decrypt", do_decrypt, tool_name="decrypt")

# --- Image tools: one route and one template serve all tools ---

def read_number(form, field, label):
    # turns a form value into a whole number, with a clear message if it isn't one
    try:
        return int(form.get(field, ""))
    except ValueError:
        raise ValueError("Please enter a whole number for " + label + ".")

def run_tool(name, path, form):
    # picks the right function for the tool and reads its settings from the form
    if name == "encrypt":
        return do_encrypt(path, form)
    if name == "decrypt":
        return do_decrypt(path, form)
    if name == "compress":
        quality = read_number(form, "quality", "quality")
        out_fmt = form.get("format", "JPG")
        return compress_image(path, quality=quality, out_format=out_fmt)
    if name == "resize":
        width = read_number(form, "width", "width")
        height_str = form.get("height", "").strip()
        height = int(height_str) if height_str.isdigit() else None
        keep_aspect = form.get("keep_aspect") in ("on", "true", "1") or height is None
        resample = form.get("resample", "LANCZOS")
        return resize_image(path, width=width, height=height, keep_aspect=keep_aspect, resample=resample)
    if name == "convert":
        return convert_image(path, form.get("format", "PNG"))
    if name == "metadata":
        return remove_metadata(path)
    raise ValueError("Invalid tool request.")

@app.route("/tool/<name>", methods=["GET", "POST"])
def tool(name):
    if name not in TOOL_PAGES:
        # unknown tool name in the URL: show the 404 page
        abort(404)
    card = TOOL_PAGES[name]
    if request.method == "GET":
        if "user_id" not in session:
            return redirect(url_for("login"))
        return render_template("tool.html", tool=card, name=name)
    # lambda = a tiny anonymous function; it lets process_upload run the right tool without knowing which one it is
    return process_upload(card["title"], lambda path, form: run_tool(name, path, form), tool_name=name)

# --- EXIF Metadata Inspector Endpoint ---

@app.route("/tool/metadata/inspect", methods=["POST"])
def inspect_metadata():
    if "user_id" not in session:
        return jsonify(ok=False, message="Please log in."), 401
    file = request.files.get("file") or request.files.get("files")
    if not file or file.filename == "":
        return jsonify(ok=False, message="Please choose an image file to inspect."), 400

    workdir = tempfile.mkdtemp()
    try:
        in_path = os.path.join(workdir, secure_filename(file.filename))
        file.save(in_path)
        info = get_metadata_info(in_path)
        return jsonify(ok=True, filename=file.filename, info=info)
    except Exception as e:
        return jsonify(ok=False, message="Could not extract metadata from this file."), 400
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

# --- Multi-Algorithm File Hash Checker ---

def compute_hashes(file):
    # reads the upload in small chunks so large files never fill the memory
    sha256 = hashlib.sha256()
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    for chunk in iter(lambda: file.stream.read(8192), b""):
        sha256.update(chunk)
        md5.update(chunk)
        sha1.update(chunk)
    return {
        "sha256": sha256.hexdigest(),
        "md5": md5.hexdigest(),
        "sha1": sha1.hexdigest()
    }

@app.route("/hash", methods=["GET", "POST"])
def hash_checker():
    if request.method == "GET":
        if "user_id" not in session:
            return redirect(url_for("login"))
        return render_template("hash.html")

    if "user_id" not in session:
        return jsonify(ok=False, error_type="auth", message="Please log in again."), 401

    first = request.files.get("file1")
    second = request.files.get("file2")
    if not first or first.filename == "":
        return jsonify(ok=False, error_type="no_file", message="Please choose at least one primary file to hash."), 400

    hashes1 = compute_hashes(first)
    result = {
        "ok": True,
        "name1": first.filename,
        "hashes1": hashes1,
        "hash1": hashes1["sha256"]  # backward compatibility
    }

    if second and second.filename != "":
        hashes2 = compute_hashes(second)
        result["name2"] = second.filename
        result["hashes2"] = hashes2
        result["hash2"] = hashes2["sha256"]
        result["match"] = result["hash1"] == result["hash2"]

    log_activity(session["user_id"], first.filename, "Multi-Hash Check", "Success")
    return jsonify(result)

# --- Password Strength Checker & Generator (AI) ---

@app.route("/password-checker")
def password_checker():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("password.html")

@app.route("/password-strength", methods=["POST"])
def password_strength():
    if "user_id" not in session:
        return jsonify(ok=False, message="Please log in again."), 401
    # the password is scored and then discarded: it is never stored or logged
    password = request.form.get("password", "")[:128]
    if not password:
        return jsonify(ok=False, message="Enter a password."), 400
    return jsonify(check_password(password))

@app.route("/password-generate", methods=["GET"])
def password_generate():
    if "user_id" not in session:
        return jsonify(ok=False, message="Please log in."), 401
    return jsonify(ok=True, password=generate_strong_password())

# --- Visual Cryptography (Naor-Shamir 2-Share Secret Splitting) ---

@app.route("/visual-crypto")
def visual_crypto_page():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("visual_crypto.html")

@app.route("/visual-crypto/split", methods=["POST"])
def visual_crypto_split():
    if "user_id" not in session:
        return jsonify(ok=False, message="Please log in again."), 401
    file = request.files.get("file")
    if not file or not file.filename.strip():
        return jsonify(ok=False, message="Please upload an image to split."), 400

    try:
        threshold = int(request.form.get("threshold", 128))
        pin = request.form.get("pin", "").strip()
        res = visual_crypto.process_visual_crypto(file.stream, threshold=threshold, pin=pin)
        share1, share2, clean_img, dims, overlay = res[0], res[1], res[2], res[3], res[4]
        
        uri1 = visual_crypto.image_to_base64_data_uri(share1)
        uri2 = visual_crypto.image_to_base64_data_uri(share2)
        uri_clean = visual_crypto.image_to_base64_data_uri(clean_img)
        uri_overlay = visual_crypto.image_to_base64_data_uri(overlay)

        log_activity(session["user_id"], file.filename, "Visual Crypto Split", "Success")

        return jsonify(
            ok=True,
            share1=uri1,
            share2=uri2,
            overlay=uri_clean,
            optical_overlay=uri_overlay,
            dimensions=f"{dims[0]}x{dims[1]} px",
            share_dimensions=f"{share1.size[0]}x{share1.size[1]} px",
            pin=pin
        )
    except Exception:
        return jsonify(ok=False, message="Could not process image for visual cryptography."), 400

@app.route("/visual-crypto/download", methods=["POST"])
def visual_crypto_download():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    file = request.files.get("file")
    if not file or not file.filename.strip():
        return redirect(url_for("visual_crypto_page"))
        
    try:
        threshold = int(request.form.get("threshold", 128))
        pin = request.form.get("pin", "").strip()
        res = visual_crypto.process_visual_crypto(file.stream, threshold=threshold, pin=pin)
        share1, share2 = res[0], res[1]

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            buf1 = io.BytesIO()
            share1.save(buf1, format="PNG")
            zf.writestr("share1_key.png", buf1.getvalue())

            buf2 = io.BytesIO()
            share2.save(buf2, format="PNG")
            zf.writestr("share2_cipher.png", buf2.getvalue())

        zip_buf.seek(0)
        return send_file(zip_buf, as_attachment=True, download_name="visual_crypto_shares.zip", mimetype="application/zip")
    except Exception:
        return redirect(url_for("visual_crypto_page"))

@app.route("/visual-crypto/unlock-pin", methods=["POST"])
def visual_crypto_unlock_pin():
    if "user_id" not in session:
        return jsonify(ok=False, message="Please log in again."), 401
    file = request.files.get("file")
    pin = request.form.get("pin", "").strip()
    if not file or not file.filename.strip():
        return jsonify(ok=False, message="Please upload a received share image."), 400
    if not pin:
        return jsonify(ok=False, message="Please enter the Secret PIN or Passphrase."), 400

    try:
        res = visual_crypto.unlock_share_with_pin(file.stream, pin)
        clean_img, share1_regen, dims, overlay_img = res[0], res[1], res[2], res[3]
        clean_uri = visual_crypto.image_to_base64_data_uri(clean_img)
        overlay_uri = visual_crypto.image_to_base64_data_uri(overlay_img)
        share1_uri = visual_crypto.image_to_base64_data_uri(share1_regen)
        log_activity(session["user_id"], file.filename, f"Visual Crypto Unlock (PIN: {pin[:2]}**)", "Success")
        return jsonify(
            ok=True,
            unlocked=clean_uri,
            optical_overlay=overlay_uri,
            share1_regenerated=share1_uri,
            dimensions=f"{dims[0]}x{dims[1]} px",
            pin=pin
        )
    except Exception:
        return jsonify(ok=False, message="Could not unlock share with PIN. Please verify it is a valid visual crypto share."), 400

@app.route("/visual-crypto/recombine", methods=["POST"])
def visual_crypto_recombine():
    if "user_id" not in session:
        return jsonify(ok=False, message="Please log in."), 401
    file1 = request.files.get("share1")
    file2 = request.files.get("share2")
    if not file1 or not file2:
        return jsonify(ok=False, message="Please upload both Share 1 and Share 2."), 400

    try:
        combined = visual_crypto.combine_two_shares(file1.stream, file2.stream)
        uri = visual_crypto.image_to_base64_data_uri(combined)
        log_activity(session["user_id"], f"{file1.filename} + {file2.filename}", "Visual Crypto Recombine", "Success")
        return jsonify(ok=True, combined=uri)
    except Exception:
        return jsonify(ok=False, message="Failed to combine shares. Please verify both are valid visual cryptography shares."), 400

@app.errorhandler(413)
def too_large(e):
    return jsonify(ok=False, error_type="file_too_large", message="Batch upload exceeds maximum allowable size (32 MB)."), 413

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
