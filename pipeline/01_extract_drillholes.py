#!/usr/bin/env python3
"""01 数据治理：解析 NTGS 报告 txt + 抽取 DIP001 钻孔数据 -> processed/ 干净 CSV。

选区：Tom's Gully 金矿（Mt Bundy 项目，北领地 Pine Creek）。
源（全程只读）：
  - source/MLN1058_2010_A_*.txt  (Tom's Gully 2010, Crocodile Gold) -> 岩性/孔口/测斜
  - 1006/processed/hanking_mtbundy_28352_v2.gpkg (DIP001) -> TGP 孔 Au 化验/孔口/测斜
输出：processed/*.csv（只写本目录）
"""
import os, re, sys
import numpy as np
import pandas as pd
import sqlite3

SRC = os.path.join(os.path.dirname(__file__), "..", "source")
OUT = os.path.join(os.path.dirname(__file__), "..", "processed")
GPKG = "/mnt/e/01_Projects/001_projects_Intelligent Mining/1006/processed/hanking_mtbundy_28352_v2.gpkg"

# Tom's Gully 参考点（WGS84）与 MGA94/52 原点
TG_LON, TG_LAT = 131.5608, -12.831
TG_E0, TG_N0 = 777000.0, 8579000.0  # MGA94/52 局部原点（约 TG 中心）


def parse_ntgs_txt(path):
    """解析 NTGS 标准 txt（DS3/SL3：列名可能嵌在元数据行尾部，随后紧跟数据行）。

    策略：定位含列名标记(BHID/Hole_ID/hole_id)的那一行，取其标记及其后（若前一字段为
    DataSet/Prospect 则一并纳入）到最后一个非空字段作为表头；其后非空行为数据行。
    """
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    marker = re.compile(r"(?i)^(bhid|hole_id|holeid|hist_holeid)$")
    header = None
    data_rows = []
    for ln in lines:
        s = ln.rstrip("\n").rstrip("\r")
        if not s.strip():
            continue
        cols = [c.strip() for c in s.split("\t")]
        if header is None:
            # 真正的数据表头行含 DataSet/Prospect 数据集名列；H1000 等元数据行不含
            if "DataSet" not in cols and "Prospect" not in cols:
                continue
            mi = next((i for i, c in enumerate(cols) if marker.match(c)), None)
            if mi is None:
                continue
            start = mi - 1 if mi >= 1 and cols[mi - 1].lower() in ("dataset", "prospect") else mi
            while cols and not cols[-1]:
                cols.pop()
            header = cols[start:]
            continue
        data_rows.append(cols)
    if header is None:
        raise RuntimeError(f"未找到表头: {path}")
    ncol = len(header)
    arr = [(r + [""] * ncol)[:ncol] for r in data_rows]
    df = pd.DataFrame(arr, columns=header)
    df = df.replace(r"^\s*$", np.nan, regex=True)
    return df


def num(s):
    return pd.to_numeric(s, errors="coerce")


def main():
    os.makedirs(OUT, exist_ok=True)

    # ---------- 1. MLN1058：岩性 / 孔口 / 测斜 ----------
    lith = parse_ntgs_txt(os.path.join(SRC, "MLN1058_2010_A_04_Lithology.txt"))
    collar = parse_ntgs_txt(os.path.join(SRC, "MLN1058_2010_A_03_DrillCollars.txt"))
    surv = parse_ntgs_txt(os.path.join(SRC, "MLN1058_2010_A_05_DownholeSurvey.txt"))

    print("== MLN1058 解析 ==")
    print("  lithology cols:", list(lith.columns))
    print("  lithology rows:", len(lith))
    print("  collar cols:", list(collar.columns))
    print("  collar rows:", len(collar))
    print("  survey cols:", list(surv.columns))
    print("  survey rows:", len(surv))

    # 岩性：规范列
    lf = pd.DataFrame()
    lf["hole_id"] = lith["BHID"].astype(str)
    lf["depth_from"] = num(lith["FROM"])
    lf["depth_to"] = num(lith["TO"])
    lf["lith1"] = lith["Lith1"].astype(str)
    lf["lith1_text"] = lith["LITH1_TXTR"].astype(str)
    lf["lith2"] = lith["Lith2"].astype(str)
    lf["lith2_text"] = lith["LITH2_TXTR"].astype(str)
    if "Sulp1" in lith.columns:
        lf["sulp1"] = lith["Sulp1"].astype(str)
        lf["sulp1_pct"] = num(lith["Sulp1_pct"])
    lf.to_csv(os.path.join(OUT, "lithology_mln1058.csv"), index=False)

    # 孔口：MGA94/52
    cf = pd.DataFrame()
    cf["hole_id"] = collar["Hole_ID"].astype(str)
    cf["east_mga94"] = num(collar["MGA_East"])
    cf["north_mga94"] = num(collar["MGA_North"])
    cf["rl_mga94"] = num(collar["MGA_RL"])
    cf["east_amg84"] = num(collar["AMG_East"])
    cf["north_amg84"] = num(collar["AMG_North"])
    cf["rl_amg84"] = num(collar["AMG_RL"])
    cf["max_depth"] = num(collar["Max_Depth"])
    cf.to_csv(os.path.join(OUT, "collar_mln1058.csv"), index=False)

    # 测斜：Dip / Azimuth（优先 Corrected_Azi，缺失回退 Mag_Azimuth，再 Orig_Azimuth）
    sf = pd.DataFrame()
    sf["hole_id"] = surv["hole_id"].astype(str)
    sf["depth"] = num(surv["survey_depth"])
    sf["dip"] = num(surv["Dip"])
    az = num(surv["Corrected_Azi"])
    az_mag = num(surv["Mag_Azimuth"])
    az_orig = num(surv["Orig_Azimuth"])
    sf["azimuth"] = az.fillna(az_mag).fillna(az_orig)
    sf.to_csv(os.path.join(OUT, "survey_mln1058.csv"), index=False)

    # ---------- 2. DIP001：TGP 孔 Au 化验 ----------
    con = sqlite3.connect(GPKG)
    cur = con.cursor()
    # 化验（Au 已>0，TGP 孔）
    qa = """SELECT HoleName, CAST(Depth_From AS REAL) d_from, CAST(Depth_To AS REAL) d_to,
            CAST(Longitude AS REAL) lon, CAST(Latitude AS REAL) lat,
            CAST(Au_ppm AS REAL) au
            FROM assay_nth_governed
            WHERE HoleName LIKE 'TGP%' AND CAST(Au_ppm AS REAL)>0"""
    ass = pd.read_sql(qa, con)
    print("\n== DIP001 TGP 化验 ==")
    print("  rows:", len(ass), " holes:", ass.HoleName.nunique())
    print("  Au min/med/max:", ass.au.min(), ass.au.median(), ass.au.max())

    # 孔口（geom 为 GPKG blob，用 hex 解析太脆弱，改用 survey_governed 的 Easting/Northing + 回退经纬度）
    # survey_governed 有 Easting/Northing/Elevation（MGA?），先查 TGP 测斜
    sq = """SELECT DrillholeId, HoleRef, SurveyType, CAST(Depth AS REAL) depth,
            CAST(Azimuth AS REAL) az, CAST(Dip AS REAL) dip, CoordSys,
            CAST(Easting AS REAL) east, CAST(Northing AS REAL) north, CAST(Elevation AS REAL) elev
            FROM survey_governed WHERE (DrillholeId LIKE 'TGP%' OR HoleRef LIKE 'TGP%')"""
    sv = pd.read_sql(sq, con)
    print("\n== DIP001 TGP 测斜 ==")
    print("  rows:", len(sv), " holes:", sv.DrillholeId.nunique())
    print("  CoordSys 取值:", sv.CoordSys.unique()[:10])
    print("  east/north 非空:", sv.east.notna().sum(), sv.north.notna().sum())
    con.close()

    ass.to_csv(os.path.join(OUT, "assay_tgp_dip001.csv"), index=False)
    sv.to_csv(os.path.join(OUT, "survey_tgp_dip001.csv"), index=False)

    print("\n[OK] 输出:", os.listdir(OUT))


if __name__ == "__main__":
    main()
