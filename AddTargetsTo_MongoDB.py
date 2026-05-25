# =============================================================================
# AddTargetsTo_MongoDB.py
#
# Author      : Vishwa Jeewanthi
# Date        : 13 April 2026

#
# Purpose:
#   Manually inserts or updates target entries in the MongoDB 'targets'
#   collection for the DFReduce polarimetry database. This script is needed
#   when a target is missing from MongoDB and the pipeline cannot recognise
#   it during reduction.
#
#   The script:
#     - Converts target RA/Dec from sexagesimal to decimal degrees
#     - Adjusts RA into the [-180, 180] range required by MongoDB GeoJSON
#     - Upserts the target document with its coordinates and survey type
#
# Usage:
#   Update the target ID, coordinates, and survey type in the script,
#   then run:
#       python add_targets.py
#
# Developed with the assistance of AI tools (ChatGPT by OpenAI).
# =============================================================================

from pymongo import MongoClient
from astropy.coordinates import SkyCoord
import astropy.units as u

client = MongoClient("localhost", 27017)
db = client["dfreduce_vishwa_polarimetry"]

coord = SkyCoord("06 05 05.7", "+23 23 39.0", unit=(u.hourangle, u.deg))

ra_deg = float(coord.ra.deg)
dec_deg = float(coord.dec.deg)

# MongoDB GeoJSON expects longitude in [-180, 180]
if ra_deg > 180:
    ra_deg -= 360

db.targets.update_one(
    {"_id": "SPST05"},
    {
        "$set": {
            "coord": {
                "type": "Point",
                "coordinates": [ra_deg, dec_deg]
            },
            "survey": "standard"
        }
    },
    upsert=True
)

print("SPST05 added/updated")
print(f"Stored coord: [{ra_deg:.6f}, {dec_deg:.6f}]")
