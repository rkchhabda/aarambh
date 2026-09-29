"""Interactive Owner Re-encryption Script for Phase 6 Holdout Archives.

RUN ONLY BY THE HUMAN OWNER IN A LOCAL TERMINAL.

Security Invariants:
1. Prompts the owner directly via getpass (no terminal echo).
2. Never echoes, logs, prints, or stores the passwords anywhere.
3. Encrypts Window A and Window B with AES-256 into external vault.
4. Cleans up all temporary staging data immediately upon completion.
5. Computes and records the new archive SHA-256 hashes in docs/holdout_access_log.md
   and test_phase6_safeguards.py.
"""

import getpass
import hashlib
import os
import shutil
import sys
import py7zr

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT_DIR = r"c:\Users\r_chh\gaurvideep_vault"
BACKUP_VAULT_DIR = r"c:\Users\r_chh\OneDrive - optgbrc\Apps\gaurvideep_vault"
STAGING_DIR = os.path.join(VAULT_DIR, ".staging_reencrypt")

LOG_FILE = os.path.join(BASE_DIR, "docs", "holdout_access_log.md")
TEST_FILE = os.path.join(BASE_DIR, "test_phase6_safeguards.py")

OLD_COMPROMISED_PASSWORDS = [
    "6xWTJh60n0VUOk-kqkVS2tHNgwmOMxS8",
    "iXR4dH2lDf1YU4XaHXOTauzEoRJ5BBmF",
]


def get_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main():
    print("=" * 65)
    print("GAURVIDEEP: OWNER HOLDOUT RE-ENCRYPTION TOOL")
    print("=" * 65)
    print("All inputs are masked and will NEVER be printed, logged, or saved.")
    print()

    if not os.path.isdir(STAGING_DIR):
        print(f"Error: Staging directory not found at {STAGING_DIR}")
        sys.exit(1)

    win_a_dir = os.path.join(STAGING_DIR, "window_a")
    win_b_dir = os.path.join(STAGING_DIR, "window_b")

    if not (os.path.exists(os.path.join(win_a_dir, "historical_10y_raw_window_a.csv")) and
            os.path.exists(os.path.join(win_b_dir, "historical_10y_raw_window_b.csv"))):
        print("Error: Staging data files are missing.")
        sys.exit(1)

    # Prompt owner for Window A password
    while True:
        pwd_a = getpass.getpass("Enter NEW Window A password (from your password manager): ")
        if not pwd_a.strip():
            print("Password cannot be empty. Try again.")
            continue
        if pwd_a in OLD_COMPROMISED_PASSWORDS:
            print("ERROR: Cannot reuse the compromised password! Generate a brand-new one.")
            continue
        pwd_a_conf = getpass.getpass("Confirm NEW Window A password: ")
        if pwd_a != pwd_a_conf:
            print("Passwords do not match. Try again.")
            continue
        break

    # Prompt owner for Window B password
    while True:
        pwd_b = getpass.getpass("Enter NEW Window B password (from your password manager): ")
        if not pwd_b.strip():
            print("Password cannot be empty. Try again.")
            continue
        if pwd_b in OLD_COMPROMISED_PASSWORDS:
            print("ERROR: Cannot reuse the compromised password! Generate a brand-new one.")
            continue
        pwd_b_conf = getpass.getpass("Confirm NEW Window B password: ")
        if pwd_b != pwd_b_conf:
            print("Passwords do not match. Try again.")
            continue
        break

    print("\nEncrypting Window A archive with owner-supplied password (AES-256)...")
    win_a_archive = os.path.join(VAULT_DIR, "window_a_sealed.7z")
    with py7zr.SevenZipFile(win_a_archive, "w", password=pwd_a) as archive:
        archive.write(os.path.join(win_a_dir, "historical_10y_raw_window_a.csv"), "historical_10y_raw_window_a.csv")
        archive.write(os.path.join(win_a_dir, "relative_features_v1_window_a.csv"), "relative_features_v1_window_a.csv")

    print("Verifying Window A decryption integrity...")
    with py7zr.SevenZipFile(win_a_archive, "r", password=pwd_a) as archive:
        archive.test()

    print("Encrypting Window B archive with owner-supplied password (AES-256)...")
    win_b_archive = os.path.join(VAULT_DIR, "window_b_sealed.7z")
    with py7zr.SevenZipFile(win_b_archive, "w", password=pwd_b) as archive:
        archive.write(os.path.join(win_b_dir, "historical_10y_raw_window_b.csv"), "historical_10y_raw_window_b.csv")
        archive.write(os.path.join(win_b_dir, "relative_features_v1_window_b.csv"), "relative_features_v1_window_b.csv")

    print("Verifying Window B decryption integrity...")
    with py7zr.SevenZipFile(win_b_archive, "r", password=pwd_b) as archive:
        archive.test()

    # Clear password variables from memory
    del pwd_a, pwd_b, pwd_a_conf, pwd_b_conf

    # Copy to backup vault outside git
    os.makedirs(BACKUP_VAULT_DIR, exist_ok=True)
    shutil.copy2(win_a_archive, os.path.join(BACKUP_VAULT_DIR, "window_a_sealed.7z"))
    shutil.copy2(win_b_archive, os.path.join(BACKUP_VAULT_DIR, "window_b_sealed.7z"))

    # Completely wipe staging unencrypted data
    print("Wiping temporary staging data...")
    shutil.rmtree(STAGING_DIR)

    # Compute new checksums
    sha_a = get_sha256(win_a_archive)
    sha_b = get_sha256(win_b_archive)

    print("\nUpdating docs/holdout_access_log.md with new archive checksums...")
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace old archive hashes
    old_hash_a = "be4529b140847aa3d0bdf264ac8e71757d26ac6f49a2c38a0f544e3e0735b170"
    old_hash_b = "31624f50f6d850031a1410df6dab626c2e22c69fedd638150e1d57a2a48b5995"
    content = content.replace(old_hash_a, sha_a).replace(old_hash_b, sha_b)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print("Updating test_phase6_safeguards.py with new archive checksums...")
    with open(TEST_FILE, "r", encoding="utf-8") as f:
        test_content = f.read()
    test_content = test_content.replace(old_hash_a, sha_a).replace(old_hash_b, sha_b)
    with open(TEST_FILE, "w", encoding="utf-8") as f:
        f.write(test_content)

    print("\n" + "=" * 65)
    print("SUCCESS: WINDOW A & B SUCCESSFULLY RE-ENCRYPTED!")
    print("=" * 65)
    print(f"Window A Archive SHA-256: {sha_a}")
    print(f"Window B Archive SHA-256: {sha_b}")
    print()
    print("Security Verification:")
    print(" - Old compromised archives: DELETED")
    print(" - Temporary unencrypted staging files: PURGED")
    print(" - Passwords: Generated and stored securely by owner — NOT printed")
    print(" - Status: Verified encrypted with owner secret (AES-256)")
    print("=" * 65)


if __name__ == "__main__":
    main()
