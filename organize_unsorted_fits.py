#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# =============================================================================
# organize_unsorted_fits.py
#
# Author      : Vishwa Jeewanthi
# Date        : 16 May 2026

# Purpose:
#   Sorts mixed-up FITS and CAT files stored across unsorted folders on the
#   DragonflyPol main computer (NAS / NewNAS / camera sticks) by reading each
#   FITS header and extracting the observing date. Files are organised into
#   per-night subfolders based on New Mexico local time. The script also
#   generates CSV reports flagging missing CAT files and unmatched CAT entries.
#
# Usage:
#   Set DRY_RUN = True for a safe preview, then False to perform actual copies.
#   Configure BASE_PATH and SUBFOLDERS in the CONFIG section before running.
#
# Developed with the assistance of AI tools (ChatGPT by OpenAI).
# =============================================================================

import os
import shutil
from astropy.io import fits
from tqdm import tqdm
from collections import defaultdict
import csv
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# ----------------------------
# CONFIG
# ----------------------------
BASE_PATH = "/Volumes/Extreme SSD/data/RawData"
SUBFOLDERS = ["2026-01-12to19", "RandomDates", "2026-04-04", "2026-04-08"]
DRY_RUN = True   # set False when ready to actually copy

# DATE priority: DATE first, then DATE-OBS
DATE_KEYS = ["DATE", "DATE-OBS"]

FITS_EXTENSIONS = {".fits", ".fit", ".fts"}
CAT_EXTENSION = ".cat"

REPORT_FILE = os.path.join(BASE_PATH, "missing_cat_report.csv")
UNMATCHED_CAT_FILE = os.path.join(BASE_PATH, "unmatched_cat_files.csv")

# ----------------------------
# HELPERS
# ----------------------------
def get_date_from_header(header):
    for key in DATE_KEYS:
        if key in header and header[key]:
            raw_value = str(header[key]).strip()

            try:
                # Parse UTC time
                if "T" in raw_value:
                    dt_utc = datetime.fromisoformat(raw_value.replace("Z", "")).replace(tzinfo=ZoneInfo("UTC"))
                elif " " in raw_value:
                    dt_utc = datetime.strptime(raw_value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("UTC"))
                else:
                    return raw_value[:10]

                # Convert to New Mexico local time
                dt_local = dt_utc.astimezone(ZoneInfo("America/Denver"))

                # Assign observing night
                if dt_local.hour < 12:
                    dt_local = dt_local - timedelta(days=1)

                return dt_local.strftime("%Y-%m-%d")

            except Exception:
                return raw_value[:10]

    return "Unknown_Date"


def ensure_unique_destination(dest_path):
    if not os.path.exists(dest_path):
        return dest_path

    parent = os.path.dirname(dest_path)
    stem, suffix = os.path.splitext(os.path.basename(dest_path))

    i = 1
    while True:
        new_dest = os.path.join(parent, f"{stem}_{i}{suffix}")
        if not os.path.exists(new_dest):
            return new_dest
        i += 1


def copy_file(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if DRY_RUN:
        print(f"  DRY RUN (COPY): {os.path.basename(src)} -> {dst}")
    else:
        shutil.copy2(src, dst)


# ----------------------------
# MAIN SORTER
# ----------------------------
def sort_camera_folder(camera_path):
    print(f"\nProcessing {os.path.basename(camera_path)}")

    missing_cat_rows = []
    unmatched_cat_rows = []

    for subfolder_name in SUBFOLDERS:
        source_folder = os.path.join(camera_path, subfolder_name)

        if not os.path.exists(source_folder):
            print(f"  Skipping missing folder: {subfolder_name}")
            continue

        print(f"  Sorting inside {subfolder_name}")

        all_files = [
            os.path.join(source_folder, f)
            for f in os.listdir(source_folder)
            if os.path.isfile(os.path.join(source_folder, f))
        ]

        if not all_files:
            print(f"  No files found in {subfolder_name}")
            continue

        fits_files = [f for f in all_files if Path(f).suffix.lower() in FITS_EXTENSIONS]
        cat_files = [f for f in all_files if Path(f).suffix.lower() == CAT_EXTENSION]

        stem_to_date = {}
        date_counts = defaultdict(lambda: {"fits": 0, "cat": 0})

        # ---------------- FITS ----------------
        for fits_file in tqdm(fits_files, desc=f"{os.path.basename(camera_path)}/{subfolder_name} FITS"):
            try:
                header = fits.getheader(fits_file)
                obs_date = get_date_from_header(header)

                stem = Path(fits_file).stem
                stem_to_date[stem] = obs_date
                date_counts[obs_date]["fits"] += 1

                target_dir = os.path.join(source_folder, obs_date)
                dest = ensure_unique_destination(os.path.join(target_dir, os.path.basename(fits_file)))
                copy_file(fits_file, dest)

            except Exception as e:
                print(f"  Error on FITS file {os.path.basename(fits_file)}: {e}")

        # ---------------- CAT ----------------
        for cat_file in tqdm(cat_files, desc=f"{os.path.basename(camera_path)}/{subfolder_name} CAT"):
            try:
                stem = Path(cat_file).stem
                obs_date = stem_to_date.get(stem)

                if obs_date is None:
                    obs_date = "Unknown_Date"
                    unmatched_cat_rows.append({
                        "camera": os.path.basename(camera_path),
                        "subfolder": subfolder_name,
                        "cat_file": os.path.basename(cat_file)
                    })
                else:
                    date_counts[obs_date]["cat"] += 1

                target_dir = os.path.join(source_folder, obs_date)
                dest = ensure_unique_destination(os.path.join(target_dir, os.path.basename(cat_file)))
                copy_file(cat_file, dest)

            except Exception as e:
                print(f"  Error on CAT file {os.path.basename(cat_file)}: {e}")

        # ---------------- REPORT ----------------
        for date_key, counts in sorted(date_counts.items()):
            fits_count = counts["fits"]
            cat_count = counts["cat"]
            missing_cat = max(0, fits_count - cat_count)

            if fits_count > 0 and missing_cat > 0:
                missing_cat_rows.append({
                    "camera": os.path.basename(camera_path),
                    "subfolder": subfolder_name,
                    "date": date_key,
                    "fits_count": fits_count,
                    "cat_count": cat_count,
                    "missing_cat_count": missing_cat
                })

    return missing_cat_rows, unmatched_cat_rows


# ----------------------------
# RUN ALL CAMERAS
# ----------------------------
def run_all_cameras():
    camera_folders = [
        os.path.join(BASE_PATH, d)
        for d in os.listdir(BASE_PATH)
        if os.path.isdir(os.path.join(BASE_PATH, d)) and d.startswith("Dragonfly")
    ]

    print(f"Found {len(camera_folders)} camera folders")

    all_missing = []
    all_unmatched = []

    for cam in sorted(camera_folders):
        missing_rows, unmatched_rows = sort_camera_folder(cam)
        all_missing.extend(missing_rows)
        all_unmatched.extend(unmatched_rows)

    # -------- SAVE CSV --------
    if all_missing:
        with open(REPORT_FILE, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["camera", "subfolder", "date", "fits_count", "cat_count", "missing_cat_count"]
            )
            writer.writeheader()
            writer.writerows(all_missing)

    if all_unmatched:
        with open(UNMATCHED_CAT_FILE, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["camera", "subfolder", "cat_file"]
            )
            writer.writeheader()
            writer.writerows(all_unmatched)

    # -------- PRINT --------
    print("\n========================================")
    print("MISSING CAT FILE REPORT")
    print("========================================\n")

    if all_missing:
        print(f"Saved CSV report to: {REPORT_FILE}\n")
        for row in all_missing:
            print(
                f"{row['camera']} | {row['subfolder']} | {row['date']} | "
                f"FITS={row['fits_count']}  CAT={row['cat_count']}  "
                f"MISSING={row['missing_cat_count']}"
            )
    else:
        print("No missing CAT files found.")

    print("\n========================================")
    print("UNMATCHED CAT FILES")
    print("========================================\n")

    if all_unmatched:
        print(f"Saved unmatched CAT file list to: {UNMATCHED_CAT_FILE}\n")
        for row in all_unmatched:
            print(f"{row['camera']} | {row['subfolder']} | {row['cat_file']}")
    else:
        print("No unmatched CAT files found.")

    print("\nDone.")


# ----------------------------
# RUN
# ----------------------------
if __name__ == "__main__":
    run_all_cameras()