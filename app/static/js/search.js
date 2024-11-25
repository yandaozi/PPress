document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.querySelector('input[name="q"]');
    const suggestionsContainer = document.createElement('div');
    suggestionsContainer.className = 'absolute w-full bg-white border rounded-lg shadow-lg mt-1 hidden';
    searchInput.parentElement.appendChild(suggestionsContainer);
    
    let debounceTimer;
    
    searchInput.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        const query = this.value.trim();
        
        if (query.length < 2) {
            suggestionsContainer.innerHTML = '';
            suggestionsContainer.classList.add('hidden');
            return;
        }
        
        debounceTimer = setTimeout(() => {
            fetch(`/search/suggestions?q=${encodeURIComponent(query)}`)
                .then(response => response.json())
                .then(suggestions => {
                    if (suggestions.length > 0) {
                        suggestionsContainer.innerHTML = suggestions.map(s => `
                            <div class="px-4 py-2 hover:bg-gray-100 cursor-pointer">
                                ${s}
                            </div>
                        `).join('');
                        suggestionsContainer.classList.remove('hidden');
                        
                        // 点击建议项
                        suggestionsContainer.querySelectorAll('div').forEach(div => {
                            div.addEventListener('click', function() {
                                searchInput.value = this.textContent.trim();
                                suggestionsContainer.classList.add('hidden');
                                searchInput.form.submit();
                            });
                        });
                    } else {
                        suggestionsContainer.classList.add('hidden');
                    }
                });
        }, 300);
    });
    
    // 点击外部时隐藏建议
    document.addEventListener('click', function(e) {
        if (!searchInput.contains(e.target) && !suggestionsContainer.contains(e.target)) {
            suggestionsContainer.classList.add('hidden');
        }
    });
}); 