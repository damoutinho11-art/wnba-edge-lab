import csv
from datetime import datetime

path = "bet_tracker.csv"
backup_path = "bet_tracker_backup_before_sparks_repair.csv"

repairs = {
    "BET-00028": {
        "Date": "2026-05-30",
        "League": "WNBA",
        "Game": "LAS SPARKS @ WAS MYSTICS",
        "Player": "",
        "Market": "Alt Game Total",
        "Direction": "OVER",
        "Line": "165.5",
        "Odds": "1.95",
        "Stake": "0.10",
        "ActualUnits": "0.10",
        "Book": "manual",
        "Result": "WIN",
        "Status": "SETTLED",
        "Actual": "179",
        "P/L": "0.10",
        "Signal": "Manual settled total ladder",
        "ModelVersion": "manual_operator_entry_v21_9",
        "Notes": "Screenshot settled entry; Over 165.5 won; returned 0.20"
    },
    "BET-00029": {
        "Date": "2026-05-30",
        "League": "WNBA",
        "Game": "LAS SPARKS @ WAS MYSTICS",
        "Player": "",
        "Market": "Alt Game Total",
        "Direction": "OVER",
        "Line": "166.5",
        "Odds": "2.05",
        "Stake": "0.10",
        "ActualUnits": "0.10",
        "Book": "manual",
        "Result": "WIN",
        "Status": "SETTLED",
        "Actual": "179",
        "P/L": "0.11",
        "Signal": "Manual settled total ladder",
        "ModelVersion": "manual_operator_entry_v21_9",
        "Notes": "Screenshot settled entry; Over 166.5 won; returned 0.21"
    },
    "BET-00030": {
        "Date": "2026-05-30",
        "League": "WNBA",
        "Game": "LAS SPARKS @ WAS MYSTICS",
        "Player": "",
        "Market": "Alt Game Total",
        "Direction": "OVER",
        "Line": "167.5",
        "Odds": "2.15",
        "Stake": "0.10",
        "ActualUnits": "0.10",
        "Book": "manual",
        "Result": "WIN",
        "Status": "SETTLED",
        "Actual": "179",
        "P/L": "0.12",
        "Signal": "Manual settled total ladder",
        "ModelVersion": "manual_operator_entry_v21_9",
        "Notes": "Screenshot settled entry; Over 167.5 won; returned 0.22"
    },
    "BET-00031": {
        "Date": "2026-05-30",
        "League": "WNBA",
        "Game": "LAS SPARKS @ WAS MYSTICS",
        "Player": "",
        "Market": "Game Total",
        "Direction": "OVER",
        "Line": "168.5",
        "Odds": "1.86",
        "Stake": "0.10",
        "ActualUnits": "0.10",
        "Book": "manual",
        "Result": "WIN",
        "Status": "SETTLED",
        "Actual": "179",
        "P/L": "0.09",
        "Signal": "Manual settled total ladder",
        "ModelVersion": "manual_operator_entry_v21_9",
        "Notes": "Screenshot settled entry; Over 168.5 won; returned 0.19"
    },
    "BET-00032": {
        "Date": "2026-05-30",
        "League": "WNBA",
        "Game": "LAS SPARKS @ WAS MYSTICS",
        "Player": "",
        "Market": "Alt Game Total",
        "Direction": "OVER",
        "Line": "168.5",
        "Odds": "2.25",
        "Stake": "0.10",
        "ActualUnits": "0.10",
        "Book": "manual",
        "Result": "WIN",
        "Status": "SETTLED",
        "Actual": "179",
        "P/L": "0.13",
        "Signal": "Manual settled total ladder",
        "ModelVersion": "manual_operator_entry_v21_9",
        "Notes": "Screenshot settled entry; Over 168.5 alt won; returned 0.23"
    },
}

with open(path, newline="", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    rows = list(reader)

now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

for row in rows:
    bet_id = row.get("BetID")
    if bet_id in repairs:
        fixed = repairs[bet_id]
        for col in fieldnames:
            if col not in fixed and col not in ["BetID", "CreatedAt", "UpdatedAt"]:
                row[col] = ""
        for k, v in fixed.items():
            row[k] = v
        if not row.get("CreatedAt"):
            row["CreatedAt"] = now
        row["UpdatedAt"] = now

with open(path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print("OK: repaired BET-00028 through BET-00032 in bet_tracker.csv")
print("Backup:", backup_path)
