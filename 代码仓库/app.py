# -*- coding: utf-8 -*-
"""
============================================================
  德州文旅 ·「九达天衢 · 韵动德州」
  主程序 app.py —— 网站全部后台逻辑

  运行步骤：
    第1步：pip install -r requirements.txt
    第2步：python app.py
    第3步：浏览器打开 http://127.0.0.1:5000

  环境变量：数据库连接 / 会话密钥 / 百度地图AK 都从 config.py 读取，
            相关说明见 .env.example。
============================================================
"""

import os
import uuid
import pymysql
from flask import (Flask, render_template, request,
                   redirect, url_for, session, flash)

from config import (DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT,
                    SECRET_KEY, BAIDU_MAP_AK, CONTACT_EMAIL)

app = Flask(__name__)
app.secret_key = SECRET_KEY


# ======================================================
# 一、数据库连接工具函数
# ======================================================
def get_db():
    """连接 MySQL，返回一个连接对象。"""
    return pymysql.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, port=DB_PORT, charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def query(sql, args=()):
    """查询多行数据，返回 [ {列:值}, ... ] 的列表。"""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall()
    finally:
        conn.close()


def query_one(sql, args=()):
    """查询单行数据，返回一个字典，没有则返回 None。"""
    rows = query(sql, args)
    return rows[0] if rows else None


def execute(sql, args=()):
    """执行增、删、改（不需要返回数据的操作）。"""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
        conn.commit()
    finally:
        conn.close()


# 允许上传的图片格式
ALLOWED_IMG = {"jpg", "jpeg", "png", "gif", "webp"}


def save_upload(file):
    """把发帖时上传的图片存到 static/uploads，返回可访问的相对 URL；不合法则返回 ''。"""
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


# ======================================================
# 二、建库建表 + 塞入示例数据
# ======================================================
def init_database():
    """程序一启动就自动：建数据库 -> 建表 -> 填入示例数据。"""
    conn = pymysql.connect(host=DB_HOST, user=DB_USER,
                           password=DB_PASSWORD, port=DB_PORT,
                           charset='utf8mb4')
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                        "DEFAULT CHARACTER SET utf8mb4")
        conn.commit()
    finally:
        conn.close()

    execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            password VARCHAR(100) NOT NULL,
            nickname VARCHAR(50) NOT NULL,
            avatar VARCHAR(200) DEFAULT '',
            bio VARCHAR(200) DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB
    """)
    execute("""
        CREATE TABLE IF NOT EXISTS attractions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            category VARCHAR(50) DEFAULT '商场',
            description TEXT,
            address VARCHAR(200) DEFAULT '',
            bus_route VARCHAR(200) DEFAULT '',
            lng DECIMAL(10,6) DEFAULT NULL,
            lat DECIMAL(10,6) DEFAULT NULL,
            hours VARCHAR(100) DEFAULT '',
            hot INT DEFAULT 0,
            image_url VARCHAR(300) DEFAULT ''
        ) ENGINE=InnoDB
    """)
    execute("""
        CREATE TABLE IF NOT EXISTS restaurants (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            cuisine VARCHAR(50) DEFAULT '',
            recommend_dish VARCHAR(100) DEFAULT '',
            price_level VARCHAR(20) DEFAULT '¥',
            rating DECIMAL(2,1) DEFAULT 5.0,
            address VARCHAR(200) DEFAULT '',
            lng DECIMAL(10,6) DEFAULT NULL,
            lat DECIMAL(10,6) DEFAULT NULL,
            description TEXT,
            hot INT DEFAULT 0,
            image_url VARCHAR(300) DEFAULT ''
        ) ENGINE=InnoDB
    """)
    execute("""
        CREATE TABLE IF NOT EXISTS cultural_sites (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            site_type VARCHAR(50) DEFAULT '博物馆',
            description TEXT,
            address VARCHAR(200) DEFAULT '',
            lng DECIMAL(10,6) DEFAULT NULL,
            lat DECIMAL(10,6) DEFAULT NULL,
            hours VARCHAR(100) DEFAULT '',
            ticket VARCHAR(100) DEFAULT '免费',
            hot INT DEFAULT 0,
            image_url VARCHAR(300) DEFAULT ''
        ) ENGINE=InnoDB
    """)
    execute("""
        CREATE TABLE IF NOT EXISTS theaters (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            show_type VARCHAR(50) DEFAULT '音乐剧',
            description TEXT,
            address VARCHAR(200) DEFAULT '',
            schedule VARCHAR(200) DEFAULT '',
            price_level VARCHAR(20) DEFAULT '¥',
            hot INT DEFAULT 0,
            image_url VARCHAR(300) DEFAULT ''
        ) ENGINE=InnoDB
    """)
    execute("""
        CREATE TABLE IF NOT EXISTS routes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(100) NOT NULL,
            theme VARCHAR(50) DEFAULT '美食',
            stops TEXT,
            description TEXT,
            duration VARCHAR(50) DEFAULT '半日游',
            hot INT DEFAULT 0
        ) ENGINE=InnoDB
    """)
    execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            category VARCHAR(50) DEFAULT '游记',
            title VARCHAR(200) NOT NULL,
            content TEXT,
            image_url VARCHAR(300) DEFAULT '',
            likes INT DEFAULT 0,
            views INT DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB
    """)
    execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            post_id INT NOT NULL,
            user_id INT NOT NULL,
            content VARCHAR(500) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB
    """)
    execute("""
        CREATE TABLE IF NOT EXISTS contact_messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(50) NOT NULL,
            email VARCHAR(100) NOT NULL,
            subject VARCHAR(100) DEFAULT '',
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB
    """)

    _seed_attractions()
    _seed_restaurants()
    _seed_cultural_sites()
    _seed_theaters()
    _seed_routes()
    _seed_posts()


def _seed_attractions():
    """公交可达的游玩地（带经纬度，供百度地图标注）。"""
    if query_one("SELECT id FROM attractions LIMIT 1"):
        return
    items = [
        ("澳德乐时代广场", "商场", "德州人气最旺的大型购物中心，吃喝玩乐购一站搞定。",
         "德城区东风东路", "可乘 1路 / 2路 / 101路 到达", 116.383000, 37.451000,
         "10:00-21:30", 98, ""),
        ("减河湿地公园", "公园", "城市里的天然氧吧，适合骑行、散步、看日落。",
         "德城区南部", "可乘 12路 / 23路 到达", 116.423000, 37.428000,
         "全天开放", 90, ""),
        ("董子文化街", "文化街区", "以汉代大儒董仲舒为主题的文化街区，夜景很美。",
         "德城区", "可乘 5路 / 18路 到达", 116.392000, 37.442000,
         "全天开放", 92, ""),
        ("长河公园", "公园", "德州地标性城市公园，湖光树影，适合全家出游。",
         "德城区长河大道", "可乘 6路 / 20路 到达", 116.371000, 37.446000,
         "全天开放", 85, ""),
        ("明月湖", "景点", "傍晚华灯初上，湖面倒影如画，是本地人散步首选。",
         "德城区", "可乘 8路 / 31路 到达", 116.377000, 37.440000,
         "全天开放", 88, ""),
        ("美食夜市街", "夜市", "德州夜生活的烟火气，小吃、烧烤、糖炒栗子应有尽有。",
         "德城区三八路", "可乘 2路 / 11路 到达", 116.368000, 37.452000,
         "18:00-次日01:00", 95, ""),
    ]
    for it in items:
        execute("""
            INSERT INTO attractions
            (name, category, description, address, bus_route, lng, lat, hours, hot, image_url)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, it)


def _seed_restaurants():
    """网红打卡餐厅（带经纬度）。"""
    if query_one("SELECT id FROM restaurants LIMIT 1"):
        return
    items = [
        ("老德州扒鸡总店", "鲁菜", "五香脱骨德州扒鸡", "¥68", 4.9,
         "德城区解放路", 116.358000, 37.443000,
         "来德州必吃的中华老字号，鸡肉软烂脱骨，香气扑鼻。", 99, ""),
        ("运河人家农家菜", "鲁菜/家常", "运河酥鱼、炒合菜", "¥45", 4.7,
         "运河岸边", 116.345000, 37.435000,
         "坐在运河边吃家常菜，看货船往来，很德州。", 90, ""),
        ("老街坊驴肉火烧", "小吃", "驴肉火烧、焖子", "¥20", 4.8,
         "德城区老街", 116.361000, 37.447000,
         "热乎乎的火烧夹上驴肉，是德州人的早餐灵魂。", 93, ""),
        ("深夜烧烤研究所", "烧烤", "烤串、烤冷面", "¥60", 4.6,
         "夜市街口", 116.369000, 37.453000,
         "网红烧烤店，排队都要吃的深夜食堂。", 88, ""),
        ("董子文化茶馆", "茶饮", "手打柠檬茶、茶点", "¥30", 4.5,
         "董子文化街", 116.392000, 37.442000,
         "逛完文化街来这儿歇脚，拍照超出片。", 84, ""),
        ("运河畔咖啡", "咖啡", "拿铁、脏脏包", "¥35", 4.7,
         "运河公园旁", 116.350000, 37.438000,
         "落地窗看运河，德州少有的文艺咖啡馆。", 87, ""),
    ]
    for it in items:
        execute("""
            INSERT INTO restaurants
            (name, cuisine, recommend_dish, price_level, rating, address,
             lng, lat, description, hot, image_url)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, it)


def _seed_cultural_sites():
    """图书馆 / 博物馆 / 文化馆（带经纬度）。"""
    if query_one("SELECT id FROM cultural_sites LIMIT 1"):
        return
    items = [
        ("德州市博物馆", "博物馆", "了解德州五千年文明史，从大运河到近代工业的城市记忆。",
         "德城区东方红路", 116.378000, 37.449000,
         "09:00-17:00（周一闭馆）", "免费", 96, ""),
        ("德州市图书馆", "图书馆", "城市书房，环境安静，自习阅读好去处。",
         "德城区新湖景区旁", 116.375000, 37.446000,
         "08:30-20:30", "免费", 88, ""),
        ("德州大运河文化博物馆", "博物馆", "讲述京杭大运河德州段的千年漕运故事。",
         "运河文化带", 116.352000, 37.436000,
         "09:00-17:00", "免费", 91, ""),
        ("苏禄王墓博物馆", "纪念馆", "全国重点文保单位，记录中菲友好交往的珍贵历史。",
         "德城区", 116.395000, 37.455000,
         "09:00-17:00", "免费", 87, ""),
        ("德州市文化馆", "文化馆", "非遗展示、书画展览、公益培训，德州文化的大本营。",
         "德城区", 116.370000, 37.450000,
         "09:00-18:00", "免费", 82, ""),
    ]
    for it in items:
        execute("""
            INSERT INTO cultural_sites
            (name, site_type, description, address, lng, lat, hours, ticket, hot, image_url)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, it)


def _seed_theaters():
    """小剧场 / 演出。"""
    if query_one("SELECT id FROM theaters LIMIT 1"):
        return
    items = [
        ("德州大剧院", "音乐剧", "德州市最高规格的演出场所，引进音乐剧、话剧、交响乐。",
         "德城区", "每周五/六晚 19:30", "¥80-280", 90, ""),
        ("运河相声社", "相声", "本土相声团队，把德州方言和段子搬上舞台，笑到岔气。",
         "老街小剧场", "每周六晚 20:00", "¥40-80", 94, ""),
        ("德州喜剧工厂", "小品/脱口秀", "年轻人组局的小剧场，脱口秀、漫才、即兴喜剧。",
         "澳德乐负一层", "每周日 19:00", "¥50-120", 89, ""),
        ("评剧票友社", "戏曲", "德州本地评剧票友的舞台，原汁原味的传统戏曲。",
         "文化馆剧场", "逢周末下午", "¥30", 80, ""),
    ]
    for it in items:
        execute("""
            INSERT INTO theaters
            (name, show_type, description, address, schedule, price_level, hot, image_url)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, it)


def _seed_routes():
    """城市漫游路线（特色功能）。"""
    if query_one("SELECT id FROM routes LIMIT 1"):
        return
    items = [
        ("运河晨光半日游", "文化", "德州市博物馆 -> 大运河文化博物馆 -> 运河人家吃酥鱼 -> 运河公园",
         "早上逛两个博物馆了解德州，中午在运河边吃酥鱼，下午沿河散步。适合文化爱好者。",
         "半日游", 90),
        ("老德州美食地图", "美食", "老街驴肉火烧 -> 董子文化茶馆 -> 老德州扒鸡总店 -> 美食夜市街",
         "从早吃到晚，把德州最有名的味道一次性吃遍。吃货闭眼冲。",
         "一日游", 95),
        ("文艺青年漫游", "文艺", "运河畔咖啡 -> 德州市图书馆 -> 德州大剧院看音乐剧 -> 深夜烧烤",
         "白天泡图书馆和咖啡馆，晚上看一场演出，收尾来顿烧烤。",
         "一日游", 86),
        ("亲子欢乐路线", "亲子", "减河湿地公园 -> 长河公园放风筝 -> 澳德乐儿童乐园 -> 明月湖看夜景",
         "适合带娃，动静结合，大人小孩都不累。",
         "一日游", 88),
    ]
    for it in items:
        execute("""
            INSERT INTO routes (title, theme, stops, description, duration, hot)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, it)


def _seed_posts():
    """论坛示例帖子 + 演示账号 + 管理员账号（含团队实拍的德州照片帖）。"""
    # 演示账号
    if not query_one("SELECT id FROM users WHERE username='demo'"):
        execute("""
            INSERT INTO users (username, password, nickname, bio)
            VALUES ('demo', '123456', '运河小导游', '本地土著，带你玩转德州')
        """)
    # 管理员账号：以官方身份发布实拍内容
    if not query_one("SELECT id FROM users WHERE username='admin'"):
        execute("""
            INSERT INTO users (username, password, nickname, bio)
            VALUES ('admin', 'admin888', '德州文旅管理员', '三个臭皮匠团队 · 德州文旅信息平台官方账号')
        """)
    demo = query_one("SELECT id FROM users WHERE username='demo'")
    uid = demo["id"]
    # 文字示例帖（仅在完全没有帖子时补充）
    if not query_one("SELECT id FROM posts LIMIT 1"):
        posts = [
            (uid, "游记", "第一次来德州，这三件事别错过！",
             "作为一个外省游客，强烈推荐：①尝一次正宗的德州扒鸡；②傍晚去运河边看货船；③去博物馆了解这座城市。"),
            (uid, "美食", "收藏！德州最好吃的驴肉火烧在哪？",
             "老街那家驴肉火烧yyds，热火烧夹驴肉，加点焖子，人均20吃到扶墙。"),
            (uid, "问答", "从火车站坐公交去澳德乐怎么走？",
             "出站坐1路或101路，大约20分钟直达，澳德乐在东风东路。"),
            (uid, "避坑", "给来德州玩的朋友提个醒",
             "①博物馆周一闭馆别跑空；②夜市晚上6点后才热闹；③扒鸡认准老字号。"),
        ]
        for p in posts:
            execute("INSERT INTO posts (user_id, category, title, content) VALUES (%s,%s,%s,%s)", p)
            pid = query_one("SELECT id FROM posts ORDER BY id DESC LIMIT 1")["id"]
            execute("INSERT INTO comments (post_id, user_id, content) VALUES (%s,%s,%s)",
                    (pid, uid, "顶一个，写得很实用！"))
    # 带图实拍帖：使用团队拍摄的德州照片，仅在还没有带图帖子时插入
    if not query_one("SELECT id FROM posts WHERE image_url != '' LIMIT 1"):
        admin = query_one("SELECT id FROM users WHERE username='admin'")
        aid = admin["id"]
        photo_posts = [
            (aid, "游记", "实拍｜德州市博物馆，一座城的历史都在这里",
             "走进德州市博物馆，从大运河的漕运故事到近代工业的城市记忆，慢慢逛能读懂德州五千年。门口“道中华杯”主题展也很有看头。",
             "/static/img/dezhou/dezhou1.jpg"),
            (aid, "其他", "实拍｜学校门口的公交站，坐公交去逛德州",
             "公交是逛德州最省钱的方式。这是华宇工学院、德州职业技术学院门口的车站，2路、102路、112路都能到市区，扫码即乘，非常方便。",
             "/static/img/dezhou/dezhou2.jpg"),
            (aid, "美食", "实拍｜银座商圈，德州人的“逛吃”主场",
             "银座INZONE是德州人常去的商圈，喜茶、海底捞、咖啡店都在楼下，逛街吃饭看电影一站搞定，周末来这里准没错。",
             "/static/img/dezhou/dezhou4.jpg"),
            (aid, "其他", "实拍｜商场里的儿童乐园",
             "商场中庭的亲子游乐区，沙池、积木、模拟驾驶都有，带孩子来逛银座，大人逛街小孩放电。",
             "/static/img/dezhou/dezhou3.jpg"),
        ]
        for p in photo_posts:
            execute("INSERT INTO posts (user_id, category, title, content, image_url) VALUES (%s,%s,%s,%s,%s)", p)


# ======================================================
# 三、页面路由
# ======================================================
@app.route("/")
def index():
    """首页：栏目入口 + 热门推荐 + 最新帖子 + 宣传视频。"""
    hot_places = query("SELECT * FROM attractions ORDER BY hot DESC LIMIT 4")
    hot_food = query("SELECT * FROM restaurants ORDER BY hot DESC LIMIT 4")
    hot_theaters = query("SELECT * FROM theaters ORDER BY hot DESC LIMIT 3")
    latest_posts = query("""
        SELECT p.*, u.nickname FROM posts p
        JOIN users u ON p.user_id = u.id
        ORDER BY p.created_at DESC LIMIT 4
    """)
    return render_template("index.html",
                           hot_places=hot_places, hot_food=hot_food,
                           hot_theaters=hot_theaters, latest_posts=latest_posts)


@app.route("/attractions")
def attractions():
    """公交可达的游玩地：支持按分类筛选。"""
    category = request.args.get("category", "")
    if category:
        rows = query("SELECT * FROM attractions WHERE category=%s ORDER BY hot DESC", (category,))
    else:
        rows = query("SELECT * FROM attractions ORDER BY hot DESC")
    cats = [r["category"] for r in query("SELECT DISTINCT category FROM attractions")]
    return render_template("attractions.html", rows=rows, cats=cats, active=category)


@app.route("/food")
def food():
    """网红餐厅。"""
    rows = query("SELECT * FROM restaurants ORDER BY hot DESC")
    return render_template("food.html", rows=rows)


@app.route("/culture")
def culture():
    """图书馆/博物馆/文化馆。"""
    stype = request.args.get("type", "")
    if stype:
        rows = query("SELECT * FROM cultural_sites WHERE site_type=%s ORDER BY hot DESC", (stype,))
    else:
        rows = query("SELECT * FROM cultural_sites ORDER BY hot DESC")
    types = [r["site_type"] for r in query("SELECT DISTINCT site_type FROM cultural_sites")]
    return render_template("culture.html", rows=rows, types=types, active=stype)


@app.route("/theater")
def theater():
    """小剧场 / 演出。"""
    rows = query("SELECT * FROM theaters ORDER BY hot DESC")
    return render_template("theater.html", rows=rows)


@app.route("/routes")
def routes():
    """城市漫游路线（特色功能）。"""
    rows = query("SELECT * FROM routes ORDER BY hot DESC")
    return render_template("routes.html", rows=rows)


@app.route("/map")
def map_page():
    """创新点：百度地图一站看全——把景点/美食/文化场馆标注在地图上。"""
    spots = query("""
        SELECT name, category AS kind, address, lng, lat, bus_route
        FROM attractions WHERE lng IS NOT NULL
        UNION ALL
        SELECT name, '美食' AS kind, address, lng, lat, '' AS bus_route
        FROM restaurants WHERE lng IS NOT NULL
        UNION ALL
        SELECT name, site_type AS kind, address, lng, lat, '' AS bus_route
        FROM cultural_sites WHERE lng IS NOT NULL
    """)
    return render_template("map.html", spots=spots, ak=BAIDU_MAP_AK)


# ---------------- 论坛 ----------------
@app.route("/forum")
def forum():
    """论坛广场：所有帖子。"""
    category = request.args.get("category", "")
    if category:
        rows = query("""
            SELECT p.*, u.nickname,
                   (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) AS comment_count
            FROM posts p JOIN users u ON p.user_id = u.id
            WHERE p.category = %s
            ORDER BY p.created_at DESC
        """, (category,))
    else:
        rows = query("""
            SELECT p.*, u.nickname,
                   (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) AS comment_count
            FROM posts p JOIN users u ON p.user_id = u.id
            ORDER BY p.created_at DESC
        """)
    cats = ["游记", "美食", "问答", "避坑", "其他"]
    return render_template("forum.html", rows=rows, cats=cats, active=category)


@app.route("/post/<int:pid>")
def post_detail(pid):
    """帖子详情 + 评论区。"""
    post = query_one("""
        SELECT p.*, u.nickname FROM posts p
        JOIN users u ON p.user_id = u.id WHERE p.id = %s
    """, (pid,))
    if not post:
        return "帖子不存在", 404
    execute("UPDATE posts SET views = views + 1 WHERE id = %s", (pid,))
    comments = query("""
        SELECT c.*, u.nickname FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.post_id = %s ORDER BY c.created_at ASC
    """, (pid,))
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
        execute("""
            INSERT INTO posts (user_id, category, title, content, image_url)
            VALUES (%s,%s,%s,%s,%s)
        """, (session["user_id"], category, title, content, image_url))
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
        execute("""
            INSERT INTO comments (post_id, user_id, content) VALUES (%s,%s,%s)
        """, (pid, session["user_id"], content))
        flash("评论成功！")
    return redirect(url_for("post_detail", pid=pid))


@app.route("/post/<int:pid>/like", methods=["POST"])
def like_post(pid):
    """点赞。"""
    execute("UPDATE posts SET likes = likes + 1 WHERE id = %s", (pid,))
    return redirect(url_for("post_detail", pid=pid))


# ---------------- 联系我们（创新点：邮箱留言） ----------------
@app.route("/contact", methods=["GET", "POST"])
def contact():
    """联系我们：访客留言（存数据库），并提供团队邮箱。"""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        subject = request.form.get("subject", "").strip()
        content = request.form.get("content", "").strip()
        if not name or not email or not content:
            flash("姓名、邮箱和留言内容都不能为空")
        else:
            execute("""
                INSERT INTO contact_messages (name, email, subject, content)
                VALUES (%s,%s,%s,%s)
            """, (name, email, subject, content))
            flash("留言已收到，我们会尽快回复你，感谢支持！")
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
        elif query_one("SELECT id FROM users WHERE username=%s", (username,)):
            flash("用户名已被占用")
        else:
            execute("""
                INSERT INTO users (username, password, nickname) VALUES (%s,%s,%s)
            """, (username, password, nickname))
            flash("注册成功，请登录！")
            return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """登录。"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user = query_one("SELECT * FROM users WHERE username=%s AND password=%s",
                         (username, password))
        if user:
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
# 四、启动入口
# ======================================================
if __name__ == "__main__":
    init_database()          # 启动时自动建库建表 + 塞示例数据
    print("=" * 50)
    print("  德州文旅网站已启动！")
    print("  请在浏览器打开： http://127.0.0.1:5000")
    print("=" * 50)
    app.run(debug=True)
