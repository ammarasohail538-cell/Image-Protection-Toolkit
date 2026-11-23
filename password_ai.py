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
    # the model returns the probability that this password looks like a commonly used one
    if model is not None:
        try:
            guessable = float(model.predict_proba([password])[0][1])
        except Exception:
            guessable = 0.5
    else:
        guessable = 0.5
    score = round((1 - guessable) * 100)  # 100 = looks random, 0 = looks like a common password

    if len(password) < 8:
        score = min(score, 20)  # very short passwords are weak whatever the model says

    if score < 40:
        label = "Weak"
    elif score < 75:
        label = "Medium"
    else:
        label = "Strong"

    entropy = calculate_entropy(password)
    crack_time = estimate_crack_time(entropy)

    # simple rule-based tips (the AI decides the score, the rules only give advice)
    tips = []
    if len(password) < 12:
        tips.append("Use at least 12 characters.")
    if password.lower() == password:
        tips.append("Mix in uppercase letters.")
    if not any(c.isdigit() for c in password):
        tips.append("Add some digits.")
    if password.isalnum():
        tips.append("Add a symbol such as ! or #.")
    if guessable > 0.5:
        tips.append("This looks similar to commonly used passwords. Avoid dictionary words and repetitive patterns.")

    composition = {
        "length": len(password),
        "has_upper": any(c.isupper() for c in password),
        "has_lower": any(c.islower() for c in password),
        "has_digit": any(c.isdigit() for c in password),
        "has_symbol": any(c in string.punctuation for c in password),
    }

    return {
        "label": label,
        "score": score,
        "entropy": entropy,
        "crack_time": crack_time,
        "composition": composition,
        "tips": tips
    }
