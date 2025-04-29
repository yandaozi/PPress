import threading
import time
import logging
from datetime import datetime
import atexit

logger = logging.getLogger(__name__)

class ScheduledTask:
    """简单的定时任务类"""
    def __init__(self, interval=3600):  # 默认1小时
        self.interval = interval
        self.running = False
        self.thread = None
        self.last_run = None
        self.tasks = []
        
    def add_task(self, task_func, *args, **kwargs):
        """添加任务到调度器"""
        self.tasks.append((task_func, args, kwargs))
        
    def start(self):
        """启动定时任务"""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        atexit.register(self.stop)
        logger.info(f"定时任务调度器已启动，间隔: {self.interval}秒")
        
    def stop(self):
        """停止定时任务"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        logger.info("定时任务调度器已停止")
        
    def _run(self):
        """运行任务循环"""
        while self.running:
            try:
                self._execute_tasks()
                self.last_run = datetime.now()
            except Exception as e:
                logger.error(f"执行定时任务时出错: {e}")
                
            # 等待下一次执行
            time.sleep(self.interval)
            
    def _execute_tasks(self):
        """执行所有任务"""
        for task_func, args, kwargs in self.tasks:
            try:
                task_func(*args, **kwargs)
            except Exception as e:
                logger.error(f"执行任务 {task_func.__name__} 失败: {e}")
                
    def get_status(self):
        """获取调度器状态"""
        return {
            'running': self.running,
            'interval': self.interval,
            'last_run': self.last_run.strftime('%Y-%m-%d %H:%M:%S') if self.last_run else None,
            'tasks_count': len(self.tasks)
        }

# 创建文章获取定时器实例
article_scheduler = ScheduledTask(interval=3600)  # 1小时

def init_schedulers(app):
    """初始化定时任务"""
    with app.app_context():
        # 只有在生产环境才自动启动定时任务
        if app.config.get('FLASK_ENV') == 'production':
            from app.services.article_api_service import fetch_and_save_articles
            
            # 添加文章获取任务
            article_scheduler.add_task(fetch_and_save_articles, "热门")
            
            # 启动调度器
            article_scheduler.start()
            app.logger.info("文章自动获取定时任务已启动")
        else:
            app.logger.info("非生产环境，文章自动获取定时任务未启动") 