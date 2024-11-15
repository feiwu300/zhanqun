import argparse
import dns.resolver
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
import sys
import threading
import os

# 禁用控制台错误输出
sys.stderr = open(os.devnull, 'w')

# 解析 URL 中的协议部分（http:// 或 https://）
def clean_url(url):
    return re.sub(r'^https?://', '', url)

# 执行 DNS 查询，获取 A 记录，增加重试机制
def query_dns(domain, retries=5, delay=2):
    for attempt in range(retries):
        try:
            # 尝试解析 A 记录
            answers = dns.resolver.resolve(domain, 'A', lifetime=10)  # 增加超时
            return [rdata.to_text() for rdata in answers]
        except dns.resolver.NoAnswer:
            try:
                answers = dns.resolver.resolve(domain, 'AAAA', lifetime=10)
                return [rdata.to_text() for rdata in answers]
            except Exception:
                return []  # 解析失败时返回空列表
        except Exception:
            time.sleep(delay)  # 等待后重试
    return []  # 如果重试次数用尽，返回空列表

# 处理单个 URL，查询 DNS A 记录并显示成功的域名和 A 记录
def process_url(url, output_counter, lock):
    try:
        domain = clean_url(url)
        a_records = query_dns(domain)
        if a_records:
            # 成功解析 A 记录，更新计数器
            with lock:
                for ip in a_records:
                    output_counter[ip] += 1
                    print(f"域名: {domain} | A 记录: {ip}")  # 控制台显示域名和 A 记录
    except Exception:
        pass  # 错误信息不输出到控制台

# 使用线程池处理 URL 列表
def process_urls_concurrently(urls, max_threads, output_counter):
    max_threads = min(max_threads, len(urls))  # 确保线程数不超过 URL 数量
    lock = threading.Lock()  # 用于线程同步
    with ThreadPoolExecutor(max_threads) as executor:
        # 提交任务并更新计数器
        futures = [executor.submit(process_url, url, output_counter, lock) for url in urls]
        # 等待所有任务完成
        for future in as_completed(futures):
            try:
                future.result()  # 获取每个线程的结果以捕获异常
            except Exception:
                pass  # 捕获异常，但不输出错误信息

# 确保目录存在
def ensure_directory_exists(file_path):
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

# 输出统计结果到文件，按 IP 数量排序，且只输出数量 > 2 的 IP
def write_sorted_output(output_counter, output_file):
    try:
        # 排序并输出 IP 和对应的数量，按数量降序排列
        sorted_ips = sorted(output_counter.items(), key=lambda x: x[1], reverse=True)
        with open(output_file, 'w', encoding='utf-8') as f:  # 使用 'w' 模式覆盖文件
            for ip, count in sorted_ips:
                # 只输出数量大于 2 的 IP
                if count > 2:
                    f.write(f"地址：{ip} | 数量：{count}\n")  # 格式化输出 IP 和数量
    except Exception as e:
        print(f"写入文件失败: {e}")  # 错误时打印信息

# 主函数：解析命令行参数并执行任务
def main():
    parser = argparse.ArgumentParser(description="获取网站或域名的真实IP")
    parser.add_argument('-f', '--file', type=str, required=True, help="包含 URL 的文件路径")
    parser.add_argument('-o', '--output', type=str, required=True, help="输出结果文件路径")
    parser.add_argument('-t', '--threads', type=int, default=100, help="最大并发线程数，默认 100")
    args = parser.parse_args()

    # 读取 URL 文件
    try:
        with open(args.file, 'r') as f:
            urls = [line.strip() for line in f.readlines()]
    except Exception as e:
        print(f"读取文件失败: {e}")
        sys.exit(1)  # 如果文件读取失败，退出程序

    # 输出文件初始化
    ensure_directory_exists(args.output)  # 确保输出目录存在
    output_counter = Counter()  # 统计每个 IP 的数量

    # 执行任务并获取统计结果
    start_time = time.time()

    # 处理 URL
    process_urls_concurrently(urls, args.threads, output_counter)

    # 写入排序后的结果到文件
    write_sorted_output(output_counter, args.output)

    # 输出任务完成信息
    print(f"\n任务已完成！")
    print(f"结果已保存到 {args.output}")
    print(f"总共耗时: {time.time() - start_time:.2f} 秒")

if __name__ == '__main__':
    main()
