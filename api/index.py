from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

app = FastAPI(
    title="Dashboard Curah Hujan Sumatera Barat",
    description="API dashboard hasil imputasi curah hujan harian dengan Random Forest sekuensial.",
    version="1.0.0",
)

STATUS_LABELS = {
    0: "Data asli",
    1: "Data imputasi",
    2: "Celah aktif belum terisi",
    3: "Di luar rentang aktif",
}

REGION_PREFIX_MAP = {
    "1301": ("1302", "Kab. Pesisir Selatan"),
    "1302": ("1303", "Kab. Solok"),
    "1303": ("1304", "Kab. Sijunjung"),
    "1304": ("1305", "Kab. Tanah Datar"),
    "1305": ("1306", "Kab. Padang Pariaman"),
    "1306": ("1307", "Kab. Agam"),
    "1307": ("1308", "Kab. Lima Puluh Kota"),
    "1308": ("1309", "Kab. Pasaman"),
    "1309": ("1301", "Kab. Kepulauan Mentawai"),
    "1310": ("1311", "Kab. Dharmasraya"),
    "1311": ("1310", "Kab. Solok Selatan"),
    "1312": ("1312", "Kab. Pasaman Barat"),
    "1371": ("1371", "Kota Padang"),
    "1372": ("1372", "Kota Solok"),
    "1373": ("1373", "Kota Sawahlunto"),
    "1374": ("1374", "Kota Padang Panjang"),
    "1375": ("1375", "Kota Bukittinggi"),
    "1376": ("1376", "Kota Payakumbuh"),
    "1377": ("1377", "Kota Pariaman"),
}


def classify_rainfall(value):
    """Classify daily rainfall using the thresholds supplied for this dashboard."""
    if value is None or pd.isna(value):
        return "Tidak tersedia"
    value = float(value)
    if value < 0.5:
        return "Tidak hujan / di bawah ambang"
    if value < 20:
        return "Hujan ringan"
    if value < 50:
        return "Hujan sedang"
    if value < 100:
        return "Hujan lebat"
    if value <= 150:
        return "Hujan sangat lebat"
    return "Hujan ekstrem"


def safe_float(value):
    if value is None or pd.isna(value):
        return None
    return float(value)


@lru_cache(maxsize=1)
def load_data():
    matrix = pd.read_csv(DATA_DIR / "rainfall_matrix.csv", low_memory=False)
    flags = pd.read_csv(DATA_DIR / "rainfall_flags.csv", low_memory=False)
    stations = pd.read_csv(DATA_DIR / "stations.csv", low_memory=False)

    matrix["tanggal"] = pd.to_datetime(matrix["tanggal"], errors="coerce").dt.strftime("%Y-%m-%d")
    flags["tanggal"] = pd.to_datetime(flags["tanggal"], errors="coerce").dt.strftime("%Y-%m-%d")
    matrix = matrix.set_index("tanggal").apply(pd.to_numeric, errors="coerce")
    flags = flags.set_index("tanggal").apply(pd.to_numeric, errors="coerce").fillna(2).astype(int)

    matrix_ids = [col for col in matrix.columns if col in set(stations["pos_hujan_id"].astype(str))]
    matrix = matrix[matrix_ids]
    active_stations = stations[stations["pos_hujan_id"].astype(str).isin(matrix_ids)].copy()
    active_stations["pos_hujan_id"] = active_stations["pos_hujan_id"].astype(str)
    active_stations["kode_bps"] = active_stations["kode_bps"].astype(str)
    active_stations["latitude"] = pd.to_numeric(active_stations["latitude"], errors="coerce")
    active_stations["longitude"] = pd.to_numeric(active_stations["longitude"], errors="coerce")
    active_stations["elevasi_m"] = pd.to_numeric(active_stations["elevasi_m"], errors="coerce")

    flags = flags.reindex(index=matrix.index, columns=matrix.columns)
    stations = stations.fillna("")
    return matrix, flags, active_stations, stations


def parse_window(start: Optional[str], end: Optional[str]):
    matrix, _, _, _ = load_data()
    min_date = date.fromisoformat(matrix.index.min())
    max_date = date.fromisoformat(matrix.index.max())
    end_date = date.fromisoformat(end) if end else max_date
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=6)
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Tanggal awal tidak boleh setelah tanggal akhir.")
    if (end_date - start_date).days > 6:
        raise HTTPException(status_code=400, detail="Rentang tanggal maksimal 7 hari.")
    if start_date < min_date or end_date > max_date:
        raise HTTPException(status_code=400, detail=f"Tanggal harus berada dalam rentang {min_date} sampai {max_date}.")
    return start_date.isoformat(), end_date.isoformat()


def status_for(flag, value):
    # Check flag 3 before missing values: outside-active cells are intentionally blank.
    if flag == 3:
        return "Di luar rentang aktif"
    if flag == 2:
        return "Celah aktif belum terisi"
    if flag == 0 and not pd.isna(value):
        return "Data asli"
    if flag == 1 and not pd.isna(value):
        return "Data imputasi"
    if pd.isna(value):
        return "Celah aktif belum terisi"
    return STATUS_LABELS.get(int(flag), "Tidak diketahui")


@app.get("/api/health")
@app.get("/health")
def health():
    matrix, _, stations, _ = load_data()
    return {"status": "ok", "dates": len(matrix), "active_stations": len(stations)}


@app.get("/api/meta")
@app.get("/meta")
def metadata():
    matrix, flags, active_stations, all_stations = load_data()
    region_rows = (
        active_stations[["kode_bps", "kabupaten_kota"]]
        .drop_duplicates()
        .sort_values("kabupaten_kota")
        .to_dict(orient="records")
    )
    return {
        "title": "Imputasi Data Curah Hujan Harian di Sumatera Barat Menggunakan Random Forest Sekuensial",
        "date_min": matrix.index.min(),
        "date_max": matrix.index.max(),
        "n_days": int(len(matrix)),
        "n_matrix_stations": int(len(active_stations)),
        "n_source_stations": int(len(all_stations)),
        "n_source_stations_not_in_matrix": int((~all_stations["ada_di_matriks"].astype(bool)).sum()),
        "regions": region_rows,
        "classifications": [
            {"label": "Tidak hujan / di bawah ambang", "range": "< 0,5 mm/hari", "color": "#9CA3AF"},
            {"label": "Hujan ringan", "range": "0,5 sampai < 20 mm/hari", "hourly": "1–5 mm/jam", "color": "#60A5FA"},
            {"label": "Hujan sedang", "range": "20 sampai < 50 mm/hari", "hourly": "5–10 mm/jam", "color": "#FBBF24"},
            {"label": "Hujan lebat", "range": "50 sampai < 100 mm/hari", "hourly": "10–20 mm/jam", "color": "#F97316"},
            {"label": "Hujan sangat lebat", "range": "100–150 mm/hari", "hourly": "> 20 mm/jam", "color": "#EF4444"},
            {"label": "Hujan ekstrem", "range": "> 150 mm/hari", "color": "#991B1B"},
        ],
        "status_labels": STATUS_LABELS,
    }


@lru_cache(maxsize=1)
def build_summary():
    matrix, flags, active_stations, all_stations = load_data()
    ids = list(matrix.columns)
    station_lookup = active_stations.set_index("pos_hujan_id").to_dict(orient="index")

    flag_counts = flags.stack().value_counts().to_dict()
    n_original = int(flag_counts.get(0, 0))
    n_imputed = int(flag_counts.get(1, 0))
    n_active_missing = int(flag_counts.get(2, 0))
    n_outside = int(flag_counts.get(3, 0))
    target_cells = n_imputed + n_active_missing
    coverage = (n_imputed / target_cells * 100) if target_cells else 0.0

    all_values = matrix.to_numpy(dtype=float)
    valid_values = all_values[np.isfinite(all_values)]
    max_value = float(np.nanmax(all_values)) if np.isfinite(all_values).any() else None
    if max_value is not None:
        max_i, max_j = np.unravel_index(np.nanargmax(all_values), all_values.shape)
        max_date = str(matrix.index[max_i])
        max_station_id = str(ids[max_j])
        max_station = station_lookup.get(max_station_id, {})
    else:
        max_date, max_station_id, max_station = None, None, {}

    station_rows = []
    for sid in ids:
        series = matrix[sid]
        if series.notna().any():
            max_idx = series.idxmax()
            station = station_lookup.get(sid, {})
            station_rows.append({
                "pos_hujan_id": sid,
                "nama_pos": str(station.get("nama_pos", sid)),
                "kode_bps": str(station.get("kode_bps", "")),
                "kabupaten_kota": str(station.get("kabupaten_kota", "Belum dipetakan")),
                "rata_rata_pos_mm_hari": float(series.mean()),
                "maksimum_harian_mm": float(series.max()),
                "tanggal_maksimum": str(max_idx),
                "latitude": safe_float(station.get("latitude")),
                "longitude": safe_float(station.get("longitude")),
            })

    per_station = pd.DataFrame(station_rows)
    rankings = []
    for (code, region), group in per_station.groupby(["kode_bps", "kabupaten_kota"], dropna=False):
        max_row = group.loc[group["maksimum_harian_mm"].idxmax()]
        rankings.append({
            "kode_bps": str(code),
            "kabupaten_kota": str(region),
            "rata_rata_curah_hujan_per_pos_mm_hari": float(group["rata_rata_pos_mm_hari"].mean()),
            "maksimum_harian_mm": float(max_row["maksimum_harian_mm"]),
            "tanggal_maksimum": str(max_row["tanggal_maksimum"]),
            "pos_maksimum": str(max_row["nama_pos"]),
            "jumlah_pos": int(group["pos_hujan_id"].nunique()),
        })
    rankings.sort(key=lambda x: x["rata_rata_curah_hujan_per_pos_mm_hari"], reverse=True)

    daily_avg = matrix.mean(axis=1, skipna=True)
    daily_series = [{"tanggal": str(idx), "mm_hari": safe_float(val)} for idx, val in daily_avg.items()]
    daily_frame = daily_avg.rename("mm_hari").reset_index()
    daily_frame.columns = ["tanggal", "mm_hari"]
    daily_frame["tanggal"] = pd.to_datetime(daily_frame["tanggal"])
    monthly = daily_frame.groupby(daily_frame["tanggal"].dt.to_period("M"))["mm_hari"].mean()
    monthly_series = [{"periode": str(idx), "mm_hari": safe_float(val)} for idx, val in monthly.items()]
    yearly = daily_frame.groupby(daily_frame["tanggal"].dt.year)["mm_hari"].mean()
    yearly_series = [{"periode": str(int(idx)), "mm_hari": safe_float(val)} for idx, val in yearly.items()]

    return {
        "global": {
            "periode_mulai": matrix.index.min(),
            "periode_selesai": matrix.index.max(),
            "jumlah_hari": int(len(matrix)),
            "jumlah_pos_matriks": int(len(ids)),
            "jumlah_pos_sumber": int(len(all_stations)),
            "pos_sumber_tidak_masuk_matriks": int((~all_stations["ada_di_matriks"].astype(bool)).sum()),
            "nilai_asli": n_original,
            "nilai_imputasi": n_imputed,
            "celah_aktif_tersisa": n_active_missing,
            "sel_di_luar_rentang_aktif": n_outside,
            "cakupan_pengisian_persen": round(coverage, 2),
            "rata_rata_curah_hujan_mm_hari": safe_float(np.nanmean(all_values)),
            "maksimum_curah_hujan_mm": max_value,
            "tanggal_maksimum": max_date,
            "pos_maksimum_id": max_station_id,
            "pos_maksimum_nama": str(max_station.get("nama_pos", "")),
            "wilayah_maksimum": str(max_station.get("kabupaten_kota", "")),
        },
        "rankings": rankings,
        "station_rankings": sorted(station_rows, key=lambda x: x["rata_rata_pos_mm_hari"], reverse=True),
        "trends": {"daily": daily_series, "monthly": monthly_series, "yearly": yearly_series},
    }


@app.get("/api/summary")
@app.get("/summary")
def summary():
    return JSONResponse(content=build_summary())


@app.get("/api/map")
@app.get("/map")
def map_data(
    start: Optional[str] = None,
    end: Optional[str] = None,
    region: Optional[str] = None,
):
    start_date, end_date = parse_window(start, end)
    matrix, flags, active_stations, _ = load_data()
    selected_matrix = matrix.loc[start_date:end_date]
    selected_flags = flags.loc[start_date:end_date]
    if selected_matrix.empty:
        raise HTTPException(status_code=404, detail="Tidak ada data untuk tanggal tersebut.")

    station_lookup = active_stations.set_index("pos_hujan_id").to_dict(orient="index")
    stations_out = []
    region_accum = {}

    for sid in selected_matrix.columns:
        station = station_lookup.get(sid)
        if not station:
            continue
        region_name = str(station.get("kabupaten_kota", "Belum dipetakan"))
        region_code = str(station.get("kode_bps", ""))
        if region and region not in (region_name, region_code, "all"):
            continue

        values = []
        observed = []
        for day in selected_matrix.index:
            value = selected_matrix.at[day, sid]
            flag = int(selected_flags.at[day, sid]) if not pd.isna(selected_flags.at[day, sid]) else 2
            val = safe_float(value)
            status = status_for(flag, value)
            values.append({
                "tanggal": str(day),
                "nilai_mm": val,
                "status_kode": flag,
                "status": status,
                "klasifikasi": classify_rainfall(val) if val is not None else status,
            })
            if val is not None:
                observed.append(val)

        mean_value = float(np.mean(observed)) if observed else None
        max_value = float(np.max(observed)) if observed else None
        imputed_n = sum(1 for x in values if x["status_kode"] == 1 and x["nilai_mm"] is not None)
        original_n = sum(1 for x in values if x["status_kode"] == 0 and x["nilai_mm"] is not None)
        missing_n = sum(1 for x in values if x["status_kode"] == 2)
        item = {
            "pos_hujan_id": sid,
            "nama_pos": str(station.get("nama_pos", sid)),
            "latitude": safe_float(station.get("latitude")),
            "longitude": safe_float(station.get("longitude")),
            "elevasi_m": safe_float(station.get("elevasi_m")),
            "kode_bps": region_code,
            "kabupaten_kota": region_name,
            "rata_rata_rentang_mm_hari": mean_value,
            "maksimum_rentang_mm_hari": max_value,
            "klasifikasi_rata_rata": classify_rainfall(mean_value),
            "jumlah_data_asli": original_n,
            "jumlah_data_imputasi": imputed_n,
            "jumlah_celah": missing_n,
            "values": values,
        }
        stations_out.append(item)
        if region_name not in region_accum:
            region_accum[region_name] = {"kode_bps": region_code, "values": [], "stations": set(), "max": None, "max_pos": None, "max_date": None}
        region_accum[region_name]["stations"].add(sid)
        region_accum[region_name]["values"].extend(observed)
        for v in values:
            if v["nilai_mm"] is not None and (region_accum[region_name]["max"] is None or v["nilai_mm"] > region_accum[region_name]["max"]):
                region_accum[region_name]["max"] = v["nilai_mm"]
                region_accum[region_name]["max_pos"] = item["nama_pos"]
                region_accum[region_name]["max_date"] = v["tanggal"]

    region_stats = []
    for name, data in region_accum.items():
        vals = data["values"]
        mean = float(np.mean(vals)) if vals else None
        region_stats.append({
            "kabupaten_kota": name,
            "kode_bps": data["kode_bps"],
            "rata_rata_mm_hari": mean,
            "klasifikasi": classify_rainfall(mean),
            "maksimum_mm_hari": data["max"],
            "tanggal_maksimum": data["max_date"],
            "pos_maksimum": data["max_pos"],
            "jumlah_pos": len(data["stations"]),
        })
    return {
        "start": start_date,
        "end": end_date,
        "jumlah_hari": len(selected_matrix),
        "stations": stations_out,
        "regions": region_stats,
    }


@app.get("/api/station/{station_id}")
@app.get("/station/{station_id}")
def station_detail(station_id: str, start: Optional[str] = None, end: Optional[str] = None):
    start_date, end_date = parse_window(start, end)
    matrix, flags, active_stations, _ = load_data()
    if station_id not in matrix.columns:
        raise HTTPException(status_code=404, detail="ID pos tidak ditemukan pada matriks hasil imputasi.")
    station = active_stations[active_stations["pos_hujan_id"] == station_id]
    if station.empty:
        raise HTTPException(status_code=404, detail="Metadata pos tidak ditemukan.")
    station = station.iloc[0].to_dict()
    selected_matrix = matrix.loc[start_date:end_date, station_id]
    selected_flags = flags.loc[start_date:end_date, station_id]
    values = []
    for day, value in selected_matrix.items():
        flag = int(selected_flags.loc[day])
        val = safe_float(value)
        values.append({"tanggal": str(day), "nilai_mm": val, "status": status_for(flag, value), "status_kode": flag, "klasifikasi": classify_rainfall(val) if val is not None else status_for(flag, value)})
    return {"station": station, "values": values}


# Vercel's Python runtime serves this ASGI application. For local development:
# uvicorn api.index:app --reload

# Serve the same frontend locally; on Vercel static files are served by @vercel/static.
# Guard the mount because Vercel packages public assets as a separate static build.
PUBLIC_DIR = BASE_DIR / "public"
if PUBLIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="public")
