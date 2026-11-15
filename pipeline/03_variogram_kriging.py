#!/usr/bin/env python3
"""03 变差函数 + 普通克里金 + 块体模型（gstlearn 3D，Tom's Gully TGP Au）。

输入 processed/assay_3d.csv（e,n,z 局部米，au g/t）
输出 estimate/blockmodel.csv（规则体元，含克里金品位）
关键坑（见 geo3d 收官 07_gst3d_close.py）：
  - 三维空间须 gst.setDefaultSpace(gst.SpaceRN.create(3))，勿用 defineDefaultSpaceRnT
  - X/Y/Z 三坐标均为 ELoc.X + locatorIndex 0/1/2；变量为 ELoc.Z
"""
import os
import numpy as np
import pandas as pd
import gstlearn as gst

OUT = os.path.join(os.path.dirname(__file__), "..", "processed")
EST = os.path.join(os.path.dirname(__file__), "..", "estimate")
TOP_CUT = 30.0          # Au 顶切 g/t（压制 433 g/t 离群）
BLOCK = (10.0, 10.0, 5.0)  # 体元 (dE, dN, dZ) 米


def main():
    a = pd.read_csv(os.path.join(OUT, "assay_3d.csv"))
    a = a[a.au > 0].copy()
    n0 = len(a)
    a["au_cut"] = a.au.clip(upper=TOP_CUT)
    print("Au 样点: %d, 顶切后 max=%.1f (原始 max=%.1f)" % (n0, a.au_cut.max(), a.au.max()))
    print("顶切影响样点数:", int((a.au > TOP_CUT).sum()))

    # ---- gstlearn 三维空间 ----
    gst.setDefaultSpace(gst.SpaceRN.create(3))
    db = gst.Db.fromTL(pd.DataFrame({"X": a.e, "Y": a.n, "Z": a.z, "AU": a.au_cut}))
    for nm, i in (("X", 0), ("Y", 1), ("Z", 2)):
        db.setLocator(nm, gst.ELoc.X, i)
    db.setLocator("AU", gst.ELoc.Z, 0)
    print("db: ndim=%d nsample=%d" % (db.getNDim(), db.getNSample()))

    # ---- 实验变差函数（3D 空间维数）----
    vp = gst.VarioParam.createFromSpaceDimension(nlag=12, dlag=25.0, toldis=0.5)
    print("VarioParam: ndim=%d nDir=%d" % (vp.getNDim(), vp.getNDir()))
    va = gst.Vario(vp)
    va.compute(db=db)

    # 打印主方向实验变差
    for idir in range(min(vp.getNDir(), 3)):
        hs, gs = [], []
        for il in range(12):
            try:
                hs.append(va.getHh(idir=idir, ilag=il))
                gs.append(va.getGg(idir=idir, ilag=il))
            except Exception:
                hs.append(np.nan); gs.append(np.nan)
        print("  dir%d h=%s" % (idir, ['%.0f' % h if np.isfinite(h) else 'nan' for h in hs]))
        print("  dir%d g=%s" % (idir, ['%.3f' % g if np.isfinite(g) else 'nan' for g in gs]))

    # ---- 模型拟合 ----
    mo = gst.Model.createFromVario(va)
    fitted = False
    for lab, f in [("fit(va)", lambda: mo.fit(va)),
                   ("model_auto_fit", lambda: gst.model_auto_fit(va, mo))]:
        try:
            r = f()
            fitted = True
            print("model %s OK ret=%r" % (lab, r))
            break
        except Exception as e:
            print("model %s -> %s" % (lab, str(e)[:120]))
    if not fitted:
        # 手工球状结构：块金 + 球状（水平 150m / 垂直 20m）
        mo = gst.Model.createFromParam(gst.ECov.SPHERICAL, ranges=[150., 150., 20.], sill=1.0, flagRange=True)
        mo.addCovFromParam(gst.ECov.NUGGET, sill=0.1)
        print("model 手工球状(块金0.1+球状150/150/20,sill1.0)")
    print(str(mo))

    # ---- 块体网格 ----
    x0 = a.e.min() - BLOCK[0]; x1 = a.e.max() + BLOCK[0]
    y0 = a.n.min() - BLOCK[1]; y1 = a.n.max() + BLOCK[1]
    z0 = a.z.min() - BLOCK[2]; z1 = a.z.max() + BLOCK[2]
    nx = int(np.ceil((x1 - x0) / BLOCK[0]))
    ny = int(np.ceil((y1 - y0) / BLOCK[1]))
    nz = int(np.ceil((z1 - z0) / BLOCK[2]))
    grid = gst.DbGrid.create(nx=[nx, ny, nz], dx=list(BLOCK), x0=[x0, y0, z0])
    print("块体网格: %d x %d x %d = %d 体元" % (nx, ny, nz, grid.getNSample()))

    neigh = gst.NeighMoving.create(True, 8, 40.0)  # 每个体元最多 8 样、搜索半径自适应(最小40m)
    try:
        gst.kriging(db, grid, mo, neigh)
        print("kriging OK")
    except Exception as e:
        print("NeighMoving 失败(%s)，回退 NeighUnique" % str(e)[:80])
        gst.kriging(db, grid, mo, gst.NeighUnique.create())

    # ---- 提取结果 ----
    names = [str(n) for n in grid.getAllNames()]
    print("grid cols:", names)
    def col(name):
        try:
            return np.asarray(grid.getArray(name), float)
        except Exception:
            try:
                return np.asarray(grid[name], float)
            except Exception:
                return None
    est = None
    for n in names:
        ln = n.lower()
        if "estim" in ln and est is None:
            est = col(n)
    if est is None:
        # 变量名为 AU，估计列可能叫 "Kriging.AU.estim"
        for n in names:
            a_col = col(n)
            if a_col is not None and np.isfinite(a_col).any():
                print("  candidate", n, "mean=%.3f" % np.nanmean(a_col))
    print("估计列 finite 比例:", float(np.mean(np.isfinite(est))) if est is not None else "N/A")

    # 体元中心坐标
    gx = x0 + (np.arange(nx) + 0.5) * BLOCK[0]
    gy = y0 + (np.arange(ny) + 0.5) * BLOCK[1]
    gz = z0 + (np.arange(nz) + 0.5) * BLOCK[2]
    GX, GY, GZ = np.meshgrid(gx, gy, gz, indexing="ij")
    df = pd.DataFrame({"x": GX.ravel(), "y": GY.ravel(), "z": GZ.ravel()})
    if est is not None:
        df["au_ok"] = est
    df = df[np.isfinite(df.get("au_ok", pd.Series([1.0] * len(df))))].reset_index(drop=True)
    os.makedirs(EST, exist_ok=True)
    df.to_csv(os.path.join(EST, "blockmodel.csv"), index=False)
    print("块体模型落盘: estimate/blockmodel.csv (%d 行)" % len(df))
    print("估计品位: min=%.3f max=%.3f mean=%.3f g/t" % (df.au_ok.min(), df.au_ok.max(), df.au_ok.mean()))

    # ---- 交叉验证 ----
    try:
        gst.xvalid(db, mo, neigh)
        xnames = [str(n) for n in db.getAllNames()]
        for n in xnames:
            if "xvalid" in n.lower() and "esterr" in n.lower():
                xe = col(n)
                me = np.nanmean(xe)
                xest = a.au_cut.values - xe
                corr = np.corrcoef(a.au_cut.values, xest)[0, 1]
                print("交叉验证: mean_err=%.4f corr=%.3f" % (me, corr))
                break
    except Exception as e:
        print("交叉验证失败:", str(e)[:120])


if __name__ == "__main__":
    main()
