/* Shared voice-pill click handler — used by wizard step 2 and /profile */
(function () {
    document.addEventListener('click', function (e) {
        var pill = e.target.closest('.voice-pill');
        if (!pill) return;
        var container = pill.closest('.voice-pills');
        if (!container) return;
        var targetName = container.dataset.target;
        var textarea = document.querySelector('textarea[name="' + targetName + '"]');
        if (!textarea) return;
        textarea.value = pill.dataset.text || '';
        container.querySelectorAll('.voice-pill').forEach(function (p) { p.classList.remove('is-active'); });
        pill.classList.add('is-active');
        textarea.focus();
        textarea.setSelectionRange(textarea.value.length, textarea.value.length);
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
    });
}());
