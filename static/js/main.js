document.addEventListener('DOMContentLoaded', function () {
    var toggle = document.getElementById('sidebarToggle');
    var sidebar = document.getElementById('sidebar');
    if (toggle && sidebar) {
        toggle.addEventListener('click', function () {
            sidebar.classList.toggle('show');
        });
    }
});

// Sitewide double-submit prevention: disable submit buttons (and show a
// spinner on the one actually clicked) once a form is submitted. Listening
// on 'submit' rather than 'click' means this only fires after any
// onclick="return confirm(...)" guard has been accepted - a cancelled
// confirm() never reaches here, so those flows are unaffected.
document.addEventListener('click', function (event) {
    var submitter = event.target.closest('button[type="submit"][name]');
    if (!submitter || !submitter.form) {
        return;
    }
    submitter.form._submittedAction = {
        name: submitter.name,
        value: submitter.value
    };
}, true);

document.addEventListener('submit', function (event) {
    var form = event.target;
    if (!(form instanceof HTMLFormElement)) {
        return;
    }
    var submitter = event.submitter;
    var submittedAction = submitter && submitter.name
        ? {name: submitter.name, value: submitter.value}
        : form._submittedAction;
    if (submittedAction) {
        var actionInput = document.createElement('input');
        actionInput.type = 'hidden';
        actionInput.name = submittedAction.name;
        actionInput.value = submittedAction.value;
        form.appendChild(actionInput);
    }
    var buttons = form.querySelectorAll('button[type="submit"]');
    buttons.forEach(function (btn) {
        btn.disabled = true;
        if (btn === submitter) {
            var spinner = document.createElement('span');
            spinner.className = 'spinner-border spinner-border-sm me-2';
            spinner.setAttribute('role', 'status');
            spinner.setAttribute('aria-hidden', 'true');
            btn.prepend(spinner);
        }
    });
}, true);
