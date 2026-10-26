-- ============================================================
--  德州文旅 ·「九达天衢 · 韵动德州」
--  数据库建库建表脚本（供学习与手动改表参考）
--  说明：程序 app.py 启动时会自动建库建表并填入示例数据，
--        这份脚本是给你用 SQLyog 手动查看 / 修改用的。
-- ============================================================

CREATE DATABASE IF NOT EXISTS dezhou_tour
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE dezhou_tour;

-- ---------- 用户表 ----------
CREATE TABLE IF NOT EXISTS users (
    id           INT AUTO_INCREMENT PRIMARY KEY COMMENT '用户ID',
    username     VARCHAR(50)  NOT NULL UNIQUE COMMENT '用户名（登录用）',
    password     VARCHAR(100) NOT NULL COMMENT '密码',
    nickname     VARCHAR(50)  NOT NULL COMMENT '昵称（显示用）',
    avatar       VARCHAR(200) DEFAULT '' COMMENT '头像地址',
    bio          VARCHAR(200) DEFAULT '' COMMENT '个人简介',
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间'
) ENGINE=InnoDB COMMENT='用户表';

-- ---------- 公交可达游玩地 ----------
CREATE TABLE IF NOT EXISTS attractions (
    id          INT AUTO_INCREMENT PRIMARY KEY COMMENT 'ID',
    name        VARCHAR(100) NOT NULL COMMENT '名称（如 澳德乐）',
    category    VARCHAR(50)  DEFAULT '商场' COMMENT '分类：商场/公园/景点/夜市',
    description TEXT COMMENT '介绍',
    address     VARCHAR(200) DEFAULT '' COMMENT '地址',
    bus_route   VARCHAR(200) DEFAULT '' COMMENT '公交路线',
    lng         DECIMAL(10,6) DEFAULT NULL COMMENT '经度（百度地图标注用）',
    lat         DECIMAL(10,6) DEFAULT NULL COMMENT '纬度（百度地图标注用）',
    hours       VARCHAR(100) DEFAULT '' COMMENT '营业时间',
    hot         INT DEFAULT 0 COMMENT '热度值（越大越靠前）',
    image_url   VARCHAR(300) DEFAULT '' COMMENT '图片地址'
) ENGINE=InnoDB COMMENT='公交可达游玩地';

-- ---------- 网红餐厅 ----------
CREATE TABLE IF NOT EXISTS restaurants (
    id             INT AUTO_INCREMENT PRIMARY KEY COMMENT 'ID',
    name           VARCHAR(100) NOT NULL COMMENT '店名',
    cuisine        VARCHAR(50)  DEFAULT '' COMMENT '菜系',
    recommend_dish VARCHAR(100) DEFAULT '' COMMENT '招牌菜',
    price_level    VARCHAR(20)  DEFAULT '¥' COMMENT '人均价位',
    rating         DECIMAL(2,1) DEFAULT 5.0 COMMENT '评分（满分5）',
    address        VARCHAR(200) DEFAULT '' COMMENT '地址',
    lng            DECIMAL(10,6) DEFAULT NULL COMMENT '经度',
    lat            DECIMAL(10,6) DEFAULT NULL COMMENT '纬度',
    description    TEXT COMMENT '介绍',
    hot            INT DEFAULT 0 COMMENT '热度',
    image_url      VARCHAR(300) DEFAULT '' COMMENT '图片地址'
) ENGINE=InnoDB COMMENT='网红餐厅';

-- ---------- 文化场馆 ----------
CREATE TABLE IF NOT EXISTS cultural_sites (
    id          INT AUTO_INCREMENT PRIMARY KEY COMMENT 'ID',
    name        VARCHAR(100) NOT NULL COMMENT '场馆名',
    site_type   VARCHAR(50)  DEFAULT '博物馆' COMMENT '类型：图书馆/博物馆/文化馆/纪念馆',
    description TEXT COMMENT '介绍',
    address     VARCHAR(200) DEFAULT '' COMMENT '地址',
    lng         DECIMAL(10,6) DEFAULT NULL COMMENT '经度',
    lat         DECIMAL(10,6) DEFAULT NULL COMMENT '纬度',
    hours       VARCHAR(100) DEFAULT '' COMMENT '开放时间',
    ticket      VARCHAR(100) DEFAULT '免费' COMMENT '门票情况',
    hot         INT DEFAULT 0 COMMENT '热度',
    image_url   VARCHAR(300) DEFAULT '' COMMENT '图片地址'
) ENGINE=InnoDB COMMENT='文化场馆';

-- ---------- 小剧场演出 ----------
CREATE TABLE IF NOT EXISTS theaters (
    id          INT AUTO_INCREMENT PRIMARY KEY COMMENT 'ID',
    name        VARCHAR(100) NOT NULL COMMENT '剧场/演出名',
    show_type   VARCHAR(50)  DEFAULT '音乐剧' COMMENT '类型：音乐剧/相声/小品/脱口秀',
    description TEXT COMMENT '介绍',
    address     VARCHAR(200) DEFAULT '' COMMENT '地址',
    schedule    VARCHAR(200) DEFAULT '' COMMENT '近期排期',
    price_level VARCHAR(20)  DEFAULT '¥' COMMENT '票价',
    hot         INT DEFAULT 0 COMMENT '热度',
    image_url   VARCHAR(300) DEFAULT '' COMMENT '图片地址'
) ENGINE=InnoDB COMMENT='小剧场演出';

-- ---------- 城市漫游路线 ----------
CREATE TABLE IF NOT EXISTS routes (
    id          INT AUTO_INCREMENT PRIMARY KEY COMMENT 'ID',
    title       VARCHAR(100) NOT NULL COMMENT '路线标题',
    theme       VARCHAR(50)  DEFAULT '美食' COMMENT '主题：美食/文化/亲子/夜景',
    stops       TEXT COMMENT '游玩点（用 -> 分隔）',
    description TEXT COMMENT '路线介绍',
    duration    VARCHAR(50)  DEFAULT '半日游' COMMENT '时长',
    hot         INT DEFAULT 0 COMMENT '热度'
) ENGINE=InnoDB COMMENT='漫游路线';

-- ---------- 论坛帖子 ----------
CREATE TABLE IF NOT EXISTS posts (
    id          INT AUTO_INCREMENT PRIMARY KEY COMMENT '帖子ID',
    user_id     INT NOT NULL COMMENT '发帖人ID',
    category    VARCHAR(50) DEFAULT '游记' COMMENT '板块：游记/问答/美食/避坑/其他',
    title       VARCHAR(200) NOT NULL COMMENT '标题',
    content     TEXT COMMENT '正文',
    image_url   VARCHAR(300) DEFAULT '' COMMENT '配图地址（发帖时可上传）',
    likes       INT DEFAULT 0 COMMENT '点赞数',
    views       INT DEFAULT 0 COMMENT '浏览数',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '发布时间'
) ENGINE=InnoDB COMMENT='论坛帖子';

-- ---------- 评论 ----------
CREATE TABLE IF NOT EXISTS comments (
    id          INT AUTO_INCREMENT PRIMARY KEY COMMENT '评论ID',
    post_id     INT NOT NULL COMMENT '所属帖子ID',
    user_id     INT NOT NULL COMMENT '评论人ID',
    content     VARCHAR(500) NOT NULL COMMENT '评论内容',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '评论时间'
) ENGINE=InnoDB COMMENT='帖子评论';

-- ---------- 联系我们留言（新增创新功能） ----------
CREATE TABLE IF NOT EXISTS contact_messages (
    id         INT AUTO_INCREMENT PRIMARY KEY COMMENT '留言ID',
    name       VARCHAR(50)  NOT NULL COMMENT '访客姓名',
    email      VARCHAR(100) NOT NULL COMMENT '联系邮箱',
    subject    VARCHAR(100) DEFAULT '' COMMENT '留言主题',
    content    TEXT NOT NULL COMMENT '留言内容',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '留言时间'
) ENGINE=InnoDB COMMENT='联系我们留言';
