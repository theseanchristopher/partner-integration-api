'use strict';
(() => {
  const form = document.getElementById('lookup-form');
  const set = (id, value) => {
    document.getElementById(id).textContent = value;
  };
  const payload = (id, value) => set(id, JSON.stringify(value, null, 2));

  function render() {
    const component = form.elements.component.value;
    const isA = component === 'COMPONENT_A';
    const name = isA ? 'Component A' : 'Component B';
    const merchant = 'merchant-1001';
    const mode = form.elements.mode.value === 'sync'
      ? 'Synchronous service' : 'Asynchronous worker';

    set('mapping-context', `${name} · ${mode} · Active record example`);

    payload('mapping-unified-request', {
      merchantId: merchant,
      component
    });

    payload('mapping-backend-request', isA
      ? {merchant_id: merchant}
      : {accountReference: merchant}
    );

    payload('mapping-native-response', isA ? {
      merchant_id: merchant,
      status: 'A',
      country_code: 'US',
      capability_codes: ['CARD'],
      onboarding_code: 'C',
      required_items: []
    } : {
      accountReference: merchant,
      enabled: true,
      profile: {country: 'US'},
      capabilities: {cardAcceptance: true},
      onboarding: {complete: true, requirements: []}
    });

    payload('mapping-unified-response', {
      merchantId: merchant,
      component,
      eligible: true,
      status: 'ACTIVE',
      country: 'US',
      capabilities: ['CARD_ACCEPTANCE'],
      onboarding: {status: 'COMPLETE', requirements: []}
    });

    set('mapping-request-title', `${name} request format`);
    set('mapping-response-title', `${name} response format`);

    set('mapping-request-rule', isA
      ? 'merchantId → merchant_id. The component field selects the destination and is omitted from its request body.'
      : 'merchantId → accountReference. The component field selects the destination and is omitted from its request body.'
    );

    set('mapping-native-rule', isA
      ? 'Flat native fields use status A/I, capability code CARD, and onboarding code C/P.'
      : 'Nested objects represent country, capability flags, and onboarding completion.'
    );

    set('mapping-response-rule', isA
      ? 'Rename merchant_id and country_code; translate CARD → CARD_ACCEPTANCE; group onboarding_code and required_items into onboarding.'
      : 'Rename accountReference; extract profile.country; convert capability flags into a list; translate onboarding.complete into a status.'
    );

    set('mapping-rules', isA
      ? 'A/I → ACTIVE/INACTIVE and eligible true/false. CARD → CARD_ACCEPTANCE. C/P → COMPLETE/PENDING. Unsupported codes are rejected.'
      : 'enabled true/false → ACTIVE/INACTIVE and eligible true/false. cardAcceptance true → CARD_ACCEPTANCE; false → an empty list. complete true/false → COMPLETE/PENDING. Boolean fields must contain actual booleans.'
    );
  }

  form.addEventListener('change', render);
  render();
})();
