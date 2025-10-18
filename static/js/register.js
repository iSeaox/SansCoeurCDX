function checkForm(e) {
    const emailInput = document.getElementById('email');
    const email = emailInput.value.trim();
    const password = document.getElementById('password').value;
    const passwordConfirm = document.getElementById('password_confirm').value;
    
    // Simple email format check in addition to HTML5 validation
    const emailRegex = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
    if (!email || !emailRegex.test(email)) {
        e.preventDefault();
        emailInput.focus();
        alert("Veuillez saisir un email valide.");
        return false;
    }

    if (password !== passwordConfirm) {
        e.preventDefault();
        alert('Les mots de passe ne correspondent pas.');
        return false;
    }
    
    if (password.length < 8) {
        e.preventDefault();
        alert('Le mot de passe doit contenir au moins 8 caractères.');
        return false;
    }
}