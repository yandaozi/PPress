// 加载文章统计信息
function loadArticleStats(articleId) {
    fetch(`/plugin/article_stats/calculate/${articleId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            const statsContainer = document.getElementById('article-stats');
            if (statsContainer) {
                let statsHtml = '';
                if (data.word_count) {
                    statsHtml += `
                        <div class="flex items-center">
                            <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                            </svg>
                            字数：${data.word_count}
                        </div>`;
                }
                if (data.read_time) {
                    statsHtml += `
                        <div class="flex items-center">
                            <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                            </svg>
                            预计阅读：${data.read_time} 分钟
                        </div>`;
                }
                if (data.code_blocks) {
                    statsHtml += `
                        <div class="flex items-center">
                            <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
                            </svg>
                            代码块：${data.code_blocks} 个
                        </div>`;
                }
                if (data.images) {
                    statsHtml += `
                        <div class="flex items-center">
                            <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
                            </svg>
                            图片：${data.images} 张
                        </div>`;
                }
                statsContainer.innerHTML = statsHtml;
            }
        })
        .catch(error => {
            console.error('Error loading article stats:', error);
            const statsContainer = document.getElementById('article-stats');
            if (statsContainer) {
                statsContainer.innerHTML = '<div class="text-red-500">加载统计信息失败</div>';
            }
        });
}

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    const articleContainer = document.querySelector('article');
    if (articleContainer) {
        const articleId = articleContainer.dataset.articleId;
        if (articleId) {
            loadArticleStats(articleId);
        }
    }
}); 