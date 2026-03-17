#!/usr/bin/env python3
"""
检查CodeFlow可用模型
"""
import requests
import yaml
import sys
from pathlib import Path

# 读取配置
config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

codeflow_config = config.get('models', {}).get('codeflow', {})
base_url = codeflow_config.get('base_url', 'https://codeflow.asia')
api_key = codeflow_config.get('api_key', '')

print("=" * 80)
print("CodeFlow 模型检查")
print("=" * 80)
print(f"\nAPI端点: {base_url}")
print(f"API密钥: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else ''}")

# 尝试获取模型列表
print("\n" + "=" * 80)
print("正在检查可用模型...")
print("=" * 80)

try:
    # OpenAI兼容格式的模型列表API
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    response = requests.get(
        f'{base_url}/v1/models',
        headers=headers,
        timeout=30
    )
    
    if response.status_code == 200:
        data = response.json()
        models = data.get('data', [])
        
        print(f"\n✅ 连接成功！发现 {len(models)} 个模型:\n")
        
        for i, model in enumerate(models, 1):
            model_id = model.get('id', 'unknown')
            model_name = model.get('name', model_id)
            description = model.get('description', 'N/A')
            print(f"  {i}. {model_id}")
            print(f"     名称: {model_name}")
            print(f"     描述: {description}")
            print()
    else:
        print(f"\n❌ 获取模型列表失败")
        print(f"   状态码: {response.status_code}")
        print(f"   响应: {response.text[:200]}")
        
        # 尝试测试简单请求
        print("\n" + "=" * 80)
        print("尝试测试对话接口...")
        print("=" * 80)
        
        test_payload = {
            'model': 'default',
            'messages': [{'role': 'user', 'content': 'Hello'}],
            'max_tokens': 10
        }
        
        test_response = requests.post(
            f'{base_url}/v1/chat/completions',
            headers=headers,
            json=test_payload,
            timeout=30
        )
        
        print(f"\n测试请求状态码: {test_response.status_code}")
        if test_response.status_code == 200:
            print("✅ 对话接口可用")
        else:
            print(f"❌ 对话接口测试失败: {test_response.text[:200]}")

except requests.exceptions.ConnectionError as e:
    print(f"\n❌ 连接失败: 无法连接到 {base_url}")
    print(f"   错误: {e}")
except requests.exceptions.Timeout:
    print(f"\n❌ 连接超时: {base_url}")
except Exception as e:
    print(f"\n❌ 检查失败: {e}")

print("\n" + "=" * 80)
