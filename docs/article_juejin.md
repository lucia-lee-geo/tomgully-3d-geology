# 用开源 Python 栈复刻 Leapfrog：三维地质建模与储量估算全流程（0 元成本）

> 发布平台：稀土掘金 · 分类：数据工程 / 科学计算
> 配套仓库：https://github.com/lucia-lee-geo/tomgully-3d-geology （pipeline/ 五段脚本可复跑）

## 一句话

矿业里做三维地质建模和资源量估算，传统上要花几十万买 Leapfrog / Surpac / Datamine。
这篇文章证明：**用一套免费开源栈（Python + GDAL + gstlearn + pyvista），一台工作站，能跑通
同样的主链路**——从政府开放数据落地，到孔斜校正、变差函数、克里金、块体模型、吨位×品位。

我把真实矿区（澳大利亚北领地 Tom's Gully 金矿）的公开数据完整跑了一遍，把结果和踩的坑都写在这。

![Tom's Gully 块体模型（10×10×5 m，普通克里金）](https://p0-xtjj-private.juejin.cn/tos-cn-i-73owjymdk6/5c62d02a5a7448cb9f876ab5f429ae02~tplv-73owjymdk6-jj-mark-v1:0:0:0:0:5o6Y6YeR5oqA5pyv56S-5Yy6IEAgTFVDSUFMRUU=:q75.awebp?policy=eyJ2bSI6MywidWlkIjoiNDM1MTI0MjIwODgyMTA2NiJ9&rk3s=e9ecf3d6&x-orig-authkey=f32326d3454f2ac7e96d3d06cdbb035152127018&x-orig-expires=1794819553&x-orig-sign=TPfaktDfvBXbkh0csuPSjKKXYvI%3D)

## 为什么要做这件事

- 商业软件授权贵、绑定重、不可复现（点鼠标，无法审计算过程）。
- 开源栈可**脚本化、可复现、可审计**，代码即文档。
- 政府开放数据（钻孔、化验、地质图）已经足够跑通方法，缺的只是没人把这些拼起来。

## 数据从哪来

全部来自澳大利亚北领地地质调查局（NTGS）的开放平台：

| 数据 | 来源 | 格式 |
|---|---|---|
| 岩性/孔口/测斜 | GEMIS 公司勘探报告（CR2010-0727） | 制表符 txt |
| Au 化验 | DIP001 区域钻孔库 | GPKG |
| 地形 | Copernicus GLO-30 | GeoTIFF |
| 官方资源量 | NTGS reserves_resources（JORC） | GPKG |

选区是 Tom's Gully 金矿：41 孔 / 584 个 Au 样段（浅层 0–60 m），另有 34 孔 / 7,698 段岩性编录（深至 840 m）。

## 五步管线（全部脚本化）

```
01 解析 NTGS txt + 抽取 DIP001   -> 干净 CSV（孔口/测斜/岩性/化验）
02 最小曲率孔斜校正               -> 每个样段/样点的真三维坐标
03 gstlearn 三维变差 + 普通克里金 -> 块体模型（10×10×5 m）
04 吨位 = 体积 × SG；吨位×品位     -> 吨-品位曲线 + 含金量
05 pyvista 三维可视化 + 导出       -> .vti/.vtu/.vtp + 截图
```

核心代码量不大，关键在**细节**（见下面的坑）。

### 变差函数（gstlearn 三维）

```python
import gstlearn as gst
gst.setDefaultSpace(gst.SpaceRN.create(3))   # 关键：正确三维空间
db = gst.Db.fromTL(df[['X','Y','Z','AU']])
for nm, i in (('X',0),('Y',1),('Z',2)): db.setLocator(nm, gst.ELoc.X, i)
db.setLocator('AU', gst.ELoc.Z, 0)
vp = gst.VarioParam.createFromSpaceDimension(nlag=12, dlag=25.0, toldis=0.5)
va = gst.Vario(vp); va.compute(db=db)
mo = gst.Model.createFromVario(va); mo.fit(va)
gst.kriging(db, grid, mo, gst.NeighMoving.create(True, 8, 40.0))
```

拟合出球状模型：基台 7.76，变程 (东,北,垂) = (72.5, 18.9, 10.2) m——典型的窄脉、块金效应。

## 结果

| 截止品位 | 吨位 | 平均品位 | 含金 |
|---|---|---|---|
| 0.1 g/t | 419,850 t | 1.11 g/t | 15,020 oz |
| 0.5 g/t | 174,150 t | 2.33 g/t | 13,060 oz |
| 1.0 g/t | 121,500 t | 3.02 g/t | 11,792 oz |

交叉核对：官方 JORC 2010 是 32.1 万吨 @ 8.9 g/t + 19.3 万吨 @ 7.8 g/t ≈ 14 万 oz。

**我的估算比官方小一个数量级，为什么？** 这正是本文最重要的边界（见下）。

## 六个可复现的坑（原创发现）

1. **数值列被声明成 TEXT**：`WHERE Longitude BETWEEN 130.95 AND 132.25` 返回 0 行、无报错，
   `CAST(... AS REAL)` 后返回 718,345 行。静默失败最危险。
2. **gstlearn 空间陷阱**：`defineDefaultSpaceRnT(3)` 建的是 RN(4)，必须 `SpaceRN.create(3)`。
3. **文件名骗人**：`glo30` 文件实为 8 角秒（≈241 m），不是 30 m。
4. **垂直基准 986 m 落差**：矿区本地 RL≈1002 m vs 海平面 DEM≈16 m，混用会让矿体「飞天」。
5. **同名不同址**：「Toms Gully」岩性钻探在官方矿床点西南 1.2 km，与 Au 孔不重叠。
6. **开放数据边界**：政府库只有浅层老孔（0–60 m），深部资源定义钻探的化验在公司 PDF 里。

每个坑的完整证据和复现方法见 `docs/原创发现.md`。

## 边界（必须说清）

- 我的估算基于**公开浅层**数据，是方法演示 + 量级参考，不是全矿床储量。
- 正式 JORC 分级（Measured/Indicated/Inferred）须合资格人签字，**脚本不代判**。
- SG=2.7 是假设值，正式值要从公司可行性研究报告里提炼。

## 结语

开源栈能不能替代商业矿业软件？**方法上能，交付上要分场景**：初步建模、量级估算、教学、
数据治理——开源完全够用且更可审计；正式资源报告出图——仍需商业软件或合资格人把关。

代码、数据、结果全在仓库里，欢迎复现和挑错：
**https://github.com/lucia-lee-geo/tomgully-3d-geology**
