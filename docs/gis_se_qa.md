# Q: How do I build a 3D geological model and estimate mineral resources using only open-source tools?

> Platform: GIS Stack Exchange — self-answered question (methodology + reproducibility).
> Tag: `qgis` `python` `geology` `3d` `geostatistics`

## Question

Commercial mining software (Leapfrog, Surpac, Datamine, Micromine) dominates 3D geological
modelling and resource estimation, but licenses are expensive and closed. Is there a
reproducible, **fully open-source** pipeline that can take public drillhole data and produce
(a) a 3D block model and (b) a tonnage/grade (resource) estimate? What are the practical gotchas?

## Answer

Yes. A free stack — Python + GDAL + `gstlearn` + `pyvista` — covers the whole main workflow.
I verified it end-to-end on real public data (Tom's Gully gold deposit, Pine Creek, Northern
Territory, Australia; drillhole + assay data from the NTGS open-data portals).

### The five-step pipeline

1. **Ingest** — parse tabular drillhole exports (NTGS format) and read the regional borehole GPKG
   (`pyogrio`/`geopandas` for geometry, `sqlite3` for attributes).
2. **Desurvey** — compute true 3D coordinates along inclined holes with the minimum-curvature method.
3. **Variography** — fit a 3D variogram with `gstlearn`.
4. **Kriging** — ordinary kriging onto a regular block grid.
5. **Estimate** — tonnage = block volume × specific gravity; metal = tonnage × grade; build a
   tonnage-grade curve across cut-offs.

Minimal `gstlearn` 3D setup (this is where most people trip):

```python
import gstlearn as gst
gst.setDefaultSpace(gst.SpaceRN.create(3))        # NOT defineDefaultSpaceRnT(3)!
db = gst.Db.fromTL(df[['X','Y','Z','AU']])
for name, i in (('X',0), ('Y',1), ('Z',2)):
    db.setLocator(name, gst.ELoc.X, i)
db.setLocator('AU', gst.ELoc.Z, 0)
vp = gst.VarioParam.createFromSpaceDimension(nlag=12, dlag=25.0, toldis=0.5)
va = gst.Vario(vp); va.compute(db=db)
mo = gst.Model.createFromVario(va); mo.fit(va)
gst.kriging(db, grid, mo, gst.NeighMoving.create(True, 8, 40.0))
```

Result on the test deposit: spherical model, sill 7.76, ranges (E,N,vertical) = (72.5, 18.9, 10.2) m;
10×10×5 m blocks; at a 0.5 g/t cut-off the shallow public data yields ≈174 kt @ 2.33 g/t
(≈13,000 oz Au).

### Gotchas worth knowing (all reproducible)

1. **Silent TEXT columns** — numeric fields stored as TEXT return *0 rows* for a numeric
   `BETWEEN` with no error. Always `CAST(col AS REAL)`.
2. **`defineDefaultSpaceRnT(n)` builds RN(n+1)** — use `SpaceRN.create(3)` for true 3D.
3. **File name ≠ resolution** — a `glo30` DEM file was actually 8 arcsec (~241 m), not 30 m;
   read the geotransform, not the name.
4. **Vertical datum mismatch** — mine "Reduced Level" (~1002 m) vs sea-level DEM (~16 m), a
   ~986 m offset. Align vertical datums before modelling.
5. **Same name, different place** — "Toms Gully" lithology drilling sits ~1.2 km from the official
   "Tom's Gully" deposit point; always cross-check coordinates against the authoritative deposit
   record, not the project name.
6. **Open-data boundary** — the public archive only holds shallow legacy assays (0–60 m); deeper
   resource-definition assays live in company PDFs. Open tools reproduce the *method* and a
   *magnitude* estimate, not the full deposit resource.

Full scripts, data provenance and boundary statements are in the project repository
https://github.com/lucia-lee-geo/tomgully-3d-geology. Formal JORC classification still requires
a Competent Person sign-off — scripts do not replace that.
