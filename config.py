# -*- coding: utf-8 -*-
"""
配置文件 —— 网站密钥、地图 AK、大模型 Key 都放在这里。

【关于数据库】本站已经不再使用 MySQL：
  全部文旅内容写在 data_store.py 里，游客产生的帖子/留言存在 data/store.json，
  所以这里没有任何数据库连接配置，装好 Flask 就能直接跑。

【关于安全】本项目的 API 密钥（如百度地图 AK、大模型 Key）属于敏感信息，
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

# ---------- 网站登录会话密钥（务必改成只有你自己知道的长字符串） ----------
SECRET_KEY = os.getenv("SECRET_KEY", "dezhou-tour-2026-three-pifu-jiang")

# ---------- 百度地图开放平台 AK（用于 /map 地图页，敏感信息，必须走环境变量） ----------
# 申请地址：https://lbsyun.baidu.com/apiconsole/key
BAIDU_MAP_AK = os.getenv("BAIDU_MAP_AK", "")

# ---------- 联系我们页的接收邮箱（访客通过留言表单联系团队） ----------
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "detuzhixing@dezhou.example")

# ---------- QQ邮箱 SMTP（"联系我们"真实发信，敏感信息走环境变量） ----------
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.qq.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "true").lower() in ("1", "true", "yes")

# ---------- AI 智能问答（大模型，OpenAI 兼容协议） ----------
# 不填 AI_API_KEY 时，问答 / 规划 / 拍照都会自动降级为「站内数据版」，网站照常能用。
# 火山方舟：https://ark.cn-beijing.volces.com/api/v3 ，模型填接入点 ID 或模型名
# DeepSeek：https://api.deepseek.com ，模型 deepseek-flash
# 智谱：https://open.bigmodel.cn/api/paas/v4 ，模型 glm-4-flash
AI_API_BASE = os.getenv("AI_API_BASE", "https://ark.cn-beijing.volces.com/api/v3")
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "doubao-seed-1-6-251015")
# 多模态识图模型（拍照识德州 / 拍照生成路线）。留空则与 AI_MODEL 相同
AI_VISION_MODEL = os.getenv("AI_VISION_MODEL", "")
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "25"))
AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.4"))
