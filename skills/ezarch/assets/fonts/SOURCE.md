# Fandol 仿宋字体来源

- 字体：FandolFang-Regular.otf，版本 0.3。
- 作者：Fandol team（Clerk Ma、Jie Su）。
- 官方发布页：https://ctan.org/pkg/fandol
- 原始字体下载：https://mirrors.ctan.org/fonts/fandol/FandolFang-Regular.otf
- 许可证：GPL + GPL font exception，原文见本目录 COPYING 和上游 README。
- 下载日期：2026-10-13。

项目保留原始 OTF。另提供由源码仓库 `tools/build_font.py` 可重建的 `EZarchFang.ttf`，将 CFF 曲线转换为 TrueType 二次曲线（误差阈值 1 字体单位），并重命名为 EZarch Fang，以用于要求 TrueType 轮廓的 CAD 软件。派生字体保留上游许可与字体例外；不声称它是微软仿宋。重建脚本随源码仓库提供，可从 [对应版本的源码归档](https://github.com/freezinlove/EZarch/releases) 取得；正常使用无需重建。

默认 PDF/SVG 使用派生 TTF；数字、英文和仿宋字体不包含的单位符号使用嵌入的 Latin 字体。调用者可指定其他字体，包括原始 OTF。原始及派生字体均随 skill 分发，保留本目录 COPYING 和 README。

The derived TTF is embedded in current PDF/SVG exports and referenced by DXF. Bootstrap installs only this uniquely named font into the current user font directory; no proprietary font is installed.
