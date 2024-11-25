import os
import requests

def ensure_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def download_file(url, filepath):
    response = requests.get(url)
    with open(filepath, 'wb') as f:
        f.write(response.content)
    print(f"Downloaded: {filepath}")

# 创建必要的目录
static_dir = 'app/static'
ensure_dir(os.path.join(static_dir, 'css'))
ensure_dir(os.path.join(static_dir, 'js'))
ensure_dir(os.path.join(static_dir, 'vendor'))

# 下载资源
resources = {
    'tailwind': {
        'url': 'https://cdn.tailwindcss.com/3.3.5',
        'path': 'app/static/vendor/tailwind.min.js'
    },
    'jquery': {
        'url': 'https://code.jquery.com/jquery-3.6.0.min.js',
        'path': 'app/static/vendor/jquery.min.js'
    },
    'plotly': {
        'url': 'https://cdn.plot.ly/plotly-latest.min.js',
        'path': 'app/static/vendor/plotly.min.js'
    },
    'ckeditor': {
        'url': 'https://cdn.ckeditor.com/ckeditor5/39.0.1/classic/ckeditor.js',
        'path': 'app/static/vendor/ckeditor.js'
    }
}

for resource in resources.values():
    download_file(resource['url'], resource['path']) 