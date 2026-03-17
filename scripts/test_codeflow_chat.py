#!/usr/bin/env python3
"""
测试CodeFlow模型对话
"""
import requests
import yaml
from pathlib import Path

# 读取配置
config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

codeflow_config = config.get('models', {}).get('codeflow', {})
base_url = codeflow_config.get('base_url', 'https://codeflow.asia')
api_key = codeflow_config.get('api_key', '')
default_model = codeflow_config.get('default_model', 'claude-sonnet-4-6')

print("=" * 80)
print("CodeFlow 对话测试")
print("=" * 80)
print(f"\n模型: {default_model}")

headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
}

payload = {
    'model': default_model,
    'messages': [
        {'role': 'system', 'content': '你是一个专业的量化交易分析师。'},
        {'role': 'user', 'content': '请简要分析当前A股市场的技术面前景。'}
    ],
    'max_tokens': 500,
    'temperature': 0.7
}

print("\n发送请求...")
print("-" * 80)

try:
    response = requests.post(
        f'{base_url}/v1/chat/completions',
        headers=headers,
        json=payload,
        timeout=60
    )
    
    if response.status_code == 200:
        data = response.json()
        content = data['choices'][0]['message']['content']
        usage = data.get('usage', {})
        
        print(f"\n✅ 请求成功！")
        print(f"\n响应内容:\n{'-'*40}")
        print(content)
        print(f"{'-'*40}")
        print(f"\nToken使用:")
        print(f"  Prompt: {usage.get('prompt_tokens', 'N/A')}")
        print(f"  Completion: {usage.get('completion_tokens', 'N/A')}")
        print(f"  Total: {usage.get('total_tokens', 'N/A')}")
    else:
        print(f"\n❌ 请求失败")
        print(f"   状态码: {response.status_code}")
        print(f"   响应: {response.text[:500]}")

except Exception as e:
    print(f"\n❌ 测试失败: {e}")

print("\n" + "=" * 80)
