# import requests
# import pandas as pd
# import numpy as np
# import warnings
# import math

# warnings.filterwarnings("ignore", category=RuntimeWarning)
# warnings.filterwarnings("ignore", category=FutureWarning)

# FIXED_TARIFF = 6.03
# FIXED_YEAR   = 2024

# try:
#     import torch
#     import torch.nn as nn
#     import pvlib
#     from pvlib.pvsystem import retrieve_sam
#     from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS
#     PVLIB_AVAILABLE = True
# except ImportError:
#     PVLIB_AVAILABLE = False

# SPACE_BUFFER = 0.20

# ############################################################
# # THREE PANEL SPECS
# ############################################################

# PANELS = {
#     "415W Mono PERC": {
#         "watt":          415,
#         "kwp":           0.415,
#         "area_m2":       3.0,
#         "eta":           0.205,
#         "gamma":        -0.0038,
#         "cost_per_w":    29.0,
#     },
#     "520W Mono PERC": {
#         "watt":          520,
#         "kwp":           0.520,
#         "area_m2":       3.0,
#         "eta":           0.215,
#         "gamma":        -0.0037,
#         "cost_per_w":    30.0,
#     },
#     "550W Mono PERC": {
#         "watt":          550,
#         "kwp":           0.550,
#         "area_m2":       3.0,
#         "eta":           0.2149,
#         "gamma":        -0.0034,
#         "cost_per_w":    30.0,
#     },
# }

# ############################################################
# # PROGRESS CALLBACK
# ############################################################

# def noop(step, message): pass

# ############################################################
# # FETCH DAILY WEATHER
# ############################################################

# def fetch_daily_weather(lat, lon, year=2024):
#     url = "https://power.larc.nasa.gov/api/temporal/daily/point"
#     params = {
#         "parameters": "ALLSKY_SFC_SW_DWN,T2M,WS10M,RH2M,PRECTOTCORR",
#         "community":  "RE",
#         "longitude":  lon,
#         "latitude":   lat,
#         "start":      f"{year}0101",
#         "end":        f"{year}1231",
#         "format":     "JSON",
#     }
#     response = requests.get(url, params=params, timeout=120)
#     response.raise_for_status()
#     data = response.json()
#     if "properties" not in data:
#         raise RuntimeError("NASA POWER daily API did not return expected data.")
#     p  = data["properties"]["parameter"]
#     df = pd.DataFrame({
#         "ghi":  list(p["ALLSKY_SFC_SW_DWN"].values()),
#         "temp": list(p["T2M"].values()),
#         "wind": list(p["WS10M"].values()),
#         "rh":   list(p["RH2M"].values()),
#         "rain": list(p["PRECTOTCORR"].values()),
#     })
#     df["date"]  = pd.date_range(f"{year}-01-01", periods=len(df))
#     df["month"] = df["date"].dt.month
#     df["ghi"]   = df["ghi"].clip(lower=0)
#     df["rh"]    = df["rh"].clip(lower=0, upper=100)
#     df["rain"]  = df["rain"].clip(lower=0)
#     return df

# ############################################################
# # FETCH HOURLY WEATHER
# ############################################################

# def fetch_hourly_weather(lat, lon, year=2024):
#     url = "https://power.larc.nasa.gov/api/temporal/hourly/point"
#     params = {
#         "parameters": (
#             "ALLSKY_SFC_SW_DWN,ALLSKY_SFC_SW_DNI,ALLSKY_SFC_SW_DIFF,"
#             "T2M,WS10M,RH2M,PRECTOTCORR"
#         ),
#         "community":  "RE",
#         "longitude":  lon,
#         "latitude":   lat,
#         "start":      f"{year}0101",
#         "end":        f"{year}1231",
#         "format":     "JSON",
#     }
#     response = requests.get(url, params=params, timeout=300)
#     response.raise_for_status()
#     data = response.json()
#     if "properties" not in data:
#         raise RuntimeError("NASA POWER hourly API did not return expected data.")
#     p     = data["properties"]["parameter"]
#     dates = pd.date_range(
#         start=f"{year}-01-01 00:00",
#         end=  f"{year}-12-31 23:00",
#         freq= "h"
#     )
#     def extract(key):
#         d = p[key]
#         return [
#             d[f"{dt.year}{str(dt.month).zfill(2)}"
#               f"{str(dt.day).zfill(2)}{str(dt.hour).zfill(2)}"]
#             for dt in dates
#         ]
#     df = pd.DataFrame({
#         "ghi":               extract("ALLSKY_SFC_SW_DWN"),
#         "dni":               extract("ALLSKY_SFC_SW_DNI"),
#         "dhi":               extract("ALLSKY_SFC_SW_DIFF"),
#         "temp_air":          extract("T2M"),
#         "wind_speed":        extract("WS10M"),
#         "relative_humidity": extract("RH2M"),
#         "precipitation":     extract("PRECTOTCORR"),
#     }, index=dates)
#     df["ghi"]               = df["ghi"].clip(lower=0)
#     df["dni"]               = df["dni"].clip(lower=0)
#     df["dhi"]               = df["dhi"].clip(lower=0)
#     df["relative_humidity"] = df["relative_humidity"].clip(lower=0, upper=100)
#     df["precipitation"]     = df["precipitation"].clip(lower=0)
#     return df

# ############################################################
# # L5 / L7 LOSS PIPELINE
# ############################################################

# def compute_l5_l7_losses(lat, lon, year, progress_cb=noop):
#     if not PVLIB_AVAILABLE:
#         return {
#             "l5_loss_pct":     11.0,
#             "l7_loss_pct":     14.0,
#             "daily_base":      None,
#             "monthly_summary": None,
#         }

#     torch.manual_seed(42)
#     np.random.seed(42)
#     torch.backends.cudnn.deterministic = True
#     torch.backends.cudnn.benchmark     = False

#     CAPACITY_KWP      = 100.0
#     TILT              = round(abs(lat))
#     AZIMUTH           = 180 if lat >= 0 else 0
#     TZ                = "UTC"
#     LOSS_MISMATCH     = 2.0
#     LOSS_WIRING       = 2.0
#     LOSS_DEGRADATION  = 0.5
#     LOSS_AVAILABILITY = 3.0
#     L_SYS             = 0.05
#     PVWATTS_LOSS      = 14.1
#     SOILING_BASE      = 0.5
#     SOILING_RATE      = 0.10
#     SOILING_MAX       = 6.0
#     TEMP_COEFF_L3     = 0.40

#     weather   = fetch_hourly_weather(lat, lon, year)
#     loc       = pvlib.location.Location(lat, lon, tz=TZ)
#     solar_pos = loc.get_solarposition(weather.index)

#     poa_hourly = pvlib.irradiance.get_total_irradiance(
#         surface_tilt    = TILT,
#         surface_azimuth = AZIMUTH,
#         dni             = weather["dni"],
#         ghi             = weather["ghi"],
#         dhi             = weather["dhi"],
#         solar_zenith    = solar_pos["zenith"],
#         solar_azimuth   = solar_pos["azimuth"],
#     )["poa_global"].clip(lower=0)

#     daily_ghi_psh     = weather["ghi"].resample("D").sum()      / 1000.0
#     daily_poa_psh     = poa_hourly.resample("D").sum()          / 1000.0
#     daily_rain_mm     = weather["precipitation"].resample("D").sum()
#     theoretical_yield = daily_poa_psh * CAPACITY_KWP

#     days = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
#     n    = len(days)

#     daily_base = pd.DataFrame({
#         "No":                    range(1, n + 1),
#         "Date":                  days,
#         "GHI_PSH":               daily_ghi_psh.values,
#         "POA_PSH":               daily_poa_psh.values,
#         "Theoretical_Yield_kWh": theoretical_yield.values,
#         "Rain_mm":               daily_rain_mm.values,
#     })

#     tp_sapm = TEMPERATURE_MODEL_PARAMETERS["sapm"]["open_rack_glass_glass"]
#     Tc = pvlib.temperature.sapm_cell(
#         poa_hourly, weather["temp_air"], weather["wind_speed"], **tp_sapm
#     )

#     progress_cb(3, "Running loss models (L1–L4)...")

#     # L1
#     sandia_modules    = retrieve_sam("SandiaMod")
#     module_sapm       = sandia_modules["Canadian_Solar_CS5P_220M___2009_"]
#     P_STC_sapm        = module_sapm["Impo"] * module_sapm["Vmpo"]
#     n_modules         = CAPACITY_KWP * 1000 / P_STC_sapm
#     sapm_out          = pvlib.pvsystem.sapm(poa_hourly, Tc, module_sapm)["p_mp"].clip(lower=0)
#     array_power_sapm  = sapm_out * n_modules / 1000.0
#     ideal_power_sapm  = (P_STC_sapm * poa_hourly.clip(lower=0) / 1000.0) * n_modules / 1000.0
#     daily_actual_sapm = array_power_sapm.resample("D").sum()
#     daily_ideal_sapm  = ideal_power_sapm.resample("D").sum()
#     L1_loss = np.where(daily_ideal_sapm > 0,
#                        (1 - daily_actual_sapm / daily_ideal_sapm) * 100, 0)
#     daily_base["L1_Generation_kWh"] = daily_actual_sapm.values
#     daily_base["L1_PR"]             = np.where(
#         daily_base["Theoretical_Yield_kWh"] > 0,
#         daily_actual_sapm.values / daily_base["Theoretical_Yield_kWh"].values, 0)
#     daily_base["L1_Loss_%"]         = np.round(L1_loss, 2)

#     # L2
#     cec_modules = retrieve_sam("CECMod")
#     module_cec  = cec_modules["Aavid_Solar_ASMS_235M"]
#     P_STC_cec   = module_cec["V_mp_ref"] * module_cec["I_mp_ref"]
#     n_mod_cec   = CAPACITY_KWP * 1000 / P_STC_cec
#     IL, I0, Rs, Rsh, nNsVth = pvlib.pvsystem.calcparams_cec(
#         effective_irradiance = poa_hourly,
#         temp_cell            = Tc,
#         alpha_sc             = module_cec["alpha_sc"],
#         a_ref                = module_cec["a_ref"],
#         I_L_ref              = module_cec["I_L_ref"],
#         I_o_ref              = module_cec["I_o_ref"],
#         R_sh_ref             = module_cec["R_sh_ref"],
#         R_s                  = module_cec["R_s"],
#         Adjust               = module_cec["Adjust"],
#     )
#     sd = pvlib.pvsystem.singlediode(IL, I0, Rs, Rsh, nNsVth)
#     array_power_cec  = sd["p_mp"].clip(lower=0) * n_mod_cec / 1000.0
#     ideal_power_cec  = (P_STC_cec * poa_hourly.clip(lower=0) / 1000.0) * n_mod_cec / 1000.0
#     daily_actual_cec = array_power_cec.resample("D").sum()
#     daily_ideal_cec  = ideal_power_cec.resample("D").sum()
#     L2_loss = np.where(daily_ideal_cec > 0,
#                        (1 - daily_actual_cec / daily_ideal_cec) * 100, 0)
#     daily_base["L2_Generation_kWh"] = daily_actual_cec.values
#     daily_base["L2_PR"]             = np.where(
#         daily_base["Theoretical_Yield_kWh"] > 0,
#         daily_actual_cec.values / daily_base["Theoretical_Yield_kWh"].values, 0)
#     daily_base["L2_Loss_%"]         = np.round(L2_loss, 2)

#     # L3
#     daily_cell_temp = Tc.resample("D").mean()
#     daily_rh_mean   = weather["relative_humidity"].resample("D").mean()
#     rain_flag       = (daily_rain_mm > 1.0).values
#     soiling_daily   = np.zeros(n)
#     cur_soil        = SOILING_BASE
#     for i in range(n):
#         cur_soil = (SOILING_BASE if rain_flag[i]
#                     else min(cur_soil + SOILING_RATE, SOILING_MAX))
#         soiling_daily[i] = cur_soil
#     L_temp_daily = np.clip(TEMP_COEFF_L3 * (daily_cell_temp.values - 25), 0, 15)
#     L_soil_daily = soiling_daily
#     L_hum_daily  = 0.5 + 2.0 * (daily_rh_mean.values / 100.0)
#     L_fixed      = LOSS_MISMATCH + LOSS_WIRING + LOSS_DEGRADATION + LOSS_AVAILABILITY
#     L3_loss_raw  = L_temp_daily + L_soil_daily + L_hum_daily + L_fixed
#     L3_loss      = np.clip(L3_loss_raw, 1, 35)
#     L3_gen       = daily_base["Theoretical_Yield_kWh"].values * (1 - L3_loss / 100)
#     daily_base["L3_Generation_kWh"] = np.round(L3_gen, 2)
#     daily_base["L3_PR"]             = np.round(np.where(
#         daily_base["Theoretical_Yield_kWh"].values > 0,
#         L3_gen / daily_base["Theoretical_Yield_kWh"].values, 0), 4)
#     daily_base["L3_Loss_%"]         = np.round(L3_loss, 2)
#     daily_base["Soiling_%"]         = np.round(soiling_daily, 2)
#     daily_base["Temp_Loss_%"]       = np.round(L_temp_daily, 2)
#     daily_base["Humidity_Loss_%"]   = np.round(L_hum_daily, 2)

#     # L4
#     L4_gen = daily_base["Theoretical_Yield_kWh"].values * (1 - PVWATTS_LOSS / 100)
#     daily_base["L4_Generation_kWh"] = np.round(L4_gen, 2)
#     daily_base["L4_PR"]             = np.round(np.where(
#         daily_base["Theoretical_Yield_kWh"].values > 0,
#         L4_gen / daily_base["Theoretical_Yield_kWh"].values, 0), 4)
#     daily_base["L4_Loss_%"]         = PVWATTS_LOSS

#     progress_cb(4, "Training AI loss models (L5 & L7)...")

#     # L5
#     loss_cols_L5 = ["L1_Loss_%", "L2_Loss_%", "L3_Loss_%"]
#     X_raw  = daily_base[loss_cols_L5].values.astype(np.float32)
#     X_min  = X_raw.min(axis=0, keepdims=True)
#     X_max  = X_raw.max(axis=0, keepdims=True)
#     X_norm = (X_raw - X_min) / (X_max - X_min + 1e-8)
#     X      = torch.tensor(X_norm, dtype=torch.float32)
#     day_mean_losses = X_raw.mean(axis=1)
#     lat_min_L5      = float(day_mean_losses.min())
#     lat_max_L5      = float(day_mean_losses.max())

#     class Encoder(nn.Module):
#         def __init__(self):
#             super().__init__()
#             self.net = nn.Sequential(
#                 nn.Linear(3, 16), nn.ReLU(),
#                 nn.Linear(16, 8), nn.ReLU(),
#                 nn.Linear(8, 1),  nn.Sigmoid())
#         def forward(self, x): return self.net(x)

#     class Decoder(nn.Module):
#         def __init__(self):
#             super().__init__()
#             self.net = nn.Sequential(
#                 nn.Linear(1, 8),   nn.ReLU(),
#                 nn.Linear(8, 16),  nn.ReLU(),
#                 nn.Linear(16, 3))
#         def forward(self, z): return self.net(z)

#     encoder = Encoder()
#     decoder = Decoder()
#     opt     = torch.optim.Adam(
#         list(encoder.parameters()) + list(decoder.parameters()), lr=1e-3)
#     loss_fn = nn.MSELoss()
#     for epoch in range(5000):
#         opt.zero_grad()
#         z    = encoder(X)
#         loss = loss_fn(decoder(z), X)
#         loss.backward()
#         opt.step()

#     with torch.no_grad():
#         latent_raw = encoder(X).numpy().squeeze()
#     latent_L5 = lat_min_L5 + latent_raw * (lat_max_L5 - lat_min_L5)
#     L5_gen    = daily_base["Theoretical_Yield_kWh"].values * (1 - latent_L5 / 100)
#     daily_base["L5_Generation_kWh"] = np.round(L5_gen, 2)
#     daily_base["L5_PR"]             = np.round(np.where(
#         daily_base["Theoretical_Yield_kWh"].values > 0,
#         L5_gen / daily_base["Theoretical_Yield_kWh"].values, 0), 4)
#     daily_base["L5_Loss_%"]         = np.round(latent_L5, 2)

#     # L6
#     L_soil_L6    = daily_base["Soiling_%"].values      / 100.0
#     L_temp_L6    = daily_base["Temp_Loss_%"].values    / 100.0
#     L_hum_L6     = daily_base["Humidity_Loss_%"].values / 100.0
#     L_coupled_L6 = 0.05 * L_temp_L6 * L_soil_L6
#     L_env_L6     = L_soil_L6 + L_temp_L6 + L_hum_L6 + L_coupled_L6
#     L6_loss_raw  = (L_SYS + L_env_L6) * 100
#     L6_loss      = np.clip(L6_loss_raw, 5, 35)
#     L6_gen       = daily_base["Theoretical_Yield_kWh"].values * (1 - L6_loss / 100)
#     daily_base["L6_Generation_kWh"] = np.round(L6_gen, 2)
#     daily_base["L6_PR"]             = np.round(np.where(
#         daily_base["Theoretical_Yield_kWh"].values > 0,
#         L6_gen / daily_base["Theoretical_Yield_kWh"].values, 0), 4)
#     daily_base["L6_Loss_%"]         = np.round(L6_loss, 2)

#     # L7
#     phys_raw  = np.column_stack([
#         daily_base["Soiling_%"].values      / 100.0,
#         daily_base["Temp_Loss_%"].values    / 100.0,
#         daily_base["Humidity_Loss_%"].values / 100.0,
#     ]).astype(np.float32)
#     phys_min  = phys_raw.min(axis=0, keepdims=True)
#     phys_max  = phys_raw.max(axis=0, keepdims=True)
#     phys_norm = (phys_raw - phys_min) / (phys_max - phys_min + 1e-8)
#     X_phys    = torch.tensor(phys_norm, dtype=torch.float32)
#     env_ref    = (daily_base["L6_Loss_%"].values / 100.0) - L_SYS
#     lat_min_L7 = float(np.clip(env_ref.min(), 0.001, None))
#     lat_max_L7 = float(env_ref.max())

#     class PhysicsEncoder(nn.Module):
#         def __init__(self):
#             super().__init__()
#             self.net = nn.Sequential(
#                 nn.Linear(3, 16), nn.ReLU(),
#                 nn.Linear(16, 8), nn.ReLU(),
#                 nn.Linear(8, 1),  nn.Sigmoid())
#         def forward(self, x): return self.net(x)

#     class PhysicsDecoder(nn.Module):
#         def __init__(self):
#             super().__init__()
#             self.net = nn.Sequential(
#                 nn.Linear(1, 8),   nn.ReLU(),
#                 nn.Linear(8, 16),  nn.ReLU(),
#                 nn.Linear(16, 3))
#         def forward(self, z): return self.net(z)

#     phys_enc   = PhysicsEncoder()
#     phys_dec   = PhysicsDecoder()
#     opt_L7     = torch.optim.Adam(
#         list(phys_enc.parameters()) + list(phys_dec.parameters()), lr=1e-3)
#     loss_fn_L7 = nn.MSELoss()
#     for epoch in range(5000):
#         opt_L7.zero_grad()
#         z_p     = phys_enc(X_phys)
#         loss_L7 = loss_fn_L7(phys_dec(z_p), X_phys)
#         loss_L7.backward()
#         opt_L7.step()

#     with torch.no_grad():
#         latent_raw_L7 = phys_enc(X_phys).numpy().squeeze()
#     latent_env_L7 = lat_min_L7 + latent_raw_L7 * (lat_max_L7 - lat_min_L7)
#     L7_loss       = np.clip((latent_env_L7 + L_SYS) * 100, 1, 35)
#     L7_gen        = daily_base["Theoretical_Yield_kWh"].values * (1 - L7_loss / 100)
#     daily_base["L7_Generation_kWh"] = np.round(L7_gen, 2)
#     daily_base["L7_PR"]             = np.round(np.where(
#         daily_base["Theoretical_Yield_kWh"].values > 0,
#         L7_gen / daily_base["Theoretical_Yield_kWh"].values, 0), 4)
#     daily_base["L7_Loss_%"]         = np.round(L7_loss, 2)

#     daily_base["Month_num"] = pd.to_datetime(daily_base["Date"]).dt.month
#     daily_base["Month"]     = pd.to_datetime(daily_base["Date"]).dt.strftime("%b")
#     monthly_summary = daily_base.groupby(["Month_num", "Month"]).agg(
#         Avg_GHI_PSH   = ("GHI_PSH",           "mean"),
#         Avg_POA_PSH   = ("POA_PSH",           "mean"),
#         Avg_Soiling   = ("Soiling_%",         "mean"),
#         Avg_Temp_Loss = ("Temp_Loss_%",       "mean"),
#         Avg_Humidity  = ("Humidity_Loss_%",   "mean"),
#         Avg_L5_Loss   = ("L5_Loss_%",         "mean"),
#         Avg_L7_Loss   = ("L7_Loss_%",         "mean"),
#         L5_Gen_MWh    = ("L5_Generation_kWh", lambda x: x.sum() / 1000),
#         L7_Gen_MWh    = ("L7_Generation_kWh", lambda x: x.sum() / 1000),
#     ).reset_index(level=0, drop=True)

#     return {
#         "l5_loss_pct":     float(daily_base["L5_Loss_%"].mean()),
#         "l7_loss_pct":     float(daily_base["L7_Loss_%"].mean()),
#         "daily_base":      daily_base,
#         "monthly_summary": monthly_summary,
#     }

# ############################################################
# # SIZING HELPER
# ############################################################

# def size_system(required_kwp, available_area_m2, panel_kwp, panel_area_m2):
#     required_panels = math.ceil(required_kwp / panel_kwp)
#     usable_area     = available_area_m2 * (1 - SPACE_BUFFER)
#     max_panels      = int(usable_area / panel_area_m2)
#     if max_panels <= 0:
#         return {
#             "required_panels":  required_panels,
#             "usable_area":      round(usable_area, 2),
#             "max_panels":       0,
#             "final_panels":     0,
#             "final_kwp":        0.0,
#             "area_constrained": True,
#             "area_ok":          False,
#             "area_used_m2":     0.0,
#         }
#     area_constrained = required_panels > max_panels
#     final_panels     = min(required_panels, max_panels)
#     final_kwp        = round(final_panels * panel_kwp, 3)
#     area_used_m2     = round(final_panels * panel_area_m2, 2)
#     return {
#         "required_panels":  required_panels,
#         "usable_area":      round(usable_area, 2),
#         "max_panels":       max_panels,
#         "final_panels":     final_panels,
#         "final_kwp":        final_kwp,
#         "area_constrained": area_constrained,
#         "area_ok":          True,
#         "area_used_m2":     area_used_m2,
#     }

# ############################################################
# # COMPUTE RESULTS FOR ONE PANEL TYPE
# ############################################################

# def compute_panel_results(
#     panel_name, panel_spec,
#     monthly_units, tariff,
#     L5_loss_pct, L7_loss_pct,
#     weather, days_in_month,
#     area_m2
# ):
#     # ─────────────────────────────────────────────────────
#     # FIX: PR removed from energy calculation.
#     # L5/L7 losses are the sole derating factors.
#     # The system is sized so that AFTER applying losses the
#     # net generation meets user demand — no double-derate.
#     # ─────────────────────────────────────────────────────

#     eta      = panel_spec["eta"]
#     gamma    = panel_spec["gamma"]
#     kwp      = panel_spec["kwp"]
#     area_m2p = panel_spec["area_m2"]
#     cpw      = panel_spec["cost_per_w"]
#     watt     = panel_spec["watt"]

#     # Step 1 — compute per-kWp energy using panel characteristics only
#     # (no PR multiplier — losses are handled entirely by L5/L7)
#     temp_factor  = np.clip(1 + gamma * (weather["temp"] - 25), 0.7, 1.0)
#     panel_factor = eta / 0.20
#     e_panel      = weather["ghi"] * temp_factor * panel_factor   # <-- PR removed

#     monthly_e = e_panel.groupby(weather["month"]).mean()
#     monthly_e = monthly_e.mul(days_in_month, fill_value=0)

#     # Use the peak month (highest GHI month) for sizing
#     peak_monthly_energy = float(monthly_e.max())

#     panel_results = {}
#     for loss_label, loss_pct in [("L5", L5_loss_pct), ("L7", L7_loss_pct)]:
#         loss_frac = loss_pct / 100.0

#         # ── SIZING ──────────────────────────────────────────────────────
#         # Inflate required gross output so that AFTER losses the user's
#         # demand is exactly met.  This is the correct industry approach:
#         #
#         #   required_gross = user_demand / (1 - loss_fraction)
#         #   ideal_kwp      = required_gross / peak_monthly_energy_per_kwp
#         # ────────────────────────────────────────────────────────────────
#         gross_needed = monthly_units / (1 - loss_frac)   # inflate for losses
#         ideal_kwp    = gross_needed / peak_monthly_energy
#         sz           = size_system(ideal_kwp, area_m2, kwp, area_m2p)

#         sys_kwp  = sz["final_kwp"]
#         n_panels = sz["final_panels"]

#         # ── GENERATION ──────────────────────────────────────────────────
#         # Apply L5/L7 loss ONCE to get realistic net generation.
#         # Because we already upsized for this loss above, the net output
#         # should closely match (or fill) the user's monthly demand.
#         # ────────────────────────────────────────────────────────────────
#         gen_net = sys_kwp * monthly_e.values * (1 - loss_frac)

#         avg_gen_mon = float(gen_net.mean())
#         ann_gen     = float(gen_net.sum())
#         sys_cost    = sys_kwp * 1000 * cpw
#         sav_mon     = avg_gen_mon * tariff
#         sav_ann     = sav_mon * 12
#         payback     = sys_cost / sav_ann if sav_ann > 0 else 0
#         coverage    = (avg_gen_mon / monthly_units) * 100 if monthly_units > 0 else 0

#         panel_results[loss_label] = {
#             "n_panels":        n_panels,
#             "sys_kwp":         round(sys_kwp, 3),
#             "sys_cost":        round(sys_cost),
#             "loss_pct":        round(loss_pct, 2),
#             "avg_gen_mon":     round(avg_gen_mon),
#             "ann_gen":         round(ann_gen),
#             "sav_mon":         round(sav_mon),
#             "sav_ann":         round(sav_ann),
#             "payback":         round(payback, 2),
#             "coverage":        round(coverage, 1),
#             "area_constrained":sz["area_constrained"],
#             "area_ok":         sz["area_ok"],
#             "usable_area":     sz["usable_area"],
#             "area_used_m2":    sz["area_used_m2"],
#             "monthly_gen":     [round(v) for v in gen_net.tolist()],
#             "monthly_savings": [round(v * tariff) for v in gen_net.tolist()],
#         }

#     return {
#         "panel_name": panel_name,
#         "specs": {
#             "watt":          watt,
#             "kwp":           kwp,
#             "area_m2":       area_m2p,
#             "efficiency_pct":round(eta * 100, 2),
#             "temp_coeff":    round(gamma * 100, 2),
#             "cost_per_w":    cpw,
#         },
#         "L5": panel_results["L5"],
#         "L7": panel_results["L7"],
#     }

# ############################################################
# # MAIN CALLABLE
# ############################################################

# def estimate_solar(lat: float, lon: float, area_m2: float,
#                    monthly_bill: float, progress_cb=noop) -> dict:
#     year   = FIXED_YEAR
#     tariff = FIXED_TARIFF

#     monthly_units = monthly_bill / tariff
#     annual_units  = monthly_units * 12
#     daily_units   = monthly_units / 30.44

#     # Step 1 — daily weather
#     progress_cb(1, "Fetching daily weather data...")
#     weather = fetch_daily_weather(lat, lon, year)

#     days_in_month = weather.groupby("month")["date"].count().rename("days_in_month")

#     # ── PR REMOVED ──────────────────────────────────────────────────────
#     # Previously PR = 0.75 was applied in compute_panel_results which
#     # caused a double-derate: GHI was already reduced by PR AND THEN
#     # further reduced by L5/L7 losses.  Since L5/L7 already encode all
#     # real-world losses (soiling, temperature, wiring, availability…),
#     # PR is now set to 1.0 (i.e. not used).  The loss-compensated sizing
#     # (gross_needed = demand / (1 - loss)) guarantees that after losses
#     # the net generation still meets user demand.
#     # ────────────────────────────────────────────────────────────────────

#     # Step 2 — hourly + L1-L7
#     progress_cb(2, "Fetching hourly weather data...")
#     loss_result  = compute_l5_l7_losses(lat, lon, year, progress_cb)
#     L5_loss_pct  = loss_result["l5_loss_pct"]
#     L7_loss_pct  = loss_result["l7_loss_pct"]

#     # Step 5 — sizing for all 3 panels
#     progress_cb(5, "Calculating solar sizing & ROI...")

#     panel_comparisons = []
#     for panel_name, panel_spec in PANELS.items():
#         result = compute_panel_results(
#             panel_name    = panel_name,
#             panel_spec    = panel_spec,
#             monthly_units = monthly_units,
#             tariff        = tariff,
#             L5_loss_pct   = L5_loss_pct,
#             L7_loss_pct   = L7_loss_pct,
#             weather       = weather,
#             days_in_month = days_in_month,
#             area_m2       = area_m2,
#             # PR argument removed — no longer passed
#         )
#         panel_comparisons.append(result)

#     month_names_list = ["Jan","Feb","Mar","Apr","May","Jun",
#                         "Jul","Aug","Sep","Oct","Nov","Dec"]

#     return {
#         "status":        "success",
#         "lat":           lat,
#         "lon":           lon,
#         "area_m2":       area_m2,
#         "monthly_bill":  monthly_bill,
#         "monthly_units": round(monthly_units, 2),
#         "annual_units":  round(annual_units, 2),
#         "daily_units":   round(daily_units, 2),
#         "tariff":        tariff,
#         "months":        month_names_list,
#         "panels":        panel_comparisons,
#         "subsidy_note":  "Payback period is calculated WITHOUT government subsidy. Actual payback will be shorter once subsidy is applied.",
#     }

import requests
import pandas as pd
import numpy as np
import warnings
import math

warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

FIXED_TARIFF = 6.03
FIXED_YEAR   = 2024

try:
    import torch
    import torch.nn as nn
    import pvlib
    from pvlib.pvsystem import retrieve_sam
    from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS
    PVLIB_AVAILABLE = True
except ImportError:
    PVLIB_AVAILABLE = False

SPACE_BUFFER = 0.20

############################################################
# THREE PANEL SPECS
############################################################

PANELS = {
    "415W Mono PERC": {
        "watt":          415,
        "kwp":           0.415,
        "area_m2":       3.0,
        "eta":           0.205,
        "gamma":        -0.0038,
        "cost_per_w":    29.0,
    },
    "520W Mono PERC": {
        "watt":          520,
        "kwp":           0.520,
        "area_m2":       3.0,
        "eta":           0.215,
        "gamma":        -0.0037,
        "cost_per_w":    30.0,
    },
    "550W Mono PERC": {
        "watt":          550,
        "kwp":           0.550,
        "area_m2":       3.0,
        "eta":           0.2149,
        "gamma":        -0.0034,
        "cost_per_w":    30.0,
    },
}

############################################################
# PROGRESS CALLBACK
############################################################

def noop(step, message): pass

############################################################
# FETCH DAILY WEATHER
############################################################

def fetch_daily_weather(lat, lon, year=2024):
    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {
        "parameters": "ALLSKY_SFC_SW_DWN,T2M,WS10M,RH2M,PRECTOTCORR",
        "community":  "RE",
        "longitude":  lon,
        "latitude":   lat,
        "start":      f"{year}0101",
        "end":        f"{year}1231",
        "format":     "JSON",
    }
    response = requests.get(url, params=params, timeout=120)
    response.raise_for_status()
    data = response.json()
    if "properties" not in data:
        raise RuntimeError("NASA POWER daily API did not return expected data.")
    p  = data["properties"]["parameter"]
    df = pd.DataFrame({
        "ghi":  list(p["ALLSKY_SFC_SW_DWN"].values()),
        "temp": list(p["T2M"].values()),
        "wind": list(p["WS10M"].values()),
        "rh":   list(p["RH2M"].values()),
        "rain": list(p["PRECTOTCORR"].values()),
    })
    df["date"]  = pd.date_range(f"{year}-01-01", periods=len(df))
    df["month"] = df["date"].dt.month
    df["ghi"]   = df["ghi"].clip(lower=0)
    df["rh"]    = df["rh"].clip(lower=0, upper=100)
    df["rain"]  = df["rain"].clip(lower=0)
    return df

############################################################
# FETCH HOURLY WEATHER
############################################################

def fetch_hourly_weather(lat, lon, year=2024):
    url = "https://power.larc.nasa.gov/api/temporal/hourly/point"
    params = {
        "parameters": (
            "ALLSKY_SFC_SW_DWN,ALLSKY_SFC_SW_DNI,ALLSKY_SFC_SW_DIFF,"
            "T2M,WS10M,RH2M,PRECTOTCORR"
        ),
        "community":  "RE",
        "longitude":  lon,
        "latitude":   lat,
        "start":      f"{year}0101",
        "end":        f"{year}1231",
        "format":     "JSON",
    }
    response = requests.get(url, params=params, timeout=300)
    response.raise_for_status()
    data = response.json()
    if "properties" not in data:
        raise RuntimeError("NASA POWER hourly API did not return expected data.")
    p     = data["properties"]["parameter"]
    dates = pd.date_range(
        start=f"{year}-01-01 00:00",
        end=  f"{year}-12-31 23:00",
        freq= "h"
    )
    def extract(key):
        d = p[key]
        return [
            d[f"{dt.year}{str(dt.month).zfill(2)}"
              f"{str(dt.day).zfill(2)}{str(dt.hour).zfill(2)}"]
            for dt in dates
        ]
    df = pd.DataFrame({
        "ghi":               extract("ALLSKY_SFC_SW_DWN"),
        "dni":               extract("ALLSKY_SFC_SW_DNI"),
        "dhi":               extract("ALLSKY_SFC_SW_DIFF"),
        "temp_air":          extract("T2M"),
        "wind_speed":        extract("WS10M"),
        "relative_humidity": extract("RH2M"),
        "precipitation":     extract("PRECTOTCORR"),
    }, index=dates)
    df["ghi"]               = df["ghi"].clip(lower=0)
    df["dni"]               = df["dni"].clip(lower=0)
    df["dhi"]               = df["dhi"].clip(lower=0)
    df["relative_humidity"] = df["relative_humidity"].clip(lower=0, upper=100)
    df["precipitation"]     = df["precipitation"].clip(lower=0)
    return df

############################################################
# L5 / L7 LOSS PIPELINE
############################################################

def compute_l5_l7_losses(lat, lon, year, progress_cb=noop):
    if not PVLIB_AVAILABLE:
        return {
            "l5_loss_pct":     11.0,
            "l7_loss_pct":     14.0,
            "daily_base":      None,
            "monthly_summary": None,
        }

    torch.manual_seed(42)
    np.random.seed(42)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark     = False

    CAPACITY_KWP      = 100.0
    TILT              = round(abs(lat))
    AZIMUTH           = 180 if lat >= 0 else 0
    TZ                = "UTC"
    LOSS_MISMATCH     = 2.0
    LOSS_WIRING       = 2.0
    LOSS_DEGRADATION  = 0.5
    LOSS_AVAILABILITY = 3.0
    L_SYS             = 0.05
    PVWATTS_LOSS      = 14.1
    SOILING_BASE      = 0.5
    SOILING_RATE      = 0.10
    SOILING_MAX       = 6.0
    TEMP_COEFF_L3     = 0.40

    weather   = fetch_hourly_weather(lat, lon, year)
    loc       = pvlib.location.Location(lat, lon, tz=TZ)
    solar_pos = loc.get_solarposition(weather.index)

    poa_hourly = pvlib.irradiance.get_total_irradiance(
        surface_tilt    = TILT,
        surface_azimuth = AZIMUTH,
        dni             = weather["dni"],
        ghi             = weather["ghi"],
        dhi             = weather["dhi"],
        solar_zenith    = solar_pos["zenith"],
        solar_azimuth   = solar_pos["azimuth"],
    )["poa_global"].clip(lower=0)

    daily_ghi_psh     = weather["ghi"].resample("D").sum()      / 1000.0
    daily_poa_psh     = poa_hourly.resample("D").sum()          / 1000.0
    daily_rain_mm     = weather["precipitation"].resample("D").sum()
    theoretical_yield = daily_poa_psh * CAPACITY_KWP

    days = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
    n    = len(days)

    daily_base = pd.DataFrame({
        "No":                    range(1, n + 1),
        "Date":                  days,
        "GHI_PSH":               daily_ghi_psh.values,
        "POA_PSH":               daily_poa_psh.values,
        "Theoretical_Yield_kWh": theoretical_yield.values,
        "Rain_mm":               daily_rain_mm.values,
    })

    tp_sapm = TEMPERATURE_MODEL_PARAMETERS["sapm"]["open_rack_glass_glass"]
    Tc = pvlib.temperature.sapm_cell(
        poa_hourly, weather["temp_air"], weather["wind_speed"], **tp_sapm
    )

    progress_cb(3, "Running loss models (L1–L4)...")

    # L1
    sandia_modules    = retrieve_sam("SandiaMod")
    module_sapm       = sandia_modules["Canadian_Solar_CS5P_220M___2009_"]
    P_STC_sapm        = module_sapm["Impo"] * module_sapm["Vmpo"]
    n_modules         = CAPACITY_KWP * 1000 / P_STC_sapm
    sapm_out          = pvlib.pvsystem.sapm(poa_hourly, Tc, module_sapm)["p_mp"].clip(lower=0)
    array_power_sapm  = sapm_out * n_modules / 1000.0
    ideal_power_sapm  = (P_STC_sapm * poa_hourly.clip(lower=0) / 1000.0) * n_modules / 1000.0
    daily_actual_sapm = array_power_sapm.resample("D").sum()
    daily_ideal_sapm  = ideal_power_sapm.resample("D").sum()
    L1_loss = np.where(daily_ideal_sapm > 0,
                       (1 - daily_actual_sapm / daily_ideal_sapm) * 100, 0)
    daily_base["L1_Generation_kWh"] = daily_actual_sapm.values
    daily_base["L1_PR"]             = np.where(
        daily_base["Theoretical_Yield_kWh"] > 0,
        daily_actual_sapm.values / daily_base["Theoretical_Yield_kWh"].values, 0)
    daily_base["L1_Loss_%"]         = np.round(L1_loss, 2)

    # L2
    cec_modules = retrieve_sam("CECMod")
    module_cec  = cec_modules["Aavid_Solar_ASMS_235M"]
    P_STC_cec   = module_cec["V_mp_ref"] * module_cec["I_mp_ref"]
    n_mod_cec   = CAPACITY_KWP * 1000 / P_STC_cec
    IL, I0, Rs, Rsh, nNsVth = pvlib.pvsystem.calcparams_cec(
        effective_irradiance = poa_hourly,
        temp_cell            = Tc,
        alpha_sc             = module_cec["alpha_sc"],
        a_ref                = module_cec["a_ref"],
        I_L_ref              = module_cec["I_L_ref"],
        I_o_ref              = module_cec["I_o_ref"],
        R_sh_ref             = module_cec["R_sh_ref"],
        R_s                  = module_cec["R_s"],
        Adjust               = module_cec["Adjust"],
    )
    sd = pvlib.pvsystem.singlediode(IL, I0, Rs, Rsh, nNsVth)
    array_power_cec  = sd["p_mp"].clip(lower=0) * n_mod_cec / 1000.0
    ideal_power_cec  = (P_STC_cec * poa_hourly.clip(lower=0) / 1000.0) * n_mod_cec / 1000.0
    daily_actual_cec = array_power_cec.resample("D").sum()
    daily_ideal_cec  = ideal_power_cec.resample("D").sum()
    L2_loss = np.where(daily_ideal_cec > 0,
                       (1 - daily_actual_cec / daily_ideal_cec) * 100, 0)
    daily_base["L2_Generation_kWh"] = daily_actual_cec.values
    daily_base["L2_PR"]             = np.where(
        daily_base["Theoretical_Yield_kWh"] > 0,
        daily_actual_cec.values / daily_base["Theoretical_Yield_kWh"].values, 0)
    daily_base["L2_Loss_%"]         = np.round(L2_loss, 2)

    # L3
    daily_cell_temp = Tc.resample("D").mean()
    daily_rh_mean   = weather["relative_humidity"].resample("D").mean()
    rain_flag       = (daily_rain_mm > 1.0).values
    soiling_daily   = np.zeros(n)
    cur_soil        = SOILING_BASE
    for i in range(n):
        cur_soil = (SOILING_BASE if rain_flag[i]
                    else min(cur_soil + SOILING_RATE, SOILING_MAX))
        soiling_daily[i] = cur_soil
    L_temp_daily = np.clip(TEMP_COEFF_L3 * (daily_cell_temp.values - 25), 0, 15)
    L_soil_daily = soiling_daily
    L_hum_daily  = 0.5 + 2.0 * (daily_rh_mean.values / 100.0)
    L_fixed      = LOSS_MISMATCH + LOSS_WIRING + LOSS_DEGRADATION + LOSS_AVAILABILITY
    L3_loss_raw  = L_temp_daily + L_soil_daily + L_hum_daily + L_fixed
    L3_loss      = np.clip(L3_loss_raw, 1, 35)
    L3_gen       = daily_base["Theoretical_Yield_kWh"].values * (1 - L3_loss / 100)
    daily_base["L3_Generation_kWh"] = np.round(L3_gen, 2)
    daily_base["L3_PR"]             = np.round(np.where(
        daily_base["Theoretical_Yield_kWh"].values > 0,
        L3_gen / daily_base["Theoretical_Yield_kWh"].values, 0), 4)
    daily_base["L3_Loss_%"]         = np.round(L3_loss, 2)
    daily_base["Soiling_%"]         = np.round(soiling_daily, 2)
    daily_base["Temp_Loss_%"]       = np.round(L_temp_daily, 2)
    daily_base["Humidity_Loss_%"]   = np.round(L_hum_daily, 2)

    # L4
    L4_gen = daily_base["Theoretical_Yield_kWh"].values * (1 - PVWATTS_LOSS / 100)
    daily_base["L4_Generation_kWh"] = np.round(L4_gen, 2)
    daily_base["L4_PR"]             = np.round(np.where(
        daily_base["Theoretical_Yield_kWh"].values > 0,
        L4_gen / daily_base["Theoretical_Yield_kWh"].values, 0), 4)
    daily_base["L4_Loss_%"]         = PVWATTS_LOSS

    progress_cb(4, "Training AI loss models (L5 & L7)...")

    # L5
    loss_cols_L5 = ["L1_Loss_%", "L2_Loss_%", "L3_Loss_%"]
    X_raw  = daily_base[loss_cols_L5].values.astype(np.float32)
    X_min  = X_raw.min(axis=0, keepdims=True)
    X_max  = X_raw.max(axis=0, keepdims=True)
    X_norm = (X_raw - X_min) / (X_max - X_min + 1e-8)
    X      = torch.tensor(X_norm, dtype=torch.float32)
    day_mean_losses = X_raw.mean(axis=1)
    lat_min_L5      = float(day_mean_losses.min())
    lat_max_L5      = float(day_mean_losses.max())

    class Encoder(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(3, 16), nn.ReLU(),
                nn.Linear(16, 8), nn.ReLU(),
                nn.Linear(8, 1),  nn.Sigmoid())
        def forward(self, x): return self.net(x)

    class Decoder(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(1, 8),   nn.ReLU(),
                nn.Linear(8, 16),  nn.ReLU(),
                nn.Linear(16, 3))
        def forward(self, z): return self.net(z)

    encoder = Encoder()
    decoder = Decoder()
    opt     = torch.optim.Adam(
        list(encoder.parameters()) + list(decoder.parameters()), lr=1e-3)
    loss_fn = nn.MSELoss()
    for epoch in range(5000):
        opt.zero_grad()
        z    = encoder(X)
        loss = loss_fn(decoder(z), X)
        loss.backward()
        opt.step()

    with torch.no_grad():
        latent_raw = encoder(X).numpy().squeeze()
    latent_L5 = lat_min_L5 + latent_raw * (lat_max_L5 - lat_min_L5)
    L5_gen    = daily_base["Theoretical_Yield_kWh"].values * (1 - latent_L5 / 100)
    daily_base["L5_Generation_kWh"] = np.round(L5_gen, 2)
    daily_base["L5_PR"]             = np.round(np.where(
        daily_base["Theoretical_Yield_kWh"].values > 0,
        L5_gen / daily_base["Theoretical_Yield_kWh"].values, 0), 4)
    daily_base["L5_Loss_%"]         = np.round(latent_L5, 2)

    # L6
    L_soil_L6    = daily_base["Soiling_%"].values      / 100.0
    L_temp_L6    = daily_base["Temp_Loss_%"].values    / 100.0
    L_hum_L6     = daily_base["Humidity_Loss_%"].values / 100.0
    L_coupled_L6 = 0.05 * L_temp_L6 * L_soil_L6
    L_env_L6     = L_soil_L6 + L_temp_L6 + L_hum_L6 + L_coupled_L6
    L6_loss_raw  = (L_SYS + L_env_L6) * 100
    L6_loss      = np.clip(L6_loss_raw, 5, 35)
    L6_gen       = daily_base["Theoretical_Yield_kWh"].values * (1 - L6_loss / 100)
    daily_base["L6_Generation_kWh"] = np.round(L6_gen, 2)
    daily_base["L6_PR"]             = np.round(np.where(
        daily_base["Theoretical_Yield_kWh"].values > 0,
        L6_gen / daily_base["Theoretical_Yield_kWh"].values, 0), 4)
    daily_base["L6_Loss_%"]         = np.round(L6_loss, 2)

    # L7
    phys_raw  = np.column_stack([
        daily_base["Soiling_%"].values      / 100.0,
        daily_base["Temp_Loss_%"].values    / 100.0,
        daily_base["Humidity_Loss_%"].values / 100.0,
    ]).astype(np.float32)
    phys_min  = phys_raw.min(axis=0, keepdims=True)
    phys_max  = phys_raw.max(axis=0, keepdims=True)
    phys_norm = (phys_raw - phys_min) / (phys_max - phys_min + 1e-8)
    X_phys    = torch.tensor(phys_norm, dtype=torch.float32)
    env_ref    = (daily_base["L6_Loss_%"].values / 100.0) - L_SYS
    lat_min_L7 = float(np.clip(env_ref.min(), 0.001, None))
    lat_max_L7 = float(env_ref.max())

    class PhysicsEncoder(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(3, 16), nn.ReLU(),
                nn.Linear(16, 8), nn.ReLU(),
                nn.Linear(8, 1),  nn.Sigmoid())
        def forward(self, x): return self.net(x)

    class PhysicsDecoder(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(1, 8),   nn.ReLU(),
                nn.Linear(8, 16),  nn.ReLU(),
                nn.Linear(16, 3))
        def forward(self, z): return self.net(z)

    phys_enc   = PhysicsEncoder()
    phys_dec   = PhysicsDecoder()
    opt_L7     = torch.optim.Adam(
        list(phys_enc.parameters()) + list(phys_dec.parameters()), lr=1e-3)
    loss_fn_L7 = nn.MSELoss()
    for epoch in range(5000):
        opt_L7.zero_grad()
        z_p     = phys_enc(X_phys)
        loss_L7 = loss_fn_L7(phys_dec(z_p), X_phys)
        loss_L7.backward()
        opt_L7.step()

    with torch.no_grad():
        latent_raw_L7 = phys_enc(X_phys).numpy().squeeze()
    latent_env_L7 = lat_min_L7 + latent_raw_L7 * (lat_max_L7 - lat_min_L7)
    L7_loss       = np.clip((latent_env_L7 + L_SYS) * 100, 1, 35)
    L7_gen        = daily_base["Theoretical_Yield_kWh"].values * (1 - L7_loss / 100)
    daily_base["L7_Generation_kWh"] = np.round(L7_gen, 2)
    daily_base["L7_PR"]             = np.round(np.where(
        daily_base["Theoretical_Yield_kWh"].values > 0,
        L7_gen / daily_base["Theoretical_Yield_kWh"].values, 0), 4)
    daily_base["L7_Loss_%"]         = np.round(L7_loss, 2)

    daily_base["Month_num"] = pd.to_datetime(daily_base["Date"]).dt.month
    daily_base["Month"]     = pd.to_datetime(daily_base["Date"]).dt.strftime("%b")
    monthly_summary = daily_base.groupby(["Month_num", "Month"]).agg(
        Avg_GHI_PSH   = ("GHI_PSH",           "mean"),
        Avg_POA_PSH   = ("POA_PSH",           "mean"),
        Avg_Soiling   = ("Soiling_%",         "mean"),
        Avg_Temp_Loss = ("Temp_Loss_%",       "mean"),
        Avg_Humidity  = ("Humidity_Loss_%",   "mean"),
        Avg_L5_Loss   = ("L5_Loss_%",         "mean"),
        Avg_L7_Loss   = ("L7_Loss_%",         "mean"),
        L5_Gen_MWh    = ("L5_Generation_kWh", lambda x: x.sum() / 1000),
        L7_Gen_MWh    = ("L7_Generation_kWh", lambda x: x.sum() / 1000),
    ).reset_index(level=0, drop=True)

    return {
        "l5_loss_pct":     float(daily_base["L5_Loss_%"].mean()),
        "l7_loss_pct":     float(daily_base["L7_Loss_%"].mean()),
        "daily_base":      daily_base,
        "monthly_summary": monthly_summary,
    }

############################################################
# SIZING HELPER
############################################################

def size_system(required_kwp, available_area_m2, panel_kwp, panel_area_m2):
    required_panels = math.ceil(required_kwp / panel_kwp)
    usable_area     = available_area_m2 * (1 - SPACE_BUFFER)
    max_panels      = int(usable_area / panel_area_m2)
    if max_panels <= 0:
        return {
            "required_panels":  required_panels,
            "usable_area":      round(usable_area, 2),
            "max_panels":       0,
            "final_panels":     0,
            "final_kwp":        0.0,
            "area_constrained": True,
            "area_ok":          False,
            "area_used_m2":     0.0,
        }
    area_constrained = required_panels > max_panels
    final_panels     = min(required_panels, max_panels)
    final_kwp        = round(final_panels * panel_kwp, 3)
    area_used_m2     = round(final_panels * panel_area_m2, 2)
    return {
        "required_panels":  required_panels,
        "usable_area":      round(usable_area, 2),
        "max_panels":       max_panels,
        "final_panels":     final_panels,
        "final_kwp":        final_kwp,
        "area_constrained": area_constrained,
        "area_ok":          True,
        "area_used_m2":     area_used_m2,
    }

############################################################
# COMPUTE RESULTS FOR ONE PANEL TYPE
############################################################

def compute_panel_results(
    panel_name, panel_spec,
    monthly_units, tariff,
    L5_loss_pct, L7_loss_pct,
    weather, days_in_month,
    area_m2
):
    # ─────────────────────────────────────────────────────
    # FIX: PR removed from energy calculation.
    # L5/L7 losses are the sole derating factors.
    # The system is sized so that AFTER applying losses the
    # net generation meets user demand — no double-derate.
    # ─────────────────────────────────────────────────────

    eta      = panel_spec["eta"]
    gamma    = panel_spec["gamma"]
    kwp      = panel_spec["kwp"]
    area_m2p = panel_spec["area_m2"]
    cpw      = panel_spec["cost_per_w"]
    watt     = panel_spec["watt"]

    # Step 1 — compute per-kWp energy using panel characteristics only
    # (no PR multiplier — losses are handled entirely by L5/L7)
    temp_factor  = np.clip(1 + gamma * (weather["temp"] - 25), 0.7, 1.0)
    panel_factor = eta / 0.20
    e_panel      = weather["ghi"] * temp_factor * panel_factor   # <-- PR removed

    monthly_e = e_panel.groupby(weather["month"]).mean()
    monthly_e = monthly_e.mul(days_in_month, fill_value=0)

    # Use the AVERAGE month for sizing so that after losses the system
    # meets demand on a typical month (~covers demand ~6 months/year).
    # Peak-month sizing produced an undersized system (coverage ~75–78%).
    # Worst-month sizing would oversize massively for monsoon months.
    # Average-month is the standard residential recommendation approach.
    avg_monthly_energy = float(monthly_e.mean())

    panel_results = {}
    for loss_label, loss_pct in [("L5", L5_loss_pct), ("L7", L7_loss_pct)]:
        loss_frac = loss_pct / 100.0

        # ── SIZING ──────────────────────────────────────────────────────
        # Inflate required gross output so that AFTER losses the user's
        # demand is exactly met on a typical (average) month.
        #
        #   required_gross = user_demand / (1 - loss_fraction)
        #   ideal_kwp      = required_gross / avg_monthly_energy_per_kwp
        #
        # This guarantees: avg_monthly_gen ≈ monthly_units after loss.
        # ────────────────────────────────────────────────────────────────
        gross_needed = monthly_units / (1 - loss_frac)   # inflate for losses
        ideal_kwp    = gross_needed / avg_monthly_energy
        sz           = size_system(ideal_kwp, area_m2, kwp, area_m2p)

        sys_kwp  = sz["final_kwp"]
        n_panels = sz["final_panels"]

        # ── GENERATION ──────────────────────────────────────────────────
        # Apply L5/L7 loss ONCE to get realistic net generation.
        # Because we already upsized for this loss above, the net output
        # should closely match (or fill) the user's monthly demand.
        # ────────────────────────────────────────────────────────────────
        gen_net = sys_kwp * monthly_e.values * (1 - loss_frac)

        avg_gen_mon = float(gen_net.mean())
        ann_gen     = float(gen_net.sum())
        sys_cost    = sys_kwp * 1000 * cpw
        sav_mon     = avg_gen_mon * tariff
        sav_ann     = sav_mon * 12
        payback     = sys_cost / sav_ann if sav_ann > 0 else 0
        coverage    = (avg_gen_mon / monthly_units) * 100 if monthly_units > 0 else 0

        panel_results[loss_label] = {
            "n_panels":        n_panels,
            "sys_kwp":         round(sys_kwp, 3),
            "sys_cost":        round(sys_cost),
            "loss_pct":        round(loss_pct, 2),
            "avg_gen_mon":     round(avg_gen_mon),
            "ann_gen":         round(ann_gen),
            "sav_mon":         round(sav_mon),
            "sav_ann":         round(sav_ann),
            "payback":         round(payback, 2),
            "coverage":        round(coverage, 1),
            "area_constrained":sz["area_constrained"],
            "area_ok":         sz["area_ok"],
            "usable_area":     sz["usable_area"],
            "area_used_m2":    sz["area_used_m2"],
            "monthly_gen":     [round(v) for v in gen_net.tolist()],
            "monthly_savings": [round(v * tariff) for v in gen_net.tolist()],
        }

    return {
        "panel_name": panel_name,
        "specs": {
            "watt":          watt,
            "kwp":           kwp,
            "area_m2":       area_m2p,
            "efficiency_pct":round(eta * 100, 2),
            "temp_coeff":    round(gamma * 100, 2),
            "cost_per_w":    cpw,
        },
        "L5": panel_results["L5"],
        "L7": panel_results["L7"],
    }

############################################################
# MAIN CALLABLE
############################################################

def estimate_solar(lat: float, lon: float, area_m2: float,
                   monthly_bill: float, progress_cb=noop) -> dict:
    year   = FIXED_YEAR
    tariff = FIXED_TARIFF

    monthly_units = monthly_bill / tariff
    annual_units  = monthly_units * 12
    daily_units   = monthly_units / 30.44

    # Step 1 — daily weather
    progress_cb(1, "Fetching daily weather data...")
    weather = fetch_daily_weather(lat, lon, year)

    days_in_month = weather.groupby("month")["date"].count().rename("days_in_month")

    # ── PR REMOVED ──────────────────────────────────────────────────────
    # Previously PR = 0.75 was applied in compute_panel_results which
    # caused a double-derate: GHI was already reduced by PR AND THEN
    # further reduced by L5/L7 losses.  Since L5/L7 already encode all
    # real-world losses (soiling, temperature, wiring, availability…),
    # PR is now set to 1.0 (i.e. not used).  The loss-compensated sizing
    # (gross_needed = demand / (1 - loss)) guarantees that after losses
    # the net generation still meets user demand.
    # ────────────────────────────────────────────────────────────────────

    # Step 2 — hourly + L1-L7
    progress_cb(2, "Fetching hourly weather data...")
    loss_result  = compute_l5_l7_losses(lat, lon, year, progress_cb)
    L5_loss_pct  = loss_result["l5_loss_pct"]
    L7_loss_pct  = loss_result["l7_loss_pct"]

    # Step 5 — sizing for all 3 panels
    progress_cb(5, "Calculating solar sizing & ROI...")

    panel_comparisons = []
    for panel_name, panel_spec in PANELS.items():
        result = compute_panel_results(
            panel_name    = panel_name,
            panel_spec    = panel_spec,
            monthly_units = monthly_units,
            tariff        = tariff,
            L5_loss_pct   = L5_loss_pct,
            L7_loss_pct   = L7_loss_pct,
            weather       = weather,
            days_in_month = days_in_month,
            area_m2       = area_m2,
            # PR argument removed — no longer passed
        )
        panel_comparisons.append(result)

    month_names_list = ["Jan","Feb","Mar","Apr","May","Jun",
                        "Jul","Aug","Sep","Oct","Nov","Dec"]

    return {
        "status":        "success",
        "lat":           lat,
        "lon":           lon,
        "area_m2":       area_m2,
        "monthly_bill":  monthly_bill,
        "monthly_units": round(monthly_units, 2),
        "annual_units":  round(annual_units, 2),
        "daily_units":   round(daily_units, 2),
        "tariff":        tariff,
        "months":        month_names_list,
        "panels":        panel_comparisons,
        "subsidy_note":  "Payback period is calculated WITHOUT government subsidy. Actual payback will be shorter once subsidy is applied.",
    }
