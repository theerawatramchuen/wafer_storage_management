"""
Wafer Box Storage Management System
Flask web application
"""

import os
import json
import math
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import pandas as pd

app = Flask(__name__)
app.secret_key = "wafer_storage_secret_2026"

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

# ── helpers ──────────────────────────────────────────────────────────────────

def load_data():
    cabinet_type = pd.read_csv(os.path.join(DATA_DIR, "cabinet_type.csv"))
    cabinet_profile = pd.read_csv(os.path.join(DATA_DIR, "cabinet_profile.csv"))
    wafer_box_type = pd.read_csv(os.path.join(DATA_DIR, "wafer_box_type.csv"))
    datalog = pd.read_csv(os.path.join(DATA_DIR, "cabinet_datalog.csv"))

    # clean up duplicate cabinet_profile rows (cabinet 24 and 225 appear twice)
    cabinet_profile = cabinet_profile.drop_duplicates(subset=["cabinet_no"])

    # join profile → type dimensions
    cabinet_merged = cabinet_profile.merge(
        cabinet_type, on="cabinet_type_id", how="left"
    )
    cabinet_merged["cabinet_vol_mm3"] = (
        cabinet_merged["width"] * cabinet_merged["length"] * cabinet_merged["height"]
    )
    cabinet_merged["cabinet_vol_cm3"] = cabinet_merged["cabinet_vol_mm3"] / 1000
    cabinet_merged["cabinet_no"] = cabinet_merged["cabinet_no"].astype(str)

    # join box_type dimensions into datalog
    datalog["cabinet_no"] = datalog["cabinet_no"].astype(str)
    datalog_full = datalog.merge(wafer_box_type, on="wafer_box_type_id", how="left")
    datalog_full["box_vol_mm3"] = (
        datalog_full["width"] * datalog_full["length"] * datalog_full["height"]
    )

    return cabinet_merged, wafer_box_type, datalog_full


def current_occupancy(datalog_full):
    """Return datalog rows that are currently IN (no take-out date)."""
    return datalog_full[datalog_full["date_time_out"].isna()].copy()


def cabinet_space_summary(cabinet_merged, datalog_full):
    """Build per-cabinet space summary."""
    occupied = current_occupancy(datalog_full)
    used_vol = (
        occupied.groupby("cabinet_no")["box_vol_mm3"].sum().reset_index()
    )
    used_vol.columns = ["cabinet_no", "used_vol_mm3"]

    summary = cabinet_merged.merge(used_vol, on="cabinet_no", how="left")
    summary["used_vol_mm3"] = summary["used_vol_mm3"].fillna(0)
    summary["free_vol_mm3"] = summary["cabinet_vol_mm3"] - summary["used_vol_mm3"]
    summary["free_vol_cm3"] = summary["free_vol_mm3"] / 1000
    summary["used_vol_cm3"] = summary["used_vol_mm3"] / 1000
    summary["total_vol_cm3"] = summary["cabinet_vol_mm3"] / 1000
    summary["usage_pct"] = (
        summary["used_vol_mm3"] / summary["cabinet_vol_mm3"] * 100
    ).clip(0, 100).round(1)
    summary["item_count"] = (
        occupied.groupby("cabinet_no").size()
        .reindex(summary["cabinet_no"]).fillna(0).values
    )
    return summary


# ── routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    cabinet_merged, wafer_box_type, datalog_full = load_data()
    summary = cabinet_space_summary(cabinet_merged, datalog_full)
    occupied = current_occupancy(datalog_full)

    total_cabinets = len(summary)
    total_vol = summary["total_vol_cm3"].sum()
    total_used = summary["used_vol_cm3"].sum()
    total_free = summary["free_vol_cm3"].sum()
    overall_pct = round(total_used / total_vol * 100, 1) if total_vol > 0 else 0
    total_items = int(occupied.shape[0])

    # cabinet type breakdown
    type_stats = (
        summary.groupby("cabinet_type_id")
        .agg(count=("cabinet_no", "count"), free_cm3=("free_vol_cm3", "sum"))
        .reset_index()
    )

    # recent activity (last 10 entries)
    sorted_log = datalog_full.sort_values("date_time_in", ascending=False)
    recent = sorted_log.head(15)[
        ["cabinet_no", "wafer_lot_no", "wafer_box_type_id", "date_time_in", "put_in_by_en", "date_time_out"]
    ].to_dict("records")

    return render_template(
        "index.html",
        summary=summary.to_dict("records"),
        total_cabinets=total_cabinets,
        total_vol=round(total_vol),
        total_used=round(total_used),
        total_free=round(total_free),
        overall_pct=overall_pct,
        total_items=total_items,
        type_stats=type_stats.to_dict("records"),
        recent=recent,
    )


@app.route("/cabinets")
def cabinets():
    cabinet_merged, wafer_box_type, datalog_full = load_data()
    summary = cabinet_space_summary(cabinet_merged, datalog_full)
    type_filter = request.args.get("type", "")
    sort_by = request.args.get("sort", "cabinet_no")
    cabinet_types = sorted(cabinet_merged["cabinet_type_id"].unique())

    if type_filter:
        summary = summary[summary["cabinet_type_id"] == type_filter]

    if sort_by == "free_asc":
        summary = summary.sort_values("free_vol_cm3")
    elif sort_by == "free_desc":
        summary = summary.sort_values("free_vol_cm3", ascending=False)
    elif sort_by == "usage":
        summary = summary.sort_values("usage_pct", ascending=False)
    else:
        summary = summary.sort_values("cabinet_no")

    return render_template(
        "cabinets.html",
        cabinets=summary.to_dict("records"),
        cabinet_types=cabinet_types,
        type_filter=type_filter,
        sort_by=sort_by,
    )


@app.route("/cabinet/<cab_no>")
def cabinet_detail(cab_no):
    cabinet_merged, wafer_box_type, datalog_full = load_data()
    summary = cabinet_space_summary(cabinet_merged, datalog_full)

    cab_info = summary[summary["cabinet_no"] == str(cab_no)]
    if cab_info.empty:
        flash(f"Cabinet {cab_no} not found.", "danger")
        return redirect(url_for("cabinets"))
    cab_info = cab_info.iloc[0].to_dict()

    occupied = current_occupancy(datalog_full)
    items_in = occupied[occupied["cabinet_no"] == str(cab_no)][
        ["wafer_lot_no", "wafer_box_no", "wafer_box_type_id", "description",
         "width", "length", "height", "box_vol_mm3", "date_time_in", "put_in_by_en"]
    ].to_dict("records")

    history = datalog_full[
        (datalog_full["cabinet_no"] == str(cab_no)) &
        (datalog_full["date_time_out"].notna())
    ].sort_values("date_time_out", ascending=False).head(20)[
        ["wafer_lot_no", "wafer_box_no", "wafer_box_type_id", "date_time_in",
         "put_in_by_en", "date_time_out", "take_out_by_en"]
    ].to_dict("records")

    return render_template(
        "cabinet_detail.html",
        cab=cab_info,
        items_in=items_in,
        history=history,
        cab_no=cab_no,
    )


@app.route("/find_space", methods=["GET", "POST"])
def find_space():
    cabinet_merged, wafer_box_type, datalog_full = load_data()
    box_types = wafer_box_type.to_dict("records")
    results = []
    search_done = False

    if request.method == "POST":
        box_type_id = request.form.get("box_type_id", "")
        qty = int(request.form.get("qty", 1))
        pref_type = request.form.get("pref_cabinet_type", "")

        box_row = wafer_box_type[wafer_box_type["wafer_box_type_id"] == box_type_id]
        if box_row.empty:
            flash("Unknown box type.", "danger")
        else:
            box_vol = int(box_row.iloc[0]["width"]) * int(box_row.iloc[0]["length"]) * int(box_row.iloc[0]["height"])
            needed_vol = box_vol * qty

            summary = cabinet_space_summary(cabinet_merged, datalog_full)
            if pref_type:
                summary = summary[summary["cabinet_type_id"] == pref_type]

            fits = summary[summary["free_vol_mm3"] >= needed_vol].sort_values("free_vol_mm3")
            results = fits[
                ["cabinet_no", "cabinet_type_id", "description",
                 "free_vol_mm3", "free_vol_cm3", "usage_pct", "item_count"]
            ].rename(columns={"description": "cabinet_desc"}).to_dict("records")
            search_done = True

    cabinet_types = sorted(cabinet_merged["cabinet_type_id"].unique())
    return render_template(
        "find_space.html",
        box_types=box_types,
        results=results,
        search_done=search_done,
        cabinet_types=cabinet_types,
    )


@app.route("/find_lot", methods=["GET", "POST"])
def find_lot():
    cabinet_merged, wafer_box_type, datalog_full = load_data()
    results = []
    search_done = False
    query = ""

    if request.method == "POST":
        query = request.form.get("lot_no", "").strip()
        if query:
            mask = (
                datalog_full["wafer_lot_no"].astype(str).str.contains(query, case=False, na=False)
            )
            found = datalog_full[mask][
                ["cabinet_no", "wafer_lot_no", "wafer_box_no", "wafer_box_type_id",
                 "date_time_in", "put_in_by_en", "date_time_out", "take_out_by_en"]
            ].sort_values("date_time_in", ascending=False)
            results = found.to_dict("records")
            search_done = True

    return render_template(
        "find_lot.html",
        results=results,
        search_done=search_done,
        query=query,
    )


@app.route("/checkin", methods=["GET", "POST"])
def checkin():
    cabinet_merged, wafer_box_type, datalog_full = load_data()

    if request.method == "POST":
        en = request.form.get("en", "").strip()
        cabinet_no = request.form.get("cabinet_no", "").strip()
        lot_no = request.form.get("lot_no", "").strip()
        box_no = request.form.get("box_no", "0").strip() or "0"
        box_type = request.form.get("box_type_id", "").strip()
        date_in = request.form.get("date_in", "").strip()

        errors = []
        if not en:
            errors.append("Employee number is required.")
        if not cabinet_no:
            errors.append("Cabinet number is required.")
        if not lot_no:
            errors.append("Wafer lot number is required.")
        if not box_type:
            errors.append("Box type is required.")
        if not date_in:
            errors.append("Date in is required.")

        # validate cabinet exists
        if cabinet_no and cabinet_no not in cabinet_merged["cabinet_no"].astype(str).values:
            errors.append(f"Cabinet '{cabinet_no}' does not exist in profile.")

        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            datalog = pd.read_csv(os.path.join(DATA_DIR, "cabinet_datalog.csv"))
            new_row = {
                "cabinet_no": cabinet_no,
                "wafer_lot_no": lot_no,
                "wafer_box_no": box_no,
                "wafer_box_type_id": box_type,
                "date_time_in": date_in,
                "put_in_by_en": en,
                "date_time_out": None,
                "take_out_by_en": None,
            }
            datalog = pd.concat([datalog, pd.DataFrame([new_row])], ignore_index=True)
            datalog.to_csv(os.path.join(DATA_DIR, "cabinet_datalog.csv"), index=False)
            flash(f"✓ Wafer lot '{lot_no}' checked in to cabinet {cabinet_no}.", "success")
            return redirect(url_for("checkin"))

    cabinet_list = sorted(cabinet_merged["cabinet_no"].astype(str).unique())
    box_types = wafer_box_type.to_dict("records")
    today = datetime.now().strftime("%d/%m/%Y")

    return render_template(
        "checkin.html",
        cabinet_list=cabinet_list,
        box_types=box_types,
        today=today,
    )


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cabinet_merged, wafer_box_type, datalog_full = load_data()

    if request.method == "POST":
        en = request.form.get("en", "").strip()
        cabinet_no = request.form.get("cabinet_no", "").strip()
        lot_no = request.form.get("lot_no", "").strip()
        box_no = request.form.get("box_no", "0").strip() or "0"
        date_out = request.form.get("date_out", "").strip()

        errors = []
        if not en:
            errors.append("Employee number is required.")
        if not lot_no:
            errors.append("Wafer lot number is required.")
        if not date_out:
            errors.append("Date out is required.")

        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            datalog = pd.read_csv(os.path.join(DATA_DIR, "cabinet_datalog.csv"))
            mask = (
                (datalog["wafer_lot_no"].astype(str) == lot_no) &
                (datalog["wafer_box_no"].astype(str) == str(box_no)) &
                (datalog["date_time_out"].isna())
            )
            if cabinet_no:
                mask &= datalog["cabinet_no"].astype(str) == cabinet_no

            if mask.sum() == 0:
                flash(f"No active record found for lot '{lot_no}' / box '{box_no}'.", "warning")
            else:
                datalog.loc[mask, "date_time_out"] = date_out
                datalog.loc[mask, "take_out_by_en"] = float(en)
                datalog.to_csv(os.path.join(DATA_DIR, "cabinet_datalog.csv"), index=False)
                flash(f"✓ Lot '{lot_no}' box '{box_no}' checked out.", "success")
                return redirect(url_for("checkout"))

    occupied = current_occupancy(datalog_full)
    active_lots = sorted(occupied["wafer_lot_no"].astype(str).unique())
    cabinet_list = sorted(cabinet_merged["cabinet_no"].astype(str).unique())
    today = datetime.now().strftime("%d/%m/%Y")

    return render_template(
        "checkout.html",
        active_lots=active_lots,
        cabinet_list=cabinet_list,
        today=today,
    )


@app.route("/api/cabinet_space")
def api_cabinet_space():
    cabinet_merged, wafer_box_type, datalog_full = load_data()
    summary = cabinet_space_summary(cabinet_merged, datalog_full)
    total = len(summary)
    by_type = summary.groupby("cabinet_type_id").agg(
        cabinets=("cabinet_no", "count"),
        total_cm3=("total_vol_cm3", "sum"),
        free_cm3=("free_vol_cm3", "sum"),
    ).reset_index()
    return jsonify({
        "total_cabinets": total,
        "total_vol_cm3": round(summary["total_vol_cm3"].sum()),
        "used_vol_cm3": round(summary["used_vol_cm3"].sum()),
        "free_vol_cm3": round(summary["free_vol_cm3"].sum()),
        "by_type": by_type.to_dict("records"),
    })


@app.route("/api/lot_location/<lot_no>")
def api_lot_location(lot_no):
    cabinet_merged, wafer_box_type, datalog_full = load_data()
    occupied = current_occupancy(datalog_full)
    found = occupied[occupied["wafer_lot_no"].astype(str).str.upper() == lot_no.upper()]
    if found.empty:
        return jsonify({"found": False})
    return jsonify({
        "found": True,
        "records": found[["cabinet_no", "wafer_box_no", "wafer_box_type_id",
                           "date_time_in", "put_in_by_en"]].to_dict("records"),
    })


@app.route("/statistics")
def statistics():
    cabinet_merged, wafer_box_type, datalog_full = load_data()
    summary = cabinet_space_summary(cabinet_merged, datalog_full)
    occupied = current_occupancy(datalog_full)

    # most used box types (currently stored)
    box_counts = occupied.groupby("wafer_box_type_id").size().reset_index(name="count")
    box_counts = box_counts.merge(wafer_box_type[["wafer_box_type_id", "description"]], on="wafer_box_type_id", how="left")
    box_counts = box_counts.sort_values("count", ascending=False)

    # cabinet utilization histogram
    labels = ["0-20%", "20-40%", "40-60%", "60-80%", "80-100%"]
    bins = [0, 20, 40, 60, 80, 100]
    cut = pd.cut(summary["usage_pct"], bins=bins, labels=labels, right=True)
    hist_series = cut.value_counts().reindex(labels, fill_value=0)
    hist = hist_series.tolist()

    # activity by EN
    activity = (
        datalog_full.groupby("put_in_by_en").size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .head(10)
    )

    return render_template(
        "statistics.html",
        summary=summary,
        box_counts=box_counts.to_dict("records"),
        activity=activity.to_dict("records"),
        hist_counts=hist,
        hist_labels=labels,
        total_active=len(occupied),
        total_cabinets=len(summary),
        avg_usage=round(summary["usage_pct"].mean(), 1),
        most_crowded=summary.nlargest(5, "usage_pct")[["cabinet_no", "cabinet_type_id", "usage_pct", "item_count"]].to_dict("records"),
        emptiest=summary.nsmallest(5, "usage_pct")[["cabinet_no", "cabinet_type_id", "usage_pct", "item_count"]].to_dict("records"),
    )


if __name__ == "__main__":
    app.run(debug=True, port=5050, host="0.0.0.0")
