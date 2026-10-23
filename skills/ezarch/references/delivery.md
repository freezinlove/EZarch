# 指定文件的转换、合订与打包

`ezarch.delivery` 操作调用者明确选择的文件，不扫描项目挑选“最终版”，不规定交付格式或成果组合。

- `convert_many(items,previous=(),retries=0,timeout=180)`：每项含 source、target，可选 version 和 repair。复用现有 ODA 转换器，每个文件单独隔离、超时和返回 ready/failed；失败不阻断其他文件。previous 可传入上次返回值，只有输入摘要、输出摘要和转换选项仍一致才复用成功结果。既有目标不覆盖，改动源文件后需选新目标或由调用者明确处理旧文件；重试最多三次，可选，不自动更换格式。结果是转换状态，不能证明设计或商业 CAD 显示正确。
- `combine_pdfs(items,output,bookmarks=())`：按顺序合订，items 可为路径或含 file、pages 的对象，页码从 1 开始。书签是 `(标题, 输出页码)`；保留所选页面尺寸，不统一缩放。无有效页或输入失败不留下半成品。原 PDF 的跨文件内部链接及复杂表单并非此接口的完整移植范围。
- `collect_outputs(items,output)`：items 为归档相对名称到实际文件的映射，只将所选文件放入 ZIP，保留中文名称，返回来源和摘要。拒绝路径逃逸、重名及覆盖已有 ZIP；不自动加入项目资料、字体或日志。

CLI `delivery convert <items.json> [--previous <上次结果.json>]`、`delivery combine <items.json> --out <PDF>`、`delivery collect <items.json> --out <ZIP>` 只是这些独立操作的文件入口。直接 Python 调用可以沿用现有项目的数据结构，无需建立此 JSON。
