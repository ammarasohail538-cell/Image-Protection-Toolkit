import os
import joblib
import math
import secrets
import string

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "password_model.joblib")
model = None
try:
    if os.path.exists(MODEL_PATH):
        model = joblib.load(MODEL_PATH)  # trained model, loaded once when the app starts
except Exception:
    model = None

def calculate_entropy(password):
    """Calculates Shannon entropy in bits based on character pool diversity."""
    pool_size = 0
    if any(c.islower() for c in password): pool_size += 26
    if any(c.isupper() for c in password): pool_size += 26
    if any(c.isdigit() for c in password): pool_size += 10
    if any(c in string.punctuation for c in password): pool_size += 32
    
    if pool_size == 0 or len(password) == 0:
        return 0.0
    
    # Entropy = length * log2(pool_size)
    entropy = len(password) * math.log2(pool_size)
    return round(entropy, 1)

def estimate_crack_time(entropy):
    """Estimates crack time assuming an offline attack at 10 billion guesses/sec."""
    if entropy <= 0:
        return "Instant"
    combinations = 2 ** entropy
    guesses_per_sec = 10_000_000_000  # 10 GH/s GPU array
    seconds = combinations / (2 * guesses_per_sec)  # average 50% search space

    if seconds < 1:
        return "< 1 second (Instant)"
    elif seconds < 60:
        return f"{round(seconds)} seconds"
    elif seconds < 3600:
        return f"{round(seconds / 60)} minutes"
    elif seconds < 86400:
        return f"{round(seconds / 3600)} hours"
    elif seconds < 31536000:
        return f"{round(seconds / 86400)} days"
    elif seconds < 31536000 * 100:
        return f"{round(seconds / 31536000)} years"
    elif seconds < 31536000 * 1_000_000:
        return f"{round(seconds / (31536000 * 1000))} thousand years"
    else:
        return "Centuries (Virtually Uncrackable)"

def generate_strong_password(length=16):
    """Generates a cryptographically secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        # Ensure it has all character classes
        if (any(c.islower() for c in password) and
            any(c.isupper() for c in password) and
            any(c.isdigit() for c in password) and
            any(c in "!@#$%^&*-_=+" for c in password)):
            return password

def check_password(password):
    # Calculate Shannon entropy and crack time
    entropy = calculate_entropy(password)
    crack_time = estimate_crack_time(entropy)

    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_symbol = any(c in string.punctuation for c in password)
    char_types = sum([has_upper, has_lower, has_digit, has_symbol])

    # Machine learning pattern probability (Tfidf + LogisticRegression)
    if model is not None:
        try:
            guessable = float(model.predict_proba([password])[0][1])
        except Exception:
            guessable = 0.5
    else:
        guessable = 0.5

    # 1. Entropy component (max 40 points)
    entropy_pts = min(40.0, (entropy / 75.0) * 40.0)

    # 2. Diversity component: 5 points per character class (max 20 points)
    diversity_pts = char_types * 5.0

    # 3. Length component (max 20 points)
    if len(password) >= 14:
        length_pts = 20.0
    elif len(password) >= 10:
        length_pts = 12.0
    elif len(password) >= 8:
        length_pts = 6.0
    else:
        length_pts = 0.0

    # 4. AI ML Model component: reward passwords that do not match known breach patterns (max 20 points)
    ai_pts = (1.0 - guessable) * 20.0

    raw_score = entropy_pts + diversity_pts + length_pts + ai_pts

    # Passwords shorter than 8 characters are strictly capped at 25 (Weak)
    if len(password) < 8:
        raw_score = min(raw_score, 25.0)

    score = max(0, min(100, round(raw_score)))

    if score < 40:
        label = "Weak"
    elif score < 75:
        label = "Medium"
    else:
        label = "Strong"

    # Context-aware security tips
    tips = []
    if len(password) < 12:
        tips.append("Use at least 12 characters.")
    if not has_upper:
        tips.append("Mix in uppercase letters.")
    if not has_lower:
        tips.append("Mix in lowercase letters.")
    if not has_digit:
        tips.append("Add some digits (0-9).")
    if not has_symbol:
        tips.append("Add a special symbol such as ! or # or @.")
    if guessable > 0.85 and len(password) < 14:
        tips.append("This contains sequences or patterns similar to common passwords. Avoid predictable dictionary phrases.")

    composition = {
        "length": len(password),
        "has_upper": has_upper,
        "has_lower": has_lower,
        "has_digit": has_digit,
        "has_symbol": has_symbol,
    }

    return {
        "label": label,
        "score": score,
        "entropy": entropy,
        "crack_time": crack_time,
        "composition": composition,
        "tips": tips
    }
