# 工具、项目与安装副本

skill 保存说明、代码和随库资源。项目资料、项目脚本和生成成果使用用户选定的项目目录；文件夹结构、命名和成果组合由任务决定。

`storage.output_path(path, allow_tool_write=False)` 解析真实路径，包括可解析的符号链接和 Windows junction，识别误写当前 EZarch 安装目录或开发仓库。Drawing/Canvas 保存、CAD 转换与预览、文件 inspect、Blender 输出和常规 CLI 输出已接入；原生库、自写脚本和外部软件不受此保护。维护任务可显式传入允许参数，或仅为该进程设置 `EZARCH_ALLOW_TOOL_WRITES=1`。它不移动旧文件，也不代表操作系统沙箱。

环境位置与复用见 [环境](environment.md)。切换位置只改变后续工具准备位置，不移动用户项目或清理旧环境。

开发仓库保留 tests、tools、发布配置；安装包只包含逐文件声明的运行内容。维护人员可运行仓库的 `tools/git_boundary.py staged` 查看暂存内容，或 `install` 显式启用 pre-commit/pre-push。已有 hooks 配置不会被覆盖。检查体积、项目目录、未声明媒体及新增维护区外路径；公开合成图纸可在仓库 `.ezarch-public-files.json` 中逐路径声明。push 检查整个新增提交范围，因此中途加入后删除的文件仍可见。它无法判断全部私人内容，未启用或绕过 hook 时不提供保护；ZIP 用户不需要 Git。

## 使用时轻提示和更新

正式 ZIP 包含 `.ezarch-release.json`，记录版本与受管文件摘要。`scripts/run.py` 在这种安装中顺带限频检查官方 release 元数据，短超时、每天至多一次，同版提示去重，离线不阻塞作图。源码仓库不走自动替换；旧包没有安装摘要时，需由 agent 首次引导到经验证的新安装，不直接覆盖未知旧文件。

`<兼容 Python 3.12> <skill>/scripts/update.py` 是不依赖绘图库的独立入口，bootstrap 返回的 Python 可直接使用：

- `install <新安装目录> [--source <HTTPS 元数据>]` 下载校验正式包并安装到尚不存在的位置，供没有更新入口的旧包或源码复制用户由 agent 一次引导。已有安装不覆盖；依赖可按需复用或准备。AI 应说明最终使用的安装路径和重新加载状态，避免多副本混淆。

- `check <安装目录> [--force] [--source <HTTPS 元数据>]` 查询；无法联网与已是最新分别返回。
- `prepare <安装目录>` 下载校验、解包、检查文件摘要与 Python 语法，返回 prepared 记录路径；此时原安装未变。
- `activate <安装目录> --prepared <记录>` 在无工具任务使用该安装时启用。完成状态是 activated_reload_required，需让宿主重新加载 skill；不能说当前对话已热切换。
- `preferences <安装目录> --auto / --no-auto / --no-remind / --skip <版本>` 记住偏好。自动偏好允许使用期间短时后台准备，不建立常驻服务；启用由 agent 在确认当前任务已结束、允许重新加载时调用 activate。关闭应用后不保证继续准备。
- `rollback <安装目录> --backup <启用结果中的目录>` 恢复所选旧版；后续本地修改会阻止覆盖。`recover` 恢复中断的文件事务。

更新只替换旧发行清单内的文件；本地改动或新文件冲突会明确停止，未知额外文件保持原样。启用前保存备份与事务日志，失败回退；多个使用进程可并行，但启用时不能有活动使用记录。异常退出遗留锁/使用记录时，先根据 PID 确认进程已结束再清理，不盲目抢锁。依赖锁变化后，已登记的旧依赖环境不再被启动器误用，可重新 bootstrap；更新不会顺便重装大型工具。

发布端 `tools/package_skill.py --out <目录> --base-url <该版 release 下载目录>` 产生 ZIP、SHA256 和轻量元数据。仓库提供按 v版本标签发布的工作流；写好工作流不代表已在远端发布。这些是版本管理操作，不是建筑任务的制作阶段。
