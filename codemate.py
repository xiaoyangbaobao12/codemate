#!/usr/bin/env python3
"""
CodeMate - AI 编程学习助手 (CLI)
基于 DeepSeek API，提供代码解释、错误诊断、概念问答三个功能。
"""

import os
import sys
from pathlib import Path

import click
from openai import OpenAI
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.live import Live

from prompts import CONCEPT_PROMPT, DEBUG_PROMPT, EXPLAIN_PROMPT

console = Console()

# ---------- API 配置 ----------
API_KEY = os.environ.get("DEEPSEEK_API_KEY")
BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

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


def get_client():
    """获取 API 客户端，未配置时给出友好提示"""
    if not API_KEY:
        console.print(Panel.fit(
            "[bold red]❌ 未设置 DEEPSEEK_API_KEY[/bold red]\n\n" + USAGE_HINT,
            border_style="red",
        ))
        sys.exit(1)
    return OpenAI(api_key=API_KEY, base_url=BASE_URL)


def call_api(system_prompt: str, user_input: str, stream: bool = False):
    """调用 DeepSeek API，返回完整响应或逐块输出"""
    client = get_client()

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            stream=stream,
            temperature=0.7,
            max_tokens=4096,
        )

        if stream:
            console.print()
            full_text = ""
            for chunk in response:
                delta = chunk.choices[0].delta
                if delta.content:
                    full_text += delta.content
                    console.print(delta.content, end="")
            console.print("\n")
            return full_text
        else:
            content = response.choices[0].message.content
            console.print(Markdown(content))
            return content

    except Exception as e:
        console.print(f"\n[bold red]❌ API 调用失败: {e}[/bold red]")
        if "Connection" in str(e) or "connect" in str(e).lower():
            console.print("[dim]请检查网络连接和 DEEPSEEK_BASE_URL 是否正确[/dim]")
        elif "401" in str(e) or "Unauthorized" in str(e):
            console.print("[dim]请检查 DEEPSEEK_API_KEY 是否有效[/dim]")
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

@click.group()
@click.version_option(version="0.1.0", prog_name="codemate")
def cli():
    """CodeMate - AI 编程学习助手

    三个子命令：explain（解释代码）| debug（诊断错误）| concept（概念问答）
    """
    pass


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


if __name__ == "__main__":
    cli()
