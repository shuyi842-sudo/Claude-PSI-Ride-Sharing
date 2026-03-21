"""
PSI拼车系统启动助手
帮助用户启动服务器并获取访问地址
"""

import socket
import subprocess
import sys
import webbrowser
from pathlib import Path


def get_local_ip():
    """获取本机局域网IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        print(f"获取IP失败: {e}")
        return None


def print_banner():
    """打印启动横幅"""
    print()
    print("=" * 60)
    print("  🚗 无人驾驶拼车系统 - 局域网启动")
    print("  基于MP-TPSI隐私保护协议")
    print("=" * 60)
    print()


def print_access_info(ip):
    """打印访问信息"""
    if ip is None:
        print("❌ 无法获取本机IP地址")
        print("   请检查网络连接")
        return

    print("📱 手机访问步骤:")
    print()
    print("1. 确保手机和电脑连接到同一个WiFi")
    print("2. 在手机浏览器中打开以下地址:")
    print()
    print(f"   ╔══════════════════════════════════════╗")
    print(f"   ║   http://{ip}:5000                  ║")
    print(f"   ╚══════════════════════════════════════╝")
    print()
    print("📊 功能选择:")
    print("   • 乘客端 - 发布出行需求，匹配车辆")
    print("   • 车辆端 - 注册车辆，查看乘客")
    print("   • 管理后台 - 查看统计数据")
    print()
    print("💡 提示:")
    print("   • 乘客ID和车辆ID可以自定义（如: P001, V001）")
    print("   • 起点和终点输入相同区域更容易匹配")
    print("   • 匹配成功后会显示6位验证码")
    print()


def open_browser():
    """在电脑浏览器打开首页"""
    try:
        webbrowser.open('http://localhost:5000')
        print("✓ 已在电脑浏览器打开: http://localhost:5000")
    except:
        print("⚠ 无法自动打开浏览器，请手动访问")


def start_server():
    """启动Flask服务器"""
    print("🚀 正在启动服务器...")
    print()

    try:
        # 使用subprocess启动app.py，这样可以捕获输出
        subprocess.run(
            [sys.executable, "app.py"],
            check=True
        )
    except KeyboardInterrupt:
        print()
        print("=" * 60)
        print("  ⏹  服务器已停止")
        print("=" * 60)
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)


def main():
    """主函数"""
    print_banner()

    # 获取本机IP
    ip = get_local_ip()

    # 打印访问信息
    print_access_info(ip)

    # 询问是否打开浏览器
    try:
        response = input("是否在电脑浏览器打开首页？(Y/n，默认Y): ").strip().lower()
        if response != 'n':
            open_browser()
    except:
        # 如果不支持输入，默认打开
        open_browser()

    print()
    print("⏳ 按 Ctrl+C 停止服务器")
    print("-" * 60)
    print()

    # 启动服务器
    start_server()


if __name__ == "__main__":
    main()
