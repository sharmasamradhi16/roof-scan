import uuid
import json
import asyncio
import traceback
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import requests as req_lib

from roof_estimator import (
    estimate_roof,
    recalculate_from_polygon,
    snap_polygon_to_rectangle,
)
from solar_estimator import estimate_solar

############################################################
# APP
############################################################

app = FastAPI(
    title="RoofScan API",
    description="Rooftop area + Solar ROI estimator",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

############################################################
# JOB STORE
############################################################

jobs: Dict[str, Any] = {}

############################################################
# SCHEMAS
############################################################

class EstimateRequest(BaseModel):
    lat: float = Field(..., ge=-90,  le=90)
    lon: float = Field(..., ge=-180, le=180)

class GeocodeRequest(BaseModel):
    query: str = Field(..., min_length=2)

class ReverseRequest(BaseModel):
    lat: float = Field(..., ge=-90,  le=90)
    lon: float = Field(..., ge=-180, le=180)

class SuggestRequest(BaseModel):
    query: str = Field(..., min_length=2)

class RecalculateRequest(BaseModel):
    polygon: List[List[float]] = Field(
        ..., description="[[lat,lon], ...] polygon vertices"
    )
    ref_lat: float = Field(..., ge=-90,  le=90)
    ref_lon: float = Field(..., ge=-180, le=180)

class SnapRectangleRequest(BaseModel):
    polygon: List[List[float]]
    ref_lat: float = Field(..., ge=-90,  le=90)
    ref_lon: float = Field(..., ge=-180, le=180)

class SolarRequest(BaseModel):
    lat:          float = Field(..., ge=-90,  le=90)
    lon:          float = Field(..., ge=-180, le=180)
    area_m2:      float = Field(..., gt=0)
    monthly_bill: float = Field(..., gt=0)

############################################################
# HEALTH
############################################################

@app.get("/")
def root():
    return {"status": "RoofScan API v3 running ✅"}

@app.get("/health")
def health():
    return {"status": "ok"}

############################################################
# GEOCODING — kept exactly from your working code
############################################################

def _fetch_nominatim(query):
    try:
        response = req_lib.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json",
                    "limit": 6, "addressdetails": 1},
            headers={
                "User-Agent":      "RoofScan/2.0 (rooftop-area-estimator)",
                "Accept":          "application/json",
                "Accept-Language": "en",
            },
            timeout=(3, 3.5),
        )
        response.raise_for_status()
        return response.json() if response.text.strip() else []
    except Exception:
        return []


def _fetch_photon(query):
    try:
        response = req_lib.get(
            "https://photon.komoot.io/api/",
            params={"q": query, "limit": 6, "lang": "en"},
            timeout=(3, 3.5),
        )
        response.raise_for_status()
        raw = response.json() if response.text.strip() else {}
        normalized = []
        for f in raw.get("features", []):
            props      = f.get("properties", {})
            coords_geo = f.get("geometry", {}).get("coordinates", [0, 0])
            parts      = [props.get(k) for k in
                          ["name", "street", "city", "state", "country"]
                          if props.get(k)]
            normalized.append({
                "lat":          coords_geo[1],
                "lon":          coords_geo[0],
                "display_name": ", ".join(parts),
                "address": {
                    "road":    props.get("street", ""),
                    "city":    props.get("city", ""),
                    "state":   props.get("state", ""),
                    "country": props.get("country", ""),
                },
            })
        return normalized
    except Exception:
        return []


def _fetch_open_meteo(query):
    try:
        response = req_lib.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": query, "count": 6, "language": "en"},
            timeout=(3, 3.5),
        )
        response.raise_for_status()
        body       = response.json() if response.text.strip() else {}
        normalized = []
        for it in body.get("results") or []:
            lat_g, lon_g = it.get("latitude"), it.get("longitude")
            if lat_g is None or lon_g is None:
                continue
            name    = (it.get("name") or "").strip()
            admin1  = (it.get("admin1") or "").strip()
            country = (it.get("country") or "").strip()
            display = ", ".join(p for p in (name, admin1, country) if p)
            normalized.append({
                "lat":          lat_g,
                "lon":          lon_g,
                "display_name": display,
                "address": {
                    "city":    it.get("admin2") or admin1 or "",
                    "state":   admin1,
                    "country": country,
                },
            })
        return normalized
    except Exception:
        return []


@app.post("/suggest")
def suggest(req: SuggestRequest):
    try:
        q = req.query.strip()

        # Query Nominatim and Photon CONCURRENTLY instead of the old
        # sequential waterfall (Nominatim -> wait -> Photon -> wait ->
        # Open-Meteo). The old code could take up to ~24s worst case
        # (3 providers x 8s timeout) whenever the first provider(s)
        # returned nothing. Now both run in parallel with a tight 3.5s
        # timeout each, and results are merged (deduped by proximity)
        # so we surface the best matches from both providers instead of
        # only ever seeing Photon when Nominatim happened to return
        # zero results for a query it could have partially matched.
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=2) as pool:
            nominatim_future = pool.submit(_fetch_nominatim, q)
            photon_future    = pool.submit(_fetch_photon, q)
            try:
                nominatim_data = nominatim_future.result(timeout=4)
            except Exception:
                nominatim_data = []
            try:
                photon_data = photon_future.result(timeout=4)
            except Exception:
                photon_data = []

        def _is_dup(item, existing):
            try:
                ilat, ilon = float(item["lat"]), float(item["lon"])
            except (TypeError, ValueError, KeyError):
                return False
            for e in existing:
                try:
                    elat, elon = float(e["lat"]), float(e["lon"])
                except (TypeError, ValueError, KeyError):
                    continue
                if abs(ilat - elat) < 1e-4 and abs(ilon - elon) < 1e-4:
                    return True
            return False

        data = list(nominatim_data)
        for item in photon_data:
            if not _is_dup(item, data):
                data.append(item)

        # Open-Meteo (place/city level, not great for street addresses)
        # is only used as a last-resort fallback when both real
        # geocoders returned nothing.
        if not data:
            data = _fetch_open_meteo(q)

        results = []
        for item in data:
            addr  = item.get("address", {})
            parts = []
            for key in ["building","road","neighbourhood","suburb",
                        "city","town","state","country"]:
                val = addr.get(key)
                if val and val not in parts:
                    parts.append(val)
            results.append({
                "lat":          float(item["lat"]),
                "lon":          float(item["lon"]),
                "display_name": item.get("display_name", ""),
                "short_label":  ", ".join(parts[:4]) if parts
                                else item.get("display_name", ""),
            })
        return {"results": results}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/geocode")
def geocode(req: GeocodeRequest):
    try:
        data = []
        try:
            response = req_lib.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": req.query, "format": "json",
                        "limit": 1, "addressdetails": 1},
                headers={"User-Agent": "RoofScan/2.0",
                         "Accept-Language": "en"},
                timeout=(5, 8)
            )
            data = response.json()
        except Exception:
            response = req_lib.get(
                "https://photon.komoot.io/api/",
                params={"q": req.query, "limit": 1, "lang": "en"},
                timeout=(5, 8)
            )
            raw        = response.json()
            normalized = []
            for f in raw.get("features", []):
                props      = f.get("properties", {})
                coords_geo = f.get("geometry", {}).get("coordinates", [0, 0])
                parts      = [props.get(k) for k in
                              ["name","street","city","state","country"]
                              if props.get(k)]
                normalized.append({
                    "lat":          coords_geo[1],
                    "lon":          coords_geo[0],
                    "display_name": ", ".join(parts),
                })
            data = normalized

        if not data:
            raise HTTPException(status_code=404, detail="Location not found.")

        result = data[0]
        return {
            "lat":          float(result["lat"]),
            "lon":          float(result["lon"]),
            "display_name": result.get("display_name", ""),
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reverse")
def reverse(req: ReverseRequest):
    """Turn a GPS lat/lon (e.g. from the browser's 'Use My Location'
    button) into a readable address, so the search bar can show
    something meaningful instead of raw coordinates. Best-effort only —
    the pin has already been placed by the time this is called, so a
    failure here is cosmetic and the frontend falls back to showing the
    coordinates themselves."""
    try:
        response = req_lib.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={
                "lat": req.lat, "lon": req.lon,
                "format": "json", "addressdetails": 1, "zoom": 18,
            },
            headers={"User-Agent": "RoofScan/2.0", "Accept-Language": "en"},
            timeout=(5, 8),
        )
        data = response.json()

        if not data or "error" in data:
            raise HTTPException(status_code=404, detail="No address found for this location.")

        addr  = data.get("address", {})
        parts = []
        for key in ["building", "road", "neighbourhood", "suburb",
                    "city", "town", "state", "country"]:
            val = addr.get(key)
            if val and val not in parts:
                parts.append(val)

        return {
            "lat":          req.lat,
            "lon":          req.lon,
            "display_name": data.get("display_name", ""),
            "short_label":  ", ".join(parts[:4]) if parts
                            else data.get("display_name", ""),
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/estimate")
def estimate(req: EstimateRequest):
    print(f"\nEstimate: lat={req.lat}, lon={req.lon}")
    try:
        result = estimate_roof(req.lat, req.lon)
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

############################################################
# POLYGON RECALCULATE
############################################################

@app.post("/recalculate")
def recalculate(req: RecalculateRequest):
    print(f"\nRecalculate: {len(req.polygon)} vertices")
    try:
        result = recalculate_from_polygon(
            req.polygon, req.ref_lat, req.ref_lon
        )
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

############################################################
# SNAP TO RECTANGLE
############################################################

@app.post("/snap-rectangle")
def snap_rectangle(req: SnapRectangleRequest):
    print(f"\nSnap rectangle: {len(req.polygon)} vertices")
    try:
        result = snap_polygon_to_rectangle(
            req.polygon, req.ref_lat, req.ref_lon
        )
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

############################################################
# SOLAR ESTIMATE — SSE — unchanged from your working code
############################################################

@app.post("/solar-estimate")
def solar_estimate_start(req: SolarRequest):
    job_id       = str(uuid.uuid4())
    jobs[job_id] = {
        "status":  "pending",
        "step":    0,
        "message": "Starting...",
        "result":  None,
        "error":   None,
        "req":     req,
    }
    return {"job_id": job_id, "status": "started"}


@app.get("/solar-progress/{job_id}")
async def solar_progress(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")

    job = jobs[job_id]
    req = job["req"]

    async def event_stream():
        loop           = asyncio.get_event_loop()
        progress_queue = asyncio.Queue()

        def progress_cb(step, message):
            job["step"]    = step
            job["message"] = message
            loop.call_soon_threadsafe(
                progress_queue.put_nowait,
                {"step": step, "message": message}
            )

        import concurrent.futures
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        def run_pipeline():
            try:
                result = estimate_solar(
                    lat=req.lat,
                    lon=req.lon,
                    area_m2=req.area_m2,
                    monthly_bill=req.monthly_bill,
                    progress_cb=progress_cb,
                )
                job["status"] = "done"
                job["result"] = result
                loop.call_soon_threadsafe(
                    progress_queue.put_nowait,
                    {"step": "done", "result": result}
                )
            except Exception as e:
                traceback.print_exc()
                err_msg       = str(e)
                job["status"] = "error"
                job["error"]  = err_msg
                loop.call_soon_threadsafe(
                    progress_queue.put_nowait,
                    {"step": "error", "message": err_msg}
                )

        loop.run_in_executor(executor, run_pipeline)

        while True:
            try:
                event = await asyncio.wait_for(
                    progress_queue.get(), timeout=300.0
                )
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("step") in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'step':'error','message':'Timeout'})}\n\n"
                break

        executor.shutdown(wait=False)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        }
    )
