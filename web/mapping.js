
'use strict';
(() => {
  const form = document.getElementById('lookup-form');
  const set = (id, value) => { document.getElementById(id).textContent = value; };
  const payload = (id, value) => set(id, JSON.stringify(value, null, 2));
  function render() {
    const component = form.elements.component.value;
    const isA = component === 'COMPONENT_A';
    const name = isA ? 'Component A' : 'Component B';
    const merchant = 'merchant-1001';
    set('mapping-context', `${name} · ${form.elements.mode.value === 'sync' ? 'Synchronous service' : 'Asynchronous worker'} · Active record example`);
    payload('mapping-unified-request', {merchantId: merchant, component});
    payload('mapping-backend-request', isA ? {merchant_id: merchant} : {accountReference: merchant});
    payload('mapping-native-response', isA ? {merchant_id: merchant, status: 'A'} : {accountReference: merchant, enabled: true});
    payload('mapping-unified-response', {merchantId: merchant, component, eligible: true, status: 'ACTIVE'});
    set('mapping-request-title', `${name} request format`);
    set('mapping-response-title', `${name} response format`);
    set('mapping-request-rule', isA ? 'merchantId → merchant_id. The routing field component is omitted from the backend body.' : 'merchantId → accountReference. The routing field component is omitted from the backend body.');
    set('mapping-native-rule', isA ? 'The backend represents account activity with status codes A and I.' : 'The backend represents account activity with the boolean enabled.');
    set('mapping-response-rule', isA ? 'merchant_id → merchantId; status A → eligible true and status ACTIVE. The adapter adds component.' : 'accountReference → merchantId; enabled true → eligible true and status ACTIVE. The adapter adds component.');
    set('mapping-rules', isA ? 'A → eligible: true, status: ACTIVE. I → eligible: false, status: INACTIVE. Any other status is rejected by the adapter.' : 'true → eligible: true, status: ACTIVE. false → eligible: false, status: INACTIVE. A non-boolean enabled value is rejected by the adapter.');
  }
  form.addEventListener('change', render);
  render();
})();
