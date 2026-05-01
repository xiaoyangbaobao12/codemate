# CodeMate — AI 编程学习助手

基于 DeepSeek API 的命令行编程学习工具，专为软件工程专业学生设计。

## 功能

- **📖 代码解释** (`explain`) — 输入代码，AI 逐块解析逻辑、算法和数据流
- **🐛 错误诊断** (`debug`) — 粘贴报错信息，AI 分析根因并给出修复代码
- **💡 概念问答** (`concept`) — 输入编程概念，AI 用生活类比 + 代码示例讲解

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
export DEEPSEEK_API_KEY="sk-xxxxxxxx"
```

可选配置：

```bash
export DEEPSEEK_BASE_URL="https://api.deepseek.com"  # 默认值
export DEEPSEEK_MODEL="deepseek-chat"                # 默认值
```

### 3. 使用

```bash
# 代码解释
python codemate.py explain app.py
cat app.py | python codemate.py explain
python codemate.py explain                 # 打开编辑器输入

# 错误诊断
python codemate.py debug "TypeError: 'int' object is not subscriptable"
python codemate.py debug "报错信息" --code "bad_code = 1[0]"
python codemate.py debug "报错信息" --file app.py

# 概念问答
python codemate.py concept "闭包"
python codemate.py concept "RESTful API"
python codemate.py concept                # 交互式输入

# 流式输出（逐字显示，体验更好）
python codemate.py explain app.py --stream
python codemate.py debug "报错" --stream
python codemate.py concept "死锁" --stream
```

## 项目结构

```
codemate/
├── codemate.py          # CLI 入口
├── prompts/
│   ├── __init__.py
│   ├── explain.py       # 代码解释的 System Prompt
│   ├── debug.py         # 错误诊断的 System Prompt
│   └── concept.py       # 概念问答的 System Prompt
├── requirements.txt
└── README.md
```

## 技术栈

- Python 3.10+
- DeepSeek API（OpenAI 兼容格式）
- Click（CLI 框架）
- Rich（终端美化，Markdown 渲染 + 代码高亮）

## License

MIT
