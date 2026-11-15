# 数据链接溯源 · IDM 可用清单（1114 三维地质建模与储量估算）

> 生成：2026-11-15 · 执行：Cline
> 原则：URL 全部取自项目台账**留痕复算**，未凭记忆编造；源全程只读；本目录为新建项目区，无覆盖动作。

## 一、溯源依据（三个留痕源，可复核）

| 源 | 相对路径（001 项目根） | 内容 |
|---|---|---|
| 0928 对账台账 | `1006/source/batch_20260928/_对账台账_20260928.csv` / `.json` | 112 行，含 `source_url` 列；其中 107 行为真 URL，去重后 18 组 |
| 直链凭证 | `1006/source/batch_20260928/_溯源凭证/ftp_links.json` | 25 条 `weblink=` 下载直链 |
| 1006 主台账 | `1006/metadata/_对账_sha256_20261006.csv` | DIP046 五个大包逐件 `sha_ok=True` 在册 |
| 下载脚本留痕 | `1006/source/batch_20260928/_溯源凭证/robust_download2.sh` | DIP001 当时使用的 GEMIS bitstream URL |

## 二、两类下载通道（关键差别，直接决定 IDM 能不能用）

| 通道 | 本机实测表现 | IDM 可用性 |
|---|---|---|
| **A** `ftp-minerals.nt.gov.au/?download&weblink=<hash>&realfilename=<fn>` | `HTTP 200` + `Content-Type: application/zip` + 精确 `Content-Length`；**Range 请求返回 206**，取回 102,400 B 真 ZIP 头 | ✅ **可直接粘贴批量下载，支持断点续传** |
| **B** `geoscience.nt.gov.au/gemis/ntgsjspui/bitstream/...` | **302 → /web/showbitstream.php → /web//bitstreams/<uuid>/download → 最终 text/html 会话页**；Range 请求仅得 302 + 265 B HTML | ❌ **不可直接粘贴**。这正是历史 `curl (56) schannel: server closed abruptly` 反复断流的根因。需装 IDM 浏览器扩展，在 GEMIS 页面点 Download 由扩展捕获会话链接 |

## 三、不需要重下的（已核验完整，别浪费带宽）

- **NTGS-DIP001.zip**：本地 1,069,757,473 B；**逐条目解压校验 16,458 / 16,458 可读、0 失败** ⇒ 重下无价值。
  - ⚠ **账注需回灌**（铁律 4）：`_对账台账_20260928` 仍记该件 `bytes=3276800、残件-不完整`，是早期中断流快照，与现件不符。
  - ⚠ **关键限制**：该包内**无任何岩性/地质编录表** —— 16,458 条目全量扫描 `lith / Interval / Geolog / Drilllog / Core / LOG` **0 命中**；`Strat_Unit_Name` 在 AOI 722,574 行中仅 20 行非空（0.00%）。重下解决不了这个缺口。
- **DIP046 五个大包**（MagMerge 36.36 GB / RadMerge 19.92 GB / MagImages 19.71 GB / MagRad 11.30 GB / RadImages 7.78 GB）：`_对账_sha256_20261006.csv` 全部 `sha_ok=True`，账实相符。

## 四、建议用 IDM 下载（见 `batch_IDM_recommended_20261115.txt`，3 条 / 31.94 GB）

| 文件 | 大小 | 优先级 | 补什么 |
|---|---:|---|---|
| `NTGS-DIP047.zip` | 8.15 GB | 重要 | 内容需先由本地 `NTGS-DIP047-Metadata.pdf`/`Release-Notes.pdf` 确认后再定，**勿盲下** |
| `DIP043.zip` | 19.19 GB | 中 | 层序/盆地格架，辅助地层三维骨架 |
| `NT-wide-gravity-grids.zip` | 4.60 GB | 中 | 深部重力约束补充（本地仅有部分重力成品） |

其余已留痕但本地无的直链（DIP008/009/010/016/017/018/020/031/046-DigitalData、NT-wide mag/rad grids）判为**低优先/非 AOI**，全部 21 条可用直链汇总在 `batch_IDM_all_directlinks_20261115.txt`；逐项状态（HTTP 码、精确字节、本地是否有、优先级、留痕出处）见 `source_links_IDM_20261115.csv`。

**全量合计 540.68 GB**；E 盘现有 1.4 TB 空闲 ⇒ 磁盘可行，但按本次实测速率（59.7 MB 耗时约 23 分钟，< 1 MB/s）**540 GB 需数天，务必按优先级分批**。

## 五、通道 B 的 302 件（不可粘贴，需浏览器+IDM 扩展）

`DIP019-Beetaloo_processed_SEGY_data.zip`、`DIP019-Kingdom_project_data.zip`、`DIP020.zip`、`DIP031.zip` 实测返回 `302`（且均为非 AOI 的 McArthur/Beetaloo 盆地），优先级低。

## 六、下载后必做验收（防 A7 假 PASS）

1. `certutil -hashfile <fn> SHA256` 与台账 sha256 逐件比对；
2. ZIP 做**全量 CRC/解压校验**（不要只看文件大小就判完整 —— 本次 DIP001 就是用 16,458 条目全读校验才定性）；
3. 入 `1114/source/` 后置只读，并回灌 manifest + 全部 ledger + 溯源清单（三本账同步）。

## 七、IDM 设置建议（针对本次实测站点特性）

- 每文件 **4–8 线程**（政府服务器易限流），失败重试 **≥10 次**、间隔 10 s；
- 关闭「下载后自动扫描」，避免数十 GB ZIP 卡队列；
- 通道 B 必须走浏览器扩展捕获；
- 建议错峰下载，先 `batch_IDM_recommended_20261115.txt` 三条（31.94 GB）验证通路，再决定是否放开 540 GB 全量。
