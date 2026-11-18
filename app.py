# -*- coding: utf-8 -*-
"""
============================================================
  德州文旅 ·「德途智行 · AI智游德州」
  主程序 app.py —— 网站全部后台逻辑

  运行步骤（不再需要 MySQL！）：
    第1步：pip install -r requirements.txt
    第2步：python app.py
    第3步：浏览器打开 http://127.0.0.1:5000

  数据说明：
    全站文旅数据都写在 data_store.py 里（纯 Python 数据，开箱即用）。
    游客产生的帖子 / 评论 / 留言会存到 data/store.json，重启不丢。
    不再依赖任何数据库服务，双击 start.bat 就能直接跑。

  环境变量：会话密钥 / 百度地图 AK / 大模型 Key 都在 config.py 读取，
            说明见 .env.example。
============================================================
"""

import os
import re
import json
import time
import uuid
import smtplib
import ssl
from email.mime.text import MIMEText
from email.header import Header
from flask import (Flask, render_template, request,
                   redirect, url_for, session, flash, jsonify,
                   Response, stream_with_context)

import data_store as db
from config import (SECRET_KEY, BAIDU_MAP_AK, CONTACT_EMAIL,
                    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_USE_SSL)

# AI 能力中心（独立文件 ai_assistant.py，出错也不影响网站其它功能）
try:
    from ai_assistant import (chat as ai_chat, ai_is_ready, AI_MODEL,
                              stream_chat, agent_plan, recognize_image,
                              vision_fallback, generate_copy, analyze_profile,
                              keywords_for_cloud, sentiment_label, check_sensitive,
                              photo_route_plan, call_llm)
except Exception as _ai_err:          # 缺依赖 / 少配置时优雅降级
    print(f"[AI] 能力中心加载失败：{_ai_err}")
    ai_chat = None
    ai_is_ready = lambda: False       # noqa: E731
    AI_MODEL = "-"

    def stream_chat(*a, **k):
        yield {"type": "token", "text": "AI 模块暂时不可用，请稍后再试。"}
        yield {"type": "done", "mode": "error", "model": "-"}

    def agent_plan(req):
        return None, []

    def recognize_image(*a, **k):
        return None

    def vision_fallback(q=""):
        return "AI 模块暂时不可用，请稍后再试。"

    def generate_copy(name, kind="景点", extra=""):
        return f"来德州，别错过{name}！"

    def analyze_profile(texts):
        return None, "empty"

    def keywords_for_cloud(texts, top_n=40):
        return []

    def sentiment_label(text):
        return "neutral"

    def check_sensitive(text):
        return False

    def photo_route_plan(image_path=None, note="", place_hint=""):
        return {"mode": "error", "error": "AI 模块暂时不可用，请稍后再试。"}

    def call_llm(messages, temperature=None, max_tokens=800, model=None):
        return None

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024     # 上传图片上限 12MB

# 允许上传的图片格式
ALLOWED_IMG = {"jpg", "jpeg", "png", "gif", "webp"}


def save_upload(file):
    """把上传的图片存到 static/uploads，返回可访问的相对 URL；不合法则返回 ''。"""
    if not file or not file.filename:
        return ""
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_IMG:
        return ""
    fname = uuid.uuid4().hex + "." + ext
    save_dir = os.path.join(app.root_path, "static", "uploads")
    os.makedirs(save_dir, exist_ok=True)
    path = os.path.join(save_dir, fname)
    file.save(path)
    return "/static/uploads/" + fname


def _abs_upload(path_url):
    """把 /static/uploads/xxx.jpg 换成磁盘绝对路径。"""
    return os.path.join(app.root_path, path_url.lstrip("/").replace("/", os.sep))


# ======================================================
# 一、数据小工具（替代原来的 SQL 查询）
# ======================================================
def _nicknames():
    return {u["id"]: u.get("nickname") or u.get("username") for u in db.all("users")}


def _comment_counts():
    counts = {}
    for c in db.all("comments"):
        counts[c["post_id"]] = counts.get(c["post_id"], 0) + 1
    return counts


def posts_with_author(rows):
    """给帖子补上作者昵称 + 评论数（原来的 JOIN 与子查询）。"""
    nicks = _nicknames()
    counts = _comment_counts()
    out = []
    for p in rows:
        item = dict(p)
        item["nickname"] = nicks.get(p["user_id"], "游客")
        item["comment_count"] = counts.get(p["id"], 0)
        out.append(item)
    return out


def latest(rows, field="created_at", n=None):
    """按时间倒序（时间是 datetime，直接排序即可）。"""
    return db.latest(rows, field=field, n=n)


# 详情页配置：kind -> 业务表 / 中文名 / 缺图时的兜底图
DETAIL_KINDS = {
    "attraction": {"table": "attractions", "label": "游玩地", "endpoint": "attractions",
                   "fallback_img": "/static/img/do-activities.jpg"},
    "food": {"table": "restaurants", "label": "美食", "endpoint": "food",
             "fallback_img": "/static/img/plan-food.jpg"},
    "culture": {"table": "cultural_sites", "label": "文化场馆", "endpoint": "culture",
                "fallback_img": "/static/img/do-culture.jpg"},
    "theater": {"table": "theaters", "label": "演出", "endpoint": "theater",
                "fallback_img": "/static/img/theater-opera.jpg"},
}


# ======================================================
# 二、页面路由
# ======================================================
@app.route("/")
def index():
    """首页：AI 拍照入口 + 栏目入口 + 热门推荐 + 个性化推荐 + 最新帖子 + 留言墙预览。"""
    hot_places = db.sort_by(db.all("attractions"), "hot")[:6]
    hot_food = db.sort_by(db.all("restaurants"), "hot")[:6]
    hot_theaters = db.sort_by(db.all("theaters"), "hot")[:3]
    latest_posts = posts_with_author(latest(db.all("posts"), n=4))
    wall_notes = sorted(db.all("sticky_notes"),
                        key=lambda r: (r.get("likes") or 0, r["id"]), reverse=True)[:8]

    # AI 游玩画像：登录用户展示个性化推荐（AI 分析发帖/评论生成）
    profile = None
    if "user_id" in session and ai_chat is not None:
        try:
            posts = db.where("posts", user_id=session["user_id"])
            comments = db.where("comments", user_id=session["user_id"])
            texts = [p["title"] + " " + (p.get("content") or "") for p in latest(posts, n=10)]
            texts += [c.get("content") or "" for c in latest(comments, n=10)]
            profile, _mode = analyze_profile(texts)
        except Exception:
            profile = None

    # 首页拍照卡片的示例地点（取自站内，点一下就能试）
    photo_demo_places = [r["name"] for r in db.sort_by(db.all("attractions"), "hot")[:6]]
    # 地点深挖的快捷地点（含商圈，因为深挖讲的是「里面有什么」）
    deep_places = photo_demo_places

    return render_template("index.html",
                           hot_places=hot_places, hot_food=hot_food,
                           hot_theaters=hot_theaters, latest_posts=latest_posts,
                           wall_notes=wall_notes, profile=profile,
                           ai_ready=ai_is_ready(),
                           photo_demo_places=photo_demo_places,
                           deep_places=deep_places)


@app.route("/attractions")
def attractions():
    """公交可达的游玩地：支持按分类筛选。"""
    category = request.args.get("category", "")
    rows = db.where("attractions", category=category) if category else db.all("attractions")
    rows = db.sort_by(rows, "hot")
    cats = []
    for r in db.all("attractions"):
        if r["category"] not in cats:
            cats.append(r["category"])
    return render_template("attractions.html", rows=rows, cats=cats, active=category)


@app.route("/food")
def food():
    """网红餐厅 + 美食故事入口。"""
    rows = db.sort_by(db.all("restaurants"), "hot")
    stories = {s["restaurant_name"]: s["id"] for s in db.all("food_stories")}
    return render_template("food.html", rows=rows, stories=stories)


@app.route("/culture")
def culture():
    """图书馆/博物馆/文化馆。"""
    stype = request.args.get("type", "")
    rows = db.where("cultural_sites", site_type=stype) if stype else db.all("cultural_sites")
    rows = db.sort_by(rows, "hot")
    types = []
    for r in db.all("cultural_sites"):
        if r["site_type"] not in types:
            types.append(r["site_type"])
    return render_template("culture.html", rows=rows, types=types, active=stype)


@app.route("/theater")
def theater():
    """小剧场 / 演出：卡片列表 + 全城演出日历（聚合各剧场节目单）。"""
    rows = db.sort_by(db.all("theaters"), "hot")
    calendar = []
    for t in rows:
        for line in (t.get("program") or "").splitlines():
            parts = [p.strip() for p in line.split("｜") if p.strip()]
            if not parts:
                continue
            calendar.append({
                "date": parts[0] if len(parts) > 0 else "",
                "show": parts[1] if len(parts) > 1 else "",
                "price": parts[2] if len(parts) > 2 else "",
                "theater": t["name"],
                "type": t["show_type"],
                "tid": t["id"],
            })

    def _date_key(item):
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", item["date"] or "")
        if m:
            return m.group(0)
        return "9999" + item["date"]       # 每周固定场次/待定的排在具体日期后面

    calendar.sort(key=_date_key)
    return render_template("theater.html", rows=rows, calendar=calendar)


@app.route("/detail/<kind>/<int:pid>")
def detail(kind, pid):
    """详情页：列表卡片点进来，看更完整的信息（含剧场节目单/评分/拍摄机位）。"""
    conf = DETAIL_KINDS.get(kind)
    if not conf:
        return "页面不存在", 404

    row = db.get(conf["table"], pid)
    if not row:
        return "页面不存在", 404
    row = dict(row)
    if not row.get("image_url"):
        row["image_url"] = conf["fallback_img"]

    if kind == "attraction":
        facts = [("类别", row.get("category")),
                 ("地址", row.get("address")),
                 ("公交路线", row.get("bus_route")),
                 ("开放时间", row.get("hours"))]
    elif kind == "food":
        facts = [("菜系", row.get("cuisine")),
                 ("招牌菜", row.get("recommend_dish")),
                 ("人均消费", row.get("price_level")),
                 ("地址", row.get("address"))]
    elif kind == "culture":
        facts = [("场馆类型", row.get("site_type")),
                 ("地址", row.get("address")),
                 ("开放时间", row.get("hours")),
                 ("门票", row.get("ticket"))]
    else:
        facts = [("演出类型", row.get("show_type")),
                 ("常规场次", row.get("schedule")),
                 ("票价区间", row.get("price_level")),
                 ("演出地点", row.get("address"))]
    facts = [(k, v) for k, v in facts if v]

    rating = row.get("rating")
    try:
        rating = float(rating) if rating is not None else None
    except (TypeError, ValueError):
        rating = None

    related = [r for r in db.sort_by(db.all(conf["table"]), "hot") if r["id"] != pid][:3]

    # 美食详情页：带上对应的美食故事（有故事才显示入口）
    story_id = story_name = None
    if kind == "food":
        srow = db.find("food_stories", lambda s: s["restaurant_name"] == row.get("name"))
        if srow:
            story_id, story_name = srow[0]["id"], srow[0]["dish"]

    name = row.get("name") or ""
    rel_routes = [r for r in db.sort_by(db.all("routes"), "hot") if name and name in (r.get("stops") or "")][:3]
    rel_posts = posts_with_author(latest(
        db.find("posts", lambda p: name and (name in (p.get("title") or "")
                                             or name in (p.get("content") or ""))), n=3))

    # 剧场节目单：每行是「日期｜节目｜票价」
    program = []
    if kind == "theater" and row.get("program"):
        for line in row["program"].splitlines():
            parts = [p.strip() for p in line.split("｜")]
            if parts and parts[0]:
                program.append((parts + ["", "", ""])[:3])

    # ★ 新增：这个地点的 AI 拍摄机位（照片 → 路线 → 机位 的数据支撑）
    spots = db.where("photo_spots", place=name) if kind == "attraction" else []

    return render_template("detail.html", kind=kind, label=conf["label"],
                           list_url=url_for(conf["endpoint"]),
                           row=row, facts=facts, rating=rating, program=program,
                           related=related, rel_routes=rel_routes, rel_posts=rel_posts,
                           story_id=story_id, story_name=story_name, spots=spots)


@app.route("/routes")
def routes():
    """城市漫游路线（特色功能）。"""
    rows = db.sort_by(db.all("routes"), "hot")
    return render_template("routes.html", rows=rows)


@app.route("/route/<int:rid>")
def route_detail(rid):
    """漫游路线详情页：站点串成动线，带 AI 讲解 / 机位 / 问答。"""
    row = db.get("routes", rid)
    if not row:
        return "路线不存在", 404
    row = dict(row)

    THEME_IMGS = {"美食": "img/food-baqi.jpg", "文化": "img/culture-canalmuseum.jpg",
                  "亲子": "img/att-park.jpg", "摄影": "img/att-moonlake.jpg",
                  "文艺": "img/food-cafe.jpg"}
    hero_img = url_for("static", filename=THEME_IMGS.get(row["theme"], "img/plan-sulu.jpg"))

    # 站点串：每个站点尝试挂上站内详情页 + AI 拍摄机位
    KIND_TABLES = [("attractions", "attraction", "name"),
                   ("restaurants", "food", "name"),
                   ("cultural_sites", "culture", "name")]
    stops = []
    for raw in (row.get("stops") or "").split("->"):
        stop_name = raw.strip()
        if not stop_name:
            continue
        item = {"name": stop_name, "url": None, "kind_label": None, "spots": []}
        for table, kind, _f in KIND_TABLES:
            hit = db.find(table, lambda r: stop_name and stop_name in (r.get("name") or "") or
                          (r.get("name") and r["name"] in stop_name))
            if hit:
                item["url"] = url_for("detail", kind=kind, pid=hit[0]["id"])
                item["kind_label"] = {"attraction": "景点", "food": "美食",
                                      "culture": "文化场馆"}[kind]
                break
        if item["url"] and "attraction" in (item["url"]):
            item["spots"] = db.where("photo_spots", place=stop_name)[:2]
        if not item["spots"]:
            item["spots"] = db.find("photo_spots", lambda s: stop_name in (s.get("place") or ""))[:2]
        stops.append(item)

    related = [r for r in db.sort_by(db.all("routes"), "hot") if r["id"] != rid][:3]
    return render_template("route_detail.html", row=row, hero_img=hero_img,
                           stops=stops, related=related)


@app.route("/map")
def map_page():
    """创新点：百度地图一站看全——把景点/美食/文化场馆标注在地图上。"""
    spots = []
    for a in db.all("attractions"):
        if a.get("lng") is not None:
            spots.append({"name": a["name"], "kind": a["category"], "address": a["address"],
                          "lng": a["lng"], "lat": a["lat"], "bus_route": a["bus_route"]})
    for r in db.all("restaurants"):
        if r.get("lng") is not None:
            spots.append({"name": r["name"], "kind": "美食", "address": r["address"],
                          "lng": r["lng"], "lat": r["lat"], "bus_route": ""})
    for c in db.all("cultural_sites"):
        if c.get("lng") is not None:
            spots.append({"name": c["name"], "kind": c["site_type"], "address": c["address"],
                          "lng": c["lng"], "lat": c["lat"], "bus_route": ""})
    return render_template("map.html", spots=spots, ak=BAIDU_MAP_AK)


# ---------------- 智慧地图 · AI 出行助手 ----------------
# 常用出发地（坐标为德州市区常用交通枢纽的近似值，用于估算）
MAP_ORIGINS = {
    "德州火车站": (116.3075, 37.4556),
    "德州东站（高铁站）": (116.4480, 37.4390),
    "澳德乐时代广场": (116.3119, 37.4292),
    "德州市中心（德城区政府）": (116.3100, 37.4460),
}

def _haversine_km(lng1, lat1, lng2, lat2):
    """球面距离估算（公里）。"""
    import math
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))

def _match_place(message):
    """在站内全部地点里匹配用户想去的目的地（双向包含 + 关键词兜底）。"""
    msg = message.strip()
    if not msg:
        return None
    pool = []
    for table, kind_label, detail_kind in [("attractions", "景点", "attraction"),
                                           ("restaurants", "美食", "food"),
                                           ("cultural_sites", "文化场馆", "culture"),
                                           ("theaters", "剧场演出", "theater")]:
        for r in db.all(table):
            pool.append({"name": r.get("name") or "", "kind": kind_label,
                         "detail_kind": detail_kind, "row": r})
    # 1) 完整名命中
    for p in pool:
        if p["name"] and p["name"] in msg:
            return p
    # 2) 消息里出现地点名的一部分（去掉「我想去/帮我到」等前缀）
    for p in sorted(pool, key=lambda x: -len(x["name"])):
        if len(p["name"]) >= 2 and p["name"] in msg:
            return p
    # 2.5) 单字打错也能容错：地点名的任意子串有一个字写错或相邻颠倒
    #      （如「奥德乐」→「澳德乐」、「月明湖」→「明月湖」）。
    #      收集全部候选，按「命中的子串最长」优先，避免「德州扒鸡」被匹配成德州博物馆。
    def _near(sub, piece):
        """两个字串等长、差异不超过一处（替换或相邻颠倒）。"""
        diffs = [i for i in range(len(sub)) if sub[i] != piece[i]]
        if len(diffs) == 1:
            return True
        if len(diffs) == 2 and diffs[1] == diffs[0] + 1:
            i, j = diffs
            return sub[i] == piece[j] and sub[j] == piece[i]
        return False

    fuzzy_hits = []
    for p in pool:
        name = p["name"]
        if len(name) < 3:
            continue
        best = 0
        for start in range(len(name)):
            for end in range(start + 3, len(name) + 1):
                sub = name[start:end]
                if len(sub) - 1 < 2:
                    continue
                # 名字的一部分被完整说出（如「苏禄王墓」→苏禄王墓博物馆）
                if sub in msg:
                    best = max(best, len(sub))
                    continue
                for s in range(len(msg) - len(sub) + 1):
                    if _near(sub, msg[s:s + len(sub)]):
                        best = max(best, len(sub))
                        break
        if best:
            fuzzy_hits.append((best, p))
    if fuzzy_hits:
        fuzzy_hits.sort(key=lambda x: -x[0])
        return fuzzy_hits[0][1]
    # 2.8) 用户只说了简称：去掉「我想去 / 想去 / 帮我找 / 带我去」等前后缀，
    #      剩下的简称（≥2 字）出现在地点全名里（如「银座」→银座商城）
    core = re.sub(r"^(我想去|帮我找下|帮我找|带我去|我想找|想去|我要去|我去|去|到|找)", "", msg)
    core = re.sub(r"(怎么走|怎么去|在哪里|在哪|好玩吗|怎么样|呀|吧|呢|吗|啊)$", "", core).strip()
    if len(core) >= 2:
        hits = [p for p in pool if core in p["name"]]
        if hits:
            return sorted(hits, key=lambda x: -(x["row"].get("hot") or 0))[0]
    # 3) 关键词模糊：先在「名字」里找，找不到再看地址（地址太容易误伤）
    for kw in ("博物馆", "公园", "夜市", "广场", "扒鸡", "火烧", "图书馆", "剧院",
               "湿地", "湖", "文化街", "烧烤", "咖啡"):
        if kw in msg:
            by_hot = sorted(pool, key=lambda x: -(x["row"].get("hot") or 0))
            for p in by_hot:
                if kw in p["name"]:
                    return p
            if len(kw) >= 3:
                for p in by_hot:
                    if kw in (p["row"].get("address") or ""):
                        return p
    return None

@app.route("/api/map/assist", methods=["POST"])
def api_map_assist():
    """
    智慧地图 AI 出行助手：
    「我想去澳德乐」-> 匹配站内地点 -> 公交 / 步行 / 打车 三种方案 + 地图联动。
    """
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    origin_name = str(data.get("origin", "")).strip() or "德州火车站"
    if len(message) > 300:
        message = message[:300]

    if not message:
        return jsonify({"ok": False, "reply": "输入你想去的地方，比如「我想去澳德乐」，或按话筒直接说。"})

    hit = _match_place(message)
    if not hit:
        # 没匹配到站内地点 -> 交给 AI 导游自由问答
        if ai_chat is not None:
            try:
                result = ai_chat(message, [])
                return jsonify({"ok": False, "reply": result.get("reply", ""),
                                "sources": result.get("sources", [])})
            except Exception:
                pass
        return jsonify({"ok": False,
                        "reply": "站内暂时没有收录这个地方。可以换一个说法，比如「德州博物馆」「澳德乐」「夜市」，或者去「AI 游德州」问小德。"})

    row = hit["row"]
    name = hit["name"]
    dlng, dlat = row.get("lng"), row.get("lat")
    if dlng is None or dlat is None:
        return jsonify({"ok": False, "reply": f"「{name}」还没有坐标数据，先去它的详情页看看地址吧。"})

    olng, olat = MAP_ORIGINS.get(origin_name, MAP_ORIGINS["德州火车站"])
    km = round(_haversine_km(olng, olat, dlng, dlat), 1)
    walk_min = max(2, int(km / 4.8 * 60))
    # 打车估价：德州白天起步价约 8 元 / 2 公里，之后约 1.8 元 / 公里
    taxi_fee = round(8 + max(0.0, km - 2) * 1.8)
    taxi_min = max(3, int(km / 28 * 60 + 3))

    bus_route = row.get("bus_route") or ""
    if hit["detail_kind"] in ("food", "culture", "theater") and not bus_route:
        # 美食/场馆没存公交字段，就近给一条通用建议
        near = min([a for a in db.all("attractions") if a.get("lng")],
                   key=lambda a: _haversine_km(dlng, dlat, a["lng"], a["lat"]), default=None)
        bus_route = near.get("bus_route") if near else ""
        near_name = near.get("name") if near else None
    else:
        near_name = None

    bus_plan = bus_route or "建议打车或骑行前往，市内公交班次请以百度地图实时查询为准。"

    # 到了附近吃什么：目的地 2 公里内的美食，按距离取 3 家（真实站内数据）
    nearby_food = []
    for r in db.sort_by(db.all("restaurants"), "hot"):
        if not r.get("lng") or not r.get("lat"):
            continue
        if r["name"] == name:
            continue  # 目的地是这家店本身，不再重复推荐
        d_km = round(_haversine_km(dlng, dlat, r["lng"], r["lat"]), 1)
        if d_km <= 2.0:
            nearby_food.append({
                "name": r["name"],
                "signature": r.get("recommend_dish", ""),
                "price": r.get("price_level", ""),
                "distance_km": d_km,
                "walk_min": max(2, int(d_km / 4.8 * 60)),
                "address": r.get("address", ""),
                "rating": r.get("rating"),
            })
        if len(nearby_food) >= 3:
            break

    detail_url = None
    try:
        detail_url = url_for("detail", kind=hit["detail_kind"], pid=row["id"])
    except Exception:
        detail_url = None

    map_url = f"https://map.baidu.com/search/{name}/@{dlng},{dlat},16z"
    nav_url = (f"https://api.map.baidu.com/direction?"
               f"origin={olat},{olng}|name:{origin_name}&"
               f"destination={dlat},{dlng}|name:{name}&mode=transit&region=德州&output=html"
               f"&src=dezhou_travel&coord_type=bd09ll")

    summary = (f"从「{origin_name}」到「{name}」直线约 {km} 公里。"
               f"公交：{bus_plan} 打车约 {taxi_fee} 元（{taxi_min} 分钟左右）。"
               f"步行约 {walk_min} 分钟，边走边逛也合适。")

    return jsonify({
        "ok": True,
        "place": {"name": name, "kind": hit["kind"], "address": row.get("address", ""),
                  "lng": dlng, "lat": dlat, "hours": row.get("hours", ""),
                  "bus_route": bus_route, "near_name": near_name},
        "origin": {"name": origin_name},
        "distance_km": km, "walk_min": walk_min,
        "taxi_fee": taxi_fee, "taxi_min": taxi_min,
        "bus_plan": bus_plan, "summary": summary,
        "nearby_food": nearby_food,
        "map_url": map_url, "nav_url": nav_url, "detail_url": detail_url,
    })


# ---------------- 论坛 ----------------
@app.route("/forum")
def forum():
    """论坛广场：所有帖子 + 苍蝇馆子 + 网红打卡路线。"""
    category = request.args.get("category", "")
    rows = db.where("posts", category=category) if category else db.all("posts")
    rows = posts_with_author(latest(rows))
    cats = ["游记", "美食", "问答", "避坑", "其他"]
    gems = db.sort_by(db.all("hidden_gems"), "hot")
    influencers = db.sort_by(db.all("influencer_routes"), "hot")
    return render_template("forum.html", rows=rows, cats=cats, active=category,
                           gems=gems, influencers=influencers)


@app.route("/post/<int:pid>")
def post_detail(pid):
    """帖子详情 + 评论区。"""
    post = db.get("posts", pid)
    if not post:
        return "帖子不存在", 404
    db.incr("posts", pid, "views")
    post = dict(post)
    post["nickname"] = _nicknames().get(post["user_id"], "游客")
    nicks = _nicknames()
    comments = []
    for c in sorted(db.where("comments", post_id=pid), key=lambda r: r.get("created_at") or 0):
        item = dict(c)
        item["nickname"] = nicks.get(c["user_id"], "游客")
        comments.append(item)
    return render_template("post_detail.html", post=post, comments=comments)


@app.route("/post/new", methods=["GET", "POST"])
def new_post():
    """发新帖（需要登录）。"""
    if "user_id" not in session:
        flash("请先登录再发帖哦")
        return redirect(url_for("login"))
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        category = request.form.get("category", "游记")
        if not title or not content:
            flash("标题和内容都不能为空")
            return redirect(url_for("new_post"))
        image_url = save_upload(request.files.get("image"))
        db.insert("posts", user_id=session["user_id"], category=category,
                  title=title, content=content, image_url=image_url, likes=0, views=0)
        flash("发布成功！")
        return redirect(url_for("forum"))
    return render_template("new_post.html")


@app.route("/post/<int:pid>/comment", methods=["POST"])
def add_comment(pid):
    """评论（需要登录）。"""
    if "user_id" not in session:
        flash("请先登录再评论哦")
        return redirect(url_for("login"))
    content = request.form.get("content", "").strip()
    if not content:
        flash("评论内容不能为空")
    else:
        db.insert("comments", post_id=pid, user_id=session["user_id"], content=content)
        flash("评论成功！")
    return redirect(url_for("post_detail", pid=pid))


@app.route("/post/<int:pid>/like", methods=["POST"])
def like_post(pid):
    """点赞。"""
    db.incr("posts", pid, "likes")
    return redirect(url_for("post_detail", pid=pid))


def send_contact_mail(to_email, visitor_name, visitor_email, subject, content):
    """用 QQ 邮箱 SMTP 把访客留言真实发到团队邮箱。成功返回 True。"""
    if not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD and to_email):
        return False
    body = (
        f"【新留言 · 德途智行·AI智游德州】\n\n"
        f"访客姓名：{visitor_name}\n"
        f"访客邮箱：{visitor_email}\n"
        f"留言主题：{subject or '（无主题）'}\n\n"
        f"留言内容：\n{content}\n"
    )
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = SMTP_USER
    msg["To"] = to_email
    msg["Subject"] = Header(f"[德州文旅留言] {subject or '来自访客'}", "utf-8")
    try:
        if SMTP_USE_SSL:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=15) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_USER, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_USER, [to_email], msg.as_string())
        return True
    except Exception:
        return False


# ---------------- 联系我们（创新点：邮箱留言） ----------------
@app.route("/contact", methods=["GET", "POST"])
def contact():
    """联系我们：访客留言（本地存档），并提供团队邮箱。"""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        subject = request.form.get("subject", "").strip()
        content = request.form.get("content", "").strip()
        if not name or not email or not content:
            flash("姓名、邮箱和留言内容都不能为空")
        else:
            senti = sentiment_label(content)
            db.insert("contact_messages", name=name, email=email,
                      subject=subject, content=content, sentiment=senti)
            if send_contact_mail(CONTACT_EMAIL, name, email, subject, content):
                flash("留言已发送到团队邮箱，我们会尽快回复你，感谢支持！")
            else:
                flash("留言已保存，我们会尽快回复你，感谢支持！（邮件服务暂不可用）")
            return redirect(url_for("contact"))
    return render_template("contact.html", contact_email=CONTACT_EMAIL)


# ---------------- 登录注册 ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    """注册账号。"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        nickname = request.form.get("nickname", "").strip() or username
        if not username or not password:
            flash("用户名和密码不能为空")
        elif db.where("users", username=username):
            flash("用户名已被占用")
        else:
            db.insert("users", username=username, password=password,
                      nickname=nickname, avatar="", bio="")
            flash("注册成功，请登录！")
            return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """登录。"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        found = db.find("users", lambda u: u["username"] == username and u["password"] == password)
        if found:
            user = found[0]
            session["user_id"] = user["id"]
            session["nickname"] = user["nickname"]
            flash("欢迎回来，" + user["nickname"] + "！")
            return redirect(url_for("index"))
        flash("用户名或密码错误")
    return render_template("login.html")


@app.route("/logout")
def logout():
    """退出登录。"""
    session.clear()
    flash("已退出登录")
    return redirect(url_for("index"))


# ======================================================
# 三、AI 智能问答接口（创新点）
# ======================================================
# 简易限流：同一个 IP 一分钟最多问 20 次，防止被刷爆大模型额度
_CHAT_HITS = {}
_CHAT_LIMIT = 20
_CHAT_WINDOW = 60


def _chat_rate_ok(ip):
    now = time.time()
    hits = [t for t in _CHAT_HITS.get(ip, []) if now - t < _CHAT_WINDOW]
    if len(hits) >= _CHAT_LIMIT:
        _CHAT_HITS[ip] = hits
        return False
    hits.append(now)
    _CHAT_HITS[ip] = hits
    return True


def _client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0].strip()


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """
    游客提问 -> 检索站内数据（RAG）-> 大模型生成回答 -> 返回 JSON。
    前端把最近几轮对话一起传上来，支持多轮追问。
    """
    if ai_chat is None:
        return jsonify({"reply": "AI 问答模块暂时不可用，请稍后再试。",
                        "sources": [], "mode": "error"}), 503

    if not _chat_rate_ok(_client_ip()):
        return jsonify({"reply": "你问得有点快啦，歇一口气再问吧～",
                        "sources": [], "mode": "error"}), 429

    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    if not message:
        return jsonify({"reply": "想问点什么？直接打字或按话筒说话都可以。",
                        "sources": [], "mode": "error"}), 400
    if len(message) > 500:
        message = message[:500]

    history = data.get("history") or []
    if not isinstance(history, list):
        history = []
    clean_history = []
    for h in history[-6:]:
        if isinstance(h, dict) and h.get("role") in ("user", "assistant"):
            content = str(h.get("content", ""))[:800]
            if content:
                clean_history.append({"role": h["role"], "content": content})

    try:
        result = ai_chat(message, clean_history)
    except Exception as e:
        print(f"[AI] 问答接口异常：{e}")
        return jsonify({"reply": "我这边卡了一下，你换个问法再试试？",
                        "sources": [], "mode": "error"}), 500
    return jsonify(result)


# ======================================================
# 四、AI 能力接口（Agent / 流式 / 多模态 / 拍照路线 / 文案 / 画像）
# ======================================================
@app.route("/ai")
def ai_center():
    """AI 游德州 · AI 能力体验中心。"""
    places = [r["name"] for r in db.sort_by(db.all("attractions"), "hot")]
    return render_template("ai.html", ai_ready=ai_is_ready(),
                           vision_model=AI_MODEL, photo_places=places,
                           deep_places=places[:8])


@app.route("/wall")
def wall():
    """游客留言墙：便利贴 + AI 词云。"""
    notes = sorted(db.all("sticky_notes"),
                   key=lambda r: (r.get("likes") or 0, r["id"]), reverse=True)[:36]
    return render_template("wall.html", notes=notes, ai_ready=ai_is_ready())


@app.route("/wall/add", methods=["POST"])
def wall_add():
    """发一张新便利贴：AI 情感分析自动配色（无 Key 时走本地规则，一样能用）。"""
    nickname = (request.form.get("nickname") or "游客").strip()[:20]
    content = (request.form.get("content") or "").strip()[:200]
    if not content:
        flash("留言内容不能为空")
        return redirect(url_for("wall"))
    if check_sensitive(content):
        flash("留言包含不当内容，请修改后再发")
        return redirect(url_for("wall"))
    senti = sentiment_label(content)
    color_map = {"pos": "yellow", "neg": "pink", "neutral": "blue"}
    db.insert("sticky_notes", nickname=nickname or "游客", content=content,
              color=color_map.get(senti, "blue"), likes=0, sentiment=senti)
    flash("留言已贴上墙，感谢你的反馈！")
    return redirect(url_for("wall"))


@app.route("/wall/like/<int:nid>", methods=["POST"])
def wall_like(nid):
    """给便利贴点赞（JSON 接口，页面无刷新 +1）。"""
    row = db.incr("sticky_notes", nid, "likes")
    return jsonify({"ok": True, "likes": row["likes"] if row else 0})


@app.route("/api/wall/cloud")
def api_wall_cloud():
    """AI 词云数据：聚合便利贴/帖子/留言文本，统计高频词 + 情感占比。"""
    texts = [r.get("content") or "" for r in db.all("sticky_notes")]
    texts += [r.get("content") or "" for r in db.all("contact_messages")]
    texts += [r["title"] + " " + (r.get("content") or "") for r in db.all("posts")]
    words = keywords_for_cloud(texts, top_n=42)

    stat = {}
    for r in db.all("sticky_notes"):
        s = r.get("sentiment") or "neutral"
        stat[s] = stat.get(s, 0) + 1
    return jsonify({
        "words": [{"w": w, "n": n} for w, n in words],
        "sentiment": {"pos": stat.get("pos", 0),
                      "neg": stat.get("neg", 0),
                      "neutral": stat.get("neutral", 0)},
        "total": len([t for t in texts if t]),
    })


@app.route("/food-story/<int:pid>")
def food_story(pid):
    """美食文化故事页：历史由来 / 趣味冷知识 / 家常做法 / 哪家好吃。"""
    story = db.get("food_stories", pid)
    if not story:
        return "故事不存在", 404
    restaurant = None
    found = db.find("restaurants", lambda r: r["name"] == story["restaurant_name"])
    if found:
        restaurant = found[0]
    others = [dict(s) for s in db.all("food_stories") if s["id"] != pid][:3]
    return render_template("food_story.html", story=story,
                           restaurant=restaurant, others=others)


@app.route("/api/chat/stream", methods=["POST"])
def api_chat_stream():
    """AI 导游流式问答（SSE）：前端逐字渲染 + 思考状态 + 来源卡片。"""
    if not _chat_rate_ok(_client_ip()):
        return jsonify({"error": "提问太频繁啦，歇一口气再问～"}), 429

    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()[:500]
    if not message:
        return jsonify({"error": "想问点什么？"}), 400
    history = data.get("history") or []
    clean_history = []
    if isinstance(history, list):
        for h in history[-6:]:
            if isinstance(h, dict) and h.get("role") in ("user", "assistant"):
                content = str(h.get("content", ""))[:800]
                if content:
                    clean_history.append({"role": h["role"], "content": content})

    def generate():
        try:
            for evt in stream_chat(message, clean_history):
                yield "data: " + json.dumps(evt, ensure_ascii=False) + "\n\n"
        except Exception as e:      # 流中途出错也要给前端一个收尾事件
            print(f"[AI] 流式问答异常：{e}")
            tail = {"type": "token", "text": "\n（刚才网络抖了一下，你可以再问一次）"}
            yield "data: " + json.dumps(tail, ensure_ascii=False) + "\n\n"
            yield "data: " + json.dumps({"type": "done", "mode": "error",
                                         "model": "-"}, ensure_ascii=False) + "\n\n"

    return Response(stream_with_context(generate()),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})


@app.route("/api/agent/plan", methods=["POST"])
def api_agent_plan():
    """AI Agent 行程规划：Function Calling 调用站内工具 -> 结构化行程 JSON。"""
    data = request.get_json(silent=True) or {}
    requirement = str(data.get("requirement", "")).strip()[:300]
    if not requirement:
        return jsonify({"error": "告诉我你想怎么玩，比如：周六带爸妈玩一天，不吃辣"}), 400
    if check_sensitive(requirement):
        return jsonify({"error": "内容包含不当词汇，请修改后再试"}), 400

    plan, trace = agent_plan(requirement)
    if plan is None:
        return jsonify({"error": "AI 规划师这会儿开小差了，请再试一次",
                        "trace": trace}), 502
    return jsonify({"plan": plan, "trace": trace,
                    "mode": "llm" if ai_is_ready() else "rule",
                    "model": AI_MODEL if ai_is_ready() else "站内规则规划"})


@app.route("/api/vision", methods=["POST"])
def api_vision():
    """拍照识德州（多模态）：上传照片 -> 识别并讲解。失败自动降级。"""
    file = request.files.get("image")
    question = (request.form.get("question") or "").strip()[:200]
    if not file or not file.filename:
        return jsonify({"error": "先选一张照片哦"}), 400
    path_url = save_upload(file)
    if not path_url:
        return jsonify({"error": "只支持 jpg/png/gif/webp 图片"}), 400

    reply = None
    if ai_chat is not None:
        try:
            reply = recognize_image(_abs_upload(path_url), question)
        except Exception as e:
            print(f"[AI] 识图异常：{e}")
    if reply:
        return jsonify({"reply": reply, "mode": "llm"})
    return jsonify({"reply": vision_fallback(question), "mode": "kb",
                    "image_url": path_url})


# ---------- ★ 新增：一张风景照 -> 游玩路线 + 拍摄点位 ----------
@app.route("/api/photo-plan", methods=["POST"])
def api_photo_plan():
    """
    网站主打功能「拍一张，AI 给你一条路线」。

    两种用法：
      1) 上传一张照片（游客在网上/小红书看到的德州风景图）
         -> 多模态大模型认出这是哪儿 -> 站内数据排出游玩路线 + 拍摄机位
      2) 不上传照片，直接选站内一个地点
         -> 同样给出路线 + 机位（没有大模型也能演示）

    返回：{mode, identified, route, photo_spots, food, tips, model}
    """
    if not _chat_rate_ok(_client_ip()):
        return jsonify({"error": "操作太频繁啦，歇一口气再试～"}), 429

    image_path = None
    if request.files.get("image"):
        file = request.files["image"]
        note = (request.form.get("note") or "").strip()[:120]
        place = (request.form.get("place") or "").strip()[:40]
        path_url = save_upload(file)
        if not path_url:
            return jsonify({"error": "只支持 jpg / png / gif / webp 图片"}), 400
        image_path = _abs_upload(path_url)
    else:
        data = request.get_json(silent=True) or {}
        note = str(data.get("note") or "").strip()[:120]
        place = str(data.get("place") or "").strip()[:40]

    if not image_path and not place:
        return jsonify({"error": "先上传一张照片，或者从下面挑一个想去的德州地点"}), 400

    try:
        result = photo_route_plan(image_path=image_path, note=note, place_hint=place)
    except Exception as e:
        print(f"[AI] 拍照路线生成异常：{e}")
        return jsonify({"error": "AI 这会儿有点忙，稍等一下再试一次"}), 500

    if result.get("error"):
        return jsonify(result), 502
    return jsonify(result)


# ---------- ★ 新增：一张图 / 一个名字 -> 深入了解某一个地点 ----------
def _ai_suggest_shops(name, basic):
    """
    站内没有收录某商场/景区的商户时，请大模型基于常识生成「场内常见商户」参考。
    生成结果前端会明确标注“AI 生成”，不冒充站内核实数据。
    """
    messages = [
        {"role": "system", "content":
         "你是德州本地商业信息助手。用户想了解德州一家商场/景区内部的餐饮娱乐商户。"
         "请基于你的知识，列出这家场所内部或同址裙楼里较知名的商户，"
         "优先列确有门店的连锁品牌，不确定存在的一律不列，宁缺毋滥。"
         "只输出一个 JSON 数组，不要任何多余文字，每个元素包含字段："
         "name(商户名)，kind(只能是 吃/玩/买 之一)，cuisine(品类，如 火锅/影城/奶茶)，"
         "signature(招牌菜或项目，一句话)，price(人均，如 ¥45/人)，"
         "rating(3.8~4.8 之间的数字)，detail(楼层或位置，如 商场4楼)，"
         "hours(营业时间，如 10:00-22:00)，recommend(给游客的一句建议)。共 4~5 条。"},
        {"role": "user", "content":
         f"地点：{name}\n简介：{(basic.get('description') or '')[:100]}\n"
         f"地址：{basic.get('address', '')}"},
    ]
    raw = call_llm(messages, temperature=0.3, max_tokens=900)
    if not raw:
        return None
    try:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        items = json.loads(text[text.index("["):text.rindex("]") + 1])
        clean = []
        for it in items[:5]:
            if not isinstance(it, dict) or not it.get("name"):
                continue
            clean.append({
                "name": str(it.get("name"))[:30],
                "kind": str(it.get("kind", "吃"))[:2],
                "cuisine": str(it.get("cuisine", ""))[:20],
                "signature": str(it.get("signature", ""))[:60],
                "price": str(it.get("price", ""))[:20],
                "rating": it.get("rating", 4.2),
                "detail": str(it.get("detail", ""))[:20],
                "hours": str(it.get("hours", ""))[:30],
                "recommend": str(it.get("recommend", ""))[:80],
            })
        return clean or None
    except (ValueError, SyntaxError) as e:
        print(f"[AI] 商户兜底解析失败：{e}")
        return None


@app.route("/api/place-deep", methods=["POST"])
def api_place_deep():
    """
    地点深挖：给一张照片或一个具体名字，输出这一个地点的可执行攻略——
    怎么去（公交/打车估价）、里面具体吃什么买什么（商户罗列：特色菜/价位/推荐理由）、
    附近美食、拍照机位。只讲这一个地点，整条路线交给 AI 漫游路线。
    """
    if not _chat_rate_ok(_client_ip()):
        return jsonify({"error": "操作太频繁啦，歇一口气再试～"}), 429

    image_path = None
    if request.files.get("image"):
        file = request.files["image"]
        note = (request.form.get("note") or "").strip()[:120]
        place = (request.form.get("place") or "").strip()[:40]
        path_url = save_upload(file)
        if not path_url:
            return jsonify({"error": "只支持 jpg / png / gif / webp 图片"}), 400
        image_path = _abs_upload(path_url)
    else:
        data = request.get_json(silent=True) or {}
        note = str(data.get("note") or "").strip()[:120]
        place = str(data.get("place") or "").strip()[:40]

    if not image_path and not place:
        return jsonify({"error": "传一张照片，或者直接点一个地点名字"}), 400

    # 复用照片排路线的识别与地点匹配（多模态识别 + 错字容错 + 降级兜底）
    try:
        base = photo_route_plan(image_path=image_path, note=note, place_hint=place)
    except Exception as e:
        print(f"[AI] 地点深挖异常：{e}")
        return jsonify({"error": "AI 这会儿有点忙，稍等一下再试一次"}), 500

    if base.get("need_place"):
        return jsonify({"need_place": True,
                        "candidate_places": base.get("candidate_places", []),
                        "tip": base.get("tip", "没认出是哪儿，挑一个地点试试？")})
    if not base.get("matched"):
        return jsonify({"error": "没匹配到站内地点，换个名字试试？"}), 404

    name = base["matched"]["name"]
    identified = base.get("identified")
    model = base.get("model", "")
    mode = base.get("mode", "rule")

    # 只在景点 / 场馆 / 美食店里深挖
    row = kind_src = None
    for table in ("attractions", "cultural_sites", "restaurants"):
        hit = db.find(table, lambda r: r["name"] == name)
        if hit:
            row, kind_src = hit[0], table
            break
    if row is None:
        return jsonify({"error": "这个地点暂时没有深挖数据"}), 404

    # 基本档案
    basic = {
        "name": name,
        "kind_label": {"attractions": "游玩地", "cultural_sites": "文化场馆",
                       "restaurants": "美食店"}[kind_src],
        "address": row.get("address", ""),
        "hours": row.get("hours", ""),
        "ticket": row.get("ticket", ""),
        "description": row.get("description", ""),
        "bus_route": row.get("bus_route", "") if row.get("bus_route") is not None else "",
        "price_level": row.get("price_level", ""),
        "image_url": row.get("image_url") or "",
        "lng": row.get("lng"), "lat": row.get("lat"),
    }

    # 怎么去：从德州火车站出发的打车估价（公交见 bus_route）
    taxi = None
    if row.get("lng") and row.get("lat"):
        olng, olat = MAP_ORIGINS["德州火车站"]
        km = round(_haversine_km(olng, olat, row["lng"], row["lat"]), 1)
        taxi = {"distance_km": km,
                "fee": round(8 + max(0.0, km - 2) * 1.8),
                "min": max(3, int(km / 28 * 60 + 3))}
        map_url = f"https://map.baidu.com/@{row['lng']},{row['lat']},16z"
    else:
        map_url = "https://map.baidu.com/@116.35,37.445,13z"

    # 里面吃什么买什么：场内/街区商户
    shops = db.where("shops", place=name)
    shops = sorted(shops, key=lambda s: -(s.get("hot") or 0))

    # 站内没收录时，让 DeepSeek 生成「场内商户参考」（前端会标注 AI 生成）
    shops_note = ""
    if not shops and ai_is_ready():
        ai_shops = _ai_suggest_shops(name, basic)
        if ai_shops:
            shops = ai_shops
            shops_note = (f"🤖 下面商户由 AI（{AI_MODEL}）根据公开信息生成，"
                          "属参考性质、非站内逐一核实，到店前建议先查点评类 App 确认。")

    # 附近还可以吃：2 公里内美食店（排除同名）
    nearby_food = []
    if row.get("lng") and row.get("lat"):
        for r in db.sort_by(db.all("restaurants"), "hot"):
            if r.get("lng") is None or r["name"] == name:
                continue
            d_km = round(_haversine_km(row["lng"], row["lat"], r["lng"], r["lat"]), 1)
            if d_km <= 2.5 and len(nearby_food) < 4:
                nearby_food.append({
                    "name": r["name"], "signature": r.get("recommend_dish", ""),
                    "price": r.get("price_level", ""), "distance_km": d_km,
                    "walk_min": max(2, int(d_km / 4.8 * 60)),
                    "address": r.get("address", "")})

    # 拍照机位
    spots = db.where("photo_spots", place=name)[:3]

    return jsonify({
        "mode": mode, "model": model, "identified": identified,
        "basic": basic, "taxi": taxi, "map_url": map_url,
        "shops": shops, "shops_note": shops_note,
        "nearby_food": nearby_food, "spots": spots,
    })


@app.route("/api/copy", methods=["POST"])
def api_copy():
    """AI 种草文案生成：详情页一键生成推广文案。"""
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()[:50]
    kind = str(data.get("kind", "景点")).strip()[:10]
    extra = str(data.get("extra", "")).strip()[:100]
    if not name:
        return jsonify({"error": "缺少名称"}), 400
    text = generate_copy(name, kind, extra)
    return jsonify({"copy": text, "mode": "llm" if ai_is_ready() else "kb"})


@app.route("/api/profile")
def api_profile():
    """AI 游玩画像：当前登录用户的兴趣标签 + 推荐（JSON 版本，供前端刷新）。"""
    if "user_id" not in session:
        return jsonify({"error": "请先登录"}), 401
    posts = latest(db.where("posts", user_id=session["user_id"]), n=10)
    comments = latest(db.where("comments", user_id=session["user_id"]), n=10)
    texts = [p["title"] + " " + (p.get("content") or "") for p in posts]
    texts += [c.get("content") or "" for c in comments]
    profile, mode = analyze_profile(texts)
    if not profile:
        return jsonify({"error": "还没有足够的动态，去发个帖或评论一下吧"}), 404
    profile["mode"] = mode
    return jsonify(profile)


# ======================================================
# 五、启动入口
# ======================================================
if __name__ == "__main__":
    print("=" * 56)
    print("  德州文旅网站已启动（数据全部内置，无需数据库）")
    print("  请在浏览器打开： http://127.0.0.1:5000")
    print("  帖子/留言存档：  data/store.json")
    print("=" * 56)
    app.run(debug=True)
