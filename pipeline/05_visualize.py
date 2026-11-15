#!/usr/bin/env python3
"""05 三维地质建模（岩性体元）+ 可视化（pyvista VTU + 截图）。

产出：
  model/lithology.vti       TGDDH 岩性体元（最近邻归属）
  model/blockmodel.vti      Au 克里金块体模型（含品位）
  model/drillholes_tgddh.vtp 岩性孔轨迹
  model/drillholes_tgp.vtp  Au 样点
  output/*.png              截图
"""
import os
import numpy as np
import pandas as pd
import pyvista as pv

pv.OFF_SCREEN = True
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

OUT = os.path.join(os.path.dirname(__file__), "..", "processed")
EST = os.path.join(os.path.dirname(__file__), "..", "estimate")
MOD = os.path.join(os.path.dirname(__file__), "..", "model")
FIG = os.path.join(os.path.dirname(__file__), "..", "output")

# 岩性归一化（公司内部码 -> 大组，保守解释）
LITH_GROUPS = {
    "Sap": 0, "Cla": 0, "Pcl": 0, "Fill": 0, "Lat": 0,  # 风化/表土
    "Psl": 1, "Pm": 1, "Pph": 1, "Pshc": 1, "Pdz": 1, "Ps-3": 1, "Pgt": 1,  # 变沉积岩
    "Qtz": 2,                                             # 石英脉
}
LITH_NAMES = {0: "Regolith", 1: "Metasediment", 2: "Quartz vein"}


def build_lithology_voxel():
    df = pd.read_csv(os.path.join(OUT, "lithology_3d.csv"))
    df = df[df.lith1.notna()].copy()
    df["group"] = df.lith1.map(lambda c: LITH_GROUPS.get(str(c).strip(), 1))
    pts = df[["em", "nm", "zm"]].values
    val = df.group.values
    # 体元范围（用样段中点）
    x0, x1 = pts[:, 0].min() - 10, pts[:, 0].max() + 10
    y0, y1 = pts[:, 1].min() - 10, pts[:, 1].max() + 10
    z0, z1 = pts[:, 2].min() - 5, pts[:, 2].max() + 5
    d = 20.0
    nx = int(np.ceil((x1 - x0) / d)); ny = int(np.ceil((y1 - y0) / d)); nz = int(np.ceil((z1 - z0) / d))
    grid = np.full((nx, ny, nz), -1, dtype=int)
    # 最近邻归属（欧氏 3D，逐点）
    gx = x0 + (np.arange(nx) + 0.5) * d
    gy = y0 + (np.arange(ny) + 0.5) * d
    gz = z0 + (np.arange(nz) + 0.5) * d
    GX, GY, GZ = np.meshgrid(gx, gy, gz, indexing="ij")
    GC = np.stack([GX.ravel(), GY.ravel(), GZ.ravel()], axis=1)
    from scipy.spatial import cKDTree
    tree = cKDTree(pts)
    _, idx = tree.query(GC, k=1)
    grid = val[idx].reshape((nx, ny, nz))
    img = pv.ImageData(dimensions=(nx + 1, ny + 1, nz + 1), spacing=(d, d, d), origin=(x0, y0, z0))
    img.cell_data["lithology"] = grid.ravel(order="F")
    os.makedirs(MOD, exist_ok=True)
    img.save(os.path.join(MOD, "lithology.vti"))
    print("岩性体元: %d×%d×%d=%d, 组=%s" % (nx, ny, nz, img.n_cells, LITH_NAMES))
    return img


def build_blockmodel_vtu():
    bm = pd.read_csv(os.path.join(EST, "blockmodel.csv"))
    d = (10.0, 10.0, 5.0)
    x0, y0, z0 = bm.x.min(), bm.y.min(), bm.z.min()
    nx = int(round((bm.x.max() - x0) / d[0])) + 1
    ny = int(round((bm.y.max() - y0) / d[1])) + 1
    nz = int(round((bm.z.max() - z0) / d[2])) + 1
    arr = np.full((nx, ny, nz), np.nan)
    for _, r in bm.iterrows():
        i = int(round((r.x - x0) / d[0])); j = int(round((r.y - y0) / d[1])); k = int(round((r.z - z0) / d[2]))
        if 0 <= i < nx and 0 <= j < ny and 0 <= k < nz:
            arr[i, j, k] = r.au_ok
    img = pv.ImageData(dimensions=(nx + 1, ny + 1, nz + 1), spacing=d, origin=(x0, y0, z0))
    img.cell_data["au_gpt"] = arr.ravel(order="F")
    img = img.threshold([0.01, np.nanmax(arr)], scalars="au_gpt") if np.nanmax(arr) > 0.01 else img
    img.save(os.path.join(MOD, "blockmodel.vtu"))
    print("Au 块体模型 VTU: 体元 %d (>=0.01 g/t)" % img.n_cells)
    return img


def build_drillholes():
    # TGDDH 轨迹
    traj_df = pd.read_csv(os.path.join(OUT, "lithology_3d.csv"))
    lines = []
    for hid, g in traj_df.groupby("hole_id"):
        pts = []
        for _, r in g.iterrows():
            pts.append([r.e1, r.n1, r.z1]); pts.append([r.e2, r.n2, r.z2])
        if pts:
            lines.append(np.array(pts))
    poly = pv.lines_from_points(np.vstack(lines))
    poly.save(os.path.join(MOD, "drillholes_tgddh.vtp"))
    print("TGDDH 孔轨迹: %d 孔" % traj_df.hole_id.nunique())
    # TGP 样点
    a = pd.read_csv(os.path.join(OUT, "assay_3d.csv"))
    pts = a[["e", "n", "z"]].values
    pc = pv.PolyData(pts)
    pc["au_gpt"] = a.au.values
    pc.save(os.path.join(MOD, "drillholes_tgp.vtp"))
    print("TGP Au 样点: %d" % len(pts))
    return poly, pc


def screenshot(img_lith, img_block, poly, pc):
    os.makedirs(FIG, exist_ok=True)
    pl = pv.Plotter(window_size=(900, 700), off_screen=True)
    pl.add_mesh(img_block, scalars="au_gpt", cmap="viridis", clim=[0.1, 5.0], opacity=1.0, show_scalar_bar=True, scalar_bar_args={"title": "Au g/t"})
    pl.add_mesh(pc, color="red", point_size=8.0, render_points_as_spheres=True)
    pl.add_mesh(poly, color="grey", line_width=2)
    pl.camera_position = "iso"
    pl.screenshot(os.path.join(FIG, "tomgully_blockmodel.png"))
    pl.close()

    pl = pv.Plotter(window_size=(900, 700), off_screen=True)
    pl.add_mesh(img_lith, scalars="lithology", cmap="tab10", clim=[0, 2], show_edges=False,
                show_scalar_bar=True, scalar_bar_args={"title": "lithology", "n_labels": 3})
    pl.add_mesh(poly, color="black", line_width=1.5)
    pl.camera_position = "iso"
    pl.screenshot(os.path.join(FIG, "tomgully_lithology.png"))
    pl.close()
    print("截图: output/tomgully_blockmodel.png + tomgully_lithology.png")


if __name__ == "__main__":
    img_lith = build_lithology_voxel()
    img_block = build_blockmodel_vtu()
    poly, pc = build_drillholes()
    screenshot(img_lith, img_block, poly, pc)
    print("[OK] 三维模型 + 截图完成")
