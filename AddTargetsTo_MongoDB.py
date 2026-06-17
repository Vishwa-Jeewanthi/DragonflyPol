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


# =============================================================================
# Configuration
# =============================================================================

MONGO_HOST = "localhost"
MONGO_PORT = 27017
DATABASE_NAME = "dfreduce_vishwa_polarimetry"
TARGET_COLLECTION = "targets"

TARGET_ID = "M51"
RA_STRING = "13 29 52.34"
DEC_STRING = "47 11 47.43"

OBJECT_TYPE = "Galaxy"
SURVEY = "standard"


# =============================================================================
# Coordinate conversion
# =============================================================================

coord = SkyCoord(RA_STRING, DEC_STRING, unit=(u.hourangle, u.deg))

ra_deg_0_360 = float(coord.ra.deg)
dec_deg = float(coord.dec.deg)

# MongoDB GeoJSON longitude should be in [-180, 180].
ra_longitude = ra_deg_0_360 - 360.0 if ra_deg_0_360 > 180.0 else ra_deg_0_360


# =============================================================================
# MongoDB upsert
# =============================================================================

client = MongoClient(MONGO_HOST, MONGO_PORT)
db = client[DATABASE_NAME]
targets = db[TARGET_COLLECTION]

target_doc = {
    "coord": {
        "type": "Point",
        "coordinates": [ra_longitude, dec_deg],
    },
    "survey": SURVEY,
    "object_type": OBJECT_TYPE,
    "ra_deg": ra_deg_0_360,
    "dec_deg": dec_deg,
}

result = targets.update_one(
    {"_id": TARGET_ID},
    {"$set": target_doc},
    upsert=True,
)

client.close()


# =============================================================================
# Summary
# =============================================================================

if result.upserted_id is not None:
    action = "added"
elif result.modified_count > 0:
    action = "updated"
else:
    action = "already up to date"

print(f"{TARGET_ID} {action}")
print(f"RA  0-360 deg: {ra_deg_0_360:.8f}")
print(f"Dec deg     : {dec_deg:.8f}")
print(f"Mongo coord : [{ra_longitude:.8f}, {dec_deg:.8f}]")
print(f"GeoJSON type: Point")
print(f"Object type : {OBJECT_TYPE}")
