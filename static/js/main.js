// Main JavaScript file for the inventory system

// Initialize Select2 dropdowns
document.addEventListener('DOMContentLoaded', function() {
    if (typeof($.fn.select2) !== 'undefined') {
        $('.select2').select2();
    }
    
    // Form submission logging
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            console.log('Form is being submitted');
        });
    });
});