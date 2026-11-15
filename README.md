# 三维地质建模与储量估算（开源全栈）· Tom's Gully 金矿

> 用 **0 元开源软件栈**（Python + GDAL + gstlearn + pyvista）复刻商业矿业软件
> （Leapfrog / Surpac / Datamine）的三维地质建模与资源量估算主链路。
> 选区：Tom's Gully 金矿（Mt Bundy 项目，澳大利亚北领地 Pine Creek）。
> 数据：NTGS 政府开放数据（GEMIS 公司报告 + DIP 区域钻孔库）。

**一句话结论**：环境与算力足够、数据可获取、链路已全通；基于**公开浅层**钻孔数据
估得浅层资源量级（约 1.3 万 oz @ 0.5 g/t 截止），与官方 JORC 差异主因是「政府开放数据
只有浅层、深部资源定义钻探的化验在公司报告 PDF 内」。正式储量分级需 Competent Person 签字。

**Abstract (EN)** — A zero-licence-cost open-source stack (Python + GDAL + gstlearn + pyvista)
that reproduces the core workflow of commercial 3D geological modelling and resource estimation
software (Leapfrog / Surpac / Datamine). Demo deposit: Tom's Gully, NTGS open data. Result:
~13,060 oz Au from the shallow (0–60 m) public dataset at a 0.5 g/t cut-off; the gap to the
JORC 2010 figure (~140,000 oz) is a data-coverage boundary, not a methodology gap.

---

## 一、结果速览（全部可复算，脚本见 `pipeline/`）

| 项 | 值 |
|---|---|
| 选区 | Tom's Gully（131.5608°E, −12.831°S，MGA94/52） |
| Au 样点 | 41 孔 / 584 样段（公开 DIP001，深度 0–60 m） |
| 岩性编录 | 34 孔 / 7,698 样段（MLN1058 公司报告，深至 840 m） |
| 变差函数 | gstlearn 三维球状：基台 7.76，变程 (东,北,垂)=(72.5, 18.9, 10.2) m |
| 块体模型 | 10×10×5 m 体元，普通克里金 |
| 浅层资源（0.5 g/t 截止） | 174,150 t @ 2.33 g/t ≈ **13,060 oz Au** |
| 官方 JORC 2010 | 321,000 t @ 8.9 g/t + 193,000 t @ 7.8 g/t ≈ 140,000 oz |
| SG | 2.7 t/m³（假设，待 CR2008-0104 报告提炼） |

> 注：本估算仅为**浅层公开数据**的演示性资源量级，不是全矿床储量，不构成 JORC 分级。

## 二、开源工具链（Windows + WSL 双环境）

| 层 | 包 · 版本 | 用途 |
|---|---|---|
| 数值 | numpy · scipy · pandas | 数组/统计 |
| 空间 | pyproj · shapely · pyogrio · rasterio · geopandas | 投影/矢量/栅格采样 |
| 地统 | gstlearn 1.11.1 · scikit-gstat | 变差函数、克里金 |
| 三维 | pyvista 0.49 · vtk · meshio | 体元/VTK 可视化 |

无 Leapfrog / Surpac / Datamine / Micromine / Geosoft / Vulcan / Petrel 等任何商业许可。

## 三、管线（5 步，可复跑）

```
01_extract_drillholes.py   NTGS txt 解析 + DIP001 抽取  -> processed/*.csv
02_desurvey.py             最小曲率孔斜校正            -> processed/lithology_3d.csv / assay_3d.csv
03_variogram_kriging.py    gstlearn 三维变差 + 克里金   -> estimate/blockmodel.csv
04_reserve.py              吨位×品位 + 吨-品位曲线      -> estimate/reserve_*.csv/md
05_visualize.py            岩性体元 + 块体模型 + 截图    -> model/*.vti/vtu/vtp, output/*.png
```

```bash
source ~/envs/geo3d/bin/activate
cd pipeline
for f in 01 02 03 04 05; do python3 ${f}_*.py; done
```

## 四、数据与溯源

| 数据 | 来源 | 文件 |
|---|---|---|
| 岩性/孔口/测斜 | NTGS GEMIS 公司报告 CR2010-0727（MLN1058） | `source/MLN1058_2010_A_*.txt` |
| Au 化验 | NTGS DIP001 区域钻孔库（assay_nth_governed） | `1006/processed/*.gpkg` |
| 地形 DEM | Copernicus GLO-30（1 角秒） | `source/Copernicus_DSM_COG_10_S1*.tif` |
| 官方资源 | NTGS reserves_resources（JORC） | `1006/processed/*.gpkg` |

源全程只读；本任务输出仅写 `processed/ model/ estimate/ output/ docs/ pipeline/`。

## 五、边界声明（事实，非免责）

1. **浅层边界**：Au 化验仅公开 0–60 m 浅层（TGP 孔）；深部资源定义钻探（TGDDH 至 840 m）的
   化验在公司报告 PDF、非机器可读，未纳入。
2. **空间偏移**：MLN1058「Toms Gully」岩性钻探（TGDDH）位于官方矿床点西南约 1.2 km，与
   浅层 Au（TGP）不重叠——详见 `docs/原创发现.md`。
3. **垂直基准**：公司报告孔口 RL 为本地基准（~1002 m），Copernicus DEM 为海平面高程（~16 m），
   二者相差 ~986 m，本任务已分别处理。
4. **正式分级红线**：Proved/Probable/Measured/Indicated/Inferred 须 Competent Person 签字，
   脚本不代判。

## 六、原创发现（详见 `docs/原创发现.md`）

1. 开源全栈复刻商业矿业软件主链路（0 元成本）。
2. 数据治理「静默失败」：GPKG 数值列被声明为 TEXT，`WHERE ... BETWEEN` 返回 0 行却无报错。
3. gstlearn 三维空间陷阱：`defineDefaultSpaceRnT(n)` 实建 RN(n+1)，正解 `SpaceRN.create(3)`。
4. 文件名 ≠ 真分辨率：`glo30` 实为 8 角秒（≈241 m）降采样。
5. 垂直基准 986 m 落差（本地 RL vs 海平面 DEM）。
6. 政府开放数据 vs 公司私有数据的边界（浅层 vs 深层资源）。

## 目录

```
1114.3D geological modeling and reserve estimation/
├─ pipeline/   01-05 可复跑脚本
├─ processed/  治理后干净 CSV（孔口/测斜/岩性/化验 3D）
├─ estimate/   块体模型 + 储量估算 + 吨-品位曲线
├─ model/      三维模型（.vti/.vtu/.vtp）
├─ output/     截图
├─ docs/       发布物料（掘金 / 小众软件 / GIS SE / 原创发现）
└─ source/     原始数据（只读，已在 .gitignore 中排除，不入库）
```

## 许可

本仓库的代码与文档采用 [MIT License](LICENSE)。`source/` 下的原始数据版权归 NTGS 及各报告
编制公司所有，未包含在本仓库中，请从 NTGS GEMIS 原始出处获取。
