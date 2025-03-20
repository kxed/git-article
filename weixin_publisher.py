#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import requests
import json
import time
import re
from datetime import datetime
from dotenv import load_dotenv
import base64
from PIL import Image, ImageDraw, ImageFont
from bs4 import BeautifulSoup, Comment

# 加载环境变量
load_dotenv()

class WeixinPublisher:
    """微信公众号文章发布工具"""
    
    def __init__(self):
        """初始化，获取配置参数"""
        self.app_id = os.getenv('WEIXIN_APP_ID')
        self.app_secret = os.getenv('WEIXIN_APP_SECRET')
        self.need_open_comment = os.getenv('NEED_OPEN_COMMENT', 'false').lower() == 'true'
        self.only_fans_can_comment = os.getenv('ONLY_FANS_CAN_COMMENT', 'false').lower() == 'true'
        
        # 验证配置
        if not self.app_id or not self.app_secret:
            raise ValueError("微信公众号配置不完整，请检查.env文件")
            
        # 微信API地址
        self.api_base_url = "https://api.weixin.qq.com"
        
        # 缓存token
        self.access_token = None
        self.token_expires_at = 0
    
    def get_access_token(self):
        """获取微信访问令牌"""
        # 如果有有效的token，直接返回
        current_time = int(time.time())
        if self.access_token and current_time < self.token_expires_at:
            return self.access_token
        
        # 请求新token
        url = f"{self.api_base_url}/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": self.app_id,
            "secret": self.app_secret
        }
        
        response = requests.get(url, params=params)
        if response.status_code != 200:
            raise Exception(f"获取微信访问令牌失败: {response.text}")
        
        result = response.json()
        if "errcode" in result and result["errcode"] != 0:
            # 处理特定错误
            if "ip" in result.get("errmsg", "") and "whitelist" in result.get("errmsg", ""):
                error_msg = (
                    f"IP白名单错误: {result['errmsg']}\n\n"
                    "您需要在微信公众号后台将您的服务器IP添加到白名单中：\n"
                    "1. 登录微信公众平台 (mp.weixin.qq.com)\n"
                    "2. 进入'设置与开发' -> '基本配置' -> 'IP白名单'\n"
                    "3. 添加您当前的IP地址\n\n"
                    "微信开发文档：https://developers.weixin.qq.com/doc/offiaccount/Basic_Information/Get_access_token.html"
                )
                raise Exception(error_msg)
            else:
                raise Exception(f"获取微信访问令牌失败: {result['errmsg']}")
        
        self.access_token = result["access_token"]
        self.token_expires_at = current_time + result["expires_in"] - 200  # 提前200秒过期
        
        return self.access_token
    
    def upload_image(self, image_url):
        """上传图片到微信素材库
        Args:
            image_url (str): 图片URL
        Returns:
            str: 图片的media_id
        """
        if not image_url:
            # 如果图片URL为空，返回默认图片ID
            return "SwCSRjrdGJNaWioRQUHzgF68BHFkSlb_f5xlTquvsOSA6Yy0ZRjFo0aW9eS3JJu_"
            
        # 获取图片内容
        try:
            response = requests.get(image_url)
            image_content = response.content
        except Exception as e:
            print(f"获取图片内容失败: {str(e)}")
            raise
            
        # 确保有有效的access_token
        token = self.get_access_token()
        url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}&type=image"
        
        try:
            # 准备文件数据
            files = {
                'media': (
                    f'image_{datetime.now().strftime("%Y%m%d%H%M%S")}.jpg',
                    image_content,
                    'image/jpeg'
                )
            }
            
            # 发送请求
            response = requests.post(url, files=files)
            result = response.json()
            
            if 'media_id' in result:
                print(f"图片上传成功，media_id: {result['media_id']}")
                return result['media_id']
            else:
                error_msg = f"上传图片失败: {result.get('errmsg', '未知错误')}"
                print(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            print(f"上传微信图片失败: {str(e)}")
            raise
    
    def process_html_content(self, html_content):
        """处理HTML内容，移除不支持的标签和属性
        
        Args:
            html_content (str): 原始HTML内容
            
        Returns:
            str: 处理后的HTML内容
        """
        try:
            # 确保输入是字符串
            if isinstance(html_content, bytes):
                html_content = html_content.decode('utf-8')
            elif not isinstance(html_content, str):
                html_content = str(html_content)
            
            # 处理代码块
            # 匹配 ```language\ncode\n``` 格式
            html_content = re.sub(
                r'```(\w*)\n(.*?)\n```',
                lambda m: self._format_code_block(m.group(1), m.group(2)),
                html_content,
                flags=re.DOTALL
            )
            
            # 处理行内代码
            html_content = re.sub(
                r'`([^`]+)`',
                lambda m: f'<code style="background-color: #f6f8fa; padding: 2px 5px; border-radius: 3px; font-family: Consolas, Monaco, \'Andale Mono\', monospace; font-size: 14px;">{m.group(1)}</code>',
                html_content
            )
            
            # 处理标题
            for i in range(6, 0, -1):
                pattern = '^{} (.+)$'.format('#' * i)
                html_content = re.sub(
                    pattern,
                    lambda m: f'<h{i} style="font-size: {28-2*i}px; margin: 20px 0 10px 0; font-weight: bold;">{m.group(1)}</h{i}>',
                    html_content,
                    flags=re.MULTILINE
                )
            
            # 处理列表
            # 无序列表
            html_content = re.sub(
                r'^- (.+)$',
                lambda m: f'<li style="margin: 8px 0; line-height: 1.6;">{m.group(1)}</li>',
                html_content,
                flags=re.MULTILINE
            )
            html_content = re.sub(
                r'(<li[^>]*>.*?</li>\s*)+',
                lambda m: f'<ul style="margin: 10px 0; padding-left: 20px;">{m.group(0)}</ul>',
                html_content,
                flags=re.DOTALL
            )
            
            # 有序列表
            html_content = re.sub(
                r'^\d+\. (.+)$',
                lambda m: f'<li style="margin: 8px 0; line-height: 1.6;">{m.group(1)}</li>',
                html_content,
                flags=re.MULTILINE
            )
            html_content = re.sub(
                r'(<li[^>]*>.*?</li>\s*)+',
                lambda m: f'<ol style="margin: 10px 0; padding-left: 20px;">{m.group(0)}</ol>',
                html_content,
                flags=re.DOTALL
            )
            
            # 处理强调和加粗（修改这部分）
            # 先处理加粗，因为它可能包含斜体
            html_content = re.sub(
                r'\*\*([^*\n]+?)\*\*',
                lambda m: f'<strong style="font-weight: bold; color: #24292e; display: inline;">{m.group(1)}</strong>',
                html_content
            )
            # 再处理斜体
            html_content = re.sub(
                r'\*([^*\n]+?)\*',
                lambda m: f'<em style="font-style: italic; color: #24292e; display: inline;">{m.group(1)}</em>',
                html_content
            )
            
            # 处理链接
            html_content = re.sub(
                r'\[([^\]]+)\]\(([^\)]+)\)',
                lambda m: f'<a href="{m.group(2)}" style="color: #0366d6; text-decoration: none; word-break: break-all;">{m.group(1)}</a>',
                html_content
            )
            
            # 处理纯URL文本（不带方括号的URL）
            html_content = re.sub(
                r'(https?://[^\s<]+)',
                lambda m: f'<a href="{m.group(1)}" style="color: #0366d6; text-decoration: none; word-break: break-all;">{m.group(1)}</a>',
                html_content
            )
            
            # 处理分隔线
            html_content = re.sub(
                r'^-{3,}$',
                '<hr style="border: none; border-top: 1px solid #e1e4e8; margin: 20px 0;">',
                html_content,
                flags=re.MULTILINE
            )
            
            # 处理段落
            html_content = re.sub(
                r'([^\n]+)\n\n',
                lambda m: f'<p style="margin: 16px 0; line-height: 1.6;">{m.group(1)}</p>\n',
                html_content
            )
            
            # 使用BeautifulSoup处理HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 移除所有注释
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()
            
            # 移除所有script标签
            for script in soup.find_all('script'):
                script.decompose()
            
            # 移除所有style标签
            for style in soup.find_all('style'):
                style.decompose()
            
            # 移除所有link标签
            for link in soup.find_all('link'):
                link.decompose()
            
            # 移除所有iframe标签
            for iframe in soup.find_all('iframe'):
                iframe.decompose()
            
            # 移除所有form标签
            for form in soup.find_all('form'):
                form.decompose()
            
            # 移除所有input标签
            for input_tag in soup.find_all('input'):
                input_tag.decompose()
            
            # 移除所有button标签
            for button in soup.find_all('button'):
                button.decompose()
            
            # 处理图片标签，保留并修改为微信支持的格式
            for img in soup.find_all('img'):
                # 获取图片URL和替代文本
                src = img.get('src', '')
                alt = img.get('alt', '')
                
                # 如果是本地图片路径，需要上传到微信
                if src.startswith(('/', 'images/')):
                    try:
                        media_id = self.upload_temp_material(src)
                        # 更新图片URL为微信临时素材URL
                        img['src'] = f"https://api.weixin.qq.com/cgi-bin/media/get?access_token={self.get_access_token()}&media_id={media_id}"
                    except Exception as e:
                        print(f"上传图片失败: {str(e)}")
                        img.decompose()
                        continue
                
                # 添加图片说明
                if alt:
                    caption = soup.new_tag('p')
                    caption.string = alt
                    caption['style'] = 'text-align: center; color: #666; font-size: 14px;'
                    img.insert_after(caption)
            
            # 获取处理后的HTML内容，确保使用UTF-8编码
            processed_html = soup.encode(formatter='html5', encoding='utf-8').decode('utf-8')
            
            # 移除多余的空白行
            lines = [line.strip() for line in processed_html.split('\n') if line.strip()]
            processed_html = '\n'.join(lines)
            
            return processed_html
            
        except Exception as e:
            print(f"处理HTML内容时发生错误: {str(e)}")
            # 返回原始内容
            return html_content
            
    def _format_code_block(self, language, code):
        """格式化代码块
        
        Args:
            language (str): 代码语言
            code (str): 代码内容
            
        Returns:
            str: 格式化后的HTML代码块
        """
        # 移除开头和结尾的空行
        code = code.strip()
        
        # 构建代码块样式
        styles = {
            'container': (
                'background-color: #f6f8fa; '
                'border-radius: 6px; '
                'margin: 16px 0; '
                'padding: 16px; '
                'overflow-x: auto; '
                'font-family: Consolas, Monaco, "Andale Mono", monospace;'
            ),
            'header': (
                'color: #666; '
                'font-size: 12px; '
                'margin-bottom: 8px; '
                'font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;'
            ),
            'code': (
                'margin: 0; '
                'font-size: 14px; '
                'line-height: 1.45; '
                'white-space: pre-wrap; '
                'word-wrap: break-word; '
                'color: #24292e;'
            )
        }
        
        # 获取语言显示名称
        lang_display = language.upper() if language else 'CODE'
        
        # 构建HTML
        html = f'''
        <div style="{styles['container']}">
            <div style="{styles['header']}">{lang_display}</div>
            <pre style="{styles['code']}">{code}</pre>
        </div>
        '''
        
        return html
    
    def upload_temp_material(self, file_path, type='image'):
        """上传临时素材
        
        Args:
            file_path: 文件路径
            type: 素材类型，可选值：image、voice、video、thumb
            
        Returns:
            media_id: 媒体文件ID
        """
        token = self.get_access_token()
        url = f"{self.api_base_url}/cgi-bin/media/upload?access_token={token}&type={type}"
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
            
        with open(file_path, 'rb') as f:
            files = {'media': f}
            response = requests.post(url, files=files)
            
        if response.status_code != 200:
            raise Exception(f"上传临时素材失败: {response.text}")
            
        result = response.json()
        if "errcode" in result and result["errcode"] != 0:
            raise Exception(f"上传临时素材失败: {result['errmsg']}")
            
        return result["media_id"]

    def create_draft(self, title, html_content, author=None, thumb_media_id=None):
        """创建草稿
        
        Args:
            title (str): 文章标题
            html_content (str): HTML内容
            author (str): 作者名称
            thumb_media_id (str): 封面图片的 media_id
            
        Returns:
            str: 草稿的 media_id
        """
        token = self.get_access_token()
        url = f"{self.api_base_url}/cgi-bin/draft/add?access_token={token}"
        
        # 处理标题和作者编码
        if isinstance(title, bytes):
            title = title.decode('utf-8')
        if isinstance(author, bytes):
            author = author.decode('utf-8')
        
        # 处理HTML内容
        try:
            print("开始处理HTML内容...")
            processed_content = self.process_html_content(html_content)
            print(f"HTML内容处理完成，处理后长度: {len(processed_content)} 字节")
        except Exception as e:
            print(f"处理HTML内容时出错: {str(e)}")
            raise
            
        # 准备文章数据
        article_data = {
            "articles": [{
                "title": title,
                "author": author or "AI助手",
                "content": processed_content,
                "content_source_url": "",
                "digest": "",
                "need_open_comment": 0,
                "only_fans_can_comment": 0
            }]
        }
        
        # 如果有封面图，添加到文章数据中
        if thumb_media_id:
            article_data["articles"][0]["thumb_media_id"] = thumb_media_id
            
        # 打印请求数据预览
        print("请求数据预览:")
        print(f"- 标题长度: {len(title)} 字符")
        print(f"- 标题内容: {title}")
        print(f"- 内容长度: {len(processed_content)} 字符")
        print(f"- 作者: {author or 'AI助手'}")
        if thumb_media_id:
            print(f"- 封面图ID: {thumb_media_id}")
            
        try:
            # 发送请求
            headers = {
                'Content-Type': 'application/json; charset=utf-8'
            }
            # 使用ensure_ascii=False确保中文字符正确编码
            request_data = json.dumps(article_data, ensure_ascii=False).encode('utf-8')
            response = requests.post(url, data=request_data, headers=headers)
            
            print(f"收到API响应: HTTP {response.status_code}")
            
            # 尝试解析响应
            try:
                result = response.json()
                print(f"API返回结果: {json.dumps(result, ensure_ascii=False)}")
            except json.JSONDecodeError:
                print(f"API返回的不是有效的JSON: {response.text}")
                raise Exception(f"API返回的不是有效的JSON: {response.text}")
            
            # 检查响应状态
            if response.status_code != 200:
                error_msg = f"创建草稿失败: {response.text}"
                print(error_msg)
                raise Exception(error_msg)
            
            # 检查返回结果
            if "media_id" not in result:
                error_msg = f"创建草稿失败: {result.get('errmsg', '未知错误')}"
                print(error_msg)
                raise Exception(error_msg)
            
            print(f"草稿创建成功，media_id: {result['media_id']}")
            return result["media_id"]
            
        except requests.exceptions.RequestException as e:
            error_msg = f"发送请求失败: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"创建草稿失败: {str(e)}"
            print(error_msg)
            raise
    
    def publish_draft(self, media_id):
        """发布草稿"""
        token = self.get_access_token()
        url = f"{self.api_base_url}/cgi-bin/freepublish/submit?access_token={token}"
        
        data = {
            "media_id": media_id
        }
        
        response = requests.post(url, json=data)
        if response.status_code != 200:
            raise Exception(f"发布草稿失败: {response.text}")
        
        result = response.json()
        if "errcode" in result and result["errcode"] != 0:
            raise Exception(f"发布草稿失败: {result['errmsg']}")
        
        return result["publish_id"]
    
    def get_publish_status(self, publish_id):
        """获取发布状态"""
        token = self.get_access_token()
        url = f"{self.api_base_url}/cgi-bin/freepublish/get?access_token={token}"
        
        data = {
            "publish_id": publish_id
        }
        
        response = requests.post(url, json=data)
        if response.status_code != 200:
            raise Exception(f"获取发布状态失败: {response.text}")
        
        result = response.json()
        if "errcode" in result and result["errcode"] != 0:
            raise Exception(f"获取发布状态失败: {result['errmsg']}")
        
        return result
    
    def publish_html(self, title, html_content, author=None, thumb_media_id=None):
        """发布HTML内容到微信公众号
        
        Args:
            title (str): 文章标题
            html_content (str): HTML内容
            author (str): 作者名称
            thumb_media_id (str): 封面图片的 media_id
            
        Returns:
            dict: 包含发布结果的字典
        """
        try:
            print("开始创建微信公众号草稿...")
            
            # 确保标题是UTF-8编码的字符串
            if isinstance(title, bytes):
                title = title.decode('utf-8')
                
            print(f"文章标题: {title}")
            
            # 处理HTML内容
            print("开始处理HTML内容...")
            
            # 确保内容是UTF-8编码
            if isinstance(html_content, bytes):
                html_content = html_content.decode('utf-8')
            
            # 使用 BeautifulSoup 处理 HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 移除所有注释
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()
            
            # 移除所有script和style标签
            for tag in soup.find_all(['script', 'style']):
                tag.decompose()
            
            # 处理图片标签
            for img in soup.find_all('img'):
                # 获取图片URL和替代文本
                src = img.get('src', '')
                alt = img.get('alt', '')
                
                # 如果是本地图片路径，需要上传到微信
                if src.startswith(('/', 'images/')):
                    try:
                        media_id = self.upload_temp_material(src)
                        # 更新图片URL为微信临时素材URL
                        img['src'] = f"https://api.weixin.qq.com/cgi-bin/media/get?access_token={self.get_access_token()}&media_id={media_id}"
                    except Exception as e:
                        print(f"上传图片失败: {str(e)}")
                        img.decompose()
                        continue
                
                # 添加图片说明
                if alt:
                    caption = soup.new_tag('p')
                    caption.string = alt
                    caption['style'] = 'text-align: center; color: #666; font-size: 14px;'
                    img.insert_after(caption)
            
            # 获取处理后的HTML内容，确保使用UTF-8编码
            processed_html = soup.encode(formatter='html5', encoding='utf-8').decode('utf-8')
            
            # 移除多余的空白行
            lines = [line.strip() for line in processed_html.split('\n') if line.strip()]
            processed_html = '\n'.join(lines)
            
            print(f"HTML内容处理完成，处理后长度: {len(processed_html)} 字节")
            
            # 准备文章数据
            article_data = {
                "articles": [{
                    "title": title,
                    "author": author or os.getenv('AUTHOR_NAME', 'AI助手'),
                    "content": processed_html,
                    "content_source_url": "",
                    "digest": "",
                    "show_cover_pic": 0,
                    "need_open_comment": 0,
                    "only_fans_can_comment": 0
                }]
            }
            
            # 如果提供了封面图片ID，添加到文章数据中
            if thumb_media_id:
                article_data["articles"][0]["thumb_media_id"] = thumb_media_id
            
            # 获取access_token
            token = self.get_access_token()
            
            # 创建草稿
            url = f"{self.api_base_url}/cgi-bin/draft/add?access_token={token}"
            
            # 打印请求数据预览
            print("请求数据预览:")
            print(f"- 标题长度: {len(title)} 字符")
            print(f"- 内容长度: {len(processed_html)} 字符")
            print(f"- 作者: {author}")
            if thumb_media_id:
                print(f"- 封面图ID: {thumb_media_id}")
            
            # 发送请求
            headers = {
                'Content-Type': 'application/json; charset=utf-8'
            }
            response = requests.post(
                url,
                data=json.dumps(article_data, ensure_ascii=False).encode('utf-8'),
                headers=headers
            )
            
            print(f"收到API响应: HTTP {response.status_code}")
            
            # 解析响应
            try:
                result = response.json()
                print(f"API返回结果: {json.dumps(result, ensure_ascii=False)}")
            except json.JSONDecodeError:
                print(f"API返回的不是有效的JSON: {response.text}")
                return {"success": False, "error": "API返回的不是有效的JSON"}
            
            if "media_id" in result:
                media_id = result["media_id"]
                print(f"草稿创建成功，media_id: {media_id}")
                return {
                    "success": True,
                    "status": {
                        "media_id": media_id,
                        "publish_status": "draft_created"
                    }
                }
            else:
                error_msg = f"创建草稿失败: {result.get('errmsg', '未知错误')}"
                print(error_msg)
                return {"success": False, "error": error_msg}
                
        except Exception as e:
            error_msg = f"创建草稿失败: {str(e)}"
            print(error_msg)
            return {"success": False, "error": error_msg}

# 测试代码
if __name__ == "__main__":
    publisher = WeixinPublisher()
    
    # 测试发布
    with open('output.html', 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    result = publisher.publish_html("测试文章", html_content)
    print(json.dumps(result, ensure_ascii=False, indent=2)) 