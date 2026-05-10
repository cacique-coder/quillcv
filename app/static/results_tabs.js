window.switchResultsTab = function (tabId, btn) {
    document.querySelectorAll('.results-tab-panel').forEach(function (p) {
        p.style.display = 'none';
        p.classList.remove('results-tab-panel--active');
    });
    document.querySelectorAll('.results-tab').forEach(function (t) {
        t.classList.remove('results-tab--active');
    });
    var panel = document.getElementById('results-tab-' + tabId);
    if (panel) {
        panel.style.display = '';
        panel.classList.add('results-tab-panel--active');
    }
    if (btn) {
        btn.classList.add('results-tab--active');
    }
};
