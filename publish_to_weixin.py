#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import argparse
from weixin_publisher import WeixinPublisher
from dotenv import load_dotenv
import traceback
import json

def publish(html='output.html', title=None, author=None, test=False, debug=False, thumb_media_id=None):
    """可被导入并调用的发布函数
    
    参数:
        html (str): HTML文件路径
        title (str): 文章标题，如果不提供则从HTML中提取
        author (str): 作者名称，如果不提供则使用配置文件中的值
        test (bool): 测试模式，不实际创建草稿
        debug (bool): 显示调试信息
        thumb_media_id (str): 封面图片的 media_id
        
    返回:
        bool: 创建草稿成功返回True，失败返回False
    """
    try:
        # 加载环境变量
        load_dotenv()
        
        print("开始准备创建微信公众号草稿...")
        
        # 检查输出文件是否存在
        html_file = html
        if not os.path.exists(html_file):
            print(f"错误: HTML文件不存在 - {html_file}")
            return False
            
        # 读取HTML文件，确保使用UTF-8编码
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
                
            # 检查内容是否为空
            if not html_content.strip():
                print(f"错误: HTML文件内容为空 - {html_file}")
                return False
                
            # 打印前100个字符用于调试
            if debug:
                print("\nHTML内容预览（前100个字符）:")
                print(html_content[:100])
                print("...")
                
        except UnicodeDecodeError:
            print(f"错误: HTML文件编码不是UTF-8，尝试使用其他编码...")
            # 尝试使用其他编码
            encodings = ['gbk', 'gb2312', 'gb18030', 'latin1']
            for encoding in encodings:
                try:
                    with open(html_file, 'r', encoding=encoding) as f:
                        html_content = f.read()
                    print(f"成功使用 {encoding} 编码读取文件")
                    # 转换为UTF-8
                    html_content = html_content.encode(encoding).decode('utf-8')
                    break
                except:
                    continue
            else:
                print("错误: 无法正确读取HTML文件，请确保文件编码正确")
                return False
            
        # 尝试从HTML中提取标题（如果未提供）
        if not title:
            import re
            title_match = re.search(r'<title>(.*?)</title>', html_content)
            if title_match:
                title = title_match.group(1)
            else:
                # 尝试获取第一个h1标签内容
                h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', html_content)
                if h1_match:
                    title = h1_match.group(1)
                else:
                    title = "项目分析报告"
                
        # 获取作者
        author = author or os.getenv('AUTHOR_NAME', 'AI助手')
        
        print(f"准备创建草稿:")
        print(f"- 标题: {title}")
        print(f"- 作者: {author}")
        print(f"- HTML长度: {len(html_content)} 字节")
        if thumb_media_id:
            print(f"- 封面图片ID: {thumb_media_id}")
        
        # 创建发布器实例
        print("初始化微信发布器...")
        publisher = WeixinPublisher()
        
        # 验证微信配置
        print("微信配置:")
        print(f"- APP_ID: {publisher.app_id[:6]}***")
        print(f"- APP_SECRET: {publisher.app_secret[:6]}***")
        print(f"- 开放评论: {publisher.need_open_comment}")
        print(f"- 仅粉丝评论: {publisher.only_fans_can_comment}")
        
        # 测试模式
        if test:
            print("\n测试模式：验证连接微信API...")
            token = publisher.get_access_token()
            print(f"连接成功！获取access_token: {token[:10]}***")
            print("测试完成，未执行实际创建草稿。")
            return True
        
        # 获取access_token测试
        print("测试获取access_token...")
        token = publisher.get_access_token()
        print(f"获取access_token成功: {token[:10]}***")
        
        # 如果是调试模式，显示部分HTML内容
        if debug:
            print("\n调试信息 - HTML内容片段:")
            print("-" * 50)
            print(html_content[:500] + "...\n[内容已截断]")
            print("-" * 50)
        
        # 创建草稿
        print("\n开始创建微信公众号草稿...")
        result = publisher.publish_html(title, html_content, author, thumb_media_id=thumb_media_id)
        
        if result['success']:
            print(f"成功创建微信公众号草稿！")
            print(f"文章标题: {title}")
            print(f"草稿状态: {result['status']['publish_status']}")
            # 输出详细信息（如果是调试模式）
            if debug:
                print("\n调试信息 - 创建结果详情:")
                print(json.dumps(result, indent=2, ensure_ascii=False))
            return True
        else:
            print(f"创建草稿失败: {result.get('error', '未知错误')}")
            return False
    
    except Exception as e:
        print(f"创建草稿过程中发生错误:")
        traceback.print_exc()
        return False

def main():
    """命令行入口函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='发布HTML文章到微信公众号')
    parser.add_argument('--html', type=str, default='output.html', help='HTML文件路径')
    parser.add_argument('--title', type=str, help='文章标题，默认从HTML中提取')
    parser.add_argument('--author', type=str, help='作者名称，默认使用配置文件中的值')
    parser.add_argument('--test', action='store_true', help='测试模式，不实际创建草稿')
    parser.add_argument('--debug', action='store_true', help='显示调试信息')
    parser.add_argument('--thumb-media-id', type=str, help='封面图片的 media_id')
    args = parser.parse_args()
    
    # 调用发布函数
    success = publish(
        html=args.html,
        title=args.title,
        author=args.author,
        test=args.test,
        debug=args.debug,
        thumb_media_id=args.thumb_media_id
    )
    
    # 返回状态码
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 