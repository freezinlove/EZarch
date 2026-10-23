# 工具、项目与安装副本

skill 保存说明、代码和随库资源。项目资料、项目脚本和生成成果使用用户选定的项目目录；文件夹结构、命名和成果组合由任务决定。

`storage.output_path(path, allow_tool_write=False)` 解析真实路径，包括可解析的符号链接和 Windows junction，识别误写当前 EZarch 安装目录或开发仓库。Drawing/Canvas 保存、CAD 转换与预览、文件 inspect、Blender 输出和常规 CLI 输出已接入；原生库、自写脚本和外部软件不受此保护。维护任务可显式传入允许参数，或仅为该进程设置 `EZARCH_ALLOW_TOOL_WRITES=1`。它不移动旧文件，也不代表操作系统沙箱。

环境位置与复用见 [环境](environment.md)。切换位置只改变后续工具准备位置，不移动用户项目或清理旧环境。

开发仓库保留 tests、tools、发布配置；安装包只包含逐文件声明的运行内容。维护人员可运行仓库的 `tools/git_boundary.py staged` 查看暂存内容，或 `install` 显式启用 pre-commit/pre-push。已有 hooks 配置不会被覆盖。检查体积、项目目录、未声明媒体及新增维护区外路径；公开合成图纸可在仓库 `.ezarch-public-files.json` 中逐路径声明。push 检查整个新增提交范围，因此中途加入后删除的文件仍可见。它无法判断全部私人内容，未启用或绕过 hook 时不提供保护；ZIP 用户不需要 Git。
