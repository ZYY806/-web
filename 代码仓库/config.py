# -*- coding: utf-8 -*-
"""
配置文件 —— 数据库连接、网站密钥、百度地图密钥都放在这里。

【关于安全】本项目的 API 密钥（如百度地图 AK）属于敏感信息，
比赛要求不得出现在公开仓库里，因此统一通过环境变量读取：
  1. 在项目根目录新建一个 .env 文件（内容见 .env.example）；
  2. 程序启动时由 python-dotenv 自动加载到环境变量；
  3. 下面的配置若读不到环境变量，则回退到本地默认值（方便本机直接跑）。
"""

import os

try:
    from dotenv import load_dotenv
    load_dotenv()          # 自动读取项目根目录下的 .env 文件
except Exception:
    pass

# ---------- MySQL 数据库连接信息 ----------
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")      # 本机 MySQL root 密码为空，留空即可
DB_NAME = os.getenv("DB_NAME", "dezhou_tour")
DB_PORT = int(os.getenv("DB_PORT", "3306"))

# ---------- 网站登录会话密钥（务必改成只有你自己知道的长字符串） ----------
SECRET_KEY = os.getenv("SECRET_KEY", "dezhou-tour-2026-three-pifu-jiang")

# ---------- 百度地图开放平台 AK（用于 /map 地图页，敏感信息，必须走环境变量） ----------
# 申请地址：https://lbsyun.baidu.com/apiconsole/key
BAIDU_MAP_AK = os.getenv("BAIDU_MAP_AK", "")

# ---------- 联系我们页的接收邮箱（访客通过留言表单联系团队） ----------
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "sanpifu@dezhou.example")
