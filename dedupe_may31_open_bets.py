import csv
from datetime import datetime

path = "bet_tracker.csv"
remove_ids = {"BET-00033", "BET-00034", "BET-00035", "BET-00036", "BET-00037", "BET-00038"}

# Final intended May 31 bet states
fixes = {
    "BET-00039": {
        "Date": "2026-05-31",
        "League": "WNBA",
        "Game": "LA Sparks @ CON Sun",
        "Player": "",
        "Market": "Spread",
        "Direction": "LAS",
        "Line": "-3.5",
        "Odds": "1.82",
        "Stake": "0.10",
        "ActualUnits": "0.10",
        "Book": "manual",
        "Result": "",
        "Status": "OPEN",
        "Actual": "",
        "P/L": "",
        "Signal": "MODEL_QUEUE_1",
        "ModelVersion": "manual_market_review_v21_9",
        "Projection": "",
        "Edge": "10.25",
        "Confidence": "66.75",
        "FinalSignal": "LEAN_SUPPORT",
        "SuggestedUnits": "",
        "Notes": "Executed model queue bet; LA Sparks -3.5 at 1.82"
    },
    "BET-00040": {
        "Date": "2026-05-31",
        "League": "WNBA",
        "Game": "LA Sparks @ CON Sun",
        "Player": "",
        "Market": "Moneyline",
        "Direction": "LAS",
        "Line": "0",
        "Odds": "1.83",
        "Stake": "0.10",
        "ActualUnits": "0.10",
        "Book": "manual",
        "Result": "",
        "Status": "OPEN",
        "Actual": "",
        "P/L": "",
        "Signal": "MODEL_QUEUE_ML",
        "ModelVersion": "manual_market_review_v21_9",
        "Projection": "",
        "Edge": "0.243",
        "Confidence": "70.0",
        "FinalSignal": "LEAN_SUPPORT",
        "SuggestedUnits": "",
        "Notes": "Executed model queue bet; LA Sparks ML at 1.83"
    },
    "BET-00041": {
        "Date": "2026-05-31",
        "League": "WNBA",
        "Game": "LV Aces @ GS Valkyries",
        "Player": "",
        "Market": "Game Total",
        "Direction": "OVER",
        "Line": "169.5",
        "Odds": "1.90",
        "Stake": "0.10",
        "ActualUnits": "0.10",
        "Book": "manual",
        "Result": "",
        "Status": "OPEN",
        "Actual": "",
        "P/L": "",
        "Signal": "MODEL_QUEUE_2",
        "ModelVersion": "manual_market_review_v21_9",
        "Projection": "",
        "Edge": "6.8133",
        "Confidence": "65.25",
        "FinalSignal": "LEAN_SUPPORT",
        "SuggestedUnits": "",
        "Notes": "Executed model queue bet; LV/GSV Over 169.5 at 1.90"
    },
    "BET-00042": {
        "Date": "2026-05-31",
        "League": "WNBA",
        "Game": "LV Aces @ GS Valkyries",
        "Player": "",
        "Market": "Spread",
        "Direction": "GSV",
        "Line": "+1.5",
        "Odds": "1.87",
        "Stake": "0.10",
        "ActualUnits": "0.10",
        "Book": "manual",
        "Result": "",
        "Status": "OPEN",
        "Actual": "",
        "P/L": "",
        "Signal": "MODEL_QUEUE_3",
        "ModelVersion": "manual_market_review_v21_9",
        "Projection": "",
        "Edge": "6.3583",
        "Confidence": "55.08",
        "FinalSignal": "LEAN_SUPPORT",
        "SuggestedUnits": "",
        "Notes": "Executed model queue bet; GSV +1.5 at 1.87"
    },
}

with open(path, newline="", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    rows = list(reader)

now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
cleaned = []

for row in rows:
    bet_id = row.get("BetID")
    if bet_id in remove_ids:
        continue

    if bet_id in fixes:
        fixed = fixes[bet_id]
        for col in fieldnames:
            if col not in fixed and col not in ["BetID", "CreatedAt", "UpdatedAt"]:
                row[col] = ""
        for k, v in fixed.items():
            row[k] = v
        if not row.get("CreatedAt"):
            row["CreatedAt"] = now
        row["UpdatedAt"] = now

    cleaned.append(row)

with open(path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(cleaned)

print("OK: removed BET-00033..BET-00038 and kept fixed BET-00039..BET-00042")
print("Backup: bet_tracker_backup_before_may31_dedupe.csv")
