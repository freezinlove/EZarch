# Rhino MCP 客户端配置

安装或修复用户所选客户端连接时读取；文档操作见 [Rhino 官方 MCP](rhino-mcp.md)。配置格式以实际客户端版本及其官方文档为准。

## 共同信息

从本机 `MCPConnect` 取得 **Router 绝对路径、args、目标 Rhino 版本**，使用对应系统和架构的实际文件。已有配置先备份，只合并 Rhino 条目，保留其他服务器与环境变量。配置后按客户端要求重载连接并查看工具列表。

支持通用 `mcpServers` JSON 的客户端，可将下例作为结构参考；`/absolute/path/to/rhino-mcp-router` 是待替换的路径，args 也需核对本机生成值：

```json
{
  "mcpServers": {
    "rhino": {
      "command": "/absolute/path/to/rhino-mcp-router",
      "args": ["--default-version", "8"]
    }
  }
}
```

Windows JSON 中路径使用正确转义的反斜杠，或客户端支持的正斜杠；不要把 PowerShell 的 `&`、整段 shell 命令或未拆开的参数写入 `command`。JSON、TOML、YAML 的根结构不同，不能把这一段原样粘到所有客户端。

## 选择对应客户端

| 用户使用的客户端 | 接法及验证入口 |
|---|---|
| Claude Desktop | 优先按 Rhino MCPConnect/官方 connector 指引操作；具备桌面本地 MCP 能力的客户端可启动 Router。重载后检查连接与工具，不把网页端或“仅远程 URL”入口当成本地 stdio 配置 |
| Claude Code | 按其当前 MCP 管理命令或配置接入 Router；通过会话 MCP 状态检查。MCPConnect 自动配置可用时优先复用 |
| Codex | 使用 MCPConnect 安装，或按本机版本在 MCP 设置/`config.toml` 的 `[mcp_servers.rhino]` 中合并 `command`、`args` |
| GitHub Copilot（VS Code） | 使用 Agent 模式。其配置常用 `servers` 根键而非 `mcpServers`；按 VS Code 的 MCP 配置格式填入 Router，再启用对应工具 |
| Gemini CLI | 按当前 `settings.json` 的 `mcpServers` 或客户端 MCP 管理入口配置 Router，重载并检查工具 |
| Cursor / Windsurf 等 | MCPConnect 没有对应入口时，按该客户端官方的本地 MCP 格式手动接；Windsurf/Cascade 与 Devin Local 的名称、配置已有变化，核对实际版本 |
| OpenCode | 按当前 `opencode.json[c]` 的 `mcp` 配置；本地条目使用 `type: "local"`、`command: [Router可执行文件, ...参数]`，环境变量字段是 `environment`，不是直接复制通用 `mcpServers`/`env` 结构 |
| Kimi Code CLI / VS Code | 当前 Kimi Code 支持本地 stdio MCP；CLI 可用 `/mcp-config` 新增、`/mcp` 查看。VS Code 可用齿轮 → MCP Servers。用户级/项目级 `.kimi-code/mcp.json` 的结构见官方文档；旧 kimi-cli 路径及子命令不同，先核对版本 |
| DSH（DeepSeek Harness） | 使用官方 `@deepseek-ai/dsh-mcp-client`，配置 `serverName`、`transport: stdio`、Router 的 `command` 与 `args`。按用户正在使用的 profile/overlay 加入实例，不向 Codex/Claude 的 JSON 位置写 DSH 配置 |
| 其他本地模型智能体 | 先确认宿主确实支持本地 MCP、工具调用和需要的图片输入，再使用 Router。仅有模型 API 或普通聊天页面不等同于 MCP 客户端 |

DSH/Kimi 支持 MCP 协议不等于 McNeel 提供一键接入或已在当前机器实测；普通网页/手机聊天的本地接入能力需单独核查。

## DSH 配置结构示意

DSH 使用 Cordis composition。临时 overlay 可使用以下 `insert` 补丁；将 Router 路径与参数替换为本机真实值，保存到项目工作目录，再按当前 CLI 支持的 `dsh web --patch <文件>` 加载。持久配置可能位于 `$DSH_HOME/profiles/<name>/cordis.patch.yml` 或 `$DSH_HOME/cordis.patch.yml`，先确认当前 home/profile 并合并已有补丁，不能整文件覆盖。

```yaml
- insert:
    - name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: rhino
        transport: stdio
        command: /absolute/path/to/rhino-mcp-router
        args: ['--default-version', '8']
```

连接后用返回的真实会话读取文档上下文，见 [会话识别](rhino-mcp.md#当前文档与会话)。

## 按需查询的官方资料

- McNeel：[各客户端入门](https://mcneel.github.io/RhinoAI/docs/getting-started/)、[Claude Desktop](https://mcneel.github.io/RhinoAI/docs/getting-started/connector/)、[Claude Code](https://mcneel.github.io/RhinoAI/docs/getting-started/cc-plugin/)、[Copilot](https://mcneel.github.io/RhinoAI/docs/getting-started/copilot/)、[Codex](https://mcneel.github.io/RhinoAI/docs/getting-started/codex/)、[Gemini](https://mcneel.github.io/RhinoAI/docs/getting-started/gemini/)。具体子页失效时从入门页导航，不猜测新 URL。
- [Codex MCP 配置](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [Cursor MCP](https://cursor.com/docs/mcp) · [OpenCode MCP](https://opencode.ai/docs/mcp-servers/) · [Cascade MCP（当前文档含 legacy 限制）](https://docs.devin.ai/desktop/cascade/mcp)
- Kimi：[CLI MCP](https://www.kimi.com/code/docs/kimi-code-cli/customization/mcp.html)、[VS Code MCP](https://www.kimi.com/code/docs/kimi-code-for-vscode/customization.html)
- [DeepSeek Harness 官方 MCP 客户端](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/mcp/mcp-client/README.md) · [DSH MCP overlay 与持久配置](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/guide/mcp-memory.md)
