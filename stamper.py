#!/usr/bin/env python3

# =============================================================================
# stamper.py
#
# Author      : Vishwa Jeewanthi
# Date        : 09 March 2026
#
# Purpose:
#   Stamps correct polarization filter information into the FITS headers of
#   DragonflyPol science frames. Raw images from the telescope record only a
#   generic filter name (r' or g') in their headers, rather than the specific
#   polarization angle assigned to each lens. This script resolves that by:
#     - Mapping each camera unit name (e.g. Dragonfly101) to its serial number
#     - Mapping each serial number to its polarization angle (r_0, r_45, r_90,
#       r_135, or r for unpolarized lenses)
#     - Writing the correct FILTER, FILTNAM, and POL_ANG keywords directly
#       into the FITS headers of all light frames for a given observing date
#     - Automatically skipping calibration frames and macOS sidecar files
#
#   This stamping step is required for the DFReduce pipeline to correctly
#   group frames by polarization angle and produce the 4 median coadds
#   (one per angle) needed for polarimetric data reduction.
#
# Usage:
#   Set TARGET_DATE and DATA_PATH in the CONFIGURATION section, then run:
#       python stamper.py
#
# Reference:
#   Camera-to-serial mappings adapted from cameras.py in the DFReduce pipeline
#   by Mehrnoosh Tahani et al.
#   https://github.com/MehrnooshTahani/DFReduce/blob/master/src/dfreduce/cameras.py
#
# =============================================================================

import os
from pathlib import Path
from astropy.io import fits

# --- BUILT-IN HARDWARE MAPPINGS ---
serialno_dict = {
    'Dragonfly101': 'T13080513',
    'Dragonfly102': 'T13100592',
    'Dragonfly103': 'T13090562',
    'Dragonfly104': 'T13100588',
    'Dragonfly105': 'T13100585',
    'Dragonfly106': 'T13030365',
    'Dragonfly107': 'T13110627',
    'Dragonfly108': 'T13110605',
    'Dragonfly109': 'T13110598',
    'Dragonfly110': 'T13060460',
    'Dragonfly111': 'T13100595',
    'Dragonfly112': 'T13110623',
    'Dragonfly113': 'T13090528',
    'Dragonfly114': 'T13090526',
    'Dragonfly115': 'T13100591',
    'Dragonfly116': 'T13100580',
    'Dragonfly117': 'T13110625',
    'Dragonfly118': 'T13090552',
    'Dragonfly119': 'T13090553',
    'Dragonfly120': 'T13110630',
    'Dragonfly121': 'T13110597',
    'Dragonfly122': 'T13090570',
    'Dragonfly123': 'T13110629',
    'Dragonfly124': 'T12110253',
    'Dragonfly201': '83F010612',
    'Dragonfly202': '83F010820',
    'Dragonfly203': '83F010692',
    'Dragonfly204': '83F010730',
    'Dragonfly205': '83F010783',
    'Dragonfly206': '83F010784',
    'Dragonfly207': '83F011129',
    'Dragonfly208': '83F010826',
    'Dragonfly209': '83F010827',
    'Dragonfly210': 'T13100590',
    'Dragonfly211': '83F010687',
    'Dragonfly212': 'T13070473',
    'Dragonfly213': 'T13090554',
    'Dragonfly214': 'T13090564',
    'Dragonfly215': 'T13090565',
    'Dragonfly216': 'T13090568',
    'Dragonfly217': 'T13090571',
    'Dragonfly218': 'T13100579',
    'Dragonfly219': 'T13100584',
    'Dragonfly220': 'T13100587',
    'Dragonfly221': 'T13110600',
    'Dragonfly222': 'T13110621',
    'Dragonfly223': 'T13110624',
    'Dragonfly224': 'T13110628',
}

filter_dict = {
    'T13080513': 'r_0',
    'T13100592': 'r_0',
    'T13090562': 'r_45',
    'T13100588': 'r_90',
    'T13100585': 'r_0',
    'T13030365': 'r_90',
    'T13110627': 'r_45',
    'T13110605': 'r_135',
    'T13110598': 'r_135',
    'T13060460': 'r_45',
    'T13100595': 'r',        # non-angle standard
    'T13110623': 'r_0',
    'T13090528': 'r_90',
    'T13090526': 'r_0',
    'T13100591': 'r_135',
    'T13100580': 'r_90',
    'T13110625': 'r_90',
    'T13090552': 'r_45',
    'T13090553': 'r_45',
    'T13110630': 'r_0',
    'T13110597': 'r_90',
    'T13090570': 'r_135',
    'T13110629': 'r_135',
    'T12110253': 'r',        # non-angle standard
    '83F010612': 'r_0',
    '83F010820': 'r_45',
    '83F010692': 'r_135',
    '83F010730': 'r_90',
    '83F010783': 'r',        # non-angle standard
    '83F010784': 'r_0',
    '83F011129': 'r_135',
    '83F010826': 'r_45',
    '83F010827': 'r_90',
    'T13100590': 'r_90',
    '83F010687': 'r_135',
    'T13070473': 'r_0',
    'T13090554': 'r_45',
    'T13090564': 'r_45',
    'T13090565': 'r_135',
    'T13090568': 'r_135',
    'T13090571': 'r_90',
    'T13100579': 'r_0',
    'T13100584': 'r_0',
    'T13100587': 'r_45',
    'T13110600': 'r_135',
    'T13110621': 'r',        # non-angle standard
    'T13110624': 'r_90',
    'T13110628': 'r_45',
}

# --- CONFIGURATION ---
DATA_PATH = '/Volumes/ExtremeSSD/data/RawData/'
TARGET_DATE = '2026-03-13'

def run_stamper(root_dir: str) -> None:
    print(f"--- Starting Header Stamping for {TARGET_DATE} ---")
    count = 0
    skipped_cals = 0
    skipped_junk = 0
    unmapped = 0

    for root, dirs, files in os.walk(root_dir):
        if TARGET_DATE not in root:
            continue

        path_parts = Path(root).parts
        unit_name = next(
            (p for p in path_parts if p.startswith("Dragonfly") and p[9:].isdigit()),
            None
        )

        if unit_name is None:
            continue

        sn = serialno_dict.get(unit_name)
        tag = filter_dict.get(sn)

        if sn is None or tag is None:
            print(f"Warning: No mapping for unit '{unit_name}' (serial: {sn})")
            unmapped += 1
            continue

        for file in files:
            if not file.endswith('.fits'):
                continue

            # Skip macOS sidecar junk files
            if file.startswith('._'):
                skipped_junk += 1
                continue

            file_path = os.path.join(root, file)

            try:
                with fits.open(file_path, mode='update') as hdul:
                    header = hdul[0].header
                    img_type = str(header.get('IMAGETYP', '')).strip().lower()

                    # Only stamp science frames
                    if img_type != 'light':
                        skipped_cals += 1
                        continue

                    header['FILTER'] = tag
                    header['FILTNAM'] = tag

                    if 'TARGET' in header:
                        header['OBJECT'] = header['TARGET']

                    if '_' in tag:
                        try:
                            header['POL_ANG'] = int(tag.split('_')[1])
                        except Exception:
                            pass

                    hdul.flush()
                    count += 1

                    if count % 20 == 0:
                        print(f"Processing {unit_name}: {count} science frames updated...")

            except Exception as e:
                print(f"Error on {file}: {e}")

    print(f"\n--- Stamping Complete! ---")
    print(f"Science Frames Updated: {count}")
    print(f"Calibration Frames Skipped: {skipped_cals}")
    print(f"Junk Files Skipped: {skipped_junk}")
    print(f"Unmapped Units: {unmapped}")

if __name__ == "__main__":
    run_stamper(DATA_PATH)