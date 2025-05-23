// Fetch CSRF token for security
fetch('/api/csrf-token')
  .then(res => res.json())
  .then(data => document.getElementById('csrf_token').value = data.csrf_token);

// Lead Form Submission
document.getElementById('lead-form').addEventListener('submit', async e => {
  e.preventDefault();
  const data = {
    first_name: document.getElementById('first-name').value,
    last_name: document.getElementById('last-name').value,
    email: document.getElementById('email').value
  };
  const response = await fetch('/api/leads', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  const result = await response.json();
  document.getElementById('lead-message').textContent = result.message || result.error;
  fetchLeads();
});

// Document Upload Form
document.getElementById('upload-form').addEventListener('submit', async e => {
  e.preventDefault();
  const formData = new FormData();
  formData.append('file', document.getElementById('file').files[0]);
  formData.append('csrf_token', document.getElementById('csrf_token').value);
  const response = await fetch('/api/documents', {
    method: 'POST',
    body: formData
  });
  const result = await response.json();
  document.getElementById('upload-message').textContent = result.message || result.error;
});

// Quote Form Submission
document.getElementById('quote-form').addEventListener('submit', async e => {
  e.preventDefault();
  const items = document.getElementById('items').value.split(',').map(item => {
    const [name, price] = item.split(':');
    return [name, parseFloat(price)];
  });
  const data = {
    contact_id: document.getElementById('contact-id').value,
    items
  };
  const response = await fetch('/api/quotes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  const result = await response.json();
  document.getElementById('quote-message').textContent = result.message || result.error;
  fetchQuotes();
});

// Schedule Form Submission
document.getElementById('schedule-form').addEventListener('submit', async e => {
  e.preventDefault();
  const data = {
    contact_id: document.getElementById('sched-contact-id').value,
    date: document.getElementById('sched-date').value,
    type: document.getElementById('sched-type').value
  };
  const response = await fetch('/api/schedule', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  const result = await response.json();
  document.getElementById('schedule-message').textContent = result.message || result.error;
});

// Fetch Leads
async function fetchLeads() {
  const response = await fetch('/api/leads');
  const leads = await response.json();
  const leadsDiv = document.getElementById('leads');
  leadsDiv.innerHTML = leads.map(lead => `<div>${lead.properties.firstname} ${lead.properties.lastname}</div>`).join('');
}

// Fetch Quotes
async function fetchQuotes() {
  const response = await fetch('/api/quotes');
  const quotes = await response.json();
  const quotesDiv = document.getElementById('quotes');
  quotesDiv.innerHTML = quotes.map(q => `<div>Quote ${q.id} (v${q.version})</div>`).join('');
}

// Initial Load
fetchLeads();
fetchQuotes();