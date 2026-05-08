# Wafer Box Storage Management System

## Requirements
```
pip install flask pandas
```

## Run
```
python run.py
```
Then open: **http://localhost:5050**

## Data Files (place in same folder as app.py)
- `cabinet_type.csv`       — cabinet type definitions (W×L×H in mm)
- `cabinet_profile.csv`    — maps each cabinet_no to its type
- `wafer_box_type.csv`     — box type definitions (W×L×H in mm)
- `cabinet_datalog.csv`    — transaction log (check-in / check-out records)

## Features
| Page | Function |
|------|----------|
| Dashboard | KPIs, space donut chart, type bar chart, recent activity |
| Cabinets | Full list with filter by type, sort by space/usage |
| Cabinet Detail | Items currently stored + history + usage donut |
| Find Space | Select box type + qty → ranked list of fitting cabinets |
| Find Lot | Search lot number (partial match) across all records |
| Check In | Add wafer box to a cabinet, logged with EN + date |
| Check Out | Mark wafer box as removed, logged with EN + date |
| Statistics | Utilization histogram, top box types, top employees |

## Notes
- Volume is computed as W × L × H (mm³) and displayed in cm³  
- Usage % = sum of stored box volumes / cabinet total volume  
- check-in/out data is written back to `cabinet_datalog.csv`
## Reference
https://claude.ai/share/93355cfc-0b55-4067-b3da-f7cb2d7ab3d7
