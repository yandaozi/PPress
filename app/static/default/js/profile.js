function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
}

function confirmDeleteHistory(historyId) {
    showAlert('确定要删除这条浏览记录吗？', 'warning', '确认删除', function() {
        fetch(`/user/history/${historyId}`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCsrfToken()
            }
        }).then(response => {
            if (response.ok) {
                const historyElement = document.querySelector(`[data-history-id="${historyId}"]`);
                if (historyElement) {
                    historyElement.remove();
                    const historyContainer = document.querySelector('.space-y-4');
                    if (!historyContainer.children.length) {
                        historyContainer.innerHTML = '<p class="text-gray-500 dark:text-gray-400 text-center py-8">暂无浏览历史</p>';
                    }
                } else {
                    location.reload();
                }
            } else {
                response.json().then(data => {
                    showAlert(data.error || '删除失败', 'error', '错误');
                });
            }
        }).catch(error => {
            showAlert('删除失败，请稍后重试', 'error', '错误');
            console.error('Error:', error);
        });
    });
}

function confirmDeleteAllHistory() {
    showAlert('确定要清空所有浏览记录吗？此操作不可恢复！', 'warning', '确认删除', function() {
        fetch('/user/history/all', {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCsrfToken()
            }
        }).then(response => {
            if (response.ok) {
                location.reload();
            } else {
                response.json().then(data => {
                    showAlert(data.error || '清空失败', 'error', '错误');
                });
            }
        }).catch(error => {
            showAlert('清空失败，请稍后重试', 'error', '错误');
            console.error('Error:', error);
        });
    });
}

// 图表初始化
document.addEventListener('DOMContentLoaded', function() {
    const chartElement = document.getElementById('interestsChart');
    if (chartElement && window.chartData) {
        if (document.documentElement.classList.contains('dark')) {
            window.chartData.layout.paper_bgcolor = '#1f2937';
            window.chartData.layout.plot_bgcolor = '#1f2937';
            window.chartData.layout.font = {
                color: '#e5e7eb'
            };
        }
        Plotly.newPlot('interestsChart', window.chartData.data, window.chartData.layout);
    }
});