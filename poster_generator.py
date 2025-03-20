#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import time
import requests
from dotenv import load_dotenv

class PosterGenerator:
    """海报生成器类"""
    
    def __init__(self):
        """初始化海报生成器"""
        # 加载环境变量
        load_dotenv()
        self.api_key = os.getenv('DASHSCOPE_API_KEY')
        if not self.api_key:
            raise ValueError("请在.env文件中设置DASHSCOPE_API_KEY")
            
        # API配置
        self.url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable"
        }

    def generate(
        self,
        title: str,
        sub_title: str,
        body_text: str,
        prompt_text_zh: str,
        wh_ratio: str = "竖版",
        lora_name: str = "童话油画",
        lora_weight: float = 0.8,
        ctrl_ratio: float = 0.7,
        ctrl_step: float = 0.7,
        generate_num: int = 1
    ) -> dict:
        """生成海报
        
        Args:
            title: 主标题
            sub_title: 副标题
            body_text: 正文内容
            prompt_text_zh: 中文提示词
            wh_ratio: 宽高比，可选 "竖版" 或 "横版"
            lora_name: 预设背景风格
            lora_weight: lora权重，范围0-1
            ctrl_ratio: 控制比例，范围0-1
            ctrl_step: 控制步长，范围0-1
            generate_num: 生成数量，范围1-4
            
        Returns:
            dict: 包含生成结果的字典，包括 url 等信息
        """
        # 请求数据
        data = {
            "model": "wanx-poster-generation-v1",
            "input": {
                "title": title,
                "sub_title": sub_title,
                "body_text": body_text,
                "prompt_text_zh": prompt_text_zh,
                "wh_ratios": wh_ratio,
                "lora_name": lora_name,
                "lora_weight": lora_weight,
                "ctrl_ratio": ctrl_ratio,
                "ctrl_step": ctrl_step,
                "generate_mode": "generate",
                "generate_num": generate_num
            },
            "parameters": {}
        }

        print("\n发送请求:")
        print(f"URL: {self.url}")
        print(f"Headers: {json.dumps({k: v if k != 'Authorization' else '[HIDDEN]' for k, v in self.headers.items()}, indent=2)}")
        print(f"Data: {json.dumps(data, indent=2, ensure_ascii=False)}")

        # 发送请求
        response = requests.post(self.url, headers=self.headers, json=data)
        print(f"\n响应状态码: {response.status_code}")
        
        if response.status_code != 200:
            print(f"错误响应: {response.text}")
            raise Exception(f"请求失败: {response.status_code}")

        result = response.json()
        print(f"响应数据: {json.dumps(result, indent=2, ensure_ascii=False)}")

        # 获取任务ID
        task_id = result.get("output", {}).get("task_id")
        if not task_id:
            raise Exception("未获取到任务ID")
            
        print(f"\n异步任务已提交，任务ID: {task_id}")

        # 轮询检查任务状态
        status_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
        while True:
            time.sleep(20)  # 每20秒检查一次状态
            print(f"\n检查任务状态: {task_id}")
            
            status_response = requests.get(status_url, headers=self.headers)
            if status_response.status_code != 200:
                print(f"检查状态失败: {status_response.text}")
                raise Exception(f"检查状态失败: {status_response.status_code}")
            
            status_result = status_response.json()
            print(f"Status Result: {json.dumps(status_result, indent=2, ensure_ascii=False)}")
            
            task_status = status_result.get("output", {}).get("task_status")
            if task_status == "SUCCEEDED":
                try:
                    render_urls = status_result["output"]["render_urls"]
                    if render_urls and len(render_urls) > 0:
                        image_url = render_urls[0]
                        print(f"\n图片生成成功: {image_url}")
                        return {"url": image_url, "task_id": task_id}
                    else:
                        raise Exception("未找到生成的图片URL")
                except (KeyError, IndexError) as e:
                    print(f"无法从响应中获取图片URL: {json.dumps(status_result, indent=2, ensure_ascii=False)}")
                    raise Exception(f"生成的响应格式不正确: {str(e)}")
            
            elif task_status == "FAILED":
                error_msg = status_result.get("output", {}).get("message", "未知错误")
                raise Exception(f"生成图片失败: {error_msg}")
            
            print("图片生成中...")

def main():
    """测试海报生成"""
    try:
        poster_gen = PosterGenerator()
        result = poster_gen.generate(
            title="春节快乐",
            sub_title="家庭团聚，共享天伦之乐",
            body_text="春节是中国最重要的传统节日之一，它象征着新的开始和希望",
            prompt_text_zh="灯笼，小猫，梅花",
            wh_ratio="竖版",
            lora_name="童话油画",
            lora_weight=0.8,
            ctrl_ratio=0.7,
            ctrl_step=0.7,
            generate_num=1
        )
        print(f"\n生成成功: {result['url']}")
    except Exception as e:
        print(f"生成失败: {str(e)}")

if __name__ == "__main__":
    main() 