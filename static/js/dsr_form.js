document.addEventListener('DOMContentLoaded', function () {
    function bytesToMb(bytes) {
        return (bytes / (1024 * 1024)).toFixed(2);
    }

    function wireFileInput(inputId, infoId) {
        var input = document.getElementById(inputId);
        var info = document.getElementById(infoId);
        if (!input || !info) {
            return;
        }
        var maxMb = parseFloat(input.getAttribute('data-max-size-mb')) || null;

        input.addEventListener('change', function () {
            var files = Array.prototype.slice.call(input.files);
            if (files.length === 0) {
                info.textContent = '';
                return;
            }

            var names = files.map(function (f) { return f.name; }).join(', ');
            var messages = [files.length + ' file(s) selected: ' + names];

            if (maxMb) {
                var tooBig = files.filter(function (f) {
                    return f.size > maxMb * 1024 * 1024;
                });
                if (tooBig.length > 0) {
                    var tooBigNames = tooBig.map(function (f) {
                        return f.name + ' (' + bytesToMb(f.size) + ' MB)';
                    }).join(', ');
                    messages.push('Warning: exceeds ' + maxMb + ' MB limit - ' + tooBigNames);
                }
            }

            info.textContent = messages.join(' ');
        });
    }

    wireFileInput('id_project_photos', 'project_photos_info');
    wireFileInput('id_attachments', 'attachments_info');
});
