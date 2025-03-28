import os
import requests
from bs4 import BeautifulSoup
import openai
from jinja2 import Template, FileSystemLoader, Environment
from dotenv import load_dotenv
import json
import base64
from datetime import datetime
import random
from poster_generator import PosterGenerator
from weixin_publisher import WeixinPublisher
import sys
import argparse
import traceback
import re
# 导入publish_to_weixin模块
import publish_to_weixin

# 加载环境变量
load_dotenv()

# OpenAI配置
openai.api_base = os.getenv('OPENAI_API_BASE', '')
openai.api_key = os.getenv('OPENAI_API_KEY', '')

def fetch_readme_content(url):
    """获取README内容和相关图片"""
    def try_get_content(url):
        """尝试获取内容"""
        print(f"尝试获取内容：{url}")
        response = requests.get(url)
        return response.status_code == 200, response.text if response.status_code == 200 else None

    def download_image(img_url, repo_base):
        """下载图片并保存到本地"""
        try:
            # 确保images目录存在
            os.makedirs('images', exist_ok=True)
            
            # 获取图片文件名
            img_filename = os.path.basename(img_url)
            if '?' in img_filename:
                img_filename = img_filename.split('?')[0]
            
            # 如果是相对路径，转换为完整URL
            if not img_url.startswith(('http://', 'https://')):
                img_url = f"{repo_base}/{img_url}"
            
            # 下载图片
            response = requests.get(img_url)
            if response.status_code == 200:
                local_path = os.path.join('images', img_filename)
                with open(local_path, 'wb') as f:
                    f.write(response.content)
                return local_path
        except Exception as e:
            print(f"下载图片失败 {img_url}: {str(e)}")
        return None

    # 如果是GitHub仓库URL
    if 'github.com' in url:
        # 检查是否是具体的文件路径
        if '/blob/' in url:
            # 从URL中提取分支和文件路径
            parts = url.split('/blob/')
            repo_url = parts[0]
            branch_and_path = parts[1].split('/', 1)
            branch = branch_and_path[0]
            file_path = branch_and_path[1] if len(branch_and_path) > 1 else ''
            
            # 转换为raw URL
            raw_url = f"{repo_url.replace('github.com', 'raw.githubusercontent.com')}/{branch}/{file_path}"
            success, content = try_get_content(raw_url)
            if success:
                print(f"成功获取文件内容：{raw_url}")
                repo_base = f"{repo_url.replace('github.com', 'raw.githubusercontent.com')}/{branch}"
                return content, []
            else:
                raise Exception(f"无法获取指定文件内容：{url}")
        
        # 处理仓库URL
        url = url.rstrip('.git').rstrip('/')
        raw_base = url.replace('github.com', 'raw.githubusercontent.com')
        repo_base = raw_base
        
        # 尝试不同分支和文件名的组合
        branches = ['main', 'master', 'dev', 'develop', 'variable']  # 添加更多常用分支
        filenames = [
            'README.md', 'README', 'readme.md', 'Readme.md',
            'README_CN.md', 'README.zh-CN.md', 'README_zh.md',  # 添加中文README文件名
            'docs/README.md', 'doc/README.md',  # 添加可能的文档目录
            'docs/zh/README.md', 'docs/cn/README.md'  # 添加可能的中文文档目录
        ]
        
        # 首先尝试直接访问仓库API获取默认分支和所有分支
        api_url = url.replace('github.com', 'api.github.com/repos')
        try:
            repo_info = requests.get(api_url).json()
            if 'default_branch' in repo_info:
                branches.insert(0, repo_info['default_branch'])
            
            # 获取所有分支
            branches_url = f"{api_url}/branches"
            branches_info = requests.get(branches_url).json()
            if isinstance(branches_info, list):
                additional_branches = [b['name'] for b in branches_info if b['name'] not in branches]
                branches.extend(additional_branches)
        except:
            pass

        content = None
        found_branch = None
        found_filename = None
        
        # 尝试所有可能的组合
        for branch in branches:
            for filename in filenames:
                raw_url = f"{raw_base}/{branch}/{filename}"
                success, content_try = try_get_content(raw_url)
                if success:
                    print(f"成功找到文件：{raw_url}")
                    content = content_try
                    found_branch = branch
                    found_filename = filename
                    break
            if content:
                break
        
        if not content:
            raise Exception(f"无法在仓库中找到README文件：{url}")
        
        # 处理图片
        repo_base = f"{raw_base}/{found_branch}"
        # 如果README在子目录中，调整repo_base
        if '/' in found_filename:
            subdir = os.path.dirname(found_filename)
            repo_base = f"{repo_base}/{subdir}"
            
        # 查找Markdown格式的图片链接
        img_links = []
        lines = content.split('\n')
        for i, line in enumerate(lines):
            # 匹配Markdown图片语法
            img_matches = re.findall(r'!\[([^\]]*)\]\(([^)]+)\)', line)
            for alt_text, img_url in img_matches:
                local_path = download_image(img_url, repo_base)
                if local_path:
                    # 替换为本地路径
                    lines[i] = line.replace(img_url, local_path)
                    img_links.append((alt_text, local_path))
        
        # 更新内容
        content = '\n'.join(lines)
        return content, img_links
    
    # 如果已经是raw内容URL
    success, content = try_get_content(url)
    if success:
        # 验证内容是否看起来像README文件
        content_lower = content.lower()
        if '# ' in content or '## ' in content or 'install' in content_lower or 'usage' in content_lower:
            return content, []
        else:
            raise Exception(f"获取的内容不像是README文件：{url}")
    
    raise Exception(f"无法获取内容：{url}")

def analyze_with_openai(content):
    """使用OpenAI分析内容"""
    # 限制输入内容长度
    max_content_length = 4000  # 设置最大内容长度
    if len(content) > max_content_length:
        content = content[:max_content_length] + "\n...(内容已截断)"
    
    prompt = f"""请仔细分析以下GitHub项目的README内容，生成一篇详细的介绍文章。要求：

1. 文章结构要求：
   - 标题：简洁有力，不超过20个字
   - 前言：概括项目的核心价值和主要用途
   - 项目介绍：详细说明项目的背景、目标和解决的问题
   - 功能亮点：列举项目的主要功能，每个功能都要详细说明
   - 技术特点：分析项目的技术架构、性能优势等
   - 安装说明：完整的安装步骤，包括环境要求
   - 使用说明：详细的使用方法，包括配置说明
   - 项目地址：项目的源码地址
   - 结语：总结项目价值，展望未来发展

2. 内容要求：
   - 直接引用README中的重要内容，保持原始信息的准确性
   - 对于代码示例和配置，保持原格式，不要简化
   - 保留原文中的所有图片引用
   - 技术术语使用原文的表述，不要随意改写
   - 如果原文有版本信息、依赖要求等，要完整保留

3. 格式要求：
   - 代码块使用 ```语言名 和 ``` 包裹
   - 图片使用原始Markdown格式
   - 重要内容使用加粗标记
   - 项目地址直接使用URL，不要加修饰
   - 列表项使用 - 标记

请基于以上要求，分析并生成文章：

{content}"""

    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "你是一个专业的技术文档作者，擅长分析开源项目并生成详细的介绍文章。你会保持原始文档的准确性，同时让内容更加结构化和易于理解。"},
            {"role": "user", "content": prompt}
        ],
        max_tokens=3000
    )
    
    # 获取响应内容
    result = response.choices[0].message.content
    
    # 确保结果是正确的中文编码
    try:
        # 1. 如果是 bytes，先解码为 utf-8
        if isinstance(result, bytes):
            result = result.decode('utf-8')
            
        # 2. 处理 Unicode 转义序列
        while '\\u' in result:
            result = result.encode().decode('unicode-escape')
            
        # 3. 确保是 utf-8 字符串
        result = result.encode('utf-8').decode('utf-8')
    except Exception as e:
        print(f"编码处理失败: {str(e)}")
        # 如果处理失败，尝试直接使用 unicode-escape 解码
        try:
            result = result.encode('utf-8').decode('unicode-escape')
        except:
            # 如果还是失败，保持原始内容
            pass
    
    print("\nOpenAI响应内容：")
    print(result)
    print("\n" + "="*50 + "\n")
    return result

def generate_html(analysis_result):
    """生成微信公众号文章HTML"""
    try:
        if isinstance(analysis_result, bytes):
            analysis_result = analysis_result.decode('utf-8')
        
        # 加载模板
        env = Environment(loader=FileSystemLoader('templates'))
        template_name = os.getenv('TEMPLATE_NAME', 'article')
        template = env.get_template(f'{template_name}.html')
        
        # 初始化sections字典
        sections = {
            'preface': '',
            'introduction': '',
            'features': '',
            'technical': '',
            'installation': '',
            'usage': '',
            'repository': '',
            'conclusion': ''
        }
        
        title = ''
        current_section = None
        current_content = []
        
        # 解析文章内容
        for line in analysis_result.split('\n'):
            if line.startswith('# '):
                # 主标题
                title = line.replace('# ', '').strip()
            elif line.startswith('## '):
                # 如果有之前的section，保存它
                if current_section and current_content:
                    section_content = '\n'.join(current_content)
                    if current_section == '前言':
                        sections['preface'] = process_section_content(section_content)
                    elif current_section == '项目介绍':
                        sections['introduction'] = process_section_content(section_content)
                    elif current_section == '功能亮点':
                        sections['features'] = process_section_content(section_content)
                    elif current_section == '技术特点':
                        sections['technical'] = process_section_content(section_content)
                    elif current_section == '安装说明':
                        sections['installation'] = process_section_content(section_content)
                    elif current_section == '使用说明':
                        sections['usage'] = process_section_content(section_content)
                    elif current_section == '项目地址':
                        sections['repository'] = process_section_content(section_content)
                    elif current_section == '结语':
                        sections['conclusion'] = process_section_content(section_content)
                
                # 新的section
                current_section = line.replace('## ', '').strip()
                current_content = []
            elif current_section:
                current_content.append(line)
        
        # 处理最后一个section
        if current_section and current_content:
            section_content = '\n'.join(current_content)
            if current_section == '结语':
                sections['conclusion'] = process_section_content(section_content)
            # ... 其他section的处理 ...
        
        # 渲染模板
        html_content = template.render(
            title=title,
            sections=sections
        )
        
        return html_content
        
    except Exception as e:
        print(f"生成HTML时发生错误: {str(e)}")
        traceback.print_exc()
        return f"<h1>生成HTML时发生错误</h1><pre>{str(e)}</pre>"

def process_section_content(content):
    """处理章节内容，包括代码块、图片等"""
    if not content:
        return ''
        
    # 处理代码块
    content = process_code_blocks(content)
    
    # 处理图片
    content = process_images(content)
    
    # 处理列表
    content = process_lists(content)
    
    # 处理链接
    content = process_links(content)
    
    # 处理加粗和斜体
    content = process_emphasis(content)
    
    return content

def process_code_blocks(content):
    """处理代码块"""
    parts = []
    lines = content.split('\n')
    in_code = False
    code_buffer = []
    
    for line in lines:
        if line.strip().startswith('```'):
            if in_code:
                # 结束代码块
                code = '\n'.join(code_buffer)
                if code.strip():
                    parts.append(f'<div class="code-block"><pre>{code}</pre></div>')
                code_buffer = []
            in_code = not in_code
            continue
            
        if in_code:
            code_buffer.append(line)
        else:
            parts.append(line)
    
    return '\n'.join(parts)

def process_images(content):
    """处理图片"""
    return re.sub(
        r'!\[(.*?)\]\((.*?)\)',
        r'<div class="image-container"><img src="\2" alt="\1"><div class="image-caption">\1</div></div>',
        content
    )

def process_lists(content):
    """处理列表"""
    if any(line.strip().startswith('- ') for line in content.split('\n')):
        lines = content.split('\n')
        list_content = ['<ul>']
        for line in lines:
            if line.strip().startswith('- '):
                item = line.strip()[2:]
                list_content.append(f'<li>{item}</li>')
        list_content.append('</ul>')
        return '\n'.join(list_content)
    return content

def process_links(content):
    """处理链接"""
    return re.sub(
        r'\[(.*?)\]\((.*?)\)',
        r'<a href="\2" target="_blank">\1</a>',
        content
    )

def process_emphasis(content):
    """处理加粗和斜体"""
    content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
    content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', content)
    return content

def process_section(section_title, content):
    """处理单个章节内容"""
    html = f'<div class="section" style="margin-bottom: 30px;">'
    html += f'<div class="section-title" style="font-size: 20px; font-weight: bold; color: #333; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #f0f0f0;">{section_title}</div>'
    
    # 根据章节内容类型进行不同处理
    if section_title == '项目地址':
        # 处理项目地址
        urls = content.split('\n')
        formatted_content = '<div class="section-content" style="font-size: 16px; line-height: 1.8; color: #444; margin-bottom: 15px;">'
        for url in urls:
            url = url.strip()
            if url and not url.startswith('!['): # 忽略图片链接
                formatted_content += f'<a href="{url}" target="_blank" class="project-link" style="color: #0366d6; text-decoration: none; word-break: break-all;">{url}</a><br>'
        formatted_content += '</div>'
        html += formatted_content
    elif section_title in ['安装说明', '使用说明']:
        # 处理可能含有代码块的内容
        html += format_content_with_code(content)
    else:
        # 处理普通内容
        html += format_regular_content(content)
    
    html += '</div>'
    return html

def format_content_with_code(content):
    """格式化可能包含代码块的内容"""
    if '```' in content:
        parts = []
        in_code = False
        code_buffer = []
        regular_buffer = []
        
        for line in content.split('\n'):
            if line.strip().startswith('```'):
                in_code = not in_code
                
                # 如果代码块结束，处理收集的代码
                if not in_code and code_buffer:
                    # 移除第一行的语言标识
                    if len(code_buffer) > 0 and not code_buffer[0].strip().startswith('```'):
                        code = '\n'.join(code_buffer)
                    else:
                        code = '\n'.join(code_buffer[1:])
                    
                    if code.strip():
                        if regular_buffer:
                            parts.append(f'<div class="section-content" style="font-size: 16px; line-height: 1.8; color: #444; margin-bottom: 15px;">{"<br>".join(regular_buffer)}</div>')
                            regular_buffer = []
                        parts.append(f'<div class="code-block" style="background-color: #f8f8f8; padding: 15px; border-radius: 5px; margin: 15px 0; overflow-x: auto;"><pre class="code" style="font-family: Consolas, Monaco, \'Andale Mono\', monospace; font-size: 14px; line-height: 1.4; color: #333; margin: 0;">{code}</pre></div>')
                    code_buffer = []
                continue
            
            if in_code:
                code_buffer.append(line)
            else:
                if line.strip():  # 忽略空行
                    # 处理Markdown格式
                    line = process_markdown_line(line)
                    regular_buffer.append(line)
        
        # 添加剩余的常规内容
        if regular_buffer:
            parts.append(f'<div class="section-content" style="font-size: 16px; line-height: 1.8; color: #444; margin-bottom: 15px;">{"<br>".join(regular_buffer)}</div>')
        
        return ''.join(parts)
    else:
        # 没有代码块，直接处理
        return f'<div class="section-content" style="font-size: 16px; line-height: 1.8; color: #444; margin-bottom: 15px;">{process_markdown_content(content)}</div>'

def format_regular_content(content):
    """格式化普通内容"""
    # 检查是否是列表
    if any(line.strip().startswith('- ') for line in content.split('\n')):
        formatted = '<div class="section-content" style="font-size: 16px; line-height: 1.8; color: #444; margin-bottom: 15px;"><ul class="feature-list" style="list-style-type: none; padding-left: 0;">'
        for line in content.split('\n'):
            if line.strip().startswith('- '):
                item_content = line[1:].strip()
                # 处理图片
                if '![' in item_content:
                    item_content = process_markdown_content(item_content)
                formatted += f'<li style="margin-bottom: 10px; padding-left: 20px; position: relative;">{item_content}</li>'
        formatted += '</ul></div>'
        return formatted
    else:
        # 常规段落
        return f'<div class="section-content" style="font-size: 16px; line-height: 1.8; color: #444; margin-bottom: 15px;">{process_markdown_content(content)}</div>'

def process_markdown_line(line):
    """处理单行Markdown格式"""
    # 处理加粗
    line = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line)
    # 处理斜体
    line = re.sub(r'\*(.*?)\*', r'<em>\1</em>', line)
    return line

def process_markdown_content(content):
    """处理Markdown内容，包括图片、加粗等"""
    # 处理图片
    content = re.sub(
        r'!\[(.*?)\]\((.*?)\)',
        r'<div class="image-container" style="margin: 20px 0; text-align: center;"><img src="\2" alt="\1" class="content-image" style="max-width: 100%; height: auto; margin-bottom: 10px;"><div class="image-caption" style="font-size: 14px; color: #666; text-align: center;">\1</div></div>',
        content
    )
    
    # 处理其他Markdown语法
    lines = content.split('\n')
    formatted_lines = [process_markdown_line(line) for line in lines]
    
    return "<br>".join(formatted_lines)

def generate_image(prompt_text_zh, title, sub_title, body_text):
    try:
        generator = ImageGenerator()
        # ... existing code ...
    except Exception as e:
        print(f"生成图片失败: {str(e)}")
        return None

def extract_article_content(analysis_result):
    """从文章内容中提取标题、副标题和正文"""
    # 确保输入是UTF-8编码的字符串
    if isinstance(analysis_result, bytes):
        analysis_result = analysis_result.decode('utf-8')
    
    lines = analysis_result.split('\n')
    title = "Open-Sora开源项目介绍"  # 设置默认标题
    sub_title = ""
    body_text = []
    
    # 提取标题（通常是第一个#开头的行）
    for line in lines:
        # 移除可能的空格
        line = line.strip()
        if line.startswith(('#', '###', '####')):
            # 移除#号和空格，并确保编码正确
            clean_title = line.lstrip('#').strip()
            if clean_title:
                # 处理可能的 Unicode 转义序列
                if '\\u' in clean_title:
                    try:
                        clean_title = clean_title.encode().decode('unicode-escape')
                    except Exception:
                        pass
                title = clean_title
                break
    
    # 提取副标题（通常是第一个##开头的行）
    for line in lines:
        if line.startswith(('##', '###')):
            sub_title = line.lstrip('#').strip()
            # 处理可能的 Unicode 转义序列
            if '\\u' in sub_title:
                try:
                    sub_title = sub_title.encode().decode('unicode-escape')
                except Exception:
                    pass
            break
    
    # 提取正文（收集所有非标题、非代码块的文本）
    in_code_block = False
    for line in lines:
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            continue
        
        if not in_code_block and not line.startswith('#') and line.strip():
            # 移除Markdown语法
            clean_line = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', line)  # 移除链接
            clean_line = re.sub(r'!\[.*?\]\(.*?\)', '', clean_line)  # 移除图片
            clean_line = re.sub(r'\*\*(.*?)\*\*', r'\1', clean_line)  # 移除加粗
            clean_line = re.sub(r'\*(.*?)\*', r'\1', clean_line)  # 移除斜体
            
            if clean_line.strip():
                # 处理可能的 Unicode 转义序列
                if '\\u' in clean_line:
                    try:
                        clean_line = clean_line.encode().decode('unicode-escape')
                    except Exception:
                        pass
                body_text.append(clean_line.strip())
    
    # 获取第一段文本，并限制长度为50个字符
    full_text = body_text[0] if body_text else ""
    if len(full_text) > 50:
        full_text = full_text[:47] + "..."
    
    # 限制标题长度为20个字符
    if len(title) > 30:
        title = title[:29] + "..."
    
    return {
        'title': title,
        'sub_title': sub_title,
        'body_text': full_text
    }

def get_random_lora_name():
    """随机选择一个预设的 lora_name"""
    lora_names = [
        "2D插画1", "2D插画2", "浩瀚星云", "浓郁色彩",
        "光线粒子", "透明玻璃", "剪纸工艺", "折纸工艺",
        "中国水墨", "中国刺绣", "真实场景", "2D卡通",
        "儿童水彩", "赛博背景", "浅蓝抽象", "深蓝抽象",
        "抽象点线", "童话油画"
    ]
    return random.choice(lora_names)

def generate_poster(article_content):
    """生成文章封面图片"""
    poster_url = None
    try:
        poster_gen = PosterGenerator()
        # 从环境变量获取配置，如果没有则使用默认值
        wh_ratios = os.getenv('POSTER_WH_RATIOS', '竖版').split(',')
        lora_name = os.getenv('POSTER_LORA_NAME', '')
        
        # 如果 lora_name 为空，随机选择一个
        if not lora_name:
            lora_name = get_random_lora_name()
            print(f"随机选择的 lora_name: {lora_name}")
        
        # 构建提示词
        prompt_text_zh = f"{article_content['title']} - {article_content['sub_title']}"
        
        # 为每个比例生成海报
        for ratio in wh_ratios:
            try:
                result = poster_gen.generate(
                    prompt_text_zh=prompt_text_zh,
                    title=article_content['title'],
                    sub_title=article_content['sub_title'],
                    body_text=article_content['body_text'],
                    wh_ratio=ratio,
                    lora_name=lora_name
                )
                print(f"成功生成比例为 {ratio} 的海报")
                # 保存第一个成功生成的海报URL
                if result and not poster_url:
                    poster_url = result.get('url')
                print(f"海报URL: {poster_url}")
            except Exception as e:
                print(f"生成比例为 {ratio} 的海报失败: {str(e)}")
    except Exception as e:
        print(f"海报生成过程中发生错误: {str(e)}")
        if args.debug:
            traceback.print_exc()
    return poster_url

def main():
    try:
        # 命令行参数解析
        parser = argparse.ArgumentParser(description='GitHub项目README分析和发布工具')
        parser.add_argument('--url', type=str, help='要分析的GitHub项目URL，覆盖环境变量中的配置')
        parser.add_argument('--debug', action='store_true', help='显示调试信息')
        parser.add_argument('--publish', action='store_true', help='强制发布到微信，覆盖环境变量配置')
        parser.add_argument('--test', action='store_true', help='微信发布测试模式')
        parser.add_argument('--no-publish', action='store_true', help='禁用发布到微信，覆盖环境变量配置')
        args = parser.parse_args()
        
        try:
            # 获取项目地址列表
            project_urls = []
            if args.url:
                project_urls = [args.url]
            else:
                urls_env = os.getenv('PROJECT_URLS', '')
                project_urls = [url.strip() for url in urls_env.split(',') if url.strip()]
            
            if not project_urls:
                raise ValueError("未配置项目地址。请在.env文件中设置PROJECT_URLS或使用--url参数")
            
            # 获取所有README内容
            all_content = []
            all_images = []
            for url in project_urls:
                try:
                    content, img_links = fetch_readme_content(url)
                    all_content.append(content)
                    all_images.extend(img_links)
                    print(f"成功获取 {url} 的README内容")
                except Exception as e:
                    print(f"获取 {url} 的README内容失败: {str(e)}")
            
            if not all_content:
                raise ValueError("未能获取任何README内容")
            
            # 合并所有内容
            combined_content = "\n\n---\n\n".join(all_content)
            
            # 使用OpenAI分析内容
            analysis_result = analyze_with_openai(combined_content)
            
            # 提取文章内容
            article_content = extract_article_content(analysis_result)
            
            # 生成HTML
            html_content = generate_html(analysis_result)
            
            # 保存HTML文件
            output_file = 'output.html'
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
                
            print(f"\n分析完成！结果已保存到 {output_file}")
            print("\n文章信息：")
            print(f"标题：{article_content['title']}")
            print(f"副标题：{article_content['sub_title']}")
            print(f"正文预览：{article_content['body_text'][:100]}...")
            
            # 判断是否需要发布到微信
            should_publish = False
            if args.publish:
                # 命令行参数优先：强制发布
                should_publish = True
            elif args.no_publish:
                # 命令行参数优先：禁用发布
                should_publish = False
            else:
                # 使用环境变量配置
                should_publish = os.getenv('PUBLISH_TO_WEIXIN', 'false').lower() == 'true'
            
            if should_publish:
                print("\n准备发布到微信...")
                # 生成封面图
                poster_url = generate_poster(article_content)
                if poster_url:
                    print(f"\n成功生成封面图：{poster_url}")
                    
                    print("\n=====================")
                    print("开始调用微信发布模块...")
                    
                    # 直接调用publish_to_weixin模块
                    try:
                        # 创建WeixinPublisher实例
                        weixin_publisher = WeixinPublisher()
                        
                        # 如果有海报，先上传海报
                        thumb_media_id = None
                        if poster_url:
                            try:
                                print("正在上传海报到微信...")
                                thumb_media_id = weixin_publisher.upload_image(poster_url)
                                print(f"海报上传成功，media_id: {thumb_media_id}")
                            except Exception as e:
                                print(f"上传海报失败: {str(e)}")
                                if args.debug:
                                    traceback.print_exc()
                        
                        print(f"准备上传微信: {poster_url}")
                        # 准备参数
                        publish_args = {
                            'html': output_file,
                            'title': article_content['title'],
                            'author': os.getenv('AUTHOR_NAME', 'AI助手'),
                            'test': args.test,
                            'debug': args.debug
                        }
                        
                        # 如果有封面图的media_id，添加到参数中
                        if thumb_media_id:
                            publish_args['thumb_media_id'] = thumb_media_id
                        
                        print(f"调用微信发布模块，参数: {publish_args}")
                        
                        # 调用publish_to_weixin模块中的publish函数
                        result = publish_to_weixin.publish(**publish_args)
                        
                        if result:
                            print("创建草稿成功！")
                        else:
                            print("创建草稿失败！")
                            
                    except Exception as e:
                        print(f"调用微信发布模块失败: {str(e)}")
                        if args.debug:
                            traceback.print_exc()
                else:
                    print("\n生成封面图失败")
            else:
                print("\n已禁用发布到微信功能")
            
        except Exception as e:
            print(f"发生错误: {str(e)}")
            if args.debug:
                traceback.print_exc()
            return 1
            
    except Exception as e:
        print(f"程序执行过程中发生未处理的异常:")
        traceback.print_exc()
        sys.exit(1)
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 