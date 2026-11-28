(() => {
  const decode = text => Uint8Array.from(atob(text.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0));
  const encode = buffer => btoa(String.fromCharCode(...new Uint8Array(buffer))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  for (const form of document.querySelectorAll('form[data-purpose]')) {
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const status = document.getElementById('passkey-status');
      const button = form.querySelector('button');
      button.disabled = true; status.textContent = 'Waiting for device verification...';
      try {
        if (!window.isSecureContext || !navigator.credentials) throw new Error('Passkeys are unavailable in this browser.');
        const csrf = form.querySelector('[name=csrfmiddlewaretoken]').value;
        const response = await fetch(form.dataset.begin, { method: 'POST', body: new FormData(form), headers: { 'X-CSRFToken': csrf }, credentials: 'same-origin' });
        const options = await response.json();
        if (!response.ok) throw new Error(options.error);
        const password = form.querySelector('[name=password]'); if (password) password.value = '';
        options.challenge = decode(options.challenge);
        for (const key of ['allowCredentials', 'excludeCredentials']) {
          if (options[key]) options[key] = options[key].map(item => ({ ...item, id: decode(item.id) }));
        }
        const registering = form.dataset.purpose === 'register';
        if (registering) options.user.id = decode(options.user.id);
        const credential = await navigator.credentials[registering ? 'create' : 'get']({ publicKey: options });
        const result = { id: credential.id, rawId: encode(credential.rawId), type: credential.type, response: { clientDataJSON: encode(credential.response.clientDataJSON) }, clientExtensionResults: credential.getClientExtensionResults() };
        if (registering) result.response.attestationObject = encode(credential.response.attestationObject);
        else {
          result.response.authenticatorData = encode(credential.response.authenticatorData);
          result.response.signature = encode(credential.response.signature);
          result.response.userHandle = credential.response.userHandle ? encode(credential.response.userHandle) : null;
        }
        const finished = await fetch(form.dataset.finish, { method: 'POST', body: JSON.stringify(result), headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf }, credentials: 'same-origin' });
        const outcome = await finished.json();
        if (!finished.ok || !outcome.ok) throw new Error(outcome.error);
        window.location.assign(form.dataset.success);
      } catch (error) {
        status.textContent = error.name === 'NotAllowedError' ? 'Verification was cancelled or timed out. Try again or use another method.' : 'Passkey verification failed. Confirm your password and device, then try again or use another method.';
      } finally { button.disabled = false; }
    });
  }
})();
