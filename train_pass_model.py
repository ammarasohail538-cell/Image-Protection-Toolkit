import os
import random
import string
import urllib.request

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline

BASE = "https://raw.githubusercontent.com/danielmiessler/SecLists/master/Passwords/Common-Credentials/"
TRAIN_LIST = ("xato-net-10-million-passwords-100000.txt", "common_passwords.txt")
TEST_LIST = ("100k-most-used-passwords-NCSC.txt", "common_passwords_ncsc.txt")

def load_passwords(remote_name, local_name):
    # downloads the list once, then reads it from disk
    if not os.path.exists(local_name):
        print("Downloading", remote_name)
        urllib.request.urlretrieve(BASE + remote_name, local_name)
    with open(local_name, encoding="utf-8", errors="ignore") as f:
        words = [line.strip() for line in f]
    # keep printable passwords of a realistic length
    return [w for w in words if 6 <= len(w) <= 20 and w.isprintable() and w.isascii()]

def random_password(length, rng):
    # random passwords built from a randomly chosen mix of character types
    pools = [
        string.ascii_lowercase,
        string.ascii_lowercase + string.digits,
        string.ascii_letters + string.digits,
        string.ascii_letters + string.digits + "!@#$%^&*()-_=+?",
    ]
    pool = rng.choice(pools)
    return "".join(rng.choice(pool) for _ in range(length))

rng = random.Random(42)  # fixed seed so the results can be reproduced

# class 1 = "common" (real passwords people use), class 0 = random passwords
common = list(dict.fromkeys(load_passwords(*TRAIN_LIST)))  # remove duplicates, keep order
# random passwords copy the length of real ones, so length alone can't separate the classes
random_pw = [random_password(len(w), rng) for w in common]

X = common + random_pw
y = [1] * len(common) + [0] * len(random_pw)
print("Training examples:", len(X), "(", len(common), "common +", len(random_pw), "random )")

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

# characters are turned into 1-3 character chunks ("pas", "ass", "ssw"...), weighted by TF-IDF,
# then logistic regression learns which chunks look like real, guessable passwords
model = make_pipeline(
    TfidfVectorizer(analyzer="char", ngram_range=(1, 3), lowercase=False, min_df=3),
    LogisticRegression(max_iter=1000),
)
model.fit(X_train, y_train)

pred = model.predict(X_test)
print("\n--- Test set results ---")
print("Accuracy :", round(accuracy_score(y_test, pred), 4))
print("Precision:", round(precision_score(y_test, pred), 4))
print("Recall   :", round(recall_score(y_test, pred), 4))
print("Confusion matrix [[TN FP] [FN TP]]:\n", confusion_matrix(y_test, pred))

# second check: a DIFFERENT list of real passwords the model never saw
seen = set(common)
other = [w for w in load_passwords(*TEST_LIST) if w not in seen]
flagged = sum(model.predict(other))
print("\n--- Unseen real passwords (NCSC list) ---")
print(len(other), "passwords not in the training list;", round(100 * flagged / len(other), 1), "% flagged as common")

joblib.dump(model, "password_model.joblib")
print("\nSaved password_model.joblib")