-- 用户表
CREATE TABLE user (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    avatar VARCHAR(200) DEFAULT '/static/default_avatar.png',
    role VARCHAR(20) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 文章表
CREATE TABLE article (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    author_id INTEGER NOT NULL,
    category_id INTEGER,
    view_count INTEGER DEFAULT 0,
    sentiment_score FLOAT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (author_id) REFERENCES user(id),
    FOREIGN KEY (category_id) REFERENCES category(id)
);

-- 评论表
CREATE TABLE comment (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    content TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    article_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (article_id) REFERENCES article(id)
);

-- 浏览历史表
CREATE TABLE view_history (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    user_id INTEGER NOT NULL,
    article_id INTEGER NOT NULL,
    viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (article_id) REFERENCES article(id)
);

-- 标签表
CREATE TABLE tag (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(50) UNIQUE NOT NULL
);

-- 文章标签关联表
CREATE TABLE article_tag (
    article_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (article_id, tag_id),
    FOREIGN KEY (article_id) REFERENCES article(id),
    FOREIGN KEY (tag_id) REFERENCES tag(id)
);

-- 分类表
CREATE TABLE category (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
-- 评论表
CREATE TABLE comments (
    id INT PRIMARY KEY AUTO_INCREMENT,
    article_id INT,
    user_id INT,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 浏览历史表
CREATE TABLE view_history (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    article_id INT,
    viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
); 