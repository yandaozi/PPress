// 文章统计功能
function calculateStats(articleId) {
    fetch(`/calculate/${articleId}`)
        .then(response => response.json())
        .then(data => {
            const statsContainer = document.getElementById('article-stats');
            if (statsContainer) {
                let statsHtml = '<div class="space-y-2">';
                if (data.word_count) {
                    statsHtml += `<div>字数：${data.word_count}</div>`;
                }
                if (data.read_time) {
                    statsHtml += `<div>预计阅读时间：${data.read_time} 分钟</div>`;
                }
                if (data.code_blocks) {
                    statsHtml += `<div>代码块：${data.code_blocks} 个</div>`;
                }
                if (data.images) {
                    statsHtml += `<div>图片：${data.images} 张</div>`;
                }
                statsHtml += '</div>';
                statsContainer.innerHTML = statsHtml;
            }
        })
        .catch(error => console.error('Error calculating stats:', error));
}

// 在页面加载时自动计算统计信息
document.addEventListener('DOMContentLoaded', function() {
    const articleContainer = document.querySelector('article');
    if (articleContainer) {
        const articleId = articleContainer.dataset.articleId;
        if (articleId) {
            calculateStats(articleId);
        }
    }
}); 