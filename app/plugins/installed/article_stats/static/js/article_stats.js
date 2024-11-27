class ArticleStats {
    constructor() {
        this.statsContainer = document.getElementById('article-stats');
        if (this.statsContainer) {
            this.articleId = this.statsContainer.dataset.articleId;
            if (this.articleId) {
                this.loadStats();
            }
        }
    }
    
    async loadStats() {
        try {
            const response = await fetch(`/article-stats/calculate/${this.articleId}`);
            if (!response.ok) throw new Error('Failed to load stats');
            const stats = await response.json();
            this.displayStats(stats);
        } catch (error) {
            console.error('Failed to load article stats:', error);
            this.displayError();
        }
    }
    
    displayStats(stats) {
        if (!this.statsContainer) return;
        
        const items = [];
        
        // 根据返回的数据显示对应的统计信息
        if ('read_time' in stats) {
            items.push(`
                <span title="预计阅读时长" class="flex items-center">
                    <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                    ${this.formatReadTime(stats.read_time)}
                </span>
            `);
        }
        
        if ('word_count' in stats) {
            items.push(`
                <span title="文章字数" class="flex items-center">
                    <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                    </svg>
                    ${this.formatNumber(stats.word_count)}字
                </span>
            `);
        }
        
        if ('code_blocks' in stats && stats.code_blocks > 0) {
            items.push(`
                <span title="代码块数量" class="flex items-center">
                    <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
                    </svg>
                    ${stats.code_blocks}段代码
                </span>
            `);
        }
        
        if ('images' in stats && stats.images > 0) {
            items.push(`
                <span title="图片数量" class="flex items-center">
                    <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
                    </svg>
                    ${stats.images}张图片
                </span>
            `);
        }
        
        if (items.length > 0) {
            this.statsContainer.innerHTML = `
                <div class="flex flex-wrap gap-4 text-sm text-gray-500 dark:text-gray-400">
                    ${items.join('')}
                </div>
            `;
        } else {
            this.statsContainer.style.display = 'none';
        }
    }
    
    displayError() {
        if (this.statsContainer) {
            this.statsContainer.style.display = 'none';
        }
    }
    
    formatReadTime(seconds) {
        if (seconds < 60) {
            return '不到1分钟';
        }
        const minutes = Math.floor(seconds / 60);
        return `约${minutes}分钟`;
    }
    
    formatNumber(num) {
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    new ArticleStats();
}); 