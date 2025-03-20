# 微信公众号文章生成工具

这是一个自动化工具，可以从GitHub仓库的README文件生成美观的微信公众号文章。它支持Markdown格式转换，自动生成配图，并可以直接发布到微信公众号。

## 功能特点

- 自动获取GitHub仓库README内容
- Markdown格式转换为微信公众号支持的格式
- 使用AI自动生成文章配图
- 支持代码高亮显示
- 自动处理图片上传
- 支持创建微信公众号草稿
- 完整的中文处理支持

## 系统要求

- Python 3.8 或更高版本
- 微信公众号服务号（订阅号不支持发布文章）
- OpenAI API 密钥
- 阿里云 DashScope API 密钥

## 安装步骤

1. 克隆仓库：
```bash
git clone https://github.com/yourusername/repo-name.git
cd repo-name
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置环境变量：
```bash
cp .env.example .env
```

4. 编辑 `.env` 文件，填入必要的配置信息：
```bash
# OpenAI配置
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4-turbo-preview

# 阿里云 DashScope 配置
DASHSCOPE_API_KEY=your_dashscope_api_key_here

# 微信公众号配置
WEIXIN_APP_ID=your_app_id_here
WEIXIN_APP_SECRET=your_app_secret_here
```

## 使用方法

1. 基本使用：
```bash
python main.py --repo https://github.com/username/repo
```

2. 高级选项：
```bash
# 测试模式（不实际发布）
python main.py --test

# 指定分支
python main.py --repo https://github.com/username/repo --branch develop

# 调试模式
python main.py --debug
```

3. 自定义模板：
- 将自定义HTML模板放在 `templates` 目录下
- 在 `.env` 文件中设置 `TEMPLATE_NAME=your_template_name`

## 目录结构

```
.
├── main.py              # 主程序
├── weixin_publisher.py  # 微信发布模块
├── poster_generator.py  # 海报生成模块
├── templates/           # HTML模板目录
├── images/             # 图片缓存目录
├── .env                # 环境配置文件
├── .env.example        # 环境配置示例
└── requirements.txt    # 项目依赖
```

## 常见问题

1. 图片上传失败
   - 检查网络连接
   - 确认图片格式是否支持（支持jpg/png）
   - 验证微信公众号配置是否正确

2. 内容格式问题
   - 确保Markdown格式正确
   - 检查是否包含不支持的HTML标签
   - 注意微信公众号的内容限制（字数、图片大小等）

3. API限制问题
   - OpenAI API: 注意使用频率和配额限制
   - DashScope API: 关注图片生成的额度使用情况
   - 微信API: 遵守每日调用次数限制

## 开发计划

- [ ] 支持更多Markdown语法
- [ ] 添加更多文章模板
- [ ] 支持自定义图片生成风格
- [ ] 添加文章定时发布功能
- [ ] 支持批量处理多个仓库

## 贡献指南

1. Fork 本仓库
2. 创建新的分支 `git checkout -b feature/your-feature`
3. 提交更改 `git commit -am 'Add some feature'`
4. 推送到分支 `git push origin feature/your-feature`
5. 提交 Pull Request

## 许可证

MIT License 