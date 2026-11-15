#!/usr/bin/env python3
"""02 孔斜校正：最小曲率法（MLN1058 TGDDH）+ 直线法（DIP001 TGP）-> 三维坐标。

输出：
  processed/lithology_3d.csv    TGDDH 岩性样段真三维（from/to 中点 + 端点）
  processed/assay_3d.csv        TGP  Au 样点真三维（中点）
  processed/collar_3d.csv       合并孔口三维
坐标框架：局部笛卡尔（米），原点 MGA94/52 E=777000, N=8579000, Z=0（高程 RL 向上）。
"""
import os
import numpy as np
import pandas as pd

OUT = os.path.join(os.path.dirname(__file__), "..", "processed")
SRC = os.path.join(os.path.dirname(__file__), "..", "source")

E0, N0 = 777000.0, 8579000.0  # 局部原点


def uv(dip_deg, az_deg):
    """钻孔方向单位向量（Dip 向下为负，Azimuth 自北顺时针）。返回 (dE, dN, dZ)。"""
    theta = np.radians(abs(dip_deg))          # 与水平面夹角
    phi = np.radians(az_deg)
    return (np.cos(theta) * np.sin(phi),     # East
            np.cos(theta) * np.cos(phi),     # North
            -np.sin(theta))                  # Z 向下为负


def min_curvature(collar, stations):
    """最小曲率法。collar=(E,N,RL)；stations=sorted[(depth,dip,az)]。
    返回 np.array [[depth,E,N,Z]] 轨迹点（含 collar 起点）。"""
    pts = [[0.0, collar[0], collar[1], collar[2]]]
    E, N, Z = collar
    for i in range(len(stations) - 1):
        d1, dip1, az1 = stations[i]
        d2, dip2, az2 = stations[i + 1]
        dd = d2 - d1
        if dd <= 0:
            continue
        v1 = np.array(uv(dip1, az1))
        v2 = np.array(uv(dip2, az2))
        cosb = float(np.clip(np.dot(v1, v2), -1.0, 1.0))
        beta = np.arccos(cosb)
        if beta < 1e-6:
            rfc = 1.0
        else:
            rfc = (2.0 / beta) * np.tan(beta / 2.0)
        dE = 0.5 * dd * (v1[0] + v2[0]) * rfc
        dN = 0.5 * dd * (v1[1] + v2[1]) * rfc
        dZ = 0.5 * dd * (v1[2] + v2[2]) * rfc
        E += dE; N += dN; Z += dZ
        pts.append([d2, E, N, Z])
    return np.array(pts)


def interp_traj(pts, depth):
    """沿轨迹按深度线性插值 -> (E,N,Z)。pts 已按 depth 升序。"""
    if depth <= pts[0, 0]:
        return pts[0, 1], pts[0, 2], pts[0, 3]
    for k in range(len(pts) - 1):
        if pts[k, 0] <= depth <= pts[k + 1, 0]:
            d0, d1 = pts[k, 0], pts[k + 1, 0]
            if d1 == d0:
                return pts[k, 1], pts[k, 2], pts[k, 3]
            f = (depth - d0) / (d1 - d0)
            return (pts[k, 1] + f * (pts[k + 1, 1] - pts[k, 1]),
                    pts[k, 2] + f * (pts[k + 1, 2] - pts[k, 2]),
                    pts[k, 3] + f * (pts[k + 1, 3] - pts[k, 3]))
    return pts[-1, 1], pts[-1, 2], pts[-1, 3]


def desurvey_tgddh():
    """MLN1058 TGDDH 34 孔：最小曲率 -> 岩性样段 3D。"""
    collar = pd.read_csv(os.path.join(OUT, "collar_mln1058.csv"))
    survey = pd.read_csv(os.path.join(OUT, "survey_mln1058.csv"))
    lith = pd.read_csv(os.path.join(OUT, "lithology_mln1058.csv"))
    lith = lith[lith.hole_id.notna()].copy()
    rows = []
    traj_store = {}
    for hid, g in collar.groupby("hole_id"):
        e, n, rl = g.east_mga94.iloc[0], g.north_mga94.iloc[0], g.rl_mga94.iloc[0]
        e -= E0; n -= N0
        sv = survey[survey.hole_id == hid].dropna(subset=["depth", "dip", "azimuth"])
        sv = sv.sort_values("depth")
        if len(sv) < 2:
            # 单站：直线法
            dip = sv.dip.iloc[0] if len(sv) else -90.0
            az = sv.azimuth.iloc[0] if len(sv) else 0.0
            pts = np.array([[0.0, e, n, rl]])
            v = np.array(uv(dip, az))
            maxd = g.max_depth.iloc[0] if pd.notna(g.max_depth.iloc[0]) else 200.0
            pts = np.vstack([pts, [maxd, e + v[0] * maxd, n + v[1] * maxd, rl + v[2] * maxd]])
        else:
            stations = list(zip(sv.depth, sv.dip, sv.azimuth))
            pts = min_curvature((e, n, rl), stations)
        traj_store[hid] = pts
    for hid, pts in traj_store.items():
        lg = lith[lith.hole_id == hid]
        if not len(lg):
            continue
        for _, r in lg.iterrows():
            d1, d2 = r.depth_from, r.depth_to
            if pd.isna(d1) or pd.isna(d2):
                continue
            e1, n1, z1 = interp_traj(pts, d1)
            e2, n2, z2 = interp_traj(pts, d2)
            rows.append(dict(hole_id=hid, depth_from=d1, depth_to=d2,
                             e1=e1, n1=n1, z1=z1, e2=e2, n2=n2, z2=z2,
                             em=(e1 + e2) / 2, nm=(n1 + n2) / 2, zm=(z1 + z2) / 2,
                             lith1=r.lith1, lith1_text=r.lith1_text,
                             lith2=r.lith2, lith2_text=r.lith2_text))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "lithology_3d.csv"), index=False)
    return df, traj_store


def desurvey_tgp():
    """DIP001 TGP 41 孔（单站直线法）：Au 样点 3D，孔口 RL 用 DEM 采样。"""
    import rasterio
    from pyproj import Transformer
    ass = pd.read_csv(os.path.join(OUT, "assay_tgp_dip001.csv"))
    sv = pd.read_csv(os.path.join(OUT, "survey_tgp_dip001.csv"))
    # 经纬度 -> MGA94/52
    tr = Transformer.from_crs("EPSG:4326", "EPSG:28352", always_xy=True)
    e, n = tr.transform(ass.lon.values, ass.lat.values)
    ass["e"] = e - E0
    ass["n"] = n - N0
    # DEM 表面高程（GLO-30，1 角秒）
    tiles = sorted(os.path.join(SRC, f) for f in os.listdir(SRC)
                   if f.startswith("Copernicus_DSM_COG_10_S1") and f.endswith(".tif"))
    surf = {}
    for t in tiles:
        with rasterio.open(t) as ds:
            for lon, lat, hid in zip(ass.lon, ass.lat, ass.HoleName):
                if hid in surf:
                    continue
                try:
                    r, c = ds.index(lon, lat)
                    v = ds.read(1, window=((r, r + 1), (c, c + 1)))
                    if v.size and v[0, 0] != ds.nodata:
                        surf[hid] = float(v[0, 0])
                except Exception:
                    pass
    ass["rl"] = ass.HoleName.map(surf)
    # 单站 dip/azimuth
    svm = sv[sv.HoleRef.notna()].copy()
    svm["hid"] = svm.HoleRef.astype(str)
    svm = svm.dropna(subset=["dip", "az"])
    svm = svm[["hid", "dip", "az"]].drop_duplicates("hid").set_index("hid")
    rows = []
    for _, r in ass.iterrows():
        hid = r.HoleName
        dip = svm.at[hid, "dip"] if hid in svm.index else -90.0
        az = svm.at[hid, "az"] if hid in svm.index else 0.0
        dm = (r.d_from + r.d_to) / 2.0
        v = np.array(uv(dip, az))
        rows.append(dict(hole_id=hid, depth_from=r.d_from, depth_to=r.d_to,
                         e=r.e + v[0] * dm, n=r.n + v[1] * dm,
                         z=r.rl + v[2] * dm, au=r.au, rl=r.rl))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "assay_3d.csv"), index=False)
    return df


if __name__ == "__main__":
    lith3d, traj = desurvey_tgddh()
    print("== TGDDH 岩性 3D ==")
    print("  样段数:", len(lith3d), " 孔数:", lith3d.hole_id.nunique())
    print("  Z 范围:", round(lith3d.zm.min(), 1), "->", round(lith3d.zm.max(), 1), "m(RL)")
    print("  水平范围 E:", round(lith3d.em.min(), 0), "->", round(lith3d.em.max(), 0),
          " N:", round(lith3d.nm.min(), 0), "->", round(lith3d.nm.max(), 0), "(局部米)")
    a3d = desurvey_tgp()
    print("== TGP Au 样点 3D ==")
    print("  样点数:", len(a3d), " 孔数:", a3d.hole_id.nunique())
    print("  Au>=0.1 样点数:", int((a3d.au >= 0.1).sum()), " Au>=1:", int((a3d.au >= 1).sum()))
    print("  RL 命中:", a3d.rl.notna().sum(), "/", len(a3d))
