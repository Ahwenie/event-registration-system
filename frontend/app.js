// ============================================
// CONFIGURATION
// ============================================
const API_BASE_URL = 'https://fmojrogkrf.execute-api.us-east-1.amazonaws.com/Prod';

// Event images mapping (using Unsplash)
const EVENT_IMAGES = {
    'cloud-tech-summit': 'https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=400&h=200&fit=crop',
    'ash-techie-Kumasi-2026': 'https://images.unsplash.com/photo-1523580494863-6f3031224c94?w=400&h=200&fit=crop',
    'default': 'https://images.unsplash.com/photo-1505373877841-8d25f7d46678?w=400&h=200&fit=crop'
};

// ============================================
// DOM ELEMENTS
// ============================================
const registrationForm = document.getElementById('registrationForm');
const eventSelect = document.getElementById('eventSelect');
const eventsList = document.getElementById('eventsList');
const messageBox = document.getElementById('messageBox');
const submitBtn = document.getElementById('submitBtn');
const btnText = submitBtn.querySelector('.btn-text');
const btnLoader = submitBtn.querySelector('.btn-loader');
const eventCountEl = document.getElementById('eventCount');

// ============================================
// UTILITY FUNCTIONS
// ============================================
function showMessage(text, type) {
    messageBox.innerHTML = text;
    messageBox.className = `message-box ${type}`;
    messageBox.classList.remove('hidden');
    
    setTimeout(() => {
        messageBox.classList.add('hidden');
    }, 6000);
}

function formatDate(dateString) {
    const options = { year: 'numeric', month: 'long', day: 'numeric' };
    return new Date(dateString).toLocaleDateString('en-US', options);
}

function setLoading(isLoading) {
    submitBtn.disabled = isLoading;
    btnText.classList.toggle('hidden', isLoading);
    btnLoader.classList.toggle('hidden', !isLoading);
}

function getEventImage(eventId) {
    return EVENT_IMAGES[eventId] || EVENT_IMAGES['default'];
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================
// API FUNCTIONS
// ============================================
async function fetchEvents() {
    try {
        const response = await fetch(`${API_BASE_URL}/events`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        const parsedBody = typeof data.body === 'string' ? JSON.parse(data.body) : data;
        
        return parsedBody.events || [];
        
    } catch (error) {
        console.error('Error fetching events:', error);
        showMessage('Failed to load events. Please refresh the page.', 'error');
        return [];
    }
}

async function submitRegistration(registrationData) {
    const response = await fetch(`${API_BASE_URL}/registrations`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(registrationData)
    });
    
    const data = await response.json();
    const parsedBody = typeof data.body === 'string' ? JSON.parse(data.body) : data;
    
    return {
        status: response.status,
        data: parsedBody
    };
}

// ============================================
// RENDER FUNCTIONS
// ============================================
function renderEvents(events) {
    // Update stats
    eventCountEl.textContent = events.length;
    
    if (events.length === 0) {
        eventsList.innerHTML = '<p class="loading">No events available at the moment.</p>';
        return;
    }
    
    eventsList.innerHTML = events.map((event, index) => {
        const isSoldOut = event.status === 'Sold Out';
        const statusClass = event.status === 'Available' ? 'status-available' 
                          : event.status === 'Limited' ? 'status-limited' 
                          : 'status-sold-out';
        
        const imageUrl = getEventImage(event.eventId);
        
        return `
            <div class="event-card ${isSoldOut ? 'sold-out' : ''}" style="animation-delay: ${index * 0.1}s">
                <img src="${imageUrl}" alt="${escapeHtml(event.eventName)}" class="event-image" loading="lazy">
                <div class="event-content">
                    <div class="event-name">${escapeHtml(event.eventName)}</div>
                    <div class="event-meta">
                        <span><i class="far fa-calendar"></i> ${formatDate(event.eventDate)}</span>
                        <span><i class="fas fa-map-marker-alt"></i> ${escapeHtml(event.location)}</span>
                    </div>
                    <div class="seats-info">
                        <span class="seats-count">
                            ${isSoldOut ? '<i class="fas fa-times-circle"></i> No seats left' : `<i class="fas fa-chair"></i> ${event.availableSeats} of ${event.totalSeats} seats left`}
                        </span>
                        <span class="status-badge ${statusClass}">${event.status}</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function populateEventSelect(events) {
    const availableEvents = events.filter(e => e.status !== 'Sold Out');
    
    if (availableEvents.length === 0) {
        eventSelect.innerHTML = '<option value="">No events available</option>';
        return;
    }
    
    eventSelect.innerHTML = `
        <option value="">Select an event...</option>
        ${availableEvents.map(event => `
            <option value="${event.eventId}">${escapeHtml(event.eventName)} - ${formatDate(event.eventDate)}</option>
        `).join('')}
    `;
}

// ============================================
// EVENT LISTENERS
// ============================================
registrationForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = {
        eventId: document.getElementById('eventSelect').value,
        email: document.getElementById('email').value.trim(),
        fullName: document.getElementById('fullName').value.trim()
    };
    
    if (!formData.eventId) {
        showMessage('Please select an event from the dropdown.', 'error');
        return;
    }
    
    if (!formData.email.includes('@') || !formData.email.includes('.', formData.email.indexOf('@'))) {
        showMessage('Please enter a valid email address.', 'error');
        return;
    }
    
    setLoading(true);
    
    try {
        const result = await submitRegistration(formData);
        
        if (result.status === 201) {
            showMessage(`✅ Registration successful! ${result.data.message} Your registration ID: ${result.data.registrationId}`, 'success');
            registrationForm.reset();
            await init();
        } else if (result.status === 409) {
            showMessage(`⚠️ ${result.data.error || 'This event is sold out. Please try another event.'}`, 'error');
        } else {
            showMessage(`❌ ${result.data.error || 'Registration failed. Please try again.'}`, 'error');
        }
        
    } catch (error) {
        console.error('Registration error:', error);
        showMessage('Network error. Please check your connection and try again.', 'error');
    } finally {
        setLoading(false);
    }
});

// ============================================
// INITIALIZATION
// ============================================
async function init() {
    const events = await fetchEvents();
    renderEvents(events);
    populateEventSelect(events);
}

document.addEventListener('DOMContentLoaded', init);