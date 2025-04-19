// Main JavaScript file for Blog Automation Platform

document.addEventListener('DOMContentLoaded', function() {
    // Enable all tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Enable all popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Auto-hide alerts after 5 seconds
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // Add event listener to the setup form if it exists
    const setupForm = document.getElementById('setupForm');
    if (setupForm) {
        setupForm.addEventListener('submit', function(event) {
            // Disable the submit button to prevent double submissions
            const submitButton = setupForm.querySelector('button[type="submit"]');
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Creating...';
            }
        });
        
        // Toggle domain suggestions fields based on checkbox
        const domainSuggestionsCheckbox = document.getElementById('enableDomainSuggestions');
        const maxPriceField = document.getElementById('maxPrice');
        
        if (domainSuggestionsCheckbox && maxPriceField) {
            const toggleMaxPriceField = function() {
                maxPriceField.disabled = !domainSuggestionsCheckbox.checked;
            };
            
            // Initial state
            toggleMaxPriceField();
            
            // On change
            domainSuggestionsCheckbox.addEventListener('change', toggleMaxPriceField);
        }
    }
});