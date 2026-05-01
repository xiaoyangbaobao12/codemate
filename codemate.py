#!/usr/bin/env python3
"""
CodeMate - AI 编程学习助手 (CLI)
基于 DeepSeek API，提供代码解释、错误诊断、概念问答三个功能。
"""

import os
import sys
from pathlib import Path

import json

import click
import requests
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from prompts import CONCEPT_PROMPT, DEBUG_PROMPT, EXPLAIN_PROMPT

console = Console()

# ---------- API 配置 ----------
CONFIG_DIR = Path.home() / ".codemate"
CONFIG_FILE = CONFIG_DIR / "config.json"

API_KEY = os.environ.get("DEEPSEEK_API_KEY")
BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")


def load_config():
    """从配置文件加载 API Key（优先级低于环境变量）"""
    if API_KEY:
        return
    try:
        if CONFIG_FILE.exists():
            config = json.loads(CONFIG_FILE.read_text())
            return config.get("api_key")
    except Exception:
        pass
    return None


def save_config(api_key: str):
    """保存 API Key 到配置文件"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps({"api_key": api_key}))


def resolve_api_key():
    """获取 API Key：环境变量 > 配置文件 > 交互输入"""
    global API_KEY
    if API_KEY:
        return

    # 尝试配置文件
    saved = load_config()
    if saved:
        API_KEY = saved
        return

    # 首次运行，交互输入
    console.print(Panel.fit(
        "[bold yellow]🔑 首次使用需要配置 DeepSeek API Key[/bold yellow]\n\n"
        "去 [link=https://platform.deepseek.com/api_keys]platform.deepseek.com/api_keys[/link] 创建一个\n"
        "然后粘贴到这里：",
        border_style="yellow",
        title="配置"
    ))
    try:
        key = click.prompt("API Key", hide_input=False).strip()
        if key:
            save_config(key)
            API_KEY = key
            console.print("[green]✅ 已保存到 ~/.codemate/config.json[/green]\n")
        else:
            console.print("[red]❌ Key 不能为空[/red]")
            sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]已取消[/yellow]")
        sys.exit(0)

# ---------- 提示 ----------
USAGE_HINT = """
[dim]提示：设置环境变量后使用[/dim]

  export DEEPSEEK_API_KEY="sk-xxxxxxxx"
  export DEEPSEEK_BASE_URL="https://api.deepseek.com"  # 可选，已默认
  export DEEPSEEK_MODEL="deepseek-chat"                # 可选，已默认

[dim]然后运行：[/dim]
  codemate explain app.py
  codemate debug "报错信息"
  codemate concept "闭包"
"""


def check_api_key():
    """检查并获取 API Key"""
    resolve_api_key()
    if not API_KEY:
        console.print(Panel.fit(
            "[bold red]❌ 未配置 DEEPSEEK_API_KEY[/bold red]\n\n" + USAGE_HINT,
            border_style="red",
        ))
        sys.exit(1)


def call_api(system_prompt: str, user_input: str, stream: bool = False):
    """调用 DeepSeek API，返回完整响应或逐块输出"""
    check_api_key()

    url = f"{BASE_URL}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ],
        "stream": stream,
        "temperature": 0.7,
        "max_tokens": 4096,
    }

    try:
        if stream:
            console.print()
            full_text = ""
            with requests.post(url, headers=headers, json=payload, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines(decode_unicode=True):
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[6:]  # 去掉 "data: " 前缀
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"]
                        if "content" in delta and delta["content"]:
                            full_text += delta["content"]
                            console.print(delta["content"], end="")
                    except (json.JSONDecodeError, KeyError):
                        continue
            console.print("\n")
            return full_text
        else:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            console.print(Markdown(content))
            return content

    except requests.exceptions.ConnectionError:
        console.print("\n[bold red]❌ 网络连接失败，无法访问 DeepSeek API[/bold red]")
        console.print("[dim]请检查网络和 DEEPSEEK_BASE_URL 配置[/dim]")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        console.print(f"\n[bold red]❌ API 返回错误[/bold red]")
        if e.response.status_code == 401:
            console.print("[dim]请检查 DEEPSEEK_API_KEY 是否有效[/dim]")
        elif e.response.status_code == 429:
            console.print("[dim]请求频率过高，请稍后重试[/dim]")
        else:
            console.print(f"[dim]HTTP {e.response.status_code}: {e.response.text[:200]}[/dim]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[bold red]❌ 调用失败: {e}[/bold red]")
        sys.exit(1)


def read_code_input(input_source: str | None) -> str:
    """读取代码：文件路径 > 管道输入 > 编辑器"""
    if input_source:
        path = Path(input_source).expanduser()
        if path.exists():
            return path.read_text(encoding="utf-8")
        else:
            console.print(f"[bold red]❌ 文件不存在: {input_source}[/bold red]")
            sys.exit(1)

    # 尝试从管道读取
    if not sys.stdin.isatty():
        return sys.stdin.read()

    # 交互式输入（打开编辑器）
    console.print("[dim]未提供文件或管道输入，将打开编辑器...[/dim]")
    code = click.edit()
    if code is None:
        console.print("[yellow]已取消[/yellow]")
        sys.exit(0)
    return code


# ---------- CLI 命令 ----------

def interactive_menu():
    """无参数双击运行时显示的交互菜单"""
    console.print(Panel.fit(
        "[bold cyan]CodeMate — AI 编程学习助手[/bold cyan]\n\n"
        "  [1] [bold]📖 代码解释[/bold]   — 粘贴代码，AI 逐块解析\n"
        "  [2] [bold]🐛 错误诊断[/bold]   — 粘贴报错，AI 分析修复\n"
        "  [3] [bold]💡 概念问答[/bold]   — 输入概念，AI 举例讲解\n"
        "  [0] 退出",
        border_style="cyan",
        title="菜单"
    ))
    try:
        choice = click.prompt("请选择", type=int, default=0)
    except (KeyboardInterrupt, EOFError):
        return

    if choice == 1:
        explain.callback(stream=True)
    elif choice == 2:
        debug.callback(stream=True)
    elif choice == 3:
        concept.callback(stream=True)
    else:
        console.print("[dim]再见 👋[/dim]")


@click.group(invoke_without_command=True)
@click.version_option(version="0.1.0", prog_name="codemate")
@click.pass_context
def cli(ctx):
    """CodeMate - AI 编程学习助手

    三个子命令：explain（解释代码）| debug（诊断错误）| concept（概念问答）

    \b
    直接双击运行或输入 codemate 进入交互菜单。
    """
    if ctx.invoked_subcommand is None:
        interactive_menu()


@cli.command()
@click.argument("file", required=False)
@click.option("--stream", is_flag=True, help="流式输出")
def explain(file, stream):
    """解释代码逻辑

    \b
    用法：
      codemate explain app.py         从文件读取
      cat app.py | codemate explain   从管道读取
      codemate explain                打开编辑器输入
    """
    code = read_code_input(file)

    if not code.strip():
        console.print("[yellow]⚠️  未输入任何代码[/yellow]")
        return

    console.print(Panel("[bold cyan]📖 代码解释[/bold cyan]", border_style="cyan"))
    call_api(EXPLAIN_PROMPT, f"请解释以下代码：\n\n```\n{code}\n```", stream=stream)


@cli.command()
@click.argument("error", required=False)
@click.option("--code", "-c", "code_str", help="相关代码片段")
@click.option("--file", "-f", "code_file", help="包含相关代码的文件")
@click.option("--stream", is_flag=True, help="流式输出")
def debug(error, code_str, code_file, stream):
    """诊断代码错误

    \b
    用法：
      codemate debug "TypeError: 'int' object is not subscriptable"
      codemate debug "报错信息" --code "相关代码"
      codemate debug "报错信息" --file app.py
    """
    if not error:
        error = click.prompt("请输入错误信息（可粘贴完整报错）")

    # 构建上下文
    parts = [f"## 错误信息\n{error}"]

    if code_file:
        path = Path(code_file).expanduser()
        if path.exists():
            code_str = path.read_text(encoding="utf-8")
        else:
            console.print(f"[yellow]⚠️  文件不存在: {code_file}，已忽略[/yellow]")

    if code_str:
        parts.append(f"\n## 相关代码\n```\n{code_str}\n```")

    console.print(Panel("[bold red]🐛 错误诊断[/bold red]", border_style="red"))
    call_api(DEBUG_PROMPT, "\n".join(parts), stream=stream)


@cli.command()
@click.argument("topic", required=False)
@click.option("--stream", is_flag=True, help="流式输出")
def concept(topic, stream):
    """解释编程概念

    \b
    用法：
      codemate concept "闭包"
      codemate concept "RESTful API"
      codemate concept                  交互式输入
    """
    if not topic:
        topic = click.prompt("请输入你想了解的编程概念")

    console.print(
        Panel(f"[bold green]💡 概念解析: {topic}[/bold green]", border_style="green")
    )
    call_api(CONCEPT_PROMPT, f"请解释以下概念：{topic}", stream=stream)


def pause():
    """Windows 双击运行时防止窗口闪退"""
    if sys.stdout.isatty():
        try:
            input("\n[dim]按 Enter 退出...[/dim]")
        except (KeyboardInterrupt, EOFError):
            pass


if __name__ == "__main__":
    try:
        cli()
    except Exception as e:
        console.print(f"\n[bold red]❌ 运行出错: {e}[/bold red]")
        import traceback
        traceback.print_exc()
        pause()
        sys.exit(1)
    else:
        pause()
