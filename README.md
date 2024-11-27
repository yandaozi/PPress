# PPress 博客系统

## 项目简介
这是一个基于 Flask 框架开发的PPress技术博客系统,带有文章情感分析,黑夜模式等以下主要功能:

- 用户系统
  - 注册/登录(支持验证码)
  - 个人中心
  - 用户主页
- 文章管理
  - 发布/编辑文章
  - Markdown编辑器
  - 图片上传
  - 文章分类与标签
- 评论系统
- 后台管理
  - 用户管理
  - 文章管理  
  - 评论管理
  - 分类管理
  - 标签管理
  - 网站配置

## 技术栈

- 后端
  - Flask - Web框架
  - SQLAlchemy - ORM框架
  - Flask-Login - 用户认证
  - Pillow - 图片处理
  - pandas/plotly - 数据分析与可视化

- 前端
  - Tailwind CSS - CSS框架
  - TinyMce - 富文本编辑器
  - jQuery - JavaScript库
  - Plotly.js - 图表库

## 项目截图
<p align="center">首页截图</p>

![首页截图](/viewimg/index.png)

<p align="center">标签页</p>

![标签页](/viewimg/tagpage.png)

<p align="center">搜索页</p>

![搜索页](/viewimg/search.png)

<p align="center">文章内页</p>

![文章内页](/viewimg/article.png)

<p align="center">个人中心</p>

![个人中心](/viewimg/mepage.png)

<p align="center">创建文章</p>

![创建文章](/viewimg/create_article.png)

<p align="center">我的文章</p>

![我的文章](/viewimg/myarticle.png)

<p align="center">文章作者主页</p>

![文章作者主页](/viewimg/userpage.png)

<p align="center">管理控制面板首页</p>

![管理控制面板首页](/viewimg/admin_dashboard.png)

<p align="center">用户管理</p>

![用户管理](/viewimg/admin_users.png)

<p align="center">文章管理</p>

![文章管理](/viewimg/admin_articles.png)

<p align="center">评论管理</p>

![评论管理](/viewimg/admin_comments.png)

<p align="center">分类管理</p>

![分类管理](/viewimg/admin_categories.png)

<p align="center">标签管理</p>

![标签管理](/viewimg/admin_tags.png)

<p align="center">网站信息配置</p>

![网站信息配置](/viewimg/admin_siteconfig.png)








## 项目结构

app/

├── init.py # Flask应用工厂

├── extensions.py # Flask扩展初始化

├── models/ # 数据模型

├── static/ # 静态文件

│ ├── css/

│ ├── js/

│ └── uploads/ # 上传文件目录

├── templates/ # 模板文件

│ ├── admin/ # 后台模板

│ ├── auth/ # 认证相关模板

│ ├── blog/ # 博客相关模板

│ └── user/ # 用户相关模板

├── utils/ # 工具函数

└── views/ # 视图函数

├── admin.py # 后台管理

├── auth.py # 用户认证

├── blog.py # 博客功能

└── user.py # 用户功能

## 安装部署

1. git clone 克隆代码
2. 安装依赖 pip install -r requirements.txt
3. 配置数据库 数据库，用户，密码都是flaskiosblog
4. 运行 init_db_purity.py(init_db.py为初始化测试数据库) 文件 初始化数据库，代码中有初始测试数据需要自行删除更改
5. 运行 run.py

## 使用说明

1. 注册管理员账号
- 访问 `/register` 注册账号
- 在数据库中将该用户的 role 字段改为 'admin'

2. 基本配置
- 登录后台 `/admin/dashboard`
- 在网站配置中设置站点信息

3. 开始使用
- 创建分类
- 发布文章
- 管理评论
- 等等

## 开发计划

- [ ] 添加文章归档功能
- [ ] 支持更多Markdown扩展语法
- [ ] 添加文章订阅功能
- [ ] 优化移动端适配
- [ ] 支持社交媒体分享

## 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交代码
4. 发起 Pull Request

## 许可证

本项目采用 MIT 许可证,详情请参阅 [LICENSE](LICENSE) 文件。