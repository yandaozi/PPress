document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.querySelector('input[name="q"]');
    const mobileSearchInput = document.querySelector('#mobilesearchInput');
    const suggestionsBox = document.getElementById('searchSuggestions');
    const mobileSuggestionsBox = document.getElementById('mobilesearchSuggestions');

    function showSuggestions(input, suggestionsContainer) {
        const query = input.value.trim();
        if (query.length < 2) {
            suggestionsContainer.classList.add('hidden');
            return;
        }

        fetch(`/search/suggestions?q=${encodeURIComponent(query)}`)
            .then(response => response.json())
            .then(suggestions => {
                if (suggestions && suggestions.length > 0) {
                    suggestionsContainer.innerHTML = suggestions
                        .map(s => `
                            <a href="/search?q=${encodeURIComponent(s)}" 
                               class="block px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">
                                ${s}
                            </a>
                        `).join('');
                    suggestionsContainer.classList.remove('hidden');
                } else {
                    suggestionsContainer.classList.add('hidden');
                }
            })
            .catch(error => {
                console.error('搜索建议获取失败:', error);
                suggestionsContainer.classList.add('hidden');
            });
    }

    let debounceTimer;
    function debounce(func, wait) {
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(debounceTimer);
                func(...args);
            };
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(later, wait);
        };
    }

    const debouncedShowSuggestions = debounce(showSuggestions, 300);

    // 桌面端搜索
    if (searchInput) {
        searchInput.addEventListener('input', () => debouncedShowSuggestions(searchInput, suggestionsBox));
        document.addEventListener('click', (e) => {
            if (!searchInput.contains(e.target) && !suggestionsBox.contains(e.target)) {
                suggestionsBox.classList.add('hidden');
            }
        });
    }

    // 移动端搜索
    if (mobileSearchInput) {
        mobileSearchInput.addEventListener('input', () => debouncedShowSuggestions(mobileSearchInput, mobileSuggestionsBox));
        document.addEventListener('click', (e) => {
            if (!mobileSearchInput.contains(e.target) && !mobileSuggestionsBox.contains(e.target)) {
                mobileSuggestionsBox.classList.add('hidden');
            }
        });
    }

    const container = document.getElementById('categoriesContainer');
    const scrollLeftBtn = document.getElementById('scrollLeft');
    const scrollRightBtn = document.getElementById('scrollRight');

    if (container && scrollLeftBtn && scrollRightBtn) {
        // 更新按钮显示状态
        function updateScrollButtons() {
            const hasOverflow = container.scrollWidth > container.clientWidth;
            const atStart = container.scrollLeft <= 0;
            const atEnd = container.scrollLeft >= container.scrollWidth - container.clientWidth;

            // 只在有溢出内容时显示按钮
            scrollLeftBtn.style.display = hasOverflow && !atStart ? 'flex' : 'none';
            scrollRightBtn.style.display = hasOverflow && !atEnd ? 'flex' : 'none';
        }

        // 滚动处理函数
        function scroll(direction) {
            const scrollAmount = container.clientWidth / 2;
            container.scrollBy({
                left: direction * scrollAmount,
                behavior: 'smooth'
            });
        }

        // 事件监听
        scrollLeftBtn.addEventListener('click', () => scroll(-1));
        scrollRightBtn.addEventListener('click', () => scroll(1));
        container.addEventListener('scroll', updateScrollButtons);
        window.addEventListener('resize', updateScrollButtons);

        // 初始化按钮状态
        updateScrollButtons();
    }
}); 