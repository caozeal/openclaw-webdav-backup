#!/usr/bin/env python3
"""
WebDAV 备份脚本
将 OpenClaw 工作目录备份到 WebDAV 服务器
"""

import os
import sys
import argparse
import tarfile
import datetime
import json
from pathlib import Path
import urllib.request
import urllib.error


def load_openclaw_config():
    """从 openclaw.json 加载 webdav-backup 配置"""
    config_paths = [
        os.path.expanduser('~/.openclaw/openclaw.json'),
        os.path.expanduser('~/.config/openclaw/openclaw.json'),
    ]
    
    for config_path in config_paths:
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                # 查找 webdav-backup 技能配置
                skills = config.get('skills', {}).get('entries', {})
                skill_config = skills.get('webdav-backup', {})
                
                if skill_config and skill_config.get('enabled', False):
                    return skill_config.get('env', {})
            except Exception:
                pass
    
    return {}


# 加载 openclaw.json 配置
openclaw_env = load_openclaw_config()

# 配置 - 优先级: 环境变量 > openclaw.json > 默认值
DEFAULT_WORKSPACE = os.path.expanduser('~/.openclaw/workspace')
WORKSPACE = os.environ.get('OPENCLAW_WORKSPACE', DEFAULT_WORKSPACE)
WEBDAV_URL = os.environ.get('WEBDAV_URL', openclaw_env.get('WEBDAV_URL', ''))
WEBDAV_USER = os.environ.get('WEBDAV_USERNAME', openclaw_env.get('WEBDAV_USERNAME', ''))
WEBDAV_PASS = os.environ.get('WEBDAV_PASS', 
              os.environ.get('WEBDAV_PASSWORD', 
              openclaw_env.get('WEBDAV_PASS', 
              openclaw_env.get('WEBDAV_PASSWORD', ''))))

def check_config():
    """检查 WebDAV 配置"""
    if not WEBDAV_URL or not WEBDAV_USER or not WEBDAV_PASS:
        print("❌ WebDAV 配置缺失")
        print("")
        print("配置方式一：编辑 ~/.openclaw/openclaw.json")
        print('  {')
        print('    "skills": {')
        print('      "entries": {')
        print('        "webdav-backup": {')
        print('          "enabled": true,')
        print('          "env": {')
        print('            "WEBDAV_URL": "https://dav.jianguoyun.com/dav/",')
        print('            "WEBDAV_USERNAME": "your-email",')
        print('            "WEBDAV_PASSWORD": "your-password"')
        print('          }')
        print('        }')
        print('      }')
        print('    }')
        print('  }')
        print("")
        print("配置方式二：设置环境变量")
        print("  export WEBDAV_URL='https://dav.jianguoyun.com/dav/'")
        print("  export WEBDAV_USERNAME='your-email'")
        print("  export WEBDAV_PASSWORD='your-password'")
        return False
    
    print(f"📡 WebDAV URL: {WEBDAV_URL}")
    print(f"👤 用户名: {WEBDAV_USER}")
    return True

def create_backup(source_dir, backup_name=None):
    """创建备份压缩包"""
    timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    if backup_name:
        backup_file = f"{backup_name}-{timestamp}.tar.gz"
    else:
        backup_file = f"openclaw-backup-{timestamp}.tar.gz"
    
    backup_path = Path('/tmp') / backup_file
    
    print(f"📦 正在创建备份: {backup_file}")
    
    with tarfile.open(backup_path, 'w:gz') as tar:
        source = Path(source_dir)
        if source.exists():
            tar.add(source, arcname=source.name)
            print(f"✅ 已添加: {source_dir}")
        else:
            print(f"⚠️  目录不存在: {source_dir}")
    
    # 显示文件大小
    size = backup_path.stat().st_size
    print(f"📊 备份大小: {size / 1024 / 1024:.2f} MB")
    
    return backup_path

def upload_to_webdav(local_file, remote_name):
    """上传到 WebDAV 服务器"""
    print(f"☁️  正在上传到 WebDAV...")
    
    remote_url = WEBDAV_URL.rstrip('/') + '/' + remote_name
    
    # 创建密码管理器
    password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    password_mgr.add_password(None, WEBDAV_URL, WEBDAV_USER, WEBDAV_PASS)
    
    handler = urllib.request.HTTPBasicAuthHandler(password_mgr)
    opener = urllib.request.build_opener(handler)
    
    try:
        with open(local_file, 'rb') as f:
            data = f.read()
        
        req = urllib.request.Request(remote_url, data=data, method='PUT')
        req.add_header('Content-Type', 'application/octet-stream')
        
        with opener.open(req) as response:
            if response.status in [200, 201, 204]:
                print(f"✅ 上传成功: {remote_name}")
                return True
            else:
                print(f"❌ 上传失败: HTTP {response.status}")
                return False
                
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP 错误: {e.code} - {e.reason}")
        if e.code == 404:
            print("💡 提示: 404 错误通常表示 WebDAV 路径不存在")
            print("   请检查坚果云网页端是否有对应文件夹")
            print("   路径示例: https://dav.jianguoyun.com/dav/openclaw-backup/")
        elif e.code == 401:
            print("💡 提示: 401 错误表示认证失败")
            print("   请检查用户名和密码是否正确")
            print("   注意: 坚果云需要使用'应用密码'而非登录密码")
        return False
    except Exception as e:
        print(f"❌ 上传失败: {e}")
        return False

def list_backups():
    """列出 WebDAV 上的备份文件"""
    print("📋 WebDAV 备份列表")
    print("注意: 此功能需要 WebDAV 服务器支持 PROPFIND 方法")
    print(f"WebDAV URL: {WEBDAV_URL}")

def main():
    parser = argparse.ArgumentParser(description='WebDAV 备份工具')
    parser.add_argument('--source', '-s', default=WORKSPACE, help='要备份的源目录')
    parser.add_argument('--name', '-n', default='openclaw-backup', help='备份文件名前缀')
    parser.add_argument('--list', '-l', action='store_true', help='列出备份')
    parser.add_argument('--restore', '-r', help='恢复指定备份')
    
    args = parser.parse_args()
    
    if args.list:
        list_backups()
        return
    
    if args.restore:
        print("🚧 恢复功能开发中...")
        return
    
    # 检查配置
    if not check_config():
        sys.exit(1)
    
    # 创建备份
    backup_file = create_backup(args.source, args.name)
    
    # 上传到 WebDAV
    remote_name = backup_file.name
    if upload_to_webdav(backup_file, remote_name):
        # 上传成功后删除本地临时文件
        backup_file.unlink()
        print(f"✅ 备份完成: {remote_name}")
    else:
        print(f"⚠️  上传失败，本地备份保留在: {backup_file}")
        sys.exit(1)

if __name__ == '__main__':
    main()
