# PPress

## 项目简介
这是一个基于 Flask 框架开发的 PPress 博客系统,内存缓存,缓存预热,支持sqlite和mysql两种数据库,带有文章情感分析,黑夜模式等以下主要功能:

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
![1.png](viewimg/1.png)

![2.png](viewimg/2.png)

![3.png](viewimg/3.png)

![4.png](viewimg/4.png)

![5.png](viewimg/5.png)

![6.png](viewimg/6.png)

![7.png](viewimg/7.png)

![8.png](viewimg/8.png)

![9.png](viewimg/9.png)

![10.png](viewimg/10.png)

![11.png](viewimg/11.png)

![12.png](viewimg/12.png)

![13.png](viewimg/13.png)

![14.png](viewimg/14.png)

![15.png](viewimg/15.png)

![16.png](viewimg/16.png)

![17.png](viewimg/17.png)

![18.png](viewimg/18.png)








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
3. 配置数据库 数据库，用户:config/database的MYSQL_CONFIG中
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