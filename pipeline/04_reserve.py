#!/usr/bin/env python3
"""04 储量估算：体元品位 × 体积 × SG -> 吨位-品位曲线，并与官方 JORC 交叉核对。

输入 estimate/blockmodel.csv（克里金品位）
输出 estimate/reserve_estimate.csv（吨位-品位曲线）+ estimate/reserve_summary.md
口径（全部留痕，可复算）：
  - 体元 10×10×5 m = 500 m³/块
  - SG = 2.7 t/m³（石英脉型金矿于变沉积岩的常规值；正式值待 CR2008-0104 报告提炼）
  - 品位 = 克里金估计，负值钳制为 0；未估计块视为贫化/无矿（不参与资源）
  - 含金量 = 吨位 × 品位 / 31.1035 (g/oz)
"""
import os
import numpy as np
import pandas as pd

EST = os.path.join(os.path.dirname(__file__), "..", "estimate")
SG = 2.7
BLOCK_VOL = 10.0 * 10.0 * 5.0          # m³
BLOCK_TON = BLOCK_VOL * SG               # 每块吨位
G_PER_OZ = 31.1035

# 官方 JORC（reserves_resources 表，已实测核对）
JORC = {
    2010: {"indicated_t": 321_000, "indicated_g": 8.9, "inferred_t": 193_000, "inferred_g": 7.8},
    2013: {"indicated_kt": 815, "indicated_g": 9.1, "inferred_kt": 250, "inferred_g": 8.7},
    2023: {"indicated_Mt": 2.3, "indicated_g": 6.3, "inferred_Mt": 0.3, "inferred_g": 6.1},
}


def main():
    bm = pd.read_csv(os.path.join(EST, "blockmodel.csv"))
    bm["au"] = bm.au_ok.clip(lower=0.0)
    print("体元数: %d, 块体积 %.0f m³, SG %.1f -> 每块 %.0f t" % (len(bm), BLOCK_VOL, SG, BLOCK_TON))

    cutoffs = [0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0, 5.0]
    rows = []
    for cut in cutoffs:
        m = bm.au >= cut
        n_blk = int(m.sum())
        ton = n_blk * BLOCK_TON
        grade = bm.au[m].mean() if n_blk else 0.0
        metal_g = ton * grade
        metal_oz = metal_g / G_PER_OZ
        rows.append(dict(cutoff_gpt=cut, blocks=n_blk, tonnage_t=ton,
                         mean_grade_gpt=round(grade, 3), metal_oz=round(metal_oz, 0)))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(EST, "reserve_estimate.csv"), index=False)
    print("\n吨位-品位曲线（浅层 TGP 数据，0-60m）：")
    print(df.to_string(index=False))

    # 交叉核对：官方 JORC 2010（与 TGP/TGDDH 同期）
    print("\n== 官方 JORC 交叉核对 ==")
    print("  2010 Indicated: 321,000 t @ 8.9 g/t = %.0f oz" % (321000 * 8.9 / G_PER_OZ))
    print("  2010 Inferred:  193,000 t @ 7.8 g/t = %.0f oz" % (193000 * 7.8 / G_PER_OZ))
    print("  2010 合计: %.0f oz" % ((321000 * 8.9 + 193000 * 7.8) / G_PER_OZ))
    print("  2023 (JORC2012): 2.3 Mt @ 6.3 g/t Indicated + 0.3 Mt @ 6.1 g/t Inferred = %.0f oz"
          % ((2.3e6 * 6.3 + 0.3e6 * 6.1) / G_PER_OZ))
    print("  本估算(0.5 g/t 截止): %.0f oz —— 仅浅层公开数据，非全矿床（见边界说明）" % df[df.cutoff_gpt == 0.5].metal_oz.iloc[0])

    # 写摘要
    md = ["# Tom's Gully 浅层资源估算摘要", "",
          "- 数据：DIP001 公开 TGP 孔 41 孔 / 584 Au 样段（深度 0-60 m）",
          "- 方法：最小曲率孔斜校正 → gstlearn 三维球状变差函数 → 普通克里金 → 10×10×5 m 体元",
          "- 变差函数：球状，基台 %.2f，变程(东,北,垂)=(%.0f, %.0f, %.0f) m" % (7.757, 72.5, 18.9, 10.2),
          "- SG=%.1f t/m³（假设，待 CR2008-0104 提炼）" % SG,
          "",
          "| 截止品位 g/t | 吨位 t | 平均品位 g/t | 含金 oz |",
          "|---|---|---|---|"]
    for _, r in df.iterrows():
        md.append("| %.1f | %.0f | %.3f | %.0f |" % (r.cutoff_gpt, r.tonnage_t, r.mean_grade_gpt, r.metal_oz))
    md += ["",
           "## 边界声明（事实，非免责）",
           "- 本估算仅基于**公开浅层** TGP 数据（0-60 m），深部资源定义钻探（TGDDH 至 840 m）的化验在",
           "  公司报告 PDF 内、非公开机器可读，未纳入本估算。",
           "- 官方 JORC（2010 约 9.2 万 oz、2023 约 47 万 oz）覆盖全矿床，量级差异主因是数据深度/覆盖边界。",
           "- 正式储量分级（Proved/Probable/Measured/Indicated/Inferred）须由 Competent Person 签字，脚本不代判。",
           ""]
    with open(os.path.join(EST, "reserve_summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("\n[OK] 输出 estimate/reserve_estimate.csv + reserve_summary.md")


if __name__ == "__main__":
    main()
