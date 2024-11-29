// 空状态 HTML 模板
const EMPTY_STATE_HTML = `
    <div class="text-center py-8">
        <svg class="w-16 h-16 mx-auto text-gray-300 dark:text-gray-600 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path>
        </svg>
        <p class="text-gray-500 dark:text-gray-400">暂无相关推荐</p>
    </div>
`;

// 错误状态 HTML 模板
const ERROR_STATE_HTML = `
    <div class="text-center py-8">
        <svg class="w-16 h-16 mx-auto text-red-300 dark:text-red-600 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
        </svg>
        <p class="text-red-500 dark:text-red-400">加载推荐文章失败</p>
    </div>
`;

// 渲染文章卡片
function renderArticleCard(article) {
    return `
        <a href="/article/${article.id}" 
           class="group block bg-gray-50 dark:bg-gray-700 rounded-lg p-6 transition-all duration-200 hover:shadow-md hover:bg-gray-100 dark:hover:bg-gray-600">
            <div class="space-y-4">
                <h4 class="font-bold text-gray-900 dark:text-gray-100 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors duration-200 line-clamp-2">
                    ${article.title}
                </h4>
                <p class="text-sm text-gray-600 dark:text-gray-300 line-clamp-2">
                    ${article.summary}
                </p>
                <div class="flex items-center justify-between">
                    <span class="text-sm text-gray-500 dark:text-gray-400">
                        ${article.category}
                    </span>
                    <div class="flex flex-wrap gap-2">
                        ${renderTags(article.tags)}
                    </div>
                </div>
            </div>
        </a>
    `;
}

// 渲染标签
function renderTags(tags) {
    const visibleTags = tags.slice(0, 2).map(tag => `
        <span class="text-xs px-2 py-1 bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded-full">
            ${tag}
        </span>
    `).join('');

    const remainingTags = tags.length > 2 ? `
        <span class="text-xs px-2 py-1 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 rounded-full">
            +${tags.length - 2}
        </span>
    ` : '';

    return visibleTags + remainingTags;
}

// 加载推荐文章
function loadRecommendations(articleId) {
    fetch(`/plugin/article_recommender/recommend/${articleId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(articles => {
            const container = document.getElementById('recommendations-container');
            if (container && articles.length > 0) {
                const html = `
                    <div class="grid gap-6 md:grid-cols-3">
                        ${articles.map(renderArticleCard).join('')}
                    </div>
                `;
                container.innerHTML = html;
            } else if (container) {
                container.innerHTML = EMPTY_STATE_HTML;
            }
        })
        .catch(error => {
            console.error('Error loading recommendations:', error);
            const container = document.getElementById('recommendations-container');
            if (container) {
                container.innerHTML = ERROR_STATE_HTML;
            }
        });
}

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    const articleContainer = document.querySelector('article');
    if (articleContainer) {
        const articleId = articleContainer.dataset.articleId;
        if (articleId) {
            loadRecommendations(articleId);
        }
    }
}); 